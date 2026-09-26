"""Registro de erros para a área de Logs do admin.

Captura automaticamente todo log de nível ERROR do backend (rotas, tarefas em segundo plano, integrações com
Mercado Pago, Resend, PNCP, IAs...) e os erros enviados pelo navegador. Erros iguais são agrupados
(contador de ocorrências) para a lista não virar ruído. Nunca grava corpo de requisição, senha ou token.
"""
import hashlib
import logging
import random
import re
import traceback
from datetime import datetime, timedelta

from flask import g, has_app_context, has_request_context, request

_local_log = logging.getLogger("kasiski.logs")
_gravando = False  # evita recursão se a própria gravação falhar


def _assinatura(origem, mensagem, rota):
    base = re.sub(r"\d+", "#", f"{origem}|{(mensagem or '').splitlines()[0][:200]}|{rota or ''}")
    return hashlib.sha1(base.encode()).hexdigest()


def _contexto():
    ctx = {"rota": None, "metodo": None, "usuario_email": None, "conta_id": None, "navegador": None}
    if has_request_context():
        ctx.update({"rota": request.path[:300], "metodo": request.method,
                    "navegador": (request.headers.get("User-Agent") or "")[:300]})
        u = getattr(g, "usuario", None)
        if u is not None:
            ctx.update({"usuario_email": u.email, "conta_id": u.conta_id})
    return ctx


def registrar(origem, mensagem, detalhe=None, status=None, nivel="erro", **extra):
    """Grava (ou soma a um erro igual das últimas 24h). Usa conexão própria: funciona mesmo com a sessão
    do SQLAlchemy em estado de erro e não interfere na transação da requisição."""
    global _gravando
    if _gravando or not has_app_context():
        return
    _gravando = True
    try:
        from extensions import db
        from models import LogErro
        ctx = {**_contexto(), **{k: v for k, v in extra.items() if v is not None}}
        mensagem = str(mensagem or "")[:4000]
        ass = _assinatura(origem, mensagem, re.sub(r"\d+", "#", ctx.get("rota") or ""))
        agora = datetime.utcnow()
        t = LogErro.__table__
        with db.engine.begin() as conn:
            existente = conn.execute(t.select().where(t.c.assinatura == ass, t.c.resolvido.is_(False),
                                                      t.c.ultimo_em >= agora - timedelta(hours=24))
                                     .order_by(t.c.id.desc()).limit(1)).first()
            if existente:
                conn.execute(t.update().where(t.c.id == existente.id).values(
                    ocorrencias=(existente.ocorrencias or 1) + 1, ultimo_em=agora,
                    detalhe=(str(detalhe)[:20000] if detalhe else existente.detalhe),
                    usuario_email=ctx.get("usuario_email") or existente.usuario_email))
            else:
                conn.execute(t.insert().values(
                    origem=origem, nivel=nivel, mensagem=mensagem, detalhe=str(detalhe)[:20000] if detalhe else None,
                    rota=ctx.get("rota"), metodo=ctx.get("metodo"), status=status, usuario_email=ctx.get("usuario_email"),
                    conta_id=ctx.get("conta_id"), navegador=ctx.get("navegador"), assinatura=ass, ocorrencias=1,
                    resolvido=False, criado_em=agora, ultimo_em=agora))
            if random.random() < 0.02:  # limpeza ocasional: guarda 90 dias
                conn.execute(t.delete().where(t.c.ultimo_em < agora - timedelta(days=90)))
    except Exception:
        pass  # o log nunca pode derrubar a requisição
    finally:
        _gravando = False


class HandlerBanco(logging.Handler):
    """Envia para a tabela de logs todo registro ERROR do backend."""

    def __init__(self):
        super().__init__(level=logging.ERROR)

    def emit(self, record):
        if record.name.startswith(("kasiski.logs", "sqlalchemy")):
            return
        try:
            mensagem = record.getMessage()
        except Exception:
            mensagem = str(record.msg)
        detalhe = "".join(traceback.format_exception(*record.exc_info)) if record.exc_info else None
        origem = "servidor" if has_request_context() else "tarefa"
        registrar(origem, f"[{record.name}] {mensagem}", detalhe)


def instalar(app):
    h = HandlerBanco()
    raiz = logging.getLogger()
    if not any(isinstance(x, HandlerBanco) for x in raiz.handlers):
        raiz.addHandler(h)
    if not any(isinstance(x, HandlerBanco) for x in app.logger.handlers):
        app.logger.addHandler(h)
        app.logger.propagate = False  # evita gravar duas vezes (app.logger + raiz)
