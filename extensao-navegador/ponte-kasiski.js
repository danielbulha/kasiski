// Roda só no aplicativo do Kasiski (app.kasiski.com.br). Avisa a página que a extensão está instalada e recebe o
// código de conexão gerado pelo próprio usuário logado, para conectar com um clique (sem digitar o código).
(() => {
  const versao = chrome.runtime.getManifest().version;
  document.documentElement.dataset.kasiskiExtensao = versao;
  const responder = (dados) => window.postMessage({ fonte: "kasiski-extensao", ...dados }, location.origin);
  window.addEventListener("message", async (ev) => {
    if (ev.source !== window || ev.origin !== location.origin) return;   // só a própria página do Kasiski
    const msg = ev.data || {};
    if (msg.fonte !== "kasiski-app") return;
    if (msg.tipo === "presente") responder({ tipo: "presente", versao });
    if (msg.tipo === "conectar" && typeof msg.codigo === "string") {
      try {
        const r = await chrome.runtime.sendMessage({ tipo: "vincular", codigo: msg.codigo.slice(0, 12) });
        responder(r?.erro ? { tipo: "erro", erro: r.erro } : { tipo: "conectado", salas: r?.salas?.length || 0 });
      } catch (e) { responder({ tipo: "erro", erro: "A extensão não respondeu. Recarregue a página e tente de novo." }); }
    }
  });
  responder({ tipo: "presente", versao });
})();
