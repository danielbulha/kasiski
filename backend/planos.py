"""Planos, limites mensais, vencimento da assinatura e registro de consumo de IA."""
from datetime import datetime, timedelta

from flask import current_app

from extensions import ErroAPI, db
from models import Empresa, UsoIA

PLANOS = {
    "trial": {"nome": "Teste grátis", "preco": 0, "empresas": 1, "analises": 2, "concorrentes": 1,
              "pecas": True, "precos": True, "propostas": False, "contratos": 1, "marca": False},
    "essencial": {"nome": "Essencial", "preco": 197, "empresas": 1, "analises": 5, "concorrentes": 0,
                  "pecas": False, "precos": False, "propostas": False, "contratos": 0, "marca": False},
    "profissional": {"nome": "Profissional", "preco": 497, "empresas": 1, "analises": 20, "concorrentes": 5,
                     "pecas": True, "precos": True, "propostas": False, "contratos": 10, "marca": False},
    "avancado": {"nome": "Avançado", "preco": 799, "empresas": 3, "analises": 40, "concorrentes": 15,
                 "pecas": True, "precos": True, "propostas": True, "contratos": 30, "marca": False},
    "consultor": {"nome": "Consultor", "preco": 1290, "empresas": 10, "analises": 60, "concorrentes": 30,
                  "pecas": True, "precos": True, "propostas": True, "contratos": 50, "marca": True},
    "suspenso": {"nome": "Suspenso", "preco": 0, "empresas": 0, "analises": 0, "concorrentes": 0,
                 "pecas": False, "precos": False, "propostas": False, "contratos": 0, "marca": False},
}

PAGOS = ("essencial", "profissional", "avancado", "consultor")
PACOTE_CONTRATOS = {"contratos": 10, "preco": 169.90}  # pacote extra mensal de contratos


def preco(plano, ciclo="mensal"):
    """Preço cobrado por ciclo. Anual = preço mensal x ANUAL_MESES_PAGOS (padrão: paga 10, leva 12)."""
    mensal = PLANOS[plano]["preco"]
    if ciclo == "anual":
        return round(mensal * current_app.config["ANUAL_MESES_PAGOS"], 2)
    return float(mensal)


def pacotes_ativos(conta):
    """Quantidade de pacotes extras de contratos pagos e dentro do prazo (com a mesma carência do plano)."""
    if not conta.pacotes_contratos or not conta.pacotes_ate or conta.plano not in PAGOS:
        return 0
    if datetime.utcnow() > conta.pacotes_ate + timedelta(days=current_app.config["CARENCIA_DIAS"]):
        return 0
    return int(conta.pacotes_contratos)


def limite_contratos(conta):
    base = PLANOS.get(conta.plano, PLANOS["suspenso"]).get("contratos") or 0
    return int(base) + pacotes_ativos(conta) * PACOTE_CONTRATOS["contratos"]


def mrr_da_conta(conta):
    """Receita recorrente mensal que a conta representa hoje (0 se não estiver pagando)."""
    if conta.plano not in PAGOS or conta.assinatura_status not in ("ativa",):
        return 0.0
    base = preco(conta.plano, conta.ciclo or "mensal") / (12 if conta.ciclo == "anual" else 1)
    if pacotes_ativos(conta) and conta.pacotes_status == "ativa":
        base += pacotes_ativos(conta) * PACOTE_CONTRATOS["preco"]
    return round(base, 2)


def verificar_vencimento(conta):
    """Suspende a conta paga cujo acesso venceu há mais que a carência. Contas com plano definido
    manualmente pelo administrador (sem pago_ate) nunca são suspensas por aqui."""
    if conta.plano not in PAGOS or not conta.pago_ate:
        return False
    limite = conta.pago_ate + timedelta(days=current_app.config["CARENCIA_DIAS"])
    if datetime.utcnow() > limite:
        conta.plano = "suspenso"
        if conta.assinatura_status == "ativa":
            conta.assinatura_status = "inadimplente"
        db.session.commit()
        return True
    return False


NOMES_RECURSO = {"propostas": "a elaboração de propostas comerciais (disponível a partir do plano Avançado)",
                 "analises": "análises de edital", "concorrentes": "análises de concorrentes",
                 "pecas": "o gerador de peças", "precos": "a inteligência de preços",
                 "contratos": "a gestão de contratos (disponível a partir do plano Profissional)", "empresas": "empresas cadastradas"}


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
                "empresas": Empresa.query.filter_by(conta_id=conta.id).count(), "contratos": contar_contratos(conta)},
        "limite_contratos": limite_contratos(conta),
        "pacotes": {"ativos": pacotes_ativos(conta), "contratados": conta.pacotes_contratos or 0,
                    "ate": conta.pacotes_ate.isoformat() if conta.pacotes_ate else None, "status": conta.pacotes_status,
                    "metodo": conta.pacotes_metodo, **PACOTE_CONTRATOS},
        "custo_ia_mes_usd": round(float(custo or 0), 4),
        "assinatura": {"status": conta.assinatura_status, "ciclo": conta.ciclo, "metodo": conta.metodo_pagamento,
                       "pago_ate": conta.pago_ate.isoformat() if conta.pago_ate else None,
                       "recorrente": conta.metodo_pagamento == "recorrente" and conta.assinatura_status == "ativa"},
    }


def contar_contratos(conta):
    from models import Contrato
    ids = [e.id for e in Empresa.query.filter_by(conta_id=conta.id)]
    return Contrato.query.filter(Contrato.empresa_id.in_(ids)).count() if ids else 0


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
    if recurso == "contratos":
        lim, atual = limite_contratos(conta), contar_contratos(conta)
        if atual >= lim:
            extra = (" Contrate um pacote de +10 contratos por R$ 169,90/mês em Plano e conta, ou faça upgrade."
                     if conta.plano in PAGOS else " Escolha um plano para cadastrar mais contratos.")
            raise ErroAPI(f"Você atingiu o limite de {lim} contrato(s) do seu plano.{extra}", 402, "limite_contratos")
        return
    if recurso == "empresas":
        atual = Empresa.query.filter_by(conta_id=conta.id).count()
    else:
        atual = uso_mes(conta, recurso)
    if atual >= limite and recurso == "empresas":
        proximo = "Avançado (3 empresas) ou Consultor (10 empresas)" if limite < 3 else "Consultor (10 empresas)"
        raise ErroAPI(f"Seu plano permite até {limite} empresa(s). Faça upgrade para o plano {proximo} "
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
