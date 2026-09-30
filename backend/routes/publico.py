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


@bp.route("/sair", methods=["GET", "POST"])
def descadastrar():
    """Descadastro com um clique (link de todos os e-mails de marketing e automação; POST = List-Unsubscribe-Post)."""
    from services import newsletter
    t = (request.args.get("t") or "")[:40]
    lead = Lead.query.filter_by(token=t).first() if t else None
    if lead:
        lead.newsletter, lead.marketing_optout = False, True
        if lead.conta_id:
            c = Conta.query.get(lead.conta_id)
            if c:
                c.marketing_optout = True
        newsletter.registrar_descadastro(request.args.get("e"))
        db.session.commit()
    if request.method == "POST":
        return ("", 204)
    return redirect(f"{current_app.config['SITE_URL']}/newsletter/?{'saiu=1' if lead else 'erro=1'}")


# ---------------------------------------------------------------- newsletter: rastreio e arquivo público
_GIF = (b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,"
        b"\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;")


@bp.get("/n/<token>/a.gif")
def newsletter_abertura(token):
    from services import newsletter
    try:
        newsletter.registrar_abertura(token)
    except Exception:
        db.session.rollback()
    return current_app.response_class(_GIF, mimetype="image/gif", headers={"Cache-Control": "no-store, max-age=0"})


@bp.get("/n/<token>/l/<int:indice>")
def newsletter_clique(token, indice):
    from services import newsletter
    try:
        url = newsletter.registrar_clique(token, indice)
    except Exception:
        db.session.rollback()
        url = None
    return redirect(url or f"{current_app.config['SITE_URL']}/newsletter/", code=302)


@bp.get("/newsletter/edicoes")
def newsletter_edicoes():
    from models import EdicaoNewsletter
    from services import newsletter
    eds = EdicaoNewsletter.query.filter_by(status="enviada").order_by(EdicaoNewsletter.numero.desc()).limit(52).all()
    return jsonify([{"numero": e.numero, "titulo": e.titulo, "assunto": e.assunto, "semana_inicio": e.semana_inicio.isoformat(),
                     "semana_fim": e.semana_fim.isoformat(), "enviada_em": newsletter._iso(e.enviada_em),
                     "metricas": (e.dados or {}).get("metricas")} for e in eds])


@bp.get("/newsletter/edicoes/<int:numero>")
def newsletter_edicao(numero):
    from models import EdicaoNewsletter
    from services import newsletter
    e = EdicaoNewsletter.query.filter_by(numero=numero, status="enviada").first()
    if not e:
        raise ErroAPI("Edição não encontrada.", 404)
    corpo, _ = newsletter.montar_html(e, web=True)
    return jsonify({"numero": e.numero, "titulo": e.titulo, "assunto": e.assunto, "semana_inicio": e.semana_inicio.isoformat(),
                    "semana_fim": e.semana_fim.isoformat(), "html": corpo})


# ---------------------------------------------------------------- relatório gratuito da prospecção
def _prospect(token):
    from models import Prospect
    p = Prospect.query.filter_by(token=(token or "")[:40]).first() if token else None
    if not p or p.status == "nao_contatar":
        raise ErroAPI("Relatório não encontrado.", 404)
    return p


@bp.get("/relatorio/<token>")
def relatorio_prospect(token):
    from services import prospeccao
    p = _prospect(token)
    publico.limitar("relatorio", publico.ip_hash(), por_ip=120, horas_ip=1)
    dados_rel = prospeccao.relatorio_publico(p)
    if request.args.get("visita") == "1":
        prospeccao.registrar_visita(p)
    db.session.commit()
    return jsonify(dados_rel)


@bp.post("/relatorio/<token>/nao-contatar")
def relatorio_nao_contatar(token):
    """Oposição ao tratamento (LGPD, art. 18, §2º): a empresa sai de todas as listas de prospecção."""
    p = _prospect(token)
    p.status, p.notas = "nao_contatar", ((p.notas or "") + f"\nPediu para não ser contatada pelo relatório em {datetime.utcnow():%d/%m/%Y}.").strip()
    if p.lead_id:
        lead = Lead.query.get(p.lead_id)
        if lead:
            lead.marketing_optout = True
    db.session.commit()
    return jsonify({"ok": True})


