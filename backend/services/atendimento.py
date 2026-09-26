"""Assistente virtual de atendimento do Kasiski.

A base de conhecimento é montada a partir das fontes oficiais do próprio sistema (tabela de planos, preços,
limites, pacotes, serviços de advogado), então preço e condição comercial nunca ficam desatualizados nem são
inventados pela IA. Sem chave de IA, responde com regras simples a partir da mesma base.
"""
import re
import unicodedata

from flask import current_app

import planos
from services import llm
from services.prompts import TIPOS_PECA, _j

TRIAL_DIAS = 7

RECURSOS = [
    ("Radar de editais", "busca diária no PNCP com nota de aderência de 0 a 100 conforme o perfil da empresa (CNAEs e palavras-chave)."),
    ("Análise do edital", "resumo, checklist de habilitação contra o cofre de documentos, cláusulas restritivas, riscos e recomendação de participar, com a página de cada ponto; verificação cruzada por uma segunda IA; roda em segundo plano (editais longos levam de 2 a 6 minutos)."),
    ("Cofre de documentos", "certidões e atestados com controle de validade e alerta antes de vencer."),
    ("Agenda de prazos", "prazos da Lei 14.133 (esclarecimento, impugnação, recurso) contados em dias úteis, mais os prazos de gestão dos contratos."),
    ("Concorrentes", "dossiê público (Receita, sanções TCU/CGU, contratos no PNCP), dossiê completo (atas e decisões no PNCP, acervo de documentos de outros certames, inabilitações anteriores, atestados, índices, pontos de ataque) e análise da habilitação/proposta do concorrente com sugestões de recurso."),
    ("Gerador de peças", "minutas pela IA de esclarecimento, impugnação, intenção de recorrer, recurso, contrarrazões, reequilíbrio, cobrança de pagamento em atraso e defesa prévia."),
    ("Elaboração com advogado", "serviço pago à parte: a peça elaborada ou revisada por advogado, com pagamento online pelo Mercado Pago (Pix, boleto ou cartão em até 3x); menu Peças > Elaboração com advogado."),
    ("Preços e propostas", "pesquisas de preço no Compras.gov.br (CATMAT/CATSER), tabelas oficiais de referência (SINAPI, SICRO, CMED, SIGTAP, convenções coletivas) e, nos planos Avançado e Consultor, a proposta comercial com IA: lê as regras da proposta no edital, forma o preço com custo, BDI (fórmula do TCU) e tributos, checa exequibilidade e gera a minuta em Word."),
    ("Gestão de contratos", "envie o PDF do contrato e a IA preenche vigência, garantia, reajuste, medição, faturamento e obrigações; a agenda avisa prorrogação (120 e 60 dias antes), garantia, reajuste e rotinas mensais, com e-mail diário."),
    ("Empresas", "cadastro por CNPJ com CNAEs, segmentos e palavras-chave do radar preenchidos automaticamente pela Receita."),
]

PLATAFORMA = [
    "Cadastro: em 'Testar grátis' informe nome, e-mail e senha; confirme o e-mail com o código de 6 números enviado (vale 15 minutos; dá para reenviar a cada 60 segundos). Depois cadastre a empresa pelo CNPJ.",
    "Esqueceu a senha: ainda não há recuperação automática; peça ao atendimento humano.",
    "Login bloqueado: após 5 senhas erradas seguidas o acesso fica pausado por 15 minutos.",
    "Pagamento: em 'Plano e conta', escolha o plano, mensal ou anual (anual = 10 mensalidades), e a forma: cartão com renovação automática ou Pix/boleto/cartão avulso por um ciclo. O plano é liberado assim que o Mercado Pago confirma.",
    "Cancelar: em 'Plano e conta', cancele a renovação automática; o acesso segue até o fim do período pago. Pagamentos por Pix não renovam sozinhos.",
    "Atraso de pagamento: após o vencimento há carência; depois a conta fica suspensa, mas os dados continuam salvos.",
    "Pacote de contratos extras: +10 contratos por R$ 169,90/mês, em 'Plano e conta', a partir do plano Profissional.",
    "O Kasiski não substitui advogado: as peças são minutas para revisar antes de protocolar.",
    "Fontes: PNCP, Receita Federal (BrasilAPI), TCU, Portal da Transparência (CEIS/CNEP) e Compras.gov.br.",
]


