"""Precificação automática da proposta pelas referências que o próprio edital manda usar.

Para cada item:
1. referência oficial — primeiro pelo código que o edital traz (SINAPI/SICRO, GGREM, registro ANVISA, CATMAT), depois
   pela descrição, sempre nas tabelas da fonte, UF, data-base e regime (desonerado ou não) exigidos;
2. o preço que vale para a compra pública (CMED: PMVG quando há CAP ou o edital manda, senão PF, na coluna da
   alíquota de ICMS do estado do órgão);
3. preços praticados (Compras.gov.br pelo CATMAT/CATSER) e o preço médio dos possíveis concorrentes nesse item;
4. uma SUGESTÃO de preço unitário, explicada, que o usuário só precisa aceitar (ou ajustar).

Regra da sugestão:
- tabela de CUSTO (SINAPI, SICRO, CCT, SIGTAP): custo = preço da tabela; preço = custo × (1 + BDI), limitado ao teto;
- tabela de PREÇO MÁXIMO (CMED, BPS) ou só o estimado do edital: preço = o menor entre o teto, a mediana praticada e
  o preço médio dos concorrentes (nunca acima do estimado nem do teto legal);
- critério "maior desconto": sugere o percentual de desconto sobre a tabela que o edital indicar.
"""
import logging
import re
import unicodedata

from services import tabelas

log = logging.getLogger(__name__)

TIPO_FONTE = {"sinapi": "custo", "sicro": "custo", "cct": "piso", "sigtap": "custo", "cmed": "teto", "bps": "teto",
              "outra": "custo"}
NOMES_FONTE = {"sinapi": "SINAPI", "sicro": "SICRO", "cct": "Convenção coletiva", "sigtap": "SIGTAP", "cmed": "CMED",
               "bps": "Banco de Preços em Saúde", "outra": "Tabela de referência", "mercado": "Compras.gov.br"}
MAX_CONSULTAS_MERCADO = 25


