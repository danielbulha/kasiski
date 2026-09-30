"""Documentos da licitação (atas, anexos, decisões...), análise de atas com sugestão de peças e o Arquivo."""
from datetime import datetime, timedelta

from flask import Blueprint, current_app, g, jsonify, request, send_file

import planos
from auth import login_requerido
from extensions import ErroAPI, db
from models import DocumentoLicitacao, Edital
from routes import dados, edital_da_conta, empresa_da_conta
from services import arquivos, llm, prompts, tarefas

bp = Blueprint("licitacao", __name__, url_prefix="/api")

TIPOS = {"ata_sessao": "Ata da sessão", "ata_julgamento": "Ata de julgamento / habilitação", "decisao": "Decisão / resultado",
         "recurso": "Recurso ou contrarrazões (de terceiros)", "proposta": "Proposta enviada", "habilitacao": "Documentos de habilitação enviados",
         "anexo": "Anexo do edital", "esclarecimento": "Resposta a esclarecimento / impugnação", "homologacao": "Adjudicação / homologação",
         "contrato": "Contrato / ata de registro de preços", "outro": "Outro"}
ANALISAVEIS = {"ata_sessao", "ata_julgamento", "decisao", "recurso", "homologacao"}


def _doc(did):
    d = DocumentoLicitacao.query.get_or_404(did)
    edital_da_conta(d.edital_id)
    return d


@bp.get("/licitacao/tipos-documento")
@login_requerido
def tipos():
    return jsonify({"tipos": TIPOS, "analisaveis": sorted(ANALISAVEIS)})


@bp.get("/editais/<int:edid>/documentos")
@login_requerido
def listar(edid):
    edital_da_conta(edid)
    return jsonify([d.to_dict() for d in DocumentoLicitacao.query.filter_by(edital_id=edid).order_by(DocumentoLicitacao.criado_em.desc())])


@bp.post("/editais/<int:edid>/documentos")
@login_requerido
def enviar(edid):
    ed = edital_da_conta(edid)
    f = request.files.get("arquivo")
    if not f or not f.filename:
        raise ErroAPI("Escolha o arquivo.")
    d = dados()
    tipo = d.get("tipo") if d.get("tipo") in TIPOS else "outro"
    tamanho = arquivos.tamanho_upload(f)
    caminho, nome = arquivos.salvar(f, f"licitacoes/{ed.empresa_id}")
    doc = DocumentoLicitacao(edital_id=ed.id, empresa_id=ed.empresa_id, tipo=tipo, titulo=(d.get("titulo") or "").strip()[:300] or nome,
                             arquivo=caminho, nome_arquivo=nome, tamanho=tamanho, enviado_por=g.usuario.nome)
    try:
        doc.texto = arquivos.extrair_texto(caminho)
    except Exception:
        doc.texto = None  # imagem, DOC antigo ou PDF escaneado: fica guardado, sem análise
    db.session.add(doc)
    db.session.commit()
    analisar_agora = str(d.get("analisar", "1")) in ("1", "true", "sim") and tipo in ANALISAVEIS and doc.texto
    if analisar_agora:
        try:
            _iniciar_analise(doc)
        except ErroAPI as e:  # sem cota: o documento fica guardado e a análise pode ser pedida depois
            return jsonify({**doc.to_dict(), "aviso": e.mensagem}), 201
    return jsonify(doc.to_dict()), 201


@bp.get("/documentos-licitacao/<int:did>/arquivo")
@login_requerido
def baixar(did):
    d = _doc(did)
    if not d.arquivo:
        raise ErroAPI("Documento sem arquivo.", 404)
    return send_file(arquivos.caminho_absoluto(d.arquivo), download_name=d.nome_arquivo or "documento",
                     as_attachment=request.args.get("baixar") == "1")


@bp.delete("/documentos-licitacao/<int:did>")
@login_requerido
def excluir(did):
    from services import lixeira
    r = lixeira.enviar("doc_licitacao", _doc(did), g.usuario.nome)
    db.session.commit()
    return jsonify(r)


def _iniciar_analise(doc):
    if not doc.texto:
        raise ErroAPI("Não consegui ler o texto deste arquivo. Envie o PDF pesquisável (com texto selecionável) ou DOCX.")
    planos.exigir(g.conta, "concorrentes")  # análise de documento da disputa usa a mesma cota das análises de concorrentes
    doc.analise_status, doc.analise_erro = "processando", None
    db.session.commit()
    tarefas.rodar(_analisar, doc.id, g.conta.id)


@bp.post("/documentos-licitacao/<int:did>/analisar")
@login_requerido
def analisar(did):
    doc = _doc(did)
    if doc.analise_status == "processando":
        return jsonify(doc.to_dict())
    _iniciar_analise(doc)
    return jsonify(doc.to_dict())


