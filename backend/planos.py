"""Planos, limites mensais, teste do Profissional, créditos de inteligência, vencimento e consumo de IA.

Tabela 2026 (FREE → Essencial → Profissional → Business → Consultor → Enterprise):
- FREE é permanente (não é teste). Dentro dele há o botão "Experimentar o Profissional por 7 dias": durante o
  teste a conta usa os limites do Profissional e, ao fim, volta sozinha ao FREE sem perder nada.
- Anual = 10 mensalidades (ANUAL_MESES_PAGOS).
- Assinantes da tabela antiga mantêm o valor que pagam (Conta.preco_contratado) e foram movidos para o plano
  novo equivalente ou superior; quem pagava mais que o preço novo passa a pagar o preço novo (o menor dos dois).
- Por trás dos limites visíveis há créditos: quando o limite do mês acaba, o Pacote de inteligência (créditos)
  cobre o excedente, com custo em créditos por recurso (CREDITOS). Assim os custos de IA podem mudar sem mudar a tabela.
"""
from datetime import datetime, timedelta

from flask import current_app

from extensions import ErroAPI, db
from models import Empresa, UsoIA

PLANOS = {
    "free": {"nome": "Free", "preco": 0, "slogan": "Conheça o seu mercado", "publico": "Para conhecer o Kasiski",
             "empresas": 1, "usuarios": 1, "analises": 1, "concorrentes": 1, "possiveis": 1, "pecas": 0,
             "precos": False, "propostas": False, "contratos": 0, "marca": False, "prioridade": False,
             "radar_max": 10, "cofre_max": 15, "oportunidades_max": 5, "empresa_extra": None, "armazenamento_mb": 100},
    "essencial": {"nome": "Essencial", "preco": 97, "slogan": "Comece sua operação B2G", "publico": "Para quem está começando a licitar",
                  "empresas": 1, "usuarios": 1, "analises": 5, "concorrentes": 3, "possiveis": 3, "pecas": 0,
                  "precos": False, "propostas": False, "contratos": 0, "marca": False, "prioridade": False,
                  "radar_max": None, "cofre_max": None, "oportunidades_max": None, "empresa_extra": None, "armazenamento_mb": 1024},
    "profissional": {"nome": "Profissional", "preco": 247, "slogan": "Transforme oportunidades em decisões",
                     "publico": "Para empresas que disputam todo mês", "destaque": True,
                     "empresas": 1, "usuarios": 3, "analises": 20, "concorrentes": 15, "possiveis": 10, "pecas": 20,
                     "precos": True, "propostas": True, "contratos": 10, "marca": False, "prioridade": False,
                     "radar_max": None, "cofre_max": None, "oportunidades_max": None, "empresa_extra": None, "armazenamento_mb": 5120},
    "business": {"nome": "Business", "preco": 497, "slogan": "Gerencie sua operação B2G", "publico": "Para operações B2G estruturadas",
                 "empresas": 3, "usuarios": 7, "analises": 50, "concorrentes": 40, "possiveis": 25, "pecas": 50,
                 "precos": True, "propostas": True, "contratos": 30, "marca": False, "prioridade": True,
                 "radar_max": None, "cofre_max": None, "oportunidades_max": None, "empresa_extra": 49, "armazenamento_mb": 15360},
    "consultor": {"nome": "Consultor", "preco": 797, "slogan": "Atenda seus clientes em escala",
                  "publico": "Para consultorias e escritórios de licitação",
                  "empresas": 10, "usuarios": 10, "analises": 80, "concorrentes": 60, "possiveis": 40, "pecas": 80,
                  "precos": True, "propostas": True, "contratos": 50, "marca": True, "prioridade": True,
                  "radar_max": None, "cofre_max": None, "oportunidades_max": None, "empresa_extra": 49, "armazenamento_mb": 30720},
    "enterprise": {"nome": "Enterprise", "preco": None, "slogan": "Para grandes operações", "publico": "Sob consulta",
                   "empresas": 50, "usuarios": 50, "analises": 300, "concorrentes": 200, "possiveis": 150, "pecas": 300,
                   "precos": True, "propostas": True, "contratos": 300, "marca": True, "prioridade": True,
                   "radar_max": None, "cofre_max": None, "oportunidades_max": None, "empresa_extra": 49, "armazenamento_mb": 102400},
    "suspenso": {"nome": "Suspenso", "preco": 0, "slogan": "", "publico": "",
                 "empresas": 0, "usuarios": 1, "analises": 0, "concorrentes": 0, "possiveis": 0, "pecas": 0,
                 "precos": False, "propostas": False, "contratos": 0, "marca": False, "prioridade": False,
                 "radar_max": 0, "cofre_max": None, "oportunidades_max": None, "empresa_extra": None, "armazenamento_mb": 100},
}
for _p in PLANOS.values():  # sala de disputa: junto com as propostas comerciais (Profissional em diante)
    _p.setdefault("disputa", _p["propostas"])
