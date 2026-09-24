"""Roteador de IAs.

Regra do produto (a mesma do Cournot):
- tarefas de busca/extração vão para a IA mais barata;
- a análise jurídica fica com a Claude;
- a verificação cruzada usa um modelo de OUTRO fornecedor sempre que houver chave.

Sem nenhuma chave configurada o app roda em modo demonstração, devolvendo respostas de exemplo.
"""
import json
import logging
import re
from dataclasses import dataclass

import requests
from flask import current_app

log = logging.getLogger(__name__)

# US$ por milhão de tokens (entrada, saída). Ajuste conforme a tabela vigente de cada fornecedor.
PRECOS = {"claude": (3.0, 15.0), "claude_barato": (1.0, 5.0), "openai": (0.4, 1.6), "gemini": (0.3, 2.5)}
FAMILIA = {"claude": "anthropic", "claude_barato": "anthropic", "openai": "openai", "gemini": "google"}

ROTAS = {
    "barata": ["gemini", "openai", "claude_barato"],
    "analise": ["claude", "openai", "gemini"],
    "redacao": ["claude", "openai", "gemini"],
    "verificacao": ["openai", "gemini", "claude_barato"],
}


@dataclass
class RespostaIA:
    texto: str
    provedor: str
    modelo: str
    tokens_entrada: int = 0
    tokens_saida: int = 0
    custo_usd: float = 0.0

    @property
    def demonstracao(self):
        return self.provedor == "demonstracao"

    @property
    def familia(self):
        return FAMILIA.get(self.provedor)


def _cfg(nome):
    return current_app.config.get(nome, "")


def disponivel(provedor):
    chaves = {"claude": "ANTHROPIC_API_KEY", "claude_barato": "ANTHROPIC_API_KEY",
              "openai": "OPENAI_API_KEY", "gemini": "GEMINI_API_KEY"}
    return bool(_cfg(chaves[provedor]))


def modo_demonstracao():
    return not any(disponivel(p) for p in PRECOS)


def _modelo(provedor):
    return {"claude": _cfg("MODELO_CLAUDE"), "claude_barato": _cfg("MODELO_CLAUDE_BARATO"),
            "openai": _cfg("MODELO_OPENAI"), "gemini": _cfg("MODELO_GEMINI")}[provedor]


def _anthropic(modelo, sistema, usuario, max_tokens, json_saida):
    r = requests.post("https://api.anthropic.com/v1/messages", timeout=300, headers={
        "x-api-key": _cfg("ANTHROPIC_API_KEY"), "anthropic-version": "2023-06-01",
        "content-type": "application/json"},
        json={"model": modelo, "max_tokens": max_tokens, "system": sistema,
              "messages": [{"role": "user", "content": usuario}]})
    r.raise_for_status()
    d = r.json()
    texto = "".join(b.get("text", "") for b in d.get("content", []) if b.get("type") == "text")
    u = d.get("usage", {})
    return texto, u.get("input_tokens", 0), u.get("output_tokens", 0)


def _openai(modelo, sistema, usuario, max_tokens, json_saida):
    corpo = {"model": modelo, "max_completion_tokens": max_tokens,
             "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": usuario}]}
    if json_saida:
        corpo["response_format"] = {"type": "json_object"}
    r = requests.post("https://api.openai.com/v1/chat/completions", timeout=300,
                      headers={"Authorization": f"Bearer {_cfg('OPENAI_API_KEY')}"}, json=corpo)
    r.raise_for_status()
    d = r.json()
    u = d.get("usage", {})
    return d["choices"][0]["message"]["content"] or "", u.get("prompt_tokens", 0), u.get("completion_tokens", 0)


def _gemini(modelo, sistema, usuario, max_tokens, json_saida):
    conf = {"maxOutputTokens": max_tokens}
    if json_saida:
        conf["responseMimeType"] = "application/json"
    r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent",
                      params={"key": _cfg("GEMINI_API_KEY")}, timeout=300,
                      json={"systemInstruction": {"parts": [{"text": sistema}]},
                            "contents": [{"role": "user", "parts": [{"text": usuario}]}],
                            "generationConfig": conf})
    r.raise_for_status()
    d = r.json()
    partes = d.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    u = d.get("usageMetadata", {})
    return ("".join(p.get("text", "") for p in partes), u.get("promptTokenCount", 0),
            u.get("candidatesTokenCount", 0))


_CHAMADAS = {"claude": _anthropic, "claude_barato": _anthropic, "openai": _openai, "gemini": _gemini}


def chamar(tarefa, sistema, usuario, max_tokens=4000, json_saida=True, demo=None, evitar_familia=None):
    """Chama a primeira IA disponível da rota. Na verificação, prefere outra família de modelo."""
    rota = list(ROTAS[tarefa])
    if evitar_familia:
        rota = ([p for p in rota if FAMILIA[p] != evitar_familia] +
                [p for p in rota if FAMILIA[p] == evitar_familia])
    if json_saida:
        sistema += ("\n\nResponda SOMENTE com um objeto JSON válido, sem texto antes ou depois "
                    "e sem blocos de código.")
    erros = []
    for prov in rota:
        if not disponivel(prov):
            continue
        modelo = _modelo(prov)
        try:
            texto, tin, tout = _CHAMADAS[prov](modelo, sistema, usuario, max_tokens, json_saida)
            pin, pout = PRECOS[prov]
            return RespostaIA(texto, prov, modelo, tin, tout, round(tin / 1e6 * pin + tout / 1e6 * pout, 5))
        except Exception as e:  # tenta o próximo fornecedor da rota
            log.warning("Falha em %s (%s): %s", prov, modelo, e)
            erros.append(f"{prov}: {e}")
    if erros:
        raise RuntimeError("Nenhuma IA respondeu. " + " | ".join(erros))
    texto = json.dumps(demo, ensure_ascii=False) if json_saida else (demo or "")
    return RespostaIA(texto, "demonstracao", "demonstracao")


def extrair_json(texto):
    """Extrai o JSON da resposta, tolerando cercas de código e texto ao redor."""
    t = re.sub(r"```(?:json)?", "", texto or "").strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass
    inicios = [i for i in (t.find("{"), t.find("[")) if i >= 0]
    ini = min(inicios) if inicios else -1
    fim = max(t.rfind("}"), t.rfind("]"))
    if ini < 0 or fim <= ini:
        raise ValueError("A IA não devolveu JSON válido.")
    return json.loads(t[ini:fim + 1])
