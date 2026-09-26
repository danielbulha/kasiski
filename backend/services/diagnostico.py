"""Diagnóstico de maturidade B2G: perguntas em backend/data/diagnostico.json (as mesmas do site)."""
import json
import os
from functools import lru_cache

from extensions import db

ARQUIVO = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "diagnostico.json")


@lru_cache(maxsize=1)
def definicao():
    with open(ARQUIVO, encoding="utf-8") as f:
        return json.load(f)


def nivel_de(nota):
    niveis = sorted(definicao()["niveis"], key=lambda n: n["min"])
    atual = niveis[0]
    for n in niveis:
        if nota >= n["min"]:
            atual = n
    return atual


def calcular(respostas):
    """respostas = {id_pergunta: índice da opção}. Devolve nota geral, notas por eixo e recomendações.
    Opções com pontuação nula ("ainda não temos contratos") tiram o eixo da média."""
    d = definicao()
    por_eixo = {e["id"]: [] for e in d["eixos"]}
    respondidas = 0
    for q in d["perguntas"]:
        try:
            i = int((respostas or {}).get(q["id"]))
        except (TypeError, ValueError):
            continue
        if not 0 <= i < len(q["opcoes"]):
            continue
        respondidas += 1
        p = q["opcoes"][i]["p"]
        if p is not None:
            por_eixo[q["eixo"]].append(p)
    eixos = {k: (round(sum(v) / len(v)) if v else None) for k, v in por_eixo.items()}
    validos = [v for v in eixos.values() if v is not None]
    nota = round(sum(validos) / len(validos)) if validos else 0
    nomes = {e["id"]: e for e in d["eixos"]}
    fracos = sorted(((k, v) for k, v in eixos.items() if v is not None and v < 70), key=lambda x: x[1])[:3]
    recs = [{"eixo": k, "nome": nomes[k]["nome"], "nota": v, "texto": nomes[k]["baixa"], "recurso": nomes[k]["recurso"]} for k, v in fracos]
    n = nivel_de(nota)
    return {"nota": nota, "nivel": n["id"], "nivel_nome": n["nome"], "nivel_texto": n["texto"], "respondidas": respondidas,
            "total": len(d["perguntas"]),
            "eixos": [{"id": e["id"], "nome": e["nome"], "nota": eixos[e["id"]]} for e in d["eixos"]],
            "recomendacoes": recs}


def media_mercado(minimo=20):
    """Média das notas (geral e por eixo) de todos os diagnósticos, quando já há amostra suficiente."""
    from models import DiagnosticoB2G
    todos = DiagnosticoB2G.query.with_entities(DiagnosticoB2G.nota, DiagnosticoB2G.eixos).all()
    if len(todos) < minimo:
        return None
    geral = round(sum(t.nota or 0 for t in todos) / len(todos))
    por = {}
    for t in todos:
        for k, v in (t.eixos or {}).items():
            if v is not None:
                por.setdefault(k, []).append(v)
    return {"nota": geral, "eixos": {k: round(sum(v) / len(v)) for k, v in por.items()}, "amostra": len(todos)}
