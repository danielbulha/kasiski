// Preços e propostas: minutas de proposta comercial com formação de preço, pesquisas de preço
// (Compras.gov.br) e consulta às tabelas oficiais de referência (SINAPI, SICRO, CMED, CCT...).
const SITUACAO_ITEM = { acima_estimado: ["Acima do estimado", "erro"], inexequivel: ["Inexequível (<75%)", "erro"],
  garantia_adicional: ["Garantia adicional (<85%)", "aviso"], indicio_inexequivel: ["Indício de inexequibilidade (<50%)", "aviso"],
  prejuizo: ["Abaixo do custo", "erro"] };
const STATUS_PROPOSTA = { lendo_edital: ["Lendo o edital", "aviso"], rascunho: ["Rascunho", "neutro"], gerando: ["Gerando minuta", "aviso"],
  pronta: ["Minuta pronta", "ok"], erro: ["Erro", "erro"] };

V.precos = async (el) => {
  if (!S.empresaId) { el.innerHTML = exigirEmpresa(); return; }
  const aba = V.precos.aba || "propostas";
  el.innerHTML = `
    <div class="cabecalho"><div><h1>Preços e propostas</h1><p>Inteligência de preços e propostas comerciais de ${esc(empresaAtual().razao_social)}.</p></div>
      <button class="botao" id="nova-acao">${icone("adicionar")} ${aba === "pesquisas" ? "Nova pesquisa" : "Nova proposta"}</button></div>
    <div class="abas" role="tablist">
      ${[["propostas", "Propostas comerciais"], ["pesquisas", "Pesquisas de preço"], ["tabelas", "Tabelas de referência"]]
        .map(([k, t]) => `<button role="tab" data-aba-pr="${k}" class="${aba === k ? "ativa" : ""}" aria-selected="${aba === k}">${t}</button>`).join("")}
    </div><div id="painel-precos"><p class="carregando">Carregando…</p></div>`;
  $$("[data-aba-pr]", el).forEach((b) => b.onclick = () => { V.precos.aba = b.dataset.abaPr; V.precos(el); });
  $("#nova-acao", el).onclick = () => (aba === "pesquisas" ? modalPesquisa() : modalNovaProposta());
  const painel = $("#painel-precos", el);
  try {
    if (aba === "propostas") await abaPropostas(painel);
    else if (aba === "pesquisas") await abaPesquisas(painel);
    else await abaTabelasRef(painel);
  } catch (e) { painel.innerHTML = erroTela(e); }
};

function upsellPropostas() {
  return `<section class="bloco destaque-plano"><h2>Proposta comercial com IA</h2>
    <p>A leitura das regras da proposta no edital, a formação do preço com BDI e tributos, a checagem de exequibilidade e a minuta em Word
    fazem parte dos planos <b>Avançado</b> (${fmt.moeda(S.planos.avancado?.preco || 799)}/mês) e <b>Consultor</b>.</p>
    <a class="botao" href="#/conta">Ver planos</a></section>`;
}

function modalUpsellPropostas() {
  modal({ titulo: "Disponível no plano Avançado", corpo: `<p>A elaboração da proposta comercial com IA faz parte dos planos Avançado e Consultor.
    Seu plano atual (${esc(S.plano?.nome || "")}) inclui as pesquisas de preço e a consulta às tabelas de referência.</p>`,
    acoes: `<a class="botao" href="#/conta" data-fechar>Ver planos</a>` });
}

async function abaPropostas(el) {
  const lista = await api("GET", `/api/empresas/${S.empresaId}/propostas`);
  if (!S.plano?.propostas && !lista.length) { el.innerHTML = upsellPropostas(); return; }
  el.innerHTML = `${!S.plano?.propostas ? upsellPropostas() : ""}${guia(`<p>Escolha um edital e o Kasiski lê o que ele exige da proposta: itens, quantidades, valores estimados, validade,
      documentos e declarações. Você informa o custo de cada item (ou busca nas tabelas oficiais e nos preços praticados), define BDI e tributos,
      e a IA redige a minuta e aponta riscos de desclassificação. A minuta sai em Word para assinar.</p>`)}
    <section class="bloco">${lista.length ? lista.map((p) => `<div class="lista-item"><div class="corpo"><b>${esc(p.titulo)}</b>
      <p>${carimboStatus(STATUS_PROPOSTA, p.status)} · ${p.n_itens} item(ns) · total ${fmt.moeda(p.totais.total)}${p.totais.total_estimado ? ` · estimado ${fmt.moeda(p.totais.total_estimado)}` : ""} · ${fmt.data(p.atualizado_em)}</p></div>
      <div class="acoes"><a class="botao pequeno secundario" href="#/propostas/${p.id}">Abrir</a></div></div>`).join("")
    : vazio("Nenhuma proposta ainda", "Monte a primeira proposta comercial a partir de um edital cadastrado.", `<button class="botao" id="primeira-proposta">Nova proposta</button>`)}</section>`;
  const b = $("#primeira-proposta", el); if (b) b.onclick = () => modalNovaProposta();
}