ORDEM = ("free", "essencial", "profissional", "business", "consultor", "enterprise")
VENDAVEIS = ("essencial", "profissional", "business", "consultor")      # checkout online
PAGOS = ("essencial", "profissional", "business", "consultor", "enterprise")
ALIAS = {"trial": "free", "avancado": "business"}                       # códigos antigos gravados no banco
TRIAL_DIAS = 7
TRIAL_PLANO = "profissional"

# migração da tabela antiga (preço mensal antigo → plano novo equivalente ou superior)
PRECOS_ANTIGOS = {"essencial": 197, "profissional": 497, "avancado": 799, "consultor": 1290}
MIGRACAO = {"essencial": "profissional", "profissional": "business", "avancado": "consultor", "consultor": "consultor"}

PACOTE_CONTRATOS = {"contratos": 10, "preco": 169.90}  # pacote extra mensal de contratos
# créditos de inteligência: custo interno de cada uso acima do limite do plano
CREDITOS = {"analises": 10, "concorrentes": 5, "possiveis": 2, "pecas": 3}
PACOTE_INTELIGENCIA = {"preco": 97.0, "creditos": 125, "validade_dias": 60,
                       "descricao": "+10 análises de edital e +5 análises de concorrentes (125 créditos, válidos por 60 dias)"}
EMPRESA_EXTRA_PRECO = 49.0


def codigo(conta):
    return ALIAS.get(conta.plano, conta.plano) if conta else "suspenso"


def em_teste(conta):
    """Teste do Profissional em andamento (a conta continua no FREE por baixo)."""
    return codigo(conta) == "free" and bool(conta.trial_fim) and datetime.utcnow() < conta.trial_fim


def efetivo(conta):
    return TRIAL_PLANO if em_teste(conta) else codigo(conta)


def dados_plano(conta):
    p = dict(PLANOS.get(efetivo(conta), PLANOS["suspenso"]))
    extras = empresas_extras_ativas(conta)
    if extras:
        p["empresas"] = p["empresas"] + extras
    return p


def teste_expirado(conta):
    """Compatibilidade: no modelo FREE o fim do teste não bloqueia nada (a conta volta ao FREE)."""
    return False


def teste_encerrado(conta):
    """Fez o teste do Profissional e ele já terminou."""
    return codigo(conta) == "free" and bool(conta.trial_fim) and datetime.utcnow() >= conta.trial_fim


def iniciar_teste(conta):
    if codigo(conta) != "free":
        raise ErroAPI("O teste do Profissional é para contas no plano Free.")
    if conta.trial_usado or conta.trial_fim:
        raise ErroAPI("Esta conta já usou o teste do Profissional. Assine para continuar com todos os recursos.", 409, "teste_usado")
    conta.trial_fim = datetime.utcnow() + timedelta(days=TRIAL_DIAS)
    conta.trial_usado = True
    from services import marketing
    marketing.evento_conta(conta, "trial_started", {"plano": TRIAL_PLANO})
    return conta.trial_fim


# ---------------------------------------------------------------- preços
def preco(plano, ciclo="mensal"):
    """Preço de tabela por ciclo. Anual = preço mensal x ANUAL_MESES_PAGOS (padrão: paga 10, leva 12)."""
    mensal = PLANOS[ALIAS.get(plano, plano)]["preco"] or 0
    if ciclo == "anual":
        return round(mensal * current_app.config["ANUAL_MESES_PAGOS"], 2)
    return float(mensal)


def preco_da_conta(conta, plano, ciclo="mensal"):
    """Valor cobrado desta conta: assinante da tabela antiga paga o menor entre o valor contratado e o de tabela."""
    tabela = preco(plano, ciclo)
    if conta.preco_contratado and ALIAS.get(plano, plano) == codigo(conta):
        antigo = conta.preco_contratado * (current_app.config["ANUAL_MESES_PAGOS"] if ciclo == "anual" else 1)
        return round(min(antigo, tabela) if tabela else antigo, 2)
    return tabela


