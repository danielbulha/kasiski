"""Kanban de oportunidades (ciclo comercial do edital) e dossiê do cartão."""
from datetime import datetime, timedelta

from flask import Blueprint, g, jsonify, request

from auth import login_requerido
from extensions import ErroAPI, db
from models import (Analise, AnaliseConcorrente, Contrato, Edital, Empresa, Movimento, Peca, Prazo, Proposta,
                    RadarItem, Usuario)
from routes import dados, edital_da_conta, empresa_da_conta
from services import oportunidades as op
from services import pncp, tarefas

bp = Blueprint("oportunidades", __name__, url_prefix="/api")


def _autor():
    return g.usuario.nome if getattr(g, "usuario", None) else None


def _ultimas_analises(ids):
    """{edital_id: última análise concluída} numa consulta só."""
    if not ids:
        return {}
    saida = {}
    for a in Analise.query.filter(Analise.edital_id.in_(ids), Analise.status == "concluida").order_by(Analise.id):
        saida[a.edital_id] = a
    return saida


@bp.get("/empresas/<int:eid>/oportunidades")
@login_requerido
def quadro(eid):
    emp = empresa_da_conta(eid)
    eds = Edital.query.filter_by(empresa_id=eid).order_by(Edital.data_abertura.asc().nullslast(), Edital.id.desc()).all()
    mudou = False
    for ed in eds:  # eventos que não dependem do PNCP (data da sessão) andam na hora
        if ed.etapa is None:
            ed.etapa = op.etapa_de(ed)
            mudou = True
        mudou = op.avancar_por_data(ed) or mudou
    if mudou:
        db.session.commit()
    analises = _ultimas_analises([e.id for e in eds])
    notas = {r.numero_controle: r.nota for r in RadarItem.query.filter_by(empresa_id=eid) if r.numero_controle}
    cartoes = [op.cartao(ed, analises.get(ed.id), notas.get(ed.numero_controle)) for ed in eds]
    usuarios = [{"id": u.id, "nome": u.nome} for u in Usuario.query.filter_by(conta_id=g.conta.id).order_by(Usuario.nome)]
    return jsonify({
        "etapas": [{"codigo": k, "nome": n, "descricao": d} for k, n, d in op.ETAPAS],
        "saidas": [{"codigo": k, "nome": n, "descricao": d} for k, n, d in op.SAIDAS],
        "cartoes": cartoes, "usuarios": usuarios,
        "radar_novos": RadarItem.query.filter_by(empresa_id=eid, status="novo").count(),
        "sincronizacao": emp.oportunidades_sync,
    })


@bp.get("/oportunidades/<int:edid>")
@login_requerido
def dossie(edid):
    ed = edital_da_conta(edid)
    analises = Analise.query.filter_by(edital_id=edid, status="concluida").order_by(Analise.id.desc()).all()
    ultima = analises[0] if analises else None
    nota = None
    if ed.numero_controle:
        ri = RadarItem.query.filter_by(empresa_id=ed.empresa_id, numero_controle=ed.numero_controle).first()
        nota = ri.nota if ri else None
    r = (ultima.resultado or {}) if ultima else {}
    checklist = (r.get("checklist") or []) + (r.get("checklist_setorial") or [])
    contagem = {}
    for c in checklist:
        contagem[c.get("status") or "verificar"] = contagem.get(c.get("status") or "verificar", 0) + 1
    pecas = Peca.query.filter_by(edital_id=edid).order_by(Peca.id.desc()).all()
    usuarios = [{"id": u.id, "nome": u.nome} for u in Usuario.query.filter_by(conta_id=g.conta.id).order_by(Usuario.nome)]
    return jsonify({
        "cartao": op.cartao(ed, ultima, nota),
        "edital": ed.to_dict(completo=True),
        "orgao_cnpj": ed.numero_controle[:14] if ed.numero_controle and ed.numero_controle[:14].isdigit() else None,
        "analise": {"id": ultima.id, "data": ultima.concluido_em.isoformat() if ultima.concluido_em else None,
                    "resumo": r.get("resumo"), "recomendacao": r.get("recomendacao"), "checklist": contagem,
                    "clausulas": len(r.get("clausulas_restritivas") or []), "riscos": r.get("riscos") or [],
                    "exigencias_tecnicas": (r.get("extracao") or {}).get("exigencias_tecnicas_objeto") or [],
                    "garantia_contrato": (r.get("extracao") or {}).get("garantia_contrato"),
                    "criterio_julgamento": (r.get("extracao") or {}).get("criterio_julgamento"),
                    "prazo_execucao": (r.get("extracao") or {}).get("prazo_execucao")} if ultima else None,
        "prazos": [p.to_dict() for p in Prazo.query.filter_by(edital_id=edid).order_by(Prazo.data)],
        "pecas": [p.to_dict(False) for p in pecas],
        "propostas": [{"id": p.id, "titulo": p.titulo, "criado_em": p.criado_em.isoformat() if getattr(p, "criado_em", None) else None}
                      for p in Proposta.query.filter_by(edital_id=edid).order_by(Proposta.id.desc())],
        "concorrentes_analisados": [a.to_dict() for a in AnaliseConcorrente.query.filter_by(edital_id=edid).order_by(AnaliseConcorrente.id.desc())],
        "contratos": [{"id": c.id, "numero": c.numero, "valor": c.valor} for c in Contrato.query.filter_by(edital_id=edid)],
        "movimentos": [m.to_dict() for m in Movimento.query.filter_by(edital_id=edid).order_by(Movimento.id.desc()).limit(100)],
        "usuarios": usuarios,
    })


