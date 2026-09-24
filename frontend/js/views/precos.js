// Inteligência de preços: preços praticados no Compras.gov.br para precificar a proposta.
V.precos = async (el) => {
  if (!S.empresaId) { el.innerHTML = exigirEmpresa(); return; }
  const lista = await api("GET", `/api/empresas/${S.empresaId}/precos`);
  el.innerHTML = `
    <div class="cabecalho"><div><h1>Preços praticados</h1><p>Pesquisas de preço de ${esc(empresaAtual().razao_social)}.</p></div>
      <button class="botao" id="nova-pesquisa">${icone("adicionar")} Nova pesquisa</button></div>
    ${guia(`<p>Informe o código CATMAT (material) ou CATSER (serviço) do Compras.gov.br para trazer preços já homologados em
      compras públicas recentes. Sem o código, cadastre a pesquisa e some orçamentos manuais para calcular a faixa competitiva.</p>`)}
    <section class="bloco">${lista.length ? lista.map(linhaPreco).join("") : vazio("Nenhuma pesquisa ainda", "Cadastre a primeira pesquisa de preço.")}</section>`;
  $("#nova-pesquisa", el).onclick = () => modalPesquisa();
  $$("[data-abrir-preco]", el).forEach((b) => b.onclick = () => abrirPesquisa(lista.find((p) => p.id == b.dataset.abrirPreco)));
  $$("[data-excluir-preco]", el).forEach((b) => b.onclick = async () => { if (await confirmar("Excluir esta pesquisa?", "Excluir")) { await api("DELETE", `/api/precos/${b.dataset.excluirPreco}`); V.precos(el); } });
};

function linhaPreco(p) {
  const e = p.estatisticas || {};
  return `<div class="lista-item"><div class="corpo"><b>${esc(p.descricao)}</b>
    <p>${p.codigo_catalogo ? `Código ${esc(p.codigo_catalogo)} · ` : ""}${e.n || 0} amostra(s)${p.uf ? " · " + esc(p.uf) : ""}</p></div>
    <div class="acoes">${e.n ? `<span>Mediana ${fmt.moeda(e.mediana)}</span>` : ""}
      <button class="botao pequeno secundario" data-abrir-preco="${p.id}">Ver</button>
      <button class="botao texto pequeno" data-excluir-preco="${p.id}">${icone("excluir",14)} Excluir</button></div></div>`;
}

function modalPesquisa() {
  const m = modal({
    titulo: "Nova pesquisa de preço", corpo: `<form id="form-preco">
      <div class="campo"><label for="descricao_pr">O que você está pesquisando</label><input id="descricao_pr" name="descricao" required placeholder="Ex.: Serviço de limpeza predial, m²/mês"></div>
      <div class="linha-campos"><div class="campo"><label for="tipo_pr">Tipo</label><select id="tipo_pr" name="tipo"><option value="material">Material (CATMAT)</option><option value="servico">Serviço (CATSER)</option></select></div>
        <div class="campo"><label for="uf_pr">UF (opcional)</label><input id="uf_pr" name="uf" maxlength="2" placeholder="SP"></div></div>
      <div class="campo"><label for="codigo_pr">Código no catálogo (opcional)</label><input id="codigo_pr" name="codigo_catalogo" placeholder="Deixe em branco para cadastrar preços manualmente">
        <small>Encontre o código em catalogo.compras.gov.br/cnbs-web/busca</small></div>
      <div id="erro-preco"></div><button class="botao" style="width:100%" type="submit">Pesquisar</button></form>`,
  });
  $("#form-preco", m).onsubmit = async (ev) => {
    ev.preventDefault();
    const b = ev.target.querySelector("button");
    await ocupado(b, "Consultando…", async () => {
      try { const p = await api("POST", `/api/empresas/${S.empresaId}/precos`, dadosForm(ev.target)); m.fechar(); abrirPesquisa(p); V.precos($("#conteudo")); }
      catch (e) { $("#erro-preco", m).innerHTML = erroTela(e); }
    });
  };
}

function corpoPesquisa(p) {
  const e = p.estatisticas || {};
  return `
    ${e.n ? `<div class="grade grade-3" style="margin-bottom:16px"><div class="indicador"><b>${fmt.moeda(e.mediana)}</b><span>Mediana (${e.n} amostras)</span></div>
      <div class="indicador"><b>${fmt.moeda(e.faixa_competitiva?.[0])} – ${fmt.moeda(e.faixa_competitiva?.[1])}</b><span>Faixa competitiva sugerida</span></div>
      <div class="indicador"><b>${fmt.moeda(e.minimo)} – ${fmt.moeda(e.maximo)}</b><span>Mínimo e máximo observados</span></div></div>`
      : `<p class="fraco">Nenhuma amostra ainda. Adicione preços manualmente ou informe o código do catálogo.</p>`}
    <div class="tabela-rolagem"><table><thead><tr><th>Preço</th><th>Órgão</th><th>UF</th><th>Data</th><th>Fonte</th></tr></thead>
      <tbody>${(p.amostras || []).map((a) => `<tr><td>${fmt.moeda(a.preco)}</td><td>${esc(a.orgao || "—")}</td><td>${esc(a.uf || "—")}</td><td>${fmt.data(a.data)}</td><td>${esc(a.fonte || "Manual")}</td></tr>`).join("")}</tbody></table></div>
    <h3 style="margin-top:18px">Adicionar amostra manual</h3>
    <form id="form-amostra" class="linha-campos" style="align-items:flex-end">
      <div class="campo"><label>Preço (R$)</label><input name="preco" required inputmode="decimal"></div>
      <div class="campo"><label>Órgão/orçamento</label><input name="orgao"></div>
      <div class="campo"><label>Fonte</label><input name="fonte" placeholder="Ex.: orçamento fornecedor"></div>
      <button class="botao" type="submit">Adicionar</button></form>`;
}

function abrirPesquisa(p) {
  const m = modal({ titulo: p.descricao, largo: true, corpo: corpoPesquisa(p) });
  const religar = () => {
    $("#form-amostra", m).onsubmit = async (ev) => {
      ev.preventDefault();
      const atualizado = await api("POST", `/api/precos/${p.id}/amostras`, dadosForm(ev.target));
      Object.assign(p, atualizado);
      $(".modal-corpo", m).innerHTML = corpoPesquisa(p);
      religar();
      toast("Amostra adicionada.", "ok");
      const el = $("#conteudo"); if (el) V.precos(el);
    };
  };
  religar();
}
