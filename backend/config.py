"""Configurações do Certame. Tudo vem de variáveis de ambiente (arquivo .env em dev)."""
import os
from dotenv import load_dotenv

load_dotenv()


def _lista(nome):
    return [x.strip().lower() for x in os.getenv(nome, "").split(",") if x.strip()]


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "troque-esta-chave-em-producao")

    _db = os.getenv("DATABASE_URL", "sqlite:///certame.db")
    if _db.startswith("postgres://"):  # Render entrega assim; SQLAlchemy exige postgresql://
        _db = _db.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_DATABASE_URI = _db
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    UPLOAD_DIR = os.getenv("UPLOAD_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads"))
    MAX_CONTENT_LENGTH = 40 * 1024 * 1024  # 40 MB por upload

    # Endereços separados por vírgula. A barra final é ignorada (o navegador nunca envia).
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")
    ADMIN_EMAILS = _lista("ADMIN_EMAILS")
    TOKEN_HORAS = int(os.getenv("TOKEN_HORAS", "72"))

    # Chaves de IA (deixe vazias para rodar em modo demonstração)
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

    MODELO_CLAUDE = os.getenv("MODELO_CLAUDE", "claude-sonnet-5")
    MODELO_CLAUDE_BARATO = os.getenv("MODELO_CLAUDE_BARATO", "claude-haiku-4-5-20251001")
    MODELO_OPENAI = os.getenv("MODELO_OPENAI", "gpt-4.1-mini")
    MODELO_GEMINI = os.getenv("MODELO_GEMINI", "gemini-2.5-flash")

    # Dados públicos
    PORTAL_TRANSPARENCIA_KEY = os.getenv("PORTAL_TRANSPARENCIA_KEY", "")

    # Limite de texto do edital enviado à IA (caracteres). ~180 mil ≈ 45 mil tokens.
    MAX_CHARS_DOCUMENTO = int(os.getenv("MAX_CHARS_DOCUMENTO", "180000"))

    # Serviço de advogado (R$) por tipo de peça: elaboração completa ou revisão da minuta da IA
    PRECO_REVISAO = {
        "esclarecimento": 290, "impugnacao": 690, "intencao_recurso": 190, "recurso": 990,
        "contrarrazoes": 890, "reequilibrio": 1490, "cobranca_pagamento": 490, "defesa_previa": 1190,
    }

    # ------------------------------------------------------------ cobrança (Mercado Pago)
    MP_ACCESS_TOKEN = os.getenv("MP_ACCESS_TOKEN", "")          # credencial de produção (APP_USR-...) ou de teste
    MP_WEBHOOK_SECRET = os.getenv("MP_WEBHOOK_SECRET", "")      # "assinatura secreta" do painel de webhooks
    FRONTEND_URL = os.getenv("FRONTEND_URL", "https://kasiski.netlify.app").rstrip("/")
    BACKEND_URL = os.getenv("BACKEND_URL", "").rstrip("/")      # URL pública desta API (para o webhook)
    ANUAL_MESES_PAGOS = int(os.getenv("ANUAL_MESES_PAGOS", "10"))  # plano anual: paga 10, leva 12
    CARENCIA_DIAS = int(os.getenv("CARENCIA_DIAS", "3"))        # dias após o vencimento antes de suspender
    # Só para testes: e-mail do COMPRADOR de teste do Mercado Pago. Quando preenchido, é enviado no lugar
    # do e-mail do usuário (o Mercado Pago recusa misturar vendedor de teste com comprador real).
    MP_EMAIL_COMPRADOR_TESTE = os.getenv("MP_EMAIL_COMPRADOR_TESTE", "").strip()
    # ------------------------------------------------------------ e-mail (Resend) e verificação
    RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
    EMAIL_REMETENTE = os.getenv("EMAIL_REMETENTE", "Kasiski <nao-responda@kasiski.com.br>")
    # auto = exige o código só quando há como enviar e-mail (RESEND_API_KEY preenchida); sim / nao forçam
    VERIFICAR_EMAIL = os.getenv("VERIFICAR_EMAIL", "auto").lower()
    USD_BRL = float(os.getenv("USD_BRL", "5.5"))                # câmbio para converter o custo de IA em R$
