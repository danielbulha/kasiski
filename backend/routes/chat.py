"""Assistente virtual (widget de atendimento) e chamados para a equipe."""
import re
import uuid
from datetime import datetime, timedelta

import jwt
from flask import Blueprint, current_app, jsonify, request

import planos
from auth import admin_requerido
from extensions import ErroAPI, db
from models import ChatConversa, ChatMensagem, Usuario
from routes import dados
from services import atendimento, email

bp = Blueprint("chat", __name__, url_prefix="/api")
LIMITE_MENSAGENS = 60        # por conversa
LIMITE_CARACTERES = 1200


def _usuario_opcional():
    cab = request.headers.get("Authorization", "")
    if not cab.startswith("Bearer "):
        return None
    try:
        d = jwt.decode(cab[7:], current_app.config["SECRET_KEY"], algorithms=["HS256"])
        return None if d.get("escopo") else Usuario.query.get(d.get("uid"))
    except Exception:
        return None


def _contexto(u):
    if not u:
        return None
    r = planos.resumo(u.conta)
    return {"nome": u.nome.split(" ")[0], "plano": r["nome"], "teste_expirado": r["teste_expirado"],
            "trial_fim": r.get("trial_fim"), "uso_mes": r["uso"], "limite_analises": r["analises"],
            "assinatura": r.get("assinatura", {}).get("status")}


def _conversa(cid, u, criar=True):
    c = ChatConversa.query.get(cid) if cid else None
    if c and u and c.conta_id and c.conta_id != u.conta_id:
        c = None  # conversa de outra conta: começa outra
    if not c and criar:
        c = ChatConversa(id=uuid.uuid4().hex, conta_id=u.conta_id if u else None, usuario_email=u.email if u else None)
        db.session.add(c)
    if c and u and not c.conta_id:
        c.conta_id, c.usuario_email = u.conta_id, u.email
    return c


@bp.post("/chat")
def conversar():
    d = request.get_json(silent=True) or {}
    msg = re.sub(r"\s+", " ", str(d.get("message") or "")).strip()
    if not msg:
        raise ErroAPI("Escreva sua pergunta.")
    msg = msg[:LIMITE_CARACTERES]
    u = _usuario_opcional()
    c = _conversa(str(d.get("conversationId") or "")[:40], u)
    c.pagina = str(d.get("pageUrl") or "")[:300] or c.pagina
    c.visitante_id = str(d.get("visitante") or "")[:40] or c.visitante_id
    if (c.n_mensagens or 0) >= LIMITE_MENSAGENS:
        return jsonify({"conversationId": c.id, "resposta": "Esta conversa ficou longa. Para continuar, toque em **Falar com atendimento** "
                        "que nossa equipe segue com você.", "encaminhar": True, "sugestoes": []})
    historico = [m.to_dict() for m in ChatMensagem.query.filter_by(conversa_id=c.id).order_by(ChatMensagem.id.desc()).limit(10)][::-1]
    db.session.add(ChatMensagem(conversa_id=c.id, papel="usuario", texto=msg))
    try:
        r, resp = atendimento.responder(historico, msg, _contexto(u))
    except Exception:
        current_app.logger.exception("Assistente virtual falhou")
        r = atendimento.resposta_por_regras(msg, _contexto(u))
        r = {"resposta": r["resposta"], "encaminhar": bool(r.get("encaminhar_para_humano")), "sugestoes": r.get("sugestoes", [])}
        resp = None
    db.session.add(ChatMensagem(conversa_id=c.id, papel="assistente", texto=r["resposta"]))
    c.n_mensagens = (c.n_mensagens or 0) + 2
    c.atualizado_em = datetime.utcnow()
    if resp is not None and u:
        planos.registrar_uso(u.conta, "chat", [resp], cobravel=False)
    db.session.commit()
    return jsonify({"conversationId": c.id, **r})


@bp.get("/chat/<cid>")
def historico(cid):
    """Retoma a conversa ao reabrir a página (só as mensagens; sem dados de contato)."""
    c = ChatConversa.query.get(cid[:40])
    if not c:
        return jsonify({"mensagens": []})
    u = _usuario_opcional()
    if c.conta_id and (not u or u.conta_id != c.conta_id):
        return jsonify({"mensagens": []})
    ms = ChatMensagem.query.filter_by(conversa_id=c.id).order_by(ChatMensagem.id.desc()).limit(40).all()[::-1]
    return jsonify({"status": c.status, "mensagens": [m.to_dict() for m in ms if m.papel != "sistema"]})


