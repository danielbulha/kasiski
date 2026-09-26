"""Radar de editais (PNCP), cadastro de editais (PNCP ou upload) e análise com verificação cruzada."""
import threading
from datetime import datetime, timedelta
from flask import Blueprint, current_app, g, jsonify, request

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
    doc = pncp.baixar_edital(numero_controle) or {}
    texto, nome = doc.get("texto"), doc.get("nome")
    caminho = arquivos.salvar_bytes(doc["conteudo"], f"editais/{empresa_id}") if doc.get("conteudo") else None
    ed = Edital(empresa_id=empresa_id, origem="pncp", numero_controle=numero_controle, numero=info.get("numero"),
                arquivo=caminho, arquivo_url=doc.get("url"),
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
        ult = Analise.query.filter_by(edital_id=e.id, status="concluida").order_by(Analise.id.desc()).first()
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
    _expirar_travadas(edid)
    analises = Analise.query.filter_by(edital_id=edid, status="concluida").order_by(Analise.id.desc()).all()
    andamento = Analise.query.filter_by(edital_id=edid).filter(Analise.status != "concluida") \
        .order_by(Analise.id.desc()).first()
    return jsonify({"edital": ed.to_dict(completo=True), "analises": [a.to_dict() for a in analises],
                    "analise_andamento": andamento.to_dict() if andamento and andamento.status == "processando" else None,
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


@bp.get("/editais/<int:edid>/documento")
@login_requerido
def documento(edid):
    """PDF do edital para consulta: o enviado pelo usuário ou o capturado no PNCP (baixado agora se ainda não estiver salvo)."""
    import os
    from flask import send_file
    ed = edital_da_conta(edid)
    if ed.arquivo and not os.path.exists(arquivos.caminho_absoluto(ed.arquivo)):
        ed.arquivo = None  # arquivo sumiu do disco (ex.: disco temporário); tenta o PNCP de novo
    if not ed.arquivo and ed.numero_controle:
        doc = pncp.baixar_edital(ed.numero_controle)
        if doc and doc.get("conteudo"):
            ed.arquivo = arquivos.salvar_bytes(doc["conteudo"], f"editais/{ed.empresa_id}")
            ed.arquivo_url, ed.nome_arquivo = doc.get("url"), ed.nome_arquivo or doc.get("nome")
            if not ed.texto:
                ed.texto = doc.get("texto")
            db.session.commit()
    if not ed.arquivo:
        raise ErroAPI("O documento deste edital não está disponível. Envie o PDF pela opção Editar ou consulte no PNCP.", 404)
    nome = ed.nome_arquivo or "edital.pdf"
    ext = os.path.splitext(ed.arquivo)[1].lower()
    tipos = {".pdf": "application/pdf", ".txt": "text/plain; charset=utf-8",
             ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".doc": "application/msword"}
    return send_file(arquivos.caminho_absoluto(ed.arquivo), mimetype=tipos.get(ext, "application/octet-stream"),
                     as_attachment=ext not in (".pdf", ".txt"), download_name=nome)


@bp.delete("/editais/<int:edid>")
@login_requerido
def excluir(edid):
    ed = edital_da_conta(edid)
    Analise.query.filter_by(edital_id=edid).delete()
    AnaliseConcorrente.query.filter_by(edital_id=edid).delete()
    Prazo.query.filter_by(edital_id=edid).delete()
    Peca.query.filter_by(edital_id=edid).update({"edital_id": None})
    from models import Proposta
    Proposta.query.filter_by(edital_id=edid).update({"edital_id": None})
    db.session.delete(ed)
    db.session.commit()
    return jsonify({"ok": True})


ANALISE_LIMITE_MIN = 20  # sem conclusão depois disso, a análise é dada como perdida (ex.: servidor reiniciou)


def _expirar_travadas(edid):
    limite = datetime.utcnow() - timedelta(minutes=ANALISE_LIMITE_MIN)
    for a in Analise.query.filter(Analise.edital_id == edid, Analise.status == "processando",
                                  Analise.criado_em < limite).all():
        a.status, a.etapa = "erro", None
        a.erro = "A análise foi interrompida (o servidor reiniciou ou demorou demais). Nada foi descontado; tente de novo."
    db.session.commit()


def _rodar_analise(app, analise_id, edital_id, empresa_id, conta_id):
    """Executa em segundo plano: a análise de um edital grande leva vários minutos e passaria do
    tempo máximo de uma requisição web."""
    with app.app_context():
        from models import Conta, Empresa
        analise = Analise.query.get(analise_id)
        ed, empresa, conta = Edital.query.get(edital_id), Empresa.query.get(empresa_id), Conta.query.get(conta_id)
        try:
            _, respostas = fluxos.analisar_edital(ed, empresa, analise)
            planos.registrar_uso(conta, "analises", respostas)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            app.logger.exception("Falha na análise %s", analise_id)
            analise = Analise.query.get(analise_id)
            analise.status, analise.etapa = "erro", None
            msg = e.mensagem if isinstance(e, ErroAPI) else "Não foi possível concluir a análise agora. Tente novamente em instantes."
            if not isinstance(e, ErroAPI) and "Nenhuma IA respondeu" in str(e):
                msg = "Os serviços de IA não responderam. Tente novamente em alguns minutos."
            analise.erro = msg
            db.session.commit()
        finally:
            db.session.remove()


@bp.post("/editais/<int:edid>/analisar")
@login_requerido
def analisar(edid):
    ed = edital_da_conta(edid)
    if not ed.texto:
        raise ErroAPI("Este edital ainda não tem texto. Envie o PDF do edital para analisar.")
    _expirar_travadas(edid)
    andamento = Analise.query.filter_by(edital_id=edid, status="processando").first()
    if andamento:  # clique duplo ou outra aba: acompanha a que já está rodando
        return jsonify(andamento.to_dict()), 202
    planos.exigir(g.conta, "analises")
    empresa = empresa_da_conta(ed.empresa_id)
    analise = Analise(edital_id=edid, status="processando", etapa="Na fila")
    db.session.add(analise)
    db.session.commit()
    threading.Thread(target=_rodar_analise, daemon=True,
                     args=(current_app._get_current_object(), analise.id, ed.id, empresa.id, g.conta.id)).start()
    return jsonify(analise.to_dict()), 202


@bp.get("/editais/<int:edid>/analises/<int:aid>")
@login_requerido
def ver_analise(edid, aid):
    edital_da_conta(edid)
    _expirar_travadas(edid)
    a = Analise.query.filter_by(id=aid, edital_id=edid).first()
    if not a:
        raise ErroAPI("Análise não encontrada.", 404)
    return jsonify(a.to_dict())


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
