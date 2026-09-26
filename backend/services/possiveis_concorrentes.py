"""Possíveis concorrentes de um edital: empresas que venceram contratações com objeto parecido no PNCP.

Fontes (APIs públicas do PNCP):
- contratos publicados com objeto semelhante -> fornecedor contratado (niFornecedor / nomeRazaoSocialFornecedor);
- atas de registro de preços e compras semelhantes -> fornecedores homologados nos itens (resultados por item).

A pontuação combina quantas vezes a empresa venceu, a semelhança do objeto, a mesma UF do edital e a data.
É um indicativo de quem costuma disputar esse tipo de objeto, não uma lista de quem vai participar.
"""
import logging
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

from services import pncp

log = logging.getLogger(__name__)

MAX_TERMOS = 3
CONTRATOS_POR_TERMO = 20
ATAS_POR_TERMO = 10
MAX_DETALHES = 30       # consultas de detalhe (contrato ou itens de ata) por busca
MAX_RESULTADO = 15
PRAZO_TOTAL_S = 100     # a busca inteira não passa disso

_VAZIAS = set("""a o as os de da do das dos e em no na nos nas para por com sem ao aos um uma uns umas que se sua seu suas seus
ou pela pelo pelas pelos entre sob sobre conforme atraves demais mediante eventual eventuais futura futuras futuro futuros
contratacao contratacoes empresa empresas especializada especializado especializadas prestacao servico servicos
aquisicao aquisicoes fornecimento registro precos preco objeto presente licitacao pregao eletronico edital item itens lote lotes
municipio municipal prefeitura secretaria estado estadual federal orgao unidade unidades atender atendimento necessidades
demanda demandas destinados destinado destinada destinadas visando tipo menor global unitario valor estimado anexo termo
referencia condicoes quantidades quantidade especificacoes estabelecidas constantes incluindo inclusive bem bens
durante periodo meses mes ano anos exercicio continuos continuo continuada continuadas execucao""".split())


def _norm(t):
    t = unicodedata.normalize("NFKD", str(t or "").lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def palavras(texto):
    return [w for w in re.findall(r"[a-z0-9]{3,}", _norm(texto)) if w not in _VAZIAS and not w.isdigit()]


def _raiz(w):
    return w[:6]  # aproximação barata de radical: "limpeza"/"limpezas", "manutencao"/"manutencoes"


def semelhanca(objeto_edital, objeto_outro):
    a = {_raiz(w) for w in palavras(objeto_edital)}
    b = {_raiz(w) for w in palavras(objeto_outro)}
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), 8)


def termos_de_busca(edital, extracao=None):
    """Termos sugeridos pela IA na extração (quando houver) e, em seguida, o núcleo do objeto."""
    termos = []
    for t in (extracao or {}).get("termos_busca_pncp") or []:
        t = " ".join(str(t).split())[:60]
        if len(t) >= 4 and t.lower() not in (x.lower() for x in termos):
            termos.append(t)
    nucleo = palavras(edital.objeto)
    if nucleo:
        for t in (" ".join(nucleo[:3]), " ".join(nucleo[:2])):
            if t and t.lower() not in (x.lower() for x in termos):
                termos.append(t)
    return termos[:MAX_TERMOS]


def _data(v):
    try:
        return datetime.fromisoformat(str(v).replace("Z", "")[:19]) if v else None
    except ValueError:
        return None


def _peso_data(d):
    if not d:
        return 0.6
    anos = (datetime.utcnow() - d).days / 365
    return 1.0 if anos <= 1 else 0.8 if anos <= 2 else 0.6 if anos <= 4 else 0.4