async function modalNovaProposta(editalId) {
  if (!S.plano?.propostas) { modalUpsellPropostas(); return; }
  const editais = await api("GET", `/api/empresas/${S.empresaId}/editais`);
  const m = modal({ titulo: "Nova proposta comercial", corpo: `<form id="form-nova-prop">
    <div class="campo"><label for="np-edital">Edital</label><select id="np-edital" name="edital_id">
      <option value="">Sem edital (itens cadastrados à mão)</option>
      ${editais.map((e) => `<option value="${e.id}" ${e.id == editalId ? "selected" : ""}>${esc(e.numero || "s/ nº")} · ${esc((e.objeto || e.orgao || "").slice(0, 80))}${e.tem_texto ? "" : " (sem PDF)"}</option>`).join("")}</select>
      <small>Com o PDF do edital, a IA lê os itens, quantidades e regras da proposta.</small></div>
    <div class="campo"><label for="np-regime">Regime tributário da empresa</label><select id="np-regime" name="regime">
      <option value="simples">Simples Nacional</option><option value="presumido">Lucro Presumido</option><option value="real">Lucro Real</option></select></div>
    <div class="campo"><label for="np-titulo">Nome da proposta (opcional)</label><input id="np-titulo" name="titulo"></div>
    <div id="erro-np"></div><button class="botao" style="width:100%" type="submit">Criar proposta</button></form>` });
  $("#form-nova-prop", m).onsubmit = async (ev) => {
    ev.preventDefault();
    await ocupado(ev.target.querySelector("button"), "Criando…", async () => {
      try { const p = await api("POST", `/api/empresas/${S.empresaId}/propostas`, dadosForm(ev.target)); m.fechar(); location.hash = `#/propostas/${p.id}`; }
      catch (e) { $("#erro-np", m).innerHTML = erroTela(e); }
    });
  };
}

async function abaPesquisas(el) {
  const lista = await api("GET", `/api/empresas/${S.empresaId}/precos`);
  el.innerHTML = `${guia(`<p>Informe o código CATMAT (material) ou CATSER (serviço) do Compras.gov.br para trazer preços já homologados em
      compras públicas recentes. Sem o código, cadastre a pesquisa e some orçamentos manuais para calcular a faixa competitiva.</p>`)}
    <section class="bloco">${lista.length ? lista.map(linhaPreco).join("") : vazio("Nenhuma pesquisa ainda", "Cadastre a primeira pesquisa de preço.")}</section>`;
  $$("[data-abrir-preco]", el).forEach((b) => b.onclick = () => abrirPesquisa(lista.find((p) => p.id == b.dataset.abrirPreco)));
  $$("[data-excluir-preco]", el).forEach((b) => b.onclick = async () => { if (await confirmar("Excluir esta pesquisa?", "Excluir")) { await api("DELETE", `/api/precos/${b.dataset.excluirPreco}`); abaPesquisas(el); } });
}

