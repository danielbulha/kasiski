"""Admin → Marketing: funil completo (visitante → assinante), canais e campanhas com CAC, leads, ferramentas,
investimentos por canal, cohorts e automações de e-mail."""
import csv
import io
from collections import defaultdict
from datetime import datetime, timedelta

from flask import Blueprint, Response, g, jsonify, request

import planos
from auth import admin_requerido
from extensions import ErroAPI, db
from models import (AnalisePublica, Automacao, AutomacaoEnvio, Conta, Empresa, Evento, InvestimentoCanal, Lead, UsoIA,
                    Usuario)
from routes import dados, para_float
from services import automacoes, marketing

bp = Blueprint("marketing", __name__, url_prefix="/api/admin/marketing")


def _periodo():
    dias = max(1, min(int(request.args.get("dias", 30)), 730))
    return dias, datetime.utcnow() - timedelta(days=dias)


def _estado_contas(contas):
    """{conta_id: {"ativado": bool, "pagante": bool, "mrr": float, "canal": str}}"""
    ids = [c.id for c in contas]
    if not ids:
        return {}
    com_empresa = {cid for (cid,) in db.session.query(Empresa.conta_id).filter(Empresa.conta_id.in_(ids)).distinct()}
    com_ia = {cid for (cid,) in db.session.query(UsoIA.conta_id).filter(UsoIA.conta_id.in_(ids), UsoIA.cobravel.is_(True)).distinct()}
    saida = {}
    for c in contas:
        pagante = c.plano in planos.PAGOS
        saida[c.id] = {"ativado": c.id in com_empresa or c.id in com_ia, "usou_ia": c.id in com_ia, "pagante": pagante,
                       "mrr": planos.mrr_da_conta(c) if pagante else 0.0, "canal": marketing.canal_da_conta(c),
                       "campanha": ((c.aquisicao or {}).get("primeiro") or {}).get("utm_campaign") or c.campanha}
    return saida


def _investimento(desde):
    mes0 = desde.strftime("%Y-%m")
    tot, por = 0.0, defaultdict(float)
    for i in InvestimentoCanal.query.filter(InvestimentoCanal.mes >= mes0):
        tot += i.valor or 0
        por[(i.canal or "").lower()] += i.valor or 0
    return tot, por


_FONTE_CANAL = {"google": "busca_paga", "google_ads": "busca_paga", "linkedin": "social_pago", "linkedin_ads": "social_pago",
                "meta": "social_pago", "facebook": "social_pago", "instagram": "social_pago"}


