"""Jornada da licitação: o que falta fazer em cada fase, montado a partir do que o Kasiski já sabe.

A situação de cada etapa é DERIVADA das fontes (análise do edital, Cofre, cronograma e prazos, possíveis
concorrentes, proposta, peças, salas de disputa, contrato). Nada aqui é gravado: se a fonte muda, a Jornada muda.

Fases e etapas:
- preparacao: analise, questionamentos (esclarecimentos e impugnação), mercado, habilitacao, proposta, conferencia
- sessao: disputa, documentos
- pos: recurso, resultado, contratacao

Cada etapa: {id, nome, sub, estado, rotulo, cor, pend, dados}
- estado: feita | atencao | atualizar | bloqueada | "" (não iniciada)
- cor: ok | aviso | erro | neutro (o carimbo da tela)
- pend: quantas pendências conta no total da fase
"""
import re
import unicodedata
from datetime import date, datetime, timedelta

from models import Analise, Contrato, Disputa, Documento, DocumentoLicitacao, Peca, Prazo, Proposta
from services import oportunidades as op
from services.prazos import dia_util

FASE_DA_ETAPA = {"identificada": "preparacao", "em_analise": "preparacao", "decisao": "preparacao", "preparacao": "preparacao",
                 "pronta": "preparacao", "em_disputa": "sessao", "classificada": "sessao", "recurso": "pos",
                 "homologada": "pos", "contratacao": "pos", "contrato_ativo": "pos"}
DEPOIS_DA_PREPARACAO = {"pronta", "em_disputa", "classificada", "recurso", "homologada", "contratacao", "contrato_ativo"}
GANHAS = {"homologada", "contratacao", "contrato_ativo"}
PECAS_QUESTIONAMENTO = {"esclarecimento", "impugnacao"}
PECAS_RECURSO = {"intencao_recurso", "recurso", "contrarrazoes"}


def _norm(t):
    t = unicodedata.normalize("NFKD", str(t or "").lower())
    return re.sub(r"\s+", " ", "".join(c for c in t if not unicodedata.combining(c))).strip()


def _iso(d):
    return d.isoformat() if d else None


def _uteis_ate(hoje, alvo):
    """Dias úteis de hoje (exclusive) até `alvo` (inclusive). Negativo se já passou."""
    if alvo < hoje:
        return -sum(1 for i in range(1, (hoje - alvo).days + 1) if dia_util(date.fromordinal(hoje.toordinal() - i)))
    return sum(1 for i in range(1, (alvo - hoje).days + 1) if dia_util(date.fromordinal(hoje.toordinal() + i)))


def _etapa(id_, nome, sub, estado, rotulo, cor, pend=0, **dados):
    return {"id": id_, "nome": nome, "sub": sub, "estado": estado, "rotulo": rotulo, "cor": cor, "pend": pend, "dados": dados}


# ---------------------------------------------------------------- preparação
def _analise(ed):
    a = Analise.query.filter_by(edital_id=ed.id).order_by(Analise.id.desc()).first()
    concluida = a if a and a.status == "concluida" else \
        Analise.query.filter_by(edital_id=ed.id, status="concluida").order_by(Analise.id.desc()).first()
    return a, concluida


def etapa_analise(ed, ultima, concluida):
    nome, sub = "Análise do edital", "Requisitos, prazos e riscos"
    if ultima and ultima.status == "processando":
        return _etapa("analise", nome, sub, "atencao", "Analisando", "aviso", 0, etapa_atual=ultima.etapa)
    if not concluida:
        if ultima and ultima.status == "erro":
            return _etapa("analise", nome, sub, "atualizar", "Erro na análise", "erro", 1, erro=ultima.erro)
        return _etapa("analise", nome, sub, "", "Não iniciada", "neutro", 1)
    r = concluida.resultado or {}
    rec = r.get("recomendacao") or {}
    riscos = sorted(r.get("riscos") or [], key=lambda x: {"alto": 0, "medio": 1, "baixo": 2}.get(x.get("nivel"), 3))
    return _etapa("analise", nome, sub, "feita", "Concluída", "ok", 0, analise_id=concluida.id,
                  analisada_em=_iso(concluida.concluido_em or concluida.criado_em), resumo=r.get("resumo"),
                  decisao=rec.get("decisao"), justificativa=rec.get("justificativa"), riscos=riscos[:5],
                  proximos_passos=(r.get("proximos_passos") or [])[:6], demonstracao=bool(concluida.demonstracao))


