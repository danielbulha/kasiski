"""Envio de e-mail transacional pelo Resend (https://resend.com/docs/api-reference/emails/send-email)."""
import html
import re
import unicodedata

import requests
from flask import current_app

from extensions import ErroAPI


_FORMATO = re.compile(r"^(?:[^<>@\"]+ <[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+>|[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+)$")


def remetente():
    """EMAIL_REMETENTE limpo: tira espaços/quebras de linha nas pontas, aspas em volta, espaços
    especiais (NBSP, zero-width) e sinais < > "parecidos" colados de outros apps."""
    v = unicodedata.normalize("NFKC", current_app.config["EMAIL_REMETENTE"] or "")
    v = re.sub(r"[\u200b-\u200d\ufeff]", "", v).replace("\u00a0", " ")
    v = v.replace("‹", "<").replace("›", ">").replace("〈", "<").replace("〉", ">")
    v = v.strip().strip("'\"“”‘’").strip()
    v = re.sub(r"\s+", " ", v)
    v = re.sub(r"\s*<\s*", " <", v).replace(" >", ">").strip()
    m = re.match(r"^(.+?)\s+([^\s<>@]+@[^\s<>@]+)$", v)  # "Nome email@x" sem os sinais < >
    if "<" not in v and m:
        v = f"{m.group(1)} <{m.group(2)}>"
    return v


def remetente_valido():
    return bool(_FORMATO.match(remetente()))


def configurado():
    return bool(current_app.config["RESEND_API_KEY"])


def enviar(para, assunto, texto, html_corpo):
    if not configurado():
        current_app.logger.warning("E-mail não enviado (RESEND_API_KEY vazia) para %s: %s", para, assunto)
        return False
    try:
        r = requests.post("https://api.resend.com/emails", timeout=20, headers={
            "Authorization": f"Bearer {current_app.config['RESEND_API_KEY']}", "Content-Type": "application/json"},
            json={"from": remetente(), "to": [para], "subject": assunto,
                  "text": texto, "html": html_corpo})
    except requests.RequestException as ex:
        current_app.logger.exception("Resend indisponível")
        e = ErroAPI("Não conseguimos enviar o e-mail agora. Tente de novo em instantes.", 502, "email_falhou")
        e.detalhe = f"sem conexão com o Resend: {ex}"
        raise e
    if r.status_code >= 400:
        current_app.logger.error("Resend recusou o envio (%s): %s", r.status_code, r.text[:500])
        e = ErroAPI("Não conseguimos enviar o e-mail agora. Tente de novo em instantes.", 502, "email_falhou")
        e.detalhe = f"Resend respondeu {r.status_code}: {r.text[:500]}"
        raise e
    return True


def diagnostico(para):
    """Envia um e-mail de teste e devolve a resposta crua do Resend (para o painel admin)."""
    cfg = current_app.config
    bruto = cfg["EMAIL_REMETENTE"] or ""
    info = {"remetente": remetente(), "remetente_bruto": repr(bruto), "remetente_valido": remetente_valido(),
            "remetente_limpo_diferente": remetente() != bruto, "chave_configurada": bool(cfg["RESEND_API_KEY"]),
            "chave_inicio": (cfg["RESEND_API_KEY"][:5] + "…") if cfg["RESEND_API_KEY"] else None, "para": para}
    if not cfg["RESEND_API_KEY"]:
        return {**info, "ok": False, "resposta": "RESEND_API_KEY está vazia no servidor."}
    try:
        r = requests.post("https://api.resend.com/emails", timeout=20, headers={
            "Authorization": f"Bearer {cfg['RESEND_API_KEY']}", "Content-Type": "application/json"},
            json={"from": remetente(), "to": [para], "subject": "Teste de envio do Kasiski",
                  "text": "Se você recebeu esta mensagem, o envio de e-mails do Kasiski está funcionando."})
        return {**info, "ok": r.status_code < 400, "status": r.status_code, "resposta": r.text[:800]}
    except requests.RequestException as ex:
        return {**info, "ok": False, "resposta": f"sem conexão com o Resend: {ex}"}


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
