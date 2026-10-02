"""Editais publicados em diários oficiais municipais, pela API pública do Querido Diário (Open Knowledge Brasil).

Por que: nem tudo passa pelo PNCP. Os chamamentos públicos para qualificar e contratar Organizações Sociais de saúde
e de educação (contratos de gestão) e muitos avisos de municípios pequenos aparecem no diário oficial antes, ou só lá.

Limites conhecidos: o Querido Diário cobre parte dos municípios brasileiros (não todos) e não traz diários estaduais
nem o da União; o texto vem do OCR do diário, então o aviso chega como um trecho — o edital completo continua no site
do órgão. A API é aberta e pede uso moderado (cerca de 60 requisições por minuto).
"""
import hashlib
import logging
import os
import re
from datetime import date, timedelta

import requests

log = logging.getLogger(__name__)
# Em ago/2026 a API saiu de api.queridodiario.ok.org.br (o domínio antigo parou de responder; dá erro de TLS)
# para api.queridodiario.org.br. QUERIDO_DIARIO_API permite trocar sem novo deploy; o antigo fica como reserva.
BASES = [b.rstrip("/") for b in (os.environ.get("QUERIDO_DIARIO_API") or "").split(",") if b.strip()] or [
    "https://api.queridodiario.org.br", "https://api.queridodiario.ok.org.br"]
BASE = BASES[0]
UA = {"User-Agent": "Mozilla/5.0 (compatible; KasiskiBot/1.0; +https://kasiski.com.br)"}
CONSULTA_OS = '"chamamento público" + ("organização social" | "organizações sociais") + (saúde | educação | "contrato de gestão")'
_AVISO = '(licitação | pregão | concorrência | "chamamento público" | "aviso de")'
_TAG = re.compile(r"<[^>]+>")


def _limpar(t):
    t = _TAG.sub("", t or "")
    return re.sub(r"\s+", " ", t).strip()


def _modalidade(t):
    n = t.lower()
    for chave, nome in (("chamamento", "Chamamento público"), ("pregão", "Pregão"), ("pregao", "Pregão"),
                        ("concorrência", "Concorrência"), ("concorrencia", "Concorrência"), ("dispensa", "Dispensa"),
                        ("inexigibilidade", "Inexigibilidade"), ("credenciamento", "Credenciamento"), ("tomada de preços", "Tomada de preços")):
        if chave in n:
            return nome
    return "Aviso em diário oficial"


def _consultar(querystring, desde, tamanho=20, timeout=20):
    global BASE
    params = {"querystring": querystring, "published_since": desde.isoformat(), "size": tamanho,
              "excerpt_size": 500, "number_of_excerpts": 1, "sort_by": "descending_date"}
    ultimo = None
    for base in [BASE] + [b for b in BASES if b != BASE]:
        try:
            r = requests.get(f"{base}/gazettes", params=params, headers=UA, timeout=timeout)
            r.raise_for_status()
            dados = r.json() or {}
        except Exception as e:  # domínio fora do ar, TLS, 404 ou resposta que não é JSON: tenta o próximo
            ultimo = e
            continue
        if base != BASE:
            log.warning("Querido Diário: passando a usar %s", base)
            BASE = base
        return dados.get("gazettes") or []
    raise ultimo or RuntimeError("Querido Diário sem endereço configurado")


def normalizar(gz, termo):
    trecho = _limpar(((gz.get("excerpts") or [""])[0]))
    if not trecho:
        return None
    municipio, uf = gz.get("territory_name") or "", (gz.get("state_code") or "").upper()[:2]
    chave = hashlib.sha1(f"{gz.get('territory_id')}|{gz.get('date')}|{trecho[:240]}".encode()).hexdigest()[:10]
    return {
        "numero_controle": f"DO-{gz.get('territory_id') or 'x'}-{gz.get('date') or ''}-{chave}"[:80],
        "fonte": "diario", "fonte_nome": "Diário oficial (Querido Diário)",
        "objeto": trecho[:600], "orgao": f"Município de {municipio}" if municipio else "Diário oficial municipal",
        "municipio": municipio, "uf": uf, "modalidade": _modalidade(trecho),
        "data_publicacao": gz.get("date"), "data_encerramento": None, "valor_estimado": None,
        "link": gz.get("url") or gz.get("txt_url") or "", "termo": termo,
    }


def buscar(termos, ufs=None, organizacoes_sociais=False, dias=10, max_consultas=4, limite=40):
    """Avisos recentes nos diários municipais. termos: os mesmos do radar. Devolve itens no formato do radar."""
    desde = date.today() - timedelta(days=dias)
    ufs_ok = {u.strip().upper() for u in (ufs or "").split(",") if u.strip()} if isinstance(ufs, str) else set(ufs or [])
    consultas = []
    if organizacoes_sociais:
        consultas.append(("organização social", CONSULTA_OS))
    for t in (termos or [])[:max(0, max_consultas - len(consultas))]:
        consultas.append((t, f'"{t}" + {_AVISO}'))
    saida, vistos = [], set()
    for termo, qs in consultas:
        try:
            gazetas = _consultar(qs, desde)
        except Exception as e:
            log.warning("Querido Diário indisponível (%s): %s", termo, type(e).__name__)
            continue
        for gz in gazetas:
            it = normalizar(gz, termo)
            if not it or it["numero_controle"] in vistos:
                continue
            if ufs_ok and it["uf"] and it["uf"] not in ufs_ok:
                continue
            vistos.add(it["numero_controle"])
            saida.append(it)
            if len(saida) >= limite:
                return saida
    return saida