@bp.get("/visao")
@admin_requerido
def visao():
    dias, desde = _periodo()
    visitantes = db.session.query(db.func.count(db.distinct(Evento.visitante_id))).filter(
        Evento.tipo.in_(["page_view", "visita"]), Evento.criado_em >= desde).scalar() or 0
    leads = Lead.query.filter(Lead.criado_em >= desde).all()
    contas = Conta.query.filter(Conta.criado_em >= desde).all()
    est = _estado_contas(contas)
    trials = len(contas)
    ativados = sum(1 for v in est.values() if v["ativado"])
    assinantes = sum(1 for v in est.values() if v["pagante"])
    mrr_novo = round(sum(v["mrr"] for v in est.values()), 2)
    invest, invest_por = _investimento(desde)

    todas = Conta.query.all()
    pagantes = [c for c in todas if c.plano in planos.PAGOS and c.assinatura_status == "ativa"]
    mrr = round(sum(planos.mrr_da_conta(c) for c in pagantes), 2)
    arpu = round(mrr / len(pagantes), 2) if pagantes else None
    cancelados = [c for c in todas if c.cancelado_em and c.cancelado_em >= desde]
    base_churn = len(pagantes) + len(cancelados)
    churn_mensal = round(100 * len(cancelados) / base_churn * (30 / dias), 2) if base_churn else None
    ltv = round(arpu / (churn_mensal / 100), 2) if arpu and churn_mensal else None
    cac = round(invest / assinantes, 2) if invest and assinantes else None
    payback = round(cac / arpu, 1) if cac and arpu else None

    # por canal
    canais = defaultdict(lambda: {"visitantes": set(), "leads": 0, "trials": 0, "ativados": 0, "assinantes": 0, "mrr": 0.0})
    for vid, canal in db.session.query(Evento.visitante_id, Evento.canal).filter(
            Evento.tipo.in_(["page_view", "visita"]), Evento.criado_em >= desde, Evento.visitante_id.isnot(None)):
        canais[canal or "direto"]["visitantes"].add(vid)
    for l in leads:
        canais[l.canal or "direto"]["leads"] += 1
    for c in contas:
        v = est[c.id]
        k = canais[v["canal"] or "direto"]
        k["trials"] += 1
        k["ativados"] += 1 if v["ativado"] else 0
        k["assinantes"] += 1 if v["pagante"] else 0
        k["mrr"] += v["mrr"]
    invest_canal = defaultdict(float)
    for fonte, valor in invest_por.items():
        invest_canal[_FONTE_CANAL.get(fonte, fonte)] += valor
    linhas_canal = []
    for canal, v in canais.items():
        inv = invest_canal.get(canal, 0.0)
        linhas_canal.append({"canal": canal, "nome": marketing.NOMES_CANAL.get(canal, canal), "visitantes": len(v["visitantes"]),
                             "leads": v["leads"], "trials": v["trials"], "ativados": v["ativados"], "assinantes": v["assinantes"],
                             "mrr": round(v["mrr"], 2), "investimento": round(inv, 2),
                             "cac": round(inv / v["assinantes"], 2) if inv and v["assinantes"] else None})
    linhas_canal.sort(key=lambda x: (-x["assinantes"], -x["trials"], -x["leads"]))

    # campanhas (utm_campaign)
    camp = defaultdict(lambda: {"leads": 0, "trials": 0, "ativados": 0, "assinantes": 0})
    for l in leads:
        if l.utm_campaign:
            camp[l.utm_campaign]["leads"] += 1
    for c in contas:
        nome = est[c.id]["campanha"]
        if nome:
            camp[nome]["trials"] += 1
            camp[nome]["ativados"] += 1 if est[c.id]["ativado"] else 0
            camp[nome]["assinantes"] += 1 if est[c.id]["pagante"] else 0
    campanhas = sorted(({"campanha": k, **v} for k, v in camp.items()), key=lambda x: (-x["assinantes"], -x["trials"], -x["leads"]))[:40]

    # ferramentas gratuitas e iscas
    magnets = defaultdict(lambda: {"leads": 0, "trials": 0, "assinantes": 0})
    contas_por_id = {c.id: c for c in Conta.query.filter(Conta.id.in_([l.conta_id for l in leads if l.conta_id] or [0]))}
    est_leads = _estado_contas(list(contas_por_id.values()))
    for l in leads:
        m = magnets[l.lead_magnet or "cadastro direto"]
        m["leads"] += 1
        if l.conta_id:
            m["trials"] += 1
            m["assinantes"] += 1 if est_leads.get(l.conta_id, {}).get("pagante") else 0
    ferramentas = {
        "analises_gratuitas": AnalisePublica.query.filter(AnalisePublica.criado_em >= desde).count(),
        "custo_ia_analises_usd": round(float(db.session.query(db.func.coalesce(db.func.sum(AnalisePublica.custo_usd), 0))
                                             .filter(AnalisePublica.criado_em >= desde).scalar() or 0), 4),
        "consultas_concorrente": Evento.query.filter(Evento.tipo == "competitor_search", Evento.criado_em >= desde).count(),
        "newsletter_ativos": Lead.query.filter(Lead.newsletter.is_(True), Lead.newsletter_confirmada.is_(True)).count(),
        "por_isca": sorted(({"isca": k, **v} for k, v in magnets.items()), key=lambda x: -x["leads"]),
    }

    # cohort por canal: trials de 60+ dias atrás — quantos pagaram e quantos seguem pagando
    corte = datetime.utcnow() - timedelta(days=60)
    antigas = Conta.query.filter(Conta.criado_em < corte, Conta.criado_em >= corte - timedelta(days=max(dias, 90))).all()
    est_ant = _estado_contas(antigas)
    from models import Cobranca
    pagaram = {cid for (cid,) in db.session.query(Cobranca.conta_id).filter(Cobranca.status == "aprovado").distinct()}
    coh = defaultdict(lambda: {"trials": 0, "pagaram": 0, "retidos": 0})
    for c in antigas:
        k = coh[est_ant[c.id]["canal"] or "direto"]
        k["trials"] += 1
        k["pagaram"] += 1 if c.id in pagaram or est_ant[c.id]["pagante"] else 0
        k["retidos"] += 1 if est_ant[c.id]["pagante"] and c.assinatura_status == "ativa" else 0
    cohorts = sorted(({"canal": k, "nome": marketing.NOMES_CANAL.get(k, k), **v} for k, v in coh.items()), key=lambda x: -x["trials"])

    def taxa(a, b):
        return round(100 * a / b, 1) if b else None

    return jsonify({
        "dias": dias,
        "funil": [
            {"chave": "visitantes", "rotulo": "Visitantes", "total": visitantes},
            {"chave": "leads", "rotulo": "Leads", "total": len(leads)},
            {"chave": "trials", "rotulo": "Trials (contas criadas)", "total": trials},
            {"chave": "ativados", "rotulo": "Ativados (empresa ou IA)", "total": ativados},
            {"chave": "assinantes", "rotulo": "Assinantes", "total": assinantes},
        ],
        "indicadores": {"mrr": mrr, "arr": round(mrr * 12, 2), "arpu": arpu, "mrr_novo": mrr_novo, "investimento": round(invest, 2),
                        "cac": cac, "ltv": ltv, "payback_meses": payback, "churn_mensal": churn_mensal,
                        "lead_para_trial": taxa(sum(1 for l in leads if l.conta_id), len(leads)),
                        "trial_para_pago": taxa(assinantes, trials), "ativacao": taxa(ativados, trials),
                        "visitante_para_lead": taxa(len(leads), visitantes), "pagantes": len(pagantes)},
        "canais": linhas_canal, "campanhas": campanhas, "ferramentas": ferramentas, "cohorts": cohorts,
        "leads_quentes": [l.to_dict() for l in Lead.query.filter(Lead.status.in_(["mql", "sql", "oportunidade"]))
                          .order_by(Lead.score.desc(), Lead.ultima_visita.desc().nullslast()).limit(12)],
    })


