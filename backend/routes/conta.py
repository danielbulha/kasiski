"""Cadastro, login, conta, plano e painel do administrador (revisões e planos)."""
import re
from datetime import datetime, timedelta

from flask import Blueprint, current_app, g, jsonify
from werkzeug.security import check_password_hash, generate_password_hash

import planos
from auth import admin_requerido, eh_admin, gerar_token, gerar_token_verificacao, login_requerido, usuario_do_token_verificacao
from extensions import ErroAPI, db
from models import Conta, Revisao, UsoIA, Usuario
from routes import dados, para_data, para_float
from services import llm, verificacao

bp = Blueprint("conta", __name__, url_prefix="/api")


@bp.get("/planos")
def planos_publicos():
    """Tabela de planos para a página inicial (sem login). Fonte única: planos.PLANOS."""
    visiveis = {k: planos.PLANOS[k] for k in planos.ORDEM}
    return jsonify({"planos": visiveis, "ordem": list(planos.ORDEM), "trial_dias": planos.TRIAL_DIAS, "trial_plano": planos.TRIAL_PLANO,
                    "anual_meses_pagos": current_app.config["ANUAL_MESES_PAGOS"], "pacote_inteligencia": planos.PACOTE_INTELIGENCIA,
                    "empresa_extra": planos.EMPRESA_EXTRA_PRECO, "pacote_contratos": planos.PACOTE_CONTRATOS})