async function abaTabelasRef(el) {
  const tabs = await api("GET", "/api/tabelas-referencia");
  el.innerHTML = `<section class="bloco">
    <p class="fraco">${tabs.length ? `Tabelas disponíveis: ${tabs.map((t) => `${esc(t.nome)}${t.data_base ? ` (${fmt.data(t.data_base)})` : ""}`).join(" · ")}` : "Nenhuma tabela de referência carregada ainda."}</p>
    <form id="form-busca-ref" class="linha-campos" style="align-items:flex-end">
      <div class="campo" style="grid-column:span 2"><label for="br-q">Buscar item</label><input id="br-q" name="q" placeholder="Ex.: servente, cimento CP II, dipirona 500mg" required minlength="3"></div>
      <div class="campo"><label for="br-uf">UF</label><input id="br-uf" name="uf" maxlength="2" value="${esc((empresaAtual().ufs || "").slice(0, 2))}"></div>
      <button class="botao" type="submit">Buscar</button></form>
    <div id="res-ref"></div></section>`;
  $("#form-busca-ref", el).onsubmit = async (ev) => {
    ev.preventDefault();
    const d = dadosForm(ev.target);
    try {
      const r = await api("GET", `/api/tabelas-referencia/buscar?q=${encodeURIComponent(d.q)}&uf=${encodeURIComponent(d.uf || "")}`);
      $("#res-ref", el).innerHTML = r.length ? tabelaRefs(r, false) : vazio("Nada encontrado", "Tente termos mais curtos ou outra UF.");
    } catch (e) { $("#res-ref", el).innerHTML = erroTela(e); }
  };
}

function tabelaRefs(refs, comUso) {
  return `<div class="tabela-rolagem"><table><thead><tr><th>Tabela</th><th>Código</th><th>Descrição</th><th>Unid.</th><th>Preço</th>${comUso ? "<th></th>" : ""}</tr></thead>
    <tbody>${refs.map((r, i) => `<tr><td>${esc(r.tabela)}${r.data_base ? `<br><small>${fmt.data(r.data_base)}${r.uf ? " · " + esc(r.uf) : ""}</small>` : ""}</td>
      <td>${esc(r.codigo || "—")}</td><td>${esc(r.descricao)}</td><td>${esc(r.unidade || "—")}</td><td>${fmt.moeda(r.preco)}</td>
      ${comUso ? `<td><button class="botao pequeno secundario" data-usar-ref="${i}">Usar como custo</button></td>` : ""}</tr>`).join("")}</tbody></table></div>`;
}

