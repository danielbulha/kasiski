"""Contatos de empresas prospectadas, além do PNCP: bases públicas do CNPJ e o site da própria empresa.

Ordem: e-mail da Receita (BrasilAPI) → Minha Receita → CNPJ.ws → site da empresa (páginas públicas de contato).
Sem e-mail público, sugere endereços corporativos genéricos do domínio (contato@, comercial@, licitacao@...),
marcados como "sugerido — não verificado". Nunca monta e-mail pessoal de sócio (LGPD: só dado da pessoa jurídica).
"""
import logging
import re
import socket
import time
import unicodedata

import requests

log = logging.getLogger(__name__)
UA = {"User-Agent": "Mozilla/5.0 (compatible; KasiskiBot/1.0; +https://kasiski.com.br)"}
PROVEDORES = {"gmail.com", "hotmail.com", "outlook.com", "live.com", "yahoo.com", "yahoo.com.br", "uol.com.br", "bol.com.br",
              "terra.com.br", "ig.com.br", "icloud.com", "globo.com", "globomail.com", "msn.com", "hotmail.com.br", "outlook.com.br",
              "r7.com", "zipmail.com.br", "me.com", "protonmail.com", "gmx.com"}
GENERICOS = ["contato", "comercial", "licitacao", "licitacoes", "vendas"]
PALAVRAS_VAZIAS = {"ltda", "me", "epp", "eireli", "sa", "s", "a", "comercio", "servicos", "de", "da", "do", "das", "dos", "e",
                   "industria", "e", "cia", "empresa", "grupo", "brasil", "the", "em", "com", "para", "limitada", "sociedade"}
RE_EMAIL = re.compile(r"[a-zA-Z0-9._%+\-]{1,64}@[a-zA-Z0-9.\-]{2,100}\.[a-zA-Z]{2,10}")
LIXO = ("example", "exemplo", "seudominio", "sentry", "wixpress", ".png", ".jpg", ".gif", "@2x", "u003e", "domain.com")


