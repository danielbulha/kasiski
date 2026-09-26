"""CRM de leads, atribuição (UTM / primeiro e último toque) e lead score.

Visitante (visitante_id no navegador) → Lead (deixou e-mail) → Trial (criou conta) → Ativado (cadastrou empresa
ou usou a IA) → Assinante. Cada evento vai para a tabela Evento com o lead e o canal, e o score do lead é
recalculado. Nada aqui pode derrubar o fluxo principal: as funções públicas engolem erros e registram no log.
"""
import logging
import re
import secrets
from datetime import datetime, timedelta
from urllib.parse import urlparse

from extensions import db
from models import Conta, Empresa, Evento, Lead, UsoIA

log = logging.getLogger(__name__)

# pontos por comportamento (cada tipo conta uma vez por lead)
PONTOS = {
    "newsletter": 2, "generate_lead": 3, "pricing_view": 5, "checklist_download": 5, "tool_started": 2,
    "competitor_search": 10, "diagnostic_completed": 8, "edital_free_analysis": 15,
    "sign_up": 20, "company_created": 20, "radar_configured": 15, "edital_analyzed": 25,
    "competitor_analyzed": 10, "proposal_generated": 10, "legal_document_generated": 10,
    "begin_checkout": 30, "purchase": 40,
}
LIMIAR_ENGAJADO, LIMIAR_MQL, LIMIAR_SQL = 10, 50, 80
ORDEM_STATUS = ["novo", "engajado", "mql", "sql", "trial", "ativado", "oportunidade", "assinante"]
STATUS = set(ORDEM_STATUS) | {"perdido"}

BUSCADORES = ("google.", "bing.", "duckduckgo.", "yahoo.", "ecosia.", "search.brave")
SOCIAIS = ("linkedin", "lnkd.in", "facebook", "instagram", "t.co", "twitter", "x.com", "youtube", "whatsapp", "wa.me", "tiktok", "threads")
CAMPOS_TOQUE = ("utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term", "gclid", "fbclid", "li_fat_id",
                "ref", "landing", "referrer", "em")
NOMES_CANAL = {"busca_paga": "Busca paga (Google Ads)", "social_pago": "Social pago (LinkedIn/Meta)",
               "busca_organica": "Busca orgânica (SEO)", "social": "Redes sociais (orgânico)", "email": "E-mail / newsletter",
               "parceiro": "Parceiros (indicação com ref)", "indicacao": "Sites que indicaram", "direto": "Direto / desconhecido"}


def _limpo(v, n=200):
    v = re.sub(r"[\x00-\x1f<>\"']", "", str(v or "")).strip()
    return v[:n] or None


def normalizar_toque(t):
    """Aceita o objeto enviado pelo navegador e devolve só os campos conhecidos, limpos."""
    if not isinstance(t, dict):
        return {}
    return {k: _limpo(t.get(k), 300 if k in ("landing", "referrer") else 200) for k in CAMPOS_TOQUE if t.get(k)}


def canal_de(toque):
    t = toque or {}
    fonte = (t.get("utm_source") or "").lower()
    meio = (t.get("utm_medium") or "").lower()
    try:
        ref = urlparse(t.get("referrer") or "").hostname or ""
    except ValueError:
        ref = ""
    if t.get("ref") or meio in ("partner", "parceiro", "afiliado", "affiliate"):
        return "parceiro"
    pago = meio in ("cpc", "ppc", "paid", "pago", "ads", "paid_social", "display", "cpm") or t.get("gclid") or t.get("fbclid") or t.get("li_fat_id")
    social = any(s in fonte for s in SOCIAIS) or any(s in ref for s in SOCIAIS)
    if pago:
        return "social_pago" if (social or t.get("fbclid") or t.get("li_fat_id")) and not t.get("gclid") else "busca_paga"
    if meio in ("email", "e-mail", "newsletter"):
        return "email"
    if social or meio in ("social", "organic_social", "organico"):
        return "social"
    if fonte in ("google", "bing") or any(b in ref for b in BUSCADORES):
        return "busca_organica"
    if ref or fonte:
        return "indicacao"
    return "direto"


def origem_de(toque):
    t = toque or {}
    if t.get("utm_source"):
        return t["utm_source"][:80]
    try:
        return (urlparse(t.get("referrer") or "").hostname or "")[:80] or None
    except ValueError:
        return None


