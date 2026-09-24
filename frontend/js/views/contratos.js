// Gestão pós-contrato: vigência, garantia, reajuste e pagamentos.
V.contratos = async (el) => {
  if (!S.empresaId) { el.innerHTML = exigirEmpresa(); return; }
  const lista = await api("GET", `/api/empresas/${S.empresaId}/contratos`);
  el.innerHTML = `
    <div class="cabecalho"><div><h1>Contratos</h1><p>Contratos vigentes de ${esc(empresaAtual().razao_social)}.</p></div>
      <button class="botao" id="novo-contrato">Novo contrato</button></div>
    ${guia(`<p>Cadastre o contrato vencido para acompanhar vigência, garantia e reajuste na agenda automaticamente, e para
      controlar pagamentos: notas fiscais em atraso viram base para o gerador de peças (requerimento de pagamento ou reequilíbrio).</p>`)}
    <section class="bloco">${lista.length ? lista.map(linhaContrato).join("") : vazio("Nenhum contrato cadastrado", "Cadastre um contrato ganho para acompanhar prazos e pagamentos.")}</section>`;
  $("#novo-contrato", el).onclick = () => modalContrato();
  $$("[data-abrir-contrato]", el).forEach((a) => a.onclick = () => { location.hash = `#/contratos/${a.dataset.abrirContrato}`; });
};

function linhaContrato(c) {
  return `<div class="lista-item"><div class="corpo"><b>${esc(c.numero || "Contrato " + c.id)} — ${esc(c.orgao)}</b>
    <p>${esc((c.objeto || "").slice(0, 140))}</p><div class="meta"><span>${fmt.data(c.inicio)} a ${fmt.data(c.fim)}</span><span>${fmt.moeda(c.valor)}</span></div></div>
    <div class="acoes">${c.qtd_atrasados ? carimbo(`${c.qtd_atrasados} pagamento(s) em atraso`, "erro") : carimbo("Pagamentos em dia", "ok")}
      <button class="botao pequeno secundario" data-abrir-contrato="${c.id}">Abrir</button></div></div>`;
}

function modalContrato(c) {
  const m = modal({
    titulo: c ? "Editar contrato" : "Novo contrato", largo: true, corpo: `<form id="form-contrato">
      <div class="linha-campos">
        <div class="campo"><label for="numero_ct">Número do contrato</label><input id="numero_ct" name="numero" value="${esc(c?.numero || "")}"></div>
        <div class="campo"><label for="valor_ct">Valor total (R$)</label><input id="valor_ct" name="valor" inputmode="decimal" value="${c?.valor ?? ""}"></div></div>
      <div class="campo"><label for="orgao_ct">Órgão</label><input id="orgao_ct" name="orgao" required value="${esc(c?.orgao || "")}"></div>
      <div class="campo"><label for="objeto_ct">Objeto</label><input id="objeto_ct" name="objeto" required value="${esc(c?.objeto || "")}"></div>
      <div class="linha-campos">
        <div class="campo"><label for="inicio_ct">Início da vigência</label><input id="inicio_ct" name="inicio" type="date" value="${fmt.paraInput(c?.inicio)}"></div>
        <div class="campo"><label for="fim_ct">Fim da vigência</label><input id="fim_ct" name="fim" type="date" value="${fmt.paraInput(c?.fim)}"></div></div>
      <div class="linha-campos">
        <div class="campo"><label for="base_ct">Data-base do orçamento (reajuste)</label><input id="base_ct" name="data_base_reajuste" type="date" value="${fmt.paraInput(c?.data_base_reajuste)}"></div>
        <div class="campo"><label for="garantia_ct">Validade da garantia</label><input id="garantia_ct" name="garantia_validade" type="date" value="${fmt.paraInput(c?.garantia_validade)}"></div></div>
      <div class="campo"><label for="indice_ct">Índice de reajuste</label><input id="indice_ct" name="indice_reajuste" value="${esc(c?.indice_reajuste || "")}" placeholder="Ex.: IPCA, INPC, convenção coletiva"></div>
      <div id="erro-contrato"></div><button class="botao" style="width:100%" type="submit">Salvar</button></form>`,
  });
  $("#form-contrato", m).onsubmit = async (ev) => {
    ev.preventDefault();
    const b = ev.target.querySelector("button");
    await ocupado(b, "Salvando…", async () => {
      try {
        const r = await api(c ? "PATCH" : "POST", c ? `/api/contratos/${c.id}` : `/api/empresas/${S.empresaId}/contratos`, dadosForm(ev.target));
        m.fechar(); location.hash = `#/contratos/${r.id}`;
        if (location.hash === `#/contratos/${r.id}`) V.contrato($("#conteudo"), r.id);
      } catch (e) { $("#erro-contrato", m).innerHTML = erroTela(e); }
    });
  };
}

