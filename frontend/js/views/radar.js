// Radar: editais recebendo proposta no PNCP que combinam com o perfil da empresa.
V.radar = async (el) => {
  if (!S.empresaId) { el.innerHTML = exigirEmpresa(); return; }
  const filtro = sessionStorage.getItem("radar_filtro") || "novo";
  const resp = await api("GET", `/api/empresas/${S.empresaId}/radar?status=${filtro}&meta=1`);
  const itens = resp.itens, cota = resp.cota || {};
  const semBusca = cota.limitado && !cota.pode_buscar;
  const emp = empresaAtual();
  el.innerHTML = `
    <div class="cabecalho"><div><h1>Radar de editais</h1>
      <p>Buscando por: ${emp.termos_radar?.length ? esc(emp.termos_radar.join(", ")) : "nenhum segmento ou palavra-chave"} ${emp.ufs ? "· " + esc(emp.ufs) : "· todo o Brasil"} · ${emp.radar_diarios ? "PNCP e diários oficiais" : "PNCP"}
        · <a href="#/empresas">ajustar</a></p></div>
      <div class="acoes"><select id="filtro" aria-label="Filtrar">
        <option value="novo" ${filtro === "novo" ? "selected" : ""}>Novos</option>
        <option value="acompanhando" ${filtro === "acompanhando" ? "selected" : ""}>Já acompanhados</option>
        <option value="descartado" ${filtro === "descartado" ? "selected" : ""}>Excluídos</option></select>
        <button class="botao" id="atualizar" ${semBusca ? "disabled" : ""} title="${semBusca ? "No Free, 1 busca por dia" : ""}">${icone("radarPing")} ${semBusca ? "Próxima busca amanhã" : "Buscar agora"}</button></div></div>
    ${guia(`<p>${cota.limitado ? `No plano Free, você faz <b>1 busca por dia</b> clicando em <b>Buscar agora</b>, e o Kasiski traz os <b>${cota.maximo} editais mais aderentes</b> com propostas abertas no PNCP.`
      : "Todo dia útil, cedo, o Kasiski consulta o PNCP e traz os editais com propostas abertas que combinam com os segmentos e as palavras-chave da empresa."}
      O sistema de inteligência artificial do Kasiski dá uma nota de 0 a 100 de aderência ao seu perfil. Clique em <b>Acompanhar</b> para baixar o edital,
      calcular os prazos e liberar a análise completa. Os segmentos, as palavras-chave e os estados ficam em <a href="#/empresas">Minha empresa</a>.</p>`)}
    ${cota.limitado ? `<div class="aviso info">${cota.buscas_hoje ? `Busca de hoje feita: aqui estão os editais mais aderentes (até ${cota.maximo}). Excluir um edital não traz outro no lugar; a próxima busca fica liberada amanhã.`
      : `Você tem <b>1 busca disponível hoje</b>: clique em <b>Buscar agora</b> para receber os ${cota.maximo} editais mais aderentes.`}
      No <b>Essencial</b> (R$ 97/mês), o radar busca sozinho todos os dias e mostra todos os editais. <a href="#/conta">Ver planos</a></div>` : ""}
    ${filtro === "novo" && itens.length ? barraLimpezaRadar(itens) : ""}
    <section class="bloco lista-faixas">
      ${itens.length ? legendaFaixas({ alta: "Aderência alta (80+)", media: "Média (50 a 79)", baixa: "Baixa (até 49)" }, "faixa-") + itens.map(linhaRadar).join("") : vazio(filtro === "novo" ? "Nenhum edital novo" : "Nada por aqui",
        filtro === "novo" ? "Clique em Buscar agora ou ajuste as palavras-chave da empresa para ampliar a busca." : "")}
    </section>`;
  $("#filtro", el).onchange = (ev) => { sessionStorage.setItem("radar_filtro", ev.target.value); V.radar(el); };
  $("#atualizar", el).onclick = (ev) => ocupado(ev.target, empresaAtual()?.radar_diarios ? "Buscando no PNCP e nos diários…" : "Buscando no PNCP…", async () => {
    try { const r = await api("POST", `/api/empresas/${S.empresaId}/radar/atualizar`); toast(`${r.novos} edital(is) novo(s) encontrado(s).`, "ok"); V.radar(el); }
    catch (e) { avisarErro(e); }
  });
  $$("[data-acompanhar]", el).forEach((b) => b.onclick = () => ocupado(b, "Baixando edital…", async () => {
    try {
      const ed = await api("POST", `/api/radar/${b.dataset.acompanhar}/acompanhar`);
      toast("Edital levado para Oportunidades.", "ok");
      location.hash = `#/oportunidades/${ed.id}`;
    }
    catch (e) { avisarErro(e); }
  }));
  $$("[data-descartar]", el).forEach((b) => b.onclick = async () => {
    const volta = b.dataset.valor === "descartado" ? "novo" : "descartado";
    try {
      await api("PATCH", `/api/radar/${b.dataset.descartar}`, { status: b.dataset.valor }); V.radar(el);
      toast(b.dataset.valor === "descartado" ? "Edital excluído da lista." : "Edital restaurado.", "ok",
        { rotulo: "Desfazer", fn: async () => { await api("PATCH", `/api/radar/${b.dataset.descartar}`, { status: volta }); V.radar(el); } });
    } catch (e) { avisarErro(e); }
  });
  const lote = $("#radar-lote", el);
  if (lote) lote.onclick = async () => {
    const corte = Number($("#radar-corte", el).value), semNota = $("#radar-sem-nota", el)?.checked || false;
    const n = itens.filter((i) => (i.nota !== null && i.nota < corte) || (semNota && i.nota === null)).length;
    if (!n) { toast("Nenhum edital nessa faixa.", "info"); return; }
    if (!(await confirmar(`Excluir ${n} edital(is) com aderência abaixo de ${corte}${semNota ? " e os sem nota" : ""}? Eles saem da lista e não voltam nas próximas buscas (dá para restaurar no filtro Excluídos).`, "Excluir"))) return;
    try {
      const r = await api("POST", `/api/empresas/${S.empresaId}/radar/descartar-lote`, { abaixo: corte, sem_nota: semNota });
      V.radar(el);
      toast(`${r.qtd} edital(is) excluído(s) da lista.`, "ok", { rotulo: "Desfazer", fn: async () => {
        await api("POST", `/api/empresas/${S.empresaId}/radar/restaurar-lote`, { ids: r.ids }); V.radar(el); } });
    } catch (e) { avisarErro(e); }
  };
  const corteSel = $("#radar-corte", el);
  const contarLote = () => { const c = Number(corteSel.value), sn = $("#radar-sem-nota", el)?.checked;
    $("#radar-lote-n", el).textContent = `Excluir (${itens.filter((i) => (i.nota !== null && i.nota < c) || (sn && i.nota === null)).length})`; };
  if (corteSel) { corteSel.onchange = contarLote; const sn = $("#radar-sem-nota", el); if (sn) sn.onchange = contarLote; }
};