# ---------------------------------------------------------------- leads
@bp.get("/leads")
@admin_requerido
def listar_leads():
    q = Lead.query
    st = request.args.get("status")
    if st == "quentes":
        q = q.filter(Lead.status.in_(["mql", "sql", "oportunidade"]))
    elif st in marketing.STATUS:
        q = q.filter(Lead.status == st)
    if request.args.get("canal"):
        q = q.filter(Lead.canal == request.args["canal"])
    termo = (request.args.get("q") or "").strip()
    if termo:
        like = f"%{termo}%"
        q = q.filter(db.or_(Lead.email.ilike(like), Lead.nome.ilike(like), Lead.empresa.ilike(like), Lead.utm_campaign.ilike(like)))
    itens = q.order_by(Lead.score.desc(), Lead.criado_em.desc()).limit(300).all()
    contagem = dict(db.session.query(Lead.status, db.func.count(Lead.id)).group_by(Lead.status).all())
    return jsonify({"leads": [l.to_dict() for l in itens], "contagem": contagem})


@bp.get("/leads/<int:lid>")
@admin_requerido
def ver_lead(lid):
    l = Lead.query.get_or_404(lid)
    evs = Evento.query.filter(db.or_(Evento.lead_id == l.id, db.and_(Evento.conta_id == l.conta_id, Evento.conta_id.isnot(None)))) \
        .order_by(Evento.criado_em.desc()).limit(200).all()
    conta = Conta.query.get(l.conta_id) if l.conta_id else None
    return jsonify({**l.to_dict(), "pontos_por_evento": marketing.PONTOS,
                    "eventos": [{"tipo": e.tipo, "canal": e.canal, "origem": e.origem, "campanha": e.campanha, "dados": e.dados,
                                 "criado_em": e.criado_em.isoformat()} for e in evs],
                    "conta": {"id": conta.id, "nome": conta.nome, "plano": conta.plano, "aquisicao": conta.aquisicao,
                              "trial_fim": conta.trial_fim.isoformat() if conta.trial_fim else None} if conta else None,
                    "analises_gratuitas": [{"id": a.id, "nome_arquivo": a.nome_arquivo, "status": a.status,
                                            "nota": (a.resultado or {}).get("nota"), "criado_em": a.criado_em.isoformat()}
                                           for a in AnalisePublica.query.filter_by(lead_id=l.id).order_by(AnalisePublica.criado_em.desc())]})


@bp.patch("/leads/<int:lid>")
@admin_requerido
def editar_lead(lid):
    l = Lead.query.get_or_404(lid)
    d = dados()
    if d.get("status") in marketing.STATUS:
        l.status = d["status"]
    for k in ("responsavel", "notas", "telefone", "whatsapp", "empresa", "cargo"):
        if k in d:
            setattr(l, k, (d[k] or "").strip() or None)
    l.atualizado_em = datetime.utcnow()
    db.session.commit()
    return jsonify(l.to_dict())


