"""Painel do administrador: CRM de contas (testes grátis e assinaturas), funil de conversão
e controle de receitas. Todas as rotas exigem e-mail listado em ADMIN_EMAILS."""
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from flask import Blueprint, current_app, jsonify, request

import planos
from auth import admin_requerido
from extensions import ErroAPI, db
from models import Cobranca, Conta, Empresa, Evento, Revisao, UsoIA, Usuario
from routes import dados, para_data, para_float

bp = Blueprint("admin", __name__, url_prefix="/api/admin")


def _iso(v):
    return v.isoformat() if v else None


def _por_conta(consulta):
    return {cid: v for cid, v in consulta.all()}


def _inicio_mes(dt=None):
    dt = dt or datetime.utcnow()
    return datetime(dt.year, dt.month, 1)


def etapa(conta, n_empresas, n_analises, pagou):
    """Em que ponto do funil a conta está hoje."""
    if conta.plano in planos.PAGOS:
        if conta.assinatura_status == "inadimplente":
            return "inadimplente"
        if conta.assinatura_status == "cancelada":
            return "cancelando"  # cancelou, mas ainda tem acesso até pago_ate
        return "assinante"
    if conta.plano == "suspenso":
        return "cancelado" if conta.assinatura_status == "cancelada" else ("inadimplente" if pagou else "suspenso")
    if planos.teste_expirado(conta):
        return "teste_expirado"
    if n_analises:
        return "engajado"
    if n_empresas:
        return "ativado"
    return "cadastrado"


def _agregados():
    empresas = _por_conta(db.session.query(Empresa.conta_id, db.func.count(Empresa.id)).group_by(Empresa.conta_id))
    analises_total = _por_conta(db.session.query(UsoIA.conta_id, db.func.count(UsoIA.id))
                                .filter(UsoIA.recurso == "analises", UsoIA.cobravel.is_(True)).group_by(UsoIA.conta_id))
    analises_mes = _por_conta(db.session.query(UsoIA.conta_id, db.func.count(UsoIA.id))
                              .filter(UsoIA.recurso == "analises", UsoIA.cobravel.is_(True),
                                      UsoIA.criado_em >= _inicio_mes()).group_by(UsoIA.conta_id))
    custo_total = _por_conta(db.session.query(UsoIA.conta_id, db.func.sum(UsoIA.custo_usd)).group_by(UsoIA.conta_id))
    custo_mes = _por_conta(db.session.query(UsoIA.conta_id, db.func.sum(UsoIA.custo_usd))
                           .filter(UsoIA.criado_em >= _inicio_mes()).group_by(UsoIA.conta_id))
    receita = _por_conta(db.session.query(Cobranca.conta_id, db.func.sum(Cobranca.valor))
                         .filter(Cobranca.status == "aprovado").group_by(Cobranca.conta_id))
    checkout = {cid for (cid,) in db.session.query(Evento.conta_id).filter(Evento.tipo == "checkout").distinct()}
    usuarios = defaultdict(list)
    for u in Usuario.query.all():
        usuarios[u.conta_id].append(u)
    return dict(empresas=empresas, analises_total=analises_total, analises_mes=analises_mes, custo_total=custo_total,
                custo_mes=custo_mes, receita=receita, checkout=checkout, usuarios=usuarios)


def _linha_crm(c, ag):
    us = ag["usuarios"].get(c.id, [])
    acessos = [u.ultimo_acesso for u in us if u.ultimo_acesso]
    p = planos.PLANOS.get(c.plano, planos.PLANOS["suspenso"])
    usd = current_app.config["USD_BRL"]
    receita = float(ag["receita"].get(c.id) or 0)
    custo = float(ag["custo_total"].get(c.id) or 0)
    dias_trial = None
    if c.plano == "trial" and c.trial_fim:
        dias_trial = (c.trial_fim.date() - datetime.utcnow().date()).days
    return {
        **c.to_dict(), "plano_nome": p["nome"], "telefone": c.telefone, "notas_crm": c.notas_crm,
        "etiqueta_crm": c.etiqueta_crm, "origem": c.origem, "campanha": c.campanha,
        "usuarios": [{"nome": u.nome, "email": u.email, "verificado": u.verificado} for u in us],
        "ultimo_acesso": _iso(max(acessos)) if acessos else None,
        "etapa": etapa(c, ag["empresas"].get(c.id, 0), ag["analises_total"].get(c.id, 0), c.id in ag["receita"]),
        "empresas": ag["empresas"].get(c.id, 0),
        "analises_mes": ag["analises_mes"].get(c.id, 0), "analises_total": ag["analises_total"].get(c.id, 0),
        "limite_analises": p["analises"], "dias_trial": dias_trial,
        "custo_ia_mes_brl": round(float(ag["custo_mes"].get(c.id) or 0) * usd, 2),
        "custo_ia_total_brl": round(custo * usd, 2),
        "receita_total": round(receita, 2), "mrr": planos.mrr_da_conta(c),
        "iniciou_checkout": c.id in ag["checkout"],
    }


