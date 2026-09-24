"""Consultas a bases públicas usadas no dossiê de concorrentes e na inteligência de preços.

- Receita Federal (via BrasilAPI, gratuita): https://brasilapi.com.br/api/cnpj/v1/{cnpj}
- TCU — Consulta Consolidada de Pessoa Jurídica (TCU, CNJ, CEIS, CNEP): certidoes-apf.apps.tcu.gov.br
- CGU — Portal da Transparência (CEIS e CNEP), requer chave gratuita: api.portaldatransparencia.gov.br
- Compras.gov.br — Dados abertos, módulo Pesquisa de Preços: dadosabertos.compras.gov.br

Todas as funções falham de forma silenciosa (retornam status 'indisponivel'), para o dossiê nunca travar.
"""
import logging
import re
import statistics

import requests
from flask import current_app

log = logging.getLogger(__name__)
UA = {"User-Agent": "Certame/1.0", "Accept": "application/json"}


def limpar_cnpj(v):
    d = re.sub(r"\D", "", v or "")
    return d if len(d) == 14 else None


def cnpj_valido(cnpj):
    c = limpar_cnpj(cnpj)
    if not c or c == c[0] * 14:
        return False

    def dv(base, pesos):
        s = sum(int(a) * b for a, b in zip(base, pesos)) % 11
        return "0" if s < 2 else str(11 - s)
    p1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    d1 = dv(c[:12], p1)
    d2 = dv(c[:12] + d1, [6] + p1)
    return c[-2:] == d1 + d2


def receita(cnpj):
    try:
        r = requests.get(f"https://brasilapi.com.br/api/cnpj/v1/{cnpj}", headers=UA, timeout=25)
        if r.status_code == 404:
            return {"status": "nao_encontrado"}
        r.raise_for_status()
        d = r.json()
        cnaes = [{"codigo": str(d.get("cnae_fiscal")), "descricao": d.get("cnae_fiscal_descricao"), "principal": True}]
        cnaes += [{"codigo": str(c.get("codigo")), "descricao": c.get("descricao"), "principal": False}
                  for c in d.get("cnaes_secundarios") or [] if c.get("codigo")]
        return {
            "status": "ok",
            "razao_social": d.get("razao_social"), "nome_fantasia": d.get("nome_fantasia"),
            "situacao": d.get("descricao_situacao_cadastral"), "data_situacao": d.get("data_situacao_cadastral"),
            "abertura": d.get("data_inicio_atividade"), "capital_social": d.get("capital_social"),
            "porte": d.get("porte") or d.get("descricao_porte"), "natureza_juridica": d.get("natureza_juridica"),
            "municipio": d.get("municipio"), "uf": d.get("uf"),
            "opcao_simples": d.get("opcao_pelo_simples"), "cnaes": cnaes,
            "socios": [{"nome": s.get("nome_socio"), "qualificacao": s.get("qualificacao_socio")}
                       for s in d.get("qsa") or []],
        }
    except Exception as e:
        log.warning("BrasilAPI falhou: %s", e)
        return {"status": "indisponivel", "erro": str(e)}


def sancoes_tcu(cnpj):
    """Certidão consolidada (TCU/CNJ/CEIS/CNEP) sem necessidade de chave."""
    try:
        r = requests.get(f"https://certidoes-apf.apps.tcu.gov.br/api/rest/publico/certidoes/{cnpj}",
                         params={"seEmitirPDF": "false"}, headers=UA, timeout=30)
        r.raise_for_status()
        d = r.json()
        certidoes = []
        for c in d.get("certidoes") or []:
            certidoes.append({"emissor": c.get("emissor") or c.get("tipo"),
                              "situacao": c.get("situacao") or c.get("descricao"),
                              "observacao": c.get("observacao")})
        constam = [c for c in certidoes if "nada consta" not in str(c.get("situacao", "")).lower()]
        return {"status": "ok", "certidoes": certidoes, "alerta": bool(constam)}
    except Exception as e:
        log.warning("Consulta TCU falhou: %s", e)
        return {"status": "indisponivel", "erro": str(e)}