@bp.post("/chat/atendimento")
def pedir_atendimento():
    d = request.get_json(silent=True) or {}
    u = _usuario_opcional()
    c = _conversa(str(d.get("conversationId") or "")[:40], u)
    nome = (d.get("nome") or (u.nome if u else "") or "").strip()[:200]
    mail = (d.get("email") or (u.email if u else "") or "").strip().lower()[:200]
    tel = re.sub(r"[^\d+()\- ]", "", str(d.get("telefone") or ""))[:40]
    assunto = str(d.get("mensagem") or "").strip()[:2000]
    if not nome or not re.match(r"[^@\s]+@[^@\s]+\.[^@\s]+$", mail):
        raise ErroAPI("Informe seu nome e um e-mail válido para a equipe responder.")
    c.nome, c.email, c.telefone = nome, mail, tel or None
    c.assunto = assunto or c.assunto
    c.status, c.encaminhada_em, c.atualizado_em = "encaminhada", datetime.utcnow(), datetime.utcnow()
    c.pagina = str(d.get("pageUrl") or "")[:300] or c.pagina
    db.session.add(ChatMensagem(conversa_id=c.id, papel="sistema", texto=f"Encaminhado para a equipe: {assunto or '(sem mensagem)'}"))
    db.session.commit()
    try:  # aviso por e-mail ao administrador (melhor esforço)
        conversa = "\n".join(f"{m.papel}: {m.texto}" for m in ChatMensagem.query.filter_by(conversa_id=c.id).order_by(ChatMensagem.id))
        for adm in current_app.config["ADMIN_EMAILS"]:
            email.enviar(adm, f"Novo pedido de atendimento: {nome}",
                         f"{nome} <{mail}> {tel}\nPlano/conta: {c.usuario_email or 'visitante'}\n\n{assunto}\n\n--- conversa ---\n{conversa}",
                         f"<p><b>{nome}</b> &lt;{mail}&gt; {tel}</p><p>{assunto}</p><p>Veja em Administração &gt; Atendimento.</p>")
    except Exception:
        current_app.logger.warning("Aviso de atendimento não enviado", exc_info=True)
    return jsonify({"ok": True, "conversationId": c.id,
                    "resposta": f"Pronto, {nome.split(' ')[0]}! Sua conversa foi encaminhada à nossa equipe. Responderemos em {mail}"
                                f"{' ou pelo WhatsApp' if tel else ''} no próximo horário útil."})


# ---------------------------------------------------------------- admin
@bp.get("/admin/atendimentos")
@admin_requerido
def admin_listar():
    status = request.args.get("status", "encaminhada")
    q = ChatConversa.query
    if status == "encaminhada":
        q = q.filter(ChatConversa.status.in_(["encaminhada", "em_atendimento"]))
    elif status in ("resolvida", "bot"):
        q = q.filter(ChatConversa.status == status)
    dias = max(1, min(int(request.args.get("dias", 30)), 180))
    q = q.filter(ChatConversa.atualizado_em >= datetime.utcnow() - timedelta(days=dias))
    itens = q.order_by(ChatConversa.atualizado_em.desc()).limit(200).all()
    abertos = ChatConversa.query.filter(ChatConversa.status.in_(["encaminhada", "em_atendimento"])).count()
    semana = ChatConversa.query.filter(ChatConversa.criado_em >= datetime.utcnow() - timedelta(days=7)).count()
    return jsonify({"conversas": [c.to_dict() for c in itens], "abertos": abertos, "conversas_7d": semana})


@bp.get("/admin/atendimentos/<cid>")
@admin_requerido
def admin_ver(cid):
    c = ChatConversa.query.get_or_404(cid)
    ms = ChatMensagem.query.filter_by(conversa_id=cid).order_by(ChatMensagem.id).all()
    return jsonify({**c.to_dict(), "mensagens": [m.to_dict() for m in ms]})


@bp.patch("/admin/atendimentos/<cid>")
@admin_requerido
def admin_atualizar(cid):
    c = ChatConversa.query.get_or_404(cid)
    d = dados()
    if d.get("status") in ("encaminhada", "em_atendimento", "resolvida", "bot"):
        c.status = d["status"]
    if "notas" in d:
        c.notas = (d["notas"] or "").strip()[:4000] or None
    c.atualizado_em = datetime.utcnow()
    db.session.commit()
    return jsonify(c.to_dict())
