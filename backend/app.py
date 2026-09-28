"""Certame — copiloto de licitações. Ponto de entrada do backend (Flask)."""
import logging
import os

from flask import Flask, jsonify
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

from config import Config
from extensions import ErroAPI, db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def create_app(config=Config):
    app = Flask(__name__)
    app.config.from_object(config)
    app.json.sort_keys = False  # preserva a ordem dos planos e de outras listas intencionais
    os.makedirs(app.config["UPLOAD_DIR"], exist_ok=True)

    checar_seguranca(app)
    CORS(app, resources={r"/api/*": {"origins": origens_cors(app)}}, expose_headers=["Content-Disposition"])
    db.init_app(app)

    from routes import registrar
    registrar(app)

    @app.before_request
    def _automacoes():  # só no servidor web (não nos jobs): a 1ª requisição liga o agendador de e-mails
        from services import automacoes
        automacoes.iniciar_agendador(app)

    @app.get("/api/saude")
    def saude():
        from services.llm import modo_demonstracao
        return jsonify({"ok": True, "modo_demonstracao": modo_demonstracao()})

    @app.after_request
    def _cabecalhos_seguranca(resp):
        """A API só devolve JSON, arquivos e redirecionamentos: nada dela deve rodar script nem ser emoldurado."""
        h = resp.headers
        h.setdefault("X-Content-Type-Options", "nosniff")
        h.setdefault("X-Frame-Options", "DENY")
        h.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        h.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'; base-uri 'none'")
        h.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        h.setdefault("Cross-Origin-Resource-Policy", "cross-origin")  # o pixel da newsletter é carregado nos e-mails
        if app.config.get("PRODUCAO"):
            h.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return resp

    from services import logs
    logs.instalar(app)

    @app.errorhandler(ErroAPI)
    def erro_api(e):
        if e.status >= 500:  # falhas de integração (Mercado Pago, IA, e-mail...) mostradas ao usuário
            logs.registrar("servidor", e.mensagem, getattr(e, "detalhe", None), status=e.status, nivel="aviso")
        return jsonify({"erro": e.mensagem, "codigo": e.codigo}), e.status

    @app.errorhandler(HTTPException)
    def erro_http(e):
        msgs = {404: "Não encontrado.", 405: "Operação não permitida.", 413: "Arquivo grande demais (máximo 40 MB)."}
        return jsonify({"erro": msgs.get(e.code, e.description)}), e.code

    @app.errorhandler(Exception)
    def erro_geral(e):
        db.session.rollback()
        app.logger.exception("Erro inesperado: %s", e)
        return jsonify({"erro": "Erro inesperado no servidor. Tente novamente."}), 500

    with app.app_context():
        db.create_all()
        _migrar_colunas_novas(app)
        from services import armazenamento
        armazenamento.criar_indices(app)
        import planos
        planos.migrar_tabela_2026(app)
    return app


def checar_seguranca(app):
    """Em produção: sem SECRET_KEY forte o servidor não sobe (qualquer um poderia forjar o login)."""
    cfg = app.config
    fraca = not cfg.get("SECRET_KEY") or cfg["SECRET_KEY"] == cfg.get("CHAVE_PADRAO") or len(cfg["SECRET_KEY"]) < 32
    if cfg.get("PRODUCAO") and fraca and os.getenv("KASISKI_JOB"):
        app.logger.error("SECRET_KEY ausente ou fraca no job agendado: configure a mesma chave do serviço web.")
    elif cfg.get("PRODUCAO") and fraca:
        raise RuntimeError("SECRET_KEY ausente, padrão ou curta demais (mínimo 32 caracteres). Defina-a nas variáveis de "
                           "ambiente do Render antes de subir o servidor.")
    if cfg.get("PRODUCAO") and cfg.get("MP_ACCESS_TOKEN") and not cfg.get("MP_WEBHOOK_SECRET"):
        app.logger.error("MP_WEBHOOK_SECRET vazio em produção: os avisos do Mercado Pago serão recusados até que a "
                         "assinatura secreta do webhook seja configurada.")


def origens_cors(app):
    """Origens liberadas no CORS. Em produção, '*' ou vazio viram só o app e o site oficiais."""
    cfg = app.config
    bruto = (cfg.get("CORS_ORIGINS") or "").strip()
    lista = [o.strip().rstrip("/") for o in bruto.split(",") if o.strip() and o.strip() != "*"]
    if cfg.get("PRODUCAO"):
        if not lista:
            lista = [u for u in (cfg.get("FRONTEND_URL"), cfg.get("SITE_URL")) if u]
            if cfg.get("SITE_URL", "").startswith("https://") and "://www." not in cfg["SITE_URL"]:
                lista.append(cfg["SITE_URL"].replace("https://", "https://www.", 1))
            app.logger.warning("CORS_ORIGINS vazio ou '*' em produção: liberando apenas %s", ", ".join(lista))
        return lista
    return lista or "*"


def _migrar_colunas_novas(app):
    """db.create_all() só cria tabelas que não existem — não adiciona colunas novas a
    tabelas já existentes (SQLite local ou Postgres em produção). Este helper faz esse
    ajuste mínimo sozinho, comparando o modelo com o banco e emitindo ALTER TABLE ADD
    COLUMN para o que estiver faltando. Suficiente para colunas simples (nosso caso);
    para mudanças maiores (renomear, remover), use uma migração de verdade (Alembic)."""
    from sqlalchemy import inspect, text
    insp = inspect(db.engine)
    for tabela in db.metadata.tables.values():
        if not insp.has_table(tabela.name):
            continue
        existentes = {c["name"] for c in insp.get_columns(tabela.name)}
        for coluna in tabela.columns:
            if coluna.name in existentes:
                continue
            tipo = coluna.type.compile(db.engine.dialect)
            with db.engine.begin() as conn:
                conn.execute(text(f'ALTER TABLE "{tabela.name}" ADD COLUMN "{coluna.name}" {tipo}'))
            app.logger.info("Migração: coluna %s.%s adicionada", tabela.name, coluna.name)


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=int(os.getenv("PORT", "5000")))