def sancoes_cgu(cnpj):
    chave = current_app.config.get("PORTAL_TRANSPARENCIA_KEY")
    if not chave:
        return {"status": "sem_chave"}
    saida = {"status": "ok", "registros": []}
    for cadastro in ("ceis", "cnep"):
        try:
            r = requests.get(f"https://api.portaldatransparencia.gov.br/api-de-dados/{cadastro}",
                             params={"codigoSancionado": cnpj, "pagina": 1},
                             headers={**UA, "chave-api-dados": chave}, timeout=30)
            r.raise_for_status()
            for s in r.json() or []:
                saida["registros"].append({
                    "cadastro": cadastro.upper(),
                    "tipo": (s.get("tipoSancao") or {}).get("descricaoResumida"),
                    "orgao": (s.get("orgaoSancionador") or {}).get("nome"),
                    "inicio": s.get("dataInicioSancao"), "fim": s.get("dataFimSancao"),
                    "fundamentacao": ", ".join(f.get("descricao", "") for f in s.get("fundamentacao") or []),
                })
        except Exception as e:
            log.warning("Portal da Transparência (%s) falhou: %s", cadastro, e)
            saida["status"] = "parcial"
    return saida


def pesquisa_precos(codigo, tipo="material", uf=None, paginas=2):
    """Preços praticados no Compras.gov.br para um código CATMAT/CATSER."""
    modulo = "1_consultarMaterial" if tipo == "material" else "3_consultarServico"
    amostras = []
    for pagina in range(1, paginas + 1):
        params = {"pagina": pagina, "tamanhoPagina": 100, "codigoItemCatalogo": codigo}
        if uf:
            params["estado"] = uf
        try:
            r = requests.get(f"https://dadosabertos.compras.gov.br/modulo-pesquisa-preco/{modulo}",
                             params=params, headers=UA, timeout=40)
            r.raise_for_status()
            d = r.json()
        except Exception as e:
            log.warning("Compras.gov pesquisa de preço falhou: %s", e)
            break
        lista = d.get("resultado") or d.get("data") or []
        for it in lista:
            preco = next((it[k] for k in ("precoUnitario", "valorUnitario", "preco") if it.get(k)), None)
            if not preco:
                continue
            amostras.append({"preco": float(preco), "orgao": it.get("nomeOrgao") or it.get("nomeUasg"),
                             "uf": it.get("estado") or it.get("siglaUf"),
                             "data": it.get("dataResultado") or it.get("dataCompra"),
                             "quantidade": it.get("quantidade"), "unidade": it.get("siglaUnidadeFornecimento")
                             or it.get("nomeUnidadeFornecimento"),
                             "fornecedor": it.get("nomeFornecedor"), "fonte": "Compras.gov.br"})
        if len(lista) < 100:
            break
    return amostras


def estatisticas(precos):
    v = sorted(p for p in precos if p and p > 0)
    if not v:
        return {"n": 0}

    def quartil(q):
        pos = (len(v) - 1) * q
        i = int(pos)
        return v[i] if i + 1 >= len(v) else v[i] + (v[i + 1] - v[i]) * (pos - i)
    q1, q3 = quartil(0.25), quartil(0.75)
    iqr = q3 - q1
    filtrados = [x for x in v if q1 - 1.5 * iqr <= x <= q3 + 1.5 * iqr] or v
    return {
        "n": len(v), "n_sem_outliers": len(filtrados), "minimo": v[0], "maximo": v[-1],
        "media": round(statistics.mean(filtrados), 4), "mediana": round(statistics.median(filtrados), 4),
        "q1": round(q1, 4), "q3": round(q3, 4),
        "faixa_competitiva": [round(quartil(0.2), 4), round(statistics.median(filtrados), 4)],
    }
