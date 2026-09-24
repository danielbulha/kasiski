"""Planos, limites mensais e registro de consumo de IA."""
from datetime import datetime

from extensions import ErroAPI, db
from models import Empresa, UsoIA

PLANOS = {
    "trial": {"nome": "Teste grátis", "preco": 0, "empresas": 1, "analises": 2, "concorrentes": 1,
              "pecas": True, "precos": True, "contratos": True, "marca": False},
    "essencial": {"nome": "Essencial", "preco": 197, "empresas": 1, "analises": 5, "concorrentes": 0,
                  "pecas": False, "precos": False, "contratos": True, "marca": False},
    "profissional": {"nome": "Profissional", "preco": 497, "empresas": 1, "analises": 20, "concorrentes": 5,
                     "pecas": True, "precos": True, "contratos": True, "marca": False},
    "consultor": {"nome": "Consultor", "preco": 1290, "empresas": 10, "analises": 60, "concorrentes": 30,
                  "pecas": True, "precos": True, "contratos": True, "marca": True},
    "suspenso": {"nome": "Suspenso", "preco": 0, "empresas": 0, "analises": 0, "concorrentes": 0,
                 "pecas": False, "precos": False, "contratos": False, "marca": False},
}

NOMES_RECURSO = {"analises": "análises de edital", "concorrentes": "análises de concorrentes",
                 "pecas": "o gerador de peças", "precos": "a inteligência de preços",
                 "contratos": "a gestão de contratos", "empresas": "empresas cadastradas"}


def _inicio_mes():
    agora = datetime.utcnow()
    return datetime(agora.year, agora.month, 1)


def teste_expirado(conta):
    return conta.plano == "trial" and conta.trial_fim and datetime.utcnow() > conta.trial_fim


def uso_mes(conta, recurso):
    return UsoIA.query.filter(UsoIA.conta_id == conta.id, UsoIA.recurso == recurso, UsoIA.cobravel.is_(True),
                              UsoIA.criado_em >= _inicio_mes()).count()


def resumo(conta):
    p = PLANOS.get(conta.plano, PLANOS["suspenso"])
    custo = db.session.query(db.func.coalesce(db.func.sum(UsoIA.custo_usd), 0)).filter(
        UsoIA.conta_id == conta.id, UsoIA.criado_em >= _inicio_mes()).scalar()
    return {
        "codigo": conta.plano, **p,
        "teste_expirado": teste_expirado(conta),
        "trial_fim": conta.trial_fim.isoformat() if conta.trial_fim else None,
        "uso": {"analises": uso_mes(conta, "analises"), "concorrentes": uso_mes(conta, "concorrentes"),
                "empresas": Empresa.query.filter_by(conta_id=conta.id).count()},
        "custo_ia_mes_usd": round(float(custo or 0), 4),
    }


def exigir(conta, recurso):
    """Bloqueia se o plano não inclui o recurso ou se o limite do mês acabou."""
    if teste_expirado(conta):
        raise ErroAPI("Seu teste grátis terminou. Escolha um plano para continuar usando a IA.", 402, "teste_expirado")
    p = PLANOS.get(conta.plano, PLANOS["suspenso"])
    limite = p.get(recurso)
    if limite is False or limite == 0:
        raise ErroAPI(f"Seu plano não inclui {NOMES_RECURSO.get(recurso, recurso)}. Faça upgrade para liberar.",
                      402, "fora_do_plano")
    if isinstance(limite, bool):
        return
    if recurso == "empresas":
        atual = Empresa.query.filter_by(conta_id=conta.id).count()
    else:
        atual = uso_mes(conta, recurso)
    if atual >= limite and recurso == "empresas":
        raise ErroAPI(f"Seu plano permite até {limite} empresa(s). Faça upgrade para o plano Consultor "
                      f"para gerenciar mais CNPJs.", 402, "limite_atingido")
    if atual >= limite:
        raise ErroAPI(f"Você atingiu o limite de {limite} {NOMES_RECURSO.get(recurso, recurso)} do seu plano "
                      f"neste mês. Faça upgrade ou aguarde a renovação.", 402, "limite_atingido")


def registrar_uso(conta, recurso, respostas, cobravel=True):
    """Grava uma linha por chamada de IA; só a primeira conta para o limite do plano."""
    primeira = True
    for r in respostas:
        if r is None:
            continue
        db.session.add(UsoIA(conta_id=conta.id, recurso=recurso, cobravel=cobravel and primeira, modelo=r.modelo,
                             tokens_entrada=r.tokens_entrada, tokens_saida=r.tokens_saida, custo_usd=r.custo_usd))
        primeira = False
    if primeira and cobravel:  # nenhuma chamada registrada (ex.: falha antes) — ainda assim conta o uso
        db.session.add(UsoIA(conta_id=conta.id, recurso=recurso, cobravel=True, modelo="-"))
