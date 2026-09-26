"""Integração com o PNCP (Portal Nacional de Contratações Públicas) — APIs públicas, sem login.

- Busca textual (a mesma do portal): https://pncp.gov.br/api/search/
- API de consulta: https://pncp.gov.br/api/consulta/v1  (Swagger: /api/consulta/swagger-ui/index.html)
- API do PNCP (arquivos, itens, resultados): https://pncp.gov.br/api/pncp/v1

Os campos das respostas variam entre endpoints; por isso a normalização é tolerante.
"""
import logging
import re
from datetime import date, datetime, timedelta

import requests

from services.arquivos import texto_de_pdf_bytes

log = logging.getLogger(__name__)
BASE_BUSCA = "https://pncp.gov.br/api/search/"
BASE_CONSULTA = "https://pncp.gov.br/api/consulta/v1"
BASE_PNCP = "https://pncp.gov.br/api/pncp/v1"
CAB = {"User-Agent": "Certame/1.0 (+contato do administrador)", "Accept": "application/json"}


def _get(url, params=None, timeout=40):
    r = requests.get(url, params=params, headers=CAB, timeout=timeout)
    if r.status_code == 204:
        return None
    r.raise_for_status()
    return r.json()


def _data(v):
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v).replace("Z", "")[:19])
    except ValueError:
        return None


def partes_controle(numero):
    """'00394460000141-1-000123/2026' -> (cnpj, ano, sequencial)."""
    m = re.match(r"(\d{14})-\d+-(\d+)/(\d{4})", numero or "")
    if not m:
        return None
    return m.group(1), int(m.group(3)), int(m.group(2))


def _normalizar(item):
    """Unifica campos da busca textual e da API de consulta."""
    orgao = item.get("orgaoEntidade") or {}
    unidade = item.get("unidadeOrgao") or {}
    numero = item.get("numeroControlePNCP") or item.get("numero_controle_pncp") or ""
    cnpj_ano_seq = partes_controle(numero)
    link = item.get("linkSistemaOrigem") or ""
    url_pncp = ""
    if cnpj_ano_seq:
        c, a, s = cnpj_ano_seq
        url_pncp = f"https://pncp.gov.br/app/editais/{c}/{a}/{s}"
    return {
        "numero_controle": numero,
        "orgao": orgao.get("razaoSocial") or item.get("orgao_nome") or "",
        "orgao_cnpj": orgao.get("cnpj") or item.get("orgao_cnpj") or "",
        "objeto": item.get("objetoCompra") or item.get("description") or item.get("title") or "",
        "modalidade": item.get("modalidadeNome") or item.get("modalidade_licitacao_nome") or "",
        "uf": unidade.get("ufSigla") or item.get("uf") or "",
        "municipio": unidade.get("municipioNome") or item.get("municipio_nome") or "",
        "valor_estimado": item.get("valorTotalEstimado") or item.get("valor_global"),
        "data_abertura": item.get("dataAberturaProposta") or item.get("data_inicio_vigencia"),
        "data_encerramento": item.get("dataEncerramentoProposta") or item.get("data_fim_vigencia"),
        "portal_disputa": link,
        "link": url_pncp or link,
        "numero": item.get("numeroCompra") or item.get("numero") or "",
    }


def buscar_editais_abertos(palavras, ufs=None, paginas=2):
    """Editais recebendo propostas que contêm as palavras-chave (busca textual do PNCP)."""
    resultados = {}
    termos = [p.strip() for p in (palavras or "").split(",") if p.strip()] or [""]
    for termo in termos[:8]:
        for pagina in range(1, paginas + 1):
            params = {"q": termo, "tipos_documento": "edital", "ordenacao": "-data", "pagina": pagina,
                      "tam_pagina": 20, "status": "recebendo_proposta"}
            if ufs:
                params["ufs"] = ufs
            try:
                dados = _get(BASE_BUSCA, params) or {}
            except Exception as e:
                log.warning("Busca PNCP falhou (%s): %s", termo, e)
                break
            itens = dados.get("items") or []
            for it in itens:
                n = _normalizar(it)
                if n["numero_controle"]:
                    n["termo"] = termo
                    resultados[n["numero_controle"]] = n
            if len(itens) < 20:
                break
    return list(resultados.values())


def buscar_abertos_consulta(uf=None, modalidade=None, pagina=1):
    """Alternativa pela API de consulta: contratações com proposta em aberto."""
    params = {"dataFinal": (date.today() + timedelta(days=60)).strftime("%Y%m%d"), "pagina": pagina,
              "tamanhoPagina": 50}
    if uf:
        params["uf"] = uf
    if modalidade:
        params["codigoModalidadeContratacao"] = modalidade
    dados = _get(f"{BASE_CONSULTA}/contratacoes/proposta", params) or {}
    return [_normalizar(i) for i in dados.get("data", [])]


def detalhe(numero_controle):
    partes = partes_controle(numero_controle)
    if not partes:
        return None
    cnpj, ano, seq = partes
    d = _get(f"{BASE_CONSULTA}/orgaos/{cnpj}/compras/{ano}/{seq}")
    return _normalizar(d) if d else None


