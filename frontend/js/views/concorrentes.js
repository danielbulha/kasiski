// Lista de concorrentes já pesquisados e seus dossiês públicos.
V.concorrentes = async (el) => {
  const lista = await api("GET", "/api/concorrentes");
  el.innerHTML = `
    <div class="cabecalho"><div><h1>Concorrentes</h1><p>Dossiês públicos consultados, de todos os editais.</p></div>
      <button class="botao" id="novo-dossie">${icone("buscar")} Consultar CNPJ</button></div>
    ${guia(`<p>Um dossiê reúne dados públicos do concorrente: situação na Receita, sanções no TCU e no Portal da Transparência e
      o histórico de contratos no PNCP. Ele é atualizado a cada 24 horas. Para analisar a habilitação ou a proposta de um
      concorrente em um edital específico, abra o edital e use a aba Concorrentes.</p>`)}
    <section class="bloco tabela-rolagem">
      ${lista.length ? `<table><thead><tr><th>Empresa</th><th>CNPJ</th><th>Situação</th><th>Sanções</th><th>Análises</th><th>Atualizado</th></tr></thead>
        <tbody>${lista.map(linhaConcorrente).join("")}</tbody></table>` : vazio("Nenhum concorrente pesquisado", "Consulte um CNPJ ou analise um documento na aba Concorrentes de um edital.")}
    </section>`;
  $$("tr.clicavel", el).forEach((tr) => tr.onclick = () => { location.hash = `#/concorrentes/${tr.dataset.id}`; });
  $("#novo-dossie", el).onclick = () => modalNovoDossie();
};

function linhaConcorrente(c) {
  const rec = c.dossie?.receita || {};
  const sancoes = (c.dossie?.sancoes_cgu?.registros?.length || 0) + ((c.dossie?.sancoes_tcu?.alerta) ? 1 : 0);
  return `<tr class="clicavel" data-id="${c.id}"><td>${esc(c.razao_social || rec.razao_social || "—")}</td><td>${fmt.cnpj(c.cnpj)}</td>
    <td>${rec.situacao ? carimbo(rec.situacao, rec.situacao === "ATIVA" ? "ok" : "erro") : "—"}</td>
    <td>${sancoes ? carimbo(`${sancoes} registro(s)`, "erro") : carimbo("Nada consta", "ok")}</td>
    <td>${c.analises}</td><td>${fmt.data(c.atualizado_em)}</td></tr>`;
}

function modalNovoDossie() {
  const m = modal({
    titulo: "Consultar CNPJ", corpo: `<form id="form-dossie">
      <div class="campo"><label for="cnpj_d">CNPJ do concorrente</label><input id="cnpj_d" name="cnpj" required placeholder="00.000.000/0000-00"></div>
      <div id="erro-dossie"></div><button class="botao" style="width:100%" type="submit">Consultar</button></form>`,
  });
  $("#form-dossie", m).onsubmit = async (ev) => {
    ev.preventDefault();
    const b = ev.target.querySelector("button");
    await ocupado(b, "Consultando bases públicas…", async () => {
      try { const c = await api("POST", "/api/concorrentes", { cnpj: $("#cnpj_d", m).value }); await atualizarConta(); m.fechar(); location.hash = `#/concorrentes/${c.id}`; }
      catch (e) { $("#erro-dossie", m).innerHTML = erroTela(e); }
    });
  };
}