def etapa_questionamentos(ed, concluida, prazos, pecas, hoje):
    nome, sub = "Esclarecimentos e impugnação", "Dúvidas e cláusulas restritivas"
    limites = {p.tipo: p for p in prazos if p.tipo in PECAS_QUESTIONAMENTO}
    prazo = min((p.data for p in limites.values()), default=None)
    pecas_q = [{"id": p.id, "tipo": p.tipo, "titulo": p.titulo, "status": p.status, "criado_em": _iso(p.criado_em)}
               for p in pecas if p.tipo in PECAS_QUESTIONAMENTO]
    base = {"prazo": _iso(prazo), "prazo_fundamento": next((p.fundamento for p in limites.values() if p.data == prazo), None),
            "dias_uteis": _uteis_ate(hoje, prazo.date()) if prazo else None, "pecas": pecas_q}
    if not concluida:
        return _etapa("questionamentos", nome, sub, "bloqueada", "Depois da análise", "neutro", 0, questoes=[], **base)
    questoes = [{"id": c.get("id"), "clausula": c.get("clausula"), "pagina": c.get("pagina"), "por_que": c.get("por_que_restringe"),
                 "fundamento": c.get("fundamento"), "gravidade": c.get("gravidade"),
                 "medida": c.get("medida") if c.get("medida") in PECAS_QUESTIONAMENTO else "esclarecimento"}
                for c in (concluida.resultado or {}).get("clausulas_restritivas") or []]
    questoes.sort(key=lambda q: {"alta": 0, "media": 1, "baixa": 2}.get(q["gravidade"], 3))
    base.update(questoes=questoes, analise_id=concluida.id)
    encerrado = bool(prazo and prazo.date() < hoje)
    if not questoes:
        return _etapa("questionamentos", nome, sub, "feita", "Nada a questionar", "ok", 0, **base)
    if pecas_q:
        return _etapa("questionamentos", nome, sub, "feita" if encerrado else "atencao",
                      f"{len(pecas_q)} peça(s)" if not encerrado else "Prazo encerrado", "ok" if encerrado else "aviso", 0, **base)
    if encerrado:
        return _etapa("questionamentos", nome, sub, "feita", "Prazo encerrado", "neutro", 0, **base)
    n = len(questoes)
    return _etapa("questionamentos", nome, sub, "atencao", f"{n} para decidir", "aviso" if (base["dias_uteis"] or 9) > 2 else "erro", n, **base)


def etapa_mercado(ed, proposta):
    nome, sub = "Concorrência e preços", "Possíveis concorrentes e preço praticado"
    pc = ed.possiveis_concorrentes or {}
    if not pc:
        return _etapa("mercado", nome, sub, "", "Não consultado", "neutro", 1)
    if pc.get("status") == "buscando":
        return _etapa("mercado", nome, sub, "atencao", "Consultando", "aviso", 0)
    if pc.get("status") == "erro":
        return _etapa("mercado", nome, sub, "atualizar", "Erro na consulta", "erro", 1, erro=pc.get("erro"))
    concorrentes = [{k: c.get(k) for k in ("cnpj", "nome", "vitorias", "relevancia", "mesma_uf", "mesmo_orgao", "ultima_data",
                                            "pct_medio_estimado", "concorrente_id")} for c in (pc.get("itens") or [])[:8]]
    meus = {str(it.get("numero") or "").strip(): it.get("preco_unitario") for it in (proposta.itens or [])} if proposta else {}
    precos = []
    for p in pc.get("precos_itens") or []:
        meu = meus.get(str(p.get("numero") or "").strip())
        precos.append({"numero": p.get("numero"), "descricao": (p.get("descricao") or "")[:160], "unidade": p.get("unidade"),
                       "estimado": p.get("estimado"), "media": p.get("media"), "minimo": p.get("minimo"), "n": p.get("n"),
                       "n_empresas": p.get("n_empresas"), "meu": meu,
                       "acima_media": bool(meu and p.get("media") and meu > p["media"])})
    acima = sum(1 for p in precos if p["acima_media"])
    return _etapa("mercado", nome, sub, "feita" if not acima else "atencao",
                  "Revisado" if not acima else f"{acima} item(ns) acima da média", "ok" if not acima else "aviso", 0,
                  consultado_em=pc.get("consultado_em"), concorrentes=concorrentes, precos=precos[:30],
                  aviso=pc.get("aviso"), itens_edital=pc.get("itens_edital"))


