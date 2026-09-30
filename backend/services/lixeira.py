"""Lixeira: excluir manda o item para cá; ele pode ser restaurado por 30 dias e depois é apagado de vez
(inclusive os arquivos). Os itens na lixeira somem de todas as consultas (filtro em models.py)."""
import logging
import os
from datetime import datetime, timedelta

from flask import current_app

from extensions import ErroAPI, db
from models import (Analise, AnaliseConcorrente, Concorrente, Contrato, Disputa, Documento, DocumentoConcorrente, DocumentoLicitacao,
                    Edital, Empresa, Movimento, Pagamento, Peca, PesquisaPreco, Prazo, Proposta, Revisao)

log = logging.getLogger(__name__)
DIAS = 30
TIPOS = {
    "edital": (Edital, "Licitação"), "contrato": (Contrato, "Contrato"), "peca": (Peca, "Peça"),
    "proposta": (Proposta, "Proposta comercial"), "documento": (Documento, "Documento do cofre"),
    "doc_licitacao": (DocumentoLicitacao, "Documento da licitação"), "doc_concorrente": (DocumentoConcorrente, "Documento de concorrente"),
    "analise_concorrente": (AnaliseConcorrente, "Análise de concorrente"), "pesquisa_preco": (PesquisaPreco, "Pesquisa de preços"),
    "prazo": (Prazo, "Prazo da agenda"), "disputa": (Disputa, "Sala de disputa"),
}
# o que vai junto para a lixeira (e volta junto) quando o principal é excluído
CASCATA = {"edital": [(Prazo, "edital_id"), (Peca, "edital_id"), (Proposta, "edital_id"), (DocumentoLicitacao, "edital_id"),
                      (AnaliseConcorrente, "edital_id"), (Disputa, "edital_id")],
           "contrato": [(Prazo, "contrato_id")]}


def _q(modelo):
    return modelo.query.execution_options(incluir_excluidos=True)


def titulo(tipo, o):
    if tipo == "edital":
        return " · ".join(x for x in (o.numero or o.numero_controle, o.orgao, (o.objeto or "")[:90]) if x) or f"Licitação {o.id}"
    if tipo == "contrato":
        return f"Contrato {o.numero or o.id} · {o.orgao or ''}".strip(" ·")
    if tipo in ("peca", "proposta"):
        return o.titulo or f"{TIPOS[tipo][1]} {o.id}"
    if tipo == "documento":
        return o.tipo or o.nome_arquivo or f"Documento {o.id}"
    if tipo in ("doc_licitacao", "doc_concorrente"):
        return o.titulo or o.nome_arquivo or f"Documento {o.id}"
    if tipo == "analise_concorrente":
        return f"Análise de {'habilitação' if o.tipo == 'habilitacao' else 'proposta'} · {o.nome_arquivo or ''}".strip(" ·")
    if tipo == "pesquisa_preco":
        return getattr(o, "descricao", None) or getattr(o, "termo", None) or f"Pesquisa {o.id}"
    if tipo == "prazo":
        return o.titulo or f"Prazo {o.id}"
    if tipo == "disputa":
        return f"Disputa · item {o.item or '—'} · {(o.descricao or '')[:80]}".strip(" ·")
    return str(o.id)


def enviar(tipo, obj, usuario_nome):
    agora = datetime.utcnow()
    grupo = f"{tipo}:{obj.id}"
    obj.excluido_em, obj.excluido_por, obj.excluido_grupo = agora, (usuario_nome or "")[:120], None
    for modelo, campo in CASCATA.get(tipo, []):
        for filho in modelo.query.filter(getattr(modelo, campo) == obj.id).all():  # só os que não estavam na lixeira
            filho.excluido_em, filho.excluido_por, filho.excluido_grupo = agora, (usuario_nome or "")[:120], grupo
    db.session.flush()
    return {"ok": True, "lixeira": True, "expira_em": (agora + timedelta(days=DIAS)).isoformat()}


def restaurar(tipo, obj):
    grupo = f"{tipo}:{obj.id}"
    obj.excluido_em = obj.excluido_por = obj.excluido_grupo = None
    for modelo, _ in CASCATA.get(tipo, []):
        for filho in _q(modelo).filter_by(excluido_grupo=grupo).all():
            filho.excluido_em = filho.excluido_por = filho.excluido_grupo = None
    db.session.flush()


def _remover_arquivo(rel):
    if not rel:
        return
    try:
        os.remove(os.path.join(current_app.config["UPLOAD_DIR"], rel))
    except OSError:
        pass


