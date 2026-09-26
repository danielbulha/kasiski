// Gerador de peças (minutas pela IA) e serviço de advogado (elaboração ou revisão, pago pelo Mercado Pago).
const STATUS_PECA = { revisada: ["Revisada", "ok"], revisao_solicitada: ["Com advogado", "aviso"], com_advogado: ["Com advogado", "aviso"], rascunho: ["Rascunho", "neutro"] };
const STATUS_PEDIDO = { aguardando_pagamento: ["Aguardando pagamento", "aviso"], pendente: ["Pago · na fila", "oficio"],
  em_andamento: ["Em elaboração", "aviso"], concluida: ["Concluído", "ok"], cancelada: ["Cancelado", "neutro"] };
V.pecas = async (el) => {
  if (!S.empresaId) { el.innerHTML = exigirEmpresa(); return; }
  const [lista, tipos] = await Promise.all([api("GET", `/api/empresas/${S.empresaId}/pecas`), api("GET", "/api/pecas/tipos")]);
  const pre = sessionStorage.getItem("nova_peca");
  el.innerHTML = `
    <div class="cabecalho"><div><h1>Gerador de peças</h1><p>Minutas de ${esc(empresaAtual().razao_social)}, prontas para revisão.</p></div>
      <div class="acoes"><a class="botao secundario" href="#/pecas/advogado">Elaboração com advogado</a>
      <button class="botao" id="nova">${icone("adicionar")} Nova peça</button></div></div>
    ${guia(`<p>Escolha o tipo de peça e o edital ou contrato de referência. Se você veio da análise de um edital ou de um concorrente,
      os pontos selecionados já entram como base. A IA redige uma minuta com fundamentação legal; revise antes de protocolar.
      Se preferir, use <a href="#/pecas/advogado">Elaboração com advogado</a> para contratar a peça feita ou revisada por um advogado.</p>`)}
    <section class="bloco">${lista.length ? lista.map((p) => `<div class="lista-item"><div class="corpo"><b>${esc(p.titulo)}</b>
        <p>${fmt.dataHora(p.criado_em)}</p></div><div class="acoes">${carimboStatus(STATUS_PECA, p.status)}
        <a class="botao pequeno secundario" href="#/pecas/${p.id}">${icone("chevronDireita",14)} Abrir</a></div></div>`).join("")
      : vazio("Nenhuma peça gerada ainda", "Clique em Nova peça para redigir a primeira minuta.")}</section>`;
  $("#nova", el).onclick = () => modalNovaPeca(tipos, pre ? JSON.parse(pre) : null);
  if (pre) sessionStorage.removeItem("nova_peca");
};

async function modalNovaPeca(tipos, pre) {
  const editais = await api("GET", `/api/empresas/${S.empresaId}/editais`);
  const contratos = await api("GET", `/api/empresas/${S.empresaId}/contratos`);
  const m = modal({
    titulo: "Nova peça", largo: true, corpo: `<form id="form-peca">
      <div class="linha-campos">
        <div class="campo"><label for="tipo_peca">Tipo de peça</label><select id="tipo_peca" name="tipo">
          ${tipos.map((t) => `<option value="${t.codigo}">${esc(t.nome)}</option>`).join("")}</select></div>
        <div class="campo"><label for="ref_peca">Referência</label><select id="ref_peca" name="ref">
          <option value="">Nenhuma (peça avulsa)</option>
          <optgroup label="Editais">${editais.map((e) => `<option value="edital:${e.id}" ${pre?.edital_id == e.id ? "selected" : ""}>${esc((e.numero || e.objeto || "Edital " + e.id).slice(0, 60))}</option>`).join("")}</optgroup>
          <optgroup label="Contratos">${contratos.map((c) => `<option value="contrato:${c.id}">${esc(c.numero || "Contrato " + c.id)}</option>`).join("")}</optgroup>
        </select></div>
      </div>
      ${pre ? `<p class="fraco">${(pre.itens || []).length} ponto(s) já selecionado(s) da análise anterior.</p>` : ""}
      <div class="campo"><label for="instrucoes_peca">Instruções (opcional)</label><textarea id="instrucoes_peca" name="instrucoes" placeholder="Explique o que a peça deve sustentar, caso não venha de uma análise."></textarea></div>
      <div id="erro-peca"></div><button class="botao" style="width:100%" type="submit">Gerar minuta</button></form>`,
  });
  $("#form-peca", m).onsubmit = async (ev) => {
    ev.preventDefault();
    const b = ev.target.querySelector("button");
    const refVal = $("#ref_peca", m).value;
    const corpo = { tipo: $("#tipo_peca", m).value, instrucoes: $("#instrucoes_peca", m).value };
    if (refVal.startsWith("edital:")) corpo.edital_id = Number(refVal.split(":")[1]);
    if (refVal.startsWith("contrato:")) corpo.contrato_id = Number(refVal.split(":")[1]);
    if (pre) Object.assign(corpo, { analise_id: pre.analise_id, analise_concorrente_id: pre.analise_concorrente_id, itens: pre.itens });
    await ocupado(b, "Redigindo a minuta…", async () => {
      try { const p = await api("POST", `/api/empresas/${S.empresaId}/pecas`, corpo); await atualizarConta(); m.fechar(); location.hash = `#/pecas/${p.id}`; }
      catch (e) { $("#erro-peca", m).innerHTML = erroTela(e); }
    });
  };
}