def etapa_habilitacao(ed, concluida, sessao):
    nome, sub = "Habilitação e Cofre", "Documentos exigidos × Cofre"
    if not concluida:
        return _etapa("habilitacao", nome, sub, "bloqueada", "Depois da análise", "neutro", 0, exigencias=[])
    r = concluida.resultado or {}
    cofre = {}
    for d in Documento.query.filter_by(empresa_id=ed.empresa_id).all():
        cofre.setdefault(_norm(d.tipo), d)
    ref = sessao.date() if sessao else None
    exig = []
    for grupo, lista in (("padrao", r.get("checklist")), ("setorial", r.get("checklist_setorial"))):
        for c in lista or []:
            status, obs = c.get("status") or "verificar", c.get("observacao") or ""
            doc = cofre.get(_norm(c.get("documento_cofre"))) if c.get("documento_cofre") else None
            item = {"exigencia": c.get("exigencia"), "categoria": c.get("categoria"), "pagina": c.get("pagina"), "grupo": grupo,
                    "documento": None, "fundamento": c.get("fundamento")}
            if doc:   # o Cofre muda depois da análise: a situação vale na data da sessão, com o Cofre de hoje
                sit = doc.situacao(ref)
                status = {"valido": "atende", "vencendo": "atende", "sem_validade": "atende", "vencido": "vencido",
                          "pendente": "falta"}.get(sit, status)
                if sit == "vencido" and ref:
                    obs = f"Vence antes da sessão ({doc.validade.strftime('%d/%m/%Y')}). Renove."
                item["documento"] = {"id": doc.id, "tipo": doc.tipo, "validade": _iso(doc.validade), "situacao": sit}
            item.update(status=status, observacao=obs)
            exig.append(item)
    ordem = {"vencido": 0, "falta": 1, "verificar": 2, "atende": 3}
    exig.sort(key=lambda x: ordem.get(x["status"], 2))
    ok = sum(1 for e in exig if e["status"] == "atende")
    graves = sum(1 for e in exig if e["status"] in ("falta", "vencido"))
    pend = len(exig) - ok
    if not exig:
        return _etapa("habilitacao", nome, sub, "", "Sem exigências lidas", "neutro", 0, exigencias=[])
    if not pend:
        return _etapa("habilitacao", nome, sub, "feita", f"{ok} de {len(exig)} OK", "ok", 0, exigencias=exig)
    return _etapa("habilitacao", nome, sub, "atencao", f"{ok} de {len(exig)} OK", "erro" if graves else "aviso", pend, exigencias=exig)


def etapa_proposta(ed, proposta):
    nome, sub = "Proposta comercial", "Itens, preços e minuta"
    if not proposta:
        return _etapa("proposta", nome, sub, "", "Não iniciada", "neutro", 1)
    total = round(sum((it.get("preco_total") or 0) for it in proposta.itens or []), 2)
    sem_preco = sum(1 for it in proposta.itens or [] if it.get("preco_unitario") is None)
    dados = {"proposta_id": proposta.id, "titulo": proposta.titulo, "status": proposta.status, "itens": len(proposta.itens or []),
             "sem_preco": sem_preco, "total": total or None, "alertas": len(proposta.alertas or []),
             "atualizado_em": _iso(proposta.atualizado_em)}
    if proposta.status in ("lendo_edital", "gerando"):
        return _etapa("proposta", nome, sub, "atencao", "Gerando", "aviso", 0, **dados)
    if proposta.status == "erro":
        return _etapa("proposta", nome, sub, "atualizar", "Erro", "erro", 1, **dados)
    if proposta.status == "pronta" and not sem_preco:
        return _etapa("proposta", nome, sub, "feita", "Pronta", "ok", 0, **dados)
    return _etapa("proposta", nome, sub, "atencao", "Rascunho" if not sem_preco else f"{sem_preco} sem preço", "aviso", 1, **dados)


def etapa_conferencia(ed, anteriores, etapa_kanban):
    nome, sub = "Pronta para disputa", "Conferência final"
    linhas = [{"id": e["id"], "nome": e["nome"], "rotulo": e["rotulo"], "cor": e["cor"], "pend": e["pend"]} for e in anteriores]
    pend = sum(e["pend"] for e in anteriores)
    if etapa_kanban in DEPOIS_DA_PREPARACAO:
        return _etapa("conferencia", nome, sub, "feita", "Pronta", "ok", 0, linhas=linhas, pendencias=pend)
    if pend:
        return _etapa("conferencia", nome, sub, "bloqueada", f"{pend} pendência(s)", "neutro", 0, linhas=linhas, pendencias=pend)
    return _etapa("conferencia", nome, sub, "atencao", "Pode marcar como pronta", "aviso", 1, linhas=linhas, pendencias=0)


