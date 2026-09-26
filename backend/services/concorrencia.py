"""Dossiê completo do concorrente: coleta (PNCP + acervo enviado + análises anteriores), leitura de cada
documento pela IA e consolidação num perfil usado nas análises de habilitação/proposta e nas peças."""
import re
from datetime import datetime

from extensions import db
from models import AnaliseConcorrente, DocumentoConcorrente, Edital
from services import arquivos, fluxos, kb, llm, pncp
from services.fluxos import cortar
from services.prompts import BASE, _j

TIPOS_DOC = {"ata": "Ata de sessão / julgamento", "decisao": "Decisão de recurso ou diligência", "habilitacao": "Documentos de habilitação",
             "proposta": "Proposta / planilha", "atestado": "Atestado de capacidade técnica", "balanco": "Balanço / demonstrações contábeis",
             "certidao": "Certidão", "outro": "Outro"}
LIMITE_COMPRAS_PNCP = 8
LIMITE_DOCS_PNCP = 12


def _menciona(texto, conc):
    """O documento fala do concorrente? (CNPJ com ou sem máscara, ou 2+ palavras marcantes da razão social)."""
    t = texto or ""
    c = conc.cnpj
    if c in re.sub(r"\D", "", t) or f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}" in t:
        return True
    palavras = [w for w in re.findall(r"[A-Za-zÀ-ú]{4,}", conc.razao_social or "")
                if w.lower() not in ("ltda", "eireli", "servicos", "serviços", "comercio", "comércio", "empresa", "limitada")]
    return len(palavras) >= 2 and all(w.lower() in t.lower() for w in palavras[:3])


# ---------------------------------------------------------------- coleta automática no PNCP
def coletar_pncp(conc, etapa=lambda t: None):
    """Parte dos contratos do concorrente no PNCP, chega à compra de origem e baixa atas/julgamentos/decisões
    que mencionem o CNPJ. Melhor esforço: órgãos nem sempre publicam esses documentos."""
    historico = (conc.dossie or {}).get("historico_pncp") or []
    ja = {d.fonte_url for d in DocumentoConcorrente.query.filter_by(concorrente_id=conc.id) if d.fonte_url}
    compras, novos = [], 0
    for h in historico:
        nc = h.get("numero_controle") or ""
        if "-1-" in nc:
            compras.append((nc, h))
        elif "-2-" in nc:
            compra = pncp.compra_do_contrato(nc)
            if compra:
                compras.append((compra, h))
        if len(compras) >= LIMITE_COMPRAS_PNCP:
            break
    vistos = set()
    for i, (nc, h) in enumerate(compras, start=1):
        if nc in vistos:
            continue
        vistos.add(nc)
        etapa(f"Procurando atas e decisões no PNCP ({i}/{len(compras)})")
        for doc in pncp.documentos_de_julgamento(nc):
            if doc["url"] in ja or not _menciona(doc["texto"], conc):
                continue
            caminho = arquivos.salvar_bytes(doc["conteudo"], f"concorrentes/{conc.conta_id}/acervo")
            db.session.add(DocumentoConcorrente(
                concorrente_id=conc.id, conta_id=conc.conta_id, origem="pncp", tipo="ata", titulo=doc["titulo"],
                orgao=h.get("orgao"), certame=nc, arquivo=caminho, nome_arquivo=f"{doc['titulo'][:80]}.pdf",
                fonte_url=doc["url"], texto=doc["texto"], status="pendente",
                data_documento=_data(doc.get("data"))))
            ja.add(doc["url"])
            novos += 1
            if novos >= LIMITE_DOCS_PNCP:
                db.session.commit()
                return novos
        db.session.commit()
    return novos


def _data(v):
    try:
        return datetime.fromisoformat(str(v)[:10]).date() if v else None
    except ValueError:
        return None