// ---------------------------------------------------------------- editor da proposta
V.proposta = async (el, id) => {
  let p = await api("GET", `/api/propostas/${id}`);
  const edital = p.edital_id ? (await api("GET", `/api/editais/${p.edital_id}`).catch(() => null))?.edital : null;
  const desenhar = () => {
    const c = p.condicoes || {}, t = p.totais;
    const ocupada = ["lendo_edital", "gerando"].includes(p.status);
    el.innerHTML = `
      <div class="cabecalho"><div><p class="fraco" style="margin:0"><a href="#/precos">← Preços e propostas</a></p>
        <h1>${esc(p.titulo)}</h1><p>${carimboStatus(STATUS_PROPOSTA, p.status)}${edital ? ` · <a href="#/editais/${edital.id}">${esc(edital.numero || "edital")} · ${esc(edital.orgao || "")}</a>` : ""}</p></div>
        <div class="acoes">
          ${p.edital_id ? `<button class="botao secundario" id="reler" ${ocupada ? "disabled" : ""}>Reler edital</button>` : ""}
          <button class="botao" id="gerar-minuta" ${ocupada ? "disabled" : ""}>${p.texto ? "Refazer minuta" : "Gerar minuta"}</button>
          <button class="botao secundario" id="baixar-docx" ${p.itens.length ? "" : "disabled"}>Baixar Word</button>
          <button class="botao texto" id="excluir-prop">${icone("excluir", 14)} Excluir</button></div></div>
      ${ocupada ? `<div class="aviso info andamento-analise" role="status"><span class="girando" aria-hidden="true"></span><div><b>${esc(STATUS_PROPOSTA[p.status][0])}…</b> ${esc(p.etapa || "")}<br><small>Pode levar alguns minutos. Pode sair desta tela: o trabalho continua.</small></div></div>` : ""}
      ${p.erro ? `<div class="aviso erro">${esc(p.erro)}</div>` : ""}
      ${p.demonstracao ? `<div class="aviso info">Resultado de demonstração: configure as chaves de IA para ler o edital e redigir a proposta de verdade.</div>` : ""}
      ${Object.keys(c).length ? blocoCondicoes(c) : ""}
      <section class="bloco"><div class="bloco-titulo"><h2>Formação do preço</h2></div>
        <form id="form-param" class="linha-campos">
          <div class="campo"><label for="pp-regime">Regime tributário</label><select id="pp-regime" name="regime">
            ${Object.entries(p.regimes).map(([k, r]) => `<option value="${k}" ${p.regime === k ? "selected" : ""}>${esc(r.nome)}</option>`).join("")}</select>
            <small>${esc(p.regimes[p.regime]?.nota || "")}</small></div>
          <div class="campo"><label for="pp-trib">Tributos sobre o preço (%)</label><input id="pp-trib" name="tributos_pct" inputmode="decimal" value="${fmt.num(p.tributos_pct)}"></div>
          <div class="campo"><label for="pp-bdi">BDI / margem padrão (%)</label><input id="pp-bdi" name="bdi_pct" inputmode="decimal" value="${fmt.num(p.bdi_pct)}">
            <button type="button" class="botao texto pequeno" id="calc-bdi" style="align-self:flex-start;padding-left:0">Calcular pela fórmula do TCU</button></div>
          <div class="campo"><label for="pp-val">Validade da proposta (dias)</label><input id="pp-val" name="validade_dias" inputmode="numeric" value="${p.validade_dias}">
            ${c.validade_minima_dias ? `<small>Mínimo do edital: ${esc(c.validade_minima_dias)} dias</small>` : ""}</div>
        </form>
        <p class="fraco" style="margin:0">Preço unitário = custo unitário × (1 + BDI). O BDI da fórmula do TCU já embute os tributos informados.</p></section>
      <section class="bloco"><div class="bloco-titulo"><h2>Itens</h2><button class="botao pequeno secundario" id="add-item">${icone("adicionar", 14)} Adicionar item</button></div>
        <div class="tabela-rolagem"><table class="tabela-itens"><thead><tr><th>Item</th><th>Descrição</th><th>Unid.</th><th>Qtd.</th><th>Estimado unit.</th>
          <th>Custo unit.</th><th>BDI %</th><th>Preço unit.</th><th>Total</th><th></th></tr></thead>
          <tbody>${p.itens.length ? p.itens.map(linhaItem).join("") : `<tr><td colspan="10">${vazio("Nenhum item", ocupada ? "Aguarde a leitura do edital." : "Adicione os itens da proposta.")}</td></tr>`}</tbody></table></div>
        <div class="grade grade-4 grade-kpi" style="margin-top:16px">
          <div class="indicador"><b>${fmt.moeda(t.total)}</b><span>valor global da proposta</span></div>
          <div class="indicador"><b>${t.total_estimado ? fmt.moeda(t.total_estimado) : "—"}</b><span>estimado pela Administração${t.total_estimado && t.total ? ` · ${Math.round(100 * t.total / t.total_estimado)}%` : ""}</span></div>
          <div class="indicador"><b>${t.custo_total ? fmt.moeda(t.custo_total) : "—"}</b><span>custo direto total</span></div>
          <div class="indicador ${t.margem_bruta !== null && t.margem_bruta < 0 ? "alerta" : ""}"><b>${t.margem_bruta !== null ? fmt.moeda(t.margem_bruta) : "—"}</b><span>BDI em reais (custos indiretos, tributos e lucro)</span></div>
        </div></section>
      ${p.alertas.length ? `<section class="bloco"><h2>Pontos de atenção</h2>${p.alertas.map((a) => `<div class="lista-item"><div class="corpo">
        ${carimbo(a.nivel === "alto" ? "Alto" : a.nivel === "medio" ? "Médio" : "Baixo", a.nivel === "alto" ? "erro" : a.nivel === "medio" ? "aviso" : "neutro")}
        ${esc(a.texto)}${a.fundamento ? ` <small class="fraco">(${esc(a.fundamento)})</small>` : ""}${a.origem === "ia" ? ` <small class="fraco">· revisão da IA</small>` : ""}</div></div>`).join("")}</section>` : ""}
      <section class="bloco"><div class="bloco-titulo"><h2>Minuta da proposta</h2>${p.texto ? `<button class="botao pequeno secundario" id="salvar-texto">Salvar texto</button>` : ""}</div>
        ${p.texto ? `<p class="fraco">Edite à vontade. <code>{{TABELA_ITENS}}</code> e <code>{{VALOR_TOTAL}}</code> são preenchidos com a tabela de itens e o valor por extenso no Word.</p>
          <textarea class="editor" id="texto-minuta" style="min-height:420px">${esc(p.texto)}</textarea>`
          : `<p class="fraco">Precifique os itens e clique em <b>Gerar minuta</b>. A IA redige a proposta com as condições e declarações que o edital exige e revisa os preços.</p>`}</section>`;
    ligar();
    if (ocupada) setTimeout(acompanhar, 4000);
  };

  const salvar = async (mudancas) => {
    try { p = await api("PATCH", `/api/propostas/${id}`, mudancas); desenharMantendoFoco(); }
    catch (e) { avisarErro(e); }
  };
  const desenharMantendoFoco = () => {
    const ativo = document.activeElement, chave = ativo?.dataset?.campo ? `[data-campo="${ativo.dataset.campo}"][data-i="${ativo.dataset.i}"]` : ativo?.id ? `#${ativo.id}` : null;
    const rolagem = window.scrollY;
    desenhar();
    window.scrollTo(0, rolagem);
    if (chave) { const n = $(chave, el); if (n) { n.focus(); if (n.select) n.select(); } }
  };
  const acompanhar = async () => {
    if (!document.body.contains(el) || location.hash !== `#/propostas/${id}`) return;
    try { p = await api("GET", `/api/propostas/${id}`); } catch { setTimeout(acompanhar, 8000); return; }
    if (["lendo_edital", "gerando"].includes(p.status)) { setTimeout(acompanhar, 4000); const box = $(".andamento-analise b", el); if (box) box.nextSibling.textContent = " " + (p.etapa || ""); return; }
    desenhar();
    if (p.status === "pronta") toast("Minuta pronta.", "ok");
  };

  const ligar = () => {
    const itensAtuais = () => p.itens.map((it) => ({ ...it }));
    $("#form-param", el).addEventListener("change", (ev) => {
      const d = dadosForm($("#form-param", el));
      if (ev.target.name === "regime") d.tributos_pct = p.regimes[d.regime].tributos_pct;
      salvar(d);
    });
    $("#calc-bdi", el).onclick = () => modalBdi(p, (d) => salvar(d));
    $$("[data-campo]", el).forEach((inp) => inp.addEventListener("change", () => {
      const itens = itensAtuais(), i = Number(inp.dataset.i), campo = inp.dataset.campo;
      let v = inp.value;
      if (["quantidade", "custo_unitario", "bdi", "preco_unitario", "valor_unitario_estimado"].includes(campo)) v = v === "" ? null : v;
      itens[i][campo] = v;
      if (campo === "preco_unitario") itens[i].preco_manual = v !== null;
      if (campo === "custo_unitario") itens[i].preco_manual = false;
      salvar({ itens });
    }));
    $$("[data-remover]", el).forEach((b) => b.onclick = async () => {
      if (!(await confirmar("Remover este item?", "Remover"))) return;
      const itens = itensAtuais(); itens.splice(Number(b.dataset.remover), 1); salvar({ itens });
    });
    $$("[data-refs]", el).forEach((b) => b.onclick = () => modalReferencias(p, Number(b.dataset.refs), (itens) => salvar({ itens })));
    $("#add-item", el).onclick = () => salvar({ itens: [...itensAtuais(), { numero: String(p.itens.length + 1), descricao: "Novo item", unidade: "un", quantidade: 1 }] });
    const reler = $("#reler", el);
    if (reler) reler.onclick = async () => {
      if (p.itens.length && !(await confirmar("Reler o edital substitui a lista de itens atual pelos itens do edital. Continuar?", "Reler"))) return;
      try { p = await api("POST", `/api/propostas/${id}/reler-edital`); desenhar(); } catch (e) { avisarErro(e); }
    };
    $("#gerar-minuta", el).onclick = async () => {
      try { p = await api("POST", `/api/propostas/${id}/minuta`); desenhar(); } catch (e) { avisarErro(e); }
    };
    $("#baixar-docx", el).onclick = async (ev) => {
      await ocupado(ev.target, "Gerando…", async () => {
        try {
          const txt = $("#texto-minuta", el);
          if (txt && txt.value !== p.texto) p = await api("PATCH", `/api/propostas/${id}`, { texto: txt.value });
          await baixar(`/api/propostas/${id}/docx`, `${(p.titulo || "proposta").replace(/[^\w\-]+/g, "_")}.docx`);
        } catch (e) { avisarErro(e); }
      });
    };
    const st = $("#salvar-texto", el);
    if (st) st.onclick = async () => { await salvar({ texto: $("#texto-minuta", el).value }); toast("Texto salvo.", "ok"); };
    $("#excluir-prop", el).onclick = async () => {
      if (!(await confirmar("Excluir esta proposta?", "Excluir"))) return;
      await api("DELETE", `/api/propostas/${id}`); location.hash = "#/precos";
    };
  };
  desenhar();
};