@bp.patch("/oportunidades/<int:edid>")
@login_requerido
def atualizar(edid):
    """Move o cartão e/ou define o responsável. {etapa, motivo, responsavel_id, responsavel}"""
    ed = edital_da_conta(edid)
    d = dados()
    if "responsavel_id" in d or "responsavel" in d:
        uid = d.get("responsavel_id")
        u = Usuario.query.filter_by(id=uid, conta_id=g.conta.id).first() if uid else None
        nome = (u.nome if u else (d.get("responsavel") or "").strip())[:120] or None
        if nome != ed.responsavel:
            db.session.add(Movimento(edital_id=ed.id, de=op.etapa_de(ed), para=op.etapa_de(ed), origem="usuario",
                                     autor=_autor(), motivo=f"Responsável: {nome or 'ninguém'}"))
        ed.responsavel, ed.responsavel_id = nome, (u.id if u else None)
    if d.get("etapa"):
        if d["etapa"] not in op.VALIDAS:
            raise ErroAPI("Etapa inválida.")
        if d["etapa"] in ("perdida", "desistencia") and not (d.get("motivo") or "").strip():
            raise ErroAPI("Conte rapidamente o motivo (fica no histórico e ajuda nas próximas decisões).")
        op.mover(ed, d["etapa"], "usuario", _autor(), (d.get("motivo") or "").strip() or None)
        if d["etapa"] == "desistencia" and ed.decisao is None and op.ORDEM.get(op.etapa_de(ed), 0) <= op.ORDEM["decisao"]:
            ed.decisao = "no_go"
    db.session.commit()
    return jsonify(op.cartao(ed, Analise.query.filter_by(edital_id=edid, status="concluida").order_by(Analise.id.desc()).first()))


@bp.post("/oportunidades/<int:edid>/decisao")
@login_requerido
def decidir(edid):
    """Go → Preparação. No-Go → Desistência (com motivo)."""
    ed = edital_da_conta(edid)
    d = dados()
    decisao = d.get("decisao")
    motivo = (d.get("motivo") or "").strip()
    if decisao not in ("go", "no_go"):
        raise ErroAPI("Escolha Go ou No-Go.")
    if decisao == "no_go" and not motivo:
        raise ErroAPI("Informe o motivo do No-Go (fica no histórico).")
    ed.decisao, ed.decisao_motivo = decisao, motivo or None
    if decisao == "go":
        op.mover(ed, "preparacao", "usuario", _autor(), "Decisão: Go" + (f" — {motivo}" if motivo else ""))
    else:
        op.mover(ed, "desistencia", "usuario", _autor(), f"Decisão: No-Go — {motivo}")
    db.session.commit()
    return jsonify(op.cartao(ed, Analise.query.filter_by(edital_id=edid, status="concluida").order_by(Analise.id.desc()).first()))


