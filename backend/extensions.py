from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class ErroAPI(Exception):
    """Erro com mensagem para o usuário e status HTTP."""

    def __init__(self, mensagem, status=400, codigo=None):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.status = status
        self.codigo = codigo
