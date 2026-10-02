"""Painel do administrador: CRM de contas (testes grátis e assinaturas), funil de conversão
e controle de receitas. Todas as rotas exigem e-mail listado em ADMIN_EMAILS."""
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from flask import Blueprint, current_app, jsonify, request

import planos
from auth import admin_requerido
from extensions import ErroAPI, db
from models import Cobranca, Conta, Empresa, Evento, LogErro, Revisao, UsoIA, Usuario
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
    if planos.codigo(conta) in planos.PAGOS:
        if conta.assinatura_status == "inadimplente":
            return "inadimplente"
        if conta.assinatura_status == "cancelada":
            return "cancelando"  # cancelou, mas ainda tem acesso até pago_ate
        return "assinante"
    if conta.plano == "suspenso":
        return "cancelado" if conta.assinatura_status == "cancelada" else ("inadimplente" if pagou else "suspenso")
    if planos.em_teste(conta):
        return "em_teste"
    if planos.teste_encerrado(conta):
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
    p = planos.dados_plano(c)
    usd = current_app.config["USD_BRL"]
    receita = float(ag["receita"].get(c.id) or 0)
    custo = float(ag["custo_total"].get(c.id) or 0)
    dias_trial = None
    if planos.em_teste(c):
        dias_trial = (c.trial_fim.date() - datetime.utcnow().date()).days
    return {
        **c.to_dict(), "plano_nome": p["nome"] + (" (teste)" if planos.em_teste(c) else ""), "preco_contratado": c.preco_contratado, "telefone": c.telefone, "notas_crm": c.notas_crm,
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
            "testes_ativos": resumo["em_teste"],
            "contas_free": sum(1 for l in linhas if l["plano"] == "free"),
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
    from services import contas
    linha["exclusao"] = contas.resumo(c)   # o que some junto, para a confirmação
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
        ("cta", "Clicaram em criar conta", visitantes("cta")),
        ("cadastros", "Criaram conta (Free)", len(contas)),
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
    for c in Conta.query.filter(Conta.plano.in_(("free", "trial"))).all():
        l = _linha_crm(c, ag)
        if l["receita_total"]:
            continue
        if c.criado_em and c.criado_em < datetime.utcnow() - timedelta(days=90) and not planos.em_teste(c):
            continue
        pontos = l["analises_total"] * 3 + (2 if l["empresas"] else 0) + (4 if l["iniciou_checkout"] else 0) + \
            (3 if planos.em_teste(c) else 0) + (2 if l["analises_mes"] >= l["limite_analises"] else 0)
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
    for r in Revisao.query.filter(Revisao.status == "concluida", Revisao.criado_em >= ini,
                                  Revisao.pago_em.is_(None)).all():
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


# ---------------------------------------------------------------- logs de erros
@bp.get("/logs")
@admin_requerido
def listar_logs():
    q = LogErro.query
    if request.args.get("origem") in ("servidor", "tarefa", "navegador"):
        q = q.filter(LogErro.origem == request.args["origem"])
    situacao = request.args.get("situacao", "abertos")
    if situacao == "abertos":
        q = q.filter(LogErro.resolvido.is_(False))
    elif situacao == "resolvidos":
        q = q.filter(LogErro.resolvido.is_(True))
    dias = max(1, min(int(request.args.get("dias", 30)), 90))
    q = q.filter(LogErro.ultimo_em >= datetime.utcnow() - timedelta(days=dias))
    busca = (request.args.get("q") or "").strip()
    if busca:
        like = f"%{busca}%"
        q = q.filter(db.or_(LogErro.mensagem.ilike(like), LogErro.rota.ilike(like), LogErro.usuario_email.ilike(like)))
    itens = q.order_by(LogErro.ultimo_em.desc()).limit(300).all()
    abertos = LogErro.query.filter(LogErro.resolvido.is_(False)).count()
    ult24 = LogErro.query.filter(LogErro.ultimo_em >= datetime.utcnow() - timedelta(hours=24)).count()
    return jsonify({"logs": [l.to_dict() for l in itens], "abertos": abertos, "ultimas_24h": ult24})


@bp.get("/logs/<int:lid>")
@admin_requerido
def ver_log(lid):
    return jsonify(LogErro.query.get_or_404(lid).to_dict(completo=True))


@bp.patch("/logs/<int:lid>")
@admin_requerido
def resolver_log(lid):
    l = LogErro.query.get_or_404(lid)
    l.resolvido = bool(dados().get("resolvido", True))
    db.session.commit()
    return jsonify(l.to_dict())


@bp.post("/logs/resolver-todos")
@admin_requerido
def resolver_todos():
    n = LogErro.query.filter(LogErro.resolvido.is_(False)).update({"resolvido": True})
    db.session.commit()
    return jsonify({"resolvidos": n})


@bp.get("/logs/exportar")
@admin_requerido
def exportar_logs():
    """Texto pronto para colar numa conversa de análise (sem dados de pagamento; e-mail do usuário incluído)."""
    ids = [int(x) for x in (request.args.get("ids") or "").split(",") if x.strip().isdigit()]
    q = LogErro.query.filter(LogErro.id.in_(ids)) if ids else LogErro.query.filter(LogErro.resolvido.is_(False))
    linhas = [f"Kasiski — relatório de erros ({datetime.utcnow():%d/%m/%Y %H:%M} UTC)", ""]
    for l in q.order_by(LogErro.ultimo_em.desc()).limit(50).all():
        linhas += [f"### #{l.id} · {l.origem} · {l.nivel} · {l.ocorrencias}x · primeiro {l.criado_em:%d/%m %H:%M} · último {l.ultimo_em:%d/%m %H:%M} UTC",
                   f"Rota: {l.metodo or ''} {l.rota or '-'}{f' (HTTP {l.status})' if l.status else ''}",
                   f"Usuário: {l.usuario_email or '-'}", f"Navegador: {l.navegador or '-'}", f"Mensagem: {l.mensagem}"]
        if l.detalhe:
            linhas += ["Detalhe:", "```", l.detalhe[-6000:], "```"]
        linhas.append("")
    return current_app.response_class("\n".join(linhas), mimetype="text/plain; charset=utf-8")


@bp.get("/armazenamento")
@admin_requerido
def armazenamento_visao():
    from services import armazenamento
    return jsonify(armazenamento.medir())


@bp.post("/armazenamento/limpar")
@admin_requerido
def armazenamento_limpar():
    from services import armazenamento
    return jsonify(armazenamento.limpar())


# ---------------------------------------------------------------- tabela 2026: economia dos planos e transição
ESTIMATIVA_USD = {"analises": 0.32, "concorrentes": 0.15, "possiveis": 0.0, "pecas": 0.12, "propostas": 0.20}


@bp.get("/planos/economia")
@admin_requerido
def economia_planos():
    """Custo de IA por uso (real, últimos 90 dias; estimado sem dados) e margem de cada plano no uso máximo."""
    desde = datetime.utcnow() - timedelta(days=90)
    usd = current_app.config["USD_BRL"]
    custo_uso = {}
    for rec, est in ESTIMATIVA_USD.items():
        total = db.session.query(db.func.coalesce(db.func.sum(UsoIA.custo_usd), 0)).filter(
            UsoIA.recurso == rec, UsoIA.criado_em >= desde).scalar() or 0
        n = UsoIA.query.filter(UsoIA.recurso == rec, UsoIA.cobravel.is_(True), UsoIA.criado_em >= desde).count()
        custo_uso[rec] = {"usd": round(total / n, 4) if n >= 5 else est, "amostra": n, "real": n >= 5}
    taxa_pagamento, infra = 0.0499, 4.0   # Mercado Pago (cartão, aprox.) e infraestrutura por conta ativa (R$/mês)
    linhas = []
    for k in planos.ORDEM:
        p = planos.PLANOS[k]
        if p["preco"] is None:
            continue
        ia = sum((p.get(r) or 0) * custo_uso[r]["usd"] for r in ("analises", "concorrentes", "possiveis", "pecas"))
        ia += (custo_uso["propostas"]["usd"] * 10 if p.get("propostas") else 0)
        ia_brl = ia * usd
        cmv = ia_brl + infra + p["preco"] * taxa_pagamento
        margem = (p["preco"] - cmv) / p["preco"] * 100 if p["preco"] else None
        linhas.append({"plano": k, "nome": p["nome"], "preco": p["preco"], "ia_max_brl": round(ia_brl, 2),
                       "cmv_max_brl": round(cmv, 2), "margem_uso_maximo": round(margem, 1) if margem is not None else None,
                       "limites": {r: p.get(r) for r in ("analises", "concorrentes", "possiveis", "pecas")}})
    # uso real médio por conta em cada plano (mês corrente)
    ini = datetime(datetime.utcnow().year, datetime.utcnow().month, 1)
    reais = defaultdict(list)
    for c in Conta.query.all():
        gasto = db.session.query(db.func.coalesce(db.func.sum(UsoIA.custo_usd), 0)).filter(UsoIA.conta_id == c.id, UsoIA.criado_em >= ini).scalar() or 0
        reais[planos.efetivo(c)].append(float(gasto) * usd)
    for l in linhas:
        v = reais.get(l["plano"], [])
        l["contas"], l["ia_media_real_brl"] = len(v), round(sum(v) / len(v), 2) if v else None
    return jsonify({"custo_por_uso": custo_uso, "planos": linhas, "usd_brl": usd, "taxa_pagamento": taxa_pagamento, "infra_por_conta": infra,
                    "creditos": planos.CREDITOS, "pacote": planos.PACOTE_INTELIGENCIA})


@bp.get("/planos/transicao")
@admin_requerido
def transicao_planos():
    """Assinantes da tabela antiga: plano novo, valor contratado e se a cobrança automática precisa ser reduzida."""
    saida = []
    for c in Conta.query.filter(Conta.preco_contratado.isnot(None)).all():
        tabela = planos.preco(planos.codigo(c), "mensal") if planos.PLANOS.get(planos.codigo(c), {}).get("preco") else None
        u = Usuario.query.filter_by(conta_id=c.id).order_by(Usuario.id).first()
        saida.append({"id": c.id, "nome": c.nome, "email": u.email if u else None, "plano": planos.codigo(c),
                      "preco_contratado": c.preco_contratado, "preco_tabela": tabela, "metodo": c.metodo_pagamento,
                      "status": c.assinatura_status, "reduzir": bool(tabela and c.preco_contratado > tabela),
                      "recorrente": c.metodo_pagamento == "recorrente" and bool(c.mp_assinatura_id)})
    return jsonify(saida)


@bp.post("/planos/transicao/aplicar")
@admin_requerido
def aplicar_transicao():
    """Reduz no Mercado Pago as assinaturas automáticas que pagam acima da tabela nova (ex.: Consultor R$ 1.290 → R$ 797)."""
    from services import mercadopago as mp
    feitos, falhas = [], []
    for c in Conta.query.filter(Conta.preco_contratado.isnot(None)).all():
        tabela = planos.PLANOS.get(planos.codigo(c), {}).get("preco")
        if not tabela or c.preco_contratado <= tabela:
            continue
        if c.metodo_pagamento == "recorrente" and c.mp_assinatura_id and mp.configurado():
            valor = tabela * (current_app.config["ANUAL_MESES_PAGOS"] if c.ciclo == "anual" else 1)
            try:
                mp.atualizar_valor_assinatura(c.mp_assinatura_id, valor)
            except Exception as e:
                falhas.append({"id": c.id, "nome": c.nome, "erro": str(getattr(e, "mensagem", e))[:200]})
                continue
        c.preco_contratado = None  # passa a pagar a tabela nova (menor)
        feitos.append({"id": c.id, "nome": c.nome, "novo_valor": tabela})
    db.session.commit()
    return jsonify({"ajustados": feitos, "falhas": falhas})


# ---------------------------------------------------------------- faturamento (notas fiscais)
def _cobrancas_faturamento():
    from services import fiscal
    situacao = request.args.get("situacao", "pendente")
    q = Cobranca.query.filter(Cobranca.status.in_(["aprovado", "estornado", "cancelado"]))
    de, ate = para_data(request.args.get("de")), para_data(request.args.get("ate"))
    if de:
        q = q.filter(Cobranca.pago_em >= datetime(de.year, de.month, de.day))
    if ate:
        q = q.filter(Cobranca.pago_em < datetime(ate.year, ate.month, ate.day) + timedelta(days=1))
    cobs = q.order_by(Cobranca.pago_em.asc().nullslast(), Cobranca.id.asc()).all()
    contas = {c.id: c for c in Conta.query.filter(Conta.id.in_({x.conta_id for x in cobs if x.conta_id})).all()} if cobs else {}
    linhas = [fiscal.linha(c, contas.get(c.conta_id)) for c in cobs]
    linhas = [l for l in linhas if l["nf_status"]]  # estornos sem nota não aparecem
    if situacao != "todas":
        linhas = [l for l in linhas if l["nf_status"] == situacao]
    return linhas


@bp.get("/faturamento")
@admin_requerido
def faturamento():
    from services import fiscal
    linhas = _cobrancas_faturamento()
    resumo = Counter()
    for c in Cobranca.query.filter(Cobranca.status.in_(["aprovado", "estornado", "cancelado"])).all():
        resumo[fiscal.situacao_nf(c) or "-"] += 1
    return jsonify({"itens": linhas, "total": round(sum(l["valor"] or 0 for l in linhas), 2),
                    "resumo": {k: v for k, v in resumo.items() if k != "-"}, "prestador": fiscal.prestador()})


@bp.patch("/faturamento/<int:cid>")
@admin_requerido
def marcar_nota(cid):
    from services import fiscal
    c = Cobranca.query.get_or_404(cid)
    d = dados()
    st = d.get("nf_status")
    if st not in ("emitida", "nao_emitir", "pendente", "cancelada"):
        raise ErroAPI("Situação inválida.")
    if st == "emitida":
        numero = (d.get("nf_numero") or "").strip()
        if not numero:
            raise ErroAPI("Informe o número da nota emitida.")
        conta = Conta.query.get(c.conta_id) if c.conta_id else None
        c.nf_numero = numero[:40]
        c.nf_emitida_em = c.nf_emitida_em or datetime.utcnow()
        c.nf_tomador = c.nf_tomador or (conta.dados_fiscais if conta else None)
    elif st == "pendente":
        c.nf_numero, c.nf_emitida_em, c.nf_tomador = None, None, None
    c.nf_status = None if st == "pendente" else st
    if "nf_obs" in d:
        c.nf_obs = (d.get("nf_obs") or "").strip()[:300] or None
    db.session.commit()
    return jsonify(fiscal.linha(c, Conta.query.get(c.conta_id) if c.conta_id else None))


@bp.get("/faturamento.csv")
@admin_requerido
def faturamento_csv():
    import csv
    import io
    from flask import Response
    from services import fiscal
    pr = fiscal.prestador()
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["id_cobranca", "data_pagamento", "valor", "meio", "situacao_nf", "numero_nf", "tomador_tipo", "tomador_documento",
                "tomador_nome", "tomador_email", "cep", "logradouro", "numero", "complemento", "bairro", "municipio", "uf",
                "codigo_ibge", "inscricao_municipal", "codigo_servico", "discriminacao", "transacao_mercado_pago", "conta"])
    for l in _cobrancas_faturamento():
        t = l["tomador"] or {}
        w.writerow([l["id"], (l["pago_em"] or "")[:10], f'{(l["valor"] or 0):.2f}'.replace(".", ","), l["meio"], l["nf_status"], l["nf_numero"] or "",
                    t.get("tipo", ""), t.get("documento_formatado", ""), t.get("nome", ""), t.get("email", ""), t.get("cep", ""),
                    t.get("logradouro", ""), t.get("numero", ""), t.get("complemento", ""), t.get("bairro", ""), t.get("municipio", ""),
                    t.get("uf", ""), t.get("codigo_ibge", ""), t.get("inscricao_municipal", ""), pr.get("codigo_servico") or "",
                    l["discriminacao"], l["mp_pagamento_id"] or "", l["conta"] or ""])
    nome = f"kasiski-faturamento-{datetime.utcnow():%Y%m%d}.csv"
    return Response("﻿" + buf.getvalue(), content_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{nome}"'})
