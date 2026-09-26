"""Execução em segundo plano para tarefas de IA que podem passar do tempo máximo de uma requisição."""
import threading

from flask import current_app

from extensions import db


def rodar(fn, *args):
    app = current_app._get_current_object()

    def alvo():
        with app.app_context():
            try:
                fn(*args)
            finally:
                db.session.remove()
    threading.Thread(target=alvo, daemon=True).start()
