"""Sala de disputa: estratégia de lances e cálculo do próximo lance.

O Kasiski não envia lances aos portais: calcula o próximo lance pela estratégia definida, respeita o piso e os
intervalos entre lances e registra o que aconteceu. O lance é dado pelo usuário no portal (Compras.gov.br, BEC etc.).

Regras gerais do pregão eletrônico (Lei 14.133/2021, Decreto 10.024/2019 e IN SEGES/ME 73/2022) — o edital manda:
- modo ABERTO: etapa de lances de 10 minutos, prorrogada por 2 minutos sempre que houver lance nos 2 minutos finais;
- modo ABERTO E FECHADO: 15 minutos, aviso de fechamento iminente e encerramento aleatório em até 10 minutos;
  depois, o melhor lance e os até 10% acima dele podem dar um lance final e fechado em até 5 minutos;
- o edital pode fixar intervalo mínimo de diferença de valores entre lances; o Compras.gov.br limita a frequência
  de lances do mesmo licitante (padrão aqui: 20 s entre os seus lances e 3 s em relação ao último lance registrado).
"""
import math
from datetime import datetime

ESTRATEGIAS = {
    "conservadora": {"nome": "Conservadora", "decremento": 0.3, "descricao": "Cobre por pouco, preserva margem. Bom quando há muitos concorrentes e o piso é apertado."},
    "moderada": {"nome": "Moderada", "decremento": 1.0, "descricao": "Equilíbrio entre margem e chance de liderar."},
    "agressiva": {"nome": "Agressiva", "decremento": 2.5, "descricao": "Reduções maiores para desestimular concorrentes. Chega ao piso mais rápido."},
    "personalizada": {"nome": "Personalizada", "decremento": None, "descricao": "Você define o decremento em % ou em R$."},
}
MODOS = {
    "aberto": {"nome": "Aberto", "regra": "10 min de lances, prorrogação de 2 min a cada lance nos 2 min finais."},
    "aberto_fechado": {"nome": "Aberto e fechado", "regra": "15 min de lances + encerramento aleatório em até 10 min; depois, lance final e fechado para quem estiver até 10% do melhor."},
    "fechado_aberto": {"nome": "Fechado e aberto", "regra": "Propostas fechadas; os melhores (até 10% ou os 3 melhores) disputam em lances abertos."},
}
PORTAIS = {
    "comprasgov": ("Compras.gov.br", "https://www.gov.br/compras/pt-br"),
    "bec": ("BEC-SP", "https://www.bec.sp.gov.br/"),
    "licitacoes_e": ("Licitações-e (Banco do Brasil)", "https://www.licitacoes-e.com.br/"),
    "bll": ("BLL Compras", "https://bllcompras.com/"),
    "portal_compras_publicas": ("Portal de Compras Públicas", "https://www.portaldecompraspublicas.com.br/"),
    "outro": ("Outro portal", ""),
}


def _arred(v, criterio):
    """Menor preço: arredonda para baixo (centavo); maior desconto: para cima (centésimo de ponto percentual)."""
    return math.floor(v * 100 + 1e-9) / 100 if criterio == "menor_preco" else math.ceil(v * 100 - 1e-9) / 100


def passo(d, base):
    """Quanto mudar em relação ao lance a cobrir."""
    if d.estrategia in ESTRATEGIAS and d.estrategia != "personalizada":
        dec, tipo = ESTRATEGIAS[d.estrategia]["decremento"], "percentual"
    else:
        dec, tipo = (d.decremento or 1.0), (d.decremento_tipo or "percentual")
    if d.criterio == "maior_desconto":  # desconto em pontos percentuais
        p = dec if tipo == "valor" else max(0.01, base * dec / 100)
    else:
        p = dec if tipo == "valor" else base * dec / 100
    if d.diferenca_minima:
        p = max(p, d.diferenca_minima)
    return max(p, 0.01)


def segundos_desde(t):
    return (datetime.utcnow() - t).total_seconds() if t else None


