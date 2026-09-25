"""Cliente mínimo da API do Mercado Pago (sem SDK — só requests).

Dois fluxos de cobrança:
- recorrente: Assinaturas (/preapproval). O cliente cadastra o cartão uma vez no Mercado Pago e é
  cobrado todo mês (ou todo ano) automaticamente.
- avulso: Checkout Pro (/checkout/preferences). Pagamento único por Pix, boleto ou cartão, que vale
  por um ciclo (1 mês ou 12 meses). O cliente renova pagando de novo.

Documentação: https://www.mercadopago.com.br/developers/pt/reference
"""
import hashlib
import hmac
import uuid

import requests
from flask import current_app

from extensions import ErroAPI

BASE = "https://api.mercadopago.com"


def configurado():
    return bool(current_app.config["MP_ACCESS_TOKEN"])


def _req(metodo, caminho, corpo=None):
    if not configurado():
        raise ErroAPI("Pagamento online ainda não configurado. Fale com o suporte.", 503, "mp_nao_configurado")
    cab = {"Authorization": f"Bearer {current_app.config['MP_ACCESS_TOKEN']}", "Content-Type": "application/json"}
    if metodo in ("POST", "PUT"):
        cab["X-Idempotency-Key"] = str(uuid.uuid4())
    try:
        r = requests.request(metodo, BASE + caminho, json=corpo, headers=cab, timeout=25)
    except requests.RequestException:
        current_app.logger.exception("Mercado Pago indisponível")
        raise ErroAPI("Não foi possível falar com o Mercado Pago agora. Tente de novo em instantes.", 502)
    if r.status_code >= 400:
        current_app.logger.error("Mercado Pago %s %s -> %s %s", metodo, caminho, r.status_code, r.text[:800])
        raise ErroAPI("O Mercado Pago recusou a operação. Tente de novo ou fale com o suporte.", 502, "mp_erro")
    return r.json() if r.content else {}


def _email(email):
    return current_app.config.get("MP_EMAIL_COMPRADOR_TESTE") or email


def _url_retorno():
    return current_app.config["FRONTEND_URL"] + "/?pagamento=retorno"


def _url_webhook():
    base = current_app.config["BACKEND_URL"]
    return base + "/api/billing/webhook" if base else None


# ---------------------------------------------------------------- criação
def criar_assinatura(*, email, valor, anual, titulo, referencia):
    """Assinatura recorrente no cartão. Devolve (id, link para o cliente concluir no Mercado Pago)."""
    corpo = {
        "reason": titulo,
        "external_reference": referencia,
        "payer_email": _email(email),
        "back_url": _url_retorno(),
        "status": "pending",
        "auto_recurring": {"frequency": 12 if anual else 1, "frequency_type": "months",
                           "transaction_amount": valor, "currency_id": "BRL"},
    }
    d = _req("POST", "/preapproval", corpo)
    return d["id"], d["init_point"]


def criar_pagamento_avulso(*, email, valor, anual, titulo, referencia):
    """Checkout Pro (Pix, boleto ou cartão). Devolve (id da preferência, link de pagamento)."""
    corpo = {
        "items": [{"id": referencia, "title": titulo, "quantity": 1, "unit_price": valor, "currency_id": "BRL"}],
        "payer": {"email": _email(email)},
        "external_reference": referencia,
        "back_urls": {k: _url_retorno() for k in ("success", "pending", "failure")},
        "auto_return": "approved",
        "statement_descriptor": "KASISKI",
        "payment_methods": {"installments": 12 if anual else 1},
    }
    if _url_webhook():
        corpo["notification_url"] = _url_webhook()
    d = _req("POST", "/checkout/preferences", corpo)
    return d["id"], d["init_point"]


# ---------------------------------------------------------------- consulta
def pagamento(pid):
    return _req("GET", f"/v1/payments/{pid}")


def assinatura(aid):
    return _req("GET", f"/preapproval/{aid}")


def pagamento_autorizado(aid):
    return _req("GET", f"/authorized_payments/{aid}")


def cancelar_assinatura(aid):
    return _req("PUT", f"/preapproval/{aid}", {"status": "cancelled"})


# ---------------------------------------------------------------- webhook
def assinatura_valida(request, data_id):
    """Confere o cabeçalho x-signature (HMAC-SHA256) enviado pelo Mercado Pago.
    Sem MP_WEBHOOK_SECRET configurado, aceita — o webhook só dispara uma consulta à API do Mercado
    Pago, que é a fonte da verdade, então um aviso forjado não libera plano sozinho."""
    segredo = current_app.config["MP_WEBHOOK_SECRET"]
    if not segredo:
        return True
    partes = dict(p.split("=", 1) for p in (request.headers.get("x-signature") or "").split(",") if "=" in p)
    ts, v1 = partes.get("ts", "").strip(), partes.get("v1", "").strip()
    if not ts or not v1:
        return False
    rid = request.headers.get("x-request-id", "")
    did = str(data_id or "")
    manifesto = f"id:{did.lower() if did.isalnum() else did};request-id:{rid};ts:{ts};"
    esperado = hmac.new(segredo.encode(), manifesto.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperado, v1)
