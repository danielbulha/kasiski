// Radar: editais recebendo proposta no PNCP que combinam com o perfil da empresa.
V.radar = async (el) => {
  if (!S.empresaId) { el.innerHTML = exigirEmpresa(); return; }
  const filtro = sessionStorage.getItem("radar_filtro") || "novo";
  const itens = await api("GET", `/api/empresas/${S.empresaId}/radar?status=${filtro}`);
  const emp = empresaAtual();
  el.innerHTML = `
    <div class="cabecalho"><div><h1>Radar de editais</h1>
      <p>Buscando por: ${emp.termos_radar?.length ? esc(emp.termos_radar.join(", ")) : "nenhum segmento ou palavra-chave"} ${emp.ufs ? "· " + esc(emp.ufs) : "· todo o Brasil"}
        · <a href="#/empresas">ajustar</a></p></div>
      <div class="acoes"><select id="filtro" aria-label="Filtrar">
        <option value="novo" ${filtro === "novo" ? "selected" : ""}>Novos</option>
        <option value="acompanhando" ${filtro === "acompanhando" ? "selected" : ""}>Já acompanhados</option>
        <option value="descartado" ${filtro === "descartado" ? "selected" : ""}>Descartados</option></select>
        <button class="botao" id="atualizar">${icone("radarPing")} Buscar agora</button></div></div>
    ${guia(`<p>Todo dia útil, cedo, o Kasiski consulta o PNCP e traz os editais com propostas abertas que contêm suas palavras-chave.
      Uma IA de baixo custo dá uma nota de 0 a 100 de aderência ao seu perfil. Clique em <b>Acompanhar</b> para baixar o edital,
      calcular os prazos e liberar a análise completa. As palavras-chave e os estados ficam em <a href="#/empresas">Minha empresa</a>.</p>`)}
    ${S.plano?.radar_max && itens.length >= S.plano.radar_max ? `<div class="aviso info">O Free mostra os ${S.plano.radar_max} editais mais aderentes. No <b>Essencial</b> (R$ 97/mês) você vê todos. <a href="#/conta">Ver planos</a></div>` : ""}
    <section class="bloco lista-faixas">
      ${itens.length ? legendaFaixas({ alta: "Aderência alta (80+)", media: "Média (50 a 79)", baixa: "Baixa (até 49)" }, "faixa-") + itens.map(linhaRadar).join("") : vazio(filtro === "novo" ? "Nenhum edital novo" : "Nada por aqui",
        filtro === "novo" ? "Clique em Buscar agora ou ajuste as palavras-chave da empresa para ampliar a busca." : "")}
    </section>`;
  $("#filtro", el).onchange = (ev) => { sessionStorage.setItem("radar_filtro", ev.target.value); V.radar(el); };
  $("#atualizar", el).onclick = (ev) => ocupado(ev.target, "Buscando no PNCP…", async () => {
    try { const r = await api("POST", `/api/empresas/${S.empresaId}/radar/atualizar`); toast(`${r.novos} edital(is) novo(s) encontrado(s).`, "ok"); V.radar(el); }
    catch (e) { avisarErro(e); }
  });
  $$("[data-acompanhar]", el).forEach((b) => b.onclick = () => ocupado(b, "Baixando edital…", async () => {
    try { const ed = await api("POST", `/api/radar/${b.dataset.acompanhar}/acompanhar`); location.hash = `#/editais/${ed.id}`; }
    catch (e) { avisarErro(e); }
  }));
  $$("[data-descartar]", el).forEach((b) => b.onclick = async () => {
    await api("PATCH", `/api/radar/${b.dataset.descartar}`, { status: b.dataset.valor }); V.radar(el);
  });
};

function linhaRadar(i) {
  const d = i.dados;
  const nota = i.nota === null ? "" : carimbo(`Aderência ${i.nota}`, i.nota >= 80 ? "ok" : i.nota >= 50 ? "aviso" : "neutro");
  const faixa = i.nota === null ? "sem-nota" : i.nota >= 80 ? "alta" : i.nota >= 50 ? "media" : "baixa";
  return `<div class="lista-item faixa-${faixa}"><div class="corpo">
      <b>${esc((d.objeto || "").slice(0, 220))}</b>
      <p>${esc(d.orgao)} · ${esc(d.municipio || "")}${d.uf ? "/" + esc(d.uf) : ""} · ${esc(d.modalidade || "")}</p>
      <div class="meta"><span>Valor estimado ${fmt.moeda(d.valor_estimado)}</span><span>Propostas até ${fmt.dataHora(d.data_encerramento)}</span>
        ${i.motivo ? `<span>${esc(i.motivo)}</span>` : ""}${d.link ? `<a href="${esc(d.link)}" target="_blank" rel="noopener">Ver no PNCP</a>` : ""}</div>
    </div><div class="acoes" style="flex-direction:column;align-items:flex-end">${nota}
      ${i.status === "novo" ? `<button class="botao pequeno" data-acompanhar="${i.id}">${icone("adicionar",14)} Acompanhar</button>
        <button class="botao texto pequeno" data-descartar="${i.id}" data-valor="descartado">${icone("fechar",14)} Descartar</button>` : ""}
      ${i.status === "descartado" ? `<button class="botao texto pequeno" data-descartar="${i.id}" data-valor="novo">${icone("restaurar",14)} Restaurar</button>` : ""}
    </div></div>`;
}