V.peca = async (el, id) => {
  const [p, tipos] = await Promise.all([api("GET", `/api/pecas/${id}`), api("GET", "/api/pecas/tipos")]);
  const ativo = p.revisoes.find((r) => ["aguardando_pagamento", "pendente", "em_andamento"].includes(r.status));
  const emElaboracao = !(p.conteudo || "").trim() && (p.status === "com_advogado" || ativo?.servico === "elaboracao");
  const concluida = p.revisoes.find((r) => r.status === "concluida" && r.parecer);
  el.innerHTML = `
    <div class="cabecalho"><div><p class="fraco" style="margin:0"><a href="#/pecas">← Peças</a></p><h1>${esc(p.titulo)}</h1><p>${fmt.dataHora(p.criado_em)}</p></div>
      <div class="acoes">${carimboStatus(STATUS_PECA, p.status)}
      ${!emElaboracao ? `<button class="botao secundario" id="baixar-peca">${icone("baixar")} Baixar .txt</button>` : ""}
      ${!ativo && !emElaboracao ? `<button class="botao" id="pedir-revisao">Revisão por advogado</button>` : ""}</div></div>
    ${p.demonstracao ? `<div class="aviso info">Minuta de demonstração — configure as chaves de IA para gerar o texto completo.</div>` : ""}
    ${ativo ? `<div class="aviso ${ativo.status === "aguardando_pagamento" ? "" : "info"}" style="${ativo.status === "aguardando_pagamento" ? "background:var(--ambar-claro);color:var(--ambar)" : ""}">
      <b>${ativo.servico === "elaboracao" ? "Elaboração" : "Revisão"} por advogado:</b> ${carimboStatus(STATUS_PEDIDO, ativo.status)}
      ${ativo.valor ? ` · ${fmt.moeda(ativo.valor)}` : ""}${ativo.prazo_desejado ? ` · prazo desejado ${fmt.data(ativo.prazo_desejado)}` : ""}
      ${ativo.status === "aguardando_pagamento" ? ` · <a href="#/pecas/advogado">Concluir o pagamento</a>` : ""}</div>` : ""}
    ${emElaboracao ? `<div class="bloco">${vazio("O advogado está elaborando esta peça", "Quando ficar pronta, o texto aparece aqui e você recebe o parecer. Acompanhe em Elaboração com advogado.", `<a class="botao secundario" href="#/pecas/advogado">Ver meus pedidos</a>`)}</div>`
      : `<div class="bloco"><textarea class="editor" id="conteudo-peca">${esc(p.conteudo)}</textarea>
      <div class="acoes" style="margin-top:10px"><button class="botao" id="salvar-peca">Salvar alterações</button></div></div>`}
    ${concluida ? `<div class="bloco"><h3>Parecer do advogado</h3><p>${esc(concluida.parecer)}</p></div>` : ""}`;
  const bx = $("#baixar-peca", el);
  if (bx) bx.onclick = () => { const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([$("#conteudo-peca", el).value], { type: "text/plain" })); a.download = p.titulo + ".txt"; a.click(); };
  const sv = $("#salvar-peca", el);
  if (sv) sv.onclick = (ev) => ocupado(ev.target, "Salvando…", async () => {
    await api("PATCH", `/api/pecas/${id}`, { conteudo: $("#conteudo-peca", el).value }); toast("Peça salva.", "ok");
  });
  const pr = $("#pedir-revisao", el);
  if (pr) pr.onclick = () => modalRevisao(p, tipos.find((t) => t.codigo === p.tipo));
};

