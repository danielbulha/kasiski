"""Kanban da oportunidade: o edital acompanhado visto como um negócio no ciclo comercial.

Etapas (em ordem) e duas saídas laterais (perdida, desistencia). O cartão anda sozinho quando o Kasiski
detecta um evento (análise, Go/No-Go, data da sessão, resultado/homologação e contrato no PNCP, peças de
recurso, contrato cadastrado). Movimento automático só avança; o usuário pode mover para qualquer etapa.
"""
import logging
import re
from datetime import datetime

from extensions import db
from models import Analise, Edital, Movimento

log = logging.getLogger(__name__)

ETAPAS = [
    ("identificada", "Identificada", "Licitação capturada, ainda sem análise."),
    ("em_analise", "Em análise", "Avaliando edital, objeto, requisitos, riscos, margem e capacidade de atendimento."),
    ("decisao", "Decisão Go / No-Go", "Decisão interna sobre participar ou não."),
    ("preparacao", "Preparação", "Documentação, habilitação, proposta técnica/comercial, garantias e planilhas."),
    ("pronta", "Pronta para disputa", "Tudo preparado, aguardando a sessão."),
    ("em_disputa", "Em disputa", "Sessão, lances e julgamento em andamento."),
    ("classificada", "Classificada / Habilitação", "Bem posicionada, aguardando análise documental ou julgamento."),
    ("recurso", "Recurso / Contrarrazões", "Fase recursal."),
    ("homologada", "Adjudicada / Homologada", "Resultado favorável confirmado."),
    ("contratacao", "Contratação", "Aguardando assinatura, empenho, ordem de serviço ou instrumento equivalente."),
    ("contrato_ativo", "Contrato ativo", "Oportunidade convertida em contrato."),
]
SAIDAS = [
    ("perdida", "Perdida", "Não vencemos ou o certame foi revogado/anulado."),
    ("desistencia", "Desistência / No-Go", "Decidimos não participar ou desistimos."),
]
ORDEM = {k: i for i, (k, _, _) in enumerate(ETAPAS)}
NOMES = {k: n for k, n, _ in ETAPAS + SAIDAS}
VALIDAS = set(NOMES)

# status antigo do edital (ainda usado no painel e na lista de editais)
STATUS_DA_ETAPA = {"identificada": "acompanhando", "em_analise": "acompanhando", "decisao": "acompanhando",
                   "preparacao": "participando", "pronta": "participando", "em_disputa": "participando",
                   "classificada": "participando", "recurso": "participando", "homologada": "ganho",
                   "contratacao": "ganho", "contrato_ativo": "ganho", "perdida": "perdido", "desistencia": "descartado"}
PRE_DISPUTA = {"identificada", "em_analise", "decisao", "preparacao", "pronta"}


def etapa_de(ed):
    """Etapa atual; editais anteriores ao Kanban são encaixados pelo status e pela análise."""
    if ed.etapa in VALIDAS:
        return ed.etapa
    if ed.status == "ganho":
        return "homologada"
    if ed.status == "perdido":
        return "perdida"
    if ed.status == "descartado":
        return "desistencia"
    if ed.status == "participando":
        return "preparacao"
    tem_analise = Analise.query.filter_by(edital_id=ed.id, status="concluida").first() is not None
    return "decisao" if tem_analise else "identificada"


def mover(ed, para, origem="usuario", autor=None, motivo=None):
    """Move o cartão (sem commit). Devolve True se mudou."""
    if para not in VALIDAS:
        return False
    atual = etapa_de(ed)
    if ed.etapa != atual:  # materializa a etapa inferida de editais antigos
        ed.etapa = atual
    if atual == para:
        return False
    ed.etapa, ed.etapa_em = para, datetime.utcnow()
    ed.status = STATUS_DA_ETAPA[para]
    if para in ("perdida", "desistencia") and motivo:
        ed.motivo_saida = motivo[:2000]
    db.session.add(Movimento(edital_id=ed.id, de=atual, para=para, origem=origem, autor=autor, motivo=(motivo or "")[:2000] or None))
    return True