def pacotes_ativos(conta):
    """Quantidade de pacotes extras de contratos pagos e dentro do prazo (com a mesma carência do plano)."""
    if not conta.pacotes_contratos or not conta.pacotes_ate or codigo(conta) not in PAGOS:
        return 0
    if datetime.utcnow() > conta.pacotes_ate + timedelta(days=current_app.config["CARENCIA_DIAS"]):
        return 0
    return int(conta.pacotes_contratos)


def empresas_extras_ativas(conta):
    if not conta or not conta.empresas_extras or not conta.empresas_extras_ate:
        return 0
    if not PLANOS.get(codigo(conta), {}).get("empresa_extra"):
        return 0
    if datetime.utcnow() > conta.empresas_extras_ate + timedelta(days=current_app.config["CARENCIA_DIAS"]):
        return 0
    return int(conta.empresas_extras)


def limite_contratos(conta):
    base = dados_plano(conta).get("contratos") or 0
    return int(base) + pacotes_ativos(conta) * PACOTE_CONTRATOS["contratos"]


def mrr_da_conta(conta):
    """Receita recorrente mensal que a conta representa hoje (0 se não estiver pagando)."""
    cod = codigo(conta)
    if cod not in PAGOS or conta.assinatura_status not in ("ativa",):
        return 0.0
    if cod == "enterprise" and not conta.preco_contratado:
        return 0.0
    base = preco_da_conta(conta, cod, conta.ciclo or "mensal") / (12 if conta.ciclo == "anual" else 1)
    if pacotes_ativos(conta) and conta.pacotes_status == "ativa":
        base += pacotes_ativos(conta) * PACOTE_CONTRATOS["preco"]
    if empresas_extras_ativas(conta) and conta.empresas_extras_status == "ativa":
        base += empresas_extras_ativas(conta) * EMPRESA_EXTRA_PRECO
    return round(base, 2)


def verificar_vencimento(conta):
    """Assinatura vencida além da carência: a conta volta ao FREE (nada é apagado). Planos definidos manualmente
    pelo administrador (sem pago_ate) nunca vencem por aqui."""
    if codigo(conta) not in PAGOS or not conta.pago_ate:
        return False
    limite = conta.pago_ate + timedelta(days=current_app.config["CARENCIA_DIAS"])
    if datetime.utcnow() > limite:
        conta.plano = "free"
        if conta.assinatura_status == "ativa":
            conta.assinatura_status = "inadimplente"
        db.session.commit()
        return True
    return False


# ---------------------------------------------------------------- créditos de inteligência
def creditos(conta):
    if not conta.creditos or not conta.creditos_validade or conta.creditos_validade < datetime.utcnow():
        return 0
    return int(conta.creditos)


def adicionar_creditos(conta, qtd, dias=None):
    agora = datetime.utcnow()
    saldo = creditos(conta)
    conta.creditos = saldo + int(qtd)
    base = conta.creditos_validade if conta.creditos_validade and conta.creditos_validade > agora else agora
    conta.creditos_validade = max(base, agora + timedelta(days=dias or PACOTE_INTELIGENCIA["validade_dias"]))


# ---------------------------------------------------------------- limites
NOMES_RECURSO = {"disputa": "a sala de disputa de lances (disponível a partir do plano Profissional)", "propostas": "a elaboração de propostas comerciais (disponível a partir do plano Profissional)",
                 "analises": "análises de edital", "concorrentes": "análises de concorrentes",
                 "possiveis": "avaliações de possíveis concorrentes",
                 "pecas": "peças com IA", "precos": "a inteligência de preços (disponível a partir do plano Profissional)",
                 "contratos": "a gestão de contratos (disponível a partir do plano Profissional)", "empresas": "empresas cadastradas",
                 "usuarios": "usuários"}
NOMES_SINGULAR = {"analises": "análise de edital", "concorrentes": "análise de concorrentes",
                  "possiveis": "avaliação de possíveis concorrentes", "pecas": "peça com IA"}
PROXIMO = {"free": "profissional", "essencial": "profissional", "profissional": "business", "business": "consultor",
           "consultor": "enterprise", "enterprise": "enterprise", "suspenso": "profissional"}


def _inicio_mes():
    agora = datetime.utcnow()
    return datetime(agora.year, agora.month, 1)


def uso_mes(conta, recurso):
    return UsoIA.query.filter(UsoIA.conta_id == conta.id, UsoIA.recurso == recurso, UsoIA.cobravel.is_(True),
                              UsoIA.criado_em >= _inicio_mes()).count()


