// Gestão de contratos: cadastro pelo PDF (a IA preenche os dados), rotinas de gestão, prazos preventivos e pagamentos.
const TIPO_PRAZO_CT = { prorrogacao: ["Prorrogação", "aviso"], vigencia: ["Vigência", "erro"], garantia: ["Garantia", "aviso"],
  reajuste: ["Reajuste", "oficio"], medicao: ["Medição", "neutro"], faturamento: ["Faturamento", "neutro"], obrigacao: ["Obrigação", "neutro"], manual: ["Manual", "neutro"] };

V.contratos = async (el) => {
  if (!S.empresaId) { el.innerHTML = exigirEmpresa(); return; }
  const g = await api("GET", `/api/empresas/${S.empresaId}/gestao-contratos`);
  if (!g.plano_permite) {
    el.innerHTML = `<div class="cabecalho"><div><h1>Gestão de contratos</h1></div></div>
      <section class="bloco destaque-plano"><h2>Gestão de contratos com IA</h2>
        <p>Envie o PDF do contrato e o Kasiski preenche vigência, garantia, reajuste, medição e faturamento, monta a agenda de gestão e avisa
        por e-mail antes de cada prazo. Disponível a partir do plano <b>Profissional</b> (10 contratos), <b>Avançado</b> (30) e <b>Consultor</b> (50).</p>
        <a class="botao" href="#/conta">Ver planos</a></section>`;
    return;
  }
  const lista = await api("GET", `/api/empresas/${S.empresaId}/contratos`);
  const cheio = g.uso >= g.limite;
  el.innerHTML = `
    <div class="cabecalho"><div><h1>Gestão de contratos</h1><p>Contratos de ${esc(empresaAtual().razao_social)} · ${g.uso} de ${g.limite} contrato(s) do plano
      ${cheio && S.plano?.codigo !== "trial" ? ` · <a href="#/conta">contratar +10 por ${fmt.moeda(g.pacote.preco)}/mês</a>` : ""}</p></div>
      <button class="botao" id="novo-contrato" ${cheio ? "disabled title=\"Limite do plano atingido\"" : ""}>${icone("adicionar")} Novo contrato</button></div>
    ${guia(`<p>Envie o PDF do contrato: a IA lê vigência, garantia, reajuste, medição, faturamento e as obrigações periódicas da contratada,
      e o Kasiski monta a agenda de gestão com avisos antecipados (prorrogação 120 e 60 dias antes, garantia 30 dias antes, reajuste no aniversário).
      Você recebe um e-mail diário quando algum prazo está a 7 dias ou menos.</p>`)}
    <section class="bloco"><div class="bloco-titulo"><h2>Próximos prazos de gestão</h2><a class="botao pequeno secundario" href="#/agenda">Agenda completa</a></div>
      ${g.prazos.length ? `<div class="tabela-rolagem"><table><thead><tr><th>Data</th><th>O que fazer</th><th>Tipo</th><th></th></tr></thead>
        <tbody>${g.prazos.map(linhaPrazoGestao).join("")}</tbody></table></div>`
        : vazio("Nada nos próximos 45 dias", lista.length ? "Os prazos aparecem aqui conforme se aproximam." : "Cadastre um contrato para montar a agenda de gestão.")}</section>
    <section class="bloco"><h2>Contratos</h2>${lista.length ? lista.map(linhaContrato).join("") : vazio("Nenhum contrato cadastrado", "Envie o PDF de um contrato para começar.")}</section>`;
  const nv = $("#novo-contrato", el); if (nv) nv.onclick = () => modalNovoContrato();
  $$("[data-abrir-contrato]", el).forEach((a) => a.onclick = () => { location.hash = `#/contratos/${a.dataset.abrirContrato}`; });
  ligarConcluirPrazo(el, () => V.contratos(el));
};

function linhaPrazoGestao(p) {
  const n = fmt.dias(p.data);
  return `<tr><td style="white-space:nowrap">${fmt.data(p.data)}<br>${carimboPrazo(p.data)}</td>
    <td>${esc(p.titulo)}${p.fundamento ? `<br><small class="fraco">${esc(p.fundamento)}</small>` : ""}</td>
    <td>${carimboStatus(TIPO_PRAZO_CT, p.tipo)}</td>
    <td>${p.concluido ? carimbo("Feito", "ok") : `<button class="botao pequeno secundario" data-concluir="${p.id}">${icone("ok", 14)} Feito</button>`}</td></tr>`;
}