function blocoCondicoes(c) {
  const linha = (rot, v) => (v === undefined || v === null || v === "" || (Array.isArray(v) && !v.length) ? "" :
    `<div class="lista-item"><div class="corpo"><b>${esc(rot)}</b><p>${Array.isArray(v) ? v.map(esc).join(" · ") : esc(v === true ? "Sim" : v === false ? "Não" : v)}</p></div></div>`);
  return `<section class="bloco"><details ${c.observacoes_importantes?.length ? "open" : ""}><summary><b>O que o edital exige da proposta</b></summary>
    <div class="grade grade-2" style="margin-top:10px"><div>
      ${linha("Critério de julgamento", c.criterio_julgamento)}${linha("Modo de disputa", c.modo_disputa)}
      ${linha("Orçamento", c.orcamento_sigiloso ? "Sigiloso" : c.valor_estimado_global ? fmt.moeda(c.valor_estimado_global) : "")}
      ${linha("Validade mínima", c.validade_minima_dias ? `${c.validade_minima_dias} dias` : "")}${linha("Prazo de entrega/execução", c.prazo_entrega_execucao)}
      ${linha("Local", c.local_entrega)}${linha("Pagamento", c.condicoes_pagamento)}${linha("Reajuste", c.reajuste)}</div><div>
      ${linha("Planilha de custos exigida", c.exige_planilha_custos)}${linha("Composição do BDI exigida", c.exige_composicao_bdi)}${linha("BDI de referência", c.bdi_referencia)}
      ${linha("Marca e modelo", c.exige_marca_modelo)}${linha("Amostra / prova de conceito", c.amostra_ou_prova_conceito)}${linha("Garantia de proposta", c.garantia_proposta)}
      ${linha("Casas decimais", c.casas_decimais)}${linha("Forma de apresentação", c.forma_apresentacao)}
      ${linha("Documentos com a proposta", c.documentos_com_proposta)}${linha("Declarações exigidas", c.declaracoes_exigidas)}${linha("Atenção", c.observacoes_importantes)}</div></div>
  </details></section>`;
}