def contar_usuarios(conta):
    from models import Convite, Usuario
    ativos = Usuario.query.filter_by(conta_id=conta.id).count()
    pendentes = Convite.query.filter(Convite.conta_id == conta.id, Convite.aceito_em.is_(None),
                                     Convite.expira_em > datetime.utcnow()).count()
    return ativos, pendentes


def _oferta(conta, recurso):
    """Mensagem de upgrade do limite: plano seguinte com o preço (e o pacote, quando cabe)."""
    prox = PROXIMO.get(efetivo(conta), "profissional")
    if prox == "enterprise":
        txt = "Fale com a gente sobre o plano Enterprise."
    else:
        p = PLANOS[prox]
        txt = f"{p['nome']} — R$ {p['preco']:,.0f}/mês. Continue →".replace(",", ".")
    if recurso in CREDITOS and codigo(conta) in PAGOS:
        txt += f" Ou contrate o Pacote de inteligência (R$ {PACOTE_INTELIGENCIA['preco']:.0f}) em Plano e conta."
    return prox, txt


def _armazenamento(conta):
    try:
        from services import armazenamento
        return armazenamento.resumo_conta(conta)
    except Exception:
        return None


def _fiscal_ok(conta):
    from services import fiscal
    return fiscal.completo(conta)


def resumo(conta):
    p = dados_plano(conta)
    custo = db.session.query(db.func.coalesce(db.func.sum(UsoIA.custo_usd), 0)).filter(
        UsoIA.conta_id == conta.id, UsoIA.criado_em >= _inicio_mes()).scalar()
    ativos, pendentes = contar_usuarios(conta)
    return {
        "codigo": efetivo(conta), "codigo_base": codigo(conta), **p,
        "dados_fiscais_ok": _fiscal_ok(conta),
        "em_teste": em_teste(conta), "teste_disponivel": codigo(conta) == "free" and not (conta.trial_usado or conta.trial_fim),
        "teste_encerrado": teste_encerrado(conta), "teste_expirado": False, "teste_dias": TRIAL_DIAS,
        "trial_fim": conta.trial_fim.isoformat() if conta.trial_fim else None,
        "preco_contratado": conta.preco_contratado,
        "armazenamento": _armazenamento(conta),
        "uso": {"analises": uso_mes(conta, "analises"), "concorrentes": uso_mes(conta, "concorrentes"),
                "possiveis": uso_mes(conta, "possiveis"), "pecas": uso_mes(conta, "pecas"),
                "empresas": Empresa.query.filter_by(conta_id=conta.id).count(), "contratos": contar_contratos(conta),
                "usuarios": ativos, "convites": pendentes},
        "limite_contratos": limite_contratos(conta),
        "creditos": {"saldo": creditos(conta), "validade": conta.creditos_validade.isoformat() if creditos(conta) else None,
                     "custo": CREDITOS, "pacote": PACOTE_INTELIGENCIA},
        "empresas_extras": {"ativas": empresas_extras_ativas(conta), "contratadas": conta.empresas_extras or 0,
                            "ate": conta.empresas_extras_ate.isoformat() if conta.empresas_extras_ate else None,
                            "status": conta.empresas_extras_status, "metodo": conta.empresas_extras_metodo,
                            "preco": EMPRESA_EXTRA_PRECO, "disponivel": bool(p.get("empresa_extra"))},
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


def limite(conta, chave):
    """Limites de volume do plano que não são mensais (radar_max, cofre_max, oportunidades_max). None = sem limite."""
    return dados_plano(conta).get(chave)


def exigir_volume(conta, chave, atual, rotulo):
    """Limites de volume do Free (radar, cofre, oportunidades)."""
    lim = limite(conta, chave)
    if lim is not None and atual >= lim:
        p = PLANOS["essencial"]
        raise ErroAPI(f"O plano Free permite até {lim} {rotulo}. {p['nome']} — R$ {p['preco']:.0f}/mês. Continue →", 402, "limite_atingido")


def exigir(conta, recurso):
    """Bloqueia se o plano não inclui o recurso ou se o limite do mês acabou (e não há créditos para cobrir)."""
    p = dados_plano(conta)
    lim = p.get(recurso)
    prox, oferta = _oferta(conta, recurso)
    if lim is False or (lim == 0 and not (recurso in CREDITOS and creditos(conta) >= CREDITOS[recurso])):
        raise ErroAPI(f"Seu plano não inclui {NOMES_RECURSO.get(recurso, recurso)}. {oferta}", 402, "fora_do_plano")
    if lim is True:
        return
    if recurso == "contratos":
        lim, atual = limite_contratos(conta), contar_contratos(conta)
        if atual >= lim:
            extra = (" Contrate um pacote de +10 contratos por R$ 169,90/mês em Plano e conta, ou faça upgrade."
                     if codigo(conta) in PAGOS else f" {oferta}")
            raise ErroAPI(f"Você atingiu o limite de {lim} contrato(s) do seu plano.{extra}", 402, "limite_contratos")
        return
    if recurso == "empresas":
        atual = Empresa.query.filter_by(conta_id=conta.id).count()
        if atual >= lim:
            extra = (f" Adicione empresas por R$ {EMPRESA_EXTRA_PRECO:.0f}/mês cada em Plano e conta." if p.get("empresa_extra") else "")
            raise ErroAPI(f"Seu plano permite até {lim} empresa(s).{extra} {oferta}", 402, "limite_atingido")
        return
    if recurso == "usuarios":
        ativos, pendentes = contar_usuarios(conta)
        if ativos + pendentes >= lim:
            raise ErroAPI(f"Seu plano permite até {lim} usuário(s). {oferta}", 402, "limite_atingido")
        return
    atual = uso_mes(conta, recurso)
    if atual >= lim:
        if recurso in CREDITOS and creditos(conta) >= CREDITOS[recurso]:
            return  # o excedente sai dos créditos do Pacote de inteligência (descontados no registro do uso)
        nome = NOMES_SINGULAR.get(recurso, NOMES_RECURSO.get(recurso, recurso)) if lim == 1 else NOMES_RECURSO.get(recurso, recurso)
        if codigo(conta) == "free" and not em_teste(conta):
            msg = f"Você utilizou {'sua' if lim == 1 else f'as {lim}'} {nome} gratuita{'s' if lim > 1 else ''} deste mês."
        else:
            msg = f"Você atingiu o limite de {lim} {nome} do seu plano neste mês."
        raise ErroAPI(f"{msg} {oferta}", 402, "limite_atingido")


def registrar_uso(conta, recurso, respostas, cobravel=True):
    """Grava uma linha por chamada de IA; só a primeira conta para o limite do plano. Uso acima do limite
    consome créditos do Pacote de inteligência."""
    if cobravel and recurso in CREDITOS:
        lim = dados_plano(conta).get(recurso)
        if isinstance(lim, int) and not isinstance(lim, bool) and uso_mes(conta, recurso) >= lim and creditos(conta):
            conta.creditos = max(0, creditos(conta) - CREDITOS[recurso])
    primeira = True
    for r in respostas:
        if r is None:
            continue
        db.session.add(UsoIA(conta_id=conta.id, recurso=recurso, cobravel=cobravel and primeira, modelo=r.modelo,
                             tokens_entrada=r.tokens_entrada, tokens_saida=r.tokens_saida, custo_usd=r.custo_usd))
        primeira = False
    if primeira and cobravel:  # nenhuma chamada registrada (ex.: falha antes) — ainda assim conta o uso
        db.session.add(UsoIA(conta_id=conta.id, recurso=recurso, cobravel=True, modelo="-"))


# ---------------------------------------------------------------- migração para a tabela 2026
def migrar_tabela_2026(app):
    """Uma vez por conta (Conta.tabela_precos vazio): códigos antigos → novos, mantendo o valor pago."""
    from models import Conta, Usuario
    try:
        pendentes = Conta.query.filter(Conta.tabela_precos.is_(None)).all()
    except Exception:
        db.session.rollback()
        return 0
    n = 0
    for c in pendentes:
        antigo = c.plano
        if antigo in MIGRACAO:
            pagante = bool(c.pago_ate or c.assinatura_status in ("ativa", "cancelada", "inadimplente"))
            c.plano = MIGRACAO[antigo]
            if pagante:
                c.preco_contratado = float(PRECOS_ANTIGOS[antigo])
        elif antigo == "trial":
            c.plano = "free"
            c.trial_usado = True
        elif antigo == "suspenso":
            c.plano = "free"
        c.tabela_precos = 2026
        n += 1
    # papéis na equipe: o primeiro usuário de cada conta é o dono
    for u in Usuario.query.filter(Usuario.papel.is_(None)).order_by(Usuario.id).all():
        primeiro = Usuario.query.filter_by(conta_id=u.conta_id).order_by(Usuario.id).first()
        u.papel = "dono" if primeiro and primeiro.id == u.id else "membro"
    db.session.commit()
    if n:
        app.logger.info("Tabela de preços 2026: %d conta(s) migrada(s)", n)
    return n
