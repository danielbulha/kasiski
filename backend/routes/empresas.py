"""Empresas (multi-CNPJ) e cofre de documentos de habilitação."""
import os

from flask import Blueprint, g, jsonify, request, send_file

import planos
from auth import login_requerido
from extensions import ErroAPI, db
from models import Documento, Empresa, TrialCnpj
from routes import dados, empresa_da_conta, para_data, para_float
from services import arquivos
from services.dados_publicos import cnpj_valido, limpar_cnpj, receita

bp = Blueprint("empresas", __name__, url_prefix="/api")

CATEGORIAS = {"juridica", "fiscal", "trabalhista", "economica", "tecnica", "declaracao", "outro"}


@bp.get("/cnpj/<cnpj>")
@login_requerido
def consultar_cnpj(cnpj):
    c = limpar_cnpj(cnpj)
    if not c or not cnpj_valido(c):
        raise ErroAPI("CNPJ inválido.")
    d = receita(c)
    if d.get("status") == "ok":
        from services import cnae
        porte = (d.get("porte") or "").upper()
        d["porte_codigo"] = "ME" if "MICRO" in porte else "EPP" if "PEQUENO" in porte else "demais"
        d["cnaes_texto"] = cnae.texto_cnaes(d.get("cnaes"))
        d["sugestao"] = cnae.sugerir(d.get("cnaes"))
    return jsonify(d)


@bp.get("/empresas")
@login_requerido
def listar():
    return jsonify([e.to_dict() for e in Empresa.query.filter_by(conta_id=g.conta.id).order_by(Empresa.razao_social)])


def _preencher(e, d):
    for campo in ("razao_social", "cnaes", "segmentos", "palavras_chave", "ufs"):
        if campo in d:
            setattr(e, campo, (d[campo] or "").strip())
    if d.get("porte") in ("ME", "EPP", "demais"):
        e.porte = d["porte"]
    if "valor_min" in d:
        e.valor_min = para_float(d["valor_min"])
    if "valor_max" in d:
        e.valor_max = para_float(d["valor_max"])
    e.ufs = ",".join(u.strip().upper()[:2] for u in (e.ufs or "").split(",") if u.strip())


@bp.post("/empresas")
@login_requerido
def criar():
    d = dados()
    planos.exigir(g.conta, "empresas")
    cnpj = limpar_cnpj(d.get("cnpj"))
    if not cnpj or not cnpj_valido(cnpj):
        raise ErroAPI("Informe um CNPJ válido.")
    if Empresa.query.filter_by(conta_id=g.conta.id, cnpj=cnpj).first():
        raise ErroAPI("Esta empresa já está cadastrada na sua conta.")
    if g.conta.plano == "trial":
        usado = TrialCnpj.query.filter_by(cnpj=cnpj).first()
        if usado and usado.conta_id != g.conta.id:
            raise ErroAPI("Este CNPJ já usou o teste grátis. Escolha um plano para cadastrá-lo.", 402)
        if not usado:
            db.session.add(TrialCnpj(cnpj=cnpj, conta_id=g.conta.id))
    if not (d.get("razao_social") or "").strip():
        raise ErroAPI("Informe a razão social.")
    e = Empresa(conta_id=g.conta.id, cnpj=cnpj, razao_social=d["razao_social"].strip())
    _preencher(e, d)
    db.session.add(e)
    db.session.flush()
    from services import marketing, publico
    marketing.evento_conta(g.conta, "company_created", {"empresa_id": e.id})
    if (e.palavras_chave or "").strip():
        marketing.evento_conta(g.conta, "radar_configured", {"empresa_id": e.id})
    publico.importar_analises(g.conta, g.usuario, e)
    db.session.commit()
    return jsonify(e.to_dict()), 201


@bp.patch("/empresas/<int:eid>")
@login_requerido
def editar(eid):
    e = empresa_da_conta(eid)
    antes = (e.palavras_chave or "").strip()
    _preencher(e, dados())
    if not antes and (e.palavras_chave or "").strip():
        from services import marketing
        marketing.evento_conta(g.conta, "radar_configured", {"empresa_id": e.id})
    db.session.commit()
    return jsonify(e.to_dict())