function linhaItem(it, i) {
  const num = (v) => (v === null || v === undefined ? "" : String(v).replace(".", ","));
  const din = (v) => (v === null || v === undefined || v === "" ? "" : Number(v).toFixed(2).replace(".", ","));
  const sit = (it.situacao || []).map((s) => carimboStatus(SITUACAO_ITEM, s)).join(" ");
  const ref = it.referencias || {};
  const dica = [ref.tabela ? `Tabela: ${ref.tabela.nome} ${fmt.moeda(ref.tabela.preco)}` : "", ref.mercado?.mediana ? `Mercado: mediana ${fmt.moeda(ref.mercado.mediana)} (${ref.mercado.n} amostras)` : ""].filter(Boolean).join(" · ");
  return `<tr>
    <td><input class="celula curta" data-campo="numero" data-i="${i}" value="${esc(it.numero || "")}" aria-label="Número do item"></td>
    <td><textarea class="celula" rows="2" data-campo="descricao" data-i="${i}" aria-label="Descrição">${esc(it.descricao || "")}</textarea>
      ${dica ? `<small class="fraco">${esc(dica)}</small>` : ""}${sit ? `<div>${sit}</div>` : ""}</td>
    <td><input class="celula curta" data-campo="unidade" data-i="${i}" value="${esc(it.unidade || "")}" aria-label="Unidade"></td>
    <td><input class="celula curta" data-campo="quantidade" data-i="${i}" value="${num(it.quantidade)}" inputmode="decimal" aria-label="Quantidade"></td>
    <td><input class="celula" data-campo="valor_unitario_estimado" data-i="${i}" value="${din(it.valor_unitario_estimado)}" inputmode="decimal" aria-label="Estimado unitário" placeholder="—"></td>
    <td><input class="celula" data-campo="custo_unitario" data-i="${i}" value="${din(it.custo_unitario)}" inputmode="decimal" aria-label="Custo unitário" placeholder="custo"></td>
    <td><input class="celula curta" data-campo="bdi" data-i="${i}" value="${num(it.bdi)}" inputmode="decimal" aria-label="BDI do item" placeholder="—" title="Vazio = BDI padrão da proposta"></td>
    <td><input class="celula" data-campo="preco_unitario" data-i="${i}" value="${din(it.preco_unitario)}" inputmode="decimal" aria-label="Preço unitário" title="Calculado pelo custo e BDI. Digite para fixar um preço manual.">
      ${it.pct_estimado ? `<small class="fraco">${it.pct_estimado}% do est.</small>` : ""}${it.pct_mercado ? `<small class="fraco"> · ${it.pct_mercado}% do mercado</small>` : ""}</td>
    <td class="num">${fmt.moeda(it.preco_total)}</td>
    <td class="acoes-celula"><button class="botao pequeno secundario" data-refs="${i}" title="Tabelas oficiais e preços praticados">Preços</button>
      <button class="botao texto pequeno" data-remover="${i}" aria-label="Remover item">${icone("excluir", 14)}</button></td></tr>`;
}