def buscar(edital, extracao=None, cnpjs_proprios=(), monitorados=None, etapa=None):
    """Monta a lista de possíveis concorrentes. `monitorados` = {cnpj: id do Concorrente} da conta."""
    inicio = datetime.utcnow()
    limite = inicio + timedelta(seconds=PRAZO_TOTAL_S)
    termos = termos_de_busca(edital, extracao)
    if not termos:
        return {"status": "concluida", "itens": [], "termos": [], "consultado_em": inicio.isoformat(),
                "aviso": "O edital ainda não tem objeto. Analise o edital ou preencha o objeto para buscar concorrentes."}
    proprios = {re.sub(r"\D", "", c or "") for c in cnpjs_proprios}

    # 1) documentos parecidos
    documentos, falhas = {}, 0
    for termo in termos:
        for tipo, n in (("contrato", CONTRATOS_POR_TERMO), ("ata", ATAS_POR_TERMO)):
            if datetime.utcnow() > limite:
                break
            try:
                for d in pncp.buscar_documentos(termo, tipo, n):
                    if d.get("numero_controle") and d["numero_controle"] not in documentos:
                        d["semelhanca"] = semelhanca(edital.objeto, d.get("objeto"))
                        documentos[d["numero_controle"]] = d
            except Exception as e:
                falhas += 1
                log.warning("Busca de %s no PNCP falhou (%s): %s", tipo, termo, e)
    if etapa:
        etapa(f"Consultando os vencedores de {len(documentos)} contratação(ões) semelhante(s)")
    # os mais parecidos primeiro; descarta os que não têm nada a ver com o objeto
    candidatos = sorted((d for d in documentos.values() if d["semelhanca"] > 0),
                        key=lambda d: (-d["semelhanca"], -(_data(d.get("data")) or datetime.min).timestamp()))[:MAX_DETALHES]

    # 2) quem venceu cada um (em paralelo, com tempo limitado)
    def vencedores(doc):
        if doc["tipo"] == "contrato":
            f = pncp.fornecedor_do_contrato(doc["numero_controle"])
            return doc, [f] if f else []
        return doc, pncp.vencedores_da_compra(doc.get("numero_controle_compra") or doc["numero_controle"])

    empresas = {}
    restante = max(10, (limite - datetime.utcnow()).total_seconds())
    with ThreadPoolExecutor(max_workers=6) as ex:
        futuros = [ex.submit(vencedores, d) for d in candidatos]
        try:
            for fut in as_completed(futuros, timeout=restante):
                try:
                    doc, lista = fut.result()
                except Exception as e:
                    log.info("Detalhe PNCP falhou: %s", e)
                    continue
                for f in lista:
                    if f["cnpj"] in proprios:
                        continue
                    e = empresas.setdefault(f["cnpj"], {"cnpj": f["cnpj"], "nome": "", "vitorias": 0, "contratos": 0, "atas": 0,
                                                         "valor_total": 0.0, "ufs": set(), "orgaos": {}, "ultima_data": None,
                                                         "pontos": 0.0, "exemplos": []})
                    e["nome"] = e["nome"] or (f.get("nome") or "").strip()
                    e["vitorias"] += 1
                    e["contratos" if doc["tipo"] == "contrato" else "atas"] += 1
                    e["valor_total"] += float(f.get("valor") or doc.get("valor") or 0)
                    uf = (f.get("uf") or doc.get("uf") or "").upper()
                    if uf:
                        e["ufs"].add(uf)
                    orgao = f.get("orgao") or doc.get("orgao") or ""
                    if orgao:
                        e["orgaos"][orgao] = e["orgaos"].get(orgao, 0) + 1
                    dt = _data(f.get("data") or doc.get("data"))
                    if dt and (not e["ultima_data"] or dt > e["ultima_data"]):
                        e["ultima_data"] = dt
                    mesma_uf = bool(edital.uf and uf == edital.uf.upper())
                    e["pontos"] += (0.4 + doc["semelhanca"]) * _peso_data(dt) * (1.35 if mesma_uf else 1.0)
                    mesmo_orgao = bool(edital.orgao and orgao and _norm(orgao) == _norm(edital.orgao))
                    if mesmo_orgao:
                        e["pontos"] += 0.8
                        e["mesmo_orgao"] = True
                    partes = pncp.partes_controle(doc.get("numero_controle_compra") or doc["numero_controle"])
                    e["exemplos"].append({"tipo": doc["tipo"], "objeto": (f.get("objeto") or doc.get("objeto") or "")[:300],
                                          "orgao": orgao, "uf": uf, "data": dt.date().isoformat() if dt else None,
                                          "valor": f.get("valor") or doc.get("valor"), "semelhanca": round(doc["semelhanca"], 2),
                                          "link": f"https://pncp.gov.br/app/editais/{partes[0]}/{partes[1]}/{partes[2]}" if partes else None})
        except Exception:  # tempo esgotado: fica com o que já chegou
            log.info("Busca de possíveis concorrentes parou no tempo limite (%s documentos)", len(candidatos))

    itens = []
    for e in sorted(empresas.values(), key=lambda x: -x["pontos"])[:MAX_RESULTADO]:
        e["exemplos"].sort(key=lambda x: (-x["semelhanca"], -int((x["data"] or "0").replace("-", ""))))
        itens.append({
            "cnpj": e["cnpj"], "nome": e["nome"] or "Razão social não informada no PNCP",
            "vitorias": e["vitorias"], "contratos": e["contratos"], "atas": e["atas"],
            "valor_total": round(e["valor_total"], 2) or None, "ufs": sorted(e["ufs"]),
            "mesma_uf": bool(edital.uf and edital.uf.upper() in e["ufs"]), "mesmo_orgao": bool(e.get("mesmo_orgao")),
            "orgaos": [o for o, _ in sorted(e["orgaos"].items(), key=lambda x: -x[1])[:3]],
            "ultima_data": e["ultima_data"].date().isoformat() if e["ultima_data"] else None,
            "pontuacao": round(e["pontos"], 2), "exemplos": e["exemplos"][:3],
            "concorrente_id": (monitorados or {}).get(e["cnpj"]),
        })
    maior = itens[0]["pontuacao"] if itens else 1
    for it in itens:
        r = it["pontuacao"] / maior if maior else 0
        it["relevancia"] = "alta" if r >= 0.6 or it["mesmo_orgao"] else "media" if r >= 0.3 else "baixa"
    saida = {"status": "concluida", "itens": itens, "termos": termos, "consultado_em": inicio.isoformat(),
             "documentos_analisados": len(candidatos), "documentos_encontrados": len(documentos)}
    if not itens:
        saida["pncp_indisponivel"] = bool(falhas and not documentos)
        saida["aviso"] = ("O PNCP não respondeu agora. Nada foi descontado do seu plano; tente de novo em alguns minutos." if falhas and not documentos else
                          "Não encontramos contratações anteriores com objeto parecido no PNCP.")
    return saida


def atualizar(edital, extracao=None, etapa=None):
    """Busca e grava em edital.possiveis_concorrentes (não faz commit). Nunca levanta erro: falhas viram aviso."""
    from models import Concorrente, Empresa
    empresa = Empresa.query.get(edital.empresa_id)
    conta_id = empresa.conta_id if empresa else None
    proprios = [e.cnpj for e in Empresa.query.filter_by(conta_id=conta_id)] if conta_id else []
    monitorados = {c.cnpj: c.id for c in Concorrente.query.filter_by(conta_id=conta_id)} if conta_id else {}
    try:
        r = buscar(edital, extracao, proprios, monitorados, etapa)
    except Exception as e:
        log.exception("Falha ao buscar possíveis concorrentes do edital %s", edital.id)
        anterior = edital.possiveis_concorrentes or {}
        r = {**anterior, "status": "erro", "erro": "Não foi possível consultar o PNCP agora. Nada foi descontado do seu plano; tente de novo em alguns minutos.",
             "itens": anterior.get("itens") or []}
    edital.possiveis_concorrentes = r
    return r
