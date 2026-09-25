"""Código de verificação do e-mail no primeiro acesso."""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

from flask import current_app

from extensions import ErroAPI, db
from models import CodigoVerificacao
from services import email

VALIDADE_MIN = 15
MAX_TENTATIVAS = 5
INTERVALO_REENVIO_S = 60
MAX_ENVIOS_HORA = 5


def exigida():
    modo = current_app.config["VERIFICAR_EMAIL"]
    if modo in ("sim", "true", "1"):
        return True
    if modo in ("nao", "não", "false", "0"):
        return False
    return email.configurado()


def _hash(codigo):
    return hmac.new(current_app.config["SECRET_KEY"].encode(), codigo.encode(), hashlib.sha256).hexdigest()


def enviar_codigo(usuario, forcar=False):
    """Gera e envia um código novo (invalida os anteriores). Respeita intervalo e limite por hora."""
    agora = datetime.utcnow()
    recentes = CodigoVerificacao.query.filter(CodigoVerificacao.usuario_id == usuario.id,
                                              CodigoVerificacao.criado_em >= agora - timedelta(hours=1)) \
        .order_by(CodigoVerificacao.criado_em.desc()).all()
    if recentes and not forcar:
        espera = INTERVALO_REENVIO_S - (agora - recentes[0].criado_em).total_seconds()
        if espera > 0:
            raise ErroAPI(f"Aguarde {int(espera) + 1} segundos para pedir um novo código.", 429, "aguarde")
    if len(recentes) >= MAX_ENVIOS_HORA:
        raise ErroAPI("Muitos códigos pedidos em pouco tempo. Tente de novo daqui a uma hora.", 429, "limite_envios")
    CodigoVerificacao.query.filter_by(usuario_id=usuario.id, usado_em=None).update({"usado_em": agora})
    codigo = f"{secrets.randbelow(10**6):06d}"
    db.session.add(CodigoVerificacao(usuario_id=usuario.id, codigo_hash=_hash(codigo),
                                     expira_em=agora + timedelta(minutes=VALIDADE_MIN)))
    db.session.commit()
    enviado = email.enviar_codigo(usuario.email, usuario.nome, codigo)
    if not enviado:  # modo forçado sem provedor (desenvolvimento): código aparece no log do servidor
        current_app.logger.warning("Código de verificação de %s: %s", usuario.email, codigo)
    return True


def conferir(usuario, codigo):
    codigo = "".join(ch for ch in str(codigo or "") if ch.isdigit())
    c = CodigoVerificacao.query.filter_by(usuario_id=usuario.id, usado_em=None) \
        .order_by(CodigoVerificacao.criado_em.desc()).first()
    if not c or c.expira_em < datetime.utcnow():
        raise ErroAPI("Este código expirou. Peça um novo.", 400, "codigo_expirado")
    if c.tentativas >= MAX_TENTATIVAS:
        raise ErroAPI("Muitas tentativas erradas. Peça um novo código.", 400, "codigo_bloqueado")
    c.tentativas += 1
    if len(codigo) != 6 or not hmac.compare_digest(c.codigo_hash, _hash(codigo)):
        db.session.commit()
        restam = MAX_TENTATIVAS - c.tentativas
        raise ErroAPI(f"Código incorreto. {restam} tentativa(s) restante(s)." if restam else
                      "Código incorreto. Peça um novo código.", 400, "codigo_incorreto")
    c.usado_em = datetime.utcnow()
    usuario.email_verificado = True
    db.session.commit()
