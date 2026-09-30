"""Sala de disputa: vários pregões ao mesmo tempo, com estratégia de lances por item e próximo lance calculado.
O Kasiski não envia lances: o usuário dá o lance no portal e registra aqui (ou registra o melhor lance que viu)."""
import re
from datetime import datetime

from flask import Blueprint, g, jsonify, request

import planos
from auth import login_requerido
from extensions import ErroAPI, db
from models import Disputa, Edital, Proposta
from routes import dados, edital_da_conta, empresa_da_conta, para_float
from services import disputa as D

bp = Blueprint("disputa", __name__, url_prefix="/api")
CAMPOS_TEXTO = ("item", "descricao", "portal", "modo", "criterio", "estrategia", "decremento_tipo", "notas", "status", "resultado")
CAMPOS_NUM = ("valor_referencia", "lance_inicial", "preco_piso", "decremento", "diferenca_minima")


def _portal_do_edital(ed):
    t = (ed.portal_disputa or ed.link or "").lower()
    for chave, padrao in (("comprasgov", r"compras\.gov|comprasnet|gov\.br/compras"), ("bec", r"\bbec\b|bec\.sp"),
                          ("licitacoes_e", r"licitacoes-e"), ("bll", r"\bbll\b"), ("portal_compras_publicas", r"portaldecompraspublicas")):
        if re.search(padrao, t):
            return chave
    return "comprasgov" if ed.numero_controle and not t else "outro"


def _disputa(did):
    d = Disputa.query.get(did)
    if not d or d.excluido_em:
        raise ErroAPI("Disputa não encontrada.", 404)
    empresa_da_conta(d.empresa_id)
    return d


def _aplicar(d, x):
    for c in CAMPOS_TEXTO:
        if c in x and x[c] is not None:
            setattr(d, c, str(x[c]).strip()[:400] or None)
    for c in CAMPOS_NUM:
        if c in x:
            setattr(d, c, para_float(x[c]))
    for c in ("intervalo_proprio_s", "intervalo_outros_s", "posicao"):
        if c in x:
            try:
                setattr(d, c, max(0, min(600, int(x[c])))) if x[c] not in (None, "") else setattr(d, c, None)
            except (TypeError, ValueError):
                pass
    if d.portal not in D.PORTAIS:
        d.portal = "outro"
    if d.modo not in D.MODOS:
        d.modo = "aberto"
    if d.criterio not in ("menor_preco", "maior_desconto"):
        d.criterio = "menor_preco"
    if d.estrategia not in D.ESTRATEGIAS:
        d.estrategia = "moderada"


@bp.get("/disputa/config")
@login_requerido
def config():
    return jsonify({"estrategias": D.ESTRATEGIAS, "modos": D.MODOS,
                    "portais": {k: {"nome": n, "url": u} for k, (n, u) in D.PORTAIS.items()}})


@bp.get("/empresas/<int:eid>/disputas")
@login_requerido
def listar(eid):
    empresa_da_conta(eid)
    q = Disputa.query.filter_by(empresa_id=eid)
    if request.args.get("encerradas") != "1":
        q = q.filter(Disputa.status != "encerrada")
    ds = q.order_by(Disputa.id.desc()).limit(100).all()
    eds = {e.id: e for e in Edital.query.filter(Edital.id.in_([d.edital_id for d in ds if d.edital_id] or [0]))}
    saida = []
    for d in ds:
        x = D.to_dict(d)
        ed = eds.get(d.edital_id)
        x["edital"] = {"id": ed.id, "numero": ed.numero, "orgao": ed.orgao, "objeto": (ed.objeto or "")[:160],
                       "data_abertura": ed.data_abertura.isoformat() if ed.data_abertura else None, "link": ed.link} if ed else None
        saida.append(x)
    # próximas sessões das oportunidades que ainda não têm sala
    com_sala = {d.edital_id for d in ds}
    agora = datetime.utcnow()
    proximas = Edital.query.filter(Edital.empresa_id == eid, Edital.data_abertura.isnot(None), Edital.data_abertura >= agora) \
        .filter(Edital.etapa.in_(["decisao", "preparacao", "pronta", "em_disputa"])).order_by(Edital.data_abertura).limit(8).all()
    return jsonify({"disputas": saida, "proximas": [{"id": e.id, "numero": e.numero, "orgao": e.orgao, "objeto": (e.objeto or "")[:140],
                                                    "data_abertura": e.data_abertura.isoformat(), "tem_sala": e.id in com_sala}
                                                   for e in proximas], "agora": agora.isoformat(timespec="seconds")})


