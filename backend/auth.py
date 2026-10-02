"""Autenticação por token JWT (o frontend no Netlify envia no cabeçalho Authorization)."""
from datetime import datetime, timedelta
from functools import wraps

import jwt
from flask import current_app, g, request

from extensions import ErroAPI, db
from models import Conta, MembroConta, Usuario


def gerar_token(usuario):
    payload = {"uid": usuario.id, "tv": usuario.token_versao or 0,
               "exp": datetime.utcnow() + timedelta(hours=current_app.config["TOKEN_HORAS"])}
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
    """Admin = e-mail da lista ADMIN_EMAILS E endereço confirmado (senão bastaria cadastrar o e-mail do admin)."""
    return usuario.verificado and usuario.email.lower() in current_app.config["ADMIN_EMAILS"]


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
        if (dados.get("tv") or 0) != (usuario.token_versao or 0):  # senha trocada depois do login
            raise ErroAPI("Sua sessão expirou. Entre novamente.", 401)
        from services import verificacao
        if not usuario.verificado and verificacao.exigida():
            raise ErroAPI("Confirme seu e-mail para continuar.", 401, "email_nao_verificado")
        g.usuario = usuario
        g.conta, g.papel = conta_ativa(usuario)
        g.admin = eh_admin(usuario)
        _registrar_acesso(usuario)
        return f(*args, **kwargs)
    return wrapper


def conta_ativa(usuario):
    """Conta em que a pessoa está trabalhando: a própria ou outra cuja equipe ela integra (cabeçalho X-Kasiski-Conta).
    Devolve (conta, papel nela)."""
    pedida = (request.headers.get("X-Kasiski-Conta") or "").strip()
    if pedida.isdigit() and int(pedida) != usuario.conta_id:
        m = MembroConta.query.filter_by(conta_id=int(pedida), usuario_id=usuario.id).first()
        conta = Conta.query.get(m.conta_id) if m else None
        if not conta:
            raise ErroAPI("Você não faz parte desta conta. Voltando para a sua conta.", 403, "conta_sem_acesso")
        return conta, m.papel or "membro"
    return usuario.conta, usuario.papel or "dono"


def tem_acesso(usuario, conta_id):
    """A pessoa ainda pode trabalhar nesta conta (é a dela ou faz parte da equipe)."""
    return usuario.conta_id == conta_id or MembroConta.query.filter_by(conta_id=conta_id, usuario_id=usuario.id).first() is not None


def contas_do_usuario(usuario):
    """Contas a que a pessoa tem acesso, a própria primeiro (para o seletor de conta do aplicativo)."""
    saida = [{"id": usuario.conta_id, "nome": usuario.conta.nome, "papel": usuario.papel or "dono", "propria": True}]
    for m in MembroConta.query.filter_by(usuario_id=usuario.id).order_by(MembroConta.id):
        c = Conta.query.get(m.conta_id)
        if c:
            saida.append({"id": c.id, "nome": c.nome, "papel": m.papel or "membro", "propria": False})
    return saida


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
    planos.verificar_vencimento(g.conta)