function modalBdi(p, aoAplicar) {
  const d = { ac: 4.0, sg: 0.8, r: 1.27, df: 1.23, l: 7.4, ...(p.bdi_detalhe || {}) };
  const m = modal({ titulo: "BDI pela fórmula do TCU", corpo: `<form id="form-bdi">
    <p class="fraco">Acórdão TCU 2.622/2013: BDI = [(1+AC+S+R+G)(1+DF)(1+L)/(1−I)] − 1. Os valores iniciais são exemplos típicos de obras; ajuste à sua realidade.</p>
    <div class="linha-campos">
      ${[["ac", "Administração central (AC) %"], ["sg", "Seguros e garantias (S+G) %"], ["r", "Riscos (R) %"], ["df", "Despesas financeiras (DF) %"], ["l", "Lucro (L) %"]]
        .map(([k, t]) => `<div class="campo"><label for="bdi-${k}">${t}</label><input id="bdi-${k}" name="${k}" inputmode="decimal" value="${fmt.num(d[k])}"></div>`).join("")}
      <div class="campo"><label>Tributos (I) %</label><input value="${fmt.num(p.tributos_pct)}" disabled><small>Definido em "Tributos sobre o preço".</small></div>
    </div>
    <p id="bdi-resultado" style="font-size:1.2rem;font-weight:700"></p>
    <button class="botao" style="width:100%" type="submit">Aplicar este BDI</button></form>` });
  const calc = () => {
    const v = (k) => Number(String($(`#bdi-${k}`, m).value).replace(",", ".")) / 100 || 0;
    const i = p.tributos_pct / 100;
    const bdi = (((1 + v("ac") + v("sg") + v("r")) * (1 + v("df")) * (1 + v("l"))) / (1 - i) - 1) * 100;
    $("#bdi-resultado", m).textContent = `BDI resultante: ${fmt.num(bdi)}%`;
  };
  $("#form-bdi", m).addEventListener("input", calc); calc();
  $("#form-bdi", m).onsubmit = (ev) => { ev.preventDefault(); m.fechar(); aoAplicar({ bdi_detalhe: dadosForm(ev.target), aplicar_bdi_tcu: true }); };
}

