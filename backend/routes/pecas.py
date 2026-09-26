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


DESCRICAO_SERVICO = {
    "esclarecimento": "Pergunta formal ao órgão sobre ponto obscuro do edital, no prazo legal.",
    "impugnacao": "Pedido de correção de cláusula ilegal ou restritiva do edital antes da sessão.",
    "intencao_recurso": "Manifestação motivada na sessão, que garante o direito de recorrer.",
    "recurso": "Razões recursais contra habilitação, desclassificação ou resultado.",
    "contrarrazoes": "Defesa do resultado contra o recurso de um concorrente.",
    "reequilibrio": "Pedido de recomposição do contrato por fato imprevisível, com memória de cálculo.",
    "cobranca_pagamento": "Requerimento administrativo de pagamento em atraso, com correção e juros.",
    "defesa_previa": "Defesa em processo administrativo sancionador (multa, impedimento, inidoneidade).",
}


@bp.get("/pecas/tipos")
@login_requerido
def tipos():
    precos = current_app.config["PRECO_REVISAO"]
    return jsonify([{"codigo": k, "nome": v, "preco_advogado": precos.get(k), "descricao": DESCRICAO_SERVICO.get(k, "")}
                    for k, v in TIPOS_PECA.items()])


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
                res = ac.resultado or {}
                pontos += [p for p in res.get("apontamentos", []) + res.get("sugestoes", []) + res.get("cruzamentos_historico", [])
                           if p.get("id") in ids]
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
    if edital and tipo in ("intencao_recurso", "recurso", "contrarrazoes"):
        from services import oportunidades
        oportunidades.avancar(edital, "recurso", f"{TIPOS_PECA[tipo]} gerada no Kasiski.", autor=g.usuario.nome)
    planos.registrar_uso(g.conta, "pecas", [r], cobravel=False)
    from services import marketing
    marketing.evento_conta(g.conta, "legal_document_generated", {"tipo": tipo})
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


def _link_pagamento(r, peca):
    """Cria o link de pagamento (Checkout Pro: Pix, boleto ou cartão em até 3x) do serviço de advogado."""
    from services import mercadopago as mp
    tipo = "Elaboração" if r.servico == "elaboracao" else "Revisão"
    _, url = mp.criar_pagamento_avulso(email=g.usuario.email, valor=float(r.valor or 0), anual=False,
                                       titulo=f"{tipo} por advogado — {TIPOS_PECA.get(peca.tipo, 'peça')}"[:250],
                                       referencia=f"r:{r.id}", destino="advogado", parcelas=3)
    return url


def _criar_pedido(peca, servico, d):
    from services import mercadopago as mp
    valor = current_app.config["PRECO_REVISAO"].get(peca.tipo)
    online = mp.configurado() and bool(valor)
    r = Revisao(peca_id=peca.id, conta_id=g.conta.id, servico=servico, valor=valor,
                status="aguardando_pagamento" if online else "pendente",
                prazo_desejado=para_data(d.get("prazo_desejado")), observacoes=(d.get("observacoes") or "").strip() or None)
    db.session.add(r)
    db.session.flush()
    url = None
    if online:
        url = _link_pagamento(r, peca)  # se o Mercado Pago falhar, o ErroAPI desfaz o pedido
    else:
        peca.status = "revisao_solicitada"
    db.session.commit()
    return r, url


@bp.post("/pecas/<int:pid>/revisao")
@login_requerido
def solicitar_revisao(pid):
    p = _peca(pid)
    if Revisao.query.filter(Revisao.peca_id == pid,
                            Revisao.status.in_(["aguardando_pagamento", "pendente", "em_andamento"])).first():
        raise ErroAPI("Já existe um pedido em andamento para esta peça. Veja em Peças > Elaboração com advogado.")
    r, url = _criar_pedido(p, "revisao", dados())
    return jsonify({**r.to_dict(), "url_pagamento": url}), 201


@bp.post("/empresas/<int:eid>/advogado")
@login_requerido
def pedir_elaboracao(eid):
    """Elaboração completa de uma peça por advogado (sem minuta prévia da IA)."""
    empresa = empresa_da_conta(eid)
    d = dados()
    tipo = d.get("tipo")
    if tipo not in TIPOS_PECA:
        raise ErroAPI("Escolha a peça que o advogado deve elaborar.")
    if not (d.get("observacoes") or "").strip():
        raise ErroAPI("Descreva o caso: o que aconteceu e o que a peça deve pedir.")
    edital = edital_da_conta(int(d["edital_id"])) if str(d.get("edital_id") or "").isdigit() else None
    contrato = contrato_da_conta(int(d["contrato_id"])) if str(d.get("contrato_id") or "").isdigit() else None
    ref = (edital.numero or edital.orgao) if edital else (f"Contrato {contrato.numero}" if contrato else empresa.razao_social)
    peca = Peca(empresa_id=eid, edital_id=edital.id if edital else None, contrato_id=contrato.id if contrato else None,
                tipo=tipo, titulo=f"{TIPOS_PECA[tipo]} — {ref or empresa.razao_social}"[:300], status="com_advogado",
                conteudo="")
    db.session.add(peca)
    db.session.flush()
    if edital and tipo in ("intencao_recurso", "recurso", "contrarrazoes"):
        from services import oportunidades
        oportunidades.avancar(edital, "recurso", f"{TIPOS_PECA[tipo]} encomendada ao advogado.", autor=g.usuario.nome)
    r, url = _criar_pedido(peca, "elaboracao", d)
    return jsonify({**r.to_dict(), "url_pagamento": url, "peca_id": peca.id}), 201


def _minha_revisao(rid):
    r = Revisao.query.filter_by(id=rid, conta_id=g.conta.id).first()
    if not r:
        raise ErroAPI("Pedido não encontrado.", 404)
    return r


@bp.post("/revisoes/<int:rid>/pagar")
@login_requerido
def pagar_revisao(rid):
    r = _minha_revisao(rid)
    if r.status != "aguardando_pagamento":
        raise ErroAPI("Este pedido não está aguardando pagamento.")
    return jsonify({"url_pagamento": _link_pagamento(r, Peca.query.get(r.peca_id))})


@bp.delete("/revisoes/<int:rid>")
@login_requerido
def cancelar_revisao(rid):
    r = _minha_revisao(rid)
    if r.status != "aguardando_pagamento":
        raise ErroAPI("Só é possível cancelar pedidos que ainda não foram pagos. Fale com o suporte.")
    peca = Peca.query.get(r.peca_id)
    db.session.delete(r)
    if peca and r.servico == "elaboracao" and not (peca.conteudo or "").strip():
        db.session.delete(peca)
    db.session.commit()
    return jsonify({"ok": True})


@bp.get("/revisoes")
@login_requerido
def minhas_revisoes():
    rs = Revisao.query.filter_by(conta_id=g.conta.id).order_by(Revisao.id.desc()).all()
    return jsonify([r.to_dict() for r in rs])
