"""Radar de editais (PNCP), cadastro de editais (PNCP ou upload) e análise com verificação cruzada."""
from flask import Blueprint, g, jsonify, request

import planos
from auth import login_requerido
from extensions import ErroAPI, db
from models import Analise, AnaliseConcorrente, Edital, Peca, Prazo, RadarItem
from routes import dados, edital_da_conta, empresa_da_conta, para_data, para_datahora, para_float
from services import arquivos, fluxos, pncp

bp = Blueprint("editais", __name__, url_prefix="/api")
STATUS = {"acompanhando", "participando", "ganho", "perdido", "descartado"}


# ---------------------------------------------------------------- radar
@bp.get("/empresas/<int:eid>/radar")
@login_requerido
def radar(eid):
    empresa_da_conta(eid)
    status = request.args.get("status", "novo")
    q = RadarItem.query.filter_by(empresa_id=eid)
    if status != "todos":
        q = q.filter_by(status=status)
    itens = q.order_by(RadarItem.nota.desc().nullslast(), RadarItem.criado_em.desc()).limit(200).all()
    return jsonify([i.to_dict() for i in itens])


@bp.post("/empresas/<int:eid>/radar/atualizar")
@login_requerido
def radar_atualizar(eid):
    e = empresa_da_conta(eid)
    if planos.teste_expirado(g.conta):
        raise ErroAPI("Seu teste grátis terminou. Escolha um plano para continuar.", 402)
    novos, respostas = fluxos.atualizar_radar(e)
    planos.registrar_uso(g.conta, "radar", respostas, cobravel=False)
    db.session.commit()
    return jsonify({"novos": novos})


@bp.patch("/radar/<int:rid>")
@login_requerido
def radar_status(rid):
    item = RadarItem.query.get_or_404(rid)
    empresa_da_conta(item.empresa_id)
    if dados().get("status") in ("novo", "descartado"):
        item.status = dados()["status"]
    db.session.commit()
    return jsonify(item.to_dict())


@bp.post("/radar/<int:rid>/acompanhar")
@login_requerido
def radar_acompanhar(rid):
    item = RadarItem.query.get_or_404(rid)
    empresa_da_conta(item.empresa_id)
    ed = _importar_pncp(item.empresa_id, item.numero_controle, item.dados)
    item.status = "acompanhando"
    db.session.commit()
    return jsonify(ed.to_dict()), 201


def _importar_pncp(empresa_id, numero_controle, base=None):
    existente = Edital.query.filter_by(empresa_id=empresa_id, numero_controle=numero_controle).first()
    if existente:
        return existente
    info = dict(base or {})
    try:
        det = pncp.detalhe(numero_controle)
        if det:
            info.update({k: v for k, v in det.items() if v})
    except Exception:
        pass
    if not info.get("objeto"):
        raise ErroAPI("Não encontrei esta contratação no PNCP. Confira o número de controle.", 404)
    texto, nome = pncp.baixar_texto_edital(numero_controle)
    ed = Edital(empresa_id=empresa_id, origem="pncp", numero_controle=numero_controle, numero=info.get("numero"),
                orgao=info.get("orgao"), objeto=info.get("objeto"), modalidade=info.get("modalidade"),
                uf=(info.get("uf") or "")[:2], municipio=info.get("municipio"),
                valor_estimado=info.get("valor_estimado"), data_abertura=pncp._data(info.get("data_abertura")),
                portal_disputa=info.get("portal_disputa"), link=info.get("link"), texto=texto, nome_arquivo=nome)
    db.session.add(ed)
    db.session.flush()
    fluxos.gerar_prazos_edital(ed)
    return ed


# ---------------------------------------------------------------- editais
@bp.get("/empresas/<int:eid>/editais")
@login_requerido
def listar(eid):
    empresa_da_conta(eid)
    q = Edital.query.filter_by(empresa_id=eid)
    if request.args.get("status") in STATUS:
        q = q.filter_by(status=request.args["status"])
    eds = q.order_by(Edital.data_abertura.desc().nullslast(), Edital.criado_em.desc()).all()
    saida = []
    for e in eds:
        d = e.to_dict()
        ult = Analise.query.filter_by(edital_id=e.id).order_by(Analise.id.desc()).first()
        d["decisao"] = ((ult.resultado or {}).get("recomendacao") or {}).get("decisao") if ult else None
        saida.append(d)
    return jsonify(saida)


