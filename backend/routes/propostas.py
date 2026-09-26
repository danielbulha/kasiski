"""Inteligência de preços e propostas comerciais; busca nas tabelas de referência; admin das tabelas."""
from datetime import datetime, timedelta

from flask import Blueprint, current_app, g, jsonify, request, send_file

import planos
from auth import admin_requerido, login_requerido
from extensions import ErroAPI, db
from models import Edital, Empresa, ItemReferencia, PesquisaPreco, Proposta, TabelaReferencia
from routes import dados, edital_da_conta, empresa_da_conta, para_data, para_float
from services import propostas as svc
from services import tabelas, tarefas
from services.dados_publicos import estatisticas, pesquisa_precos

bp = Blueprint("propostas", __name__, url_prefix="/api")
EM_ANDAMENTO = ("lendo_edital", "gerando")
LIMITE_MIN = 20


def _proposta(pid):
    p = Proposta.query.get(pid)
    if not p:
        raise ErroAPI("Proposta não encontrada.", 404)
    empresa_da_conta(p.empresa_id)
    if p.status in EM_ANDAMENTO and p.atualizado_em and p.atualizado_em < datetime.utcnow() - timedelta(minutes=LIMITE_MIN):
        p.status, p.etapa = ("rascunho" if p.itens else "erro"), None
        p.erro = "A tarefa foi interrompida (o servidor reiniciou ou demorou demais). Tente de novo."
        db.session.commit()
    return p


def _saida(p):
    return {**p.to_dict(), "totais": svc.totais(p), "regimes": svc.REGIMES}


# ---------------------------------------------------------------- propostas
@bp.get("/empresas/<int:eid>/propostas")
@login_requerido
def listar(eid):
    empresa_da_conta(eid)
    ps = Proposta.query.filter_by(empresa_id=eid).order_by(Proposta.id.desc()).all()
    return jsonify([{**p.to_dict(completo=False), "totais": svc.totais(p)} for p in ps])


def _ler_edital(pid, edital_id, conta_id):
    from models import Conta
    p, ed, conta = Proposta.query.get(pid), Edital.query.get(edital_id), Conta.query.get(conta_id)
    try:
        respostas = svc.ler_condicoes(p, ed)
        svc.recalcular(p)
        p.status, p.etapa, p.erro = "rascunho", None, None
        planos.registrar_uso(conta, "propostas", respostas, cobravel=False)
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Falha na tarefa _ler_edital (id %s)", pid)
        p = Proposta.query.get(pid)
        p.status, p.etapa = "rascunho", None
        p.erro = (e.mensagem if isinstance(e, ErroAPI) else
                  "Não foi possível ler o edital agora. Cadastre os itens manualmente ou tente de novo.")
    db.session.commit()


@bp.post("/empresas/<int:eid>/propostas")
@login_requerido
def criar(eid):
    empresa = empresa_da_conta(eid)
    planos.exigir(g.conta, "propostas")
    d = dados()
    ed = edital_da_conta(int(d["edital_id"])) if str(d.get("edital_id") or "").isdigit() else None
    titulo = (d.get("titulo") or "").strip() or (
        f"Proposta — {ed.numero or ed.orgao or 'edital'}" if ed else f"Proposta — {empresa.razao_social}")
    reg = d.get("regime") if d.get("regime") in svc.REGIMES else "simples"
    p = Proposta(empresa_id=eid, edital_id=ed.id if ed else None, titulo=titulo[:300], regime=reg,
                 tributos_pct=svc.REGIMES[reg]["tributos_pct"], bdi_pct=20.0, itens=[], condicoes={})
    if ed and ed.texto:
        p.status, p.etapa = "lendo_edital", "Lendo as regras da proposta no edital"
    db.session.add(p)
    db.session.commit()
    if p.status == "lendo_edital":
        tarefas.rodar(_ler_edital, p.id, ed.id, g.conta.id)
    return jsonify(_saida(p)), 201


@bp.get("/propostas/<int:pid>")
@login_requerido
def ver(pid):
    return jsonify(_saida(_proposta(pid)))


