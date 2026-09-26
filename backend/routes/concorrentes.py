"""Inteligência de concorrentes: dossiê público por CNPJ e análise de habilitação/proposta."""
from datetime import datetime, timedelta

from flask import Blueprint, current_app, g, jsonify, request, send_file

import planos
from auth import login_requerido
from extensions import ErroAPI, db
from models import AnaliseConcorrente, Concorrente, DocumentoConcorrente
from routes import dados, edital_da_conta, para_data, para_float
from services import arquivos, concorrencia, fluxos, tarefas
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


def _meu(cid):
    c = Concorrente.query.filter_by(id=cid, conta_id=g.conta.id).first()
    if not c:
        raise ErroAPI("Concorrente não encontrado.", 404)
    return c


@bp.get("/concorrentes/<int:cid>")
@login_requerido
def ver(cid):
    c = _meu(cid)
    # tarefa interrompida (reinício do servidor): libera depois de 30 min
    if c.perfil_status == "atualizando" and c.atualizado_em and c.atualizado_em < datetime.utcnow() - timedelta(minutes=30):
        c.perfil_status, c.perfil_etapa, c.perfil_erro = "erro", None, "A atualização foi interrompida. Tente de novo."
        db.session.commit()
    d = c.to_dict()
    d["analises"] = [a.to_dict() for a in AnaliseConcorrente.query.filter_by(concorrente_id=cid)
                     .order_by(AnaliseConcorrente.id.desc())]
    d["documentos"] = [x.to_dict() for x in DocumentoConcorrente.query.filter_by(concorrente_id=cid)
                       .order_by(DocumentoConcorrente.data_documento.desc().nullslast(), DocumentoConcorrente.id.desc())]
    d["tipos_documento"] = concorrencia.TIPOS_DOC
    return jsonify(d)


def _rodar_dossie(cid, conta_id, buscar_pncp, so_consolidar=False):
    from models import Conta
    c, conta = Concorrente.query.get(cid), Conta.query.get(conta_id)
    try:
        if so_consolidar:
            pend = DocumentoConcorrente.query.filter_by(concorrente_id=cid, status="pendente").all()
            respostas = []
            for i, doc in enumerate(pend, start=1):
                c.perfil_etapa = f"Lendo documentos do acervo ({i}/{len(pend)})"
                db.session.commit()
                try:
                    respostas.append(concorrencia.ler_documento(doc, c))
                except Exception:
                    current_app.logger.exception("Falha ao ler documento %s do concorrente %s", doc.id, cid)
                    doc.status = "erro"
                db.session.commit()
            c.perfil_etapa = "Consolidando o dossiê e os pontos de ataque"
            db.session.commit()
            respostas.append(concorrencia.consolidar(c))
        else:
            respostas = concorrencia.atualizar_completo(c, buscar_pncp=buscar_pncp)
        planos.registrar_uso(conta, "dossie", respostas, cobravel=False)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Falha no dossiê completo do concorrente %s", cid)
        c = Concorrente.query.get(cid)
        c.perfil_status, c.perfil_etapa = "erro", None
        c.perfil_erro = e.mensagem if isinstance(e, ErroAPI) else "Não foi possível montar o dossiê agora. Tente de novo em instantes."
        db.session.commit()


@bp.post("/concorrentes/<int:cid>/dossie-completo")
@login_requerido
def dossie_completo(cid):
    """Consulta pública + busca de atas/decisões no PNCP + leitura do acervo + consolidação pela IA.
    Conta como 1 análise de concorrente do plano."""
    c = _meu(cid)
    if c.perfil_status == "atualizando":
        return jsonify(c.to_dict()), 202
    planos.exigir(g.conta, "concorrentes")
    planos.registrar_uso(g.conta, "concorrentes", [], cobravel=True)
    c.perfil_status, c.perfil_etapa, c.perfil_erro, c.atualizado_em = "atualizando", "Na fila", None, datetime.utcnow()
    db.session.commit()
    tarefas.rodar(_rodar_dossie, c.id, g.conta.id, dados().get("buscar_pncp", True) not in (False, "false", 0))
    return jsonify(c.to_dict()), 202


@bp.post("/concorrentes/<int:cid>/documentos")
@login_requerido
def enviar_documento(cid):
    """Acervo: ata, decisão, habilitação, balanço, atestado… de outro certame. A IA lê e o dossiê é reconsolidado."""
    c = _meu(cid)
    planos.exigir(g.conta, "concorrentes")
    d = dados()
    arq = request.files.get("arquivo")
    if not arq or not arq.filename:
        raise ErroAPI("Envie o documento (PDF, DOCX ou TXT).")
    caminho, nome = arquivos.salvar(arq, f"concorrentes/{g.conta.id}/acervo")
    texto = arquivos.extrair_texto(caminho)
    doc = DocumentoConcorrente(concorrente_id=c.id, conta_id=g.conta.id, origem="upload",
                               tipo=d.get("tipo") if d.get("tipo") in concorrencia.TIPOS_DOC else "outro",
                               titulo=(d.get("titulo") or nome)[:300], orgao=(d.get("orgao") or "").strip()[:300] or None,
                               certame=(d.get("certame") or "").strip()[:200] or None, data_documento=para_data(d.get("data_documento")),
                               arquivo=caminho, nome_arquivo=nome, texto=texto, status="pendente")
    db.session.add(doc)
    if c.perfil_status != "atualizando":
        c.perfil_status, c.perfil_etapa, c.perfil_erro, c.atualizado_em = "atualizando", "Na fila", None, datetime.utcnow()
    db.session.commit()
    tarefas.rodar(_rodar_dossie, c.id, g.conta.id, False, True)
    return jsonify(doc.to_dict()), 201


@bp.post("/concorrentes/<int:cid>/reconsolidar")
@login_requerido
def reconsolidar(cid):
    c = _meu(cid)
    if c.perfil_status == "atualizando":
        return jsonify(c.to_dict()), 202
    c.perfil_status, c.perfil_etapa, c.perfil_erro, c.atualizado_em = "atualizando", "Na fila", None, datetime.utcnow()
    db.session.commit()
    tarefas.rodar(_rodar_dossie, c.id, g.conta.id, False, True)
    return jsonify(c.to_dict()), 202


@bp.get("/documentos-concorrente/<int:did>/arquivo")
@login_requerido
def baixar_documento(did):
    doc = DocumentoConcorrente.query.filter_by(id=did, conta_id=g.conta.id).first_or_404()
    if not doc.arquivo:
        raise ErroAPI("Documento sem arquivo.", 404)
    return send_file(arquivos.caminho_absoluto(doc.arquivo), download_name=doc.nome_arquivo or "documento.pdf",
                     as_attachment=not (doc.nome_arquivo or "").lower().endswith(".pdf"), mimetype="application/pdf"
                     if (doc.nome_arquivo or "").lower().endswith(".pdf") else None)


@bp.delete("/documentos-concorrente/<int:did>")
@login_requerido
def excluir_documento(did):
    doc = DocumentoConcorrente.query.filter_by(id=did, conta_id=g.conta.id).first_or_404()
    c = Concorrente.query.get(doc.concorrente_id)
    db.session.delete(doc)
    if c and c.perfil:
        c.perfil_status = "desatualizado"
    db.session.commit()
    return jsonify({"ok": True})


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