@bp.get("/leads.csv")
@admin_requerido
def exportar_leads():
    so_news = request.args.get("newsletter") == "1"
    q = Lead.query
    if so_news:
        q = q.filter(Lead.newsletter.is_(True), Lead.newsletter_confirmada.is_(True), Lead.marketing_optout.isnot(True))
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    cols = ["nome", "email", "telefone", "empresa", "cargo", "segmento", "uf", "canal", "utm_source", "utm_medium", "utm_campaign",
            "lead_magnet", "score", "status", "newsletter", "criado_em"]
    w.writerow(cols)
    for l in q.order_by(Lead.criado_em.desc()):
        d = l.to_dict()
        w.writerow([d.get(c) if d.get(c) is not None else "" for c in cols])
    nome = "kasiski-newsletter.csv" if so_news else "kasiski-leads.csv"
    return Response("﻿" + buf.getvalue(), mimetype="text/csv", headers={"Content-Disposition": f"attachment; filename={nome}"})


# ---------------------------------------------------------------- investimentos
@bp.get("/investimentos")
@admin_requerido
def listar_invest():
    return jsonify([i.to_dict() for i in InvestimentoCanal.query.order_by(InvestimentoCanal.mes.desc(), InvestimentoCanal.id.desc()).limit(200)])


@bp.post("/investimentos")
@admin_requerido
def novo_invest():
    d = dados()
    mes = (d.get("mes") or "")[:7]
    if not (len(mes) == 7 and mes[4] == "-"):
        raise ErroAPI("Informe o mês (AAAA-MM).")
    valor = para_float(d.get("valor"))
    if not valor or valor <= 0:
        raise ErroAPI("Informe o valor investido.")
    i = InvestimentoCanal(mes=mes, canal=(d.get("canal") or "").strip().lower()[:80] or "outro",
                          campanha=(d.get("campanha") or "").strip()[:120] or None, valor=valor, notas=(d.get("notas") or "")[:300] or None)
    db.session.add(i)
    db.session.commit()
    return jsonify(i.to_dict()), 201


@bp.delete("/investimentos/<int:iid>")
@admin_requerido
def apagar_invest(iid):
    InvestimentoCanal.query.filter_by(id=iid).delete()
    db.session.commit()
    return jsonify({"ok": True})


# ---------------------------------------------------------------- automações
@bp.get("/automacoes")
@admin_requerido
def listar_automacoes():
    automacoes.garantir_padrao()
    desde = datetime.utcnow() - timedelta(days=30)
    cont = defaultdict(lambda: {"enviado": 0, "falhou": 0})
    for aid, st, n in db.session.query(AutomacaoEnvio.automacao_id, AutomacaoEnvio.status, db.func.count(AutomacaoEnvio.id)) \
            .filter(AutomacaoEnvio.enviado_em >= desde).group_by(AutomacaoEnvio.automacao_id, AutomacaoEnvio.status):
        cont[aid][st] = n
    from services import email as em
    return jsonify({"email_configurado": em.configurado(),
                    "automacoes": [{"id": a.id, "chave": a.chave, "nome": a.nome, "gatilho": a.gatilho, "atraso_min": a.atraso_min,
                                    "condicao": a.condicao, "assunto": a.assunto, "ativo": a.ativo, **cont[a.id]}
                                   for a in Automacao.query.order_by(Automacao.id)]})


@bp.patch("/automacoes/<int:aid>")
@admin_requerido
def editar_automacao(aid):
    a = Automacao.query.get_or_404(aid)
    d = dados()
    if "ativo" in d:
        a.ativo = bool(d["ativo"]) and str(d["ativo"]).lower() not in ("0", "false")
    if (d.get("assunto") or "").strip():
        a.assunto = d["assunto"].strip()[:200]
    if "atraso_min" in d:
        try:
            a.atraso_min = max(0, min(int(d["atraso_min"]), 60 * 24 * 14))
        except (TypeError, ValueError):
            raise ErroAPI("Atraso inválido.")
    db.session.commit()
    return jsonify({"ok": True})


@bp.post("/automacoes/<int:aid>/teste")
@admin_requerido
def testar_automacao(aid):
    from services import email as em
    if not em.configurado():
        raise ErroAPI("Configure o RESEND_API_KEY para enviar e-mails.")
    a = Automacao.query.get_or_404(aid)
    automacoes.enviar_um(a, g.conta, g.usuario, automacoes.metricas(g.conta), teste_para=g.usuario.email)
    return jsonify({"ok": True, "para": g.usuario.email})


@bp.post("/automacoes/rodar")
@admin_requerido
def rodar_agora():
    return jsonify({"enviados": len(automacoes.rodar())})
