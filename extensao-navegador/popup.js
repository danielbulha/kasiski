const $ = (s) => document.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const pedir = (msg) => chrome.runtime.sendMessage(msg);
const MOTIVOS = {
  lendo: ["ok", "Lendo a sala de disputa."], sem_itens: ["", "Na sala, mas nenhum item visível."],
  fora_da_sala: ["", "Abra a sala de disputa do portal."], erro_leitura: ["erro", "Não consegui ler esta página."],
  aguardando_configuracao: ["erro", "A leitura deste portal ainda está sendo configurada. Clique em \"Copiar estrutura da página\" e envie ao suporte do Kasiski."],
};

async function desenhar() {
  const { conexao: c, abas } = await pedir({ tipo: "estado" });
  const [aba] = await chrome.tabs.query({ active: true, currentWindow: true });
  const st = abas?.[aba?.id];
  const linhaAba = st ? `<p class="${MOTIVOS[st.motivo]?.[0] || ""}">${esc(MOTIVOS[st.motivo]?.[1] || st.motivo)}</p>`
    : `<p class="fraco">Esta aba não é a sala de disputa de um portal atendido.</p>`;
  const captura = st ? `<button class="sec" id="capturar">Copiar estrutura da página (sem números)</button>` : "";
  if (!c?.token) {
    $("#conteudo").innerHTML = `${c?.erro ? `<p class="erro">${esc(c.erro)}</p>` : ""}
      <p>Na sala de disputa do Kasiski, clique em <b>Conectar extensão</b> e digite aqui o código.</p>
      <form id="f"><input id="codigo" maxlength="9" placeholder="ABCD-1234" autocomplete="off" required><div id="msg"></div>
      <button type="submit">Conectar</button></form><div class="caixa">${linhaAba}</div>${captura}`;
    $("#codigo").focus();
    $("#f").onsubmit = async (ev) => {
      ev.preventDefault();
      const r = await pedir({ tipo: "vincular", codigo: $("#codigo").value });
      if (r.erro) $("#msg").innerHTML = `<p class="erro">${esc(r.erro)}</p>`; else desenhar();
    };
  } else {
    $("#conteudo").innerHTML = `<div class="caixa"><p class="ok"><b>Conectada</b>${c.licitacao ? ` · ${esc(c.licitacao.numero || "")}` : ""}</p>
        ${c.licitacao?.orgao ? `<small>${esc(c.licitacao.orgao)}</small>` : ""}
        <ul>${(c.salas || []).map((s) => `<li>Item ${esc(s.item || "—")} <small>${esc(s.descricao || "")}</small></li>`).join("")}</ul>
        <small>${c.aceitos || 0} atualização(ões) enviada(s)${c.ultimo_envio ? ` · última às ${new Date(c.ultimo_envio).toLocaleTimeString("pt-BR")}` : ""}.
        Válida até ${c.expira_em ? new Date(c.expira_em + "Z").toLocaleString("pt-BR") : "—"}.</small></div>
      <div class="caixa">${linhaAba}</div>
      <button class="sec" id="sair">Desconectar</button>${captura}`;
    $("#sair").onclick = async () => { await pedir({ tipo: "desconectar" }); desenhar(); };
  }
  const b = $("#capturar");
  if (b) b.onclick = async () => {
    const r = await chrome.tabs.sendMessage(aba.id, { tipo: "capturar_estrutura" }).catch(() => null);
    if (!r?.html) { b.textContent = "Não consegui capturar esta página"; return; }
    await navigator.clipboard.writeText(r.html);
    b.textContent = "Copiado. Revise antes de enviar ao Kasiski.";
  };
}
desenhar();
