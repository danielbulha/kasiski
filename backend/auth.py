"""Autenticação por token JWT (o frontend no Netlify envia no cabeçalho Authorization)."""
from datetime import datetime, timedelta
from functools import wraps

import jwt
from flask import current_app, g, request

from extensions import ErroAPI
from models import Usuario


def gerar_token(usuario):
    payload = {"uid": usuario.id, "exp": datetime.utcnow() + timedelta(hours=current_app.config["TOKEN_HORAS"])}
    return jwt.encode(payload, current_app.config["SECRET_KEY"], algorithm="HS256")


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
        usuario = Usuario.query.get(dados.get("uid"))
        if not usuario:
            raise ErroAPI("Usuário não encontrado.", 401)
        g.usuario = usuario
        g.conta = usuario.conta
        g.admin = eh_admin(usuario)
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
