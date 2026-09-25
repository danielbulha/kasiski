"""Autenticação por token JWT (o frontend no Netlify envia no cabeçalho Authorization)."""
from datetime import datetime, timedelta
from functools import wraps

import jwt
from flask import current_app, g, request

from extensions import ErroAPI, db
from models import Usuario


def gerar_token(usuario):
    payload = {"uid": usuario.id, "exp": datetime.utcnow() + timedelta(hours=current_app.config["TOKEN_HORAS"])}
    return jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm="HS256")


def gerar_token_verificacao(usuario):
    """Token curto que só serve para confirmar o e-mail (não dá acesso ao sistema)."""
    payload = {"uid": usuario.id, "escopo": "verificar", "exp": datetime.utcnow() + timedelta(hours=2)}
    return jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm="HS256")


def usuario_do_token_verificacao(token):
    try:
        dados = jwt.decode(token or "", current_app.config["SECRET_KEY"], algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise ErroAPI("O prazo para confirmar expirou. Entre de novo com seu e-mail e senha.", 401, "verificacao_expirada")
    except jwt.InvalidTokenError:
        raise ErroAPI("Sessão de verificação inválida. Entre de novo com seu e-mail e senha.", 401, "verificacao_expirada")
    if dados.get("escopo") != "verificar":
        raise ErroAPI("Sessão de verificação inválida.", 401)
    u = Usuario.query.get(dados.get("uid"))
    if not u:
        raise ErroAPI("Usuário não encontrado.", 401)
    return u


def eh_admin(usuario):
    return usuario.email.lower() in current_app.config["ADMIN_EMAILS"]


def login_requerido(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        cab = request.headers.get("Authorization", "")
        if not cab.startswith("Bearer "):
            raise ErroAPI("Faça login para continuar.", 401)
        try:
            dados = jwt.decode(cab[7:], current_app.config["SECRET_KEY"], algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            raise ErroAPI("Sua sessão expirou. Entre novamente.", 401)
        except jwt.InvalidTokenError:
            raise ErroAPI("Sessão inválida. Entre novamente.", 401)
        if dados.get("escopo"):  # token de verificação não abre o sistema
            raise ErroAPI("Confirme seu e-mail para continuar.", 401)
        usuario = Usuario.query.get(dados.get("uid"))
        if not usuario:
            raise ErroAPI("Usuário não encontrado.", 401)
        if not usuario.verificado:
            raise ErroAPI("Confirme seu e-mail para continuar.", 401, "email_nao_verificado")
        g.usuario = usuario
        g.conta = usuario.conta
        g.admin = eh_admin(usuario)
        _registrar_acesso(usuario)
        return f(*args, **kwargs)
    return wrapper


def admin_requerido(f):
    @wraps(f)
    @login_requerido
    def wrapper(*args, **kwargs):
        if not g.admin:
            raise ErroAPI("Acesso restrito ao administrador.", 403)
        return f(*args, **kwargs)
    return wrapper


def _registrar_acesso(usuario):
    """Último acesso (para o CRM, gravado no máximo 1x/hora) e suspensão de plano vencido."""
    import planos
    agora = datetime.utcnow()
    if not usuario.ultimo_acesso or agora - usuario.ultimo_acesso > timedelta(hours=1):
        usuario.ultimo_acesso = agora
        db.session.commit()
    planos.verificar_vencimento(usuario.conta)
