// Observa a sala de disputa aberta pelo usuário e manda ao Kasiski só o que MUDOU na tela.
// Não clica, não preenche e não envia nada ao portal: apenas lê o texto visível.
(() => {
  const adaptador = window.KasiskiAdaptador;
  if (!adaptador) return;
  const anterior = new Map();              // item -> último estado lido
  const mensagensVistas = new Set();
  let agendado = null, ultimoStatus = "";

  const enviar = (msg) => { try { chrome.runtime.sendMessage(msg).catch(() => {}); } catch { /* extensão atualizada/recarregada */ } };
  const status = (lendo, motivo, extra = {}) => {
    const s = JSON.stringify({ lendo, motivo });
    if (s === ultimoStatus && !extra.forcar) return;
    ultimoStatus = s;
    enviar({ tipo: "status", lendo, motivo, portal: adaptador.nome, url: location.origin + location.pathname });
  };
  const id = () => (crypto.randomUUID ? crypto.randomUUID() : Kasiski.hash(Math.random() + ":" + Date.now()));

  function ciclo() {
    agendado = null;
    let lido;
    try { lido = adaptador.ler(); } catch (e) { status(false, "erro_leitura"); return; }
    if (lido?.erro) { status(false, lido.erro); return; }
    if (!lido) { status(false, "fora_da_sala"); return; }
    status(true, lido.itens.length ? "lendo" : "sem_itens");
    const agora = new Date().toISOString(), eventos = [];
    for (const x of lido.itens) {
      const antes = anterior.get(x.item) || {};
      // o seu lance primeiro: quando ele vira o melhor, o "melhor valor" igual não é registrado como lance do mercado
      for (const [campo, tipo] of [["meu_lance", "meu_lance"], ["melhor_lance", "melhor_lance"], ["posicao", "posicao"]]) {
        if (x[campo] !== null && x[campo] !== undefined && x[campo] !== antes[campo]) eventos.push({ id: id(), tipo, item: x.item, valor: x[campo], visto_em: agora });
      }
      if (x.fase && x.fase !== antes.fase) eventos.push({ id: id(), tipo: "fase", item: x.item, texto: x.fase, visto_em: agora });
      anterior.set(x.item, x);
    }
    for (const m of lido.mensagens) {
      const chave = "m" + Kasiski.hash(`${m.item}|${m.hora}|${m.texto}`);   // a mesma mensagem relida tem o mesmo id
      if (mensagensVistas.has(chave)) continue;
      mensagensVistas.add(chave);
      // sem item: aviso geral do pregoeiro, o Kasiski coloca em todas as salas desta licitação
      eventos.push({ id: chave, tipo: "mensagem", item: m.item || "", texto: m.hora ? `${m.hora} · ${m.texto}` : m.texto, visto_em: agora });
    }
    for (let i = 0; i < eventos.length; i += 100) enviar({ tipo: "eventos", eventos: eventos.slice(i, i + 100) });
  }
  const agendar = () => { if (!agendado) agendado = setTimeout(ciclo, 300); };

  new MutationObserver(agendar).observe(document.documentElement, { subtree: true, childList: true, characterData: true });
  setInterval(agendar, 2000);   // garante a leitura mesmo se a página atualizar sem mexer no DOM observado
  ciclo();

  // Popup: "Copiar estrutura da página" para configurar o adaptador sem expor números da disputa.
  chrome.runtime.onMessage.addListener((msg, _de, responder) => {
    if (msg?.tipo === "capturar_estrutura") { responder({ html: estruturaSemDados() }); return; }
    if (msg?.tipo === "reenviar_status") { ultimoStatus = ""; ciclo(); }
  });

  function estruturaSemDados() {
    const copia = document.body.cloneNode(true);
    copia.querySelectorAll("script, style, noscript, svg, canvas, iframe, img, video, link").forEach((n) => n.remove());
    const manter = /^(id|class|role|name|type|for|title|aria-[\w-]+|data-[\w-]+)$/;
    copia.querySelectorAll("*").forEach((el) => {
      [...el.attributes].forEach((a) => { if (!manter.test(a.name)) el.removeAttribute(a.name); else if (a.name !== "id" && a.name !== "class") el.setAttribute(a.name, a.value.replace(/\d/g, "9")); });
      if (el.tagName === "INPUT" || el.tagName === "TEXTAREA") el.removeAttribute("value");
    });
    const andar = document.createTreeWalker(copia, NodeFilter.SHOW_TEXT);
    for (let n = andar.nextNode(); n; n = andar.nextNode()) n.nodeValue = n.nodeValue.replace(/\d/g, "9").replace(/[\w.+-]+@[\w-]+\.[\w.]+/g, "email@omitido");
    return `<!-- ${location.origin}${location.pathname} · estrutura sem números, capturada pela extensão Kasiski -->\n` + copia.outerHTML.slice(0, 3_000_000);
  }
})();