async function modalReferencias(p, i, aoSalvar) {
  const it = { ...p.itens[i] };
  const m = modal({ titulo: `Preços de referência · item ${it.numero || i + 1}`, largo: true, corpo: `
    <p><b>${esc(it.descricao)}</b></p>
    <form id="form-refs" class="linha-campos" style="align-items:flex-end">
      <div class="campo" style="grid-column:span 2"><label for="rf-desc">Buscar por</label><input id="rf-desc" name="descricao" value="${esc(it.descricao)}"></div>
      <div class="campo"><label for="rf-cat">Código CATMAT/CATSER</label><input id="rf-cat" name="catmat" value="${esc(it.catmat || "")}" inputmode="numeric" placeholder="opcional"></div>
      <div class="campo"><label for="rf-tipo">Tipo</label><select id="rf-tipo" name="tipo_catalogo"><option value="material">Material</option><option value="servico" ${it.tipo_catalogo === "servico" ? "selected" : ""}>Serviço</option></select></div>
      <button class="botao" type="submit">Buscar</button></form>
    <div id="rf-res"><p class="carregando">Buscando…</p></div>` });
  const buscar = async () => {
    const d = dadosForm($("#form-refs", m));
    $("#rf-res", m).innerHTML = `<p class="carregando">Buscando nas tabelas oficiais${d.catmat ? " e no Compras.gov.br" : ""}…</p>`;
    let r;
    try { r = await api("POST", `/api/propostas/${p.id}/referencias`, d); } catch (e) { $("#rf-res", m).innerHTML = erroTela(e); return; }
    const e = r.mercado?.estatisticas || {};
    $("#rf-res", m).innerHTML = `
      <h3>Preços praticados em compras públicas</h3>
      ${r.mercado ? (e.n ? `<div class="grade grade-3" style="margin-bottom:10px">
          <div class="indicador"><b>${fmt.moeda(e.mediana)}</b><span>mediana (${e.n} amostras${r.mercado.uf ? `, ${esc(r.mercado.uf)}` : ""})</span></div>
          <div class="indicador"><b>${fmt.moeda(e.faixa_competitiva?.[0])} – ${fmt.moeda(e.faixa_competitiva?.[1])}</b><span>faixa competitiva</span></div>
          <div class="indicador"><b>${fmt.moeda(e.minimo)} – ${fmt.moeda(e.maximo)}</b><span>mínimo e máximo</span></div></div>
          <button class="botao pequeno secundario" id="usar-mercado">Guardar como referência de mercado</button>`
        : `<p class="fraco">Nenhum preço encontrado no Compras.gov.br para este código.</p>`)
        : `<p class="fraco">Informe o código CATMAT/CATSER para consultar os preços homologados no Compras.gov.br. Encontre o código em catalogo.compras.gov.br.</p>`}
      ${r.pesquisas.length ? `<p class="fraco" style="margin-top:10px">Suas pesquisas parecidas: ${r.pesquisas.map((s) => `${esc(s.descricao)} (mediana ${fmt.moeda(s.estatisticas.mediana)})`).join(" · ")}</p>` : ""}
      <h3 style="margin-top:18px">Tabelas oficiais de referência</h3>
      ${r.tabelas.length ? tabelaRefs(r.tabelas, true) : `<p class="fraco">${r.tem_tabelas ? "Nenhum item parecido nas tabelas carregadas. Tente outros termos." : "Nenhuma tabela de referência carregada ainda (o administrador envia pelo painel)."}</p>`}`;
    $$("[data-usar-ref]", m).forEach((b) => b.onclick = () => {
      const ref = r.tabelas[Number(b.dataset.usarRef)];
      const itens = p.itens.map((x) => ({ ...x }));
      itens[i] = { ...itens[i], custo_unitario: ref.preco, preco_manual: false, catmat: d.catmat, tipo_catalogo: d.tipo_catalogo,
        referencias: { ...(itens[i].referencias || {}), tabela: { nome: ref.tabela, codigo: ref.codigo, descricao: ref.descricao, preco: ref.preco, unidade: ref.unidade, data_base: ref.data_base } } };
      m.fechar(); aoSalvar(itens); toast("Custo preenchido pela tabela. Confira a unidade antes de seguir.", "ok");
    });
    const um = $("#usar-mercado", m);
    if (um) um.onclick = () => {
      const itens = p.itens.map((x) => ({ ...x }));
      itens[i] = { ...itens[i], catmat: d.catmat, tipo_catalogo: d.tipo_catalogo,
        referencias: { ...(itens[i].referencias || {}), mercado: { codigo: d.catmat, mediana: e.mediana, faixa: e.faixa_competitiva, n: e.n } } };
      m.fechar(); aoSalvar(itens); toast("Referência de mercado guardada no item.", "ok");
    };
  };
  $("#form-refs", m).onsubmit = (ev) => { ev.preventDefault(); buscar(); };
  buscar();
}

// ---------------------------------------------------------------- pesquisas de preço (Compras.gov.br)
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
      try { const p = await api("POST", `/api/empresas/${S.empresaId}/precos`, dadosForm(ev.target)); m.fechar(); abrirPesquisa(p); V.precos.aba = "pesquisas"; V.precos($("#conteudo")); }
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
