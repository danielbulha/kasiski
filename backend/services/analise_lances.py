"""Análise de lances: sugere proposta inicial, alvo e limite a partir dos preços que os possíveis concorrentes
praticaram em contratações parecidas (PNCP), do valor estimado e do piso da empresa. Depois, a IA explica a
estratégia e o DoubleCheck confere cada afirmação contra os números (a IA não pode inventar valores).

Base: edital.possiveis_concorrentes (services/possiveis_concorrentes.py), que já traz, por item do edital, o preço
unitário médio e mínimo homologado de cada empresa em itens semelhantes, e o % desses preços sobre o estimado.
"""
import json
import logging
import statistics
from datetime import datetime

from extensions import db

log = logging.getLogger(__name__)
AVISO = ("Sugestão estatística a partir de preços homologados no PNCP em contratações parecidas. Preços passados não garantem o "
         "comportamento dos concorrentes neste pregão, e o seu piso deve vir dos seus custos.")


def _pct(v, est):
    try:
        return round(float(v) / float(est) * 100, 2) if v and est else None
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _item_do_edital(pc, item):
    alvo = str(item or "").strip().lstrip("0")
    for p in pc.get("precos_itens") or []:
        if str(p.get("numero") or "").strip().lstrip("0") == alvo and p.get("n"):
            return p
    return None


def evidencias(d, edital):
    """Números que sustentam a sugestão. Devolve {base, concorrentes[], fonte, n_amostras, ...}."""
    pc = (edital.possiveis_concorrentes or {}) if edital else {}
    base = d.valor_referencia or (edital.valor_estimado if edital else None)
    item = _item_do_edital(pc, d.item)
    comparaveis = [p for p in pc.get("precos_itens") or [] if p.get("n")]
    if not item and len(comparaveis) == 1 and len(pc.get("precos_itens") or []) == 1:
        item = comparaveis[0]  # edital de um item só: a disputa global é o próprio item
    concorrentes = []
    fonte = None
    if item and item.get("estimado"):
        fonte = f"preços unitários homologados em itens parecidos com o item {item.get('numero') or d.item} do edital"
        for e in item.get("empresas") or []:
            concorrentes.append({"cnpj": e.get("cnpj"), "nome": e.get("nome"), "n": e.get("n"),
                                 "pct_medio": _pct(e.get("media"), item["estimado"]), "pct_minimo": _pct(e.get("minimo"), item["estimado"])})
    else:  # sem o item: média de cada concorrente sobre o estimado nos itens que foi possível comparar
        fonte = "média dos preços de cada possível concorrente sobre o estimado, nos itens comparáveis do edital"
        for e in pc.get("itens") or []:
            if e.get("pct_medio_estimado"):
                mins = [x.get("pct_estimado") for x in e.get("precos") or [] if x.get("pct_estimado")]
                concorrentes.append({"cnpj": e.get("cnpj"), "nome": e.get("nome"), "n": len(e.get("precos") or []),
                                     "pct_medio": e["pct_medio_estimado"], "pct_minimo": min(mins) if mins else e["pct_medio_estimado"],
                                     "relevancia": e.get("relevancia"), "mesmo_orgao": e.get("mesmo_orgao"), "vitorias": e.get("vitorias")})
    # completa com relevância/vitórias quando vier da lista de itens
    info = {e.get("cnpj"): e for e in pc.get("itens") or []}
    for c in concorrentes:
        i = info.get(c["cnpj"]) or {}
        c.setdefault("relevancia", i.get("relevancia"))
        c.setdefault("vitorias", i.get("vitorias"))
        c.setdefault("mesmo_orgao", i.get("mesmo_orgao"))
    concorrentes = [c for c in concorrentes if c.get("pct_medio")]
    concorrentes.sort(key=lambda c: c["pct_medio"])
    return {"base": base, "criterio": d.criterio, "piso": d.preco_piso, "lance_inicial_atual": d.lance_inicial,
            "concorrentes": concorrentes[:10], "fonte": fonte, "n_concorrentes": len(concorrentes),
            "n_amostras": sum(int(c.get("n") or 0) for c in concorrentes),
            "possiveis_consultado_em": pc.get("consultado_em"), "tem_possiveis": bool(pc.get("itens")),
            "tipo_objeto": edital.tipo_objeto if edital else None, "modo": d.modo}