V.contrato = async (el, id) => {
  const c = await api("GET", `/api/contratos/${id}`);
  el.innerHTML = `
    <div class="capa"><div class="capa-topo"><div><div class="processo">${esc(c.numero || "Contrato " + c.id)}</div>
        <h1>${esc(c.objeto)}</h1></div><button class="botao secundario" id="editar-contrato">Editar</button></div>
      <dl class="capa-campos">
        <div><dt>Órgão</dt><dd>${esc(c.orgao)}</dd></div><div><dt>Valor</dt><dd>${fmt.moeda(c.valor)}</dd></div>
        <div><dt>Vigência</dt><dd>${fmt.data(c.inicio)} a ${fmt.data(c.fim)}</dd></div>
        <div><dt>Garantia até</dt><dd>${fmt.data(c.garantia_validade)}</dd></div>
        <div><dt>Data-base do reajuste</dt><dd>${fmt.data(c.data_base_reajuste)}</dd></div>
        <div><dt>Índice</dt><dd>${esc(c.indice_reajuste || "—")}</dd></div></dl></div>
    <section class="bloco"><div class="bloco-titulo"><h2>Pagamentos</h2><button class="botao pequeno" id="novo-pagamento">Novo pagamento</button></div>
      ${c.pagamentos.length ? `<div class="tabela-rolagem"><table><thead><tr><th>Referência</th><th>NF</th><th>Valor</th><th>Vencimento</th><th>Situação</th><th></th></tr></thead>
      <tbody>${c.pagamentos.map(linhaPagamento).join("")}</tbody></table></div>` : vazio("Nenhum pagamento lançado", "Cadastre as notas fiscais para acompanhar atrasos.")}</section>
    <section class="bloco"><div class="bloco-titulo"><h2>Peças deste contrato</h2>
      <a class="botao pequeno secundario" href="#/pecas">Gerar peça</a></div>
      ${c.pecas.length ? c.pecas.map((p) => `<div class="lista-item"><div class="corpo"><b>${esc(p.titulo)}</b><p>${fmt.dataHora(p.criado_em)}</p></div>
        <a class="botao pequeno secundario" href="#/pecas/${p.id}">Abrir</a></div>`).join("") : vazio("Nenhuma peça ainda", "")}</section>`;
  $("#editar-contrato", el).onclick = () => modalContrato(c);
  $("#novo-pagamento", el).onclick = () => modalPagamento(c.id);
  $$("[data-pago]", el).forEach((b) => b.onclick = async () => { await api("PATCH", `/api/pagamentos/${b.dataset.pago}`, { pago_em: new Date().toISOString().slice(0, 10) }); V.contrato(el, id); });
  $$("[data-excluir-pgto]", el).forEach((b) => b.onclick = async () => { if (await confirmar("Excluir este pagamento?", "Excluir")) { await api("DELETE", `/api/pagamentos/${b.dataset.excluirPgto}`); V.contrato(el, id); } });
};

function linhaPagamento(p) {
  const sit = { pago: ["Pago", "ok"], atrasado: ["Atrasado" + (p.dias_atraso ? ` (${p.dias_atraso}d)` : ""), "erro"], a_receber: ["A receber", "neutro"] }[p.situacao];
  return `<tr><td>${esc(p.referencia || "—")}</td><td>${esc(p.nota_fiscal || "—")}</td><td>${fmt.moeda(p.valor)}</td><td>${fmt.data(p.vencimento)}</td>
    <td>${carimbo(sit[0], sit[1])}</td><td>${p.situacao !== "pago" ? `<button class="botao texto pequeno" data-pago="${p.id}">Marcar pago</button>` : ""}
    <button class="botao texto pequeno" data-excluir-pgto="${p.id}">Excluir</button></td></tr>`;
}

function modalPagamento(contratoId) {
  const m = modal({
    titulo: "Novo pagamento", corpo: `<form id="form-pgto">
      <div class="linha-campos"><div class="campo"><label for="ref_pg">Referência</label><input id="ref_pg" name="referencia" placeholder="Ex.: Medição de julho"></div>
        <div class="campo"><label for="nf_pg">Nota fiscal</label><input id="nf_pg" name="nota_fiscal"></div></div>
      <div class="linha-campos"><div class="campo"><label for="valor_pg">Valor (R$)</label><input id="valor_pg" name="valor" required inputmode="decimal"></div>
        <div class="campo"><label for="venc_pg">Vencimento</label><input id="venc_pg" name="vencimento" type="date" required></div></div>
      <div id="erro-pgto"></div><button class="botao" style="width:100%" type="submit">Salvar</button></form>`,
  });
  $("#form-pgto", m).onsubmit = async (ev) => {
    ev.preventDefault();
    try { await api("POST", `/api/contratos/${contratoId}/pagamentos`, dadosForm(ev.target)); m.fechar(); V.contrato($("#conteudo"), contratoId); }
    catch (e) { $("#erro-pgto", m).innerHTML = erroTela(e); }
  };
}