def _norm(t):
    t = unicodedata.normalize("NFKD", str(t or "").lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def fonte_de(texto):
    """'Tabela CMED (PMVG)' -> 'cmed'; 'SINAPI-SP' -> 'sinapi'; 'Painel de Preços' -> 'mercado'."""
    t = _norm(texto)
    for chave, fonte in (("sinapi", "sinapi"), ("sicro", "sicro"), ("cmed", "cmed"), ("pmvg", "cmed"), ("preco fabrica", "cmed"),
                         ("medicamento", "cmed"), ("bps", "bps"), ("banco de precos em saude", "bps"), ("sigtap", "sigtap"),
                         ("convencao", "cct"), ("cct", "cct"), ("acordo coletivo", "cct"), ("painel de precos", "mercado"),
                         ("compras.gov", "mercado"), ("comprasnet", "mercado"), ("catmat", "mercado"), ("catser", "mercado")):
        if chave in t:
            return fonte
    return None


_MEDICAMENTO = re.compile(r"\b(\d+[,.]?\d*\s?(mg|mcg|ml|ui)\b|comprimid|capsul|ampola|frasco-ampola|injetav|xarope|pomada|"
                          r"suspensao oral|solucao oral|colirio|medicament)")
_OBRA = re.compile(r"\b(m2|m3|m²|m³|concreto|alvenaria|pavimenta|escava|reboco|argamassa|revestimento|pintura|demoli|"
                   r"estaca|forma de madeira|armacao|aco ca)")


def fontes_provaveis(item):
    d = _norm(item.get("descricao"))
    if _MEDICAMENTO.search(d):
        return ["cmed", "bps"]
    if _OBRA.search(d) or _norm(item.get("unidade")) in ("m2", "m3", "m²", "m³"):
        return ["sinapi", "sicro"]
    if re.search(r"\b(posto|servente|vigilante|porteiro|recepcionista|motorista|encarregado)\b", d):
        return ["cct"]
    return None


def parametros_padrao(proposta, edital=None, empresa=None):
    """O que o edital pede como referência de preço, com valores iniciais editáveis pelo usuário."""
    cond = proposta.condicoes or {}
    atual = dict(proposta.parametros or {})
    refs = cond.get("referencias_preco") or []
    fontes = []
    for r in refs:
        f = fonte_de(f"{r.get('fonte', '')} {r.get('detalhe', '')}")
        if f and f not in fontes:
            fontes.append(f)
    uf = (atual.get("uf") or cond.get("uf_orgao") or (edital.uf if edital else None) or
          ((empresa.ufs or "")[:2] if empresa else "") or "").upper()[:2] or None
    texto_refs = _norm(" ".join(f"{r.get('fonte', '')} {r.get('detalhe', '')} {r.get('criterio_cmed', '')}" for r in refs))
    criterio = "PMVG" if "pmvg" in texto_refs else "PF" if re.search(r"\bpf\b|preco fabrica", texto_refs) else "auto"
    deson = None
    for r in refs:
        if r.get("desonerado") in (True, False):
            deson = r["desonerado"]
    if deson is None and "nao desonerad" in texto_refs:
        deson = False
    elif deson is None and "desonerad" in texto_refs:
        deson = True
    icms = cond.get("icms_aliquota")
    try:
        icms = float(icms) if icms not in (None, "") else None
    except (TypeError, ValueError):
        icms = None
    crit_julg = _norm(cond.get("criterio_julgamento"))
    par = {"uf": uf, "icms_pct": icms if icms is not None else tabelas.ICMS_UF.get(uf or ""), "criterio_cmed": criterio,
           "desonerado": deson, "fontes": fontes, "modo": "desconto" if "desconto" in crit_julg else "preco",
           "usar_concorrentes": True, "usar_mercado": True}
    for k, v in atual.items():  # o que o usuário já ajustou prevalece
        if v is not None and k in par:
            par[k] = v
    return par


def _unidade_compativel(a, b):
    a, b = _norm(a), _norm(b)
    if not a or not b:
        return None
    raiz = lambda u: re.sub(r"[^a-z0-9²³]", "", u)[:2]
    return raiz(a) == raiz(b)


_EMB = re.compile(r"\bx\s*(\d{1,4})\b(?!\s*(ml|g|mg|mcg|l|kg|cm|m)\b)")


def unidades_por_embalagem(apresentacao):
    """'500 MG COM CT BL AL PLAS TRANS X 10' -> 10; '100 UI/ML SUS INJ CT FA VD X 10 ML' -> None (10 ml é volume)."""
    t = _norm(apresentacao)
    achados = [int(m.group(1)) for m in _EMB.finditer(t)]
    return achados[-1] if achados else None


def _unidade_fracionada(unidade):
    u = _norm(unidade)
    return bool(re.match(r"(comp|cp|cap|dra|drag|un|ampola|amp|fr|frasco|fa|bisnaga|envelope|sache|seringa|tablete)", u))


def melhor_referencia(item, par):
    """Escolhe a referência oficial do item. Devolve dict pronto para item['referencias']['tabela'] ou None."""
    uf, deson = par.get("uf"), par.get("desonerado")
    exigidas = [f for f in (par.get("fontes") or []) if f != "mercado"]
    f_item = fonte_de(item.get("fonte_referencia") or "")
    fontes = [f_item] if f_item and f_item != "mercado" else exigidas or fontes_provaveis(item)
    codigo = (item.get("codigo_referencia") or "").strip()
    candidatos, por_codigo = [], False
    if codigo:
        candidatos = tabelas.por_codigo(codigo, uf, fontes, deson) or tabelas.por_codigo(codigo, None, fontes, deson)
        por_codigo = bool(candidatos)
    if not candidatos:
        candidatos = tabelas.buscar(item.get("descricao", ""), uf=uf, fontes=fontes, limite=6, desonerado=deson)
    fora_da_fonte = False
    if not candidatos and exigidas:
        candidatos = tabelas.buscar(item.get("descricao", ""), uf=uf, fontes=None, limite=6, desonerado=deson)
        fora_da_fonte = bool(candidatos)
    if not candidatos:
        return None

    def nota(c):
        u = _unidade_compativel(item.get("unidade"), c.get("unidade"))
        return (c.get("aderencia") or 0) + (0.15 if u else -0.1 if u is False else 0)
    ref = max(candidatos, key=nota)
    ap = tabelas.preco_aplicavel(ref, ref.get("fonte"), uf, par.get("icms_pct"),
                                 None if par.get("criterio_cmed") in (None, "auto") else par["criterio_cmed"])
    if not ap.get("valor"):
        return None
    preco_ref, conversao = ap["valor"], None
    if ref.get("fonte") == "cmed":
        n = unidades_por_embalagem(tabelas.extra(ref, "apresentacao") or ref.get("descricao"))
        if n and n > 1 and _unidade_fracionada(item.get("unidade")):
            preco_ref = round(ap["valor"] / n, 4)
            conversao = f"embalagem com {n}: {ap['valor']:.2f} ÷ {n}".replace(".", ",")
    ader = ref.get("aderencia") or 0
    unid = True if conversao else _unidade_compativel(item.get("unidade"), ref.get("unidade"))
    confianca = "alta" if por_codigo or (ader >= 0.85 and unid is not False) else "media" if ader >= 0.6 else "baixa"
    if fora_da_fonte:
        confianca = "baixa"
    motivo = ("código do edital" if por_codigo else f"descrição parecida ({round(ader * 100)}% dos termos)")
    if unid is False:
        motivo += "; unidade diferente, confira a conversão"
    if fora_da_fonte:
        motivo += f"; não achamos na fonte exigida ({', '.join(NOMES_FONTE.get(f, f) for f in exigidas)})"
    info = {}
    for rotulo, prefixos in (("fabricante", ("laboratorio", "fabricante", "marca")), ("registro", ("registro",)),
                             ("apresentacao", ("apresentacao",)), ("substancia", ("substancia", "principio")),
                             ("ean", ("ean",)), ("tarja", ("tarja",)), ("cap", ("cap",)), ("origem_preco", ("origem",))):
        v = tabelas.extra(ref, *prefixos)
        if v:
            info[rotulo] = v
    return {"fonte": ref.get("fonte"), "nome": ref.get("tabela"), "codigo": ref.get("codigo"), "descricao": ref.get("descricao"),
            "unidade": ref.get("unidade"), "preco": preco_ref, "preco_embalagem": ap["valor"] if conversao else None,
            "conversao": conversao, "coluna": ap.get("coluna"),
            "regra": "; ".join(x for x in (ap.get("regra"), conversao) if x) or None,
            "tipo": "teto" if ap.get("teto") or TIPO_FONTE.get(ref.get("fonte")) == "teto" else TIPO_FONTE.get(ref.get("fonte"), "custo"),
            "data_base": ref.get("data_base"), "uf": ref.get("uf"), "desonerado": ref.get("desonerado"),
            "confianca": confianca, "motivo": motivo, "info": info, "item_id": ref.get("id")}


def mercado(item, uf):
    from services.dados_publicos import estatisticas, pesquisa_precos
    codigo = "".join(ch for ch in str(item.get("catmat") or "") if ch.isdigit())
    if not codigo:
        return None
    tipo = item.get("tipo_catalogo") if item.get("tipo_catalogo") in ("material", "servico") else \
        ("servico" if re.search(r"servi|posto|mao de obra", _norm(item.get("descricao"))) else "material")
    try:
        amostras = pesquisa_precos(codigo, tipo, uf) or (pesquisa_precos(codigo, tipo, None) if uf else [])
    except Exception as e:
        log.info("Compras.gov indisponível para %s: %s", codigo, e)
        return None
    e = estatisticas([a["preco"] for a in amostras])
    if not e.get("n"):
        return None
    return {"codigo": codigo, "tipo": tipo, "mediana": e.get("mediana"), "faixa": e.get("faixa_competitiva"), "n": e["n"],
            "media": e.get("media")}


def concorrentes_do_item(item, edital):
    """Preço médio praticado pelos possíveis concorrentes neste item (da última avaliação do edital)."""
    pc = (edital.possiveis_concorrentes or {}) if edital else {}
    lista = pc.get("precos_itens") or []
    num = str(item.get("numero") or "").strip()
    for p in lista:
        if num and str(p.get("numero") or "").strip() == num and p.get("media"):
            return {"media": p["media"], "minimo": p.get("minimo"), "n": p.get("n"), "empresas": p.get("empresas")}
    from services.possiveis_concorrentes import semelhanca
    melhor = max(lista, key=lambda p: semelhanca(item.get("descricao"), p.get("descricao")), default=None)
    if melhor and melhor.get("media") and semelhanca(item.get("descricao"), melhor.get("descricao")) >= 0.6:
        return {"media": melhor["media"], "minimo": melhor.get("minimo"), "n": melhor.get("n"), "empresas": melhor.get("empresas")}
    return None


def sugerir(item, par, bdi_padrao):
    """Sugestão de preço (ou desconto) do item, com a explicação do cálculo."""
    refs = item.get("referencias") or {}
    tab, merc, conc = refs.get("tabela"), refs.get("mercado"), refs.get("concorrentes")
    est = item.get("valor_unitario_estimado")
    bdi = item.get("bdi") if item.get("bdi") is not None else bdi_padrao or 0
    tetos = []
    if est:
        tetos.append((float(est), "estimado do edital"))
    if tab and tab.get("tipo") == "teto" and tab.get("preco"):
        tetos.append((float(tab["preco"]), f"{NOMES_FONTE.get(tab.get('fonte'), 'tabela')} ({tab.get('coluna') or 'preço máximo'})"))
    teto = min(tetos, key=lambda x: x[0]) if tetos else None

    if par.get("modo") == "desconto":
        base = tab.get("preco") if tab else None
        if not base:
            return None
        alvos = [v for v in ((merc or {}).get("mediana") if par.get("usar_mercado") else None,
                             (conc or {}).get("media") if par.get("usar_concorrentes") else None) if v]
        alvo = min(alvos) if alvos else base
        desc = max(0.0, round((1 - alvo / base) * 100, 2))
        return {"desconto_pct": desc, "preco_unitario": round(base * (1 - desc / 100), 2), "custo_unitario": None,
                "origem": "desconto", "confianca": tab.get("confianca"),
                "explicacao": f"Desconto sobre {NOMES_FONTE.get(tab.get('fonte'), 'a tabela')} {tab.get('coluna') or ''} "
                              f"({base:,.2f})".replace(",", "X").replace(".", ",").replace("X", ".") +
                              (" para acompanhar o preço praticado." if alvos else ": sem preços praticados, desconto 0%.")}

    custo = item.get("custo_unitario")
    origem, partes = None, []
    if custo is not None:
        partes.append("custo informado")
    if custo is None and tab and tab.get("tipo") == "custo" and tab.get("preco"):
        custo = float(tab["preco"])
        partes.append(f"custo {NOMES_FONTE.get(tab.get('fonte'), 'da tabela')} {tab.get('codigo') or ''}".strip())
    if custo is not None:
        preco = round(float(custo) * (1 + float(bdi) / 100), 2)
        origem = "custo_bdi"
        partes.append(f"+ BDI {bdi:g}%".replace(".", ","))
    else:
        candidatos = []
        if teto:
            candidatos.append((teto[0], teto[1]))
        if merc and merc.get("mediana") and par.get("usar_mercado"):
            candidatos.append((float(merc["mediana"]), f"mediana praticada no Compras.gov.br ({merc.get('n')} compras)"))
        if conc and conc.get("media") and par.get("usar_concorrentes"):
            candidatos.append((float(conc["media"]), "preço médio dos possíveis concorrentes"))
        if not candidatos:
            return None
        preco, rotulo = min(candidatos, key=lambda x: x[0])
        preco = round(preco, 2)
        origem = "referencia"
        partes.append(rotulo)
    if teto and preco > teto[0]:
        partes.append(f"limitado ao teto ({teto[1]})")
        preco = round(teto[0], 2)
    confianca = (tab or {}).get("confianca") or ("media" if (merc or conc) else "baixa")
    if origem == "referencia" and not tab and not merc and not conc:
        confianca = "baixa"
    return {"preco_unitario": preco, "custo_unitario": round(float(custo), 4) if custo is not None else None,
            "origem": origem, "confianca": confianca, "explicacao": " ".join(partes)}


def precificar(proposta, edital=None, empresa=None, consultar_mercado=True):
    """Preenche referências e sugestões de todos os itens. Não altera o que o usuário já aceitou ou digitou."""
    par = parametros_padrao(proposta, edital, empresa)
    proposta.parametros = par
    itens, consultas = [], 0
    for it in proposta.itens or []:
        it = dict(it)
        refs = dict(it.get("referencias") or {})
        if not refs.get("tabela_manual"):
            refs["tabela"] = melhor_referencia(it, par)
        if consultar_mercado and par.get("usar_mercado") and it.get("catmat") and consultas < MAX_CONSULTAS_MERCADO:
            consultas += 1
            m = mercado(it, par.get("uf"))
            if m:
                refs["mercado"] = m
        c = concorrentes_do_item(it, edital)
        if c:
            refs["concorrentes"] = c
        it["referencias"] = refs
        tab = refs.get("tabela") or {}
        info = tab.get("info") or {}
        # dados do produto que o edital costuma pedir na proposta (medicamentos: fabricante, registro ANVISA)
        if tab.get("fonte") == "cmed":
            it.setdefault("fabricante", None)
            it.setdefault("registro", None)
            it["fabricante_sugerido"] = info.get("fabricante")
            it["registro_sugerido"] = info.get("registro")
        it["sugestao"] = sugerir(it, par, proposta.bdi_pct)
        itens.append(it)
    proposta.itens = itens
    return par


def aceitar(proposta, indices=None):
    """Aplica a sugestão aos itens (todos, ou os índices informados). Devolve quantos foram aceitos."""
    n = 0
    itens = []
    for i, it in enumerate(proposta.itens or []):
        it = dict(it)
        s = it.get("sugestao")
        if s and (indices is None or i in indices):
            if s.get("origem") == "custo_bdi":
                it["custo_unitario"] = s.get("custo_unitario")
                it["preco_manual"] = False
            else:
                it["preco_unitario"] = s.get("preco_unitario")
                it["preco_manual"] = True
            if s.get("desconto_pct") is not None:
                it["desconto_pct"] = s["desconto_pct"]
            if not it.get("fabricante") and it.get("fabricante_sugerido"):
                it["fabricante"] = it["fabricante_sugerido"]
            if not it.get("registro") and it.get("registro_sugerido"):
                it["registro"] = it["registro_sugerido"]
            it["aceito"] = True
            n += 1
        itens.append(it)
    proposta.itens = itens
    return n
