"""API pública das ferramentas gratuitas e do rastreamento do site (sem login). Tudo com limites anti-abuso."""
import json
import re
from datetime import datetime

from flask import Blueprint, current_app, jsonify, redirect, request

from extensions import ErroAPI, db
from models import AnalisePublica, Conta, Lead
from routes import dados
from services import arquivos, marketing, publico, tarefas

bp = Blueprint("publico", __name__, url_prefix="/api/public")

EVENTOS_PUBLICOS = {"page_view", "cta_click", "pricing_view", "lead_form_start", "tool_started", "tool_completed",
                    "checklist_download", "diagnostic_completed", "radar_result_viewed", "visita", "cta"}


def _toque(d):
    t = d.get("toque")
    if isinstance(t, str):
        try:
            t = json.loads(t)
        except ValueError:
            t = {}
    return marketing.normalizar_toque(t or {})


def _visitante(d):
    return (re.sub(r"[^\w-]", "", str(d.get("visitante") or "")) or None) and str(d.get("visitante"))[:40]


def _email(d, obrigatorio=True):
    email = (d.get("email") or "").strip().lower()
    if obrigatorio and not publico.email_valido(email):
        raise ErroAPI("Informe um e-mail válido.")
    return email or None


def _consentimento(d):
    if str(d.get("consentimento")).lower() not in ("1", "true", "on", "sim"):
        raise ErroAPI("Para continuar, aceite a Política de Privacidade.")


def _lead(d, magnet, email):
    lead = marketing.obter_lead(email=email, visitante=_visitante(d), criar=True, toque=_toque(d),
                                nome=(d.get("nome") or "").strip()[:200] or None,
                                telefone=(d.get("telefone") or "").strip()[:40] or None,
                                whatsapp=(d.get("whatsapp") or "").strip()[:40] or None,
                                empresa=(d.get("empresa") or "").strip()[:250] or None,
                                cargo=(d.get("cargo") or "").strip()[:120] or None,
                                segmento=(d.get("segmento") or "").strip()[:80] or None,
                                cidade=(d.get("cidade") or "").strip()[:120] or None,
                                uf=(d.get("uf") or "").strip().upper()[:2] or None,
                                lead_magnet=magnet)
    lead.consentimento_em = lead.consentimento_em or datetime.utcnow()
    if str(d.get("newsletter")).lower() in ("1", "true", "on", "sim"):
        lead.newsletter = True
    return lead


# ---------------------------------------------------------------- analisador gratuito de edital
@bp.post("/analisar-edital")
def analisar_edital():
    d = dados()
    publico.exigir_humano(d)
    _consentimento(d)
    email = _email(d)
    if not (d.get("nome") or "").strip():
        raise ErroAPI("Informe seu nome.")
    arq = request.files.get("arquivo")
    if not arq or not arq.filename:
        raise ErroAPI("Envie o PDF do edital.")
    if not arq.filename.lower().endswith(".pdf"):
        raise ErroAPI("Envie o edital em PDF.")
    arq.stream.seek(0, 2)
    tamanho = arq.stream.tell()
    arq.stream.seek(0)
    if tamanho > current_app.config["PUBLICO_MAX_MB"] * 1024 * 1024:
        raise ErroAPI(f"O PDF passa de {current_app.config['PUBLICO_MAX_MB']} MB. Envie só o edital, sem anexos pesados.")
    if publico.teto_global_atingido():
        raise ErroAPI("A análise gratuita atingiu o limite de hoje. Crie sua conta grátis: o teste inclui análises completas.", 503, "teto_diario")
    ip = publico.ip_hash()
    publico.limitar("analisar_edital", ip, email, por_ip=current_app.config["PUBLICO_ANALISES_IP_DIA"],
                    por_email=current_app.config["PUBLICO_ANALISES_EMAIL_MES"])
    caminho, nome = arquivos.salvar(arq, "publico")
    texto = arquivos.extrair_texto(caminho) or ""
    if len(texto.strip()) < 400:
        db.session.rollback()
        raise ErroAPI("Não conseguimos ler o texto deste PDF (parece escaneado). Envie a versão com texto selecionável.", 422, "pdf_sem_texto")
    lead = _lead(d, "analisar_edital", email)
    ap = AnalisePublica(id=publico.novo_token(), lead_id=lead.id, email=email, ip_hash=ip, arquivo=caminho,
                        nome_arquivo=nome, texto=texto, status="processando", etapa="Na fila")
    db.session.add(ap)
    marketing.registrar("generate_lead", lead=lead, dados={"lead_magnet": "analisar_edital"})
    marketing.registrar("tool_started", lead=lead, dados={"ferramenta": "analisar_edital"})
    db.session.commit()
    tarefas.rodar(publico.rodar_triagem, ap.id)
    return jsonify({"id": ap.id, "status": ap.status}), 202


