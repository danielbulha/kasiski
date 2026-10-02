"""Backup dos dados do cliente: tudo o que é da conta, num .zip para guardar no computador.

Conteúdo:
- dados/<tabela>.json — todos os registros da conta (empresas, editais, documentos, contratos, prazos, peças,
  propostas, salas de disputa, concorrentes, análises...), achados seguindo as chaves estrangeiras a partir da conta;
- planilhas/<tabela>.csv — as mesmas tabelas em planilha (abre no Excel), com separador ";";
- arquivos/<tabela>/<id>-<nome> — os arquivos enviados (PDFs do cofre, editais, contratos...).

Nunca vão para o arquivo: senhas, tokens, códigos e hashes, identificadores internos de pagamento e IPs.
"""
import csv
import io
import json
import os
import re
import zipfile
from datetime import datetime, timezone

from flask import current_app
from sqlalchemy import select

from extensions import db
from services.backup import _valor

# tabelas internas (segurança, custo, controle) que não fazem parte dos dados do cliente
FORA = {"codigo_verificacao", "vinculo_extensao", "membro_conta", "uso_ia", "automacao_envio", "trial_cnpj"}
# colunas que nunca saem do sistema
SEGREDO = re.compile(r"senha|token|hash|segredo|secret|^mp_|_mp_|_ip$|^ip_|falhas_login|bloqueado_ate|_crm$", re.I)


def _colunas(t):
    return [c for c in t.columns if not SEGREDO.search(c.name)]


def coletar(conta_id):
    """{tabela: [linhas]} com tudo o que depende da conta (descendo pelas chaves estrangeiras)."""
    conta = db.metadata.tables["conta"]
    dados, fila, vistos = {}, [(conta, [conta_id])], set()
    while fila:
        tabela, ids = fila.pop(0)
        ids = [i for i in ids if (tabela.name, i) not in vistos]
        if not ids:
            continue
        vistos.update((tabela.name, i) for i in ids)
        cols = _colunas(tabela)
        linhas = [dict(r) for r in db.session.execute(select(*cols).where(tabela.c.id.in_(ids))).mappings()]
        dados.setdefault(tabela.name, []).extend(linhas)
        for filha in db.metadata.sorted_tables:
            if filha.name in FORA or "id" not in filha.c:
                continue
            for fk in filha.foreign_keys:
                if fk.column.table is tabela:
                    filhos = [r[0] for r in db.session.execute(select(filha.c.id).where(fk.parent.in_(ids)))]
                    if filhos:
                        fila.append((filha, filhos))
    for linhas in dados.values():
        linhas.sort(key=lambda r: r.get("id") or 0)
    return dados


def _nome_arquivo(t, linha):
    base = re.sub(r"[^\w.\- ]", "_", linha.get("nome_arquivo") or os.path.basename(linha["arquivo"]))[:120]
    return f"arquivos/{t}/{linha['id']}-{base}"


def gerar(conta, destino):
    """Escreve o zip em `destino`. Devolve um resumo (tabelas, registros, arquivos)."""
    dados = coletar(conta.id)
    raiz = os.path.realpath(current_app.config["UPLOAD_DIR"])
    n_arquivos, faltando = 0, []
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as z:
        for tabela, linhas in sorted(dados.items()):
            serial = [{k: _valor(v) for k, v in l.items()} for l in linhas]
            z.writestr(f"dados/{tabela}.json", json.dumps(serial, ensure_ascii=False, indent=2))
            if serial:
                buf = io.StringIO()
                cab = list(serial[0].keys())
                w = csv.DictWriter(buf, fieldnames=cab, delimiter=";", extrasaction="ignore")
                w.writeheader()
                for l in serial:
                    w.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for k, v in l.items()})
                z.writestr(f"planilhas/{tabela}.csv", "﻿" + buf.getvalue())   # BOM: o Excel abre com acentos
            for l in linhas:
                rel = l.get("arquivo")
                if not rel or not isinstance(rel, str):
                    continue
                caminho = os.path.realpath(os.path.join(raiz, rel))
                if not caminho.startswith(raiz + os.sep):
                    continue   # nunca lê fora da pasta de uploads
                if os.path.isfile(caminho):
                    z.write(caminho, _nome_arquivo(tabela, l))
                    n_arquivos += 1
                else:
                    faltando.append(rel)
        resumo = {"conta": conta.nome, "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                  "tabelas": {t: len(l) for t, l in sorted(dados.items())}, "arquivos": n_arquivos,
                  "arquivos_nao_encontrados": len(faltando)}
        z.writestr("LEIA-ME.txt", (
            f"Backup dos dados da conta \"{conta.nome}\" no Kasiski\nGerado em {resumo['gerado_em']} (UTC)\n\n"
            "dados/      todos os registros da conta, em JSON\n"
            "planilhas/  as mesmas tabelas em CSV (abra no Excel; separador ponto e vírgula)\n"
            "arquivos/   os arquivos enviados (documentos do cofre, editais, contratos...)\n\n"
            f"Registros por tabela: {json.dumps(resumo['tabelas'], ensure_ascii=False)}\n"
            f"Arquivos incluídos: {n_arquivos}\n\n"
            "Senhas, tokens e dados internos de pagamento não são incluídos.\n"))
        z.writestr("resumo.json", json.dumps(resumo, ensure_ascii=False, indent=2))
    return resumo
