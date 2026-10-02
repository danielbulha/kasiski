"""Backup do sistema (administrador).

- Banco: todas as tabelas em JSON Lines (uma linha por registro) dentro de um .zip, com um manifesto das contagens.
  Formato independente do banco (Postgres em produção, SQLite em desenvolvimento) e restaurável com
  scripts/restaurar_backup.py.
- Automático: uma vez por dia o servidor grava o backup do banco em BACKUP_DIR e mantém os últimos BACKUP_DIAS.
- Completo: banco + todos os arquivos enviados (UPLOAD_DIR), gerado na hora para o administrador baixar e guardar fora
  do servidor.

O backup automático fica no mesmo disco do servidor: protege contra exclusão acidental e erro de dados, não contra
perda do disco. Por isso o administrador deve baixar o backup completo de tempos em tempos.
"""
import base64
import json
import logging
import os
import zipfile
from datetime import date, datetime, timezone
from decimal import Decimal

from flask import current_app
from sqlalchemy import select

from extensions import db

log = logging.getLogger(__name__)
FORMATO = 1


def pasta():
    p = current_app.config["BACKUP_DIR"]
    os.makedirs(p, exist_ok=True)
    return p


def _valor(v):
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return str(v)
    if isinstance(v, (bytes, bytearray, memoryview)):
        return {"__b64__": base64.b64encode(bytes(v)).decode()}
    return v


def gravar_banco(z, prefixo="banco/"):
    """Escreve cada tabela em <prefixo><tabela>.jsonl no zip aberto. Devolve {tabela: registros}."""
    contagem = {}
    for t in db.metadata.sorted_tables:   # ordem de dependência: a restauração insere nesta ordem
        n = 0
        with z.open(f"{prefixo}{t.name}.jsonl", "w") as f:
            ordem = [t.c.id] if "id" in t.c else []
            for linha in db.session.execute(select(t).order_by(*ordem)).mappings().yield_per(1000):
                f.write((json.dumps({k: _valor(v) for k, v in linha.items()}, ensure_ascii=False) + "\n").encode())
                n += 1
        contagem[t.name] = n
    return contagem


def _manifesto(z, contagem, com_arquivos, arquivos=0):
    z.writestr("manifesto.json", json.dumps({
        "sistema": "Kasiski", "formato": FORMATO, "criado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "banco": db.engine.dialect.name, "tabelas": contagem, "registros": sum(contagem.values()),
        "com_arquivos": com_arquivos, "arquivos": arquivos,
        "ordem_restauracao": [t.name for t in db.metadata.sorted_tables],
    }, ensure_ascii=False, indent=2))


def criar_backup_banco(nome=None):
    """Grava o backup do banco em BACKUP_DIR. Devolve o caminho."""
    nome = nome or f"kasiski-banco-{datetime.utcnow():%Y-%m-%d-%H%M}.zip"
    destino = os.path.join(pasta(), nome)
    tmp = destino + ".parcial"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        _manifesto(z, gravar_banco(z), False)
    os.replace(tmp, destino)   # só aparece na lista quando está completo
    return destino


def criar_backup_completo(destino):
    """Banco + arquivos enviados, num zip em `destino` (para download pelo administrador)."""
    raiz = current_app.config["UPLOAD_DIR"]
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as z:
        contagem = gravar_banco(z)
        n = 0
        for base, _dirs, nomes in os.walk(raiz):
            for nome in nomes:
                caminho = os.path.join(base, nome)
                z.write(caminho, "arquivos/" + os.path.relpath(caminho, raiz))
                n += 1
        _manifesto(z, contagem, True, n)
    return destino


def enviar_temporario(caminho, nome):
    """Resposta que envia o zip em partes e apaga a cópia temporária assim que o envio termina (ou é interrompido)."""
    from urllib.parse import quote
    from flask import Response
    tamanho = os.path.getsize(caminho)

    def partes():
        try:
            with open(caminho, "rb") as f:
                while True:
                    bloco = f.read(1 << 16)
                    if not bloco:
                        break
                    yield bloco
        finally:
            try:
                os.remove(caminho)
            except OSError:
                pass
    return Response(partes(), mimetype="application/zip", direct_passthrough=True, headers={
        "Content-Length": str(tamanho),
        "Content-Disposition": f"attachment; filename=\"{nome}\"; filename*=UTF-8''{quote(nome)}"})


def limpar_temporarios(pasta_tmp, idade_s=3600):
    """Cópias temporárias que sobraram de downloads interrompidos (mais de 1 hora)."""
    import time
    for nome in os.listdir(pasta_tmp):
        caminho = os.path.join(pasta_tmp, nome)
        if nome.startswith("tmp") and nome.endswith(".zip") and time.time() - os.path.getmtime(caminho) > idade_s:
            try:
                os.remove(caminho)
            except OSError:
                pass


def listar():
    saida = []
    for nome in sorted(os.listdir(pasta()), reverse=True):
        if nome.startswith("kasiski-banco-") and nome.endswith(".zip"):
            caminho = os.path.join(pasta(), nome)
            saida.append({"nome": nome, "bytes": os.path.getsize(caminho),
                          "criado_em": datetime.utcfromtimestamp(os.path.getmtime(caminho)).isoformat(timespec="seconds")})
    return saida


def caminho_seguro(nome):
    """Só arquivos de backup desta pasta (nada de ../)."""
    if os.path.basename(nome) != nome or not (nome.startswith("kasiski-banco-") and nome.endswith(".zip")):
        return None
    caminho = os.path.join(pasta(), nome)
    return caminho if os.path.isfile(caminho) else None


def apagar_antigos():
    dias = current_app.config["BACKUP_DIAS"]
    automaticos = [b for b in listar() if b["nome"].startswith("kasiski-banco-auto-")]
    for b in automaticos[dias:]:
        try:
            os.remove(os.path.join(pasta(), b["nome"]))
        except OSError:
            pass


def automatico():
    """Backup diário (chamado pelo agendador do servidor). Vários processos podem chamar: só um grava por dia."""
    if not current_app.config.get("BACKUP_AUTOMATICO"):
        return None
    hoje = datetime.utcnow().strftime("%Y-%m-%d")
    nome = f"kasiski-banco-auto-{hoje}.zip"
    if os.path.exists(os.path.join(pasta(), nome)):
        return None
    trava = os.path.join(pasta(), f".trava-{hoje}")
    try:
        fd = os.open(trava, os.O_CREAT | os.O_EXCL | os.O_WRONLY)   # o primeiro processo do dia fica com o backup
        os.close(fd)
    except FileExistsError:
        return None
    try:
        caminho = criar_backup_banco(nome)
        apagar_antigos()
        for velho in os.listdir(pasta()):
            if velho.startswith(".trava-") and velho != f".trava-{hoje}":
                os.remove(os.path.join(pasta(), velho))
        log.info("Backup automático gravado: %s", caminho)
        return caminho
    except Exception:
        os.remove(trava)   # deixa tentar de novo no próximo ciclo
        raise