def calcular(ev):
    """Regras determinísticas (o que a IA vai explicar e o DoubleCheck vai conferir)."""
    base, piso = ev["base"], ev["piso"]
    cs = ev["concorrentes"]
    out = {"suficiente": bool(cs and base), "alertas": []}
    if ev["criterio"] == "maior_desconto":
        out["alertas"].append("Critério de maior desconto: a análise por preço sobre o estimado não se aplica diretamente; use-a como referência.")
    if not out["suficiente"]:
        return out
    medios = [c["pct_medio"] for c in cs]
    minimos = [c["pct_minimo"] or c["pct_medio"] for c in cs]
    fech_pct = min(medios)                       # preço típico do concorrente mais barato
    agress_pct = min(minimos)                    # o menor preço já praticado por eles
    med_pct = statistics.median(medios)
    v = lambda p: round(base * p / 100, 2)
    out.update({
        "pct_fechamento_provavel": round(fech_pct, 2), "pct_mais_agressivo": round(agress_pct, 2), "pct_mediana": round(med_pct, 2),
        "fechamento_provavel": v(fech_pct), "mais_agressivo": v(agress_pct), "mediana": v(med_pct),
    })
    # proposta inicial: dentro de ~8% do provável vencedor (no aberto e fechado só passa quem estiver até 10% do melhor)
    prop = v(min(med_pct, fech_pct * 1.08))
    alvo = v(fech_pct * 0.995)                   # cobrir o concorrente mais barato por pouco
    if piso:
        prop, alvo = max(prop, piso), max(alvo, piso)
    out.update({"proposta_inicial": prop, "alvo_fechamento": alvo, "limite": piso})
    if piso:
        folga = (out["fechamento_provavel"] - piso) / piso * 100
        out["folga_pct"] = round(folga, 2)
        if folga < 0:
            out["estrategia"] = "conservadora"
            out["alertas"].append(f"O concorrente mais barato costuma fechar em {fech_pct:.1f}% do estimado, abaixo do seu piso. "
                                  "Há risco real de não vencer sem prejuízo: reveja custos ou avalie não disputar.")
        elif folga < 3:
            out["estrategia"] = "conservadora"
        elif folga < 8:
            out["estrategia"] = "moderada"
        else:
            out["estrategia"] = "moderada" if len(cs) >= 5 else "agressiva"
    else:
        out["estrategia"] = "moderada"
        out["alertas"].append("Defina o piso (custo + margem mínima) para a sugestão levar em conta o seu limite.")
    # inexequibilidade (Lei 14.133, art. 59, §4º; IN SEGES/ME 73/2022, art. 34)
    eng = ev.get("tipo_objeto") in ("obra", "servico_engenharia")
    limite_inex = 75 if eng else 50
    if agress_pct < limite_inex:
        out["alertas"].append(f"Já houve preço de {agress_pct:.1f}% do estimado: abaixo de {limite_inex}% "
                              + ("a proposta de obra ou serviço de engenharia é considerada inexequível (art. 59, §4º)." if eng else
                                 "é indício de inexequibilidade para bens e serviços (IN 73/2022, art. 34). Pode haver diligência."))
    if len(cs) < 3:
        out["alertas"].append(f"Base pequena: só {len(cs)} concorrente(s) com preço comparável. Use com cautela.")
    return out


def _prompt(ev, calc):
    from services.prompts import BASE
    sistema = BASE + (" Você é consultor de disputa de pregões eletrônicos. Explique a estratégia de lances usando SOMENTE os números "
                      "fornecidos (não invente valores, empresas nem percentuais). Linguagem direta, para quem vai dar lances.")
    usuario = f"""EVIDÊNCIAS (preços homologados de possíveis concorrentes em contratações parecidas, em % do valor estimado):
{json.dumps(ev, ensure_ascii=False, default=str)}

CÁLCULOS DO KASISKI:
{json.dumps(calc, ensure_ascii=False, default=str)}

Devolva JSON:
{{"resumo": "2 a 3 frases",
 "estrategia": "conservadora|moderada|agressiva", "por_que": "",
 "afirmacoes": [{{"texto": "afirmação curta e verificável sobre os números (ex.: 'A empresa X costuma fechar em 88% do estimado')"}}],
 "concorrentes": [{{"nome": "", "leitura": "como costuma se comportar, pelos números"}}],
 "riscos": [""], "na_sessao": ["dicas práticas para a sessão, sem valores novos"]}}"""
    demo = {"resumo": "O concorrente mais barato costuma fechar perto de " + f"{calc.get('pct_fechamento_provavel', 0):.1f}% do estimado. "
            "Entre com proposta competitiva e guarde margem para cobrir por pouco.",
            "estrategia": calc.get("estrategia", "moderada"), "por_que": "A folga entre o provável preço de fechamento e o seu piso permite reduções moderadas.",
            "afirmacoes": [{"texto": f"O preço típico do concorrente mais barato é {calc.get('pct_fechamento_provavel', 0):.1f}% do estimado."},
                           {"texto": f"A mediana dos concorrentes é {calc.get('pct_mediana', 0):.1f}% do estimado."}],
            "concorrentes": [{"nome": c["nome"], "leitura": f"Média de {c['pct_medio']:.1f}% do estimado."} for c in ev["concorrentes"][:3]],
            "riscos": calc.get("alertas") or [], "na_sessao": ["Registre cada lance do portal na sala para o Kasiski recalcular o próximo."]}
    return sistema, usuario, demo