# ---------------------------------------------------------------- sessão
def etapa_disputa(ed, disputas):
    nome, sub = "Disputa", "Salas, lances e resultado"
    salas = [{"id": d.id, "item": d.item, "descricao": d.descricao, "status": d.status, "resultado": d.resultado,
              "posicao": d.posicao, "melhor_lance": d.melhor_lance, "meu_ultimo": d.meu_ultimo, "preco_piso": d.preco_piso}
             for d in disputas]
    if not salas:
        return _etapa("disputa", nome, sub, "", "Nenhuma sala", "neutro", 0, salas=[])
    if any(s["status"] == "em_disputa" for s in salas):
        return _etapa("disputa", nome, sub, "atencao", "Em disputa", "aviso", 0, salas=salas)
    if all(s["status"] == "encerrada" for s in salas):
        venceu = sum(1 for s in salas if s["resultado"] == "vencedor" or s["posicao"] == 1)
        return _etapa("disputa", nome, sub, "feita", f"1º em {venceu} de {len(salas)}" if venceu else "Encerrada",
                      "ok" if venceu else "neutro", 0, salas=salas)
    return _etapa("disputa", nome, sub, "", f"{len(salas)} sala(s) preparada(s)", "neutro", 0, salas=salas)


def etapa_documentos(ed, docs):
    nome, sub = "Atas e decisões", "Documentos da sessão lidos pela IA"
    lista = [{"id": d.id, "tipo": d.tipo, "titulo": d.titulo or d.nome_arquivo, "analise_status": d.analise_status,
              "sugestoes": len(((d.analise or {}).get("sugestoes")) or []), "criado_em": _iso(d.criado_em)} for d in docs]
    if not lista:
        return _etapa("documentos", nome, sub, "", "Nenhum documento", "neutro", 0, documentos=[])
    sugestoes = sum(d["sugestoes"] for d in lista)
    return _etapa("documentos", nome, sub, "feita" if not sugestoes else "atencao",
                  f"{len(lista)} documento(s)" if not sugestoes else f"{sugestoes} peça(s) sugerida(s)",
                  "ok" if not sugestoes else "aviso", 0, documentos=lista)


# ---------------------------------------------------------------- pós-sessão
def etapa_recurso(ed, prazos, pecas, etapa_kanban, agora):
    nome, sub = "Recurso", "Intenção, razões e contrarrazões"
    pr = [{"titulo": p.titulo, "data": _iso(p.data), "fundamento": p.fundamento, "concluido": p.concluido}
          for p in prazos if p.tipo == "recurso"]
    pc = [{"id": p.id, "tipo": p.tipo, "titulo": p.titulo, "status": p.status} for p in pecas if p.tipo in PECAS_RECURSO]
    correndo = [p for p in prazos if p.tipo == "recurso" and not p.concluido and p.data >= agora]
    if correndo:
        return _etapa("recurso", nome, sub, "atualizar", "Prazo correndo", "erro", 1, prazos=pr, pecas=pc)
    if etapa_kanban == "recurso":
        return _etapa("recurso", nome, sub, "atencao", "Em recurso", "aviso", 1 if not pc else 0, prazos=pr, pecas=pc)
    if etapa_kanban in GANHAS and (pr or pc):
        return _etapa("recurso", nome, sub, "feita", "Encerrado", "ok", 0, prazos=pr, pecas=pc)
    if pc or pr:
        return _etapa("recurso", nome, sub, "feita", f"{len(pc)} peça(s)", "neutro", 0, prazos=pr, pecas=pc)
    return _etapa("recurso", nome, sub, "", "Sem recurso", "neutro", 0, prazos=pr, pecas=pc)


def etapa_resultado(ed, etapa_kanban):
    nome, sub = "Adjudicação e homologação", "Resultado oficial"
    d = {"pncp_situacao": ed.pncp_situacao, "resultado_em": _iso(ed.resultado_em), "motivo_saida": ed.motivo_saida}
    if etapa_kanban in GANHAS:
        return _etapa("resultado", nome, sub, "feita", "Homologado", "ok", 0, **d)
    if etapa_kanban == "perdida":
        return _etapa("resultado", nome, sub, "feita", "Não vencemos", "neutro", 0, **d)
    if etapa_kanban == "desistencia":
        return _etapa("resultado", nome, sub, "feita", "Desistência", "neutro", 0, **d)
    return _etapa("resultado", nome, sub, "", "Aguardando", "neutro", 0, **d)