def sugerir(d):
    """Próximo lance e situação: {situacao, proximo, espera_s, margem_pct, lances_ate_piso, mensagem}."""
    menor = d.criterio == "menor_preco"
    melhor, meu, piso = d.melhor_lance, d.meu_ultimo, d.preco_piso
    base = melhor if melhor is not None else (meu if meu is not None else d.lance_inicial)
    out = {"situacao": "aguardando", "proximo": None, "espera_s": 0, "margem_pct": None, "lances_ate_piso": None, "mensagem": ""}
    if base is None:
        out["mensagem"] = "Informe o lance inicial (proposta) ou o melhor lance do portal para calcular o próximo."
        return out
    # esperar o intervalo entre os próprios lances e o intervalo em relação ao último lance visto
    esp = []
    s_meu = segundos_desde(d.meu_ultimo_em)
    if s_meu is not None:
        esp.append((d.intervalo_proprio_s or 0) - s_meu)
    s_out = segundos_desde(d.melhor_em)
    if s_out is not None:
        esp.append((d.intervalo_outros_s or 0) - s_out)
    out["espera_s"] = max(0, math.ceil(max(esp))) if esp else 0
    if melhor is None and meu is None:
        out.update(situacao="aguardando", mensagem="Sua proposta está registrada. Assim que abrir a etapa de lances, registre aqui o melhor lance do portal.")
        out["margem_pct"] = _margem(d.lance_inicial, piso, menor)
        return out
    lider = meu is not None and melhor is not None and (meu <= melhor if menor else meu >= melhor)
    if lider:
        out.update(situacao="lider", mensagem="Você está com o melhor lance. Não dê lance contra você mesmo: aguarde.")
        out["margem_pct"] = _margem(meu, piso, menor)
        return out
    p = passo(d, base)
    alvo = _arred(base - p if menor else base + p, d.criterio)
    if piso is not None:
        if (menor and base <= piso) or (not menor and base >= piso):
            out.update(situacao="parar", mensagem="O melhor lance já passou do seu piso. Pela estratégia, pare de cobrir.")
            out["margem_pct"] = _margem(base, piso, menor)
            return out
        if (menor and alvo < piso) or (not menor and alvo > piso):
            alvo = piso
            out.update(situacao="no_piso", mensagem="Próximo lance chega ao piso: é o último lance da estratégia.")
    if out["situacao"] == "aguardando":
        out["situacao"] = "cobrir"
        out["mensagem"] = "Você foi superado. Próximo lance pela estratégia:" if melhor is not None else "Lance de abertura pela estratégia:"
    out["proximo"] = alvo
    out["margem_pct"] = _margem(alvo, piso, menor)
    if piso is not None and p > 0:
        dist = (alvo - piso) if menor else (piso - alvo)
        out["lances_ate_piso"] = max(0, int(dist // p))
    return out


def _margem(valor, piso, menor):
    if valor is None or piso is None or not piso:
        return None
    return round(((valor - piso) / piso * 100) if menor else (piso - valor), 2)


def registrar_lance(d, valor, tipo, obs=None):
    agora = datetime.utcnow()
    log = list(d.lances or [])
    log.append({"em": agora.isoformat(timespec="seconds"), "valor": valor, "tipo": tipo, "obs": (obs or "")[:200] or None})
    d.lances = log[-500:]
    if tipo == "meu":
        d.meu_ultimo, d.meu_ultimo_em = valor, agora
        if d.melhor_lance is None or (valor < d.melhor_lance if d.criterio == "menor_preco" else valor > d.melhor_lance):
            d.melhor_lance, d.melhor_em = valor, agora
    else:
        d.melhor_lance, d.melhor_em = valor, agora
    if d.status == "preparando":
        d.status = "em_disputa"


def piso_da_proposta(prop):
    """Ponto de equilíbrio da proposta comercial: custo total dividido por (1 - tributos). Abaixo disso, prejuízo."""
    itens = prop.itens or []
    custo = sum(float(i.get("custo_unitario") or 0) * float(i.get("quantidade") or 0) for i in itens)
    preco = sum(float(i.get("preco_unitario") or 0) * float(i.get("quantidade") or 0) for i in itens)
    trib = float(prop.tributos_pct or 0) / 100
    piso = round(custo / (1 - trib), 2) if custo and trib < 1 else None
    return {"custo": round(custo, 2) or None, "preco": round(preco, 2) or None, "piso": piso}


def to_dict(d):
    return {
        "id": d.id, "empresa_id": d.empresa_id, "edital_id": d.edital_id, "item": d.item, "descricao": d.descricao,
        "portal": d.portal, "portal_nome": PORTAIS.get(d.portal, PORTAIS["outro"])[0], "portal_url": PORTAIS.get(d.portal, PORTAIS["outro"])[1],
        "modo": d.modo, "modo_regra": MODOS.get(d.modo, {}).get("regra"), "criterio": d.criterio,
        "valor_referencia": d.valor_referencia, "lance_inicial": d.lance_inicial, "preco_piso": d.preco_piso,
        "estrategia": d.estrategia, "decremento_tipo": d.decremento_tipo, "decremento": d.decremento,
        "diferenca_minima": d.diferenca_minima, "intervalo_proprio_s": d.intervalo_proprio_s, "intervalo_outros_s": d.intervalo_outros_s,
        "status": d.status, "resultado": d.resultado, "posicao": d.posicao, "melhor_lance": d.melhor_lance,
        "meu_ultimo": d.meu_ultimo, "lances": (d.lances or [])[-60:], "notas": d.notas, "analise": d.analise,
        "sugestao": sugerir(d), "agora": datetime.utcnow().isoformat(timespec="seconds"),
    }
