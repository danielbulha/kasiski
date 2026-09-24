"""Inteligência de concorrentes: dossiê público por CNPJ e análise de habilitação/proposta."""
from datetime import datetime, timedelta

from flask import Blueprint, g, jsonify, request

import planos
from auth import login_requerido
from extensions import ErroAPI, db
from models import AnaliseConcorrente, Concorrente
from routes import dados, edital_da_conta, para_float
from services import arquivos, fluxos
from services.dados_publicos import cnpj_valido, limpar_cnpj

bp = Blueprint("concorrentes", __name__, url_prefix="/api")


@bp.get("/concorrentes")
@login_requerido
def listar():
    cs = Concorrente.query.filter_by(conta_id=g.conta.id).order_by(Concorrente.atualizado_em.desc()).all()
    saida = []
    for c in cs:
        d = c.to_dict()
        d["analises"] = AnaliseConcorrente.query.filter_by(concorrente_id=c.id).count()
        saida.append(d)
    return jsonify(saida)


def _obter_ou_criar(cnpj, forcar=False):
    c = limpar_cnpj(cnpj)
    if not c or not cnpj_valido(c):
        raise ErroAPI("CNPJ do concorrente inválido.")
    conc = Concorrente.query.filter_by(conta_id=g.conta.id, cnpj=c).first()
    recente = conc and conc.atualizado_em and datetime.utcnow() - conc.atualizado_em < timedelta(hours=24)
    if conc and recente and not forcar:
        return conc
    dossie, razao = fluxos.montar_dossie(c)
    if not conc:
        conc = Concorrente(conta_id=g.conta.id, cnpj=c)
        db.session.add(conc)
    conc.dossie, conc.razao_social, conc.atualizado_em = dossie, razao or conc.razao_social, datetime.utcnow()
    db.session.flush()
    return conc


@bp.post("/concorrentes")
@login_requerido
def criar():
    planos.exigir(g.conta, "concorrentes")
    d = dados()
    conc = _obter_ou_criar(d.get("cnpj"), forcar=bool(d.get("atualizar")))
    planos.registrar_uso(g.conta, "dossie", [], cobravel=False)
    db.session.commit()
    return jsonify(conc.to_dict()), 201


@bp.get("/concorrentes/<int:cid>")
@login_requerido
def ver(cid):
    c = Concorrente.query.filter_by(id=cid, conta_id=g.conta.id).first_or_404()
    d = c.to_dict()
    d["analises"] = [a.to_dict() for a in AnaliseConcorrente.query.filter_by(concorrente_id=cid)
                     .order_by(AnaliseConcorrente.id.desc())]
    return jsonify(d)


@bp.post("/editais/<int:edid>/concorrentes")
@login_requerido
def analisar(edid):
    """multipart: cnpj, tipo (habilitacao|proposta), arquivo, valor_proposta (opcional), engenharia (0/1)."""
    ed = edital_da_conta(edid)
    planos.exigir(g.conta, "concorrentes")
    d = dados()
    tipo = d.get("tipo")
    if tipo not in ("habilitacao", "proposta"):
        raise ErroAPI("Escolha se o documento é de habilitação ou proposta.")
    arq = request.files.get("arquivo")
    if not arq or not arq.filename:
        raise ErroAPI("Envie o documento do concorrente baixado do portal da disputa.")
    conc = _obter_ou_criar(d.get("cnpj"))
    caminho, nome = arquivos.salvar(arq, f"concorrentes/{g.conta.id}")
    texto = arquivos.extrair_texto(caminho)
    try:
        ac, respostas = fluxos.analisar_concorrente(ed, conc, tipo, texto, nome, para_float(d.get("valor_proposta")),
                                                    str(d.get("engenharia")) in ("1", "true", "on"))
    except ErroAPI:
        raise
    except Exception as e:
        db.session.rollback()
        raise ErroAPI(f"Não foi possível concluir a análise agora. Tente novamente. ({e})", 502)
    planos.registrar_uso(g.conta, "concorrentes", respostas)
    db.session.commit()
    return jsonify(ac.to_dict()), 201


@bp.delete("/analises-concorrente/<int:aid>")
@login_requerido
def excluir_analise(aid):
    ac = AnaliseConcorrente.query.get_or_404(aid)
    edital_da_conta(ac.edital_id)
    db.session.delete(ac)
    db.session.commit()
    return jsonify({"ok": True})
