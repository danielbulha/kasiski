"""Cronograma da licitação: sessão pública, janela de envio de propostas/documentos e prazos de impugnação/esclarecimento.

Por que existe: o PNCP tem só "dataAberturaProposta" (início do envio de propostas — muitas vezes a publicação) e
"dataEncerramentoProposta" (fim do envio, em geral o momento da sessão), e o órgão às vezes cadastra errado.
O edital é a fonte que vale. Aqui juntamos as três leituras — o que o usuário informou, o que a IA leu no edital,
o que uma leitura determinística do texto encontrou — com o que está no PNCP, escolhemos a data da sessão e apontamos
divergências para o usuário conferir.

Prioridade para cada data: usuário > IA (edital) > leitura do texto (edital) > PNCP.
"""
import re
import unicodedata
from datetime import datetime

EVENTOS = {
    "sessao": "Sessão pública",
    "inicio_propostas": "Início do envio de propostas e documentos",
    "fim_propostas": "Fim do envio de propostas e documentos",
    "impugnacao": "Limite para impugnação",
    "esclarecimento": "Limite para pedido de esclarecimento",
}
FONTES = {"usuario": "informada por você", "edital_ia": "lida no edital pela IA", "edital_texto": "encontrada no texto do edital",
          "pncp": "vinda do cadastro do órgão no PNCP"}

