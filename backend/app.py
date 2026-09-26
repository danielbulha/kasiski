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

    origens = app.config["CORS_ORIGINS"]
    CORS(app, resources={r"/api/*": {"origins": origens if origens == "*" else [o.strip().rstrip("/") for o in origens.split(",") if o.strip()]}},
         expose_headers=["Content-Disposition"])
    db.init_app(app)

    from routes import registrar
    registrar(app)

    @app.get("/api/saude")
    def saude():
        from services.llm import modo_demonstracao
        return jsonify({"ok": True, "modo_demonstracao": modo_demonstracao()})

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
    return app


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