def apagar(tipo, o):
    """Exclusão definitiva (sem volta), com os arquivos."""
    if tipo == "edital":
        eid = o.id
        _remover_arquivo(o.arquivo)
        for d in _q(DocumentoLicitacao).filter_by(edital_id=eid).all():
            _remover_arquivo(d.arquivo)
            db.session.delete(d)
        grupo = f"edital:{eid}"
        for p in _q(Peca).filter_by(excluido_grupo=grupo).all():
            Revisao.query.filter_by(peca_id=p.id).delete()
            db.session.delete(p)
        _q(Proposta).filter_by(excluido_grupo=grupo).delete(synchronize_session=False)
        Analise.query.filter_by(edital_id=eid).delete()
        _q(AnaliseConcorrente).filter_by(edital_id=eid).delete(synchronize_session=False)
        _q(Prazo).filter_by(edital_id=eid).delete(synchronize_session=False)
        _q(Disputa).filter_by(edital_id=eid).delete(synchronize_session=False)
        Movimento.query.filter_by(edital_id=eid).delete()
        _q(Peca).filter_by(edital_id=eid).update({"edital_id": None}, synchronize_session=False)
        _q(Proposta).filter_by(edital_id=eid).update({"edital_id": None}, synchronize_session=False)
        _q(Contrato).filter_by(edital_id=eid).update({"edital_id": None}, synchronize_session=False)
    elif tipo == "contrato":
        _remover_arquivo(o.arquivo)
        _q(Prazo).filter_by(contrato_id=o.id).delete(synchronize_session=False)
        Pagamento.query.filter_by(contrato_id=o.id).delete()
        _q(Peca).filter_by(contrato_id=o.id).update({"contrato_id": None}, synchronize_session=False)
    elif tipo == "peca":
        Revisao.query.filter_by(peca_id=o.id).delete()
    elif tipo in ("documento", "doc_licitacao", "doc_concorrente"):
        _remover_arquivo(o.arquivo)
        if tipo == "doc_concorrente":
            c = Concorrente.query.get(o.concorrente_id)
            if c and c.perfil:
                c.perfil_status = "desatualizado"
    db.session.delete(o)
    db.session.flush()


def _empresas_da_conta(conta_id):
    return [e.id for e in Empresa.query.filter_by(conta_id=conta_id)]


def _dono(tipo, o, conta_id, empresas):
    if tipo == "doc_concorrente":
        return o.conta_id == conta_id
    if tipo == "analise_concorrente":
        ed = _q(Edital).get(o.edital_id)
        return bool(ed and ed.empresa_id in empresas)
    return getattr(o, "empresa_id", None) in empresas


def listar(conta_id):
    empresas = _empresas_da_conta(conta_id)
    itens = []
    for tipo, (modelo, rotulo) in TIPOS.items():
        q = _q(modelo).filter(modelo.excluido_em.isnot(None), modelo.excluido_grupo.is_(None))
        if tipo == "doc_concorrente":
            q = q.filter(modelo.conta_id == conta_id)
        elif tipo == "analise_concorrente":
            ids = [e.id for e in _q(Edital).filter(Edital.empresa_id.in_(empresas or [0]))]
            q = q.filter(modelo.edital_id.in_(ids or [0]))
        else:
            q = q.filter(modelo.empresa_id.in_(empresas or [0]))
        for o in q.all():
            itens.append({"tipo": tipo, "rotulo": rotulo, "id": o.id, "titulo": titulo(tipo, o)[:250],
                          "excluido_em": o.excluido_em.isoformat(), "excluido_por": o.excluido_por,
                          "apaga_em": (o.excluido_em + timedelta(days=DIAS)).isoformat(),
                          "arrasta": sum(_q(m).filter_by(excluido_grupo=f"{tipo}:{o.id}").count() for m, _ in CASCATA.get(tipo, []))})
    itens.sort(key=lambda x: x["excluido_em"], reverse=True)
    return itens


def obter(tipo, oid, conta_id):
    if tipo not in TIPOS:
        raise ErroAPI("Tipo de item inválido.", 404)
    modelo = TIPOS[tipo][0]
    o = _q(modelo).filter(modelo.id == oid, modelo.excluido_em.isnot(None)).first()
    if not o or not _dono(tipo, o, conta_id, _empresas_da_conta(conta_id)):
        raise ErroAPI("Item não encontrado na lixeira.", 404)
    return o


def purgar(conta_id=None, dias=DIAS):
    """Apaga de vez o que está na lixeira há mais de `dias` dias. Chamado pelo job diário e ao abrir a lixeira."""
    corte = datetime.utcnow() - timedelta(days=dias)
    empresas = _empresas_da_conta(conta_id) if conta_id else None
    total = 0
    for tipo, (modelo, _) in TIPOS.items():
        q = _q(modelo).filter(modelo.excluido_em.isnot(None), modelo.excluido_em < corte, modelo.excluido_grupo.is_(None))
        if empresas is not None and hasattr(modelo, "empresa_id"):
            q = q.filter(modelo.empresa_id.in_(empresas or [0]))
        elif empresas is not None and tipo == "doc_concorrente":
            q = q.filter(modelo.conta_id == conta_id)
        for o in q.all():
            try:
                apagar(tipo, o)
                total += 1
            except Exception:
                log.exception("Falha ao apagar %s %s da lixeira", tipo, o.id)
                db.session.rollback()
    db.session.commit()
    return total