MESES = {"janeiro": 1, "fevereiro": 2, "marco": 3, "abril": 4, "maio": 5, "junho": 6, "julho": 7, "agosto": 8,
         "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12}
_HORA = r"(?:\s*(?:,|-|–|às|as|horário:?|horario:?|hora:?)?\s*(\d{1,2})\s*(?:h|:|hs|horas)\s*(\d{2})?)?"
RE_HORA_ANTES = re.compile(r"(\d{1,2})\s*(?:h|:)\s*(\d{2})?\s*(?:hs|horas|min)?\s*(?:\([^)]{0,40}\))?\s*(?:do dia|de)\s*$")
RE_DATA_NUM = re.compile(r"\b(\d{1,2})[/.](\d{1,2})[/.](\d{4})\b" + _HORA, re.I)
RE_DATA_EXT = re.compile(r"\b(\d{1,2})º?\s+de\s+([a-zç]+)\s+de\s+(\d{4})\b" + _HORA, re.I)
RE_PAG = re.compile(r"\[p[aá]g\.\s*(\d+)\]")

# palavras-chave que antecedem a data de cada evento (texto já sem acento e em minúsculas)
CHAVES = {
    "sessao": [r"abertura da sessao", r"sessao publica", r"inicio da sessao", r"inicio da disputa", r"abertura da disputa",
               r"disputa de lances", r"fase de lances", r"realizacao do pregao", r"realizacao da sessao",
               r"data (?:da|de) abertura", r"abertura do certame", r"abertura das propostas", r"sessao de disputa",
               r"data do certame", r"data da sessao", r"horario da sessao"],
    "inicio_propostas": [r"inicio (?:do|para o|de) (?:recebimento|envio|cadastr\w*|acolhimento)", r"inicio das propostas",
                         r"(?:recebimento|envio|cadastr\w*|acolhimento) das propostas[^;]{0,60}?a partir d",
                         r"propostas[^.;]{0,30}a partir d", r"inicio do prazo (?:para|de) (?:envio|cadastr\w*)"],
    "fim_propostas": [r"(?:fim|termino|encerramento|limite) (?:do|para o|de) (?:recebimento|envio|cadastr\w*|acolhimento)",
                      r"(?:recebimento|envio|cadastr\w*) das propostas[^;]{0,90}?\bate\b", r"propostas[^.;]{0,30}ate o dia"],
    "impugnacao": [r"impugna\w*[^.;]{0,80}ate", r"prazo (?:para|de) impugna\w*", r"limite (?:para|de) impugna\w*"],
    "esclarecimento": [r"esclarecimento\w*[^.;]{0,80}ate", r"prazo (?:para|de) (?:pedido de )?esclarecimento",
                       r"limite (?:para|de) (?:pedido de )?esclarecimento"],
}
_CHAVES_RE = {ev: [re.compile(c) for c in lista] for ev, lista in CHAVES.items()}
# datas de normas, assinatura e publicação não são do cronograma
_IGNORAR = re.compile(r"(?:lei|decreto|portaria|instrucao normativa|resolucao|lei complementar|in)\s*(?:n[ºo°.]*\s*)?[\d.]*\s*,?\s*de\s*$|"
                      r"(?:publicad\w*|assinad\w*|datad\w*|emitid\w*|em)\s*$")


def _norm(t):
    """Minúsculas sem acento, preservando o tamanho (cada posição continua batendo com o texto original)."""
    return "".join((unicodedata.normalize("NFD", c)[0] if c.isalpha() else c) for c in (t or "").lower())


def _iso(d):
    return d.isoformat(timespec="minutes") if d else None


def _para_data(v):
    if not v:
        return None
    if isinstance(v, datetime):
        return v
    try:
        return datetime.fromisoformat(str(v).replace("Z", "")[:16])
    except ValueError:
        try:
            return datetime.fromisoformat(str(v)[:10])
        except ValueError:
            return None


def _montar(dia, mes, ano, h, m):
    try:
        ano = int(ano)
        if not (datetime.utcnow().year - 2 <= ano <= datetime.utcnow().year + 3):
            return None
        hora = int(h) if h else 0
        return datetime(ano, int(mes), int(dia), hora if hora < 24 else 0, int(m) if m and int(m) < 60 else 0)
    except (ValueError, TypeError):
        return None


def _datas(norm):
    for rx, conv in ((RE_DATA_NUM, lambda g: g), (RE_DATA_EXT, lambda g: MESES.get(g))):
        for r in rx.finditer(norm):
            h, m = r.group(4), r.group(5)
            if not h:  # hora antes da data: "às 09h00 do dia 19/10/2026"
                a = RE_HORA_ANTES.search(norm[max(0, r.start() - 40):r.start()])
                if a:
                    h, m = a.group(1), a.group(2)
            mes = conv(r.group(2))
            d = _montar(r.group(1), mes, r.group(3), h, m) if mes else None
            if d:
                yield r.start(), r.end(), d, bool(h)


def do_texto(texto, limite=120000):
    """Leitura determinística: para cada evento, a primeira data do texto precedida de perto por uma palavra-chave.
    Devolve {evento: {"data", "pagina", "trecho"}}. Olha o começo do edital (preâmbulo/cronograma), onde as datas ficam."""
    if not texto:
        return {}
    bruto = texto[:limite]
    norm = _norm(bruto)
    if len(norm) != len(bruto):  # algum caractere especial mudou o tamanho: trabalha só no normalizado
        bruto = norm
    achados = {}
    for ini, fim, data, tem_hora in sorted(_datas(norm), key=lambda x: x[0]):
        antes = norm[max(0, ini - 160):ini]
        if _IGNORAR.search(antes[-40:]):
            continue
        melhor = None
        for ev, regs in _CHAVES_RE.items():
            for rg in regs:
                for m in rg.finditer(antes):
                    dist = len(antes) - m.end()
                    if dist <= 120 and (melhor is None or dist < melhor[1]):
                        melhor = (ev, dist)
        if not melhor:
            continue
        ev = melhor[0]
        atual = achados.get(ev)
        # a primeira ocorrência vale; uma posterior só substitui se trouxer a hora que faltava no mesmo dia
        if atual and not (not atual["_hora"] and tem_hora and atual["data"].date() == data.date()):
            continue
        pags = RE_PAG.findall(norm[:ini])
        trecho = re.sub(r"\s+", " ", bruto[max(0, ini - 110):fim + 12]).strip()
        trecho = re.sub(r"^\S*\s", "", trecho) if ini > 110 else trecho  # começa numa palavra inteira
        trecho = re.sub(r"\s\S*$", "", trecho)
        achados[ev] = {"data": data, "pagina": pags[-1] if pags else None, "trecho": trecho[-220:], "_hora": tem_hora}
    return {ev: {k: v for k, v in a.items() if k != "_hora"} for ev, a in achados.items()}


def _da_ia(extracao):
    """Datas lidas pela IA na extração (formato novo "cronograma" ou o antigo "data_abertura")."""
    ex = extracao or {}
    c = ex.get("cronograma") or {}
    saida = {}
    mapa = {"sessao": ("data_sessao",), "inicio_propostas": ("inicio_recebimento_propostas",),
            "fim_propostas": ("fim_recebimento_propostas",), "impugnacao": ("limite_impugnacao",),
            "esclarecimento": ("limite_esclarecimento",)}
    for ev, chaves in mapa.items():
        for k in chaves:
            d = _para_data(c.get(k))
            if d:
                saida[ev] = {"data": d, "pagina": (c.get("paginas") or {}).get(k) if isinstance(c.get("paginas"), dict) else None,
                             "trecho": (c.get("trechos") or {}).get(k) if isinstance(c.get("trechos"), dict) else None}
    if "sessao" not in saida and _para_data(ex.get("data_abertura")):
        saida["sessao"] = {"data": _para_data(ex.get("data_abertura")), "pagina": None, "trecho": None}
    return saida


def _mesmo_dia(a, b):
    return bool(a and b and a.date() == b.date())


def _br(d):
    return d.strftime("%d/%m/%Y") + (d.strftime(" %H:%M") if (d.hour or d.minute) else "") if d else "—"


def montar(ed, extracao=None, pncp_datas=None):
    """Recalcula ed.cronograma e ajusta ed.data_abertura (a sessão). Devolve True se a data da sessão mudou.
    pncp_datas: {"abertura": ..., "encerramento": ...} (datas do PNCP, quando conhecidas)."""
    antigo = dict(ed.cronograma or {})
    pncp_ant = antigo.get("pncp") or {}
    pncp = {"abertura": _iso(_para_data((pncp_datas or {}).get("abertura"))) or pncp_ant.get("abertura"),
            "encerramento": _iso(_para_data((pncp_datas or {}).get("encerramento"))) or pncp_ant.get("encerramento")}
    if extracao is None:  # a última leitura da IA guardada aqui; senão, a da última análise
        extracao = antigo.get("_ia") if (antigo.get("_ia") or {}).get("cronograma") or (antigo.get("_ia") or {}).get("data_abertura") else None
        if extracao is None:
            from models import Analise
            a = Analise.query.filter_by(edital_id=ed.id, status="concluida").order_by(Analise.id.desc()).first()
            extracao = ((a.resultado or {}).get("extracao") if a else None) or {}
    ia = _da_ia(extracao)
    texto = do_texto(ed.texto) if ed.texto else {}
    usuario = {ev: {"data": _para_data(v)} for ev, v in (antigo.get("usuario") or {}).items() if _para_data(v)}
    if ed.data_sessao_fonte == "usuario" and ed.data_abertura and "sessao" not in usuario:
        usuario["sessao"] = {"data": ed.data_abertura}
    pn = {}
    if _para_data(pncp["abertura"]):
        pn["inicio_propostas"] = {"data": _para_data(pncp["abertura"])}
    if _para_data(pncp["encerramento"]):
        pn["fim_propostas"] = {"data": _para_data(pncp["encerramento"])}
        pn["sessao"] = {"data": _para_data(pncp["encerramento"])}  # no PNCP, o fim do envio costuma coincidir com a sessão

    eventos, divergencias = {}, []
    for ev in EVENTOS:
        for fonte, base in (("usuario", usuario), ("edital_ia", ia), ("edital_texto", texto), ("pncp", pn)):
            if ev in base:
                eventos[ev] = {**base[ev], "fonte": fonte}
                break

    # confusões comuns: a "sessão" escolhida é, na verdade, o início do envio de propostas
    s = eventos.get("sessao")
    if s and s["fonte"] != "usuario":
        inicio = (eventos.get("inicio_propostas") or {}).get("data")
        candidatos = [x["data"] for x in (texto.get("sessao"), ia.get("sessao"), eventos.get("fim_propostas")) if x and x.get("data")]
        if inicio and _mesmo_dia(s["data"], inicio):
            posterior = max((c for c in candidatos if c.date() > inicio.date()), default=None)
            if posterior:
                divergencias.append(f"{_br(s['data'])} é o início do envio de propostas/documentos, não a sessão pública. "
                                    f"Usamos {_br(posterior)} como sessão.")
                eventos["sessao"] = {"data": posterior, "fonte": "edital_texto" if texto.get("sessao") else s["fonte"],
                                     "pagina": (texto.get("sessao") or {}).get("pagina"), "trecho": (texto.get("sessao") or {}).get("trecho")}
                s = eventos["sessao"]
    # fim do envio vindo do PNCP em outro dia que a sessão lida no edital: é o cadastro errado, não vira prazo
    fp = eventos.get("fim_propostas")
    if s and fp and fp["fonte"] == "pncp" and s["fonte"] != "pncp" and not _mesmo_dia(fp["data"], s["data"]):
        eventos.pop("fim_propostas")
    # início do envio depois da sessão não existe: descarta
    if s and eventos.get("inicio_propostas") and eventos["inicio_propostas"]["data"] > s["data"]:
        eventos.pop("inicio_propostas")

    # divergências entre fontes (sempre sobre a sessão, que move todos os prazos)
    s = eventos.get("sessao")
    if s:
        leituras = {"a IA": (ia.get("sessao") or {}).get("data"), "o texto do edital": (texto.get("sessao") or {}).get("data"),
                    "o PNCP": (pn.get("sessao") or {}).get("data")}
        for quem, d in leituras.items():
            if d and not _mesmo_dia(d, s["data"]):
                if quem == "o PNCP":
                    divergencias.append(f"No PNCP, o fim do envio de propostas está em {_br(d)}, mas a sessão considerada é "
                                        f"{_br(s['data'])} ({FONTES[s['fonte']]}). O órgão pode ter cadastrado a data errada no PNCP.")
                else:
                    divergencias.append(f"Segundo {quem}, a sessão seria em {_br(d)} (considerada: {_br(s['data'])}).")
    divergencias = list(dict.fromkeys(divergencias))

    sessao_nova = s["data"] if s else None
    mudou = bool(sessao_nova and sessao_nova != ed.data_abertura)
    if sessao_nova:
        ed.data_abertura = sessao_nova
        ed.data_sessao_fonte = {"usuario": "usuario", "edital_ia": "edital", "edital_texto": "edital", "pncp": "pncp"}[s["fonte"]]

    confirmado = antigo.get("confirmado") or None
    # se a sessão mudou depois da conferência, ela precisa ser conferida de novo
    if confirmado and sessao_nova and _iso(sessao_nova) != confirmado.get("sessao"):
        confirmado = None
    ed.cronograma = {
        "eventos": {ev: {"data": _iso(e["data"]), "fonte": e["fonte"], "pagina": e.get("pagina"),
                         "trecho": (e.get("trecho") or None) and str(e["trecho"])[:300]} for ev, e in eventos.items()},
        "pncp": pncp, "divergencias": divergencias[:6], "usuario": antigo.get("usuario") or {},
        "confirmado": confirmado, "atualizado_em": _iso(datetime.utcnow()),
        "_ia": {"cronograma": (extracao or {}).get("cronograma"), "data_abertura": (extracao or {}).get("data_abertura")},
    }
    return mudou


def alerta(ed):
    """Aviso para o usuário conferir as datas no edital. None depois de conferidas (se nada mudou)."""
    c = ed.cronograma or {}
    if c.get("confirmado") or not ed.data_abertura:
        return None
    div = c.get("divergencias") or []
    fonte = ((c.get("eventos") or {}).get("sessao") or {}).get("fonte")
    if div:
        return {"nivel": "divergencia", "titulo": "As datas desta licitação não batem entre as fontes",
                "texto": "Confira no edital a data da sessão e do envio de propostas antes de seguir os prazos.", "itens": div}
    if fonte == "pncp":
        return {"nivel": "confirmar", "titulo": "Datas vindas só do cadastro do órgão no PNCP",
                "texto": "O órgão às vezes cadastra o edital com data errada no PNCP. Confira no edital e confirme.", "itens": []}
    if fonte == "usuario":
        return None
    return {"nivel": "confirmar", "titulo": "Confirme os prazos no edital",
            "texto": "As datas foram lidas automaticamente. Confira no edital (e em eventuais erratas) e confirme.", "itens": []}


def publico(ed):
    """Versão para a tela (sem campos internos)."""
    c = dict(ed.cronograma or {})
    c.pop("_ia", None)
    c["rotulos"] = EVENTOS
    c["fontes"] = FONTES
    return c
