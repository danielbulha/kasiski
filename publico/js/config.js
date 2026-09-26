// Ajuste antes de publicar no Netlify.
// Domínios: o site público (kasiski.com.br, pasta publico/) e o aplicativo (app.kasiski.com.br, pasta frontend/).
const _LOCAL = ["localhost", "127.0.0.1"].includes(location.hostname);
window.CERTAME = {
  SITE_URL: _LOCAL ? `http://${location.hostname}:8081` : "https://kasiski.com.br",
  APP_URL: _LOCAL ? `http://${location.hostname}:8080` : "https://app.kasiski.com.br",
  // Endereço do backend no Render (sem barra no final). Em desenvolvimento: http://localhost:5000
  API_URL: location.hostname === "localhost" || location.hostname === "127.0.0.1"
    ? "http://127.0.0.1:5000"
    : "https://certame-api-va8f.onrender.com",
  // Contato comercial (usado como alternativa quando o pagamento online estiver indisponível)
  LINK_ASSINATURA: "https://wa.me/5511999999999?text=Quero%20assinar%20o%20Kasiski",
  // Nome curto: usado na navegação (barra lateral, barra mobile, textos internos).
  NOME: "Kasiski",
  // Nome completo: usado na apresentação de marca (tela de login, título da aba do navegador).
  NOME_COMPLETO: "Kasiski Public Market Intelligence",
  // Tags de medição e anúncios. Cole os IDs quando criar as contas; vazio = a tag não é carregada.
  // Recomendado: só o GTM_ID e configure GA4, Google Ads, LinkedIn e Meta DENTRO do Tag Manager.
  TAGS: {
    GTM_ID: "",              // Google Tag Manager (GTM-XXXXXXX)
    GA4_ID: "",              // Google Analytics 4 (G-XXXXXXXXXX) — só usado se não houver GTM
    GOOGLE_ADS_ID: "",       // Google Ads (AW-XXXXXXXXX) — só usado se não houver GTM
    LINKEDIN_PARTNER_ID: "", // LinkedIn Insight Tag (número) — só usado se não houver GTM
    META_PIXEL_ID: "",       // Meta Pixel (número) — só usado se não houver GTM
  },
  // Cloudflare Turnstile (anti-robô nas ferramentas gratuitas). Preencha junto com TURNSTILE_SECRET no Render.
  TURNSTILE_SITEKEY: "",
};