# ---------------------------------------------------------------- CRM
@bp.get("/crm")
@admin_requerido
def crm():
    ag = _agregados()
    linhas = [_linha_crm(c, ag) for c in Conta.query.order_by(Conta.criado_em.desc()).all()]
    agora = datetime.utcnow()
    resumo = Counter(l["etapa"] for l in linhas)
    return jsonify({
        "contas": linhas,
        "resumo": {
            "total": len(linhas),
            "testes_ativos": sum(1 for l in linhas if l["plano"] == "trial" and l["etapa"] not in ("teste_expirado",)),
            "testes_expirando": sum(1 for l in linhas if l["dias_trial"] is not None and 0 <= l["dias_trial"] <= 2),
            "testes_expirados": resumo["teste_expirado"],
            "assinantes": resumo["assinante"] + resumo["cancelando"],
            "inadimplentes": resumo["inadimplente"],
            "cancelados": resumo["cancelado"] + resumo["cancelando"],
            "novos_7d": sum(1 for c in Conta.query.filter(Conta.criado_em >= agora - timedelta(days=7))),
        },
    })


@bp.get("/crm/<int:cid>")
@admin_requerido
def crm_detalhe(cid):
    c = Conta.query.get_or_404(cid)
    linha = _linha_crm(c, _agregados())
    linha["cobrancas"] = [x.to_dict() for x in
                          Cobranca.query.filter_by(conta_id=cid).order_by(Cobranca.criado_em.desc()).all()]
    linha["uso_recursos"] = {r: n for r, n in db.session.query(UsoIA.recurso, db.func.count(UsoIA.id))
                             .filter(UsoIA.conta_id == cid).group_by(UsoIA.recurso).all()}
    linha["mp_assinatura_id"] = c.mp_assinatura_id
    return jsonify(linha)