def avancar(ed, para, motivo, autor="Kasiski"):
    """Movimento automático: só avança no funil e nunca tira o cartão de uma saída (perdida/desistência).
    Para as saídas, move a partir de qualquer etapa ativa."""
    atual = etapa_de(ed)
    if atual in ("perdida", "desistencia"):
        return False
    if para in ("perdida", "desistencia") or ORDEM.get(para, -1) > ORDEM.get(atual, -1):
        return mover(ed, para, "automatico", autor, motivo)
    return False


def registrar_criacao(ed, como):
    """Cartão novo entra em Identificada com o registro de como chegou."""
    ed.etapa, ed.etapa_em = "identificada", datetime.utcnow()
    db.session.flush()
    db.session.add(Movimento(edital_id=ed.id, de=None, para="identificada", origem="automatico", autor="Kasiski", motivo=como))


# ---------------------------------------------------------------- fit e risco
PESO_CHECK = {"atende": 1.0, "verificar": 0.5, "falta": 0.0, "vencido": 0.0}
PESO_DECISAO = {"participar": 100, "participar_com_ressalvas": 60, "nao_participar": 15}


def fit_e_risco(resultado, nota_radar=None):
    """Fit (0-100) = 70% aderência da habilitação (checklist) + 30% recomendação da IA.
    Sem análise, usa a nota do radar. Risco = pior nível entre riscos e cláusulas restritivas."""
    if not resultado:
        return (int(nota_radar) if isinstance(nota_radar, (int, float)) else None), None
    itens = (resultado.get("checklist") or []) + (resultado.get("checklist_setorial") or [])
    pesos = [PESO_CHECK.get(i.get("status"), 0.5) for i in itens]
    base = 100 * sum(pesos) / len(pesos) if pesos else 60
    dec = PESO_DECISAO.get((resultado.get("recomendacao") or {}).get("decisao"), 60)
    fit = round(0.7 * base + 0.3 * dec)
    niveis = [r.get("nivel") for r in resultado.get("riscos") or []] + \
             [{"alta": "alto", "media": "medio", "baixa": "baixo"}.get(c.get("gravidade")) for c in resultado.get("clausulas_restritivas") or []]
    risco = "alto" if "alto" in niveis else "medio" if "medio" in niveis else "baixo" if niveis else "baixo"
    return max(0, min(100, fit)), risco


def cartao(ed, ultima=None, nota_radar=None):
    r = (ultima.resultado or {}) if ultima else None
    fit, risco = fit_e_risco(r, nota_radar)
    dias = None
    if ed.data_abertura:
        dias = (ed.data_abertura.date() - datetime.utcnow().date()).days
    return {"id": ed.id, "etapa": etapa_de(ed), "numero": ed.numero, "modalidade": ed.modalidade, "orgao": ed.orgao,
            "objeto": ed.objeto, "valor_estimado": ed.valor_estimado,
            "data_abertura": ed.data_abertura.isoformat() if ed.data_abertura else None, "dias": dias,
            "responsavel": ed.responsavel, "responsavel_id": ed.responsavel_id, "fit": fit, "risco": risco,
            "fit_fonte": "analise" if r else ("radar" if fit is not None else None),
            "decisao": ed.decisao, "decisao_ia": ((r or {}).get("recomendacao") or {}).get("decisao"),
            "uf": ed.uf, "municipio": ed.municipio, "numero_controle": ed.numero_controle,
            "etapa_em": ed.etapa_em.isoformat() if ed.etapa_em else None, "motivo_saida": ed.motivo_saida,
            "pncp_situacao": ed.pncp_situacao}


# ---------------------------------------------------------------- eventos automáticos
def avancar_por_data(ed):
    """Sessão pública já começou e o cartão ainda estava na preparação → Em disputa."""
    if ed.data_abertura and ed.data_abertura <= datetime.utcnow() and etapa_de(ed) in ("preparacao", "pronta"):
        return avancar(ed, "em_disputa", f"Sessão pública iniciada em {ed.data_abertura.strftime('%d/%m/%Y %H:%M')}.")
    return False