def _limite(v, sing, plur):
    if v is True:
        return f"{plur} ilimitados"
    if not v:
        return f"sem {plur}"
    return f"{v} {sing if v == 1 else plur}"


def brl(v):
    """Valor em reais no padrão brasileiro: 1290 -> 'R$ 1.290,00'."""
    return "R$ " + f"{float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def base_conhecimento():
    cfg = current_app.config
    linhas = ["PLANOS (preço mensal; anual = preço mensal x %d):" % cfg["ANUAL_MESES_PAGOS"]]
    for k in ("trial", "essencial", "profissional", "avancado", "consultor"):
        p = planos.PLANOS[k]
        preco = "grátis por %d dias, sem cartão" % TRIAL_DIAS if k == "trial" else brl(p['preco']) + "/mês"
        itens = [_limite(p["empresas"], "empresa", "empresas"), _limite(p["analises"], "análise de edital/mês", "análises de edital/mês"),
                 _limite(p["concorrentes"], "análise de concorrente/mês", "análises de concorrente/mês"),
                 _limite(p.get("possiveis"), "avaliação de possíveis concorrentes/mês", "avaliações de possíveis concorrentes/mês"),
                 "gerador de peças" if p["pecas"] else "sem gerador de peças",
                 "inteligência de preços" if p["precos"] else "sem inteligência de preços",
                 "proposta comercial com IA" if p.get("propostas") else "sem proposta comercial com IA",
                 _limite(p.get("contratos"), "contrato em gestão", "contratos em gestão"),
                 "relatórios com a marca do escritório" if p.get("marca") else ""]
        linhas.append(f"- {p['nome']}: {preco}; " + "; ".join(i for i in itens if i))
    pk = planos.PACOTE_CONTRATOS
    linhas.append(f"- Pacote extra: +{pk['contratos']} contratos por {brl(pk['preco'])}/mês")
    linhas.append("SERVIÇO DE ADVOGADO (elaboração ou revisão, pagamento único):")
    for k, nome in TIPOS_PECA.items():
        v = cfg["PRECO_REVISAO"].get(k)
        if v:
            linhas.append(f"- {nome}: {brl(v)}")
    linhas.append("FUNCIONALIDADES:")
    linhas += [f"- {n}: {d}" for n, d in RECURSOS]
    linhas.append("USO DA PLATAFORMA:")
    linhas += [f"- {x}" for x in PLATAFORMA]
    return "\n".join(linhas)


SISTEMA = """Você é o assistente virtual de atendimento do KASISKI Public Market Intelligence, plataforma de inteligência
para licitações (Lei 14.133/2021). Responda em português do Brasil, de forma curta (até 6 frases), cordial e objetiva.
Regras:
- Use SOMENTE a BASE OFICIAL abaixo para preços, planos, limites e condições. Se algo não estiver na base, diga que não
  tem essa informação e ofereça o atendimento humano. Nunca invente preço, prazo, desconto ou funcionalidade.
- Dúvidas jurídicas de licitação: explique o conceito em linhas gerais, sem parecer jurídico sobre o caso concreto, e
  sugira a análise do edital no Kasiski ou o serviço de Elaboração com advogado.
- Ofereça atendimento humano quando: o usuário pedir, houver problema de pagamento/cobrança, erro que você não resolve,
  pedido de reembolso, recuperação de senha, ou a pergunta fugir da base.
- Não peça senha, número de cartão ou documentos pessoais.
- Para indicar telas, use os caminhos entre crases, ex.: `Plano e conta`, `Peças > Elaboração com advogado`.
Responda SOMENTE com JSON: {"resposta": "texto (pode usar **negrito** e quebras de linha)",
 "encaminhar_para_humano": false, "sugestoes": ["até 3 perguntas curtas de continuação"]}"""