@bp.patch("/propostas/<int:pid>")
@login_requerido
def editar(pid):
    p = _proposta(pid)
    if p.status in EM_ANDAMENTO:
        raise ErroAPI("Aguarde a tarefa em andamento terminar.", 409)
    d = dados()
    if "titulo" in d:
        p.titulo = (d["titulo"] or "").strip()[:300] or p.titulo
    if d.get("regime") in svc.REGIMES:
        p.regime = d["regime"]
    for campo in ("tributos_pct", "bdi_pct"):
        if campo in d and para_float(d[campo]) is not None:
            setattr(p, campo, max(0.0, min(para_float(d[campo]), 300.0)))
    if "validade_dias" in d:
        try:
            p.validade_dias = max(1, min(int(d["validade_dias"]), 3650))
        except (TypeError, ValueError):
            pass
    if isinstance(d.get("bdi_detalhe"), dict):
        det = {k: para_float(v) or 0 for k, v in d["bdi_detalhe"].items() if k in ("ac", "sg", "r", "df", "l")}
        p.bdi_detalhe = det
        if d.get("aplicar_bdi_tcu"):
            calc = svc.bdi_tcu(det.get("ac"), det.get("sg"), det.get("r"), det.get("df"), det.get("l"), p.tributos_pct)
            if calc is not None:
                p.bdi_pct = calc
    if isinstance(d.get("itens"), list):
        permitidos = ("numero", "lote", "descricao", "unidade", "quantidade", "custo_unitario", "bdi", "preco_unitario",
                      "preco_manual", "valor_unitario_estimado", "catmat", "tipo_catalogo", "pagina", "referencias",
                      "observacao")
        p.itens = [{k: v for k, v in it.items() if k in permitidos} for it in d["itens"][:500] if isinstance(it, dict)]
    if "texto" in d:
        p.texto = d["texto"] or ""
    svc.recalcular(p)
    db.session.commit()
    return jsonify(_saida(p))


@bp.delete("/propostas/<int:pid>")
@login_requerido
def excluir(pid):
    p = _proposta(pid)
    db.session.delete(p)
    db.session.commit()
    return jsonify({"ok": True})


@bp.post("/propostas/<int:pid>/reler-edital")
@login_requerido
def reler(pid):
    p = _proposta(pid)
    planos.exigir(g.conta, "propostas")
    if not p.edital_id:
        raise ErroAPI("Esta proposta não está ligada a um edital.")
    ed = edital_da_conta(p.edital_id)
    if not ed.texto:
        raise ErroAPI("O edital ainda não tem texto. Envie o PDF do edital.")
    if p.status in EM_ANDAMENTO:
        return jsonify(_saida(p)), 202
    p.status, p.etapa, p.erro = "lendo_edital", "Lendo as regras da proposta no edital", None
    db.session.commit()
    tarefas.rodar(_ler_edital, p.id, ed.id, g.conta.id)
    return jsonify(_saida(p)), 202


def _gerar_minuta(pid, conta_id):
    from models import Conta
    p, conta = Proposta.query.get(pid), Conta.query.get(conta_id)
    try:
        empresa = Empresa.query.get(p.empresa_id)
        edital = Edital.query.get(p.edital_id) if p.edital_id else None
        p.etapa = "Redigindo a minuta e revisando os preços"
        db.session.commit()
        respostas = svc.gerar_minuta(p, empresa, edital)
        p.status, p.etapa, p.erro = "pronta", None, None
        planos.registrar_uso(conta, "propostas", respostas, cobravel=False)
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception("Falha na tarefa _gerar_minuta (id %s)", pid)
        p = Proposta.query.get(pid)
        p.status, p.etapa = "rascunho", None
        p.erro = e.mensagem if isinstance(e, ErroAPI) else "Não foi possível gerar a minuta agora. Tente de novo em instantes."
    db.session.commit()


@bp.post("/propostas/<int:pid>/minuta")
@login_requerido
def minuta(pid):
    p = _proposta(pid)
    planos.exigir(g.conta, "propostas")
    if not p.itens:
        raise ErroAPI("Cadastre pelo menos um item com preço antes de gerar a minuta.")
    if not any(it.get("preco_unitario") for it in p.itens):
        raise ErroAPI("Informe o custo ou o preço de pelo menos um item antes de gerar a minuta.")
    if p.status in EM_ANDAMENTO:
        return jsonify(_saida(p)), 202
    svc.recalcular(p)
    p.status, p.etapa, p.erro = "gerando", "Na fila", None
    db.session.commit()
    tarefas.rodar(_gerar_minuta, p.id, g.conta.id)
    return jsonify(_saida(p)), 202


