"""Histórico da própria empresa no PNCP: contratos e atas em que ela aparece como fornecedora.

Serve para o painel de vitórias no cadastro e para guardar no cofre os contratos já firmados (base para pedir
atestado de capacidade técnica). O PNCP publica os documentos do ÓRGÃO (contratos, atas); as certidões e demais
documentos de habilitação da empresa não ficam lá, então não há o que puxar deles.
"""
import logging
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from extensions import ErroAPI, db
from services import pncp

log = logging.getLogger(__name__)
VALIDADE_CACHE = timedelta(days=7)
RE_CONTRATO = re.compile(r"^(\d{14})-2-(\d+)/(\d{4})$")
RE_ATA = re.compile(r"^(\d{14})-1-(\d+)/(\d{4})-(\d+)$")


def _ano(v):
    m = re.match(r"(\d{4})", str(v or ""))
    return m.group(1) if m else None


def montar(cnpj, limite=50):
    itens = pncp.historico_fornecedor(cnpj, limite=limite)
    vistos, lista = set(), []
    for it in itens:
        chave = it.get("numero_controle") or (it.get("orgao"), it.get("objeto"), it.get("data"))
        if chave in vistos:
            continue
        vistos.add(chave)
        lista.append(it)
    lista.sort(key=lambda x: str(x.get("data") or ""), reverse=True)
    por_ano = defaultdict(lambda: {"qtd": 0, "valor": 0.0})
    orgaos_qtd, orgaos_valor, ufs = Counter(), Counter(), Counter()
    for it in lista:
        a = _ano(it.get("data"))
        if a:
            por_ano[a]["qtd"] += 1
            por_ano[a]["valor"] += float(it.get("valor") or 0)
        if it.get("orgao"):
            orgaos_qtd[it["orgao"]] += 1
            orgaos_valor[it["orgao"]] += float(it.get("valor") or 0)
        if it.get("uf"):
            ufs[it["uf"]] += 1
    anos = sorted(por_ano)[-6:]
    return {
        "consultado_em": datetime.utcnow().isoformat(timespec="minutes"),
        "contratos": sum(1 for i in lista if i["tipo"] == "contrato"), "atas": sum(1 for i in lista if i["tipo"] == "ata"),
        "valor_total": round(sum(float(i.get("valor") or 0) for i in lista), 2),
        "orgaos_distintos": len(orgaos_qtd), "ufs": [u for u, _ in ufs.most_common(8)],
        "por_ano": [{"ano": a, **por_ano[a]} for a in anos],
        "top_orgaos": [{"orgao": o, "qtd": n, "valor": round(orgaos_valor[o], 2)} for o, n in orgaos_qtd.most_common(6)],
        "itens": [{**i, "pode_guardar": bool(RE_CONTRATO.match(i.get("numero_controle") or "") or RE_ATA.match(i.get("numero_controle") or ""))}
                  for i in lista[:30]],
        "limite_consulta": limite,
    }


def da_empresa(empresa, atualizar=False):
    h = empresa.historico_pncp or {}
    try:
        recente = h.get("consultado_em") and datetime.fromisoformat(h["consultado_em"]) > datetime.utcnow() - VALIDADE_CACHE
    except ValueError:
        recente = False
    if atualizar or not recente:
        h = montar(empresa.cnpj)
        empresa.historico_pncp = h
        db.session.commit()
    return h


def _arquivos(numero_controle):
    m = RE_CONTRATO.match(numero_controle or "")
    if m:
        url = f"{pncp.BASE_PNCP}/orgaos/{m.group(1)}/contratos/{m.group(3)}/{int(m.group(2))}/arquivos"
    else:
        m = RE_ATA.match(numero_controle or "")
        if not m:
            return []
        url = f"{pncp.BASE_PNCP}/orgaos/{m.group(1)}/compras/{m.group(3)}/{int(m.group(2))}/atas/{int(m.group(4))}/arquivos"
    try:
        lista = pncp._get(url, timeout=20) or []
    except Exception as e:
        log.info("Arquivos de %s indisponíveis: %s", numero_controle, e)
        return []
    return [{"titulo": a.get("titulo") or a.get("tipoDocumentoNome") or "Documento", "url": a.get("url") or a.get("uri")}
            for a in lista if (a.get("url") or a.get("uri"))]


def _baixar(url):
    import requests
    r = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0 (compatible; KasiskiBot/1.0)"})
    r.raise_for_status()
    return r.content


def guardar_no_cofre(empresa, numeros, conta, antes_de_salvar=None):
    """Baixa do PNCP o PDF de cada contrato/ata e guarda no cofre (categoria técnica). Devolve {guardados, falhas}."""
    from models import Documento
    from services import arquivos
    h = empresa.historico_pncp or {}
    por_numero = {i.get("numero_controle"): i for i in h.get("itens") or []}
    guardados, falhas = [], []
    for nc in numeros[:5]:
        it = por_numero.get(nc)
        if not it:
            falhas.append({"numero": nc, "erro": "Item não está no histórico consultado."})
            continue
        marca = f"PNCP {nc}"
        if Documento.query.filter(Documento.empresa_id == empresa.id, Documento.descricao.contains(marca)).first():
            falhas.append({"numero": nc, "erro": "Já está no cofre."})
            continue
        pdfs = [a for a in _arquivos(nc)]
        conteudo, nome = None, None
        for a in pdfs:
            try:
                bruto = _baixar(a["url"])
            except Exception as e:
                log.info("Download de %s falhou: %s", nc, e)
                continue
            achados = pncp._pdfs_do_arquivo(bruto, a["titulo"])
            if achados:
                nome, conteudo = achados[0]
                break
        if not conteudo:
            falhas.append({"numero": nc, "erro": "O órgão não publicou o PDF no PNCP (ou ele não abriu)."})
            continue
        if antes_de_salvar:
            antes_de_salvar()  # limite do cofre no plano
        caminho = arquivos.salvar_bytes(conteudo, f"cofre/{empresa.id}", conta=conta)  # respeita o espaço do plano
        tipo = "Ata de registro de preços" if it["tipo"] == "ata" else "Contrato"
        rotulo = "Ata de registro de preços assinada" if it["tipo"] == "ata" else "Contrato firmado"
        doc = Documento(empresa_id=empresa.id, categoria="tecnica",
                        tipo=f"{rotulo} — {(it.get('orgao') or 'órgão público')}"[:120],
                        descricao=(f"{(it.get('objeto') or '')[:400]}\n{marca}. Documento público do contrato já executado pela "
                                   "empresa: use como base para pedir o atestado de capacidade técnica ao órgão."),
                        arquivo=caminho, nome_arquivo=(nome or f"{tipo}.pdf")[:250])
        db.session.add(doc)
        db.session.flush()
        guardados.append({"numero": nc, "documento_id": doc.id})
    db.session.commit()
    if not guardados and falhas and all("Já está" in f["erro"] for f in falhas):
        raise ErroAPI("Esses documentos já estão no cofre.")
    return {"guardados": guardados, "falhas": falhas}