@bp.get("/oportunidades/<int:edid>/itens")
@login_requerido
def itens(edid):
    ed = edital_da_conta(edid)
    if not ed.numero_controle:
        return jsonify({"itens": [], "aviso": "Edital enviado por upload: os itens estão no documento."})
    try:
        return jsonify({"itens": pncp.itens_da_compra(ed.numero_controle)})
    except Exception:
        return jsonify({"itens": [], "aviso": "O PNCP não respondeu agora. Tente de novo em instantes."})


@bp.get("/oportunidades/<int:edid>/historico-orgao")
@login_requerido
def historico_orgao(edid):
    ed = edital_da_conta(edid)
    cnpj = ed.numero_controle[:14] if ed.numero_controle and ed.numero_controle[:14].isdigit() else None
    if not cnpj:
        return jsonify({"contratos": [], "aviso": "Sem o número de controle do PNCP não dá para identificar o órgão."})
    try:
        contratos = pncp.contratos_do_orgao(cnpj)
    except Exception:
        return jsonify({"contratos": [], "aviso": "O PNCP não respondeu agora. Tente de novo em instantes."})
    # outras oportunidades da conta no mesmo órgão (ganhas e perdidas)
    ids = [e.id for e in Empresa.query.filter_by(conta_id=g.conta.id)]
    nossas = Edital.query.filter(Edital.empresa_id.in_(ids), Edital.numero_controle.like(f"{cnpj}-%"), Edital.id != ed.id).all()
    return jsonify({"contratos": contratos,
                    "nossas": [{"id": e.id, "numero": e.numero, "objeto": e.objeto, "etapa": op.etapa_de(e)} for e in nossas]})


@bp.post("/oportunidades/<int:edid>/sincronizar")
@login_requerido
def sincronizar_um(edid):
    ed = edital_da_conta(edid)
    emp = Empresa.query.get(ed.empresa_id)
    feitos = op.sincronizar(ed, emp)
    db.session.commit()
    return jsonify({"movimentos": feitos, "cartao": op.cartao(ed, Analise.query.filter_by(edital_id=edid, status="concluida").order_by(Analise.id.desc()).first())})


def _sincronizar_empresa(eid):
    emp = Empresa.query.get(eid)
    try:
        movidos = op.sincronizar_empresa(emp)
        emp.oportunidades_sync = {"status": "concluida", "iniciado_em": (emp.oportunidades_sync or {}).get("iniciado_em"),
                                  "concluido_em": datetime.utcnow().isoformat(), "movidos": movidos}
    except Exception:
        emp.oportunidades_sync = {"status": "erro", "concluido_em": datetime.utcnow().isoformat(),
                                  "erro": "Não foi possível consultar o PNCP agora."}
    db.session.commit()


@bp.post("/empresas/<int:eid>/oportunidades/sincronizar")
@login_requerido
def sincronizar_todas(eid):
    emp = empresa_da_conta(eid)
    atual = emp.oportunidades_sync or {}
    if atual.get("status") == "sincronizando" and atual.get("iniciado_em") and \
            datetime.fromisoformat(atual["iniciado_em"]) > datetime.utcnow() - timedelta(minutes=15):
        return jsonify(atual), 202
    emp.oportunidades_sync = {"status": "sincronizando", "iniciado_em": datetime.utcnow().isoformat()}
    db.session.commit()
    tarefas.rodar(_sincronizar_empresa, emp.id)
    return jsonify(emp.oportunidades_sync), 202


@bp.get("/empresas/<int:eid>/oportunidades/resumo")
@login_requerido
def resumo(eid):
    """Resumo do pipeline para o Painel: quantidade e valor por etapa."""
    empresa_da_conta(eid)
    por = {k: {"quantidade": 0, "valor": 0.0} for k in op.VALIDAS}
    for ed in Edital.query.filter_by(empresa_id=eid):
        e = op.etapa_de(ed)
        por[e]["quantidade"] += 1
        por[e]["valor"] += ed.valor_estimado or 0
    return jsonify({"etapas": [{"codigo": k, "nome": n, **por[k]} for k, n, _ in op.ETAPAS + op.SAIDAS]})
