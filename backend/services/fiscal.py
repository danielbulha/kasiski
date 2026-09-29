"""Dados do tomador para a Nota Fiscal de Serviço (NFS-e) e apoio ao faturamento.

O Kasiski não emite a nota sozinho (ainda): guarda os dados do cliente, exige que estejam completos
antes do pagamento e entrega ao administrador a lista de pagamentos a faturar (tela e CSV).
Prestador: D.B.C. Consultoria e Serviços Ltda., São Paulo/SP — configurável por variáveis de ambiente.
"""
import logging
import re

import requests
from flask import current_app

from extensions import ErroAPI

log = logging.getLogger(__name__)
UA = {"User-Agent": "Kasiski/1.0 (+https://kasiski.com.br)"}
UFS = {"AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI",
       "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"}
OBRIGATORIOS = ("documento", "nome", "email", "cep", "logradouro", "numero", "bairro", "municipio", "uf")
CAMPOS = OBRIGATORIOS + ("complemento", "inscricao_municipal", "codigo_ibge")


def so_digitos(v):
    return re.sub(r"\D", "", str(v or ""))


def cpf_valido(c):
    c = so_digitos(c)
    if len(c) != 11 or c == c[0] * 11:
        return False
    for n in (9, 10):
        s = sum(int(c[i]) * (n + 1 - i) for i in range(n))
        if int(c[n]) != (s * 10 % 11) % 10:
            return False
    return True


def cnpj_valido(c):
    c = so_digitos(c)
    if len(c) != 14 or c == c[0] * 14:
        return False
    def dv(base, pesos):
        r = sum(int(x) * p for x, p in zip(base, pesos)) % 11
        return "0" if r < 2 else str(11 - r)
    p1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    return c[12] == dv(c[:12], p1) and c[13] == dv(c[:13], [6] + p1)


def formatar_documento(d):
    d = so_digitos(d)
    if len(d) == 14:
        return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"
    if len(d) == 11:
        return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"
    return d


def normalizar(d):
    """Valida e limpa os dados enviados pelo formulário. Levanta ErroAPI com a mensagem do campo."""
    d = {k: (str(d.get(k) or "").strip())[:200] for k in CAMPOS}
    doc = so_digitos(d["documento"])
    if not (cpf_valido(doc) or cnpj_valido(doc)):
        raise ErroAPI("CPF ou CNPJ inválido. Confira os números.", 400, "documento_invalido")
    d["documento"] = doc
    d["tipo"] = "pj" if len(doc) == 14 else "pf"
    if not d["nome"]:
        raise ErroAPI("Informe o nome ou a razão social que vai na nota.")
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", d["email"]):
        raise ErroAPI("Informe um e-mail válido para receber a nota fiscal.")
    d["email"] = d["email"].lower()
    d["cep"] = so_digitos(d["cep"])
    if len(d["cep"]) != 8:
        raise ErroAPI("CEP inválido: use 8 números.")
    d["uf"] = d["uf"].upper()
    if d["uf"] not in UFS:
        raise ErroAPI("Informe a UF do endereço (ex.: SP).")
    for campo, rotulo in (("logradouro", "o endereço"), ("numero", "o número (use S/N se não houver)"),
                          ("bairro", "o bairro"), ("municipio", "a cidade")):
        if not d[campo]:
            raise ErroAPI(f"Informe {rotulo}.")
    d["codigo_ibge"] = so_digitos(d["codigo_ibge"])[:7]
    return d


def completo(conta):
    f = conta.dados_fiscais or {}
    return all(f.get(k) for k in OBRIGATORIOS) and (cpf_valido(f.get("documento")) or cnpj_valido(f.get("documento")))


def exigir(conta):
    """Chamado antes de gerar qualquer link de pagamento."""
    if not completo(conta):
        raise ErroAPI("Antes do pagamento, preencha os dados para a nota fiscal (CPF ou CNPJ, nome e endereço). "
                      "Leva menos de um minuto.", 400, "dados_fiscais")


def publico(conta):
    f = dict(conta.dados_fiscais or {})
    if f.get("documento"):
        f["documento_formatado"] = formatar_documento(f["documento"])
    return {"dados": f, "completo": completo(conta)}