# ---------------------------------------------------------------- leitura de cada documento (IA barata)
def prompt_documento(doc, conc):
    sistema = BASE + (" Você lê documentos de licitações e extrai APENAS o que diz respeito a uma empresa específica "
                      "(a concorrente), sem opinar.")
    usuario = f"""EMPRESA CONCORRENTE: {conc.razao_social or ''} — CNPJ {conc.cnpj}
TIPO INFORMADO DO DOCUMENTO: {TIPOS_DOC.get(doc.tipo, doc.tipo)}
ÓRGÃO/CERTAME INFORMADOS: {doc.orgao or '-'} / {doc.certame or '-'}

Extraia em JSON:
{{"menciona_a_concorrente": true, "tipo_documento": "", "orgao": "", "certame": "", "data": "AAAA-MM-DD ou null", "resumo": "",
 "resultado_da_concorrente": "vencedora|habilitada|inabilitada|desclassificada|recorreu|recorrida|nao_informado",
 "inabilitacoes_ou_desclassificacoes": [{{"fase": "habilitacao|proposta|outra", "motivo": "", "fundamento": "", "decisao_final": "", "pagina": ""}}],
 "atestados": [{{"emissor": "", "objeto": "", "quantitativo": "", "periodo": "", "pagina": ""}}],
 "dados_contabeis": {{"exercicio": "", "ativo_circulante": null, "passivo_circulante": null, "ativo_total": null, "passivo_nao_circulante": null,
   "patrimonio_liquido": null, "liquidez_geral": null, "liquidez_corrente": null, "solvencia_geral": null, "pagina": ""}},
 "certidoes": [{{"tipo": "", "validade": "AAAA-MM-DD ou null", "situacao": "", "pagina": ""}}],
 "responsaveis_tecnicos": [{{"nome": "", "registro": "", "pagina": ""}}],
 "fatos_relevantes": [""]}}
Se o documento não tratar da concorrente, devolva "menciona_a_concorrente": false e listas vazias.
Números sem símbolo de moeda, com ponto decimal. Indique a página ([pág. N]).

DOCUMENTO:
{cortar(doc.texto, 120000)}"""
    demo = {"menciona_a_concorrente": True, "tipo_documento": "Ata de julgamento", "orgao": doc.orgao or "Prefeitura de Exemplo",
            "certame": doc.certame or "PE 12/2025", "data": None,
            "resumo": "A concorrente foi inabilitada por apresentar atestado sem o quantitativo mínimo exigido.",
            "resultado_da_concorrente": "inabilitada",
            "inabilitacoes_ou_desclassificacoes": [{"fase": "habilitacao", "motivo": "Atestado com 40% do quantitativo mínimo (exigido 50%)",
                                                    "fundamento": "Item 9.4 do edital; Lei 14.133, art. 67", "decisao_final": "Mantida após recurso", "pagina": "3"}],
            "atestados": [{"emissor": "Município de Exemplo", "objeto": "Limpeza predial", "quantitativo": "4.000 m²", "periodo": "2023-2024", "pagina": "5"}],
            "dados_contabeis": {"exercicio": "2024", "liquidez_geral": 1.08, "liquidez_corrente": 0.97, "solvencia_geral": 1.3, "patrimonio_liquido": 180000},
            "certidoes": [], "responsaveis_tecnicos": [], "fatos_relevantes": ["Liquidez corrente abaixo de 1 no exercício de 2024"]}
    return sistema, usuario, demo


def ler_documento(doc, conc):
    s, u, demo = prompt_documento(doc, conc)
    r = llm.chamar("barata", s, u, max_tokens=4000, demo=demo)
    d = llm.extrair_json(r.texto)
    doc.extracao = d
    doc.status = "lido" if d.get("menciona_a_concorrente", True) else "sem_mencao"
    doc.orgao = doc.orgao or (d.get("orgao") or "")[:300] or None
    doc.certame = doc.certame or (d.get("certame") or "")[:200] or None
    doc.data_documento = doc.data_documento or _data(d.get("data"))
    return r


# ---------------------------------------------------------------- consolidação do perfil
def _material(conc):
    docs = [d for d in DocumentoConcorrente.query.filter_by(concorrente_id=conc.id).order_by(DocumentoConcorrente.id)
            if d.status == "lido"]
    analises = AnaliseConcorrente.query.filter_by(concorrente_id=conc.id).order_by(AnaliseConcorrente.id.desc()).limit(15).all()
    eds = {e.id: e for e in Edital.query.filter(Edital.id.in_([a.edital_id for a in analises])).all()} if analises else {}
    return docs, analises, eds


