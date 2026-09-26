// Assistente virtual do Kasiski (widget de atendimento).
// Visual do frontend "kasiski-chatbot-frontend"; respostas vindas de POST /api/chat, com a base oficial de
// planos e funcionalidades montada no servidor. Funciona para visitantes e para usuários logados.
(() => {
  const API = (window.CERTAME && CERTAME.API_URL) || "";
  const CHAVE = "kasiski_chat_id";
  const ler = (k) => { try { return localStorage.getItem(k); } catch { return null; } };
  const gravar = (k, v) => { try { localStorage.setItem(k, v); } catch { /* navegação privada */ } };
  const token = () => (window.S && S.token) || ler("certame_token");
  const e = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const marca = (t) => (typeof simboloMarca === "function" ? simboloMarca(t) : "≡");

  const raiz = document.createElement("div");
  raiz.innerHTML = `
  <button id="k-open" class="k-launch" aria-label="Abrir o assistente do Kasiski" aria-expanded="false" aria-controls="k-chat"><span class="k-mark">${marca(30)}</span><span class="k-ping" aria-hidden="true"></span></button>
  <section id="k-chat" class="k-chat hidden" aria-label="Assistente virtual Kasiski" role="dialog" aria-hidden="true" inert>
    <header class="k-head"><div class="k-brand"><div class="k-icon">${marca(24)}</div><div><strong>KASISKI</strong><small>Assistente virtual</small></div></div>
      <div class="k-actions"><button id="k-novo" aria-label="Nova conversa" title="Nova conversa">↺</button><button id="k-close" aria-label="Fechar">×</button></div></header>
    <main id="k-messages" class="k-body" aria-live="polite"></main>
    <footer class="k-foot"><form id="k-form"><input id="k-input" autocomplete="off" maxlength="1200" placeholder="Digite sua pergunta..." aria-label="Digite sua pergunta"><button type="submit" aria-label="Enviar">➤</button></form>
      <p>O assistente utiliza informações oficiais do KASISKI.<br>Em caso de dúvidas específicas, nossa equipe poderá ajudar.</p></footer>
  </section>`;
  document.body.appendChild(raiz);

  const $ = (s) => raiz.querySelector(s);
  const chat = $("#k-chat"), abrir = $("#k-open"), form = $("#k-form"), input = $("#k-input"), msgs = $("#k-messages");
  let conversa = ler(CHAVE), carregado = false, ocupado = false;

  const rolar = () => { msgs.scrollTop = msgs.scrollHeight; };
  // texto do assistente: escapa HTML e aplica **negrito**, `tela`, quebras de linha e links do app (#/...)
  // no site público (kasiski.com.br), os links #/tela apontam para o app (app.kasiski.com.br)
  const APP = (window.CERTAME && CERTAME.APP_URL) || "";
  const baseApp = APP && !location.href.startsWith(APP) ? APP + "/" : "";
  const formatar = (t) => e(t).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/(^|\s)(#\/[\w/-]+)/g, `$1<a href="${baseApp}$2">$2</a>`).replace(/\n/g, "<br>");

  function balao(texto, tipo = "bot", opts = {}) {
    const row = document.createElement("div");
    row.className = "k-row " + (tipo === "bot" ? "bot" : "user");
    row.innerHTML = (tipo === "bot" ? `<div class="k-avatar" aria-hidden="true">${marca(18)}</div>` : "") +
      `<div class="k-bubble${opts.erro ? " erro" : ""}">${tipo === "bot" ? formatar(texto) : e(texto)}</div>`;
    msgs.appendChild(row); rolar(); return row;
  }
  function boasVindas() {
    msgs.innerHTML = `<div class="k-day">Hoje</div>`;
    const nome = window.S && S.usuario ? `, ${S.usuario.nome.split(" ")[0]}` : "";
    balao(`Olá${nome}! Sou o assistente virtual do **KASISKI Public Market Intelligence.**\n\nPosso ajudar com informações sobre a plataforma, funcionalidades, planos, assinatura ou suporte.\n\n**Como posso ajudar?**`);
    const q = document.createElement("div");
    q.className = "k-quick";
    q.innerHTML = [["⌕", "Conhecer o KASISKI", "O que é, como funciona e benefícios", "Quero conhecer o KASISKI"],
      ["▥", "Planos e assinatura", "Preços, período gratuito e contratação", "Quero saber sobre planos e assinatura"],
      ["⚙", "Ajuda com a plataforma", "Cadastro, acesso e utilização", "Preciso de ajuda com a plataforma"],
      ["◉", "Falar com atendimento", "Converse com nossa equipe", "__humano__"]]
      .map(([ic, t, s, m]) => `<button type="button" data-msg="${e(m)}"><b aria-hidden="true">${ic}</b><span><strong>${e(t)}</strong><small>${e(s)}</small></span><i aria-hidden="true">›</i></button>`).join("");
    msgs.appendChild(q);
    q.querySelectorAll("[data-msg]").forEach((b) => b.onclick = () => (b.dataset.msg === "__humano__" ? formularioHumano() : enviar(b.dataset.msg)));
  }
  function sugestoes(lista, humano) {
    const itens = [...(lista || [])];
    if (!itens.length && !humano) return;
    const d = document.createElement("div");
    d.className = "k-sugestoes";
    d.innerHTML = itens.map((s) => `<button type="button">${e(s)}</button>`).join("") + (humano ? `<button type="button" class="k-humano" data-humano>Falar com atendimento</button>` : "");
    d.querySelectorAll("button").forEach((b) => b.onclick = () => { d.remove(); if (b.dataset.humano !== undefined || /falar com atendimento/i.test(b.textContent)) formularioHumano(); else enviar(b.textContent); });
    msgs.appendChild(d); rolar();
  }
  function digitando() {
    const row = document.createElement("div");
    row.className = "k-row bot";
    row.innerHTML = `<div class="k-avatar" aria-hidden="true">${marca(18)}</div><div class="k-bubble"><span class="typing" aria-label="Digitando"><i></i><i></i><i></i></span></div>`;
    msgs.appendChild(row); rolar(); return row;
  }
  async function chamar(caminho, corpo, metodo = "POST") {
    const cab = { "Content-Type": "application/json" };
    if (token()) cab.Authorization = "Bearer " + token();
    const r = await fetch(API + caminho, { method: metodo, headers: cab, body: corpo ? JSON.stringify(corpo) : undefined });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.erro || "Não consegui responder agora.");
    return d;
  }

  async function enviar(texto) {
    texto = String(texto || "").trim();
    if (!texto || ocupado) return;
    ocupado = true; form.querySelector("button").disabled = true;
    msgs.querySelectorAll(".k-quick,.k-sugestoes").forEach((x) => x.remove());
    balao(texto, "user"); input.value = "";
    const t = digitando();
    try {
      const visitante = (window.Kasiski && Kasiski.visitante) || (window.FUNIL && FUNIL.visitante) || ler("kasiski_visitante") || "";
      const d = await chamar("/api/chat", { message: texto, conversationId: conversa, pageUrl: location.hash || location.pathname, visitante });
      conversa = d.conversationId; gravar(CHAVE, conversa);
      t.remove(); balao(d.resposta);
      sugestoes(d.sugestoes, d.encaminhar);
    } catch (err) {
      t.remove();
      balao("Não consegui responder agora. Tente de novo em instantes ou fale com a nossa equipe.", "bot", { erro: true });
      sugestoes([], true);
      if (typeof reportarErro === "function") reportarErro({ tipo: "servidor", mensagem: `Assistente: ${err.message}`, chamada: "/api/chat", metodo: "POST" });
    } finally { ocupado = false; form.querySelector("button").disabled = false; input.focus(); }
  }

  function formularioHumano() {
    msgs.querySelectorAll(".k-quick,.k-sugestoes,.k-handoff").forEach((x) => x.remove());
    balao("Claro! Deixe seu contato e, se quiser, descreva o assunto. A conversa vai junto, para você não precisar repetir.");
    const u = window.S && S.usuario;
    const f = document.createElement("form");
    f.className = "k-handoff";
    f.innerHTML = `<b>Falar com a equipe</b>
      <input name="nome" required placeholder="Seu nome" value="${e(u?.nome || "")}" aria-label="Seu nome" autocomplete="name">
      <input name="email" type="email" required placeholder="Seu e-mail" value="${e(u?.email || "")}" aria-label="Seu e-mail" autocomplete="email">
      <input name="telefone" type="tel" placeholder="WhatsApp (opcional)" aria-label="WhatsApp" autocomplete="tel">
      <textarea name="mensagem" placeholder="Como podemos ajudar?" aria-label="Assunto"></textarea>
      <small data-erro></small>
      <div class="k-acoes"><button type="button" data-cancelar>Voltar</button><button type="submit">Enviar para a equipe</button></div>`;
    msgs.appendChild(f); rolar(); f.querySelector(u ? "textarea" : "input").focus();
    f.querySelector("[data-cancelar]").onclick = () => { f.remove(); sugestoes(["Quais são os planos?", "Como funciona o Kasiski?"]); };
    f.onsubmit = async (ev) => {
      ev.preventDefault();
      const b = f.querySelector("button[type=submit]"); b.disabled = true; b.textContent = "Enviando…";
      const dados = Object.fromEntries(new FormData(f).entries());
      try {
        const d = await chamar("/api/chat/atendimento", { ...dados, conversationId: conversa, pageUrl: location.hash || location.pathname });
        conversa = d.conversationId; gravar(CHAVE, conversa);
        f.remove(); input.focus(); balao(dados.mensagem ? `Assunto: ${dados.mensagem}` : "Quero falar com a equipe.", "user"); balao(d.resposta);
      } catch (err) { f.querySelector("[data-erro]").textContent = err.message; b.disabled = false; b.textContent = "Enviar para a equipe"; }
    };
  }

  async function carregar() {
    if (carregado) return;
    carregado = true;
    if (!conversa) { boasVindas(); return; }
    try {
      const cab = token() ? { Authorization: "Bearer " + token() } : {};
      const r = await fetch(`${API}/api/chat/${encodeURIComponent(conversa)}`, { headers: cab });
      const d = await r.json();
      if (!d.mensagens || !d.mensagens.length) { conversa = null; boasVindas(); return; }
      msgs.innerHTML = `<div class="k-day">Conversa anterior</div>`;
      d.mensagens.forEach((m) => balao(m.texto, m.papel === "usuario" ? "user" : "bot"));
      if (d.status === "encaminhada") balao("Sua conversa está com a nossa equipe. Se quiser, continue por aqui.");
      else sugestoes(["Quais são os planos?", "Como funciona o Kasiski?"]);
    } catch { boasVindas(); }
  }

  function mostrar() {
    carregar();
    chat.classList.remove("hidden"); chat.removeAttribute("inert"); chat.setAttribute("aria-hidden", "false");
    abrir.style.display = "none"; abrir.setAttribute("aria-expanded", "true");
    setTimeout(() => input.focus(), 200);
  }
  function esconder() {
    chat.classList.add("hidden"); chat.setAttribute("inert", ""); chat.setAttribute("aria-hidden", "true");
    abrir.style.display = "grid"; abrir.setAttribute("aria-expanded", "false"); abrir.focus();
  }
  abrir.onclick = mostrar;
  $("#k-close").onclick = esconder;
  $("#k-novo").onclick = () => { conversa = null; try { localStorage.removeItem(CHAVE); } catch { /* ok */ } carregado = true; boasVindas(); input.focus(); };
  document.addEventListener("keydown", (ev) => { if (ev.key === "Escape" && chat.getAttribute("aria-hidden") === "false" && !document.querySelector(".modal")) esconder(); });
  form.onsubmit = (ev) => { ev.preventDefault(); enviar(input.value); };
  msgs.addEventListener("click", (ev) => { const a = ev.target.closest("a[href^='#/']"); if (a && window.innerWidth < 600) esconder(); });
  window.KasiskiChat = { abrir: mostrar, fechar: esconder, perguntar: (t) => { mostrar(); setTimeout(() => enviar(t), 250); } };
})();