function ligarConcluirPrazo(el, depois) {
  $$("[data-concluir]", el).forEach((b) => b.onclick = async () => {
    try { await api("PATCH", `/api/agenda/${b.dataset.concluir}`, { concluido: true }); toast("Marcado como feito.", "ok"); depois(); } catch (e) { avisarErro(e); }
  });
}

function linhaContrato(c) {
  const lendo = c.leitura_status === "lendo";
  return `<div class="lista-item"><div class="corpo"><b>${esc(c.numero || "Contrato " + c.id)} — ${esc(c.orgao)}</b>
    <p>${esc((c.objeto || "").slice(0, 140))}</p><div class="meta"><span>${fmt.data(c.inicio)} a ${fmt.data(c.fim)}</span><span>${fmt.moeda(c.valor)}</span>
      ${c.fim ? `<span>${carimboPrazo(c.fim)}</span>` : ""}</div></div>
    <div class="acoes">${lendo ? carimbo("Lendo o PDF…", "aviso") : c.qtd_atrasados ? carimbo(`${c.qtd_atrasados} pagamento(s) em atraso`, "erro") : carimbo("Pagamentos em dia", "ok")}
      <button class="botao pequeno secundario" data-abrir-contrato="${c.id}">${icone("chevronDireita",14)} Abrir</button></div></div>`;
}

async function modalNovoContrato() {
  const editais = await api("GET", `/api/empresas/${S.empresaId}/editais`).catch(() => []);
  const m = modal({ titulo: "Novo contrato", corpo: `<form id="form-novo-ct">
    <div class="campo"><label for="ct-pdf">PDF do contrato</label><input id="ct-pdf" name="arquivo" type="file" accept=".pdf,.docx" required>
      <small>A IA lê o contrato e preenche vigência, valores, garantia, reajuste, medição, faturamento e as obrigações periódicas. Você confere depois.</small></div>
    <div class="campo"><label for="ct-edital">Edital de origem (opcional)</label><select id="ct-edital" name="edital_id"><option value="">—</option>
      ${editais.map((e) => `<option value="${e.id}">${esc((e.numero || e.objeto || "Edital " + e.id).slice(0, 70))}</option>`).join("")}</select></div>
    <div id="erro-novo-ct"></div><button class="botao" style="width:100%" type="submit">Enviar e ler o contrato</button>
    <p style="text-align:center;margin:12px 0 0"><button type="button" class="botao texto" id="ct-manual">Prefiro preencher à mão</button></p></form>` });
  $("#ct-manual", m).onclick = () => { m.fechar(); modalContrato(); };
  $("#form-novo-ct", m).onsubmit = async (ev) => {
    ev.preventDefault();
    await ocupado(ev.target.querySelector("button[type=submit]"), "Enviando…", async () => {
      try { const c = await api("POST", `/api/empresas/${S.empresaId}/contratos`, new FormData(ev.target)); m.fechar(); location.hash = `#/contratos/${c.id}`; }
      catch (e) { $("#erro-novo-ct", m).innerHTML = erroTela(e); }
    });
  };
}

