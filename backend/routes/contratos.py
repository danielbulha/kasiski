"""Gestão pós-contrato: vigência, garantia, reajuste e pagamentos, com prazos automáticos na agenda."""
from datetime import date, timedelta

from flask import Blueprint, g, jsonify

import planos
from auth import login_requerido
from extensions import ErroAPI, db
from models import Contrato, Pagamento, Peca, Prazo
from routes import contrato_da_conta, dados, edital_da_conta, empresa_da_conta, para_data, para_float
from services.prazos import fim_do_dia

bp = Blueprint("contratos", __name__, url_prefix="/api")


def _mais_um_ano(d):
    try:
        return d.replace(year=d.year + 1)
    except ValueError:  # 29/02
        return d + timedelta(days=365)


def _prazos_contrato(c):
    Prazo.query.filter_by(contrato_id=c.id, automatico=True).delete(synchronize_session=False)
    base = {"empresa_id": c.empresa_id, "contrato_id": c.id, "automatico": True}
    nome = f"Contrato {c.numero or c.id}"
    novos = []
    if c.fim:
        novos.append(Prazo(titulo=f"{nome}: fim da vigência", data=fim_do_dia(c.fim), tipo="vigencia",
                           fundamento="Avaliar prorrogação com antecedência (Lei 14.133, arts. 106 e 107)", **base))
    if c.garantia_validade:
        novos.append(Prazo(titulo=f"{nome}: vencimento da garantia", data=fim_do_dia(c.garantia_validade),
                           tipo="garantia", fundamento="Renovar a garantia contratual (Lei 14.133, art. 96)", **base))
    if c.data_base_reajuste:
        alvo = _mais_um_ano(c.data_base_reajuste)
        while alvo < date.today():
            alvo = _mais_um_ano(alvo)
        novos.append(Prazo(titulo=f"{nome}: aniversário para reajuste/repactuação", data=fim_do_dia(alvo),
                           tipo="reajuste", fundamento="Anualidade contada da data do orçamento estimado "
                           "(Lei 14.133, art. 25, §7º, e art. 135)", **base))
    db.session.add_all(novos)


def _preencher(c, d):
    for campo in ("numero", "orgao", "objeto", "indice_reajuste", "observacoes"):
        if campo in d:
            setattr(c, campo, d[campo])
    if "valor" in d:
        c.valor = para_float(d["valor"])
    for campo in ("inicio", "fim", "data_base_reajuste", "garantia_validade"):
        if campo in d:
            setattr(c, campo, para_data(d[campo]))


@bp.get("/empresas/<int:eid>/contratos")
@login_requerido
def listar(eid):
    empresa_da_conta(eid)
    saida = []
    for c in Contrato.query.filter_by(empresa_id=eid).order_by(Contrato.fim.desc().nullslast()):
        d = c.to_dict()
        atrasados = [p for p in c.pagamentos if p.situacao() == "atrasado"]
        d["em_atraso"] = sum(p.valor or 0 for p in atrasados)
        d["qtd_atrasados"] = len(atrasados)
        d["recebido"] = sum(p.valor or 0 for p in c.pagamentos if p.pago_em)
        saida.append(d)
    return jsonify(saida)


@bp.post("/empresas/<int:eid>/contratos")
@login_requerido
def criar(eid):
    empresa_da_conta(eid)
    planos.exigir(g.conta, "contratos")
    d = dados()
    c = Contrato(empresa_id=eid)
    if d.get("edital_id"):  # a partir de um edital ganho
        ed = edital_da_conta(d["edital_id"])
        c.edital_id, c.orgao, c.objeto = ed.id, ed.orgao, ed.objeto
        ed.status = "ganho"
    _preencher(c, d)
    if not (c.orgao and c.objeto):
        raise ErroAPI("Informe o órgão e o objeto do contrato.")
    db.session.add(c)
    db.session.flush()
    _prazos_contrato(c)
    db.session.commit()
    return jsonify(c.to_dict(True)), 201


@bp.get("/contratos/<int:cid>")
@login_requerido
def ver(cid):
    c = contrato_da_conta(cid)
    d = c.to_dict(True)
    d["pecas"] = [p.to_dict(False) for p in Peca.query.filter_by(contrato_id=cid).order_by(Peca.id.desc())]
    return jsonify(d)


@bp.patch("/contratos/<int:cid>")
@login_requerido
def editar(cid):
    c = contrato_da_conta(cid)
    _preencher(c, dados())
    _prazos_contrato(c)
    db.session.commit()
    return jsonify(c.to_dict(True))


@bp.delete("/contratos/<int:cid>")
@login_requerido
def excluir(cid):
    c = contrato_da_conta(cid)
    Prazo.query.filter_by(contrato_id=cid).delete()
    Peca.query.filter_by(contrato_id=cid).update({"contrato_id": None})
    db.session.delete(c)
    db.session.commit()
    return jsonify({"ok": True})


@bp.post("/contratos/<int:cid>/pagamentos")
@login_requerido
def novo_pagamento(cid):
    c = contrato_da_conta(cid)
    d = dados()
    p = Pagamento(contrato_id=c.id, referencia=d.get("referencia"), nota_fiscal=d.get("nota_fiscal"),
                  valor=para_float(d.get("valor")), vencimento=para_data(d.get("vencimento")),
                  pago_em=para_data(d.get("pago_em")))
    if not p.vencimento:
        raise ErroAPI("Informe o vencimento do pagamento.")
    db.session.add(p)
    db.session.commit()
    return jsonify(p.to_dict()), 201


@bp.patch("/pagamentos/<int:pid>")
@login_requerido
def editar_pagamento(pid):
    p = Pagamento.query.get_or_404(pid)
    contrato_da_conta(p.contrato_id)
    d = dados()
    for campo in ("referencia", "nota_fiscal"):
        if campo in d:
            setattr(p, campo, d[campo])
    if "valor" in d:
        p.valor = para_float(d["valor"])
    for campo in ("vencimento", "pago_em"):
        if campo in d:
            setattr(p, campo, para_data(d[campo]))
    db.session.commit()
    return jsonify(p.to_dict())


@bp.delete("/pagamentos/<int:pid>")
@login_requerido
def excluir_pagamento(pid):
    p = Pagamento.query.get_or_404(pid)
    contrato_da_conta(p.contrato_id)
    db.session.delete(p)
    db.session.commit()
    return jsonify({"ok": True})