def etapa_contratacao(ed, contrato, etapa_kanban):
    nome, sub = "Ata e contrato", "Assinatura e garantia"
    if contrato:
        return _etapa("contratacao", nome, sub, "feita", "Contrato ativo", "ok", 0, contrato_id=contrato.id,
                      numero=contrato.numero, valor=contrato.valor, inicio=_iso(contrato.inicio), fim=_iso(contrato.fim))
    if etapa_kanban in ("homologada", "contratacao"):
        return _etapa("contratacao", nome, sub, "atencao", "Cadastrar contrato", "aviso", 1)
    return _etapa("contratacao", nome, sub, "", "Depois da homologação", "neutro", 0)


# ---------------------------------------------------------------- montagem
def montar(ed):
    agora = datetime.utcnow() - timedelta(hours=3)   # datas da licitação ficam no horário de Brasília
    hoje = agora.date()
    etapa_kanban = op.etapa_de(ed)
    sessao = ed.data_abertura
    prazos = Prazo.query.filter_by(edital_id=ed.id).order_by(Prazo.data).all()
    pecas = Peca.query.filter_by(edital_id=ed.id).order_by(Peca.id.desc()).all()
    proposta = Proposta.query.filter_by(edital_id=ed.id).order_by(Proposta.id.desc()).first()
    ultima, concluida = _analise(ed)

    prep = [etapa_analise(ed, ultima, concluida), etapa_questionamentos(ed, concluida, prazos, pecas, hoje),
            etapa_mercado(ed, proposta), etapa_habilitacao(ed, concluida, sessao), etapa_proposta(ed, proposta)]
    prep.append(etapa_conferencia(ed, prep, etapa_kanban))
    ses = [etapa_disputa(ed, Disputa.query.filter_by(edital_id=ed.id).order_by(Disputa.id).all()),
           etapa_documentos(ed, DocumentoLicitacao.query.filter_by(edital_id=ed.id).order_by(DocumentoLicitacao.id.desc()).all())]
    pos = [etapa_recurso(ed, prazos, pecas, etapa_kanban, agora), etapa_resultado(ed, etapa_kanban),
           etapa_contratacao(ed, Contrato.query.filter_by(edital_id=ed.id).order_by(Contrato.id.desc()).first(), etapa_kanban)]

    if etapa_kanban in FASE_DA_ETAPA:
        fase = FASE_DA_ETAPA[etapa_kanban]
    else:   # perdida / desistência: onde parou
        fase = "pos" if sessao and sessao < agora else "preparacao"
    fases = [{"id": "preparacao", "nome": "Preparação", "etapas": prep}, {"id": "sessao", "nome": "Sessão", "etapas": ses},
             {"id": "pos", "nome": "Pós-sessão", "etapas": pos}]
    for f in fases:
        f["pendencias"] = sum(e["pend"] for e in f["etapas"])
        f["concluidas"] = sum(1 for e in f["etapas"] if e["estado"] == "feita")

    proximo = next((p for p in prazos if not p.concluido and p.data >= agora), None)
    return {
        "edital": {"id": ed.id, "numero": ed.numero or ed.numero_controle, "orgao": ed.orgao, "objeto": ed.objeto,
                   "modalidade": ed.modalidade, "valor_estimado": ed.valor_estimado, "portal_disputa": ed.portal_disputa,
                   "etapa": etapa_kanban, "etapa_nome": op.NOMES.get(etapa_kanban, etapa_kanban),
                   "responsavel": ed.responsavel, "alerta_datas": bool((ed.cronograma or {}).get("divergencias")) and
                   not (ed.cronograma or {}).get("confirmado")},
        "fase_atual": fase,
        "sessao": {"data": _iso(sessao), "dias_uteis": _uteis_ate(hoje, sessao.date()) if sessao else None,
                   "fonte": ed.data_sessao_fonte},
        "proximo_prazo": {"titulo": proximo.titulo, "data": _iso(proximo.data), "tipo": proximo.tipo,
                          "dias_uteis": _uteis_ate(hoje, proximo.data.date())} if proximo else None,
        "fases": fases,
    }
