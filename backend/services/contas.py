"""Exclusão definitiva de uma conta pelo administrador.

Apaga a conta e tudo o que depende dela (usuários, empresas, editais, documentos, contratos, salas de disputa,
análises, convites, vínculos de equipe...) seguindo as chaves estrangeiras do banco, e os arquivos enviados.
Ficam, sem a conta: os pagamentos (histórico financeiro e fiscal) e o registro de teste grátis por CNPJ (para o mesmo
CNPJ não ganhar outro teste). Registros soltos que só citam a conta (logs, leads, eventos, chat) ficam sem o vínculo.
"""
import os
import shutil

from flask import current_app
from sqlalchemy import select

from extensions import ErroAPI, db

PRESERVAR = {"cobranca"}              # registros financeiros: ficam, sem a conta
MANTER_SEM_MEXER = {"trial_cnpj"}     # um teste por CNPJ, mesmo depois da exclusão


def _apagar(tabela, ids, vistos):
    """Apaga as linhas `ids` de `tabela` e, antes, tudo o que aponta para elas (chaves estrangeiras)."""
    ids = [i for i in ids if (tabela.name, i) not in vistos]
    if not ids:
        return
    vistos.update((tabela.name, i) for i in ids)
    for filha in db.metadata.sorted_tables:
        for fk in filha.foreign_keys:
            if fk.column.table is not tabela:
                continue
            col = fk.parent
            if filha.name in PRESERVAR and col.nullable:
                db.session.execute(filha.update().where(col.in_(ids)).values({col.name: None}))
            elif "id" in filha.c:
                filhos = [r[0] for r in db.session.execute(select(filha.c.id).where(col.in_(ids)))]
                _apagar(filha, filhos, vistos)
            else:
                db.session.execute(filha.delete().where(col.in_(ids)))
    db.session.execute(tabela.delete().where(tabela.c.id.in_(ids)))


def _soltar(coluna_nome, ids):
    """Colunas que citam a conta/usuário sem chave estrangeira: tira o vínculo (ou apaga, se não aceitar vazio)."""
    if not ids:
        return
    for t in db.metadata.sorted_tables:
        col = t.c.get(coluna_nome)
        if col is None or col.foreign_keys or t.name in MANTER_SEM_MEXER:
            continue
        if col.nullable:
            db.session.execute(t.update().where(col.in_(ids)).values({coluna_nome: None}))
        else:
            db.session.execute(t.delete().where(col.in_(ids)))


def resumo(conta):
    from models import Empresa, MembroConta, Usuario
    return {"usuarios": Usuario.query.filter_by(conta_id=conta.id).count(),
            "empresas": Empresa.query.filter_by(conta_id=conta.id).count(),
            "membros_de_outras_contas": MembroConta.query.filter_by(conta_id=conta.id).count()}


def excluir(conta, admin):
    """Exclui a conta. `admin` é quem está excluindo (não pode excluir a própria conta)."""
    from models import Conta, Evento, Usuario
    from services import armazenamento
    cid = conta.id   # depois do commit o objeto da conta não existe mais
    if cid == admin.conta_id:
        raise ErroAPI("Você não pode excluir a sua própria conta pelo painel.")
    if conta.assinatura_status == "ativa" and conta.metodo_pagamento == "recorrente" and conta.mp_assinatura_id:
        raise ErroAPI("Esta conta tem assinatura automática ativa no Mercado Pago. Cancele a assinatura antes de excluir, "
                      "para o cliente não continuar sendo cobrado.", 409, "assinatura_ativa")
    usuarios = Usuario.query.filter_by(conta_id=conta.id).all()
    if any(u.email.lower() in current_app.config["ADMIN_EMAILS"] for u in usuarios):
        raise ErroAPI("Esta conta tem um administrador do Kasiski. Tire o e-mail de ADMIN_EMAILS antes de excluir.")
    info = {"conta_id": conta.id, "nome": conta.nome, "emails": [u.email for u in usuarios], **resumo(conta),
            "excluida_por": admin.email}
    pastas = armazenamento._pastas_da_conta(conta)
    ids_usuarios = [u.id for u in usuarios]
    vistos = set()
    _soltar("usuario_id", ids_usuarios)
    _soltar("conta_id", [cid])
    _apagar(Conta.__table__, [cid], vistos)
    db.session.add(Evento(tipo="conta_excluida", dados=info))
    db.session.commit()
    raiz = os.path.realpath(current_app.config["UPLOAD_DIR"])
    for p in pastas:   # arquivos só depois do commit: se o banco falhar, nada some
        if os.path.realpath(p).startswith(raiz + os.sep) and os.path.isdir(p):
            shutil.rmtree(p, ignore_errors=True)
    armazenamento.esquecer_uso(cid)
    return info