function modalRevisao(p, tipo) {
  const m = modal({
    titulo: "Revisão por advogado", corpo: `<p>Um advogado revisa esta minuta, ajusta a fundamentação e devolve o texto pronto para protocolo, com parecer.</p>
      <p class="preco-checkout">${fmt.moeda(tipo?.preco_advogado)}<small>pagamento único · Pix, boleto ou cartão em até 3x</small></p>
      <form id="form-revisao">
      <div class="campo"><label for="prazo_rev">Prazo desejado</label><input id="prazo_rev" name="prazo_desejado" type="date"></div>
      <div class="campo"><label for="obs_rev">O que o advogado deve saber</label><textarea id="obs_rev" name="observacoes" placeholder="Ex.: prazo final de protocolo, pontos que mais preocupam"></textarea></div>
      <div id="erro-revisao"></div><button class="botao" style="width:100%" type="submit">Ir para o pagamento</button></form>`,
  });
  $("#form-revisao", m).onsubmit = async (ev) => {
    ev.preventDefault();
    await ocupado(ev.target.querySelector("button"), "Abrindo o Mercado Pago…", async () => {
      try {
        const r = await api("POST", `/api/pecas/${p.id}/revisao`, dadosForm(ev.target));
        if (r.url_pagamento) { location.href = r.url_pagamento; return; }
        m.fechar(); toast("Pedido registrado. Entraremos em contato para combinar o pagamento.", "ok"); V.peca($("#conteudo"), p.id);
      } catch (e) { $("#erro-revisao", m).innerHTML = erroTela(e); }
    });
  };
}

// ---------------------------------------------------------------- elaboração com advogado
V.advogado = async (el) => {
  if (!S.empresaId) { el.innerHTML = exigirEmpresa(); return; }
  let retorno = null;
  try { retorno = JSON.parse(sessionStorage.getItem("kasiski_retorno_advogado") || "null"); sessionStorage.removeItem("kasiski_retorno_advogado"); } catch { /* segue */ }
  if (retorno?.payment_id) { try { await api("POST", "/api/billing/sincronizar", retorno); } catch { /* o webhook resolve */ } }
  const [tipos, pedidos] = await Promise.all([api("GET", "/api/pecas/tipos"), api("GET", "/api/revisoes")]);
  const msg = !retorno ? "" : ["approved"].includes(retorno.status)
    ? `<div class="aviso ok">Pagamento confirmado. Seu pedido entrou na fila do advogado; você acompanha o andamento abaixo.</div>`
    : ["rejected", "failure", "null"].includes(retorno.status)
      ? `<div class="aviso erro">O pagamento não foi concluído. Você pode tentar de novo em "Meus pedidos".</div>`
      : `<div class="aviso info">Recebemos seu pedido. Assim que o Mercado Pago confirmar o pagamento (Pix: segundos; boleto: até 2 dias úteis), ele entra na fila.</div>`;
  el.innerHTML = `
    <div class="cabecalho"><div><p class="fraco" style="margin:0"><a href="#/pecas">← Peças</a></p><h1>Elaboração com advogado</h1>
      <p>A peça feita por advogado especialista em licitações, com base no seu caso, no edital e nos documentos do processo.</p></div></div>
    ${msg}
    <section class="bloco"><h2>Como funciona</h2>
      <div class="grade grade-3">
        <div class="indicador"><b style="font-size:1.1rem">1. Escolha a peça</b><span>e descreva o caso: o que aconteceu e o que você quer pedir.</span></div>
        <div class="indicador"><b style="font-size:1.1rem">2. Pague online</b><span>Pix, boleto ou cartão em até 3x, pelo Mercado Pago.</span></div>
        <div class="indicador"><b style="font-size:1.1rem">3. Receba aqui</b><span>a peça pronta para protocolo e o parecer do advogado.</span></div>
      </div>
      <p class="fraco" style="margin:14px 0 0">Já tem uma minuta gerada pela IA? Abra a peça e use <b>Revisão por advogado</b>, pelo mesmo valor.</p></section>
    <div class="grade-servicos">${tipos.map((t) => `<div class="servico">
      <h3>${esc(t.nome)}</h3><p>${esc(t.descricao)}</p>
      <div class="servico-rodape"><span class="servico-preco">${t.preco_advogado ? fmt.moeda(t.preco_advogado) : "Sob consulta"}</span>
        <button class="botao pequeno" data-contratar="${t.codigo}">Contratar</button></div></div>`).join("")}</div>
    <section class="bloco" style="margin-top:18px"><h2>Meus pedidos</h2>
      ${pedidos.length ? `<div class="tabela-rolagem"><table><thead><tr><th>Pedido</th><th>Serviço</th><th>Valor</th><th>Situação</th><th>Data</th><th></th></tr></thead>
        <tbody>${pedidos.map((r) => `<tr><td><a href="#/pecas/${r.peca_id}">${esc(r.peca_titulo || "Peça")}</a></td>
          <td>${r.servico === "elaboracao" ? "Elaboração" : "Revisão"}</td><td>${fmt.moeda(r.valor)}</td><td>${carimboStatus(STATUS_PEDIDO, r.status)}</td>
          <td>${fmt.data(r.criado_em)}</td>
          <td class="acoes-celula">${r.status === "aguardando_pagamento" ? `<button class="botao pequeno" data-pagar="${r.id}">Pagar</button>
            <button class="botao texto pequeno" data-cancelar="${r.id}">Cancelar</button>` : ""}</td></tr>`).join("")}</tbody></table></div>`
        : vazio("Nenhum pedido ainda", "Escolha acima a peça que o advogado deve elaborar.")}</section>`;
  $$("[data-contratar]", el).forEach((b) => b.onclick = () => modalContratar(tipos.find((t) => t.codigo === b.dataset.contratar)));
  $$("[data-pagar]", el).forEach((b) => b.onclick = () => ocupado(b, "Abrindo…", async () => {
    try { location.href = (await api("POST", `/api/revisoes/${b.dataset.pagar}/pagar`)).url_pagamento; } catch (e) { avisarErro(e); }
  }));
  $$("[data-cancelar]", el).forEach((b) => b.onclick = async () => {
    if (!(await confirmar("Cancelar este pedido ainda não pago?", "Cancelar pedido"))) return;
    try { await api("DELETE", `/api/revisoes/${b.dataset.cancelar}`); toast("Pedido cancelado.", "ok"); V.advogado(el); } catch (e) { avisarErro(e); }
  });
};