@bp.get("/analisar-edital/<aid>")
def ver_analise(aid):
    ap = AnalisePublica.query.get(aid[:40])
    if not ap:
        raise ErroAPI("Análise não encontrada ou expirada.", 404)
    if ap.status == "processando" and ap.criado_em and (datetime.utcnow() - ap.criado_em).total_seconds() > 900:
        ap.status, ap.erro = "erro", "A análise demorou demais. Tente de novo."
        db.session.commit()
    return jsonify(publico.visao_publica(ap))


# ---------------------------------------------------------------- consulta de concorrente
@bp.post("/concorrente")
def concorrente():
    from services.dados_publicos import cnpj_valido, limpar_cnpj
    d = dados()
    publico.exigir_humano(d)
    cnpj = limpar_cnpj(d.get("cnpj"))
    if not cnpj or not cnpj_valido(cnpj):
        raise ErroAPI("Informe um CNPJ válido.")
    publico.limitar("concorrente", publico.ip_hash(), por_ip=current_app.config["PUBLICO_CONSULTAS_IP_DIA"])
    email = _email(d, obrigatorio=False)
    lead = None
    if email and publico.email_valido(email):
        _consentimento(d)
        lead = _lead(d, "consultar_concorrente", email)
    db.session.commit()
    visao = publico.consultar_concorrente(cnpj)
    marketing.registrar("competitor_search", visitante=_visitante(d), lead=lead, toque=_toque(d), dados={"cnpj": cnpj})
    db.session.commit()
    return jsonify(visao)


# ---------------------------------------------------------------- newsletter
@bp.post("/newsletter")
def newsletter():
    d = dados()
    publico.exigir_humano(d)
    _consentimento(d)
    email = _email(d)
    publico.limitar("newsletter", publico.ip_hash(), por_ip=20)
    lead = _lead(d, "newsletter", email)
    lead.newsletter, lead.marketing_optout = True, False
    marketing.registrar("generate_lead", lead=lead, dados={"lead_magnet": "newsletter"})
    marketing.recalcular(lead)
    db.session.commit()
    if not lead.newsletter_confirmada:
        _enviar_confirmacao(lead)
    return jsonify({"ok": True, "confirmar": not lead.newsletter_confirmada})


def _enviar_confirmacao(lead):
    from services import email as em
    if not em.configurado():
        lead.newsletter_confirmada = True  # sem e-mail configurado não há como confirmar: aceita o opt-in do formulário
        db.session.commit()
        return
    base = current_app.config["BACKEND_URL"] or request.host_url.rstrip("/")
    link = f"{base}/api/public/newsletter/confirmar?t={lead.token}"
    corpo = em.layout_marketing("Confirme sua inscrição no Kasiski Intelligence",
                                "<p>Toda semana: quanto o governo está comprando, os setores em alta, as maiores oportunidades "
                                "e o radar regulatório das licitações. Confirme para começar a receber.</p>",
                                "Confirmar inscrição", link,
                                "<p style='color:#4F6373;font-size:13px'>Se você não pediu, ignore este e-mail.</p>")
    try:
        em.enviar(lead.email, "Confirme sua inscrição no Kasiski Intelligence", f"Confirme: {link}", corpo)
    except Exception:
        current_app.logger.warning("Falha ao enviar confirmação de newsletter para o lead %s", lead.id)


@bp.get("/newsletter/confirmar")
def confirmar_newsletter():
    lead = Lead.query.filter_by(token=(request.args.get("t") or "")[:40]).first() if request.args.get("t") else None
    if lead:
        lead.newsletter, lead.newsletter_confirmada, lead.marketing_optout = True, True, False
        db.session.commit()
    return redirect(f"{current_app.config['SITE_URL']}/newsletter/?{'confirmado=1' if lead else 'erro=1'}")


