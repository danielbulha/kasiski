// Gerador de peças e acompanhamento das revisões profissionais pagas.
V.pecas = async (el) => {
  if (!S.empresaId) { el.innerHTML = exigirEmpresa(); return; }
  const [lista, tipos] = await Promise.all([api("GET", `/api/empresas/${S.empresaId}/pecas`), api("GET", "/api/pecas/tipos")]);
  const pre = sessionStorage.getItem("nova_peca");
  el.innerHTML = `
    <div class="cabecalho"><div><h1>Gerador de peças</h1><p>Minutas de ${esc(empresaAtual().razao_social)}, prontas para revisão.</p></div>
      <button class="botao" id="nova">Nova peça</button></div>
    ${guia(`<p>Escolha o tipo de peça e o edital ou contrato de referência. Se você veio da análise de um edital ou de um concorrente,
      os pontos selecionados já entram como base. A IA redige uma minuta com fundamentação legal; revise antes de protocolar, ou peça
      a revisão profissional paga pela D.B.C. Consultoria.</p>`)}
    <section class="bloco">${lista.length ? lista.map((p) => `<div class="lista-item"><div class="corpo"><b>${esc(p.titulo)}</b>
        <p>${fmt.dataHora(p.criado_em)}</p></div><div class="acoes">${carimbo(p.status === "revisada" ? "Revisada" : p.status === "revisao_solicitada" ? "Em revisão" : "Rascunho",
          p.status === "revisada" ? "ok" : p.status === "revisao_solicitada" ? "aviso" : "neutro")}
        <a class="botao pequeno secundario" href="#/pecas/${p.id}">Abrir</a></div></div>`).join("")
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
          ${tipos.map((t) => `<option value="${t.codigo}" ${pre ? "" : ""}>${esc(t.nome)}${t.preco_revisao ? ` · revisão a partir de ${fmt.moeda(t.preco_revisao)}` : ""}</option>`).join("")}</select></div>
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
  const p = await api("GET", `/api/pecas/${id}`);
  const revisaoAtiva = p.revisoes.find((r) => ["pendente", "em_andamento"].includes(r.status));
  el.innerHTML = `
    <div class="cabecalho"><div><h1>${esc(p.titulo)}</h1><p>${fmt.dataHora(p.criado_em)}</p></div>
      <div class="acoes">${carimbo(p.status === "revisada" ? "Revisada" : p.status === "revisao_solicitada" ? "Em revisão" : "Rascunho",
        p.status === "revisada" ? "ok" : p.status === "revisao_solicitada" ? "aviso" : "neutro")}
      <button class="botao secundario" id="baixar-peca">Baixar .txt</button>
      ${!revisaoAtiva ? `<button class="botao" id="pedir-revisao">Pedir revisão profissional</button>` : ""}</div></div>
    ${p.demonstracao ? `<div class="aviso info">Minuta de demonstração — configure as chaves de IA para gerar o texto completo.</div>` : ""}
    <div class="bloco"><textarea class="editor" id="conteudo-peca">${esc(p.conteudo)}</textarea>
      <div class="acoes" style="margin-top:10px"><button class="botao" id="salvar-peca">Salvar alterações</button></div></div>
    ${revisaoAtiva ? `<div class="bloco"><h3>Revisão profissional</h3><p>${carimbo(revisaoAtiva.status === "pendente" ? "Aguardando início" : "Em andamento", "aviso")}
      ${revisaoAtiva.valor ? ` · ${fmt.moeda(revisaoAtiva.valor)}` : ""}</p>${revisaoAtiva.observacoes ? `<p class="fraco">${esc(revisaoAtiva.observacoes)}</p>` : ""}</div>` : ""}
    ${p.revisoes.find((r) => r.status === "concluida" && r.parecer) ? `<div class="bloco"><h3>Parecer do revisor</h3>
      <p>${esc(p.revisoes.find((r) => r.status === "concluida").parecer)}</p></div>` : ""}`;
  $("#baixar-peca", el).onclick = () => { const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([p.conteudo], { type: "text/plain" })); a.download = p.titulo + ".txt"; a.click(); };
  $("#salvar-peca", el).onclick = (ev) => ocupado(ev.target, "Salvando…", async () => {
    await api("PATCH", `/api/pecas/${id}`, { conteudo: $("#conteudo-peca", el).value }); toast("Peça salva.", "ok");
  });
  const pr = $("#pedir-revisao", el);
  if (pr) pr.onclick = () => modalRevisao(p);
};

function modalRevisao(p) {
  const preco = { esclarecimento: 290, impugnacao: 690, intencao_recurso: 190, recurso: 990, contrarrazoes: 890,
    reequilibrio: 1490, cobranca_pagamento: 490, defesa_previa: 1190 }[p.tipo];
  const m = modal({
    titulo: "Pedir revisão profissional", corpo: `<p>Um advogado da D.B.C. Consultoria revisa a minuta antes do protocolo.
      Valor de referência: <b>${fmt.moeda(preco)}</b>${p.demonstracao ? "" : ""}. Você será contatado para confirmar prazo e pagamento.</p>
      <form id="form-revisao">
      <div class="campo"><label for="prazo_rev">Prazo desejado</label><input id="prazo_rev" name="prazo_desejado" type="date"></div>
      <div class="campo"><label for="obs_rev">O que o revisor deve saber</label><textarea id="obs_rev" name="observacoes"></textarea></div>
      <div id="erro-revisao"></div><button class="botao" style="width:100%" type="submit">Solicitar revisão</button></form>`,
  });
  $("#form-revisao", m).onsubmit = async (ev) => {
    ev.preventDefault();
    try { await api("POST", `/api/pecas/${p.id}/revisao`, dadosForm(ev.target)); m.fechar(); toast("Revisão solicitada. Você será contatado em breve.", "ok"); location.hash = `#/pecas/${p.id}`; }
    catch (e) { $("#erro-revisao", m).innerHTML = erroTela(e); }
  };
}