def executar(disputa_id, conta_id=None):
    """Roda em segundo plano: evidências → cálculo → explicação da IA → DoubleCheck. Grava em disputa.analise."""
    from models import Disputa, Edital
    from services import fluxos, llm
    d = Disputa.query.get(disputa_id)
    if not d:
        return
    ed = Edital.query.get(d.edital_id) if d.edital_id else None
    try:
        if ed and not (ed.possiveis_concorrentes or {}).get("itens") and conta_id:
            # ainda não há histórico de concorrentes: busca agora (conta uma avaliação do plano se o PNCP responder)
            import planos
            from models import Analise, Conta
            from services import possiveis_concorrentes
            d.analise = {**(d.analise or {}), "status": "processando", "etapa": "Buscando os possíveis concorrentes e os preços que praticaram no PNCP"}
            db.session.commit()
            ult = Analise.query.filter_by(edital_id=ed.id, status="concluida").order_by(Analise.id.desc()).first()
            r = possiveis_concorrentes.atualizar(ed, (ult.resultado or {}).get("extracao") if ult else None)
            if r.get("status") == "concluida" and not r.get("pncp_indisponivel"):
                planos.registrar_uso(Conta.query.get(conta_id), "possiveis", [])
            d.analise = {**(d.analise or {}), "status": "processando", "etapa": "Calculando a faixa de preços e pedindo a análise à IA"}
            db.session.commit()
        ev = evidencias(d, ed)
        calc = calcular(ev)
        res = {"status": "concluida", "evidencias": ev, "calculo": calc, "aviso": AVISO, "concluida_em": datetime.utcnow().isoformat(timespec="minutes")}
        if calc["suficiente"]:
            s, u, demo = _prompt(ev, calc)
            r = llm.chamar("analise", s, u, max_tokens=2500, demo=demo)
            ia = llm.extrair_json(r.texto) or {}
            itens = [{"id": f"a{i}", "tipo": "afirmacao_sobre_numeros", "texto": str(a.get("texto") or "")[:400]}
                     for i, a in enumerate(ia.get("afirmacoes") or []) if a.get("texto")][:10]
            itens += [{"id": f"c{i}", "tipo": "leitura_de_concorrente", "texto": f"{c.get('nome')}: {c.get('leitura')}"[:400]}
                      for i, c in enumerate(ia.get("concorrentes") or [])][:8]
            itens.append({"id": "e0", "tipo": "estrategia", "texto": f"Estratégia {ia.get('estrategia')}: {ia.get('por_que') or ''}"[:500]})
            # o "documento" do DoubleCheck aqui são os próprios números: o verificador confere se a IA os leu direito
            doc = json.dumps({"evidencias": ev, "calculos": calc}, ensure_ascii=False, default=str)
            mapa, _ = fluxos._verificar(doc, itens, r.familia)
            for it in itens:
                it["verificacao"] = mapa.get(it["id"], dict(fluxos.SEM_RETORNO))
            res["ia"] = {k: ia.get(k) for k in ("resumo", "estrategia", "por_que", "riscos", "na_sessao")}
            res["itens"] = itens
            res["doublecheck"] = fluxos.resumo_doublecheck({"apontamentos": itens})
            res["demonstracao"] = bool(getattr(r, "demonstracao", False))
        d.analise = res
    except Exception as e:
        log.exception("Análise de lances da disputa %s falhou", disputa_id)
        d.analise = {"status": "erro", "erro": "Não foi possível concluir a análise agora. Tente de novo em instantes."}
    db.session.commit()
