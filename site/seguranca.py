"""Cabeçalhos de segurança dos dois sites no Netlify (arquivo _headers).

Mantidos num só lugar: `site/gerar.py` grava `publico/_headers` e `frontend/_headers` com a mesma política.
Se entrar um serviço novo (outra tag, outro domínio da API), inclua o domínio aqui e gere de novo.
"""
API = ["https://certame-api-va8f.onrender.com", "https://*.onrender.com"]
TAGS = ["https://www.googletagmanager.com", "https://*.googletagmanager.com", "https://www.google-analytics.com",
        "https://*.google-analytics.com", "https://*.analytics.google.com", "https://www.googleadservices.com",
        "https://googleads.g.doubleclick.net", "https://*.doubleclick.net", "https://www.google.com",
        "https://snap.licdn.com", "https://px.ads.linkedin.com", "https://*.linkedin.com",
        "https://connect.facebook.net", "https://www.facebook.com", "https://*.facebook.com"]
TURNSTILE = ["https://challenges.cloudflare.com"]

CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self' 'unsafe-inline' " + " ".join(TAGS + TURNSTILE),
    "connect-src 'self' " + " ".join(API + TAGS + TURNSTILE),
    "img-src 'self' data: blob: https:",
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
    "font-src 'self' data: https://fonts.gstatic.com",
    "frame-src 'self' blob: " + " ".join(TURNSTILE + ["https://www.googletagmanager.com", "https://td.doubleclick.net",
                                                    "https://www.facebook.com"]),
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    "upgrade-insecure-requests",
])


def headers():
    return f"""# Gerado por site/seguranca.py — cabeçalhos de segurança (Netlify)
/*
  Content-Security-Policy: {CSP}
  X-Content-Type-Options: nosniff
  X-Frame-Options: DENY
  Referrer-Policy: strict-origin-when-cross-origin
  Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=()
  Strict-Transport-Security: max-age=31536000; includeSubDomains
"""
