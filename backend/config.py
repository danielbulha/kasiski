"""Configurações do Certame. Tudo vem de variáveis de ambiente (arquivo .env em dev)."""
import os
from dotenv import load_dotenv

load_dotenv()


def _lista(nome):
    return [x.strip().lower() for x in os.getenv(nome, "").split(",") if x.strip()]


class Config:
    # Produção = rodando no Render (RENDER=true) ou PRODUCAO=sim. Em produção o servidor se recusa a subir com chave
    # fraca e fecha CORS e webhook quando falta configuração (ver app.checar_seguranca).
    PRODUCAO = os.getenv("RENDER", "").lower() == "true" or os.getenv("PRODUCAO", "").lower() in ("sim", "1", "true")
    CHAVE_PADRAO = "troque-esta-chave-em-producao"
    SECRET_KEY = os.getenv("SECRET_KEY", CHAVE_PADRAO)

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

    # ------------------------------------------------------------ nota fiscal (prestador) — confirme com o contador
    NFSE_PRESTADOR_RAZAO = os.getenv("NFSE_PRESTADOR_RAZAO", "D.B.C. Consultoria e Serviços Ltda.")
    NFSE_PRESTADOR_CNPJ = os.getenv("NFSE_PRESTADOR_CNPJ", "01.152.886/0001-51")
    NFSE_PRESTADOR_MUNICIPIO = os.getenv("NFSE_PRESTADOR_MUNICIPIO", "São Paulo/SP")
    NFSE_PRESTADOR_IM = os.getenv("NFSE_PRESTADOR_IM", "")          # inscrição municipal (CCM) em São Paulo
    NFSE_CODIGO_SERVICO = os.getenv("NFSE_CODIGO_SERVICO", "")      # código do serviço definido pelo contador

    # ------------------------------------------------------------ cobrança (Mercado Pago)
    MP_ACCESS_TOKEN = os.getenv("MP_ACCESS_TOKEN", "")          # credencial de produção (APP_USR-...) ou de teste
    MP_WEBHOOK_SECRET = os.getenv("MP_WEBHOOK_SECRET", "")      # "assinatura secreta" do painel de webhooks
    FRONTEND_URL = os.getenv("FRONTEND_URL", "https://app.kasiski.com.br").rstrip("/")   # aplicativo (login, painel...)
    SITE_URL = os.getenv("SITE_URL", "https://kasiski.com.br").rstrip("/")               # site público (ferramentas, newsletter)
    BACKEND_URL = os.getenv("BACKEND_URL", "").rstrip("/")      # URL pública desta API (para o webhook)
    ANUAL_MESES_PAGOS = int(os.getenv("ANUAL_MESES_PAGOS", "10"))  # plano anual: paga 10, leva 12
    CARENCIA_DIAS = int(os.getenv("CARENCIA_DIAS", "3"))        # dias após o vencimento antes de suspender
    # Só para testes: e-mail do COMPRADOR de teste do Mercado Pago. Quando preenchido, é enviado no lugar
    # do e-mail do usuário (o Mercado Pago recusa misturar vendedor de teste com comprador real).
    MP_EMAIL_COMPRADOR_TESTE = os.getenv("MP_EMAIL_COMPRADOR_TESTE", "").strip()
    # ------------------------------------------------------------ e-mail (Resend) e verificação
    RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
    EMAIL_REMETENTE = os.getenv("EMAIL_REMETENTE", "Kasiski <nao-responda@kasiski.com.br>")
    # e-mails de prospecção enviados pelo Admin (as respostas voltam para esta caixa)
    PROSPECCAO_REMETENTE = os.getenv("PROSPECCAO_REMETENTE", "Daniel | Kasiski <daniel@kasiski.com.br>")
    PROSPECCAO_LIMITE_DIA = int(os.getenv("PROSPECCAO_LIMITE_DIA", "60"))   # teto diário (protege a reputação do domínio)
    # auto = exige o código só quando há como enviar e-mail (RESEND_API_KEY preenchida); sim / nao forçam
    VERIFICAR_EMAIL = os.getenv("VERIFICAR_EMAIL", "auto").lower()
    USD_BRL = float(os.getenv("USD_BRL", "5.5"))
    # ------------------------------------------------------------ ferramentas gratuitas do site (/api/public)
    PUBLICO_ANALISES_DIA = int(os.getenv("PUBLICO_ANALISES_DIA", "40"))       # teto global/dia (controle de custo de IA)
    PUBLICO_ANALISES_IP_DIA = int(os.getenv("PUBLICO_ANALISES_IP_DIA", "2"))  # por IP a cada 24h
    PUBLICO_ANALISES_EMAIL_MES = int(os.getenv("PUBLICO_ANALISES_EMAIL_MES", "2"))  # por e-mail a cada 30 dias
    PUBLICO_CONSULTAS_IP_DIA = int(os.getenv("PUBLICO_CONSULTAS_IP_DIA", "10"))    # consulta de concorrente por IP/24h
    PUBLICO_MAX_MB = int(os.getenv("PUBLICO_MAX_MB", "15"))
    PUBLICO_MAX_CHARS = int(os.getenv("PUBLICO_MAX_CHARS", "90000"))          # texto do edital enviado à IA na triagem
    TURNSTILE_SECRET = os.getenv("TURNSTILE_SECRET", "")                      # Cloudflare Turnstile (opcional)
    # ------------------------------------------------------------ automações de e-mail (onboarding/trial)
    # limites por IP (anti-abuso), contados no banco para valer entre os processos do servidor
    # cabeçalho com o IP real do visitante, gravado pelo proxy na frente da API (Render = Cloudflare)
    IP_CABECALHO = os.getenv("IP_CABECALHO", "CF-Connecting-IP")
    LOGIN_FALHAS_IP = int(os.getenv("LOGIN_FALHAS_IP", "20"))          # senhas erradas por IP a cada 15 min
    CADASTROS_IP_HORA = int(os.getenv("CADASTROS_IP_HORA", "5"))       # contas novas por IP a cada hora
    CODIGOS_IP_HORA = int(os.getenv("CODIGOS_IP_HORA", "15"))          # reenvios/verificações de código por IP a cada hora
    AUTOMACOES_ATIVAS = os.getenv("AUTOMACOES_ATIVAS", "sim").lower() in ("sim", "1", "true")
    AUTOMACOES_INTERVALO_S = int(os.getenv("AUTOMACOES_INTERVALO_S", "600"))
    # armazenamento contratado no Render (para o painel e o alerta de 70%)
    DB_LIMITE_GB = float(os.getenv("DB_LIMITE_GB", "1"))            # espaço do PostgreSQL (Database → Storage)
    DISCO_LIMITE_GB = os.getenv("DISCO_LIMITE_GB") or None          # vazio = lê o tamanho do disco montado
    # newsletter Kasiski Intelligence
    NEWSLETTER_RASCUNHO_AUTO = os.getenv("NEWSLETTER_RASCUNHO_AUTO", "sim").lower() in ("sim", "1", "true")  # rascunho toda segunda
    NEWSLETTER_MAX_PAGINAS = int(os.getenv("NEWSLETTER_MAX_PAGINAS", "60"))    # páginas de 50 por modalidade lidas no PNCP
    NEWSLETTER_VALOR_MAX = float(os.getenv("NEWSLETTER_VALOR_MAX", "20000000000"))  # ignora valores acima (erro de digitação)
    NEWSLETTER_LOTE = int(os.getenv("NEWSLETTER_LOTE", "100"))
    NEWSLETTER_PAUSA_S = float(os.getenv("NEWSLETTER_PAUSA_S", "0.6"))
    NEWSLETTER_RODAPE = os.getenv("NEWSLETTER_RODAPE", "Kasiski · D.B.C. Consultoria e Serviços Ltda. · Juquitiba/SP")                # câmbio para converter o custo de IA em R$
