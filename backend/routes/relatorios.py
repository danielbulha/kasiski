"""Relatórios para a alta administração (visão geral de todas as empresas da conta ou de uma)."""
from flask import Blueprint, g, jsonify, request

from auth import login_requerido
from models import Empresa
from routes import empresa_da_conta
from services import relatorios

bp = Blueprint("relatorios", __name__, url_prefix="/api")


@bp.get("/relatorios/executivo")
@login_requerido
def executivo():
    alvo = request.args.get("empresa") or "todas"
    if alvo == "todas":
        ids = [e.id for e in Empresa.query.filter_by(conta_id=g.conta.id)]
    else:
        ids = [empresa_da_conta(alvo).id]
    try:
        meses = max(3, min(int(request.args.get("meses") or 12), 24))
    except ValueError:
        meses = 12
    return jsonify(relatorios.executivo(ids, meses))
