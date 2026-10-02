"""Extensão do navegador da sala de disputa: vínculo por código e recebimento dos eventos lidos na tela do portal.
A extensão só lê a sala oficial aberta pelo usuário; nenhum lance é enviado ao portal (ver services/extensao.py)."""
from flask import Blueprint, current_app, g, jsonify, request

import planos
from auth import login_requerido
from extensions import db
from routes import dados
from routes.disputa import _disputa
from services import extensao as X

bp = Blueprint("extensao", __name__, url_prefix="/api")


# ---------------------------------------------------------------- lado do Kasiski (usuário logado)
@bp.post("/disputas/<int:did>/extensao/codigo")
@login_requerido
def gerar_codigo(did):
    d = _disputa(did)
    planos.exigir(g.conta, "disputa")
    return jsonify(X.gerar_codigo(d, g.usuario)), 201


@bp.get("/disputas/<int:did>/extensao")
@login_requerido
def estado(did):
    return jsonify(X.estado(_disputa(did)))


@bp.delete("/disputas/<int:did>/extensao")
@login_requerido
def desconectar(did):
    n = X.revogar_da_disputa(_disputa(did))
    db.session.commit()
    return jsonify({"ok": True, "desconectadas": n})


# ---------------------------------------------------------------- lado da extensão (token próprio)
@bp.post("/extensao/vincular")
def vincular():
    from routes.conta import _limite_ip, _registrar_ip
    ip = _limite_ip("extensao_codigo", current_app.config["CODIGOS_IP_HORA"], 60,
                    "Muitas tentativas de código a partir desta rede. Aguarde e tente de novo.")
    _registrar_ip("extensao_codigo", ip)
    return jsonify(X.vincular(dados().get("codigo")))


@bp.get("/extensao/estado")
def estado_extensao():
    v = X.vinculo_do_token(request.headers.get("Authorization"))
    return jsonify(X.resumo_vinculo(v))


@bp.post("/extensao/eventos")
def eventos():
    v = X.vinculo_do_token(request.headers.get("Authorization"))
    return jsonify(X.receber(v, dados().get("eventos")))


@bp.delete("/extensao")
def sair():
    v = X.vinculo_do_token(request.headers.get("Authorization"))
    X.revogar(v)
    db.session.commit()
    return jsonify({"ok": True})