def _analisar(did, conta_id):
    from models import Conta, Empresa
    from services import fluxos
    doc = DocumentoLicitacao.query.get(did)
    conta = Conta.query.get(conta_id)
    if not doc:  # foi para a lixeira ou apagado enquanto a análise rodava
        return
    try:
        ed = Edital.query.get(doc.edital_id)
        emp = Empresa.query.get(ed.empresa_id)
        s, u, demo = prompts.analise_ata(arquivos.cortar(doc.texto), {"razao_social": emp.razao_social, "cnpj": emp.cnpj},
                                         {"orgao": ed.orgao, "numero": ed.numero, "objeto": (ed.objeto or "")[:400], "modalidade": ed.modalidade})
        r = llm.chamar("analise", s, u, max_tokens=5000, demo=demo)
        res = llm.extrair_json(r.texto)
        sug = [x for x in (res.get("sugestoes_peca") or []) if x.get("peca") in ("intencao_recurso", "recurso", "contrarrazoes")]
        for i, x in enumerate(sug):
            x["id"] = f"a{i}"
        respostas = [r]
        if sug:  # verificação cruzada: só o que outra IA confirmar no texto vem marcado como confirmado
            mapa, r_ver = fluxos._verificar(doc.texto, [{"id": x["id"], "tema": x.get("tema"), "descricao": x.get("descricao"),
                                                         "fundamento": x.get("fundamento"), "pagina": x.get("pagina")} for x in sug], r.familia)
            for x in sug:
                x["verificacao"] = mapa.get(x["id"], {"confirmado": None, "comentario": "Sem retorno do revisor."})
            if r_ver:
                respostas.append(r_ver)
        res["sugestoes_peca"] = sug
        doc.analise, doc.analise_status = res, "concluida"
        # prazo de recurso na agenda, a partir da data da ata
        data = res.get("data_ata")
        if data and any(x["peca"] in ("recurso", "intencao_recurso") for x in sug):
            try:
                fluxos.gerar_prazos_recurso(ed, datetime.strptime(data[:10], "%Y-%m-%d").date())
            except ValueError:
                pass
        if sug:
            from services import oportunidades
            oportunidades.avancar(ed, "recurso", "Ata analisada: há peça sugerida (recurso ou contrarrazões).")
        planos.registrar_uso(conta, "concorrentes", respostas, cobravel=True)
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Falha na análise da ata %s", did)
        doc = DocumentoLicitacao.query.get(did)
        if not doc:
            return
        doc.analise_status = "erro"
        doc.analise_erro = (e.mensagem if isinstance(e, ErroAPI) else "Não foi possível analisar agora. Tente de novo.")[:300]
    db.session.commit()


# ---------------------------------------------------------------- Arquivo (licitações encerradas)
@bp.get("/empresas/<int:eid>/arquivo")
@login_requerido
def arquivo(eid):
    empresa_da_conta(eid)
    from services import arquivo_licitacao as al
    q = (request.args.get("q") or "").strip().lower()
    eds = Edital.query.filter(Edital.empresa_id == eid, Edital.arquivado_em.isnot(None)).order_by(Edital.arquivado_em.desc()).all()
    saida = []
    for ed in eds:
        if q and q not in " ".join(filter(None, [ed.orgao, ed.objeto, ed.numero, ed.numero_controle])).lower():
            continue
        c = al.conteudo(ed)
        saida.append({**ed.to_dict(), "qtd_documentos": len(c["documentos"]) + (1 if ed.arquivo else 0),
                      "qtd_pecas": len(c["pecas"]), "qtd_propostas": len(c["propostas"]), "contrato": bool(c["contratos"])})
    return jsonify(saida)


@bp.get("/editais/<int:edid>/dossie")
@login_requerido
def dossie(edid):
    from services import arquivo_licitacao as al
    return jsonify(al.resumo(edital_da_conta(edid)))


@bp.get("/editais/<int:edid>/dossie.zip")
@login_requerido
def dossie_zip(edid):
    from services import arquivo_licitacao as al
    ed = edital_da_conta(edid)
    nome = f"licitacao-{(ed.numero or ed.numero_controle or str(ed.id)).replace('/', '-')}.zip"
    return send_file(al.zip_dossie(ed), mimetype="application/zip", as_attachment=True, download_name=nome)


@bp.post("/editais/<int:edid>/arquivar")
@login_requerido
def arquivar(edid):
    ed = edital_da_conta(edid)
    ed.arquivado_em = datetime.utcnow() - timedelta(days=30)  # manual: sai do quadro na hora
    db.session.commit()
    return jsonify(ed.to_dict())


@bp.post("/editais/<int:edid>/reabrir")
@login_requerido
def reabrir(edid):
    ed = edital_da_conta(edid)
    ed.arquivado_em = None
    db.session.commit()
    return jsonify(ed.to_dict())
