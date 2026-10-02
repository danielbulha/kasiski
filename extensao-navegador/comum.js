// Utilidades da leitura da tela (rodam dentro da página do portal, no navegador do usuário).
// Regra da extensão: só LER o que está visível. Nunca clicar, preencher, enviar formulário ou ler cookies/senhas.
const Kasiski = {
  // "R$ 93.400,50" | "93.400,5000" | "12,5 %" -> número. Devolve null se não houver valor.
  valorBR(t) {
    const m = String(t ?? "").replace(/\s/g, "").match(/-?\d{1,3}(?:\.\d{3})*(?:,\d+)?|-?\d+(?:,\d+)?/);
    if (!m) return null;
    const n = Number(m[0].replace(/\./g, "").replace(",", "."));
    return Number.isFinite(n) ? n : null;
  },
  texto(el) { return (el?.innerText ?? el?.textContent ?? "").replace(/\s+/g, " ").trim(); },
  // Hash curto e determinístico: a mesma mensagem lida de novo (recarregar a página) gera o mesmo id.
  hash(s) {
    let h1 = 0x811c9dc5, h2 = 0x1000193;
    for (let i = 0; i < s.length; i++) { const c = s.charCodeAt(i); h1 = Math.imul(h1 ^ c, 16777619); h2 = Math.imul(h2 ^ c, 2246822519); }
    return (h1 >>> 0).toString(36) + (h2 >>> 0).toString(36);
  },
};