@bp.delete("/empresas/<int:eid>")
@login_requerido
def excluir(eid):
    e = empresa_da_conta(eid)
    from models import (AnaliseConcorrente, Analise, Contrato, Edital, Peca, PesquisaPreco, Prazo, RadarItem,
                        Revisao)
    ids_ed = [x.id for x in Edital.query.filter_by(empresa_id=e.id)]
    ids_pc = [x.id for x in Peca.query.filter_by(empresa_id=e.id)]
    if ids_pc:
        Revisao.query.filter(Revisao.peca_id.in_(ids_pc)).delete(synchronize_session=False)
    if ids_ed:
        Analise.query.filter(Analise.edital_id.in_(ids_ed)).delete(synchronize_session=False)
        AnaliseConcorrente.query.filter(AnaliseConcorrente.edital_id.in_(ids_ed)).delete(synchronize_session=False)
    from models import Proposta
    for M in (Peca, Prazo, RadarItem, PesquisaPreco, Documento, Proposta):
        M.query.filter_by(empresa_id=e.id).delete(synchronize_session=False)
    for c in Contrato.query.filter_by(empresa_id=e.id):
        db.session.delete(c)
    Edital.query.filter_by(empresa_id=e.id).delete(synchronize_session=False)
    db.session.delete(e)
    db.session.commit()
    return jsonify({"ok": True})


# ---------------------------------------------------------------- cofre
@bp.get("/empresas/<int:eid>/documentos")
@login_requerido
def documentos(eid):
    empresa_da_conta(eid)
    docs = Documento.query.filter_by(empresa_id=eid).order_by(Documento.categoria, Documento.tipo).all()
    return jsonify([d.to_dict() for d in docs])


@bp.post("/empresas/<int:eid>/documentos")
@login_requerido
def novo_documento(eid):
    empresa_da_conta(eid)
    d = dados()
    if not (d.get("tipo") or "").strip():
        raise ErroAPI("Informe o tipo do documento (ex.: CND Federal).")
    doc = Documento(empresa_id=eid, tipo=d["tipo"].strip(), descricao=d.get("descricao", ""),
                    categoria=d.get("categoria") if d.get("categoria") in CATEGORIAS else "outro",
                    validade=para_data(d.get("validade")))
    if "arquivo" in request.files and request.files["arquivo"].filename:
        doc.arquivo, doc.nome_arquivo = arquivos.salvar(request.files["arquivo"], f"cofre/{eid}")
    db.session.add(doc)
    from services import marketing
    marketing.evento_conta(g.conta, "document_uploaded", {"tipo": doc.tipo})
    db.session.commit()
    return jsonify(doc.to_dict()), 201


@bp.patch("/documentos/<int:did>")
@login_requerido
def editar_documento(did):
    doc = Documento.query.get_or_404(did)
    empresa_da_conta(doc.empresa_id)
    d = dados()
    for campo in ("tipo", "descricao"):
        if campo in d:
            setattr(doc, campo, d[campo])
    if d.get("categoria") in CATEGORIAS:
        doc.categoria = d["categoria"]
    if "validade" in d:
        doc.validade = para_data(d["validade"])
    if "arquivo" in request.files and request.files["arquivo"].filename:
        doc.arquivo, doc.nome_arquivo = arquivos.salvar(request.files["arquivo"], f"cofre/{doc.empresa_id}")
    db.session.commit()
    return jsonify(doc.to_dict())


@bp.delete("/documentos/<int:did>")
@login_requerido
def excluir_documento(did):
    doc = Documento.query.get_or_404(did)
    empresa_da_conta(doc.empresa_id)
    if doc.arquivo:
        try:
            os.remove(arquivos.caminho_absoluto(doc.arquivo))
        except OSError:
            pass
    db.session.delete(doc)
    db.session.commit()
    return jsonify({"ok": True})


@bp.get("/documentos/<int:did>/arquivo")
@login_requerido
def baixar_documento(did):
    doc = Documento.query.get_or_404(did)
    empresa_da_conta(doc.empresa_id)
    if not doc.arquivo:
        raise ErroAPI("Este documento não tem arquivo anexado.", 404)
    return send_file(arquivos.caminho_absoluto(doc.arquivo), download_name=doc.nome_arquivo, as_attachment=True)