def prompt_consolidacao(conc, docs, analises, eds):
    dossie = conc.dossie or {}
    rec = dossie.get("receita") or {}
    base_publica = {"receita": {k: rec.get(k) for k in ("razao_social", "situacao", "abertura", "capital_social", "porte", "cnaes", "socios")},
                    "sancoes_tcu": (dossie.get("sancoes_tcu") or {}).get("certidoes"),
                    "sancoes_cgu": (dossie.get("sancoes_cgu") or {}).get("registros"),
                    "contratos_pncp": [{k: h.get(k) for k in ("tipo", "orgao", "objeto", "valor", "uf", "data")}
                                       for h in (dossie.get("historico_pncp") or [])[:20]]}
    acervo = [{"fonte": f"doc#{d.id}", "tipo": d.tipo, "orgao": d.orgao, "certame": d.certame,
               "data": d.data_documento.isoformat() if d.data_documento else None, **(d.extracao or {})} for d in docs[:40]]
    anteriores = [{"fonte": f"analise#{a.id}", "tipo": a.tipo, "edital": (eds.get(a.edital_id).numero or eds.get(a.edital_id).objeto or "")[:120] if eds.get(a.edital_id) else None,
                   "data": a.criado_em.date().isoformat() if a.criado_em else None, "resumo": (a.resultado or {}).get("resumo"),
                   "apontamentos": [{k: ap.get(k) for k in ("tema", "descricao", "fundamento", "forca")} for ap in (a.resultado or {}).get("apontamentos", [])][:12]}
                  for a in analises]
    contexto = kb.buscar("habilitação inabilitação atestado índices contábeis recurso diligência sanções impedimento "
                         "capacidade técnica qualificação econômico-financeira", k=5)
    sistema = BASE + (" Você monta o DOSSIÊ de uma empresa concorrente para quem vai disputar licitações contra ela. "
                      "Consolide os fatos das fontes, sem inventar nada: todo item deve citar a fonte (doc#N, analise#N ou "
                      "'dados públicos'). Identifique padrões de falha e, com base neles, onde a concorrente costuma ser "
                      "vulnerável em habilitação e proposta, sempre com o que deve ser conferido nos próximos certames.")
    usuario = f"""CONCORRENTE: {conc.razao_social or ''} — CNPJ {conc.cnpj}
DADOS PÚBLICOS: {_j(base_publica)}
ACERVO (documentos de outros certames lidos pela IA): {_j(acervo)}
ANÁLISES ANTERIORES DESTE CONCORRENTE NO KASISKI: {_j(anteriores)}
REFERÊNCIAS LEGAIS:
{contexto}

Devolva JSON:
{{"resumo": "visão geral em 3 a 5 frases",
 "inabilitacoes": [{{"orgao": "", "certame": "", "data": "", "fase": "habilitacao|proposta|outra", "motivo": "", "desfecho": "", "fonte": ""}}],
 "atestados": [{{"emissor": "", "objeto": "", "quantitativo": "", "periodo": "", "fonte": ""}}],
 "economico": {{"exercicio": "", "patrimonio_liquido": null, "capital_social": null, "liquidez_geral": null, "liquidez_corrente": null,
   "solvencia_geral": null, "observacoes": "", "fonte": ""}},
 "certidoes": [{{"tipo": "", "validade": "", "situacao": "", "fonte": ""}}],
 "responsaveis_tecnicos": [{{"nome": "", "registro": "", "fonte": ""}}],
 "sancoes": [{{"cadastro": "", "descricao": "", "vigencia": "", "fonte": ""}}],
 "fragilidades_recorrentes": [{{"tema": "", "descricao": "", "ocorrencias": 1, "fontes": [""]}}],
 "pontos_de_ataque": [{{"tema": "", "argumento": "o que pode ser alegado em recurso, contrarrazões, diligência ou representação",
   "como_verificar": "o que conferir nos documentos do próximo certame", "fundamento": "", "forca": "forte|medio|fraco", "fontes": [""]}}],
 "lacunas": ["informação que falta e onde obtê-la (ex.: pedir acesso à ata do PE X via LAI)"]}}"""
    demo = {"resumo": f"{conc.razao_social or 'A concorrente'} tem histórico de inabilitação por qualificação técnica e índices de liquidez no limite. "
                      "Os contratos públicos encontrados são de porte menor que o exigido em editais maiores.",
            "inabilitacoes": [{"orgao": "Prefeitura de Exemplo", "certame": "PE 12/2025", "data": "2025-05-10", "fase": "habilitacao",
                               "motivo": "Atestado com 40% do quantitativo mínimo", "desfecho": "Mantida após recurso", "fonte": "doc#1"}],
            "atestados": [{"emissor": "Município de Exemplo", "objeto": "Limpeza predial", "quantitativo": "4.000 m²", "periodo": "2023-2024", "fonte": "doc#1"}],
            "economico": {"exercicio": "2024", "liquidez_geral": 1.08, "liquidez_corrente": 0.97, "solvencia_geral": 1.3, "patrimonio_liquido": 180000,
                          "observacoes": "Liquidez corrente abaixo de 1", "fonte": "doc#1"},
            "certidoes": [], "responsaveis_tecnicos": [], "sancoes": [],
            "fragilidades_recorrentes": [{"tema": "Qualificação técnica", "descricao": "Atestados abaixo dos quantitativos mínimos", "ocorrencias": 1, "fontes": ["doc#1"]}],
            "pontos_de_ataque": [{"tema": "Atestados", "argumento": "Verificar se os atestados apresentados somam o quantitativo mínimo; há precedente de inabilitação pelo mesmo motivo.",
                                  "como_verificar": "Somar os quantitativos e conferir se são do mesmo objeto e período", "fundamento": "Lei 14.133, art. 67, II e §1º",
                                  "forca": "forte", "fontes": ["doc#1"]},
                                 {"tema": "Liquidez corrente", "argumento": "Índice abaixo de 1 no último balanço conhecido; se o edital exigir LC ≥ 1, conferir o balanço novo.",
                                  "como_verificar": "Recalcular LC = AC/PC do balanço apresentado", "fundamento": "Lei 14.133, art. 69", "forca": "medio", "fontes": ["doc#1"]}],
            "lacunas": ["Balanço mais recente não localizado; pedir cópia no próximo certame em que ela for habilitada"]}
    return sistema, usuario, demo