// Limpeza rápida: descartar de uma vez os editais pouco aderentes
function barraLimpezaRadar(itens) {
  const baixos = itens.filter((i) => i.nota !== null && i.nota < 50).length;
  const semNota = itens.filter((i) => i.nota === null).length;
  return `<div class="radar-lote">
    <span>${baixos ? `<b>${baixos}</b> edital(is) com aderência baixa.` : "Limpe a lista excluindo os menos aderentes."}</span>
    <label for="radar-corte" class="oculto-visual">Excluir abaixo de</label>
    <select id="radar-corte"><option value="50" selected>Aderência baixa (até 49)</option><option value="80">Baixa e média (até 79)</option><option value="30">Muito baixa (até 29)</option></select>
    ${semNota ? `<label class="check"><input type="checkbox" id="radar-sem-nota"> incluir ${semNota} sem nota</label>` : ""}
    <button class="botao pequeno secundario" id="radar-lote">${icone("excluir", 14)} <span id="radar-lote-n">Excluir (${baixos})</span></button></div>`;
}

function linhaRadar(i) {
  const d = i.dados;
  const nota = i.nota === null ? "" : carimbo(`Aderência ${i.nota}`, i.nota >= 80 ? "ok" : i.nota >= 50 ? "aviso" : "neutro");
  const faixa = i.nota === null ? "sem-nota" : i.nota >= 80 ? "alta" : i.nota >= 50 ? "media" : "baixa";
  return `<div class="lista-item faixa-${faixa}"><div class="corpo">
      <b>${esc((d.objeto || "").slice(0, 220))}</b>
      <p>${esc(d.orgao)} · ${esc(d.municipio || "")}${d.uf ? "/" + esc(d.uf) : ""} · ${esc(d.modalidade || "")}</p>
      ${d.fonte === "diario" ? `<div class="meta"><span class="fonte-diario">Diário oficial</span><span>Publicado em ${fmt.data(d.data_publicacao)}</span>
        ${i.motivo ? `<span>${esc(i.motivo)}</span>` : ""}${d.link ? `<a href="${esc(d.link)}" target="_blank" rel="noopener">Ver o diário</a>` : ""}</div>`
      : `<div class="meta"><span>Valor estimado ${fmt.moeda(d.valor_estimado)}</span><span title="Data cadastrada pelo órgão no PNCP. Confira no edital: às vezes o cadastro vem errado.">Propostas até ${fmt.dataHora(d.data_encerramento)} <small class="fraco">(PNCP, a conferir)</small></span>
        ${i.motivo ? `<span>${esc(i.motivo)}</span>` : ""}${d.link ? `<a href="${esc(d.link)}" target="_blank" rel="noopener">Ver no PNCP</a>` : ""}</div>`}
    </div><div class="acoes" style="flex-direction:column;align-items:flex-end">${nota}
      ${i.status === "novo" ? `<button class="botao pequeno" data-acompanhar="${i.id}">${icone("adicionar",14)} Acompanhar</button>
        <button class="botao texto pequeno" data-descartar="${i.id}" data-valor="descartado" title="Sai da lista e não volta nas próximas buscas">${icone("excluir",14)} Excluir</button>` : ""}
      ${i.status === "descartado" ? `<button class="botao texto pequeno" data-descartar="${i.id}" data-valor="novo">${icone("restaurar",14)} Restaurar</button>` : ""}
    </div></div>`;
}