_CSP_PAGINA = {"Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'"}


def _optout_prospect(p, origem):
    p.status = "nao_contatar"
    p.notas = ((p.notas or "") + f"\nPediu para não ser contatada ({origem}) em {datetime.utcnow():%d/%m/%Y}.").strip()[:4000]
    if p.lead_id:
        lead = Lead.query.get(p.lead_id)
        if lead:
            lead.marketing_optout = True
    db.session.commit()


@bp.route("/prospect/<token>/sair", methods=["GET", "POST"])
def prospect_sair(token):
    """Descadastro do e-mail de prospecção. GET mostra a confirmação; POST (botão ou one-click do provedor) aplica."""
    from flask import Response
    from models import Prospect
    p = Prospect.query.filter_by(token=(token or "")[:40]).first() if token else None
    estilo = ("<style>body{font-family:Arial,sans-serif;background:#F4F3EF;color:#071D2D;display:flex;justify-content:center;padding:48px 16px}"
              "main{background:#fff;border-radius:10px;padding:28px;max-width:460px}button{font:inherit;font-weight:700;background:#071D2D;color:#fff;"
              "border:0;border-radius:6px;padding:10px 18px;cursor:pointer}</style>")
    if request.method == "POST":
        if p and p.status != "nao_contatar":
            _optout_prospect(p, "link do e-mail")
        return Response(f"<!doctype html><meta charset='utf-8'><meta name='viewport' content='width=device-width'>{estilo}"
                        "<main><h1>Pronto.</h1><p>Sua empresa saiu de todas as listas de contato do Kasiski. Não enviaremos novos e-mails.</p></main>",
                        mimetype="text/html", headers=_CSP_PAGINA)
    return Response(f"<!doctype html><meta charset='utf-8'><meta name='viewport' content='width=device-width'>{estilo}"
                    "<main><h1>Não receber contatos do Kasiski</h1><p>Confirme para que sua empresa saia das nossas listas de contato comercial.</p>"
                    "<form method='post'><button type='submit'>Confirmar</button></form></main>", mimetype="text/html", headers=_CSP_PAGINA)


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


# ---------------------------------------------------------------- checklist de habilitação
@bp.post("/checklist")
def checklist_publico():
    """{acao: baixar|importar, segmento, itens: [{id, tem, validade}], nome, email, empresa, consentimento}.
    Gera o lead; 'importar' fica guardado e entra no Cofre quando a pessoa cadastra a empresa com o mesmo e-mail."""
    from models import ChecklistPublico
    from services import checklist
    d = request.get_json(silent=True) or {}
    publico.exigir_humano(d)
    _consentimento(d)
    email = _email(d)
    if not (d.get("nome") or "").strip():
        raise ErroAPI("Informe seu nome.")
    publico.limitar("lead", publico.ip_hash(), por_ip=20)
    validos = {i["id"] for i in checklist.definicao()["itens"]}
    itens = [{"id": str(x.get("id")), "tem": bool(x.get("tem")), "validade": str(x.get("validade") or "")[:10] or None}
             for x in (d.get("itens") or []) if isinstance(x, dict) and str(x.get("id")) in validos][:80]
    acao = "importar" if d.get("acao") == "importar" else "baixar"
    seg = re.sub(r"[^a-z_]", "", str(d.get("segmento") or ""))[:40] or None
    lead = _lead({**d, "segmento": seg}, "checklist", email)
    c = ChecklistPublico(id=publico.novo_token(), lead_id=lead.id, email=email, segmento=seg, itens=itens, acao=acao)
    db.session.add(c)
    marketing.registrar("generate_lead", lead=lead, dados={"lead_magnet": "checklist"})
    marketing.registrar("checklist_import" if acao == "importar" else "checklist_download", lead=lead,
                        dados={"itens": len(itens), "tem": sum(1 for x in itens if x["tem"]), "segmento": seg or ""})
    marketing.recalcular(lead)
    db.session.commit()
    return jsonify({"ok": True, "id": c.id, "acao": acao})


@bp.get("/checklist/modelo")
def checklist_modelo():
    from services import checklist
    return jsonify(checklist.definicao())
