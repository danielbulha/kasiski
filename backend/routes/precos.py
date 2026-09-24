"""Inteligência de preços: preços praticados no Compras.gov.br + amostras manuais."""
from flask import Blueprint, g, jsonify

import planos
from auth import login_requerido
from extensions import ErroAPI, db
from models import PesquisaPreco
from routes import dados, empresa_da_conta, para_float
from services.dados_publicos import estatisticas, pesquisa_precos

bp = Blueprint("precos", __name__, url_prefix="/api")


@bp.get("/empresas/<int:eid>/precos")
@login_requerido
def listar(eid):
    empresa_da_conta(eid)
    return jsonify([p.to_dict() for p in PesquisaPreco.query.filter_by(empresa_id=eid).order_by(PesquisaPreco.id.desc())])


@bp.post("/empresas/<int:eid>/precos")
@login_requerido
def pesquisar(eid):
    empresa_da_conta(eid)
    planos.exigir(g.conta, "precos")
    d = dados()
    descricao = (d.get("descricao") or "").strip()
    if not descricao:
        raise ErroAPI("Descreva o item pesquisado.")
    codigo = (d.get("codigo_catalogo") or "").strip()
    tipo = d.get("tipo") if d.get("tipo") in ("material", "servico") else "material"
    uf = (d.get("uf") or "").upper()[:2] or None
    amostras = pesquisa_precos(codigo, tipo, uf) if codigo else []
    p = PesquisaPreco(empresa_id=eid, descricao=descricao, codigo_catalogo=codigo or None, tipo=tipo, uf=uf,
                      amostras=amostras, estatisticas=estatisticas([a["preco"] for a in amostras]))
    db.session.add(p)
    db.session.commit()
    return jsonify(p.to_dict()), 201


@bp.post("/precos/<int:pid>/amostras")
@login_requerido
def adicionar_amostra(pid):
    p = PesquisaPreco.query.get_or_404(pid)
    empresa_da_conta(p.empresa_id)
    d = dados()
    preco = para_float(d.get("preco"))
    if not preco or preco <= 0:
        raise ErroAPI("Informe um preço válido.")
    amostras = list(p.amostras or [])
    amostras.append({"preco": preco, "orgao": d.get("orgao"), "uf": d.get("uf"), "data": d.get("data"),
                     "fornecedor": d.get("fornecedor"), "fonte": d.get("fonte") or "Manual"})
    p.amostras = amostras
    p.estatisticas = estatisticas([a["preco"] for a in amostras])
    db.session.commit()
    return jsonify(p.to_dict())


@bp.delete("/precos/<int:pid>")
@login_requerido
def excluir(pid):
    p = PesquisaPreco.query.get_or_404(pid)
    empresa_da_conta(p.empresa_id)
    db.session.delete(p)
    db.session.commit()
    return jsonify({"ok": True})
