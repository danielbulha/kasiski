"""Restaura um backup do Kasiski (services/backup.py) num banco VAZIO.

Uso (na pasta backend, com DATABASE_URL apontando para o banco de destino):
    python scripts/restaurar_backup.py kasiski-banco-2026-10-02-0300.zip
    python scripts/restaurar_backup.py kasiski-completo-2026-10-02-0300.zip --arquivos   # também copia os arquivos

Segurança: recusa restaurar num banco que já tem contas, para não misturar nem sobrescrever dados. Para substituir um
banco existente, crie um banco novo, restaure nele e só depois troque o DATABASE_URL do servidor.
"""
import argparse
import base64
import json
import os
import sys
import zipfile
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("AUTOMACOES_ATIVAS", "nao")

from sqlalchemy import Date, DateTime, text  # noqa: E402

from app import app  # noqa: E402
from extensions import db  # noqa: E402


def _converter(col, v):
    if v is None:
        return None
    if isinstance(v, dict) and "__b64__" in v:
        return base64.b64decode(v["__b64__"])
    if isinstance(col.type, DateTime) and isinstance(v, str):
        return datetime.fromisoformat(v)
    if isinstance(col.type, Date) and isinstance(v, str):
        return date.fromisoformat(v)
    return v


def restaurar(zip_path, com_arquivos=False):
    with app.app_context():
        db.create_all()
        tem_dados = db.session.execute(text("select count(*) from conta")).scalar()
        if tem_dados:
            raise SystemExit("O banco de destino já tem contas. Restaure num banco vazio (veja o cabeçalho deste script).")
        with zipfile.ZipFile(zip_path) as z:
            manifesto = json.loads(z.read("manifesto.json"))
            nomes = set(z.namelist())
            tabelas = {t.name: t for t in db.metadata.sorted_tables}
            total = 0
            for nome in manifesto["ordem_restauracao"]:
                t = tabelas.get(nome)
                arq = f"banco/{nome}.jsonl"
                if t is None or arq not in nomes:
                    print(f"  pulando {nome} (não existe nesta versão)")
                    continue
                lote = []
                with z.open(arq) as f:
                    for linha in f:
                        d = json.loads(linha)
                        lote.append({c.name: _converter(c, d.get(c.name)) for c in t.columns if c.name in d})
                        if len(lote) >= 1000:
                            db.session.execute(t.insert(), lote); total += len(lote); lote = []
                if lote:
                    db.session.execute(t.insert(), lote); total += len(lote)
            db.session.commit()
            if db.engine.dialect.name == "postgresql":   # próximos ids continuam depois dos restaurados
                for t in tabelas.values():
                    if "id" in t.c and t.c.id.autoincrement:
                        db.session.execute(text(
                            f"select setval(pg_get_serial_sequence('\"{t.name}\"', 'id'), coalesce(max(id), 1)) from \"{t.name}\""))
                db.session.commit()
            print(f"Banco restaurado: {total} registros de {manifesto['criado_em']}.")
            if com_arquivos:
                if not manifesto.get("com_arquivos"):
                    print("Este backup não tem arquivos (é só do banco).")
                    return
                raiz = os.path.realpath(app.config["UPLOAD_DIR"])
                n = 0
                for nome in nomes:
                    if not nome.startswith("arquivos/") or nome.endswith("/"):
                        continue
                    destino = os.path.realpath(os.path.join(raiz, nome[len("arquivos/"):]))
                    if not destino.startswith(raiz + os.sep):
                        continue   # nunca escreve fora da pasta de uploads
                    os.makedirs(os.path.dirname(destino), exist_ok=True)
                    with z.open(nome) as src, open(destino, "wb") as dst:
                        dst.write(src.read())
                    n += 1
                print(f"Arquivos restaurados: {n} em {raiz}.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("backup")
    ap.add_argument("--arquivos", action="store_true", help="copiar também os arquivos enviados (backup completo)")
    a = ap.parse_args()
    restaurar(a.backup, a.arquivos)