def responder(historico, pergunta, contexto_usuario=None):
    """historico: [{'papel': 'usuario'|'assistente', 'texto': ...}] (últimas mensagens)."""
    conversa = "\n".join(f"{'Usuário' if m['papel'] == 'usuario' else 'Assistente'}: {m['texto']}" for m in historico[-10:])
    usuario = (f"BASE OFICIAL DO KASISKI:\n{base_conhecimento()}\n\n"
               f"USUÁRIO: {_j(contexto_usuario) if contexto_usuario else 'visitante sem login'}\n\n"
               f"CONVERSA ATÉ AGORA:\n{conversa or '(início)'}\n\nNOVA PERGUNTA: {pergunta}")
    demo = resposta_por_regras(pergunta, contexto_usuario)
    r = llm.chamar("barata", SISTEMA, usuario, max_tokens=900, demo=demo)
    try:
        d = llm.extrair_json(r.texto)
    except Exception:
        d = {"resposta": r.texto.strip()[:2000]}
    resposta = str(d.get("resposta") or "").strip() or demo["resposta"]
    sugestoes = [str(x)[:80] for x in (d.get("sugestoes") or []) if str(x).strip()][:3]
    return {"resposta": resposta[:3000], "encaminhar": bool(d.get("encaminhar_para_humano")), "sugestoes": sugestoes}, r


# ---------------------------------------------------------------- respostas sem IA (modo demonstração / queda da IA)
def _n(t):
    return "".join(c for c in unicodedata.normalize("NFKD", (t or "").lower()) if not unicodedata.combining(c))


