// Agenda: prazos automáticos (editais e contratos) e manuais.
V.agenda = async (el) => {
  if (!S.empresas.length) { el.innerHTML = exigirEmpresa(); return; }
  const todas = S.empresas.length > 1 && sessionStorage.getItem("agenda_todas") === "1";
  const itens = await api("GET", `/api/agenda?pendentes=1${todas ? "" : `&empresa_id=${S.empresaId}`}`);
  const grupos = { atrasado: [], hoje: [], semana: [], depois: [] };
  itens.forEach((p) => { const n = fmt.dias(p.data); (grupos[n < 0 ? "atrasado" : n === 0 ? "hoje" : n <= 7 ? "semana" : "depois"]).push(p); });
  const secao = (t, l, vazioMsg) => l.length ? `<section class="bloco"><h3>${t}</h3>${l.map(linhaAgenda).join("")}</section>` : (vazioMsg ? `<section class="bloco">${vazio(t, vazioMsg)}</section>` : "");
  el.innerHTML = `
    <div class="cabecalho"><div><h1>Agenda de prazos</h1><p>Esclarecimento, impugnação, recurso, contrato e cofre — tudo em um lugar.</p></div>
      <div class="acoes">${S.empresas.length > 1 ? `<label class="check"><input type="checkbox" id="todas" ${todas ? "checked" : ""}> Todas as empresas</label>` : ""}
      <button class="botao" id="novo-prazo">Novo prazo</button></div></div>
    ${guia(`<p>Os prazos com fundamento legal (esclarecimento, impugnação, recurso, vigência, garantia, reajuste) são calculados
      automaticamente. Use "Novo prazo" para compromissos próprios, como uma reunião com o órgão ou a entrega de uma proposta técnica.</p>`)}
    ${secao("Atrasados", grupos.atrasado)}${secao("Hoje", grupos.hoje)}
    ${secao("Nos próximos 7 dias", grupos.semana)}${secao("Mais adiante", grupos.depois, itens.length ? "" : "Nenhum prazo pendente no momento.")}`;
  const t = $("#todas", el); if (t) t.onchange = () => { sessionStorage.setItem("agenda_todas", t.checked ? "1" : "0"); V.agenda(el); };
  $("#novo-prazo", el).onclick = () => modalNovoPrazo();
  $$("[data-concluir-prazo]", el).forEach((c) => c.onchange = async () => { await api("PATCH", `/api/agenda/${c.dataset.concluirPrazo}`, { concluido: c.checked }); V.agenda(el); });
  $$("[data-abrir-edital]", el).forEach((a) => a.onclick = () => { location.hash = `#/editais/${a.dataset.abrirEdital}`; });
};

function linhaAgenda(p) {
  const manual = !p.automatico;
  return `<div class="lista-item"><div class="corpo"><b>${esc(p.titulo)}</b>
    <p>${esc(p.empresa || "")}${p.fundamento ? " · " + esc(p.fundamento) : ""}</p></div>
    <div class="acoes">${carimboPrazo(p.data)}<span class="fraco">${fmt.dataHora(p.data)}</span>
      ${p.edital_id ? `<button class="botao texto pequeno" data-abrir-edital="${p.edital_id}">Abrir edital</button>` : ""}
      ${manual ? `<label class="check"><input type="checkbox" data-concluir-prazo="${p.id}"> Feito</label>` : ""}</div></div>`;
}

function modalNovoPrazo() {
  const opcoes = S.empresas.map((e) => `<option value="${e.id}" ${e.id === S.empresaId ? "selected" : ""}>${esc(e.razao_social)}</option>`).join("");
  const m = modal({
    titulo: "Novo prazo", corpo: `<form id="form-prazo">
      ${S.empresas.length > 1 ? `<div class="campo"><label for="empresa_p">Empresa</label><select id="empresa_p" name="empresa_id">${opcoes}</select></div>` : `<input type="hidden" name="empresa_id" value="${S.empresaId}">`}
      <div class="campo"><label for="titulo_p">Título</label><input id="titulo_p" name="titulo" required></div>
      <div class="campo"><label for="data_p">Data e hora</label><input id="data_p" name="data" type="datetime-local" required></div>
      <div class="campo"><label for="fundamento_p">Observação (opcional)</label><input id="fundamento_p" name="fundamento"></div>
      <div id="erro-prazo"></div><button class="botao" style="width:100%" type="submit">Salvar</button></form>`,
  });
  $("#form-prazo", m).onsubmit = async (ev) => {
    ev.preventDefault();
    try { await api("POST", "/api/agenda", dadosForm(ev.target)); m.fechar(); V.agenda($("#conteudo")); }
    catch (e) { $("#erro-prazo", m).innerHTML = erroTela(e); }
  };
}