def baixar_texto_edital(numero_controle):
    """Compatibilidade: devolve só (texto, nome_arquivo)."""
    d = baixar_edital(numero_controle)
    return (d["texto"], d["nome"]) if d else (None, None)


def baixar_edital(numero_controle):
    """Baixa o primeiro PDF de edital publicado. Devolve {texto, nome, conteudo, url} ou None.
    Zip e imagens são ignorados."""
    partes = partes_controle(numero_controle)
    if not partes:
        return None
    cnpj, ano, seq = partes
    try:
        arquivos = _get(f"{BASE_PNCP}/orgaos/{cnpj}/compras/{ano}/{seq}/arquivos") or []
    except Exception as e:
        log.warning("Lista de arquivos PNCP falhou: %s", e)
        return None
    arquivos = sorted(arquivos, key=lambda a: 0 if "edital" in str(a.get("tipoDocumentoNome", "")).lower() else 1)
    for a in arquivos:
        url = a.get("url") or a.get("uri")
        if not url:
            continue
        try:
            r = requests.get(url, headers={"User-Agent": CAB["User-Agent"]}, timeout=90)
            if r.content[:4] != b"%PDF":
                continue
            texto = texto_de_pdf_bytes(r.content)
            if len(texto) > 500:
                nome = a.get("titulo") or "edital"
                return {"texto": texto, "nome": nome if nome.lower().endswith(".pdf") else f"{nome}.pdf",
                        "conteudo": r.content, "url": url}
        except Exception as e:
            log.warning("Download de arquivo PNCP falhou: %s", e)
    return None


def historico_fornecedor(cnpj, limite=20):
    """Contratos e atas em que o CNPJ aparece (busca textual do PNCP)."""
    saida = []
    for tipo in ("contrato", "ata"):
        try:
            dados = _get(BASE_BUSCA, {"q": cnpj, "tipos_documento": tipo, "ordenacao": "-data",
                                      "pagina": 1, "tam_pagina": limite}) or {}
        except Exception as e:
            log.warning("Histórico PNCP falhou: %s", e)
            continue
        for it in dados.get("items") or []:
            saida.append({"tipo": tipo, "orgao": it.get("orgao_nome"), "objeto": it.get("description") or it.get("title"),
                          "valor": it.get("valor_global"), "uf": it.get("uf"),
                          "data": it.get("data_publicacao_pncp") or it.get("data_inicio_vigencia"),
                          "numero_controle": it.get("numero_controle_pncp")})
    return saida


_DOC_RELEVANTE = re.compile(r"ata|julgament|habilita|recurs|resultado|decis|parecer|adjudica|homologa|relat[oó]rio|diligên|dilig", re.I)
_DOC_IGNORAR = re.compile(r"\bedital\b|termo de refer|estudo t[eé]cnico|projeto b[aá]sico|minuta|aviso", re.I)


def compra_do_contrato(numero_controle_contrato):
    """'CNPJ-2-000140/2026' -> numero de controle da compra de origem ('CNPJ-1-000968/2026') ou None."""
    try:
        cnpj, _, resto = numero_controle_contrato.split("-")
        seq, ano = resto.split("/")
        d = _get(f"{BASE_PNCP}/orgaos/{cnpj}/contratos/{ano}/{int(seq)}") or {}
        return d.get("numeroControlePncpCompra") or d.get("numeroControlePNCPCompra")
    except Exception as e:
        log.warning("Contrato PNCP %s sem compra de origem: %s", numero_controle_contrato, e)
        return None


def documentos_de_julgamento(numero_controle_compra, limite=3):
    """Atas, julgamentos, decisões de recurso etc. publicados na compra (PDFs). Devolve [{titulo, tipo, url, conteudo, texto}]."""
    partes = partes_controle(numero_controle_compra)
    if not partes:
        return []
    cnpj, ano, seq = partes
    try:
        arquivos = _get(f"{BASE_PNCP}/orgaos/{cnpj}/compras/{ano}/{seq}/arquivos") or []
    except Exception as e:
        log.warning("Arquivos da compra %s indisponíveis: %s", numero_controle_compra, e)
        return []
    saida = []
    for a in arquivos:
        rotulo = f"{a.get('tipoDocumentoNome') or ''} {a.get('titulo') or ''}"
        if not _DOC_RELEVANTE.search(rotulo) or _DOC_IGNORAR.search(rotulo):
            continue
        url = a.get("url") or a.get("uri")
        if not url:
            continue
        try:
            r = requests.get(url, headers={"User-Agent": CAB["User-Agent"]}, timeout=60)
            if r.content[:4] != b"%PDF" or len(r.content) > 25 * 1024 * 1024:
                continue
            texto = texto_de_pdf_bytes(r.content)
            if len(texto) < 200:
                continue
            saida.append({"titulo": (a.get("titulo") or a.get("tipoDocumentoNome") or "Documento")[:300],
                          "tipo_pncp": a.get("tipoDocumentoNome"), "url": url, "conteudo": r.content, "texto": texto,
                          "data": a.get("dataPublicacaoPncp")})
        except Exception as e:
            log.warning("Download de documento PNCP falhou: %s", e)
        if len(saida) >= limite:
            break
    return saida
