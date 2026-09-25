"""Envio de e-mail transacional pelo Resend (https://resend.com/docs/api-reference/emails/send-email)."""
import html

import requests
from flask import current_app

from extensions import ErroAPI


def configurado():
    return bool(current_app.config["RESEND_API_KEY"])


def enviar(para, assunto, texto, html_corpo):
    if not configurado():
        current_app.logger.warning("E-mail não enviado (RESEND_API_KEY vazia) para %s: %s", para, assunto)
        return False
    try:
        r = requests.post("https://api.resend.com/emails", timeout=20, headers={
            "Authorization": f"Bearer {current_app.config['RESEND_API_KEY']}", "Content-Type": "application/json"},
            json={"from": current_app.config["EMAIL_REMETENTE"], "to": [para], "subject": assunto,
                  "text": texto, "html": html_corpo})
    except requests.RequestException:
        current_app.logger.exception("Resend indisponível")
        raise ErroAPI("Não conseguimos enviar o e-mail agora. Tente de novo em instantes.", 502)
    if r.status_code >= 400:
        current_app.logger.error("Resend recusou o envio (%s): %s", r.status_code, r.text[:500])
        raise ErroAPI("Não conseguimos enviar o e-mail agora. Tente de novo em instantes.", 502)
    return True


def enviar_codigo(para, nome, codigo):
    n = html.escape((nome or "").split(" ")[0])
    texto = (f"Olá, {nome}!\n\nSeu código de verificação do Kasiski é: {codigo}\n\n"
             "Ele vale por 15 minutos. Se você não pediu este código, ignore este e-mail.")
    corpo = f"""<div style="font-family:Inter,Segoe UI,Arial,sans-serif;max-width:480px;margin:0 auto;color:#071D2D">
  <p style="font-size:18px;font-weight:800;margin:0 0 20px">Kasiski <span style="font-weight:500;font-size:12px;color:#4F6373;letter-spacing:.08em">PUBLIC MARKET INTELLIGENCE</span></p>
  <p>Olá, {n}!</p><p>Use este código para confirmar seu e-mail e concluir o cadastro:</p>
  <p style="font-size:34px;font-weight:800;letter-spacing:10px;background:#F4F3EF;border-radius:6px;padding:16px;text-align:center;margin:20px 0">{codigo}</p>
  <p style="color:#4F6373;font-size:14px">O código vale por 15 minutos. Se você não pediu este código, ignore este e-mail: ninguém consegue entrar na sua conta sem ele.</p></div>"""
    return enviar(para, f"{codigo} é o seu código de verificação do Kasiski", texto, corpo)
