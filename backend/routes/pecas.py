"""Gerador de peças e pedidos de revisão profissional."""
from flask import Blueprint, current_app, g, jsonify, request

import planos
from auth import login_requerido
from extensions import ErroAPI, db
from models import Analise, AnaliseConcorrente, Peca, Revisao
from routes import contrato_da_conta, dados, edital_da_conta, empresa_da_conta, para_data
from services import fluxos
from services.prompts import TIPOS_PECA

bp = Blueprint("pecas", __name__, url_prefix="/api")


@bp.get("/pecas/tipos")
@login_requerido
def tipos():
    precos = current_app.config["PRECO_REVISAO"]
    return jsonify([{"codigo": k, "nome": v, "preco_revisao": precos.get(k)} for k, v in TIPOS_PECA.items()])


@bp.get("/empresas/<int:eid>/pecas")
@login_requerido
def listar(eid):
    empresa_da_conta(eid)
    return jsonify([p.to_dict(False) for p in Peca.query.filter_by(empresa_id=eid).order_by(Peca.id.desc())])


@bp.post("/empresas/<int:eid>/pecas")
@login_requerido
def gerar(eid):
    empresa = empresa_da_conta(eid)
    planos.exigir(g.conta, "pecas")
    d = request.get_json(silent=True) or {}
    tipo = d.get("tipo")
    if tipo not in TIPOS_PECA:
        raise ErroAPI("Escolha o tipo de peça.")
    referencia, pontos, edital, contrato = {}, list(d.get("pontos") or []), None, None
    if d.get("edital_id"):
        edital = edital_da_conta(d["edital_id"])
        referencia = {"orgao": edital.orgao, "numero": edital.numero, "objeto": edital.objeto,
                      "data_sessao": edital.data_abertura.isoformat() if edital.data_abertura else None,
                      "portal": edital.portal_disputa, "tipo_objeto": edital.tipo_objeto, "segmento": edital.segmento}
        # Pontos selecionados na análise do edital ou na análise de concorrente
        if d.get("analise_id"):
            a = Analise.query.filter_by(id=d["analise_id"], edital_id=edital.id).first()
            if a:
                ids = set(d.get("itens") or [])
                pontos += [c for c in (a.resultado or {}).get("clausulas_restritivas", []) if c.get("id") in ids]
        if d.get("analise_concorrente_id"):
            ac = AnaliseConcorrente.query.filter_by(id=d["analise_concorrente_id"], edital_id=edital.id).first()
            if ac:
                ids = set(d.get("itens") or [])
                referencia["recorrido"] = ac.concorrente.to_dict()["razao_social"] if ac.concorrente else None
                pontos += [p for p in (ac.resultado or {}).get("apontamentos", []) if p.get("id") in ids]
    if d.get("contrato_id"):
        contrato = contrato_da_conta(d["contrato_id"])
        referencia.update({"orgao": contrato.orgao, "numero": f"Contrato {contrato.numero}",
                           "objeto": contrato.objeto, "valor": contrato.valor,
                           "pagamentos_em_atraso": [p.to_dict() for p in contrato.pagamentos
                                                    if p.situacao() == "atrasado"]})
    if not pontos and not (d.get("instrucoes") or "").strip():
        raise ErroAPI("Selecione ao menos um ponto ou descreva o que a peça deve sustentar.")
    try:
        texto, r = fluxos.gerar_peca(tipo, empresa, referencia, pontos, d.get("instrucoes"))
    except Exception as e:
        raise ErroAPI(f"Não foi possível gerar a peça agora. Tente novamente. ({e})", 502)
    titulo = f"{TIPOS_PECA[tipo]} — {referencia.get('numero') or referencia.get('orgao') or empresa.razao_social}"
    p = Peca(empresa_id=eid, edital_id=edital.id if edital else None, contrato_id=contrato.id if contrato else None,
             tipo=tipo, titulo=titulo[:300], conteudo=texto, demonstracao=r.demonstracao)
    db.session.add(p)
    planos.registrar_uso(g.conta, "pecas", [r], cobravel=False)
    db.session.commit()
    return jsonify(p.to_dict()), 201


def _peca(pid):
    p = Peca.query.get_or_404(pid)
    empresa_da_conta(p.empresa_id)
    return p


@bp.get("/pecas/<int:pid>")
@login_requerido
def ver(pid):
    p = _peca(pid)
    d = p.to_dict()
    d["revisoes"] = [r.to_dict() for r in Revisao.query.filter_by(peca_id=pid).order_by(Revisao.id.desc())]
    return jsonify(d)


@bp.patch("/pecas/<int:pid>")
@login_requerido
def editar(pid):
    p = _peca(pid)
    d = dados()
    if "conteudo" in d:
        p.conteudo = d["conteudo"]
    if "titulo" in d:
        p.titulo = d["titulo"][:300]
    db.session.commit()
    return jsonify(p.to_dict())


@bp.delete("/pecas/<int:pid>")
@login_requerido
def excluir(pid):
    p = _peca(pid)
    Revisao.query.filter_by(peca_id=pid).delete()
    db.session.delete(p)
    db.session.commit()
    return jsonify({"ok": True})


@bp.post("/pecas/<int:pid>/revisao")
@login_requerido
def solicitar_revisao(pid):
    p = _peca(pid)
    if Revisao.query.filter(Revisao.peca_id == pid, Revisao.status.in_(["pendente", "em_andamento"])).first():
        raise ErroAPI("Já existe uma revisão em andamento para esta peça.")
    d = dados()
    r = Revisao(peca_id=pid, conta_id=g.conta.id, valor=current_app.config["PRECO_REVISAO"].get(p.tipo),
                prazo_desejado=para_data(d.get("prazo_desejado")), observacoes=d.get("observacoes"))
    p.status = "revisao_solicitada"
    db.session.add(r)
    db.session.commit()
    return jsonify(r.to_dict()), 201


@bp.get("/revisoes")
@login_requerido
def minhas_revisoes():
    rs = Revisao.query.filter_by(conta_id=g.conta.id).order_by(Revisao.id.desc()).all()
    return jsonify([r.to_dict() for r in rs])