# ---------------------------------------------------------------- preenchimento automático
def buscar_cep(cep):
    cep = so_digitos(cep)
    if len(cep) != 8:
        raise ErroAPI("CEP inválido: use 8 números.")
    try:
        r = requests.get(f"https://viacep.com.br/ws/{cep}/json/", headers=UA, timeout=10)
        j = r.json() if r.ok else {}
        if j and not j.get("erro"):
            return {"cep": cep, "logradouro": j.get("logradouro") or "", "bairro": j.get("bairro") or "",
                    "municipio": j.get("localidade") or "", "uf": j.get("uf") or "", "codigo_ibge": j.get("ibge") or ""}
    except Exception as e:
        log.info("ViaCEP falhou: %s", e)
    try:
        r = requests.get(f"https://brasilapi.com.br/api/cep/v2/{cep}", headers=UA, timeout=10)
        if r.ok:
            j = r.json()
            return {"cep": cep, "logradouro": j.get("street") or "", "bairro": j.get("neighborhood") or "",
                    "municipio": j.get("city") or "", "uf": j.get("state") or "", "codigo_ibge": ""}
    except Exception as e:
        log.info("BrasilAPI CEP falhou: %s", e)
    raise ErroAPI("Não encontramos esse CEP. Preencha o endereço manualmente.", 404, "cep_nao_encontrado")


def buscar_cnpj(cnpj):
    cnpj = so_digitos(cnpj)
    if not cnpj_valido(cnpj):
        raise ErroAPI("CNPJ inválido. Confira os números.")
    try:
        r = requests.get(f"https://brasilapi.com.br/api/cnpj/v1/{cnpj}", headers=UA, timeout=20)
        if r.status_code == 404:
            raise ErroAPI("CNPJ não encontrado na Receita Federal.", 404)
        r.raise_for_status()
        j = r.json()
    except ErroAPI:
        raise
    except Exception as e:
        log.info("BrasilAPI CNPJ falhou: %s", e)
        raise ErroAPI("A consulta à Receita está indisponível agora. Preencha os dados manualmente.", 502)
    tipo_log = (j.get("descricao_tipo_de_logradouro") or "").strip()
    logradouro = " ".join(x for x in (tipo_log, (j.get("logradouro") or "").strip()) if x)
    return {"documento": cnpj, "nome": j.get("razao_social") or "", "cep": so_digitos(j.get("cep")),
            "logradouro": logradouro.title() if logradouro.isupper() else logradouro,
            "numero": (j.get("numero") or "").strip(), "complemento": (j.get("complemento") or "").strip(),
            "bairro": (j.get("bairro") or "").strip().title(), "municipio": (j.get("municipio") or "").strip().title(),
            "uf": (j.get("uf") or "").strip().upper(), "codigo_ibge": str(j.get("codigo_municipio_ibge") or ""),
            "email_receita": (j.get("email") or "").strip().lower(),
            "situacao": j.get("descricao_situacao_cadastral")}


# ---------------------------------------------------------------- faturamento (admin)
def prestador():
    cfg = current_app.config
    return {"razao_social": cfg.get("NFSE_PRESTADOR_RAZAO"), "cnpj": cfg.get("NFSE_PRESTADOR_CNPJ"),
            "municipio": cfg.get("NFSE_PRESTADOR_MUNICIPIO"), "codigo_servico": cfg.get("NFSE_CODIGO_SERVICO"),
            "inscricao_municipal": cfg.get("NFSE_PRESTADOR_IM")}


def discriminacao(c):
    """Texto sugerido para o campo 'discriminação do serviço' da nota."""
    quando = c.pago_em.strftime("%d/%m/%Y") if c.pago_em else ""
    if c.tipo == "assinatura" and c.plano not in (None, "empresas_extras", "pacote_contratos"):
        base = "Licença de uso do software Kasiski (SaaS de inteligência em licitações)"
        detalhe = f" — {c.descricao}" if c.descricao else ""
    else:
        base = c.descricao or "Serviço Kasiski"
        detalhe = ""
    ref = f" Pagamento em {quando}" + (f", transação Mercado Pago {c.mp_pagamento_id}" if c.mp_pagamento_id else "") + "."
    return (base + detalhe + "." + ref)[:1000]


def situacao_nf(c):
    if c.nf_status == "emitida" and c.status in ("estornado", "cancelado"):
        return "cancelar"
    if c.nf_status:
        return c.nf_status
    return "pendente" if c.status == "aprovado" else None


def linha(c, conta):
    t = c.nf_tomador or (conta.dados_fiscais if conta else None) or {}
    return {"id": c.id, "conta_id": c.conta_id, "conta": conta.nome if conta else None, "pago_em": c.pago_em.isoformat() if c.pago_em else None,
            "valor": c.valor, "meio": c.meio, "tipo": c.tipo, "plano": c.plano, "ciclo": c.ciclo, "status_pagamento": c.status,
            "mp_pagamento_id": c.mp_pagamento_id, "descricao": c.descricao, "discriminacao": discriminacao(c),
            "nf_status": situacao_nf(c), "nf_numero": c.nf_numero, "nf_obs": c.nf_obs,
            "nf_emitida_em": c.nf_emitida_em.isoformat() if c.nf_emitida_em else None,
            "tomador": {**t, "documento_formatado": formatar_documento(t.get("documento"))} if t else None,
            "tomador_completo": all(t.get(k) for k in OBRIGATORIOS) if t else False}