@bp.get("/sair")
def descadastrar():
    """Descadastro com um clique (link de todos os e-mails de marketing e automação)."""
    t = (request.args.get("t") or "")[:40]
    lead = Lead.query.filter_by(token=t).first() if t else None
    if lead:
        lead.newsletter, lead.marketing_optout = False, True
        if lead.conta_id:
            c = Conta.query.get(lead.conta_id)
            if c:
                c.marketing_optout = True
        db.session.commit()
    return redirect(f"{current_app.config['SITE_URL']}/newsletter/?{'saiu=1' if lead else 'erro=1'}")


# ---------------------------------------------------------------- leads e eventos
@bp.post("/leads")
def leads():
    """Formulários do site (consultorias, contato, checklist, diagnóstico)."""
    d = dados()
    publico.exigir_humano(d)
    _consentimento(d)
    email = _email(d)
    magnet = re.sub(r"[^a-z_]", "", (d.get("lead_magnet") or "contato").lower())[:60] or "contato"
    publico.limitar("lead", publico.ip_hash(), por_ip=20)
    lead = _lead(d, magnet, email)
    if d.get("mensagem"):
        lead.notas = ((lead.notas or "") + f"\n[{datetime.utcnow():%d/%m/%Y}] {str(d['mensagem'])[:2000]}").strip()
    marketing.registrar("generate_lead", lead=lead, dados={"lead_magnet": magnet})
    db.session.commit()
    if magnet in ("consultorias", "contato", "partners"):
        _avisar_admins(lead, magnet, d.get("mensagem"))
    return jsonify({"ok": True})


def _avisar_admins(lead, magnet, mensagem):
    from services import email as em
    if not em.configurado():
        return
    corpo = em.layout_marketing(f"Novo lead: {lead.nome or lead.email}",
                                f"<p><b>{em.esc(lead.nome)}</b> — {em.esc(lead.email)} — {em.esc(lead.telefone or lead.whatsapp or '')}<br>"
                                f"{em.esc(lead.empresa or '')} · {em.esc(lead.cargo or '')} · formulário: {em.esc(magnet)} · canal: {em.esc(lead.canal)}</p>"
                                f"<p>{em.esc(mensagem or '')}</p>")
    for adm in current_app.config.get("ADMIN_EMAILS") or []:
        try:
            em.enviar(adm, f"[Kasiski] Novo lead ({magnet}): {lead.nome or lead.email}", f"{lead.nome} {lead.email}", corpo)
        except Exception:
            pass


@bp.post("/eventos")
def eventos():
    d = request.get_json(silent=True) or {}
    tipo = d.get("tipo")
    vid = _visitante(d)
    if tipo not in EVENTOS_PUBLICOS or not vid:
        return jsonify({"ok": False}), 400
    publico.limitar("evento", publico.ip_hash(), por_ip=600)
    info = {"pagina": str(d.get("pagina") or "")[:200]}
    if isinstance(d.get("dados"), dict):
        info.update({k: str(v)[:120] for k, v in list(d["dados"].items())[:8]})
    marketing.registrar(tipo, visitante=vid, toque=_toque(d), dados=info)
    db.session.commit()
    return jsonify({"ok": True})


# ---------------------------------------------------------------- diagnóstico de maturidade B2G
@bp.post("/diagnostico")
def diagnostico():
    """Calcula e guarda o diagnóstico (anônimo). O e-mail é opcional, depois, para receber o relatório."""
    from models import DiagnosticoB2G
    from services import diagnostico as dg
    d = request.get_json(silent=True) or {}
    publico.exigir_humano(d)
    publico.limitar("diagnostico", publico.ip_hash(), por_ip=30)
    resp = d.get("respostas") if isinstance(d.get("respostas"), dict) else {}
    r = dg.calcular(resp)
    if r["respondidas"] < r["total"] - 2:
        raise ErroAPI("Responda todas as perguntas para ver o diagnóstico.")
    perfil = d.get("perfil") if isinstance(d.get("perfil"), dict) else {}
    diag = DiagnosticoB2G(id=publico.novo_token(), visitante_id=_visitante(d), ip_hash=publico.ip_hash(), respostas=resp,
                          eixos={e["id"]: e["nota"] for e in r["eixos"]}, nota=r["nota"], nivel=r["nivel"],
                          segmento=str(perfil.get("segmento") or "")[:80] or None, porte=str(perfil.get("porte") or "")[:30] or None,
                          versao=dg.definicao().get("versao", 1))
    db.session.add(diag)
    lead = marketing.obter_lead(visitante=diag.visitante_id) if diag.visitante_id else None
    if lead:
        diag.lead_id = lead.id
        lead.segmento = lead.segmento or diag.segmento
    marketing.registrar("diagnostic_completed", visitante=diag.visitante_id, lead=lead, toque=_toque(d),
                        dados={"nota": r["nota"], "nivel": r["nivel"]})
    db.session.commit()
    return jsonify({"id": diag.id, **r, "mercado": dg.media_mercado()})


