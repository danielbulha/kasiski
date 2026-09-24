"""Registro das rotas e utilidades comuns."""
from datetime import date, datetime

from flask import g, request

from extensions import ErroAPI
from models import Contrato, Edital, Empresa


def registrar(app):
    from routes import conta, empresas, editais, pecas, concorrentes, precos, contratos, agenda
    for m in (conta, empresas, editais, pecas, concorrentes, precos, contratos, agenda):
        app.register_blueprint(m.bp)


def dados():
    """Corpo da requisição, venha como JSON ou como formulário (uploads)."""
    return request.get_json(silent=True) or request.form.to_dict() or {}


def empresa_da_conta(empresa_id):
    try:
        empresa_id = int(empresa_id)
    except (TypeError, ValueError):
        raise ErroAPI("Selecione uma empresa.")
    e = Empresa.query.filter_by(id=empresa_id, conta_id=g.conta.id).first()
    if not e:
        raise ErroAPI("Empresa não encontrada.", 404)
    return e


def edital_da_conta(edital_id):
    ed = Edital.query.get(edital_id)
    if not ed:
        raise ErroAPI("Edital não encontrado.", 404)
    empresa_da_conta(ed.empresa_id)
    return ed


def contrato_da_conta(contrato_id):
    c = Contrato.query.get(contrato_id)
    if not c:
        raise ErroAPI("Contrato não encontrado.", 404)
    empresa_da_conta(c.empresa_id)
    return c


def para_data(v):
    if not v:
        return None
    if isinstance(v, date):
        return v
    try:
        return datetime.strptime(str(v)[:10], "%Y-%m-%d").date()
    except ValueError:
        raise ErroAPI(f"Data inválida: {v}. Use o formato AAAA-MM-DD.")


def para_datahora(v):
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v)[:16])
    except ValueError:
        raise ErroAPI(f"Data e hora inválidas: {v}.")


def para_float(v):
    if v in (None, ""):
        return None
    try:
        return float(str(v).replace(".", "").replace(",", ".")) if isinstance(v, str) and "," in v else float(v)
    except ValueError:
        raise ErroAPI(f"Valor numérico inválido: {v}.")