async function modalContratar(t) {
  const [editais, contratos] = await Promise.all([api("GET", `/api/empresas/${S.empresaId}/editais`), api("GET", `/api/empresas/${S.empresaId}/contratos`)]);
  const m = modal({ titulo: `${t.nome} · com advogado`, largo: true, corpo: `
    <p class="preco-checkout">${t.preco_advogado ? fmt.moeda(t.preco_advogado) : "Sob consulta"}<small>pagamento único · Pix, boleto ou cartão em até 3x</small></p>
    <form id="form-contratar">
      <div class="linha-campos">
        <div class="campo"><label for="ct-ref">Edital ou contrato</label><select id="ct-ref" name="ref">
          <option value="">Nenhum (vou descrever abaixo)</option>
          <optgroup label="Editais">${editais.map((e) => `<option value="edital:${e.id}">${esc((e.numero || e.objeto || "Edital " + e.id).slice(0, 70))}</option>`).join("")}</optgroup>
          <optgroup label="Contratos">${contratos.map((c) => `<option value="contrato:${c.id}">${esc(c.numero || "Contrato " + c.id)}</option>`).join("")}</optgroup></select>
          <small>O advogado consulta o edital, a análise e os documentos já cadastrados.</small></div>
        <div class="campo"><label for="ct-prazo">Prazo final para protocolo</label><input id="ct-prazo" name="prazo_desejado" type="date"></div>
      </div>
      <div class="campo"><label for="ct-obs">Descreva o caso *</label><textarea id="ct-obs" name="observacoes" rows="6" required
        placeholder="O que aconteceu, qual decisão ou cláusula você quer contestar, e o que a peça deve pedir. Inclua datas importantes."></textarea></div>
      <div id="erro-contratar"></div>
      <button class="botao" style="width:100%" type="submit">Ir para o pagamento</button>
      <p class="fraco" style="margin:10px 0 0;text-align:center">Você será levado ao ambiente seguro do Mercado Pago. O pedido entra na fila assim que o pagamento for confirmado.</p>
    </form>` });
  $("#form-contratar", m).onsubmit = async (ev) => {
    ev.preventDefault();
    const d = dadosForm(ev.target), ref = d.ref || "";
    const corpo = { tipo: t.codigo, prazo_desejado: d.prazo_desejado, observacoes: d.observacoes };
    if (ref.startsWith("edital:")) corpo.edital_id = Number(ref.split(":")[1]);
    if (ref.startsWith("contrato:")) corpo.contrato_id = Number(ref.split(":")[1]);
    await ocupado(ev.target.querySelector("button"), "Abrindo o Mercado Pago…", async () => {
      try {
        const r = await api("POST", `/api/empresas/${S.empresaId}/advogado`, corpo);
        if (r.url_pagamento) { location.href = r.url_pagamento; return; }
        m.fechar(); toast("Pedido registrado. Entraremos em contato para combinar o pagamento.", "ok"); V.advogado($("#conteudo"));
      } catch (e) { $("#erro-contratar", m).innerHTML = erroTela(e); }
    });
  };
}
