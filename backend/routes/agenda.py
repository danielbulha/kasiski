"""Agenda de prazos (automáticos + manuais) e painel consolidado."""
from datetime import date, datetime, timedelta

from flask import Blueprint, g, jsonify, request

from auth import login_requerido
from extensions import ErroAPI, db
from models import Contrato, Documento, Edital, Empresa, Pagamento, Prazo, RadarItem
from routes import dados, empresa_da_conta, para_datahora

bp = Blueprint("agenda", __name__, url_prefix="/api")


def _ids_empresas(eid=None):
    if eid:
        return [empresa_da_conta(eid).id]
    return [e.id for e in Empresa.query.filter_by(conta_id=g.conta.id)]


@bp.get("/agenda")
@login_requerido
def agenda():
    """?empresa_id=  (vazio = todas as empresas da conta: visão do consultor)."""
    ids = _ids_empresas(request.args.get("empresa_id"))
    nomes = {e.id: e.razao_social for e in Empresa.query.filter(Empresa.id.in_(ids))}
    q = Prazo.query.filter(Prazo.empresa_id.in_(ids))
    if request.args.get("pendentes", "1") == "1":
        q = q.filter(Prazo.concluido.is_(False), Prazo.data >= datetime.utcnow() - timedelta(days=7))
    itens = []
    for p in q.order_by(Prazo.data).limit(300):
        d = p.to_dict()
        d["empresa"] = nomes.get(p.empresa_id)
        itens.append(d)
    # documentos do cofre que vencem em 30 dias entram como prazo virtual
    limite = date.today() + timedelta(days=30)
    for doc in Documento.query.filter(Documento.empresa_id.in_(ids), Documento.validade.isnot(None),
                                      Documento.validade <= limite):
        itens.append({"id": f"doc{doc.id}", "titulo": f"Renovar {doc.tipo}", "empresa": nomes.get(doc.empresa_id),
                      "empresa_id": doc.empresa_id, "data": datetime(doc.validade.year, doc.validade.month,
                                                                     doc.validade.day, 23, 59).isoformat(),
                      "tipo": "documento", "fundamento": "Cofre de habilitação", "concluido": False,
                      "automatico": True})
    itens.sort(key=lambda x: x["data"])
    return jsonify(itens)


@bp.post("/agenda")
@login_requerido
def novo():
    d = dados()
    empresa_da_conta(d.get("empresa_id"))
    data = para_datahora(d.get("data"))
    if not (d.get("titulo") or "").strip() or not data:
        raise ErroAPI("Informe título e data do prazo.")
    p = Prazo(empresa_id=int(d["empresa_id"]), titulo=d["titulo"].strip(), data=data, tipo="manual",
              fundamento=d.get("fundamento"), edital_id=d.get("edital_id") or None)
    db.session.add(p)
    db.session.commit()
    return jsonify(p.to_dict()), 201


@bp.patch("/agenda/<int:pid>")
@login_requerido
def editar(pid):
    p = Prazo.query.get_or_404(pid)
    empresa_da_conta(p.empresa_id)
    d = dados()
    if "concluido" in d:
        p.concluido = bool(d["concluido"])
    if "data" in d and not p.automatico:
        p.data = para_datahora(d["data"])
    db.session.commit()
    return jsonify(p.to_dict())


@bp.delete("/agenda/<int:pid>")
@login_requerido
def excluir(pid):
    p = Prazo.query.get_or_404(pid)
    empresa_da_conta(p.empresa_id)
    db.session.delete(p)
    db.session.commit()
    return jsonify({"ok": True})


@bp.get("/painel")
@login_requerido
def painel():
    ids = _ids_empresas(request.args.get("empresa_id"))
    eds = Edital.query.filter(Edital.empresa_id.in_(ids))
    por_status = {s: eds.filter_by(status=s).count() for s in
                  ("acompanhando", "participando", "ganho", "perdido", "descartado")}
    decididos = por_status["ganho"] + por_status["perdido"]
    agora = datetime.utcnow()
    proximos = Prazo.query.filter(Prazo.empresa_id.in_(ids), Prazo.concluido.is_(False), Prazo.data >= agora) \
        .order_by(Prazo.data).limit(6).all()
    docs = Documento.query.filter(Documento.empresa_id.in_(ids), Documento.validade.isnot(None),
                                  Documento.validade <= date.today() + timedelta(days=30)).all()
    ids_ct = [c.id for c in Contrato.query.filter(Contrato.empresa_id.in_(ids))]
    atrasados = [p for p in Pagamento.query.filter(Pagamento.contrato_id.in_(ids_ct), Pagamento.pago_em.is_(None),
                                                   Pagamento.vencimento < date.today())] if ids_ct else []
    return jsonify({
        "editais": por_status,
        "taxa_sucesso": round(por_status["ganho"] / decididos * 100) if decididos else None,
        "radar_novos": RadarItem.query.filter(RadarItem.empresa_id.in_(ids), RadarItem.status == "novo").count(),
        "proximos_prazos": [p.to_dict() for p in proximos],
        "documentos_alerta": [d.to_dict() for d in docs],
        "pagamentos_atrasados": {"quantidade": len(atrasados), "valor": sum(p.valor or 0 for p in atrasados)},
        "contratos_ativos": Contrato.query.filter(Contrato.empresa_id.in_(ids),
                                                  (Contrato.fim.is_(None)) | (Contrato.fim >= date.today())).count(),
    })