@bp.post("/auth/registro")
def registro():
    d = dados()
    ip = _limite_ip("cadastro", current_app.config["CADASTROS_IP_HORA"], 60,
                    "Muitos cadastros a partir desta rede na última hora. Tente de novo mais tarde.")
    _registrar_ip("cadastro", ip)
    nome, email, senha = (d.get("nome") or "").strip(), (d.get("email") or "").strip().lower(), d.get("senha") or ""
    if not nome or not re.match(r"[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise ErroAPI("Informe nome e um e-mail válido.")
    if len(senha) < 8:
        raise ErroAPI("A senha precisa ter pelo menos 8 caracteres.")
    if Usuario.query.filter_by(email=email).first():
        raise ErroAPI("Já existe uma conta com este e-mail. Entre com sua senha.")
    conta = Conta(nome=(d.get("nome_conta") or nome).strip(), plano="free", tabela_precos=2026,
                  telefone=(d.get("telefone") or "").strip()[:30] or None,
                  origem=(d.get("origem") or "").strip()[:80] or None,
                  campanha=(d.get("campanha") or "").strip()[:120] or None,
                  visitante_id=(d.get("visitante") or "").strip()[:40] or None)
    db.session.add(conta)
    db.session.flush()
    exigir = verificacao.exigida()
    admin = email in current_app.config["ADMIN_EMAILS"]
    u = Usuario(conta_id=conta.id, nome=nome, email=email, senha_hash=generate_password_hash(senha), papel="dono",
                modo_guiado=d.get("perfil") != "experiente", email_verificado=not (exigir or admin))
    db.session.add(u)
    db.session.flush()
    from services import marketing
    aq = d.get("aquisicao") if isinstance(d.get("aquisicao"), dict) else {}
    marketing.vincular_cadastro(conta, u, aq.get("primeiro"), aq.get("ultimo"))
    db.session.commit()
    if exigir:
        return _pedir_verificacao(u, primeiro=True), 201
    return jsonify({"token": gerar_token(u), "usuario": u.to_dict(eh_admin(u))}), 201


def _pedir_verificacao(u, primeiro=False):
    try:
        verificacao.enviar_codigo(u)
        aviso = None
    except ErroAPI as e:
        # Código recente ainda válido, limite de envios ou falha do provedor: a conta já existe, então
        # segue para a tela do código (com aviso) em vez de travar o cadastro; lá dá para reenviar.
        if e.codigo == "email_falhou":
            aviso = "Não conseguimos enviar o e-mail agora. Aguarde um minuto e clique em \"Reenviar código\"."
        elif e.codigo in ("aguarde", "limite_envios"):
            aviso = e.mensagem
        else:
            raise
    return jsonify({"verificacao_pendente": True, "token_verificacao": gerar_token_verificacao(u),
                    "email": u.email, "novo_cadastro": primeiro, "aviso": aviso})


@bp.post("/auth/verificar")
def verificar_email():
    d = dados()
    _registrar_ip("codigo", _limite_ip("codigo", current_app.config["CODIGOS_IP_HORA"] * 2, 60,
                                       "Muitas tentativas de código a partir desta rede. Aguarde e tente de novo."))
    u = usuario_do_token_verificacao(d.get("token_verificacao"))
    if not u.verificado:
        verificacao.conferir(u, d.get("codigo"))
    return jsonify({"token": gerar_token(u), "usuario": u.to_dict(eh_admin(u))})


@bp.post("/auth/reenviar-codigo")
def reenviar_codigo():
    _registrar_ip("codigo_envio", _limite_ip("codigo_envio", current_app.config["CODIGOS_IP_HORA"], 60,
                                             "Muitos pedidos de código a partir desta rede. Aguarde e tente de novo."))
    u = usuario_do_token_verificacao(dados().get("token_verificacao"))
    if u.verificado:
        return jsonify({"ok": True, "ja_verificado": True})
    verificacao.enviar_codigo(u)
    return jsonify({"ok": True})


def _ip():
    from services.publico import ip_hash
    return ip_hash()


def _limite_ip(tipo, maximo, minutos, mensagem):
    """Conta os eventos do IP na janela (tabela uso_publico, compartilhada entre os processos do servidor)."""
    from models import UsoPublico
    desde = datetime.utcnow() - timedelta(minutes=minutos)
    ip = _ip()
    if UsoPublico.query.filter(UsoPublico.tipo == tipo, UsoPublico.ip_hash == ip, UsoPublico.criado_em >= desde).count() >= maximo:
        raise ErroAPI(mensagem, 429, "limite_ip")
    return ip


def _registrar_ip(tipo, ip):
    from models import UsoPublico
    db.session.add(UsoPublico(tipo=tipo, ip_hash=ip))
    db.session.commit()


@bp.post("/auth/login")
def login():
    d = dados()
    ip = _limite_ip("login_falha", current_app.config["LOGIN_FALHAS_IP"], 15,
                    "Muitas tentativas de login a partir desta rede. Aguarde 15 minutos e tente de novo.")
    u = Usuario.query.filter_by(email=(d.get("email") or "").strip().lower()).first()
    if u:
        _conferir_bloqueio_conta(u, ip)
    if not u or not check_password_hash(u.senha_hash, d.get("senha") or ""):
        _registrar_ip("login_falha", ip)
        if u:
            from models import UsoPublico
            db.session.add(UsoPublico(tipo="login_conta", ip_hash=ip, email=u.email))
            db.session.commit()
        raise ErroAPI("E-mail ou senha incorretos.", 401)
    _limpar_falhas_conta(u, ip)
    if not u.verificado and verificacao.exigida():
        return _pedir_verificacao(u)
    return jsonify({"token": gerar_token(u), "usuario": u.to_dict(eh_admin(u))})


def _conferir_bloqueio_conta(u, ip):
    """Pausa as tentativas numa conta só para quem está errando a senha dela (conta + IP). Assim um terceiro que
    sabe o e-mail não consegue travar o acesso do dono, que entra de outra rede. Se a conta recebe muitas senhas
    erradas de vários IPs (ataque distribuído), toda rede que já errou nela fica pausada por 1 hora."""
    from models import UsoPublico
    cfg, agora = current_app.config, datetime.utcnow()
    q = UsoPublico.query.filter(UsoPublico.tipo == "login_conta", UsoPublico.email == u.email)
    if q.filter(UsoPublico.ip_hash == ip, UsoPublico.criado_em >= agora - timedelta(minutes=15)).count() \
            >= cfg["LOGIN_FALHAS_CONTA_IP"]:
        raise ErroAPI("Muitas tentativas de senha. Por segurança, o acesso desta rede foi pausado por 15 minutos.", 429,
                      "bloqueado")
    hora = q.filter(UsoPublico.criado_em >= agora - timedelta(hours=1))
    if hora.count() >= cfg["LOGIN_FALHAS_CONTA_HORA"] and hora.filter(UsoPublico.ip_hash == ip).first():
        raise ErroAPI("Muitas tentativas de senha nesta conta. Por segurança, o acesso desta rede foi pausado por 1 hora.",
                      429, "bloqueado")


def _limpar_falhas_conta(u, ip):
    """Senha certa: zera as falhas desta rede na conta (as de outras redes continuam contando)."""
    from models import UsoPublico
    UsoPublico.query.filter(UsoPublico.tipo == "login_conta", UsoPublico.email == u.email,
                            UsoPublico.ip_hash == ip).delete(synchronize_session=False)
    db.session.commit()


@bp.get("/conta")
@login_requerido
def ver_conta():
    return _dados_conta()


def _dados_conta():
    if g.usuario.tour is None:
        # quem já usava o Kasiski antes do tour não é interrompido; o tour aparece na próxima mudança de plano
        # (e pode ser feito a qualquer momento em Plano e conta)
        antigo = g.usuario.criado_em and g.usuario.criado_em < datetime.utcnow() - timedelta(days=2)
        g.usuario.tour = {planos.efetivo(g.conta): "anterior"} if antigo else {}
        db.session.commit()
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
    if isinstance(d.get("tour"), dict):  # {"planos": ["free", ...], "estado": "concluido"|"pulado"} ou {"reiniciar": true}
        t = {} if d["tour"].get("reiniciar") else dict(g.usuario.tour or {})
        if d["tour"].get("estado") in ("concluido", "pulado"):
            for p in (d["tour"].get("planos") or [])[:8]:
                if p in planos.ORDEM:
                    t[p] = d["tour"]["estado"]
        g.usuario.tour = t
    if "nome" in d and d["nome"].strip():
        g.usuario.nome = d["nome"].strip()
    if "marca_relatorio" in d:
        if not planos.dados_plano(g.conta).get("marca"):
            raise ErroAPI("Relatórios com a marca do escritório fazem parte do plano Consultor.", 402)
        g.conta.marca_relatorio = (d["marca_relatorio"] or "").strip()[:200] or None
    if d.get("nova_senha"):
        if not check_password_hash(g.usuario.senha_hash, d.get("senha_atual") or ""):
            raise ErroAPI("Senha atual incorreta.")
        if len(d["nova_senha"]) < 8:
            raise ErroAPI("A nova senha precisa ter pelo menos 8 caracteres.")
        g.usuario.senha_hash = generate_password_hash(d["nova_senha"])
        g.usuario.token_versao = (g.usuario.token_versao or 0) + 1   # encerra as sessões abertas em outros aparelhos
        db.session.commit()
        return jsonify({**_dados_conta().get_json(), "token": gerar_token(g.usuario)})
    db.session.commit()
    return _dados_conta()


# ---------------------------------------------------------------- teste do Profissional (a conta segue no Free)
@bp.post("/conta/teste")
@login_requerido
def iniciar_teste():
    fim = planos.iniciar_teste(g.conta)
    db.session.commit()
    return jsonify({"trial_fim": fim.isoformat(), "plano": planos.resumo(g.conta)})


# ---------------------------------------------------------------- equipe (usuários da conta)
def _dono():
    if g.usuario.papel not in (None, "dono") and not g.admin:
        raise ErroAPI("Só o responsável pela conta pode gerenciar a equipe.", 403)


@bp.get("/conta/equipe")
@login_requerido
def equipe():
    from models import Convite
    membros = Usuario.query.filter_by(conta_id=g.conta.id).order_by(Usuario.id).all()
    convites = Convite.query.filter(Convite.conta_id == g.conta.id, Convite.aceito_em.is_(None),
                                    Convite.expira_em > datetime.utcnow()).order_by(Convite.id.desc()).all()
    return jsonify({"membros": [{"id": u.id, "nome": u.nome, "email": u.email, "papel": u.papel or "dono",
                                 "ultimo_acesso": u.ultimo_acesso.isoformat() if u.ultimo_acesso else None, "voce": u.id == g.usuario.id}
                                for u in membros],
                    "convites": [c.to_dict() for c in convites], "limite": planos.dados_plano(g.conta).get("usuarios"),
                    "posso_gerenciar": g.usuario.papel in (None, "dono")})


@bp.post("/conta/equipe/convites")
@login_requerido
def convidar():
    import secrets
    from models import Convite
    from services import email as em
    _dono()
    email = (dados().get("email") or "").strip().lower()
    if not re.match(r"[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise ErroAPI("Informe um e-mail válido.")
    if email in current_app.config["ADMIN_EMAILS"]:
        raise ErroAPI("Este e-mail não pode ser convidado. Fale com o suporte.")
    existente = Usuario.query.filter_by(email=email).first()
    if existente:
        raise ErroAPI("Este e-mail já tem uma conta no Kasiski. Peça para a pessoa usar outro e-mail ou fale com o suporte.")
    Convite.query.filter(Convite.conta_id == g.conta.id, Convite.email == email, Convite.aceito_em.is_(None)).delete()
    planos.exigir(g.conta, "usuarios")
    c = Convite(conta_id=g.conta.id, email=email, token=secrets.token_urlsafe(32), convidado_por=g.usuario.id,
                expira_em=datetime.utcnow() + timedelta(days=7))
    db.session.add(c)
    db.session.commit()
    link = f"{current_app.config['FRONTEND_URL']}/#/convite?t={c.token}"
    enviado = False
    if em.configurado():
        corpo = em.layout_marketing(f"{em.esc(g.usuario.nome)} convidou você para o Kasiski",
                                    f"<p>Você foi convidado para a equipe <b>{em.esc(g.conta.nome)}</b> no Kasiski, a plataforma de "
                                    "inteligência para licitações. Crie sua senha para entrar.</p>"
                                    "<p style='color:#4F6373;font-size:13px'>O convite vale por 7 dias.</p>",
                                    "Aceitar o convite", link)
        try:
            enviado = em.enviar(email, f"Convite para a equipe {g.conta.nome} no Kasiski", f"Aceite em: {link}", corpo)
        except ErroAPI:
            enviado = False
    c.enviado_email = bool(enviado)
    db.session.commit()
    # Link entregue por e-mail não volta para quem convidou (senão daria para "provar" um e-mail alheio).
    return jsonify({**c.to_dict(), "link": None if enviado else link, "email_enviado": bool(enviado)}), 201


@bp.delete("/conta/equipe/convites/<int:cid>")
@login_requerido
def cancelar_convite(cid):
    from models import Convite
    _dono()
    c = Convite.query.filter_by(id=cid, conta_id=g.conta.id).first_or_404()
    db.session.delete(c)
    db.session.commit()
    return jsonify({"ok": True})


@bp.delete("/conta/equipe/<int:uid>")
@login_requerido
def remover_membro(uid):
    _dono()
    u = Usuario.query.filter_by(id=uid, conta_id=g.conta.id).first_or_404()
    if u.id == g.usuario.id or u.papel == "dono":
        raise ErroAPI("O responsável pela conta não pode ser removido.")
    db.session.delete(u)
    db.session.commit()
    return jsonify({"ok": True})


@bp.get("/auth/convite/<token>")
def ver_convite(token):
    from models import Convite
    c = Convite.query.filter_by(token=token[:60]).first()
    if not c or c.aceito_em or not c.expira_em or c.expira_em < datetime.utcnow():
        raise ErroAPI("Convite inválido ou expirado. Peça um novo convite a quem convidou você.", 404)
    return jsonify({"email": c.email, "conta": Conta.query.get(c.conta_id).nome})


@bp.post("/auth/convite/<token>")
def aceitar_convite(token):
    from models import Convite
    c = Convite.query.filter_by(token=token[:60]).first()
    if not c or c.aceito_em or not c.expira_em or c.expira_em < datetime.utcnow():
        raise ErroAPI("Convite inválido ou expirado. Peça um novo convite a quem convidou você.", 404)
    d = dados()
    nome, senha = (d.get("nome") or "").strip(), d.get("senha") or ""
    if not nome:
        raise ErroAPI("Informe seu nome.")
    if len(senha) < 8:
        raise ErroAPI("A senha precisa ter pelo menos 8 caracteres.")
    if Usuario.query.filter_by(email=c.email).first():
        raise ErroAPI("Este e-mail já tem uma conta no Kasiski. Entre com sua senha.")
    conta = Conta.query.get(c.conta_id)
    ativos, _ = planos.contar_usuarios(conta)
    if ativos >= (planos.dados_plano(conta).get("usuarios") or 1):
        raise ErroAPI("A equipe desta conta já está no limite de usuários do plano. Avise quem convidou você.", 402)
    # Só o link que chegou por e-mail prova o endereço; link copiado por quem convidou pede o código depois.
    u = Usuario(conta_id=c.conta_id, nome=nome[:200], email=c.email, senha_hash=generate_password_hash(senha),
                papel="membro", email_verificado=bool(c.enviado_email), modo_guiado=True)
    db.session.add(u)
    c.aceito_em = datetime.utcnow()
    db.session.commit()
    if not u.verificado and verificacao.exigida():
        return _pedir_verificacao(u, primeiro=True), 201
    return jsonify({"token": gerar_token(u), "usuario": u.to_dict(eh_admin(u))}), 201


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
        u = Usuario.query.filter_by(conta_id=r.conta_id).first()
        d["email"] = u.email if u else None
        saida.append(d)
    return jsonify(saida)


@bp.patch("/admin/revisoes/<int:rid>")
@admin_requerido
def admin_atualizar_revisao(rid):
    r = Revisao.query.get_or_404(rid)
    d = dados()
    if d.get("status") in ("aguardando_pagamento", "pendente", "em_andamento", "concluida", "cancelada"):
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
    if "preco_contratado" in d:
        c.preco_contratado = para_float(d["preco_contratado"]) or None
    if d.get("trial_fim"):
        dt = para_data(d["trial_fim"])
        c.trial_fim = datetime(dt.year, dt.month, dt.day, 23, 59)
    if d.get("estender_trial_dias"):
        base = c.trial_fim if c.trial_fim and c.trial_fim > datetime.utcnow() else datetime.utcnow()
        c.trial_fim = base + timedelta(days=int(d["estender_trial_dias"]))
        c.trial_usado = True
        if planos.codigo(c) not in planos.PAGOS:
            c.plano = "free"
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


@bp.post("/admin/teste-email")
@admin_requerido
def admin_teste_email():
    from services import email
    return jsonify(email.diagnostico((dados().get("para") or g.usuario.email).strip()))


# ---------------------------------------------------------------- dados para a nota fiscal (tomador)
@bp.get("/conta/dados-fiscais")
@login_requerido
def ver_dados_fiscais():
    from services import fiscal
    r = fiscal.publico(g.conta)
    r["posso_editar"] = g.usuario.papel in (None, "dono") or g.admin
    return jsonify(r)


@bp.put("/conta/dados-fiscais")
@login_requerido
def salvar_dados_fiscais():
    from services import fiscal
    if g.usuario.papel not in (None, "dono") and not g.admin:
        raise ErroAPI("Só o responsável pela conta pode alterar os dados da nota fiscal.", 403)
    g.conta.dados_fiscais = fiscal.normalizar(dados())
    db.session.commit()
    return jsonify(fiscal.publico(g.conta))


@bp.get("/conta/dados-fiscais/cep/<cep>")
@login_requerido
def dados_fiscais_cep(cep):
    from services import fiscal
    return jsonify(fiscal.buscar_cep(cep))


@bp.get("/conta/dados-fiscais/cnpj/<cnpj>")
@login_requerido
def dados_fiscais_cnpj(cnpj):
    from services import fiscal
    return jsonify(fiscal.buscar_cnpj(cnpj))