def _aplicar_toque(lead, toque):
    """Primeiro toque vence nos campos de origem; o último atualiza a última visita."""
    if not toque:
        return
    if not lead.utm_source and not lead.origem:
        lead.utm_source = toque.get("utm_source")
        lead.utm_medium = toque.get("utm_medium")
        lead.utm_campaign = toque.get("utm_campaign")
        lead.utm_content = toque.get("utm_content")
        lead.utm_term = toque.get("utm_term")
        lead.gclid = toque.get("gclid")
        lead.origem = origem_de(toque)
        lead.campanha = toque.get("utm_campaign")
        lead.canal = canal_de(toque)
        lead.landing_page = toque.get("landing")
    lead.ref_parceiro = lead.ref_parceiro or toque.get("ref")
    lead.canal = lead.canal or canal_de(toque)
    em = _data(toque.get("em"))
    lead.primeira_visita = lead.primeira_visita or em or datetime.utcnow()
    lead.ultima_visita = datetime.utcnow()


def _data(v):
    try:
        return datetime.fromisoformat(str(v).replace("Z", "")[:19]) if v else None
    except ValueError:
        return None


def obter_lead(email=None, visitante=None, criar=False, **campos):
    """Acha o lead pelo e-mail (ou pelo visitante) e cria se `criar`. Campos vazios não sobrescrevem."""
    email = (email or "").strip().lower() or None
    lead = Lead.query.filter_by(email=email).first() if email else None
    if not lead and visitante:
        lead = Lead.query.filter_by(visitante_id=visitante).order_by(Lead.id.desc()).first()
        if lead and email and lead.email and lead.email != email:
            lead = None  # outra pessoa no mesmo navegador
    if not lead and not criar:
        return None
    if not lead:
        lead = Lead(email=email, visitante_id=visitante, token=secrets.token_urlsafe(20), status="novo", score=0)
        db.session.add(lead)
    if email and not lead.email:
        lead.email = email
    lead.visitante_id = lead.visitante_id or visitante
    lead.token = lead.token or secrets.token_urlsafe(20)
    for k, v in campos.items():
        if k == "toque":
            _aplicar_toque(lead, v)
        elif v not in (None, "") and hasattr(lead, k) and (not getattr(lead, k) or k in ("nome", "telefone", "whatsapp", "empresa", "cargo")):
            setattr(lead, k, v)
    lead.atualizado_em = datetime.utcnow()
    db.session.flush()
    # eventos anônimos anteriores do mesmo navegador passam a pertencer ao lead
    if lead.visitante_id:
        Evento.query.filter(Evento.visitante_id == lead.visitante_id, Evento.lead_id.is_(None)).update(
            {"lead_id": lead.id}, synchronize_session=False)
    return lead


def recalcular(lead):
    """Score = soma dos pontos de cada tipo de evento (uma vez por tipo). Status pelo estágio da conta ou pelo score."""
    tipos = {t for (t,) in db.session.query(Evento.tipo).filter(Evento.lead_id == lead.id).distinct()}
    if lead.newsletter:
        tipos.add("newsletter")
    lead.score = min(200, sum(PONTOS.get(t, 0) for t in tipos))
    novo = status_por_conta(lead) or ("sql" if lead.score > LIMIAR_SQL else "mql" if lead.score > LIMIAR_MQL
                                      else "engajado" if lead.score >= LIMIAR_ENGAJADO else "novo")
    if lead.status == "perdido" and novo in ("novo", "engajado", "mql", "sql"):
        return lead  # marcado como perdido manualmente: só volta se virar trial/assinante
    if lead.status == "oportunidade" and novo in ("novo", "engajado", "mql", "sql", "trial", "ativado"):
        return lead  # oportunidade comercial marcada pelo time
    lead.status = novo
    return lead


def status_por_conta(lead):
    if not lead.conta_id:
        return None
    import planos
    c = Conta.query.get(lead.conta_id)
    if not c:
        return None
    if c.plano in planos.PAGOS:
        return "assinante"
    if c.plano in ("trial", "suspenso") and c.trial_fim and c.trial_fim < datetime.utcnow() - timedelta(days=15):
        return "perdido"
    usou_ia = UsoIA.query.filter(UsoIA.conta_id == c.id, UsoIA.cobravel.is_(True)).first() is not None
    tem_empresa = Empresa.query.filter_by(conta_id=c.id).first() is not None
    if usou_ia or tem_empresa:
        return "ativado"
    return "trial"