def _norm(t):
    t = unicodedata.normalize("NFD", (t or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def _email_ok(e):
    e = (e or "").strip().strip(".").lower()
    if not RE_EMAIL.fullmatch(e) or any(x in e for x in LIXO):
        return None
    return e


def dominio_de(email):
    d = (email or "").split("@")[-1].lower().strip()
    return None if not d or d in PROVEDORES else d


def contador_provavel(email):
    """E-mail cadastrado na Receita muitas vezes é do escritório de contabilidade."""
    e = _norm(email)
    return any(x in e for x in ("contab", "contador", "escritorio", "assessoria", "fiscal@", "dp@", "rh@"))


def _get_json(url, timeout=12):
    try:
        r = requests.get(url, headers=UA, timeout=timeout)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        log.info("Consulta %s falhou: %s", url.split("/")[2], e)
    return None


def minha_receita(cnpj):
    d = _get_json(f"https://minhareceita.org/{cnpj}")
    if not d:
        return {}
    tels = [t for t in (d.get("ddd_telefone_1"), d.get("ddd_telefone_2")) if t and str(t).strip()]
    return {"email": _email_ok(d.get("email")), "telefones": tels}


def cnpj_ws(cnpj):
    d = _get_json(f"https://publica.cnpj.ws/cnpj/{cnpj}")
    est = (d or {}).get("estabelecimento") or {}
    tels = []
    for n in ("1", "2"):
        if est.get(f"ddd{n}") and est.get(f"telefone{n}"):
            tels.append(f"{est[f'ddd{n}']}{est[f'telefone{n}']}")
    return {"email": _email_ok(est.get("email")), "telefones": tels}


def _candidatos_dominio(razao, fantasia):
    """Domínios prováveis a partir do nome da empresa (ex.: 'Limpa Bem Serviços Ltda' -> limpabem.com.br)."""
    saida = []
    for nome in (fantasia, razao):
        palavras = [p for p in re.findall(r"[a-z0-9]+", _norm(nome)) if p not in PALAVRAS_VAZIAS]
        if not palavras:
            continue
        for base in ("".join(palavras[:3]), "".join(palavras[:2]), palavras[0]):
            if len(base) >= 4:
                for tld in (".com.br", ".com"):
                    d = base + tld
                    if d not in saida:
                        saida.append(d)
    return saida[:6]


def _resolve(dominio):
    try:
        socket.setdefaulttimeout(4)
        socket.gethostbyname(dominio)
        return True
    except Exception:
        return False


def tem_mx(dominio):
    """True/False se souber; None se a biblioteca de DNS não estiver disponível."""
    try:
        import dns.resolver
        return bool(dns.resolver.resolve(dominio, "MX", lifetime=5))
    except ImportError:
        return None
    except Exception:
        return False


def _pagina(url):
    try:
        r = requests.get(url, headers=UA, timeout=8, allow_redirects=True)
        if r.status_code == 200 and "text/html" in r.headers.get("content-type", ""):
            return r.text[:600000]
    except Exception:
        pass
    return None


def _confere_site(html, razao, fantasia, cnpj):
    """O site é mesmo da empresa? CNPJ na página ou palavras marcantes do nome."""
    t = _norm(re.sub(r"<[^>]+>", " ", html))
    digitos = re.sub(r"\D", "", t)
    if cnpj and cnpj in digitos:
        return True
    palavras = [p for p in re.findall(r"[a-z0-9]+", _norm(fantasia or razao)) if p not in PALAVRAS_VAZIAS and len(p) >= 4]
    return bool(palavras) and sum(1 for p in palavras[:3] if p in t) >= min(2, len(palavras[:3]))


def emails_do_site(dominio, razao, fantasia, cnpj, exigir_conferencia=True):
    for esquema in ("https://", "http://"):
        base = f"{esquema}{dominio}"
        home = _pagina(base) or _pagina(f"{esquema}www.{dominio}")
        if not home:
            continue
        if exigir_conferencia and not _confere_site(home, razao, fantasia, cnpj):
            return None, []
        achados = set()
        paginas = [home]
        for caminho in ("/contato", "/fale-conosco", "/contato/", "/contatos"):
            h = _pagina(base + caminho)
            if h:
                paginas.append(h)
                break
        for h in paginas:
            for e in RE_EMAIL.findall(h.replace("%40", "@").replace("[at]", "@").replace("(at)", "@")):
                ok = _email_ok(e)
                if ok:
                    achados.add(ok)
        # prioriza e-mails do próprio domínio
        return base, sorted(achados, key=lambda e: (not e.endswith("@" + dominio) and not e.endswith("." + dominio), e))[:8]
    return None, []


def buscar(p, rapido=False):
    """Monta a lista de contatos do prospect. Devolve {contatos, site, dominio, email_principal}."""
    contatos, vistos = [], set()

    def add(email, fonte, verificado, obs=None):
        e = _email_ok(email)
        if not e or e in vistos:
            return
        vistos.add(e)
        if contador_provavel(e) and not obs:
            obs = "Parece ser do escritório de contabilidade"
        contatos.append({"tipo": "email", "valor": e, "fonte": fonte, "verificado": verificado, "obs": obs})

    add(p.email_empresa, "Receita Federal (BrasilAPI)", True)
    telefones = [t for t in [p.telefone] if t]
    if not rapido:
        for fonte, fn in (("Minha Receita", minha_receita), ("CNPJ.ws", cnpj_ws)):
            if any(c["verificado"] and not c["obs"] for c in contatos):
                break  # já há e-mail público da empresa
            r = fn(p.cnpj)
            add(r.get("email"), fonte, True)
            telefones += [t for t in r.get("telefones", []) if t not in telefones]
            time.sleep(0.5)
    # domínio: do e-mail corporativo encontrado ou deduzido do nome
    dominio = next((dominio_de(c["valor"]) for c in contatos if dominio_de(c["valor"]) and not c["obs"]), None)
    site, deduzido = None, False
    if not rapido:
        candidatos = [dominio] if dominio else [d for d in _candidatos_dominio(p.razao_social, p.nome_fantasia) if _resolve(d)]
        for d in candidatos[:3]:
            base, achados = emails_do_site(d, p.razao_social, p.nome_fantasia, p.cnpj, exigir_conferencia=not dominio)
            if base:
                site, dominio = base, d
                for e in achados:
                    add(e, "Site da empresa", True)
                break
        if not dominio:  # sem site confirmado: domínio deduzido do nome, só se ele recebe e-mails
            for d in candidatos[:2]:
                if tem_mx(d):
                    dominio, deduzido = d, True
                    break
    # sugestões genéricas do domínio (quando não há e-mail público da própria empresa)
    if dominio and not any(c["verificado"] and not c["obs"] and c["valor"].endswith(dominio) for c in contatos):
        mx = tem_mx(dominio)
        if mx is not False:
            obs = ("Sugerido — domínio deduzido do nome da empresa; confirme antes de enviar" if deduzido else
                   "Sugerido — não verificado" + (" (o domínio recebe e-mails)" if mx else ""))
            for nome in GENERICOS:
                add(f"{nome}@{dominio}", "Sugerido pelo domínio", False, obs)
    principal = next((c["valor"] for c in contatos if c["verificado"] and not c["obs"]), None) \
        or next((c["valor"] for c in contatos if c["verificado"]), None) \
        or next((c["valor"] for c in contatos), None)
    return {"contatos": contatos, "telefones": telefones[:4], "site": site, "dominio": dominio, "dominio_deduzido": deduzido,
            "email_principal": principal}


def rascunho_email(p, link_relatorio, remetente="Daniel"):
    """E-mail de abordagem pronto, com os números públicos da própria empresa e opção de não receber contato."""
    nome = p.nome_fantasia or (p.razao_social or "").title()
    vit = (p.contratos or 0) + (p.atas or 0)
    seg = (p.segmentos or ["licitações"])[0]
    orgaos = list((p.orgaos or {}).keys())
    assunto = f"{nome}: {vit} {'vitória' if vit == 1 else 'vitórias'} em {seg} no PNCP — relatório gratuito"
    linhas = [
        "Olá, tudo bem?",
        "",
        f"Acompanhando o PNCP, vi que a {nome} venceu {vit} {'contratação' if vit == 1 else 'contratações'} de {seg} nos últimos meses"
        + (f", com {len(orgaos)} órgãos diferentes (entre eles {orgaos[0]})." if len(orgaos) >= 2 else "."),
        "",
        "Preparei um relatório gratuito com o histórico público de vocês, os concorrentes que mais aparecem no segmento "
        "e os editais abertos agora que combinam com a empresa:",
        link_relatorio,
        "",
        "O Kasiski procura esses editais todos os dias, lê o edital com inteligência artificial (requisitos, riscos, documentos "
        "que faltam, preço de referência) e organiza prazos, propostas e contratos. A conta é grátis.",
        "",
        "Se fizer sentido, posso mostrar em 15 minutos como isso funcionaria para vocês. Qual o melhor horário?",
        "",
        "Abraço,",
        f"{remetente} — Kasiski Public Market Intelligence",
        "kasiski.com.br",
        "",
        "Se preferir não receber contatos do Kasiski, é só responder \"não quero\" ou usar o link no fim do relatório.",
    ]
    return {"assunto": assunto[:150], "corpo": "\n".join(linhas)}