@bp.post("/empresas/<int:eid>/editais")
@login_requerido
def criar(eid):
    empresa_da_conta(eid)
    d = dados()
    if d.get("numero_controle"):
        ed = _importar_pncp(eid, d["numero_controle"].strip())
        db.session.commit()
        return jsonify(ed.to_dict()), 201
    arq = request.files.get("arquivo")
    if not arq or not arq.filename:
        raise ErroAPI("Envie o PDF do edital ou informe o número de controle do PNCP.")
    caminho, nome = arquivos.salvar(arq, f"editais/{eid}")
    ed = Edital(empresa_id=eid, origem="upload", arquivo=caminho, nome_arquivo=nome,
                objeto=d.get("objeto"), orgao=d.get("orgao"), numero=d.get("numero"),
                portal_disputa=d.get("portal_disputa"), link=d.get("link"),
                valor_estimado=para_float(d.get("valor_estimado")), data_abertura=para_datahora(d.get("data_abertura")))
    ed.texto = arquivos.extrair_texto(caminho)
    db.session.add(ed)
    db.session.flush()
    fluxos.gerar_prazos_edital(ed)
    db.session.commit()
    return jsonify(ed.to_dict()), 201


@bp.get("/editais/<int:edid>")
@login_requerido
def ver(edid):
    ed = edital_da_conta(edid)
    analises = Analise.query.filter_by(edital_id=edid).order_by(Analise.id.desc()).all()
    return jsonify({"edital": ed.to_dict(completo=True), "analises": [a.to_dict() for a in analises],
                    "prazos": [p.to_dict() for p in Prazo.query.filter_by(edital_id=edid).order_by(Prazo.data)],
                    "pecas": [p.to_dict(False) for p in Peca.query.filter_by(edital_id=edid).order_by(Peca.id.desc())],
                    "concorrentes": [a.to_dict() for a in AnaliseConcorrente.query.filter_by(edital_id=edid)
                                     .order_by(AnaliseConcorrente.id.desc())]})


@bp.patch("/editais/<int:edid>")
@login_requerido
def editar(edid):
    ed = edital_da_conta(edid)
    d = dados()
    for campo in ("numero", "orgao", "objeto", "modalidade", "portal_disputa", "link", "municipio", "tipo_objeto", "segmento"):
        if campo in d:
            setattr(ed, campo, d[campo])
    if d.get("status") in STATUS:
        ed.status = d["status"]
    if "valor_estimado" in d:
        ed.valor_estimado = para_float(d["valor_estimado"])
    if "data_abertura" in d:
        ed.data_abertura = para_datahora(d["data_abertura"])
        fluxos.gerar_prazos_edital(ed)
    if "arquivo" in request.files and request.files["arquivo"].filename:
        ed.arquivo, ed.nome_arquivo = arquivos.salvar(request.files["arquivo"], f"editais/{ed.empresa_id}")
        ed.texto = arquivos.extrair_texto(ed.arquivo)
    db.session.commit()
    return jsonify(ed.to_dict())


@bp.delete("/editais/<int:edid>")
@login_requerido
def excluir(edid):
    ed = edital_da_conta(edid)
    Analise.query.filter_by(edital_id=edid).delete()
    AnaliseConcorrente.query.filter_by(edital_id=edid).delete()
    Prazo.query.filter_by(edital_id=edid).delete()
    Peca.query.filter_by(edital_id=edid).update({"edital_id": None})
    db.session.delete(ed)
    db.session.commit()
    return jsonify({"ok": True})


@bp.post("/editais/<int:edid>/analisar")
@login_requerido
def analisar(edid):
    ed = edital_da_conta(edid)
    planos.exigir(g.conta, "analises")
    empresa = empresa_da_conta(ed.empresa_id)
    try:
        analise, respostas = fluxos.analisar_edital(ed, empresa)
    except ErroAPI:
        raise
    except Exception as e:
        db.session.rollback()
        raise ErroAPI(f"Não foi possível concluir a análise agora. Tente novamente em instantes. ({e})", 502)
    planos.registrar_uso(g.conta, "analises", respostas)
    db.session.commit()
    return jsonify(analise.to_dict()), 201


@bp.post("/editais/<int:edid>/resultado")
@login_requerido
def resultado(edid):
    """Registra a intimação do resultado/habilitação e calcula o prazo das razões de recurso."""
    ed = edital_da_conta(edid)
    d = dados()
    data = para_data(d.get("data"))
    if not data:
        raise ErroAPI("Informe a data da intimação ou da ata.")
    ed.resultado_em = data
    if d.get("status") in STATUS:
        ed.status = d["status"]
    fluxos.gerar_prazos_recurso(ed, data)
    db.session.commit()
    return jsonify(ed.to_dict())