# ---------------------------------------------------------------- funil
@bp.get("/funil")
@admin_requerido
def funil():
    dias = max(1, min(int(request.args.get("dias", 30)), 730))
    desde = datetime.utcnow() - timedelta(days=dias)

    def visitantes(tipo):
        return db.session.query(db.func.count(db.distinct(Evento.visitante_id))).filter(
            Evento.tipo == tipo, Evento.criado_em >= desde).scalar() or 0

    contas = Conta.query.filter(Conta.criado_em >= desde).all()
    ids = {c.id for c in contas}
    ag = _agregados()
    pagantes_ids = {cid for cid in ids if cid in ag["receita"]} | \
                   {c.id for c in contas if c.plano in planos.PAGOS}
    etapas = [
        ("visitas", "Visitaram a página inicial", visitantes("visita")),
        ("cta", "Clicaram em testar grátis", visitantes("cta")),
        ("cadastros", "Criaram conta (teste grátis)", len(contas)),
        ("ativados", "Cadastraram a empresa", sum(1 for i in ids if ag["empresas"].get(i))),
        ("engajados", "Fizeram 1ª análise de edital", sum(1 for i in ids if ag["analises_total"].get(i))),
        ("checkout", "Abriram o pagamento", sum(1 for i in ids if i in ag["checkout"])),
        ("pagantes", "Viraram assinantes", len(pagantes_ids)),
    ]

    por_origem = defaultdict(lambda: {"cadastros": 0, "engajados": 0, "pagantes": 0})
    for c in contas:
        o = por_origem[c.origem or "direto / não identificado"]
        o["cadastros"] += 1
        o["engajados"] += 1 if ag["analises_total"].get(c.id) else 0
        o["pagantes"] += 1 if c.id in pagantes_ids else 0

    tempos = []
    primeiro_pgto = _por_conta(db.session.query(Cobranca.conta_id, db.func.min(Cobranca.pago_em))
                               .filter(Cobranca.status == "aprovado").group_by(Cobranca.conta_id))
    for c in contas:
        if primeiro_pgto.get(c.id) and c.criado_em:
            tempos.append((primeiro_pgto[c.id] - c.criado_em).total_seconds() / 86400)

    # Leads para abordar: em teste (ou teste vencido há até 15 dias), sem pagamento, ordenados por "temperatura"
    leads = []
    for c in Conta.query.filter(Conta.plano == "trial").all():
        l = _linha_crm(c, ag)
        if l["receita_total"]:
            continue
        if l["dias_trial"] is not None and l["dias_trial"] < -15:
            continue
        pontos = l["analises_total"] * 3 + (2 if l["empresas"] else 0) + (4 if l["iniciou_checkout"] else 0)
        if l["dias_trial"] is not None and 0 <= l["dias_trial"] <= 2:
            pontos += 3
        l["pontos"] = pontos
        l["temperatura"] = "quente" if pontos >= 7 else "morno" if pontos >= 3 else "frio"
        leads.append(l)
    leads.sort(key=lambda x: (-x["pontos"], x["dias_trial"] if x["dias_trial"] is not None else 99))

    serie = defaultdict(lambda: {"cadastros": 0, "pagantes": 0})
    for c in contas:
        dia = c.criado_em.date().isoformat()
        serie[dia]["cadastros"] += 1
        serie[dia]["pagantes"] += 1 if c.id in pagantes_ids else 0

    return jsonify({
        "dias": dias,
        "etapas": [{"chave": k, "rotulo": r, "total": n} for k, r, n in etapas],
        "por_origem": sorted(({"origem": k, **v} for k, v in por_origem.items()), key=lambda x: -x["cadastros"]),
        "dias_ate_pagar": round(sum(tempos) / len(tempos), 1) if tempos else None,
        "leads": leads[:60],
        "serie": [{"dia": k, **v} for k, v in sorted(serie.items())],
    })


# ---------------------------------------------------------------- receitas
def _mes(dt):
    return f"{dt.year}-{dt.month:02d}"