V.concorrente = async (el, id) => {
  const c = await api("GET", `/api/concorrentes/${id}`);
  const rec = c.dossie?.receita || {};
  const nomeConhecido = c.razao_social || rec.razao_social;
  const tcu = c.dossie?.sancoes_tcu || {};
  const cgu = c.dossie?.sancoes_cgu || {};
  el.innerHTML = `
    <div class="cabecalho"><div><h1>${esc(nomeConhecido || "Empresa não identificada")}</h1><p>${fmt.cnpj(c.cnpj)} · atualizado em ${fmt.data(c.atualizado_em)}</p></div>
      <button class="botao secundario" id="atualizar-dossie">${icone("atualizar",15)} Atualizar dossiê</button></div>
    <div class="grade grade-2">
      <section class="bloco"><h2>Receita Federal</h2>
        ${rec.status === "ok" ? `<dl class="capa-campos" style="border:0"><div style="border:0"><dt>Situação</dt><dd>${carimbo(rec.situacao, rec.situacao === "ATIVA" ? "ok" : "erro")}</dd></div>
          <div style="border:0"><dt>Abertura</dt><dd>${fmt.data(rec.abertura)}</dd></div>
          <div style="border:0"><dt>Capital social</dt><dd>${fmt.moeda(rec.capital_social)}</dd></div>
          <div style="border:0"><dt>Porte</dt><dd>${esc(rec.porte || "—")}</dd></div></dl>
          <p><b>CNAEs:</b> ${(rec.cnaes || []).map((cn) => esc(cn.codigo + " " + (cn.descricao || ""))).join("; ") || "—"}</p>
          <p><b>Sócios:</b> ${(rec.socios || []).map((s) => esc(s.nome)).join(", ") || "—"}</p>`
          : `<p class="fraco">${rec.status === "nao_encontrado" ? "CNPJ não encontrado na base da Receita." : "Consulta indisponível no momento."}</p>`}</section>
      <section class="bloco"><h2>Sanções e impedimentos</h2>
        ${tcu.alerta ? tcu.certidoes.filter((x) => !String(x.situacao || "").toLowerCase().includes("nada consta"))
          .map((x) => `<p>${carimbo(x.emissor, "erro")} ${esc(x.situacao)}</p>`).join("") : ""}
        ${(cgu.registros || []).map((s) => `<p>${carimbo(s.cadastro, "erro")} ${esc(s.tipo)} — ${esc(s.orgao)} (${fmt.data(s.inicio)} a ${fmt.data(s.fim)})</p>`).join("")}
        ${!tcu.alerta && !(cgu.registros || []).length ? `<p>${carimbo("Nada consta nas bases consultadas", "ok")}</p>` : ""}
        ${cgu.status === "sem_chave" ? `<p class="fraco">Cadastre a chave do Portal da Transparência no servidor para consultar CEIS/CNEP.</p>` : ""}
      </section>
    </div>
    <section class="bloco"><h2>Histórico no PNCP</h2>
      ${(c.dossie?.historico_pncp || []).length ? c.dossie.historico_pncp.map((h) => `<div class="lista-item"><div class="corpo">
        <b>${esc(h.objeto || "")}</b><p>${esc(h.orgao || "")} · ${esc(h.uf || "")} · ${fmt.data(h.data)}</p></div>${fmt.moeda(h.valor)}</div>`).join("")
        : vazio("Sem histórico encontrado", "Não há contratos ou atas deste CNPJ na busca do PNCP.")}</section>
    <section class="bloco"><h2>Análises neste concorrente</h2>
      ${c.analises.length ? c.analises.map((a) => `<div class="lista-item"><div class="corpo"><b>${a.tipo === "habilitacao" ? "Habilitação" : "Proposta"}</b>
        <p>${fmt.dataHora(a.criado_em)} · ${(a.resultado.apontamentos || []).length} apontamento(s)</p></div>
        <button class="botao pequeno secundario" data-ver="${a.id}">${icone("olho",14)} Ver parecer</button></div>`).join("")
        : vazio("Nenhuma análise ainda", "Analise a habilitação ou a proposta deste concorrente em um edital.")}</section>`;
  $("#atualizar-dossie", el).onclick = (ev) => ocupado(ev.target, "Atualizando…", async () => {
    try { await api("POST", "/api/concorrentes", { cnpj: c.cnpj, atualizar: true }); V.concorrente(el, id); } catch (e) { avisarErro(e); }
  });
  $$("[data-ver]", el).forEach((b) => b.onclick = () => abrirParecerConcorrente(c.analises.find((a) => a.id == b.dataset.ver)));
};
