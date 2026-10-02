// Service worker: guarda a conexão com o Kasiski e entrega os eventos lidos na sala à API.
// O token da extensão fica em chrome.storage.session (some ao fechar o navegador) e só serve para enviar eventos.
importScripts("config.js");

let fila = [], enviando = false, timer = null;
const statusAbas = {};   // aba -> {lendo, motivo, portal, url, em}

async function conexao() { return (await chrome.storage.session.get("conexao")).conexao || null; }
async function salvarConexao(c) { c ? await chrome.storage.session.set({ conexao: c }) : await chrome.storage.session.remove("conexao"); }

async function chamar(metodo, caminho, corpo, token) {
  const headers = { "Content-Type": "application/json" };
  if (token) headers.Authorization = "Extensao " + token;
  const r = await fetch(KASISKI_API + caminho, { method: metodo, headers, body: corpo ? JSON.stringify(corpo) : undefined });
  const d = await r.json().catch(() => ({}));
  if (!r.ok) { const e = new Error(d.erro || `Erro ${r.status}`); e.status = r.status; e.codigo = d.codigo; throw e; }
  return d;
}

async function marcar() {
  const c = await conexao();
  const algumaLendo = Object.values(statusAbas).some((s) => s.lendo);
  await chrome.action.setBadgeText({ text: !c ? "" : c.erro ? "!" : algumaLendo ? "ON" : "…" });
  await chrome.action.setBadgeBackgroundColor({ color: c?.erro ? "#B42318" : "#1B7F4B" });
}

async function descarregar() {
  timer = null;
  if (enviando || !fila.length) return;
  const c = await conexao();
  if (!c) { fila = []; return; }    // sem conexão: não acumula dados da sala
  enviando = true;
  const lote = fila.splice(0, 100);
  try {
    const r = await chamar("POST", "/api/extensao/eventos", { eventos: lote }, c.token);
    await salvarConexao({ ...c, erro: null, ultimo_envio: new Date().toISOString(), aceitos: (c.aceitos || 0) + r.aceitos });
  } catch (e) {
    if (e.status === 401) { fila = []; await salvarConexao({ ...c, token: null, erro: e.message }); }
    else if (e.status === 413 || e.status === 400) { /* lote inválido: descarta */ }
    else { fila = lote.concat(fila).slice(0, 1000); setTimeout(descarregar, 5000); }   // rede/429: tenta de novo
  } finally {
    enviando = false;
    marcar();
    if (fila.length && !timer) timer = setTimeout(descarregar, 250);
  }
}

chrome.runtime.onMessage.addListener((msg, remetente, responder) => {
  (async () => {
    if (msg.tipo === "eventos") {
      const c = await conexao();
      if (c?.token) { fila.push(...msg.eventos); if (!timer) timer = setTimeout(descarregar, 250); }
      return {};
    }
    if (msg.tipo === "status") {
      if (remetente.tab?.id !== undefined) statusAbas[remetente.tab.id] = { ...msg, em: Date.now() };
      marcar();
      return {};
    }
    if (msg.tipo === "estado") {
      return { conexao: await conexao(), abas: statusAbas };
    }
    if (msg.tipo === "vincular") {
      const d = await chamar("POST", "/api/extensao/vincular", { codigo: msg.codigo });
      await salvarConexao({ ...d, conectado_em: new Date().toISOString(), aceitos: 0 });
      chrome.tabs.query({}, (abas) => abas.forEach((a) => chrome.tabs.sendMessage(a.id, { tipo: "reenviar_status" }).catch(() => {})));
      marcar();
      return { ok: true, ...d, token: undefined };
    }
    if (msg.tipo === "desconectar") {
      const c = await conexao();
      if (c?.token) await chamar("DELETE", "/api/extensao", null, c.token).catch(() => {});
      await salvarConexao(null);
      fila = [];
      marcar();
      return { ok: true };
    }
    return {};
  })().then(responder, (e) => responder({ erro: e.message }));
  return true;   // resposta assíncrona
});

chrome.tabs.onRemoved.addListener((id) => { delete statusAbas[id]; marcar(); });