@bp.post("/empresas/<int:eid>/disputas")
@login_requerido
def criar(eid):
    empresa_da_conta(eid)
    planos.exigir(g.conta, "disputa")
    x = dados()
    ed = edital_da_conta(x["edital_id"]) if x.get("edital_id") else None
    if ed and ed.empresa_id != eid:
        raise ErroAPI("Esta licitação é de outra empresa.")
    itens = x.get("itens") or [{"item": x.get("item") or "Global", "descricao": x.get("descricao") or (ed.objeto if ed else ""),
                                "valor_referencia": x.get("valor_referencia") if x.get("valor_referencia") is not None else (ed.valor_estimado if ed else None)}]
    base = {"portal": x.get("portal") or (_portal_do_edital(ed) if ed else "outro"), "modo": x.get("modo") or "aberto",
            "criterio": x.get("criterio") or "menor_preco", "estrategia": x.get("estrategia") or "moderada"}
    prop = Proposta.query.filter_by(edital_id=ed.id).order_by(Proposta.id.desc()).first() if ed else None
    pp = D.piso_da_proposta(prop) if prop else {}
    criadas = []
    for it in itens[:50]:
        d = Disputa(empresa_id=eid, edital_id=ed.id if ed else None)
        _aplicar(d, {**base, **{k: v for k, v in x.items() if k in CAMPOS_TEXTO + CAMPOS_NUM and k not in ("item", "descricao")}, **it})
        if len(itens) == 1 and prop:  # uma disputa pelo valor global: a proposta comercial dá o lance inicial e o piso
            d.lance_inicial = d.lance_inicial or pp.get("preco")
            d.preco_piso = d.preco_piso or pp.get("piso")
        db.session.add(d)
        criadas.append(d)
    db.session.commit()
    return jsonify({"disputas": [D.to_dict(d) for d in criadas], "proposta": pp or None}), 201


@bp.patch("/disputas/<int:did>")
@login_requerido
def editar(did):
    d = _disputa(did)
    _aplicar(d, dados())
    if d.status == "encerrada" and d.resultado == "vencedor" and d.edital_id:
        from services import oportunidades
        ed = Edital.query.get(d.edital_id)
        if ed:
            oportunidades.avancar(ed, "classificada", f"Sala de disputa: melhor lance no item {d.item or ''}.".strip(), autor=g.usuario.nome)
    db.session.commit()
    return jsonify(D.to_dict(d))


@bp.post("/disputas/<int:did>/lance")
@login_requerido
def lance(did):
    """{valor, tipo: 'meu' (dei este lance no portal) | 'mercado' (melhor lance que apareceu no portal)}"""
    d = _disputa(did)
    x = dados()
    valor = para_float(x.get("valor"))
    if valor is None or valor <= 0:
        raise ErroAPI("Informe o valor do lance.")
    tipo = "meu" if x.get("tipo") == "meu" else "mercado"
    if tipo == "meu" and d.preco_piso is not None and \
            ((d.criterio == "menor_preco" and valor < d.preco_piso) or (d.criterio == "maior_desconto" and valor > d.preco_piso)) \
            and not x.get("confirmar_abaixo_piso"):
        raise ErroAPI("Esse lance passa do seu piso. Confirme se foi isso mesmo.", 409, "abaixo_piso")
    D.registrar_lance(d, valor, tipo, x.get("obs"))
    db.session.commit()
    return jsonify(D.to_dict(d))


@bp.post("/disputas/<int:did>/desfazer")
@login_requerido
def desfazer(did):
    """Apaga o último registro (digitação errada) e recalcula a situação."""
    d = _disputa(did)
    log = list(d.lances or [])
    if log:
        log.pop()
    d.lances = log
    meus = [x for x in log if x["tipo"] == "meu"]
    d.meu_ultimo = meus[-1]["valor"] if meus else None
    d.meu_ultimo_em = datetime.fromisoformat(meus[-1]["em"]) if meus else None
    todos = [x["valor"] for x in log]
    d.melhor_lance = (min(todos) if d.criterio == "menor_preco" else max(todos)) if todos else None
    d.melhor_em = datetime.fromisoformat(log[-1]["em"]) if log else None
    db.session.commit()
    return jsonify(D.to_dict(d))


@bp.post("/disputas/<int:did>/analise")
@login_requerido
def analisar(did):
    """Análise de lances com IA + DoubleCheck, em segundo plano (a tela acompanha pelo GET)."""
    d = _disputa(did)
    atual = d.analise or {}
    ini = atual.get("iniciado_em")
    if atual.get("status") == "processando" and ini and (datetime.utcnow() - datetime.fromisoformat(ini)).total_seconds() < 600:
        return jsonify(D.to_dict(d)), 202
    ed = Edital.query.get(d.edital_id) if d.edital_id else None
    if not ed:
        raise ErroAPI("A análise de lances usa o histórico da licitação: abra a sala a partir de uma oportunidade.")
    if not (ed.possiveis_concorrentes or {}).get("itens"):
        if not (ed.objeto or "").strip():
            raise ErroAPI("A licitação ainda não tem objeto. Analise o edital antes de pedir a análise de lances.")
        planos.exigir(g.conta, "possiveis")
    d.analise = {"status": "processando", "etapa": "Reunindo o histórico de preços dos possíveis concorrentes",
                 "iniciado_em": datetime.utcnow().isoformat(timespec="seconds")}
    db.session.commit()
    from services import analise_lances, tarefas
    tarefas.rodar(analise_lances.executar, d.id, g.conta.id)
    return jsonify(D.to_dict(d)), 202


@bp.get("/disputas/<int:did>")
@login_requerido
def ver(did):
    return jsonify(D.to_dict(_disputa(did)))


@bp.delete("/disputas/<int:did>")
@login_requerido
def excluir(did):
    d = _disputa(did)
    from services import lixeira
    r = lixeira.enviar("disputa", d, g.usuario.nome)
    db.session.commit()
    return jsonify(r)
