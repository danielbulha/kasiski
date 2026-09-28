"""Armazenamento: índices de busca, limpeza automática e medição do banco e do disco.

- Índices: no PostgreSQL, a busca por palavras nas tabelas de preços (LIKE '%termo%') usa um índice trigram
  (extensão pg_trgm), que evita varrer centenas de milhares de linhas no plano pequeno do banco.
- Limpeza (job diário): itens de tabelas de preços desativadas há mais de 30 dias (a tabela fica no histórico,
  sem os itens; para voltar a usar, reimporte) e eventos de rastreamento com mais de 24 meses (política de privacidade).
- Medição: tamanho do banco e de cada tabela, uso do disco dos arquivos, com alerta a partir de 70%.
"""
import logging
import os
import shutil
from datetime import datetime, timedelta

from flask import current_app
from sqlalchemy import text

from extensions import db

log = logging.getLogger(__name__)
ALERTA_PCT = 70
DIAS_TABELA_INATIVA = 30
MESES_EVENTOS = 24


def _postgres():
    return db.engine.dialect.name == "postgresql"


def criar_indices(app):
    """Idempotente; roda na subida do servidor. Falha aqui nunca derruba o app."""
    comandos = ['CREATE INDEX IF NOT EXISTS ix_item_referencia_codigo ON item_referencia (tabela_id, codigo)',
                'CREATE INDEX IF NOT EXISTS ix_evento_criado_em ON evento (criado_em)']
    if _postgres():
        comandos = ["CREATE EXTENSION IF NOT EXISTS pg_trgm",
                    "CREATE INDEX IF NOT EXISTS ix_item_referencia_termos_trgm ON item_referencia USING gin (termos gin_trgm_ops)",
                    "CREATE INDEX IF NOT EXISTS ix_prospect_razao_trgm ON prospect USING gin (razao_social gin_trgm_ops)"] + comandos
    for sql in comandos:
        try:
            with db.engine.begin() as conn:
                conn.execute(text(sql))
        except Exception as e:  # ex.: sem permissão para criar extensão — a busca continua funcionando, só mais lenta
            app.logger.warning("Índice não criado (%s): %s", sql[:60], str(e).splitlines()[0][:200])


def limpar():
    """Limpeza do job diário. Devolve o que foi removido."""
    from models import Evento, ItemReferencia, TabelaReferencia
    agora = datetime.utcnow()
    saida = {"tabelas": 0, "itens": 0, "eventos": 0}
    for t in TabelaReferencia.query.filter(TabelaReferencia.ativa.is_(False), TabelaReferencia.desativada_em.isnot(None),
                                           TabelaReferencia.desativada_em < agora - timedelta(days=DIAS_TABELA_INATIVA),
                                           TabelaReferencia.itens_removidos_em.is_(None)):
        n = ItemReferencia.query.filter_by(tabela_id=t.id).delete(synchronize_session=False)
        t.itens_removidos_em = agora
        saida["tabelas"] += 1
        saida["itens"] += n
    saida["eventos"] = Evento.query.filter(Evento.criado_em < agora - timedelta(days=30 * MESES_EVENTOS)).delete(synchronize_session=False)
    db.session.commit()
    if _postgres() and (saida["itens"] > 20000 or saida["eventos"] > 50000):
        try:  # devolve o espaço para reuso (VACUUM não roda dentro de transação)
            with db.engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
                conn.execute(text("VACUUM (ANALYZE) item_referencia"))
                conn.execute(text("VACUUM (ANALYZE) evento"))
        except Exception as e:
            log.info("VACUUM não executado: %s", e)
    return saida


def _tamanho_pasta(caminho, limite_arquivos=200000):
    total, n = 0, 0
    for raiz, _, arquivos in os.walk(caminho):
        for a in arquivos:
            try:
                total += os.path.getsize(os.path.join(raiz, a))
            except OSError:
                pass
            n += 1
            if n >= limite_arquivos:
                return total, n
    return total, n