@bp.post("/diagnostico/<did>/email")
def diagnostico_email(did):
    """Envia o relatório completo por e-mail e transforma o visitante em lead."""
    from models import DiagnosticoB2G
    from services import diagnostico as dg
    diag = DiagnosticoB2G.query.get(did[:40])
    if not diag:
        raise ErroAPI("Diagnóstico não encontrado. Refaça o teste.", 404)
    d = dados()
    publico.exigir_humano(d)
    _consentimento(d)
    email = _email(d)
    publico.limitar("lead", publico.ip_hash(), por_ip=20)
    lead = _lead({**d, "visitante": diag.visitante_id or d.get("visitante"), "segmento": d.get("segmento") or diag.segmento}, "diagnostico", email)
    diag.lead_id = lead.id
    marketing.registrar("generate_lead", lead=lead, dados={"lead_magnet": "diagnostico", "nota": diag.nota})
    marketing.recalcular(lead)
    db.session.commit()
    _enviar_relatorio(diag, lead, dg.calcular(diag.respostas))
    return jsonify({"ok": True})


def _enviar_relatorio(diag, lead, r):
    from services import email as em
    if not em.configurado():
        return
    site, app = current_app.config["SITE_URL"], current_app.config["FRONTEND_URL"]
    barras = "".join(
        f"<tr><td style='padding:6px 12px 6px 0;white-space:nowrap'>{em.esc(e['nome'])}</td><td style='width:100%'>"
        + (f"<div style='background:#E7ECEF;border-radius:4px;height:12px'><div style='background:#2E6CA4;height:12px;border-radius:0 4px 4px 0;width:{e['nota']}%'></div></div>"
           if e["nota"] is not None else "<span style='color:#91A5B3'>não se aplica</span>")
        + f"</td><td style='padding-left:10px;font-weight:700'>{'' if e['nota'] is None else e['nota']}</td></tr>" for e in r["eixos"])
    recs = "".join(f"<li style='margin-bottom:10px'><b>{em.esc(x['nome'])} ({x['nota']}/100).</b> {em.esc(x['texto'])} "
                   f"<a href='{site}{x['recurso']['url']}'>{em.esc(x['recurso']['nome'])}</a></li>" for x in r["recomendacoes"])
    corpo = em.layout_marketing(
        f"Maturidade B2G: {r['nota']}/100 — {r['nivel_nome']}",
        f"<p>{em.esc(r['nivel_texto'])}</p><table style='width:100%;border-collapse:collapse;margin:14px 0'>{barras}</table>"
        + (f"<h2 style='font-size:16px;margin:20px 0 8px'>Plano de ação — por onde começar</h2><ol style='padding-left:18px'>{recs}</ol>" if recs else
           "<p>Sua empresa está bem estruturada em todos os eixos. O Kasiski ajuda a ganhar escala com radar, análise e pipeline automatizados.</p>"),
        "Começar gratuitamente no Kasiski", f"{app}/#/cadastro?utm_source=kasiski&utm_medium=email&utm_campaign=diagnostico",
        descadastro=(f"{current_app.config['BACKEND_URL']}/api/public/sair?t={lead.token}" if current_app.config.get("BACKEND_URL") else None))
    try:
        em.enviar(lead.email, f"Seu diagnóstico de maturidade B2G: {r['nota']}/100", f"Nota {r['nota']}/100 — {r['nivel_nome']}", corpo)
    except Exception:
        current_app.logger.warning("Falha ao enviar relatório do diagnóstico %s", diag.id)
