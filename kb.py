"""Base de conhecimento simples (RAG por palavras-chave), sem banco vetorial para manter custo zero.

Coloque arquivos .md na pasta knowledge-base/. Cada seção iniciada por '## ' vira um trecho recuperável.
Quando a base crescer, troque por embeddings + pgvector sem mudar a interface `buscar()`.
"""
import os
import re
import unicodedata
from functools import lru_cache

PASTA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "knowledge-base")
_STOP = set("para pela pelo como mais quando onde sobre entre deve pode seus suas este esta esse essa "
            "isso aquele qual quais sera serao caso desde ainda apenas tambem cada todo toda todos todas".split())


def _norm(t):
    t = unicodedata.normalize("NFKD", t.lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def _termos(t):
    return {w for w in re.findall(r"[a-z0-9]{4,}", _norm(t)) if w not in _STOP}


@lru_cache(maxsize=1)
def _trechos():
    trechos = []
    if not os.path.isdir(PASTA):
        return trechos
    for nome in sorted(os.listdir(PASTA)):
        if not nome.endswith(".md"):
            continue
        with open(os.path.join(PASTA, nome), encoding="utf-8") as f:
            conteudo = f.read()
        for bloco in re.split(r"\n(?=## )", conteudo):
            bloco = bloco.strip()
            if len(bloco) > 40:
                trechos.append((nome, bloco, _termos(bloco)))
    return trechos


def buscar(consulta, k=4):
    alvo = _termos(consulta)
    pontuados = sorted(((len(alvo & termos), nome, bloco) for nome, bloco, termos in _trechos()), reverse=True)
    escolhidos = [f"[Fonte: {nome}]\n{bloco}" for pontos, nome, bloco in pontuados[:k] if pontos > 0]
    return "\n\n".join(escolhidos)
