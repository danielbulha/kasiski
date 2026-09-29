"""Lixeira da conta: listar, restaurar e apagar de vez."""
from flask import Blueprint, g, jsonify

from auth import login_requerido
from extensions import db
from services import lixeira

bp = Blueprint("lixeira", __name__, url_prefix="/api")


@bp.get("/lixeira")
@login_requerido
def listar():
    lixeira.purgar(g.conta.id)  # o que passou de 30 dias sai antes de mostrar
    return jsonify({"itens": lixeira.listar(g.conta.id), "dias": lixeira.DIAS})


@bp.post("/lixeira/<tipo>/<int:oid>/restaurar")
@login_requerido
def restaurar(tipo, oid):
    lixeira.restaurar(tipo, lixeira.obter(tipo, oid, g.conta.id))
    db.session.commit()
    return jsonify({"ok": True})


@bp.delete("/lixeira/<tipo>/<int:oid>")
@login_requerido
def apagar(tipo, oid):
    lixeira.apagar(tipo, lixeira.obter(tipo, oid, g.conta.id))
    db.session.commit()
    return jsonify({"ok": True})


@bp.delete("/lixeira")
@login_requerido
def esvaziar():
    n = 0
    for it in lixeira.listar(g.conta.id):
        lixeira.apagar(it["tipo"], lixeira.obter(it["tipo"], it["id"], g.conta.id))
        n += 1
    db.session.commit()
    return jsonify({"apagados": n})
