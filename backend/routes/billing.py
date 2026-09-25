"""Cobrança pelo Mercado Pago (checkout, cancelamento, webhook) e eventos públicos do funil."""
import re
from datetime import datetime

from flask import Blueprint, current_app, g, jsonify, request

import planos
from auth import login_requerido
from extensions import ErroAPI, db
from models import Cobranca, Evento
from routes import dados
from services import cobranca as cob
from services import mercadopago as mp

bp = Blueprint("billing", __name__, url_prefix="/api")


@bp.post("/billing/checkout")
@login_requerido
def checkout():
    """Cria o link de pagamento. metodo: 'recorrente' (cartão, renova sozinho) ou 'avulso' (Pix,
    boleto ou cartão, vale um ciclo). ciclo: 'mensal' ou 'anual'."""
    d = dados()
    plano, ciclo, metodo = d.get("plano"), d.get("ciclo") or "mensal", d.get("metodo") or "recorrente"
    if plano not in planos.PAGOS or ciclo not in ("mensal", "anual") or metodo not in ("recorrente", "avulso"):
        raise ErroAPI("Escolha um plano, o ciclo e a forma de pagamento.")
    conta = g.conta
    if metodo == "recorrente" and conta.assinatura_status == "ativa" and conta.metodo_pagamento == "recorrente" \
            and conta.mp_assinatura_id:
        raise ErroAPI("Você já tem uma assinatura automática ativa. Cancele a atual antes de trocar de plano, "
                      "ou fale com o suporte para ajustar.", 409, "assinatura_ativa")
    valor = planos.preco(plano, ciclo)
    titulo = f"Kasiski {planos.PLANOS[plano]['nome']} — {'anual' if ciclo == 'anual' else 'mensal'}"
    ref = cob.referencia(conta, plano, ciclo, metodo)
    if metodo == "recorrente":
        aid, url = mp.criar_assinatura(email=g.usuario.email, valor=valor, anual=ciclo == "anual",
                                       titulo=titulo, referencia=ref)
        conta.mp_assinatura_id = aid
        conta.assinatura_status = "pendente" if conta.assinatura_status != "ativa" else conta.assinatura_status
    else:
        _, url = mp.criar_pagamento_avulso(email=g.usuario.email, valor=valor, anual=ciclo == "anual",
                                           titulo=titulo, referencia=ref)
    db.session.add(Evento(tipo="checkout", conta_id=conta.id, visitante_id=conta.visitante_id,
                          dados={"plano": plano, "ciclo": ciclo, "metodo": metodo, "valor": valor}))
    db.session.commit()
    return jsonify({"url": url, "valor": valor})


@bp.get("/billing/cobrancas")
@login_requerido
def minhas_cobrancas():
    cs = Cobranca.query.filter_by(conta_id=g.conta.id).order_by(Cobranca.criado_em.desc()).limit(50).all()
    return jsonify([c.to_dict() for c in cs])


@bp.post("/billing/cancelar")
@login_requerido
def cancelar():
    conta = g.conta
    if conta.metodo_pagamento != "recorrente" or not conta.mp_assinatura_id:
        raise ErroAPI("Não há assinatura automática para cancelar. Planos pagos por Pix ou boleto "
                      "simplesmente não renovam.")
    mp.cancelar_assinatura(conta.mp_assinatura_id)
    conta.assinatura_status = "cancelada"
    conta.cancelado_em = datetime.utcnow()
    db.session.commit()
    return jsonify({"ok": True, "pago_ate": conta.pago_ate.isoformat() if conta.pago_ate else None})


@bp.post("/billing/sincronizar")
@login_requerido
def sincronizar():
    """Chamado quando o cliente volta do Mercado Pago: confere a assinatura na hora, sem esperar o webhook."""
    conta = g.conta
    if conta.mp_assinatura_id and mp.configurado():
        try:
            cob.processar_assinatura(conta.mp_assinatura_id)
        except ErroAPI:
            pass
    pid = (dados().get("payment_id") or dados().get("collection_id") or "").strip()
    if pid.isdigit() and mp.configurado():
        try:
            cob.processar_pagamento(pid)
        except ErroAPI:
            pass
    return jsonify({"plano": planos.resumo(conta)})


@bp.post("/billing/webhook")
def webhook():
    """Avisos do Mercado Pago. Responde 200 rápido; a fonte da verdade é sempre a consulta à API."""
    corpo = request.get_json(silent=True) or {}
    tipo = corpo.get("type") or corpo.get("topic") or request.args.get("type") or request.args.get("topic")
    data_id = (corpo.get("data") or {}).get("id") or request.args.get("data.id") or request.args.get("id")
    if not data_id:
        return jsonify({"ok": True})
    if not mp.assinatura_valida(request, request.args.get("data.id") or data_id):
        current_app.logger.warning("Webhook do Mercado Pago com assinatura inválida (id=%s)", data_id)
        return jsonify({"erro": "assinatura inválida"}), 401
    try:
        if tipo == "payment":
            cob.processar_pagamento(data_id)
        elif tipo in ("subscription_preapproval", "preapproval"):
            cob.processar_assinatura(data_id)
        elif tipo in ("subscription_authorized_payment", "authorized_payment"):
            cob.processar_pagamento_autorizado(data_id)
    except ErroAPI as e:
        # 5xx faz o Mercado Pago reenviar o aviso mais tarde
        current_app.logger.error("Falha ao processar webhook %s %s: %s", tipo, data_id, e.mensagem)
        db.session.rollback()
        return jsonify({"erro": e.mensagem}), 502
    return jsonify({"ok": True})


# ---------------------------------------------------------------- funil (público, sem login)
TIPOS_PUBLICOS = {"visita", "cta"}


def _limpo(v, n):
    return re.sub(r"[^\w\-. /:]", "", str(v or ""))[:n] or None


@bp.post("/eventos")
def registrar_evento():
    d = request.get_json(silent=True) or {}
    tipo = d.get("tipo")
    if tipo not in TIPOS_PUBLICOS:
        return jsonify({"ok": False}), 400
    vid = _limpo(d.get("visitante"), 40)
    if not vid:
        return jsonify({"ok": False}), 400
    db.session.add(Evento(tipo=tipo, visitante_id=vid, origem=_limpo(d.get("origem"), 80),
                          campanha=_limpo(d.get("campanha"), 120),
                          dados={"pagina": _limpo(d.get("pagina"), 120), "referencia": _limpo(d.get("referencia"), 200)}))
    db.session.commit()
    return jsonify({"ok": True})
