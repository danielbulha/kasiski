"""Gestão de contratos: leitura do PDF pela IA, rotinas de gestão, prazos preventivos e pagamentos."""
from datetime import date, datetime, timedelta

from flask import Blueprint, current_app, g, jsonify, request

import planos
from auth import login_requerido
from extensions import ErroAPI, db
from models import Contrato, Pagamento, Peca, Prazo
from routes import contrato_da_conta, dados, edital_da_conta, empresa_da_conta, para_data, para_float
from services import arquivos, tarefas
from services import contratos as gestao
from services.prazos import fim_do_dia

bp = Blueprint("contratos", __name__, url_prefix="/api")


def _prazos_contrato(c):
    gestao.gerar_prazos(c)


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


def _ler_pdf(cid, conta_id):
    from models import Conta
    c, conta = Contrato.query.get(cid), Conta.query.get(conta_id)
    try:
        respostas = gestao.ler_contrato(c)
        c.leitura_status, c.leitura_erro = "concluida", None
        if not c.orgao:
            c.orgao = "Órgão não identificado"
        if not c.objeto:
            c.objeto = "Objeto não identificado — confira o contrato"
        gestao.gerar_prazos(c)
        planos.registrar_uso(conta, "contratos", respostas, cobravel=False)
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Falha na tarefa _ler_pdf (id %s)", cid)
        c = Contrato.query.get(cid)
        c.leitura_status = "erro"
        c.leitura_erro = (e.mensagem if isinstance(e, ErroAPI) else
                          "Não foi possível ler o contrato agora. Preencha os dados manualmente ou tente de novo.")
        c.orgao = c.orgao or "A preencher"
        c.objeto = c.objeto or "A preencher"
    db.session.commit()


def _anexar_pdf(c):
    f = request.files.get("arquivo")
    if not f or not f.filename:
        return False
    c.arquivo, c.nome_arquivo = arquivos.salvar(f, f"contratos/{c.empresa_id}")
    c.texto = arquivos.extrair_texto(c.arquivo)
    c.leitura_status, c.leitura_erro = "lendo", None
    return True


@bp.post("/empresas/<int:eid>/contratos")
@login_requerido
def criar(eid):
    empresa_da_conta(eid)
    planos.exigir(g.conta, "contratos")
    d = dados()
    c = Contrato(empresa_id=eid)
    if d.get("edital_id"):  # a partir de um edital ganho
        ed = edital_da_conta(int(d["edital_id"]))
        c.edital_id, c.orgao, c.objeto = ed.id, ed.orgao, ed.objeto
        ed.status = "ganho"
    _preencher(c, {k: v for k, v in d.items() if v not in ("", None)})
    com_pdf = _anexar_pdf(c)
    if not com_pdf and not (c.orgao and c.objeto):
        raise ErroAPI("Envie o PDF do contrato ou informe o órgão e o objeto.")
    db.session.add(c)
    db.session.flush()
    if not com_pdf:
        _prazos_contrato(c)
    db.session.commit()
    if com_pdf:
        tarefas.rodar(_ler_pdf, c.id, g.conta.id)
    return jsonify(c.to_dict(True)), 201


@bp.post("/contratos/<int:cid>/arquivo")
@login_requerido
def enviar_arquivo(cid):
    """Envia (ou reenvia) o PDF do contrato e roda a leitura pela IA de novo."""
    c = contrato_da_conta(cid)
    if c.leitura_status == "lendo":
        return jsonify(c.to_dict(True)), 202
    if not _anexar_pdf(c):
        if not c.texto:
            raise ErroAPI("Envie o PDF do contrato.")
        c.leitura_status, c.leitura_erro = "lendo", None
    db.session.commit()
    tarefas.rodar(_ler_pdf, c.id, g.conta.id)
    return jsonify(c.to_dict(True)), 202


@bp.patch("/contratos/<int:cid>/obrigacoes")
@login_requerido
def editar_obrigacoes(cid):
    c = contrato_da_conta(cid)
    lista = (dados().get("obrigacoes") or [])
    if not isinstance(lista, list):
        raise ErroAPI("Lista de rotinas inválida.")
    limpas = []
    for o in lista[:40]:
        if not isinstance(o, dict) or not str(o.get("descricao") or "").strip():
            continue
        per = o.get("periodicidade") if o.get("periodicidade") in (*gestao.PERIODOS, "unica") else "mensal"
        try:
            dia = int(o.get("dia_do_mes")) if o.get("dia_do_mes") not in (None, "") else None
        except (TypeError, ValueError):
            dia = None
        limpas.append({"descricao": str(o["descricao"]).strip()[:300], "periodicidade": per,
                       "dia_do_mes": dia if dia and 1 <= dia <= 31 else None, "prazo": str(o.get("prazo") or "")[:200],
                       "fundamento": str(o.get("fundamento") or "")[:200], "pagina": str(o.get("pagina") or ""),
                       "ativa": o.get("ativa", True) not in (False, "false", 0)})
    c.obrigacoes = limpas
    gestao.gerar_prazos(c)
    db.session.commit()
    return jsonify(c.to_dict(True))


@bp.get("/empresas/<int:eid>/gestao-contratos")
@login_requerido
def painel_gestao(eid):
    """Resumo da carteira: limite do plano, próximos prazos de gestão e pendências."""
    empresa_da_conta(eid)
    hoje = datetime.utcnow()
    ids = [c.id for c in Contrato.query.filter_by(empresa_id=eid)]
    prazos = Prazo.query.filter(Prazo.contrato_id.in_(ids), Prazo.concluido.is_(False),
                                Prazo.data <= hoje + timedelta(days=45)).order_by(Prazo.data).limit(40).all() if ids else []
    return jsonify({"uso": planos.contar_contratos(g.conta), "limite": planos.limite_contratos(g.conta),
                    "prazos": [p.to_dict() for p in prazos], "pacote": planos.PACOTE_CONTRATOS,
                    "plano_permite": bool(planos.PLANOS.get(g.conta.plano, {}).get("contratos"))})


@bp.get("/contratos/<int:cid>")
@login_requerido
def ver(cid):
    c = contrato_da_conta(cid)
    if c.leitura_status == "lendo" and c.criado_em and c.criado_em < datetime.utcnow() - timedelta(minutes=20) \
            and not c.dados_ia:
        c.leitura_status, c.leitura_erro = "erro", "A leitura foi interrompida. Clique em Ler de novo."
        db.session.commit()
    d = c.to_dict(True)
    d["prazos"] = [p.to_dict() for p in Prazo.query.filter_by(contrato_id=cid).order_by(Prazo.concluido, Prazo.data).all()]
    d["pecas"] = [p.to_dict(False) for p in Peca.query.filter_by(contrato_id=cid).order_by(Peca.id.desc())]
    return jsonify(d)


@bp.get("/contratos/<int:cid>/arquivo")
@login_requerido
def baixar_arquivo(cid):
    from flask import send_file
    c = contrato_da_conta(cid)
    if not c.arquivo:
        raise ErroAPI("Este contrato não tem arquivo.", 404)
    return send_file(arquivos.caminho_absoluto(c.arquivo), download_name=c.nome_arquivo, as_attachment=True)


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