def registrar(tipo, visitante=None, conta=None, lead=None, dados=None, toque=None, email=None):
    """Grava o evento do funil e atualiza o lead. Nunca levanta erro."""
    try:
        toque = normalizar_toque(toque)
        if not lead and conta and conta.lead_id:
            lead = Lead.query.get(conta.lead_id)
        if not lead and (email or visitante):
            lead = obter_lead(email=email, visitante=visitante, criar=False)
        canal = (lead.canal if lead else None) or (canal_de(toque) if toque else None) or \
                (canal_de((conta.aquisicao or {}).get("primeiro")) if conta and conta.aquisicao else None)
        ev = Evento(tipo=tipo[:30], visitante_id=visitante or (lead.visitante_id if lead else None) or (conta.visitante_id if conta else None),
                    conta_id=conta.id if conta else (lead.conta_id if lead else None), lead_id=lead.id if lead else None,
                    origem=origem_de(toque) or (lead.origem if lead else None) or (conta.origem if conta else None),
                    campanha=(toque or {}).get("utm_campaign") or (lead.campanha if lead else None) or (conta.campanha if conta else None),
                    canal=canal, dados=dados or None)
        db.session.add(ev)
        db.session.flush()
        if lead:
            if toque:
                _aplicar_toque(lead, toque)
            lead.ultima_visita = datetime.utcnow()
            recalcular(lead)
        return ev
    except Exception:
        log.exception("Falha ao registrar evento de marketing %s", tipo)
        return None


def evento_conta(conta, tipo, dados=None):
    """Atalho para eventos do produto (conta logada). Seguro para chamar em qualquer rota."""
    if conta is None:
        return None
    try:
        if not conta.lead_id:
            _garantir_lead_da_conta(conta)
        return registrar(tipo, conta=conta, dados=dados)
    except Exception:
        log.exception("Falha no evento %s da conta %s", tipo, getattr(conta, "id", None))
        return None


def _garantir_lead_da_conta(conta):
    from models import Usuario
    u = Usuario.query.filter_by(conta_id=conta.id).order_by(Usuario.id).first()
    if not u:
        return None
    lead = obter_lead(email=u.email, visitante=conta.visitante_id, criar=True, nome=u.nome, telefone=conta.telefone,
                      toque=(conta.aquisicao or {}).get("primeiro") or ({"utm_source": conta.origem, "utm_campaign": conta.campanha} if conta.origem else None))
    lead.usuario_id, lead.conta_id = u.id, conta.id
    lead.convertido_em = lead.convertido_em or conta.criado_em or datetime.utcnow()
    conta.lead_id = lead.id
    return lead


def vincular_cadastro(conta, usuario, primeiro=None, ultimo=None):
    """No cadastro: liga (ou cria) o lead, guarda o primeiro e o último toque na conta e registra sign_up."""
    try:
        primeiro, ultimo = normalizar_toque(primeiro), normalizar_toque(ultimo)
        conta.aquisicao = {"primeiro": primeiro or None, "ultimo": ultimo or None}
        if primeiro and not conta.origem:
            conta.origem = origem_de(primeiro)
            conta.campanha = conta.campanha or primeiro.get("utm_campaign")
        lead = obter_lead(email=usuario.email, visitante=conta.visitante_id, criar=True, nome=usuario.nome,
                          telefone=conta.telefone, toque=primeiro or ultimo)
        lead.usuario_id, lead.conta_id = usuario.id, conta.id
        lead.convertido_em = lead.convertido_em or datetime.utcnow()
        conta.lead_id = lead.id
        registrar("sign_up", conta=conta, lead=lead, toque=ultimo)
        registrar("trial_started", conta=conta, lead=lead)
        return lead
    except Exception:
        log.exception("Falha ao vincular o cadastro ao CRM de leads")
        return None


def canal_da_conta(conta):
    if conta.lead_id:
        lead = Lead.query.get(conta.lead_id)
        if lead and lead.canal:
            return lead.canal
    primeiro = (conta.aquisicao or {}).get("primeiro")
    if primeiro:
        return canal_de(primeiro)
    if conta.origem:
        return canal_de({"utm_source": conta.origem})
    return "direto"


def marcar_perdidos():
    """Trial vencido há mais de 15 dias sem pagamento → perdido (rodado pelo job diário)."""
    import planos
    limite = datetime.utcnow() - timedelta(days=15)
    n = 0
    for c in Conta.query.filter(Conta.plano == "trial", Conta.trial_fim < limite, Conta.lead_id.isnot(None)):
        lead = Lead.query.get(c.lead_id)
        if lead and lead.status in ("trial", "ativado"):
            lead.status = "perdido"
            n += 1
    return n
