"""Cadastro, login, conta, plano e painel do administrador (revisões e planos)."""
import re
from datetime import datetime, timedelta

from flask import Blueprint, current_app, g, jsonify
from werkzeug.security import check_password_hash, generate_password_hash

import planos
from auth import admin_requerido, eh_admin, gerar_token, gerar_token_verificacao, login_requerido, usuario_do_token_verificacao
from extensions import ErroAPI, db
from models import Conta, Revisao, UsoIA, Usuario
from routes import dados, para_data
from services import llm, verificacao

bp = Blueprint("conta", __name__, url_prefix="/api")


@bp.get("/planos")
def planos_publicos():
    """Tabela de planos para a página inicial (sem login). Fonte única: planos.PLANOS."""
    visiveis = {k: v for k, v in planos.PLANOS.items() if k != "suspenso"}
    return jsonify({"planos": visiveis, "trial_dias": 7, "anual_meses_pagos": current_app.config["ANUAL_MESES_PAGOS"]})


@bp.post("/auth/registro")
def registro():
    d = dados()
    nome, email, senha = (d.get("nome") or "").strip(), (d.get("email") or "").strip().lower(), d.get("senha") or ""
    if not nome or not re.match(r"[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise ErroAPI("Informe nome e um e-mail válido.")
    if len(senha) < 8:
        raise ErroAPI("A senha precisa ter pelo menos 8 caracteres.")
    if Usuario.query.filter_by(email=email).first():
        raise ErroAPI("Já existe uma conta com este e-mail. Entre com sua senha.")
    conta = Conta(nome=(d.get("nome_conta") or nome).strip(), plano="trial",
                  trial_fim=datetime.utcnow() + timedelta(days=7),
                  telefone=(d.get("telefone") or "").strip()[:30] or None,
                  origem=(d.get("origem") or "").strip()[:80] or None,
                  campanha=(d.get("campanha") or "").strip()[:120] or None,
                  visitante_id=(d.get("visitante") or "").strip()[:40] or None)
    db.session.add(conta)
    db.session.flush()
    exigir = verificacao.exigida()
    u = Usuario(conta_id=conta.id, nome=nome, email=email, senha_hash=generate_password_hash(senha),
                modo_guiado=d.get("perfil") != "experiente", email_verificado=not exigir)
    db.session.add(u)
    db.session.commit()
    if exigir:
        return _pedir_verificacao(u, primeiro=True), 201
    return jsonify({"token": gerar_token(u), "usuario": u.to_dict(eh_admin(u))}), 201


def _pedir_verificacao(u, primeiro=False):
    try:
        verificacao.enviar_codigo(u)
        aviso = None
    except ErroAPI as e:
        if e.codigo not in ("aguarde",):  # um código recente ainda vale: segue para a tela do código
            raise
        aviso = e.mensagem
    return jsonify({"verificacao_pendente": True, "token_verificacao": gerar_token_verificacao(u),
                    "email": u.email, "novo_cadastro": primeiro, "aviso": aviso})


@bp.post("/auth/verificar")
def verificar_email():
    d = dados()
    u = usuario_do_token_verificacao(d.get("token_verificacao"))
    if not u.verificado:
        verificacao.conferir(u, d.get("codigo"))
    return jsonify({"token": gerar_token(u), "usuario": u.to_dict(eh_admin(u))})


@bp.post("/auth/reenviar-codigo")
def reenviar_codigo():
    u = usuario_do_token_verificacao(dados().get("token_verificacao"))
    if u.verificado:
        return jsonify({"ok": True, "ja_verificado": True})
    verificacao.enviar_codigo(u)
    return jsonify({"ok": True})


@bp.post("/auth/login")
def login():
    d = dados()
    u = Usuario.query.filter_by(email=(d.get("email") or "").strip().lower()).first()
    agora = datetime.utcnow()
    if u and u.bloqueado_ate and u.bloqueado_ate > agora:
        minutos = int((u.bloqueado_ate - agora).total_seconds() // 60) + 1
        raise ErroAPI(f"Muitas tentativas de senha. Por segurança, o acesso foi pausado por {minutos} minuto(s).", 429,
                      "bloqueado")
    if not u or not check_password_hash(u.senha_hash, d.get("senha") or ""):
        if u:
            u.falhas_login = (u.falhas_login or 0) + 1
            if u.falhas_login >= 5:
                u.bloqueado_ate = agora + timedelta(minutes=15)
                u.falhas_login = 0
            db.session.commit()
        raise ErroAPI("E-mail ou senha incorretos.", 401)
    if u.falhas_login or u.bloqueado_ate:
        u.falhas_login, u.bloqueado_ate = 0, None
        db.session.commit()
    if not u.verificado:
        return _pedir_verificacao(u)
    return jsonify({"token": gerar_token(u), "usuario": u.to_dict(eh_admin(u))})


@bp.get("/conta")
@login_requerido
def ver_conta():
    return jsonify({"usuario": g.usuario.to_dict(g.admin), "conta": g.conta.to_dict(),
                    "plano": planos.resumo(g.conta), "planos": planos.PLANOS,
                    "modo_demonstracao": llm.modo_demonstracao(),
                    "cobranca": {"online": bool(current_app.config["MP_ACCESS_TOKEN"]),
                                 "anual_meses_pagos": current_app.config["ANUAL_MESES_PAGOS"]}})


@bp.patch("/conta")
@login_requerido
def editar_conta():
    d = dados()
    if "modo_guiado" in d:
        g.usuario.modo_guiado = bool(d["modo_guiado"])
    if "nome" in d and d["nome"].strip():
        g.usuario.nome = d["nome"].strip()
    if "marca_relatorio" in d:
        if not planos.PLANOS.get(g.conta.plano, {}).get("marca"):
            raise ErroAPI("Relatórios com a marca do escritório fazem parte do plano Consultor.", 402)
        g.conta.marca_relatorio = (d["marca_relatorio"] or "").strip()[:200] or None
    if d.get("nova_senha"):
        if not check_password_hash(g.usuario.senha_hash, d.get("senha_atual") or ""):
            raise ErroAPI("Senha atual incorreta.")
        if len(d["nova_senha"]) < 8:
            raise ErroAPI("A nova senha precisa ter pelo menos 8 caracteres.")
        g.usuario.senha_hash = generate_password_hash(d["nova_senha"])
    db.session.commit()
    return ver_conta()


# ---------------------------------------------------------------- administrador
@bp.get("/admin/revisoes")
@admin_requerido
def admin_revisoes():
    rs = Revisao.query.order_by(Revisao.criado_em.desc()).limit(200).all()
    saida = []
    for r in rs:
        d = r.to_dict()
        d["conta"] = Conta.query.get(r.conta_id).nome
        d["conteudo"] = r.peca.conteudo if r.peca else ""
        saida.append(d)
    return jsonify(saida)


@bp.patch("/admin/revisoes/<int:rid>")
@admin_requerido
def admin_atualizar_revisao(rid):
    r = Revisao.query.get_or_404(rid)
    d = dados()
    if d.get("status") in ("pendente", "em_andamento", "concluida", "cancelada"):
        r.status = d["status"]
    if "parecer" in d:
        r.parecer = d["parecer"]
    if "valor" in d:
        r.valor = float(d["valor"] or 0)
    if d.get("conteudo_revisado") and r.peca:
        r.peca.conteudo = d["conteudo_revisado"]
    if r.status == "concluida" and r.peca:
        r.peca.status = "revisada"
    db.session.commit()
    return jsonify(r.to_dict())


@bp.get("/admin/contas")
@admin_requerido
def admin_contas():
    saida = []
    for c in Conta.query.order_by(Conta.criado_em.desc()).all():
        custo = db.session.query(db.func.coalesce(db.func.sum(UsoIA.custo_usd), 0)).filter(
            UsoIA.conta_id == c.id).scalar()
        usuarios = Usuario.query.filter_by(conta_id=c.id).all()
        saida.append({**c.to_dict(), "usuarios": [u.email for u in usuarios],
                      "custo_ia_total_usd": round(float(custo or 0), 4), "uso": planos.resumo(c)["uso"]})
    return jsonify(saida)


@bp.patch("/admin/contas/<int:cid>")
@admin_requerido
def admin_atualizar_conta(cid):
    c = Conta.query.get_or_404(cid)
    d = dados()
    if d.get("plano") in planos.PLANOS:
        c.plano = d["plano"]
    if d.get("trial_fim"):
        dt = para_data(d["trial_fim"])
        c.trial_fim = datetime(dt.year, dt.month, dt.day, 23, 59)
    if d.get("estender_trial_dias"):
        base = c.trial_fim if c.trial_fim and c.trial_fim > datetime.utcnow() else datetime.utcnow()
        c.trial_fim = base + timedelta(days=int(d["estender_trial_dias"]))
        c.plano = "trial"
    if "pago_ate" in d:
        dt = para_data(d["pago_ate"])
        c.pago_ate = datetime(dt.year, dt.month, dt.day, 23, 59) if dt else None
    if d.get("assinatura_status") in ("ativa", "pendente", "pausada", "cancelada", "inadimplente", ""):
        c.assinatura_status = d["assinatura_status"] or None
    if d.get("ciclo") in ("mensal", "anual"):
        c.ciclo = d["ciclo"]
    for campo, n in (("notas_crm", 5000), ("telefone", 30), ("etiqueta_crm", 30)):
        if campo in d:
            setattr(c, campo, (d[campo] or "").strip()[:n] or None)
    db.session.commit()
    return jsonify(c.to_dict())