@bp.get("/propostas/<int:pid>/docx")
@login_requerido
def baixar_docx(pid):
    p = _proposta(pid)
    buf = svc.docx(p, Empresa.query.get(p.empresa_id))
    return send_file(buf, as_attachment=True, download_name=svc.nome_arquivo(p),
                     mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document")


# ---------------------------------------------------------------- inteligência de preço por item
@bp.post("/propostas/<int:pid>/referencias")
@login_requerido
def referencias(pid):
    """Referências para um item: tabelas oficiais, preços praticados (Compras.gov) e pesquisas salvas."""
    p = _proposta(pid)
    planos.exigir(g.conta, "propostas")
    d = dados()
    descricao = (d.get("descricao") or "").strip()
    if not descricao:
        raise ErroAPI("Informe a descrição do item.")
    empresa = Empresa.query.get(p.empresa_id)
    uf = (d.get("uf") or (empresa.ufs or "")[:2] or "").upper()[:2] or None
    codigo = "".join(ch for ch in str(d.get("catmat") or "") if ch.isdigit())
    tipo = d.get("tipo_catalogo") if d.get("tipo_catalogo") in ("material", "servico") else "material"
    mercado = None
    if codigo:
        amostras = pesquisa_precos(codigo, tipo, uf) or (pesquisa_precos(codigo, tipo, None) if uf else [])
        mercado = {"codigo": codigo, "tipo": tipo, "uf": uf, "estatisticas": estatisticas([a["preco"] for a in amostras]),
                   "amostras": sorted(amostras, key=lambda a: str(a.get("data") or ""), reverse=True)[:30]}
    ts = tabelas.termos(descricao)
    salvas = []
    for ps in PesquisaPreco.query.filter_by(empresa_id=p.empresa_id).all():
        alvo = tabelas.norm(ps.descricao)
        if ts and sum(t in alvo for t in ts) >= max(1, len(ts) // 2) and (ps.estatisticas or {}).get("n"):
            salvas.append({"id": ps.id, "descricao": ps.descricao, "estatisticas": ps.estatisticas})
    return jsonify({"tabelas": tabelas.buscar(descricao, uf=uf, limite=12), "mercado": mercado, "pesquisas": salvas[:5],
                    "uf": uf, "tem_tabelas": TabelaReferencia.query.filter_by(ativa=True).count() > 0})


@bp.get("/tabelas-referencia")
@login_requerido
def tabelas_publicas():
    return jsonify([t.to_dict() for t in TabelaReferencia.query.filter_by(ativa=True).order_by(TabelaReferencia.nome)])


@bp.get("/tabelas-referencia/buscar")
@login_requerido
def buscar_tabelas():
    q = (request.args.get("q") or "").strip()
    if len(q) < 3:
        raise ErroAPI("Digite pelo menos 3 letras para buscar.")
    fontes = [f for f in (request.args.get("fontes") or "").split(",") if f in tabelas.FONTES] or None
    return jsonify(tabelas.buscar(q, uf=(request.args.get("uf") or "").upper()[:2] or None, fontes=fontes, limite=40))


# ---------------------------------------------------------------- admin: tabelas de referência
@bp.get("/admin/tabelas")
@admin_requerido
def admin_tabelas():
    return jsonify({"tabelas": [t.to_dict() for t in TabelaReferencia.query.order_by(TabelaReferencia.id.desc())],
                    "fontes": tabelas.FONTES})


def _arquivo():
    f = request.files.get("arquivo")
    if not f or not f.filename:
        raise ErroAPI("Envie a planilha (.xlsx ou .csv).")
    return f.read(), f.filename


@bp.post("/admin/tabelas/previa")
@admin_requerido
def admin_previa():
    conteudo, nome = _arquivo()
    return jsonify(tabelas.ler_previa(conteudo, nome))


@bp.post("/admin/tabelas")
@admin_requerido
def admin_importar():
    conteudo, nome = _arquivo()
    d = request.form
    if not (d.get("nome") or "").strip():
        raise ErroAPI("Dê um nome à tabela (ex.: SINAPI SP 09/2026 não desonerado).")

    def idx(campo):
        v = d.get(f"col_{campo}")
        return int(v) if v not in (None, "", "-1") and str(v).lstrip("-").isdigit() else None
    mapa = {c: idx(c) for c in ("codigo", "descricao", "unidade", "preco")}
    t = TabelaReferencia(nome=d["nome"].strip()[:200], fonte=d.get("fonte") if d.get("fonte") in tabelas.FONTES else "outra",
                         uf=(d.get("uf") or "").upper()[:2] or None, data_base=para_data(d.get("data_base")),
                         observacao=(d.get("observacao") or "").strip() or None)
    db.session.add(t)
    db.session.flush()
    try:
        tabelas.importar(t, conteudo, nome, mapa, int(d.get("linha_cabecalho") or 0))
    except Exception:
        db.session.rollback()
        raise
    return jsonify(t.to_dict()), 201


@bp.patch("/admin/tabelas/<int:tid>")
@admin_requerido
def admin_editar_tabela(tid):
    t = TabelaReferencia.query.get_or_404(tid)
    d = dados()
    if "ativa" in d:
        t.ativa = bool(d["ativa"])
    for campo in ("nome", "observacao"):
        if campo in d:
            setattr(t, campo, (d[campo] or "").strip() or getattr(t, campo))
    db.session.commit()
    return jsonify(t.to_dict())


@bp.delete("/admin/tabelas/<int:tid>")
@admin_requerido
def admin_excluir_tabela(tid):
    t = TabelaReferencia.query.get_or_404(tid)
    ItemReferencia.query.filter_by(tabela_id=tid).delete()
    db.session.delete(t)
    db.session.commit()
    return jsonify({"ok": True})