def consolidar(conc):
    docs, analises, eds = _material(conc)
    s, u, demo = prompt_consolidacao(conc, docs, analises, eds)
    r = llm.chamar("analise", s, u, max_tokens=6000, demo=demo)
    perfil = llm.extrair_json(r.texto)
    perfil["fontes"] = {"documentos": len(docs), "analises": len(analises),
                        "contratos_pncp": len((conc.dossie or {}).get("historico_pncp") or [])}
    conc.perfil, conc.perfil_em, conc.perfil_status, conc.perfil_etapa, conc.perfil_erro = perfil, datetime.utcnow(), "pronto", None, None
    return r


def atualizar_completo(conc, buscar_pncp=True):
    """Pipeline do dossiê completo. Devolve as respostas de IA (para registro de custo)."""
    respostas = []

    def etapa(t):
        conc.perfil_etapa = t
        db.session.commit()

    etapa("Consultando Receita, TCU, CGU e o histórico no PNCP")
    dossie, razao = fluxos.montar_dossie(conc.cnpj)
    conc.dossie, conc.razao_social, conc.atualizado_em = dossie, razao or conc.razao_social, datetime.utcnow()
    db.session.commit()
    if buscar_pncp:
        coletar_pncp(conc, etapa)
    pendentes = DocumentoConcorrente.query.filter_by(concorrente_id=conc.id, status="pendente").all()
    for i, d in enumerate(pendentes, start=1):
        etapa(f"Lendo documentos do acervo ({i}/{len(pendentes)})")
        try:
            respostas.append(ler_documento(d, conc))
        except Exception:
            d.status = "erro"
        db.session.commit()
    etapa("Consolidando o dossiê e os pontos de ataque")
    respostas.append(consolidar(conc))
    db.session.commit()
    return respostas


# ---------------------------------------------------------------- uso nas análises
def contexto_para_analise(conc):
    """Versão enxuta do perfil para entrar no prompt da análise de habilitação/proposta."""
    p = conc.perfil or {}
    if not p:
        return None
    return {k: p.get(k) for k in ("resumo", "inabilitacoes", "atestados", "economico", "certidoes", "responsaveis_tecnicos",
                                  "sancoes", "fragilidades_recorrentes", "pontos_de_ataque") if p.get(k)}