def medir():
    """Uso do banco (total e por tabela) e do disco de arquivos."""
    cfg = current_app.config
    limite_db = float(cfg.get("DB_LIMITE_GB") or 1) * 1024 ** 3
    tabelas = []
    if _postgres():
        total = db.session.execute(text("SELECT pg_database_size(current_database())")).scalar() or 0
        linhas = db.session.execute(text(
            "SELECT c.relname, pg_total_relation_size(c.oid), GREATEST(c.reltuples, 0)::bigint FROM pg_class c "
            "JOIN pg_namespace n ON n.oid = c.relnamespace WHERE c.relkind = 'r' AND n.nspname = 'public' "
            "ORDER BY 2 DESC LIMIT 15")).fetchall()
        tabelas = [{"tabela": r[0], "bytes": int(r[1] or 0), "linhas": int(r[2] or 0)} for r in linhas]
    else:
        caminho = db.engine.url.database or ""
        total = os.path.getsize(caminho) if caminho and os.path.exists(caminho) else 0
        for nome in db.metadata.tables:
            try:
                n = db.session.execute(text(f'SELECT COUNT(*) FROM "{nome}"')).scalar()
            except Exception:
                db.session.rollback()
                continue
            tabelas.append({"tabela": nome, "bytes": None, "linhas": int(n or 0)})
        tabelas.sort(key=lambda x: -x["linhas"])
        tabelas = tabelas[:15]
    pasta = cfg.get("UPLOAD_DIR") or "uploads"
    try:
        du = shutil.disk_usage(pasta)
        disco_total, disco_usado = du.total, du.used
    except OSError:
        disco_total = disco_usado = 0
    arquivos_bytes, arquivos_n = _tamanho_pasta(pasta) if os.path.isdir(pasta) else (0, 0)
    pct = lambda usado, lim: round(usado / lim * 100, 1) if lim else None
    banco = {"usado": int(total), "limite": int(limite_db), "pct": pct(total, limite_db), "tabelas": tabelas}
    if cfg.get("DISCO_LIMITE_GB"):  # limite informado: mede só a pasta de arquivos do Kasiski
        disco = {"usado": int(arquivos_bytes), "limite": int(float(cfg["DISCO_LIMITE_GB"]) * 1024 ** 3)}
    else:  # disco próprio do Render montado em /var/data: o sistema operacional informa o total e o usado
        disco = {"usado": int(disco_usado), "limite": int(disco_total)}
    disco["arquivos"], disco["bytes_arquivos"] = arquivos_n, int(arquivos_bytes)
    disco["pct"] = pct(disco["usado"], disco["limite"])
    alertas = []
    if banco["pct"] is not None and banco["pct"] >= ALERTA_PCT:
        alertas.append(f"O banco de dados está com {banco['pct']:.0f}% do espaço contratado. Aumente o armazenamento do "
                       "PostgreSQL no Render (Database → Storage) e ajuste DB_LIMITE_GB.")
    if disco["pct"] is not None and disco["pct"] >= ALERTA_PCT:
        alertas.append(f"O disco de arquivos está com {disco['pct']:.0f}% de uso. Aumente o disco no Render "
                       "(serviço da API → Disks) e ajuste DISCO_LIMITE_GB.")
    from models import TabelaReferencia
    inativas = [t.to_dict() for t in TabelaReferencia.query.filter(TabelaReferencia.ativa.is_(False),
                                                                    TabelaReferencia.itens_removidos_em.is_(None))]
    return {"banco": banco, "disco": disco, "alertas": alertas, "tabelas_inativas": inativas,
            "limpeza": {"dias_tabela_inativa": DIAS_TABELA_INATIVA, "meses_eventos": MESES_EVENTOS}, "medido_em": datetime.utcnow().isoformat() + "Z"}


def avisar_se_preciso():
    """Job diário: e-mail aos admins quando banco ou disco passam de 70% (no máximo 1 aviso a cada 3 dias)."""
    from models import Evento
    from services import email as em
    m = medir()
    if not m["alertas"] or not em.configurado():
        return m
    recente = Evento.query.filter(Evento.tipo == "alerta_armazenamento",
                                  Evento.criado_em > datetime.utcnow() - timedelta(days=3)).first()
    if recente:
        return m
    corpo = em.layout_marketing("Armazenamento do Kasiski perto do limite",
                                "".join(f"<p>{em.esc(a)}</p>" for a in m["alertas"]),
                                "Ver o painel", f"{current_app.config.get('FRONTEND_URL')}/#/admin")
    for para in current_app.config.get("ADMIN_EMAILS") or []:
        try:
            em.enviar(para, "Kasiski: armazenamento perto do limite", "\n".join(m["alertas"]), corpo)
        except Exception:
            log.warning("Falha ao avisar sobre o armazenamento")
    db.session.add(Evento(tipo="alerta_armazenamento", dados={"alertas": m["alertas"]}))
    db.session.commit()
    return m