function modalContrato(c) {
  const m = modal({
    titulo: c ? "Editar dados do contrato" : "Novo contrato (manual)", largo: true, corpo: `<form id="form-contrato">
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
  const d = c.dados_ia || {}, gar = d.garantia || {}, pag = d.pagamento || {}, med = d.medicao || {}, fat = d.faturamento || {};
  const lendo = c.leitura_status === "lendo";
  const abertos = c.prazos.filter((p) => !p.concluido), feitos = c.prazos.filter((p) => p.concluido);
  const item = (rot, v) => (v === undefined || v === null || v === "" || (Array.isArray(v) && !v.filter(Boolean).length) ? "" :
    `<div><dt>${esc(rot)}</dt><dd>${Array.isArray(v) ? v.filter(Boolean).map(esc).join("; ") : esc(v === true ? "Sim" : v === false ? "Não" : v)}</dd></div>`);
  el.innerHTML = `
    ${lendo ? `<div class="aviso info andamento-analise" role="status"><span class="girando" aria-hidden="true"></span><div><b>Lendo o contrato…</b> A IA está extraindo os dados e as rotinas de gestão.<br><small>Leva de 30 segundos a alguns minutos. Pode sair desta tela.</small></div></div>` : ""}
    ${c.leitura_status === "erro" ? `<div class="aviso erro">${esc(c.leitura_erro || "Não foi possível ler o contrato.")}</div>` : ""}
    ${c.leitura_status === "concluida" ? `<div class="aviso ok">Dados preenchidos a partir do PDF. Confira as datas e os valores: eles alimentam os avisos.</div>` : ""}
    <div class="capa"><div class="capa-topo"><div><div class="processo">${esc(c.numero || "Contrato " + c.id)}${d.processo ? ` · ${esc(d.processo)}` : ""}</div>
        <h1>${esc(c.objeto)}</h1></div>
        <div class="acoes">${c.tem_arquivo ? `<button class="botao secundario" id="baixar-ct">${icone("baixar", 15)} PDF</button>` : ""}
          <button class="botao secundario" id="reler-ct" ${lendo ? "disabled" : ""}>${c.tem_arquivo ? "Ler de novo" : "Enviar PDF"}</button>
          <button class="botao secundario" id="editar-contrato">${icone("editar",15)} Editar</button></div></div>
      <dl class="capa-campos">
        <div><dt>Órgão</dt><dd>${esc(c.orgao)}</dd></div><div><dt>Valor</dt><dd>${fmt.moeda(c.valor)}${d.valor_mensal ? `<br><small>${fmt.moeda(d.valor_mensal)}/mês</small>` : ""}</dd></div>
        <div><dt>Vigência</dt><dd>${fmt.data(c.inicio)} a ${fmt.data(c.fim)} ${c.fim ? carimboPrazo(c.fim) : ""}</dd></div>
        <div><dt>Garantia até</dt><dd>${fmt.data(c.garantia_validade)}</dd></div>
        <div><dt>Data-base do reajuste</dt><dd>${fmt.data(c.data_base_reajuste)}</dd></div>
        <div><dt>Índice</dt><dd>${esc(c.indice_reajuste || "—")}</dd></div></dl></div>
    ${Object.keys(d).length ? `<section class="bloco"><details open><summary><b>Condições de gestão lidas do contrato</b></summary>
      <dl class="capa-campos" style="margin-top:12px">
        ${item("Serviço contínuo", d.servico_continuo)}${item("Prorrogação", d.regras_prorrogacao || d.prorrogavel)}${item("Regime de execução", d.regime_execucao)}
        ${item("Garantia", [gar.modalidade, gar.percentual ? gar.percentual + "%" : "", gar.valor ? fmt.moeda(gar.valor) : "", gar.prazo_apresentacao].filter(Boolean).join(" · "))}
        ${item("Pagamento", [pag.prazo_dias ? `${pag.prazo_dias} dias` : "", pag.condicoes].filter(Boolean).join(" · "))}${item("Documentos para pagamento", pag.documentos_para_pagamento)}
        ${item("Medição", [med.periodicidade, med.dia_ou_prazo, med.prazo_ateste_dias ? `ateste em ${med.prazo_ateste_dias} dias` : "", med.como].filter(Boolean).join(" · "))}
        ${item("Faturamento", [fat.periodicidade, fat.prazo].filter(Boolean).join(" · "))}${item("Documentos do faturamento", fat.documentos)}
        ${item("Fiscal", d.fiscal)}${item("Gestor", d.gestor)}${item("Repactuação", d.repactuacao)}${item("Penalidades", d.penalidades)}${item("Pontos de atenção", d.pontos_de_atencao)}
      </dl></details></section>` : ""}
    <section class="bloco"><div class="bloco-titulo"><h2>Agenda de gestão</h2><span class="fraco">${abertos.length} em aberto</span></div>
      ${abertos.length ? `<div class="tabela-rolagem"><table><thead><tr><th>Data</th><th>O que fazer</th><th>Tipo</th><th></th></tr></thead>
        <tbody>${abertos.slice(0, 30).map(linhaPrazoGestao).join("")}</tbody></table></div>` : vazio("Nenhum prazo em aberto", "Informe vigência, garantia e data-base, ou cadastre rotinas abaixo.")}
      ${feitos.length ? `<details style="margin-top:10px"><summary>${feitos.length} concluído(s)</summary>${feitos.map((p) => `<p class="fraco">${fmt.data(p.data)} · ${esc(p.titulo)}</p>`).join("")}</details>` : ""}</section>
    <section class="bloco"><div class="bloco-titulo"><h2>Rotinas de gestão</h2><button class="botao pequeno secundario" id="add-rotina">${icone("adicionar", 14)} Adicionar rotina</button></div>
      <p class="fraco">Medição, nota fiscal, comprovação de encargos, relatórios… As próximas 3 ocorrências de cada rotina ficam na agenda e se renovam sozinhas.</p>
      <div class="tabela-rolagem"><table class="tabela-itens"><thead><tr><th>Rotina</th><th>Periodicidade</th><th>Dia do mês</th><th>Prazo / fundamento</th><th>Ativa</th><th></th></tr></thead>
        <tbody id="rotinas">${(c.obrigacoes || []).map(linhaRotina).join("") || `<tr><td colspan="6">${vazio("Nenhuma rotina", "Adicione as rotinas que o contrato exige.")}</td></tr>`}</tbody></table></div>
      <div class="acoes" style="margin-top:10px"><button class="botao" id="salvar-rotinas">Salvar rotinas e atualizar a agenda</button></div></section>
    <section class="bloco"><div class="bloco-titulo"><h2>Pagamentos e faturamento</h2><button class="botao pequeno" id="novo-pagamento">${icone("adicionar", 15)} Lançar nota/medição</button></div>
      ${c.pagamentos.length ? `<div class="tabela-rolagem"><table><thead><tr><th>Referência</th><th>NF</th><th>Valor</th><th>Vencimento</th><th>Situação</th><th></th></tr></thead>
      <tbody>${c.pagamentos.map(linhaPagamento).join("")}</tbody></table></div>` : vazio("Nenhum pagamento lançado", "Lance cada nota fiscal ou medição para acompanhar os atrasos.")}</section>
    <section class="bloco"><div class="bloco-titulo"><h2>Peças deste contrato</h2>
      <a class="botao pequeno secundario" href="#/pecas">Gerar peça</a></div>
      ${c.pecas.length ? c.pecas.map((p) => `<div class="lista-item"><div class="corpo"><b>${esc(p.titulo)}</b><p>${fmt.dataHora(p.criado_em)}</p></div>
        <a class="botao pequeno secundario" href="#/pecas/${p.id}">${icone("chevronDireita",14)} Abrir</a></div>`).join("") : vazio("Nenhuma peça ainda", "")}</section>`;
  $("#editar-contrato", el).onclick = () => modalContrato(c);
  $("#novo-pagamento", el).onclick = () => modalPagamento(c.id);
  const bx = $("#baixar-ct", el); if (bx) bx.onclick = () => baixar(`/api/contratos/${id}/arquivo`, c.nome_arquivo || "contrato.pdf");
  $("#reler-ct", el).onclick = () => {
    if (c.tem_arquivo) { api("POST", `/api/contratos/${id}/arquivo`).then(() => V.contrato(el, id)).catch(avisarErro); return; }
    const inp = document.createElement("input"); inp.type = "file"; inp.accept = ".pdf,.docx";
    inp.onchange = async () => { const fd = new FormData(); fd.append("arquivo", inp.files[0]); try { await api("POST", `/api/contratos/${id}/arquivo`, fd); V.contrato(el, id); } catch (e) { avisarErro(e); } };
    inp.click();
  };
  const coletar = () => $$("#rotinas tr[data-rotina]", el).map((tr) => ({
    descricao: $("[name=descricao]", tr).value, periodicidade: $("[name=periodicidade]", tr).value, dia_do_mes: $("[name=dia]", tr).value,
    prazo: "", fundamento: $("[name=fundamento]", tr).value, pagina: tr.dataset.pagina || "", ativa: $("[name=ativa]", tr).checked }));
  $("#add-rotina", el).onclick = () => {
    const tb = $("#rotinas", el); if (!tb.querySelector("tr[data-rotina]")) tb.innerHTML = "";
    tb.insertAdjacentHTML("beforeend", linhaRotina({ descricao: "", periodicidade: "mensal", dia_do_mes: 10, ativa: true }));
    ligarRemoverRotina(); tb.querySelector("tr:last-child [name=descricao]").focus();
  };
  const ligarRemoverRotina = () => $$("[data-remover-rotina]", el).forEach((b) => b.onclick = () => b.closest("tr").remove());
  ligarRemoverRotina();
  $("#salvar-rotinas", el).onclick = (ev) => ocupado(ev.target, "Salvando…", async () => {
    try { await api("PATCH", `/api/contratos/${id}/obrigacoes`, { obrigacoes: coletar() }); toast("Rotinas salvas e agenda atualizada.", "ok"); V.contrato(el, id); } catch (e) { avisarErro(e); }
  });
  ligarConcluirPrazo(el, () => V.contrato(el, id));
  $$("[data-pago]", el).forEach((b) => b.onclick = async () => { await api("PATCH", `/api/pagamentos/${b.dataset.pago}`, { pago_em: new Date().toISOString().slice(0, 10) }); V.contrato(el, id); });
  $$("[data-excluir-pgto]", el).forEach((b) => b.onclick = async () => { if (await confirmar("Excluir este pagamento?", "Excluir")) { await api("DELETE", `/api/pagamentos/${b.dataset.excluirPgto}`); V.contrato(el, id); } });
  if (lendo) setTimeout(async () => { if (location.hash === `#/contratos/${id}`) V.contrato(el, id); }, 5000);
};

function linhaRotina(o) {
  const per = ["mensal", "bimestral", "trimestral", "semestral", "anual", "unica"];
  const nomes = { mensal: "Mensal", bimestral: "Bimestral", trimestral: "Trimestral", semestral: "Semestral", anual: "Anual", unica: "Uma vez" };
  return `<tr data-rotina data-prazo="${esc(o.prazo || "")}" data-pagina="${esc(o.pagina || "")}">
    <td><textarea class="celula" rows="2" name="descricao" aria-label="Rotina">${esc(o.descricao || "")}</textarea></td>
    <td><select class="celula" name="periodicidade" aria-label="Periodicidade">${per.map((p) => `<option value="${p}" ${o.periodicidade === p ? "selected" : ""}>${nomes[p]}</option>`).join("")}</select></td>
    <td><input class="celula curta" name="dia" inputmode="numeric" value="${o.dia_do_mes ?? ""}" aria-label="Dia do mês"></td>
    <td><input class="celula" name="fundamento" value="${esc([o.prazo, o.fundamento].filter(Boolean).join(" · "))}" aria-label="Prazo e fundamento"></td>
    <td><input type="checkbox" name="ativa" ${o.ativa !== false ? "checked" : ""} aria-label="Ativa"></td>
    <td><button class="botao texto pequeno" data-remover-rotina aria-label="Remover rotina">${icone("excluir", 14)}</button></td></tr>`;
}

function linhaPagamento(p) {
  const sit = { pago: ["Pago", "ok"], atrasado: ["Atrasado" + (p.dias_atraso ? ` (${p.dias_atraso}d)` : ""), "erro"], a_receber: ["A receber", "neutro"] }[p.situacao];
  return `<tr><td>${esc(p.referencia || "—")}</td><td>${esc(p.nota_fiscal || "—")}</td><td>${fmt.moeda(p.valor)}</td><td>${fmt.data(p.vencimento)}</td>
    <td>${carimbo(sit[0], sit[1])}</td><td>${p.situacao !== "pago" ? `<button class="botao texto pequeno" data-pago="${p.id}">${icone("ok",14)} Marcar pago</button>` : ""}
    <button class="botao texto pequeno" data-excluir-pgto="${p.id}">${icone("excluir",14)} Excluir</button></td></tr>`;
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