@bp.get("/receitas")
@admin_requerido
def receitas():
    meses = max(1, min(int(request.args.get("meses", 12)), 36))
    agora = datetime.utcnow()
    ini = _inicio_mes(agora)
    for _ in range(meses - 1):
        ini = _inicio_mes(ini - timedelta(days=1))
    rotulos = []
    d = ini
    while d <= agora:
        rotulos.append(_mes(d))
        d = _inicio_mes(d + timedelta(days=32))
    serie = {m: {"mes": m, "assinaturas": 0.0, "servicos": 0.0, "estornos": 0.0, "tarifas": 0.0, "custo_ia": 0.0}
             for m in rotulos}
    usd = current_app.config["USD_BRL"]

    cobrancas = Cobranca.query.filter(db.or_(Cobranca.pago_em >= ini, Cobranca.criado_em >= ini)).all()
    por_meio, por_plano_recebido = Counter(), Counter()
    for c in cobrancas:
        quando = c.pago_em or c.criado_em
        m = _mes(quando)
        if m not in serie:
            continue
        if c.status == "aprovado":
            chave = "assinaturas" if c.tipo == "assinatura" else "servicos"
            serie[m][chave] += c.valor or 0
            if c.valor_liquido is not None:
                serie[m]["tarifas"] += (c.valor or 0) - c.valor_liquido
            por_meio[c.meio or "outro"] += c.valor or 0
            if c.plano:
                por_plano_recebido[c.plano] += c.valor or 0
        elif c.status == "estornado":
            serie[m]["estornos"] += c.valor or 0

    # Revisões profissionais concluídas contam como receita de serviço (valor combinado na revisão)
    for r in Revisao.query.filter(Revisao.status == "concluida", Revisao.criado_em >= ini).all():
        m = _mes(r.criado_em)
        if m in serie:
            serie[m]["servicos"] += r.valor or 0

    for quando, custo in db.session.query(UsoIA.criado_em, UsoIA.custo_usd).filter(UsoIA.criado_em >= ini).all():
        m = _mes(quando)
        if m in serie:
            serie[m]["custo_ia"] += (custo or 0) * usd

    for s in serie.values():
        s["receita"] = s["assinaturas"] + s["servicos"] - s["estornos"]
        s["resultado"] = s["receita"] - s["tarifas"] - s["custo_ia"]
        for k in list(s):
            if k != "mes":
                s[k] = round(s[k], 2)

    contas = Conta.query.all()
    ativos = [c for c in contas if planos.mrr_da_conta(c) > 0]
    mrr = round(sum(planos.mrr_da_conta(c) for c in ativos), 2)
    mrr_plano = Counter()
    for c in ativos:
        mrr_plano[c.plano] += planos.mrr_da_conta(c)
    mes_atual = serie[_mes(agora)]
    cancel_mes = sum(1 for c in contas if c.cancelado_em and c.cancelado_em >= _inicio_mes(agora))
    base_churn = len(ativos) + cancel_mes
    recentes = Cobranca.query.order_by(db.func.coalesce(Cobranca.pago_em, Cobranca.criado_em).desc()).limit(40).all()
    nomes = {c.id: c.nome for c in contas}
    return jsonify({
        "indicadores": {
            "mrr": mrr, "arr": round(mrr * 12, 2), "assinantes": len(ativos),
            "ticket_medio": round(mrr / len(ativos), 2) if ativos else 0,
            "receita_mes": mes_atual["receita"], "resultado_mes": mes_atual["resultado"],
            "custo_ia_mes": mes_atual["custo_ia"],
            "receita_periodo": round(sum(s["receita"] for s in serie.values()), 2),
            "cancelamentos_mes": cancel_mes,
            "churn_mes": round(100 * cancel_mes / base_churn, 1) if base_churn else 0,
            "pendentes": sum(1 for c in recentes if c.status == "pendente"),
            "usd_brl": usd,
        },
        "serie": list(serie.values()),
        "mrr_por_plano": [{"plano": k, "nome": planos.PLANOS[k]["nome"], "mrr": round(v, 2)} for k, v in mrr_plano.most_common()],
        "por_meio": [{"meio": k, "valor": round(v, 2)} for k, v in por_meio.most_common()],
        "cobrancas": [{**c.to_dict(), "conta": nomes.get(c.conta_id)} for c in recentes],
    })


@bp.post("/receitas")
@admin_requerido
def lancar_receita():
    """Receita recebida fora do Mercado Pago (transferência, consultoria etc.)."""
    d = dados()
    valor = para_float(d.get("valor"))
    if not valor or valor <= 0:
        raise ErroAPI("Informe o valor recebido.")
    conta_id = int(d["conta_id"]) if str(d.get("conta_id") or "").isdigit() else None
    if conta_id and not Conta.query.get(conta_id):
        raise ErroAPI("Conta não encontrada.", 404)
    pago = para_data(d.get("pago_em")) or datetime.utcnow().date()
    tipo = d.get("tipo") if d.get("tipo") in ("assinatura", "servico", "outro") else "outro"
    c = Cobranca(conta_id=conta_id, origem="manual", tipo=tipo, valor=valor, status="aprovado", aplicado=True,
                 meio=(d.get("meio") or "outro")[:30], descricao=(d.get("descricao") or "Lançamento manual")[:300],
                 plano=d.get("plano") if d.get("plano") in planos.PAGOS else None,
                 pago_em=datetime(pago.year, pago.month, pago.day, 12))
    db.session.add(c)
    db.session.commit()
    return jsonify(c.to_dict()), 201


@bp.delete("/receitas/<int:rid>")
@admin_requerido
def excluir_receita(rid):
    c = Cobranca.query.get_or_404(rid)
    if c.origem != "manual":
        raise ErroAPI("Só lançamentos manuais podem ser excluídos. Pagamentos do Mercado Pago são o registro oficial.")
    db.session.delete(c)
    db.session.commit()
    return jsonify({"ok": True})