_REVOGADA = re.compile(r"revogad|anulad|desert|fracassad|cancelad", re.I)


def sincronizar(ed, empresa):
    """Consulta o PNCP e movimenta o cartão conforme os eventos públicos. Devolve lista de movimentos feitos."""
    from services import pncp
    feitos = []
    if not ed.numero_controle:
        if avancar_por_data(ed):
            feitos.append(ed.etapa)
        return feitos
    etapa = etapa_de(ed)
    try:
        s = pncp.situacao_compra(ed.numero_controle) or {}
    except Exception as e:
        log.info("Situação PNCP de %s indisponível: %s", ed.numero_controle, e)
        s = {}
    if s:
        ed.pncp_situacao = (s.get("situacao") or "")[:80] or ed.pncp_situacao
        ed.unidade_codigo = s.get("unidade_codigo") or ed.unidade_codigo
        ed.unidade_nome = (s.get("unidade_nome") or "")[:300] or ed.unidade_nome
        nova = pncp._data(s.get("data_abertura"))
        if nova and nova != ed.data_abertura:
            ed.data_abertura = nova
            from services import fluxos
            fluxos.gerar_prazos_edital(ed)
        if _REVOGADA.search(ed.pncp_situacao or "") and avancar(ed, "perdida", f"PNCP: licitação {ed.pncp_situacao.lower()}."):
            feitos.append("perdida")
            return feitos
    if avancar_por_data(ed):
        feitos.append("em_disputa")
    etapa = etapa_de(ed)
    # resultado publicado (homologação dos itens)
    if etapa not in ("homologada", "contratacao", "contrato_ativo", "perdida", "desistencia"):
        try:
            vencedores = pncp.vencedores_da_compra(ed.numero_controle, max_itens=10)
        except Exception:
            vencedores = []
        if vencedores:
            nossos = empresa and any(v["cnpj"] == empresa.cnpj for v in vencedores)
            if nossos:
                if avancar(ed, "homologada", "PNCP: resultado homologado com a sua empresa como vencedora."):
                    feitos.append("homologada")
            elif ORDEM.get(etapa, 0) >= ORDEM["em_disputa"]:
                nomes = ", ".join(v["nome"] for v in vencedores[:3] if v.get("nome"))
                if avancar(ed, "perdida", f"PNCP: resultado homologado para outra empresa ({nomes})." if nomes else "PNCP: resultado homologado para outra empresa."):
                    feitos.append("perdida")
                    return feitos
    # contrato publicado no PNCP com a empresa
    if etapa_de(ed) in ("homologada", "contratacao") and empresa:
        try:
            for c in pncp.historico_fornecedor(empresa.cnpj, limite=10):
                if c["tipo"] != "contrato" or not c.get("numero_controle"):
                    continue
                if pncp.compra_do_contrato(c["numero_controle"]) == ed.numero_controle:
                    if avancar(ed, "contrato_ativo", f"PNCP: contrato {c['numero_controle']} publicado."):
                        feitos.append("contrato_ativo")
                    break
        except Exception as e:
            log.info("Contratos PNCP de %s indisponíveis: %s", empresa.cnpj, e)
    ed.pncp_sincronizado_em = datetime.utcnow()
    return feitos


def sincronizar_empresa(empresa):
    """Sincroniza todos os cartões ativos da empresa. Devolve quantos cartões mudaram de etapa."""
    movidos = 0
    for ed in Edital.query.filter_by(empresa_id=empresa.id):
        if etapa_de(ed) in ("perdida", "desistencia", "contrato_ativo"):
            continue
        try:
            if sincronizar(ed, empresa):
                movidos += 1
            db.session.commit()
        except Exception:
            db.session.rollback()
            log.exception("Falha ao sincronizar a oportunidade %s", ed.id)
    return movidos
