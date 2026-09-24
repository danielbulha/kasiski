// Ajuste antes de publicar no Netlify.
window.CERTAME = {
  // Endereço do backend no Render (sem barra no final). Em desenvolvimento: http://127.0.0.1:5000
  API_URL: location.hostname === "localhost" || location.hostname === "127.0.0.1"
    ? "http://127.0.0.1:5000"
    : "https://certame-api.onrender.com",
  // Link para contratar um plano (WhatsApp, página de checkout do Asaas/Mercado Pago etc.)
  LINK_ASSINATURA: "https://wa.me/5511999999999?text=Quero%20assinar%20o%20Certame",
  NOME: "Certame",
};