def resposta_por_regras(pergunta, ctx=None):
    q = _n(pergunta)
    P = planos.PLANOS

    def preco(k):
        return brl(P[k]['preco'])
    if re.search(r"atendente|humano|pessoa|atendimento|falar com|suporte humano|reembolso|estorno", q):
        return {"resposta": "Claro! Vou encaminhar sua conversa para a nossa equipe. Toque em **Falar com atendimento** e deixe seu contato: "
                            "a conversa vai junto, para você não precisar repetir.", "encaminhar_para_humano": True, "sugestoes": []}
    if re.search(r"plano|preco|valor|quanto custa|assinatura|mensal|anual|pagar|pagamento", q):
        return {"resposta": f"Planos mensais: **Essencial** {preco('essencial')}, **Profissional** {preco('profissional')}, "
                            f"**Avançado** {preco('avancado')} (com proposta comercial com IA) e **Consultor** {preco('consultor')}. "
                            f"No anual você paga {current_app.config['ANUAL_MESES_PAGOS']} mensalidades e leva 12. Dá para começar com o **teste grátis de {TRIAL_DIAS} dias**, sem cartão. "
                            "A assinatura é feita em `Plano e conta`, com cartão recorrente ou Pix.",
                "sugestoes": ["O que cada plano inclui?", "Como funciona o teste grátis?", "Posso cancelar quando quiser?"]}
    if re.search(r"teste|gratis|trial|periodo gratuito", q):
        t = P["trial"]
        return {"resposta": f"O teste grátis dura **{TRIAL_DIAS} dias**, sem cartão, com {t['analises']} análises de edital, "
                            f"{t['concorrentes']} análise de concorrente, gerador de peças, inteligência de preços e {t['contratos']} contrato em gestão. "
                            "É só clicar em **Testar grátis**, confirmar o e-mail com o código e cadastrar a empresa pelo CNPJ.",
                "sugestoes": ["Quais são os planos?", "Como cadastro minha empresa?"]}
    if re.search(r"cancel", q):
        return {"resposta": "Você cancela em `Plano e conta` > **Cancelar renovação automática**. O acesso continua até o fim do período já pago. "
                            "Pagamentos por Pix não renovam sozinhos.", "sugestoes": ["Falar com atendimento"]}
    if re.search(r"advogad|revis|elabora", q):
        return {"resposta": "Em `Peças > Elaboração com advogado` você contrata a peça feita ou revisada por advogado, com pagamento online "
                            f"(Pix, boleto ou cartão em até 3x). Exemplos: recurso {brl(current_app.config['PRECO_REVISAO']['recurso'])}, "
                            f"impugnação {brl(current_app.config['PRECO_REVISAO']['impugnacao'])}.",
                "sugestoes": ["Como funciona o gerador de peças?"]}
    if re.search(r"contrato|vigencia|garantia|medicao|faturamento", q):
        return {"resposta": "Na **Gestão de contratos** você envia o PDF do contrato e a IA preenche vigência, garantia, reajuste, medição e faturamento. "
                            "O Kasiski avisa a prorrogação 120 e 60 dias antes, a renovação da garantia e as rotinas mensais, com e-mail diário. "
                            f"Limites: Profissional {P['profissional']['contratos']}, Avançado {P['avancado']['contratos']}, Consultor {P['consultor']['contratos']} contratos "
                            f"(+{planos.PACOTE_CONTRATOS['contratos']} por {brl(planos.PACOTE_CONTRATOS['preco'])}/mês).", "sugestoes": ["Quais são os planos?"]}
    if re.search(r"proposta|bdi|preco praticado|sinapi|cotacao", q):
        return {"resposta": "Em `Preços e propostas` você pesquisa preços praticados e consulta tabelas oficiais (SINAPI, CMED, convenções coletivas). "
                            "Nos planos **Avançado** e **Consultor**, a IA lê as regras da proposta no edital, calcula o preço com BDI e tributos, "
                            "checa a exequibilidade e gera a minuta em Word.", "sugestoes": ["Quanto custa o plano Avançado?"]}
    if re.search(r"concorrent|dossie|inabilit", q):
        return {"resposta": "Em `Concorrentes` você consulta o CNPJ e monta o **dossiê completo**: dados públicos, sanções, atas e decisões no PNCP, "
                            "documentos de outros certames e inabilitações anteriores. Nas análises da habilitação ou da proposta, a IA usa esse histórico para sugerir recursos.",
                "sugestoes": ["Como analiso a habilitação de um concorrente?"]}
    if re.search(r"senha|login|entrar|acesso|codigo|verifica|bloque", q):
        return {"resposta": "Se o código de verificação não chegou, confira o spam e use **Reenviar código** (a cada 60 segundos). "
                            "Após 5 senhas erradas o acesso pausa por 15 minutos. Para recuperar a senha, fale com o atendimento.",
                "encaminhar_para_humano": "senha" in q and "esquec" in q, "sugestoes": ["Falar com atendimento"]}
    if re.search(r"edital|analis|radar|pncp|habilita", q):
        return {"resposta": "O **Radar** busca editais no PNCP todo dia conforme o perfil da sua empresa. Em `Editais`, a **análise** confere a habilitação "
                            "contra o seu cofre de documentos, aponta cláusulas restritivas e riscos e recomenda se vale participar. Editais longos levam de 2 a 6 minutos.",
                "sugestoes": ["Quantas análises cada plano tem?", "Como funciona o cofre de documentos?"]}
    if re.search(r"o que e|conhecer|como funciona|kasiski|beneficio", q):
        return {"resposta": "O **KASISKI** é uma plataforma de inteligência para o mercado público: encontra editais no PNCP, analisa o edital e a sua "
                            "habilitação, investiga concorrentes, gera peças (impugnação, recurso), forma o preço da proposta e faz a gestão dos contratos. "
                            "Cada conclusão da IA é conferida por um segundo modelo.",
                "sugestoes": ["Quais são os planos?", "Como funciona o teste grátis?", "Como funciona a análise do edital?"]}
    return {"resposta": "Posso ajudar com planos e assinatura, funcionalidades (radar, análise de edital, concorrentes, peças, propostas e contratos), "
                        "cadastro e acesso. Se preferir, encaminho você para a nossa equipe.",
            "sugestoes": ["Quais são os planos?", "Como funciona o Kasiski?", "Falar com atendimento"]}
