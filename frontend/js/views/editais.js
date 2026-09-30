// A lista de editais agora mora em Oportunidades (visão "Lista"): um só lugar para ver o que foi selecionado e o andamento.
V.editais = async () => { sessionStorage.setItem("op_visao", "lista"); location.replace("#/oportunidades"); };

// Legenda das faixas coloridas (a cor nunca é a única pista: o status também aparece escrito na linha)
function legendaFaixas(rotulos, prefixo) {
  return `<div class="legenda-faixas" aria-hidden="true">${Object.entries(rotulos).map(([k, v]) =>
    `<span><i class="${prefixo}${k}"></i>${esc(v)}</span>`).join("")}</div>`;
}

function modalNovoEdital() {
  const m = modal({
    titulo: "Novo edital", corpo: `
    <div class="abas" role="tablist"><button class="ativa" data-aba="pncp">Pelo PNCP</button><button data-aba="upload">Enviar PDF</button></div>
    <form id="form-edital">
      <div data-painel="pncp"><div class="campo"><label for="numero_controle">Número de controle no PNCP</label>
        <input id="numero_controle" name="numero_controle" placeholder="00000000000191-1-000123/2026">
        <small>Está no rodapé da página do edital em pncp.gov.br. Formato: CNPJ-1-sequencial/ano.</small></div></div>
      <div data-painel="upload" class="oculto">
        <div class="campo"><label for="arquivo">PDF do edital</label><input id="arquivo" name="arquivo" type="file" accept=".pdf,.doc,.docx,.txt"></div>
        <div class="linha-campos"><div class="campo"><label for="orgao">Órgão</label><input id="orgao" name="orgao"></div>
          <div class="campo"><label for="numero">Número</label><input id="numero" name="numero" placeholder="Pregão 12/2026"></div></div>
        <div class="campo"><label for="objeto">Objeto</label><input id="objeto" name="objeto"></div>
        <div class="linha-campos"><div class="campo"><label for="valor_estimado">Valor estimado (R$)</label><input id="valor_estimado" name="valor_estimado" inputmode="decimal"></div>
          <div class="campo"><label for="data_abertura">Data e hora da sessão</label><input id="data_abertura" name="data_abertura" type="datetime-local"></div></div>
        <div class="campo"><label for="portal_disputa">Portal onde ocorre a disputa</label><input id="portal_disputa" name="portal_disputa" placeholder="Ex.: BLL, Licitanet, Compras.gov.br"></div>
      </div>
      <div id="erro-edital"></div>
      <button class="botao" style="width:100%" type="submit">Cadastrar edital</button>
    </form>`,
  });
  const form = $("#form-edital", m);
  $$("[data-aba]", m).forEach((b) => b.onclick = () => {
    $$("[data-aba]", m).forEach((x) => x.classList.remove("ativa")); b.classList.add("ativa");
    $$("[data-painel]", m).forEach((p) => p.classList.toggle("oculto", p.dataset.painel !== b.dataset.aba));
  });
  form.onsubmit = async (ev) => {
    ev.preventDefault();
    const modoUpload = $("[data-aba].ativa", m).dataset.aba === "upload";
    const b = form.querySelector("button[type=submit]");
    await ocupado(b, modoUpload ? "Lendo o PDF…" : "Buscando no PNCP…", async () => {
      try {
        let corpo;
        if (modoUpload) { corpo = new FormData(form); if (!$("#arquivo", m).files.length) throw new Error_("Selecione o PDF do edital."); }
        else corpo = { numero_controle: $("#numero_controle", m).value.trim() };
        const ed = await api("POST", `/api/empresas/${S.empresaId}/editais`, corpo);
        marcar("edital_added");
        m.fechar(); location.hash = `#/editais/${ed.id}`;
      } catch (e) { $("#erro-edital", m).innerHTML = erroTela(e); }
    });
  };
}
function Error_(m) { return new Error(m); }

// ---------------------------------------------------------------- datas da licitação (cronograma)
// O PNCP traz só o início e o fim do envio de propostas, e o órgão às vezes cadastra errado: o edital é quem vale.
function htmlAlertaDatas(a, compacto = false) {
  if (!a) return "";
  const cls = a.nivel === "divergencia" ? "aviso alerta-datas divergencia" : "aviso alerta-datas";
  return `<div class="${cls}" role="status">
    <div class="alerta-datas-txt"><b>${icone("alerta", 15)} ${esc(a.titulo)}</b>${compacto ? "" : `<span>${esc(a.texto || "")}</span>`}
      ${!compacto && a.itens?.length ? `<ul>${a.itens.map((i) => `<li>${esc(i)}</li>`).join("")}</ul>` : ""}</div>
    <button class="botao pequeno" data-conferir-datas>Conferir e confirmar</button></div>`;
}

async function modalCronograma(edId, depois) {
  let d;
  try { d = await api("GET", `/api/editais/${edId}`); } catch (e) { avisarErro(e); return; }
  const ed = d.edital, cr = ed.cronograma || {}, ev = cr.eventos || {}, rot = cr.rotulos || {}, fontes = cr.fontes || {};
  const ordem = ["inicio_propostas", "fim_propostas", "sessao", "esclarecimento", "impugnacao"];
  const valor = (iso) => (iso || "").slice(0, 16);
  const linha = (k) => {
    const e = ev[k] || {};
    return `<tr><th scope="row"><label for="cr-${k}">${esc(rot[k] || k)}</label>${k === "sessao" ? " <span class='fraco'>(move todos os prazos)</span>" : ""}</th>
      <td><input type="datetime-local" id="cr-${k}" data-ev="${k}" value="${esc(valor(e.data))}" data-orig="${esc(valor(e.data))}"></td>
      <td class="cr-fonte">${e.fonte ? `${esc(fontes[e.fonte] || e.fonte)}${e.pagina ? ` · pág. ${esc(e.pagina)}` : ""}` : `<span class="fraco">${["esclarecimento", "impugnacao"].includes(k) ? "não fixada no edital: calculada pela lei (3 dias úteis antes da sessão)" : "não encontrada"}</span>`}
        ${e.trecho ? `<small class="cr-trecho">“${esc(e.trecho)}”</small>` : ""}</td></tr>`;
  };
  const pn = cr.pncp || {};
  const m = modal({ titulo: "Datas da licitação", largo: true, corpo: `
    ${htmlAlertaDatas(ed.alerta_datas).replace(/<button[^]*?<\/button>/, "")}
    <p class="fraco">Confira cada data no edital (e em erratas publicadas). As que você corrigir aqui valem sobre qualquer leitura automática,
      e os prazos da agenda são refeitos na hora.</p>
    <div><table class="cr-tabela"><thead><tr><th>Evento</th><th>Data e hora</th><th>De onde veio</th></tr></thead>
      <tbody>${ordem.map(linha).join("")}</tbody></table></div>
    ${pn.abertura || pn.encerramento ? `<p class="fraco cr-pncp">No cadastro do órgão no PNCP: início do envio de propostas ${fmt.dataHora(pn.abertura)} · fim do envio ${fmt.dataHora(pn.encerramento)}.</p>` : ""}
    <p class="fraco">Esclarecimento e impugnação: quando o edital não fixa a data, o Kasiski calcula 3 dias úteis antes da sessão (Lei 14.133, art. 164).</p>
    <div id="cr-erro"></div>`,
    acoes: `${ed.tem_texto ? `<button class="botao texto" id="cr-reler">Ler de novo no edital</button>` : ""}
      <button class="botao secundario" data-fechar>Cancelar</button><button class="botao" id="cr-ok">Salvar e confirmar datas</button>` });
  const rel = $("#cr-reler", m);
  if (rel) rel.onclick = () => ocupado(rel, "Lendo o edital…", async () => {
    try { await api("POST", `/api/editais/${edId}/cronograma/reler`); m.fechar(); toast("Datas lidas de novo no edital. Confira.", "ok"); modalCronograma(edId, depois); if (depois) depois(); }
    catch (e) { $("#cr-erro", m).innerHTML = erroTela(e); }
  });
  $("#cr-ok", m).onclick = () => ocupado($("#cr-ok", m), "Salvando…", async () => {
    const datas = {};
    $$("[data-ev]", m).forEach((i) => { if (i.value !== i.dataset.orig) datas[i.dataset.ev] = i.value || null; });
    if (!$("#cr-sessao", m).value) { $("#cr-erro", m).innerHTML = `<div class="aviso erro">Informe a data e hora da sessão pública.</div>`; return; }
    try {
      await api("POST", `/api/editais/${edId}/cronograma`, { datas, confirmar: true });
      m.fechar(); toast("Datas confirmadas. Prazos atualizados.", "ok"); if (depois) depois();
    } catch (e) { $("#cr-erro", m).innerHTML = erroTela(e); }
  });
}

// ---------------------------------------------------------------- detalhe do edital
V.edital = async (el, id) => {
  const d = await api("GET", `/api/editais/${id}`);
  const ed = d.edital;
  const aba = sessionStorage.getItem("edital_aba_" + id) || "analise";
  const abas = [["analise", "Análise"], ["prazos", `Prazos${d.prazos.filter((p) => !p.concluido).length ? ` (${d.prazos.filter((p) => !p.concluido).length})` : ""}`],
    ["documentos", `Documentos e atas${d.qtd_documentos ? ` (${d.qtd_documentos})` : ""}`],
    ["concorrentes", `Concorrentes (${d.concorrentes.length})`], ["pecas", `Peças (${d.pecas.length})`]];
  el.innerHTML = `
    <nav class="trilha" aria-label="Você está em"><a href="#/oportunidades/${ed.id}">${icone("chevronEsquerda", 14)} Oportunidades</a><span aria-hidden="true">/</span><span>${esc(ed.numero || ed.numero_controle || "Licitação")}</span></nav>
    <div class="capa">
      <div class="capa-topo"><div><div class="processo">${esc(ed.numero || ed.numero_controle || "Sem número")} · ${esc(ed.modalidade || "")}</div>
          <h1>${esc(ed.objeto || "Edital ainda sem objeto — clique em Analisar para extrair")}</h1></div>
        <div class="acoes"><a class="botao pequeno secundario" href="#/oportunidades/${ed.id}" title="Abrir no quadro de oportunidades">${icone("kanban", 14)} ${esc(ETAPA_NOMES_OP[ed.etapa] || "Ver no quadro")}</a>
          ${carimbo(ROTULOS.statusEdital[ed.status] || ed.status, ed.status === "ganho" ? "ok" : ed.status === "perdido" ? "erro" : "neutro")}
          <select id="status" aria-label="Alterar status">${Object.entries(ROTULOS.statusEdital).map(([k, v]) => `<option value="${k}" ${ed.status === k ? "selected" : ""}>${v}</option>`).join("")}</select>
          <button class="botao pequeno texto" id="excluir-edital" title="Excluir licitação">${icone("excluir", 14)} Excluir</button></div></div>
      <dl class="capa-campos">
        <div><dt>Órgão</dt><dd>${esc(ed.orgao || "—")}</dd></div>
        <div><dt>${/dispensa|inexigib/i.test(ed.modalidade || "") ? "Publicação do aviso" : "Sessão pública"}</dt><dd>${fmt.dataHora(ed.data_abertura)} <button class="botao texto pequeno" data-conferir-datas title="Conferir e corrigir as datas">${ed.data_abertura ? "Conferir datas" : "Informar datas"}</button></dd></div>
        <div><dt>Valor estimado</dt><dd>${fmt.moeda(ed.valor_estimado)}</dd></div>
        <div><dt>Tipo de objeto</dt><dd><select id="tipo_objeto_ed" aria-label="Tipo de objeto">
          <option value="">Não classificado</option>
          ${Object.entries(ROTULOS.tipoObjeto).map(([k, v]) => `<option value="${k}" ${ed.tipo_objeto === k ? "selected" : ""}>${v}</option>`).join("")}
          </select></dd></div>
        <div><dt>Segmento</dt><dd><select id="segmento_ed" aria-label="Segmento">
          <option value="">Não classificado</option>
          ${Object.entries(ROTULOS.segmento).map(([k, v]) => `<option value="${k}" ${ed.segmento === k ? "selected" : ""}>${v}</option>`).join("")}
          </select></dd></div>
        <div><dt>Portal da disputa</dt><dd>${esc(ed.portal_disputa || "—")}</dd></div>
        <div><dt>Local</dt><dd>${esc(ed.municipio || "—")}${ed.uf ? "/" + esc(ed.uf) : ""}</dd></div>
        <div><dt>Documento</dt><dd>${ed.tem_documento ? `<button class="botao pequeno secundario" id="abrir-doc">${icone("olho", 14)} Abrir edital</button>` : ""}
          <button class="botao pequeno texto" id="enviar-pdf-ed">${icone("upload", 14)} ${ed.nome_arquivo ? "Trocar PDF" : "Enviar PDF"}</button>
          ${ed.link ? ` <a href="${esc(ed.link)}" target="_blank" rel="noopener">Ver no PNCP</a>` : ""}${!ed.tem_documento && !ed.link ? "—" : ""}
          ${ed.nome_arquivo ? `<br><small class="fraco">${esc(ed.nome_arquivo)}</small>` : ""}</dd></div>
      </dl>${ed.data_abertura && !ed.alerta_datas && ed.cronograma?.confirmado ? `<p class="fraco cr-conferido">${icone("ok", 13)} Datas conferidas por ${esc(ed.cronograma.confirmado.por || "")} em ${fmt.dataHora(ed.cronograma.confirmado.em)} · <button class="botao texto pequeno" data-conferir-datas>rever</button></p>` : ""}</div>
    ${htmlAlertaDatas(ed.alerta_datas)}
    <div class="abas" role="tablist">${abas.map(([k, t]) => `<button data-aba="${k}" class="${aba === k ? "ativa" : ""}">${t}</button>`).join("")}</div>
    <div id="painel-aba"></div>`;
  const ad = $("#abrir-doc", el); if (ad) ad.onclick = () => abrirDocumentoEdital(id, ad);
  $$("[data-conferir-datas]", el).forEach((b) => b.onclick = () => modalCronograma(id, () => V.edital(el, id)));
  $("#enviar-pdf-ed", el).onclick = () => modalEditalSemDocumento(id, { erro: "Envie o edital em PDF (de preferência com texto selecionável) para guardar e analisar.", link: ed.link });
  $("#excluir-edital", el).onclick = () => excluirParaLixeira({ url: `/api/editais/${id}`, nome: "esta licitação", tipo: "edital",
    aviso: "Prazos, peças, propostas e documentos dela vão junto. ", depois: () => { if (location.hash === `#/editais/${id}`) location.hash = "#/oportunidades"; else V.edital(el, id); } });
  $("#status", el).onchange = async (ev) => { await api("PATCH", `/api/editais/${id}`, { status: ev.target.value }); toast("Status atualizado.", "ok"); };
  $("#tipo_objeto_ed", el).onchange = async (ev) => { await api("PATCH", `/api/editais/${id}`, { tipo_objeto: ev.target.value }); toast("Tipo de objeto atualizado.", "ok"); };
  $("#segmento_ed", el).onchange = async (ev) => { await api("PATCH", `/api/editais/${id}`, { segmento: ev.target.value }); toast("Segmento atualizado.", "ok"); };
  $$("[data-aba]", el).forEach((b) => b.onclick = () => { sessionStorage.setItem("edital_aba_" + id, b.dataset.aba); V.edital(el, id); });
  const painel = $("#painel-aba", el);
  if (aba === "analise") painelAnalise(painel, ed, d.analises, d.analise_andamento);
  if (aba === "prazos") painelPrazosEdital(painel, ed, d.prazos);
  if (aba === "documentos") painelDocumentosEdital(painel, ed);
  if (aba === "concorrentes") painelConcorrentesEdital(painel, ed, d.concorrentes);
  if (aba === "pecas") painelPecasEdital(painel, ed, d.pecas);
};

function painelAnalise(el, ed, analises, andamento) {
  const ultima = analises[0];
  el.innerHTML = `
    <div class="acoes nao-imprimir" style="margin-bottom:14px">
      <button class="botao" id="analisar">${icone("radarPing")} ${ultima ? "Analisar novamente" : "Analisar edital"}</button>
      ${!ed.tem_texto ? `<span class="fraco">Envie o PDF do edital para habilitar a análise.</span>` : ""}
      ${ultima ? `<button class="botao secundario" id="imprimir">${icone("imprimir")} Imprimir relatório</button>` : ""}
      <button class="botao secundario" id="montar-proposta">Montar proposta comercial</button>
    </div>
    <div id="corpo-analise">${ultima ? htmlAnalise(ultima) : guia(`<p>A análise extrai os dados do edital, confere cada exigência de habilitação
      contra o <a href="#/cofre">cofre de documentos</a> da empresa, aponta cláusulas que restringem a competição e recomenda se vale a pena participar.
      Cada exigência, cláusula restritiva e risco passa pelo <b>DoubleCheck™</b>: uma IA analisa, outra confere e você vê o resultado de cada item.</p>`)}</div>
    <div id="possiveis-conc"></div>`;
  $("#analisar", el).onclick = async () => {
    try { acompanharAnalise(el, ed, await api("POST", `/api/editais/${ed.id}/analisar`)); }
    catch (e) { avisarErro(e); }
  };
  if (ultima) ligarAcoesAnalise(el, ed, ultima);
  // Vindo do dossiê da oportunidade com "Analisar edital": começa a análise sem outro clique
  if (sessionStorage.getItem("analisar_auto") === String(ed.id)) {
    sessionStorage.removeItem("analisar_auto");
    if (andamento) { /* já está analisando */ }
    else if (ed.tem_texto) $("#analisar", el).click();
    else toast("Envie o PDF do edital para a IA poder analisar.", "erro");
  }
  desenharPossiveis($("#possiveis-conc", el), ed);
  if (andamento) acompanharAnalise(el, ed, andamento);
  $("#montar-proposta", el).onclick = () => modalNovaProposta(ed.id);
  const imp = $("#imprimir", el); if (imp) imp.onclick = () => window.print();
}

function htmlAnalise(a) {
  const r = a.resultado;
  const rec = r.recomendacao || {};
  const [rotulo, tipo] = ROTULOS.decisao[rec.decisao] || ["—", "neutro"];
  return `
    <div class="relatorio-cabecalho"><strong>${esc(S.conta?.marca_relatorio || S.conta?.nome || "")}</strong><span>${new Date().toLocaleDateString("pt-BR")}</span></div>
    ${a.demonstracao ? `<div class="aviso info">Análise de demonstração — configure as chaves de IA para uma análise real deste edital.</div>` : ""}
    ${dcResumoHtml(r.doublecheck, { titulo: "DoubleCheck™ desta análise", sub: "Uma IA analisa. Outra confere. Você decide." })}
    <div class="bloco"><div class="bloco-titulo"><h2>Recomendação</h2>${carimbo(rotulo, tipo, true)}</div>
      <p>${esc(r.resumo || "")}</p>${rec.justificativa ? `<p class="fraco">${esc(rec.justificativa)}</p>` : ""}
      ${r.beneficios_me_epp ? `<p><b>ME/EPP:</b> ${esc(r.beneficios_me_epp)}</p>` : ""}
      ${r.proximos_passos?.length ? `<p><b>Próximos passos:</b></p><ul>${r.proximos_passos.map((p) => `<li>${esc(p)}</li>`).join("")}</ul>` : ""}</div>

    <div class="bloco"><h2>Checklist de habilitação</h2>
      <div class="tabela-rolagem"><table><thead><tr><th>Exigência</th><th>Categoria</th><th>Pág.</th><th>Situação</th><th>Documento no cofre</th><th>DoubleCheck™</th></tr></thead>
      <tbody>${(r.checklist || []).map((c) => `<tr><td>${esc(c.exigencia)}${c.observacao ? `<div class="fraco" style="font-size:.85rem">${esc(c.observacao)}</div>` : ""}</td>
        <td>${esc(ROTULOS.categoriaDoc[c.categoria] || c.categoria || "")}</td><td>${esc(c.pagina || "—")}</td>
        <td>${carimboStatus(ROTULOS.checklist, c.status)}</td><td>${esc(c.documento_cofre || "—")}</td>
        <td>${c.verificacao ? dcSelo(c.verificacao, { titulo: c.exigencia, texto: `Situação atribuída: ${ROTULOS.checklist[c.status]?.[0] || c.status || "—"}${c.documento_cofre ? ` · documento no cofre: ${c.documento_cofre}` : ""}`, pagina: c.pagina }, { compacto: true }) : `<span class="fraco">—</span>`}</td></tr>`).join("")}</tbody></table></div>
      ${(r.checklist || []).some((c) => c.status !== "atende") ? `<p class="nao-imprimir"><a href="#/cofre">Atualizar o cofre de documentos →</a></p>` : ""}</div>

    ${(r.checklist_setorial || []).length ? `<div class="bloco"><h2>Checklist setorial</h2>
      <p class="fraco">Exigências regulatórias próprias do tipo de objeto ou do setor (ex.: ANVISA, ART/RRT, PNAE) — não fazem parte da habilitação padrão da Lei 14.133.</p>
      <div class="tabela-rolagem"><table><thead><tr><th>Exigência</th><th>Pág.</th><th>Situação</th><th>Fundamento</th><th>DoubleCheck™</th></tr></thead>
      <tbody>${r.checklist_setorial.map((c) => `<tr><td>${esc(c.exigencia)}${c.observacao ? `<div class="fraco" style="font-size:.85rem">${esc(c.observacao)}</div>` : ""}</td>
        <td>${esc(c.pagina || "—")}</td><td>${carimboStatus(ROTULOS.checklist, c.status)}</td><td>${esc(c.fundamento || "—")}</td>
        <td>${c.verificacao ? dcSelo(c.verificacao, { titulo: c.exigencia, texto: c.fundamento || "", pagina: c.pagina }, { compacto: true }) : `<span class="fraco">—</span>`}</td></tr>`).join("")}</tbody></table></div></div>` : ""}

    ${(r.clausulas_restritivas || []).length ? `<div class="bloco"><h2>Cláusulas potencialmente restritivas</h2>
      <p class="fraco">Selecione as que quer sustentar e gere a minuta de esclarecimento ou impugnação.</p>
      ${r.clausulas_restritivas.map((c) => apontamentoHtml({
        id: c.id, titulo: c.clausula, gravidade: c.gravidade, pagina: c.pagina, fundamento: c.fundamento,
        corpo: c.por_que_restringe, verificacao: c.verificacao, medida: c.medida === "impugnacao" ? "Sugestão: impugnação" : "Sugestão: pedido de esclarecimento",
      })).join("")}
      <button class="botao nao-imprimir" id="gerar-peca-clausulas">Gerar peça com os selecionados</button></div>` : ""}

    ${(r.riscos || []).length ? `<div class="bloco"><h2>Riscos identificados</h2>
      ${r.riscos.map((rk) => apontamentoHtml({ id: rk.id, titulo: rk.tema, gravidade: rk.nivel, pagina: rk.pagina, corpo: rk.descricao, verificacao: rk.verificacao, semSelecao: true })).join("")}</div>` : ""}
    ${dcRodape()}`;
}

function apontamentoHtml({ id, titulo, gravidade, pagina, fundamento, corpo, verificacao, medida, semSelecao }) {
  const [gLabel, gTipo] = ROTULOS.gravidade[gravidade] || ROTULOS.forca[gravidade] || [gravidade, "neutro"];
  return `<div class="apontamento ${gravidade}"><header><h4>${esc(titulo)}</h4>${carimbo(gLabel, gTipo)}</header>
    <p>${esc(corpo)}</p>
    <p class="fraco">${pagina ? `Pág. ${esc(pagina)} · ` : ""}${esc(fundamento || "")}${medida ? " · " + esc(medida) : ""}</p>
    ${revisorHtml(verificacao, { titulo, texto: corpo, pagina, fonte: fundamento })}
    ${semSelecao ? "" : `<label class="selecionar"><input type="checkbox" class="sel-clausula" value="${id}"> Usar nesta peça</label>`}</div>`;
}

function ligarAcoesAnalise(el, ed, analise) {
  const btn = $("#gerar-peca-clausulas", el);
  if (btn) btn.onclick = () => {
    const ids = $$(".sel-clausula:checked", el).map((c) => c.value);
    if (!ids.length) { toast("Selecione ao menos uma cláusula."); return; }
    location.hash = `#/pecas`;
    sessionStorage.setItem("nova_peca", JSON.stringify({ edital_id: ed.id, analise_id: analise.id, itens: ids }));
  };
}

function painelPrazosEdital(el, ed, prazos) {
  const direta = /dispensa|inexigib/i.test(ed.modalidade || "");
  el.innerHTML = `
    ${guia(direta
      ? `<p>Este processo é de <b>contratação direta</b> (dispensa/inexigibilidade), não um pregão: não há sessão
        de disputa nem prazo de impugnação/recurso nesses moldes. O prazo calculado é o de divulgação prévia
        mínima do aviso de contratação direta (3 dias úteis, art. 75, §3º) — é a janela para questionar o
        enquadramento, se for o caso, antes de o contrato ser assinado.</p>`
      : `<p>Os prazos de esclarecimento, impugnação e sessão são calculados a partir da data e hora da sessão, em dias úteis (art. 164).
        Depois da sessão, registre a data da intimação do resultado para calcular o prazo das razões de recurso (3 dias úteis, art. 165).</p>`)}
    <section class="bloco"><div class="bloco-titulo"><h3>Registrar resultado / intimação</h3></div>
      <form id="form-resultado" class="linha-campos" style="align-items:flex-end">
        <div class="campo"><label for="data_resultado">Data da intimação ou da ata</label><input type="date" id="data_resultado" name="data" required></div>
        <div class="campo"><label for="status_resultado">Novo status</label><select id="status_resultado" name="status">
          ${Object.entries(ROTULOS.statusEdital).map(([k, v]) => `<option value="${k}" ${ed.status === k ? "selected" : ""}>${v}</option>`).join("")}</select></div>
        <button class="botao" type="submit">Calcular prazo de recurso</button></form></section>
    <section class="bloco">${prazos.length ? prazos.map((p) => `<div class="lista-item"><div class="corpo"><b>${esc(p.titulo)}</b>
      <p>${esc(p.fundamento || "")}</p></div><div class="acoes"><span>${fmt.dataHora(p.data)}</span>${carimboPrazo(p.data)}
      <label class="check"><input type="checkbox" data-concluir="${p.id}" ${p.concluido ? "checked" : ""}> Feito</label></div></div>`).join("")
      : vazio("Sem prazos ainda", "Informe a data da sessão para calcular os prazos automaticamente.")}</section>`;
  $("#form-resultado", el).onsubmit = async (ev) => {
    ev.preventDefault();
    await api("POST", `/api/editais/${ed.id}/resultado`, dadosForm(ev.target));
    toast("Prazo de recurso calculado.", "ok");
    sessionStorage.setItem("edital_aba_" + ed.id, "prazos"); // mantém a aba atual após recarregar
    V.edital($("#conteudo"), ed.id);
  };
  $$("[data-concluir]", el).forEach((c) => c.onchange = () => api("PATCH", `/api/agenda/${c.dataset.concluir}`, { concluido: c.checked }));
}

function painelPecasEdital(el, ed, pecas) {
  el.innerHTML = `<section class="bloco"><div class="bloco-titulo"><h3>Peças deste edital</h3><a class="botao pequeno" href="#/pecas">Gerar nova peça</a></div>
    ${pecas.length ? pecas.map((p) => `<div class="lista-item"><div class="corpo"><b>${esc(p.titulo)}</b>
      <p>${fmt.dataHora(p.criado_em)}</p></div>${carimbo(p.status === "revisada" ? "Revisada" : p.status === "revisao_solicitada" ? "Em revisão" : "Rascunho",
        p.status === "revisada" ? "ok" : p.status === "revisao_solicitada" ? "aviso" : "neutro")}
      <a class="botao pequeno secundario" href="#/pecas/${p.id}">${icone("chevronDireita",14)} Abrir</a></div>`).join("")
      : vazio("Nenhuma peça gerada", "Selecione cláusulas na aba Análise ou vá em Peças para redigir do zero.")}</section>`;
}

function painelConcorrentesEdital(el, ed, analises) {
  el.innerHTML = `
    ${guia(`<p>Depois da sessão, baixe do portal da disputa a habilitação ou a proposta do concorrente que você quer questionar
      e envie aqui junto com o CNPJ dele. O Kasiski monta um dossiê público (Receita, sanções e histórico no PNCP), confronta o
      documento com as exigências do edital e só mantém no parecer os apontamentos confirmados pelo DoubleCheck™ (verificação por uma segunda IA).</p>`)}
    <section class="bloco"><div class="bloco-titulo"><h3>Nova análise de concorrente</h3></div>
      <form id="form-concorrente">
        <div class="linha-campos">
          <div class="campo"><label for="cnpj_c">CNPJ do concorrente</label><input id="cnpj_c" name="cnpj" required placeholder="00.000.000/0000-00"></div>
          <div class="campo"><label for="tipo_c">Tipo de documento</label><select id="tipo_c" name="tipo">
            <option value="habilitacao">Documentos de habilitação</option><option value="proposta">Proposta comercial</option></select></div>
        </div>
        <div id="campos-proposta" class="linha-campos oculto">
          <div class="campo"><label for="valor_proposta">Valor da proposta (R$)</label><input id="valor_proposta" name="valor_proposta" inputmode="decimal"></div>
          <div class="campo"><label class="check"><input type="checkbox" name="engenharia"> É obra/serviço de engenharia</label></div>
        </div>
        <div class="campo"><label for="arquivo_c">Documento baixado do portal (PDF)</label><input id="arquivo_c" name="arquivo" type="file" accept=".pdf,.doc,.docx,.txt" required></div>
        <div id="erro-concorrente"></div>
        <button class="botao" type="submit">Analisar concorrente</button></form></section>
    <section class="bloco">${analises.length ? analises.map((a) => `<div class="lista-item"><div class="corpo">
        <b>${esc(a.concorrente?.razao_social || fmt.cnpj(a.concorrente?.cnpj))} — ${a.tipo === "habilitacao" ? "Habilitação" : "Proposta"}</b>
        <p>${fmt.cnpj(a.concorrente?.cnpj)} · ${fmt.dataHora(a.criado_em)} · ${(a.resultado.apontamentos || []).length} apontamento(s) confirmado(s)</p></div>
        <div class="acoes"><a class="botao pequeno secundario" data-abrir-conc="${a.id}">${icone("olho",14)} Ver parecer</a>
        <button class="botao pequeno texto" data-excluir-conc="${a.id}" aria-label="Excluir análise">${icone("excluir",14)}</button></div></div>`).join("")
      : vazio("Nenhuma análise ainda", "Envie o primeiro documento de um concorrente acima.")}</section>`;
  const pre = sessionStorage.getItem("cnpj_concorrente_" + ed.id);
  if (pre) { $("#cnpj_c", el).value = fmt.cnpj(pre); sessionStorage.removeItem("cnpj_concorrente_" + ed.id); $("#arquivo_c", el).focus(); }
  const sel = $("#tipo_c", el);
  sel.onchange = () => $("#campos-proposta", el).classList.toggle("oculto", sel.value !== "proposta");
  $("#form-concorrente", el).onsubmit = async (ev) => {
    ev.preventDefault();
    const b = ev.target.querySelector("button[type=submit]");
    await ocupado(b, "Consultando dossiê público e analisando…", async () => {
      try {
        const ac = await api("POST", `/api/editais/${ed.id}/concorrentes`, new FormData(ev.target));
        await atualizarConta();
        abrirParecerConcorrente(ac);
        V.edital($("#conteudo"), ed.id);
      } catch (e) { $("#erro-concorrente", el).innerHTML = erroTela(e); }
    });
  };
  $$("[data-excluir-conc]", el).forEach((b) => b.onclick = () => excluirParaLixeira({ url: `/api/analises-concorrente/${b.dataset.excluirConc}`,
    nome: "esta análise de concorrente", tipo: "analise_concorrente", depois: () => V.edital($("#conteudo"), ed.id) }));
  $$("[data-abrir-conc]", el).forEach((b) => b.onclick = async () => {
    const c = await api("GET", `/api/concorrentes/${(analises.find((a) => a.id == b.dataset.abrirConc)).concorrente_id}`);
    abrirParecerConcorrente(c.analises.find((a) => a.id == b.dataset.abrirConc));
  });
}

function abrirParecerConcorrente(a) {
  const r = a.resultado;
  const m = modal({
    titulo: `Parecer — ${a.tipo === "habilitacao" ? "Habilitação" : "Proposta"} do concorrente`, largo: true, corpo: `
    ${a.demonstracao ? `<div class="aviso info">Análise de demonstração — configure as chaves de IA para um parecer real.</div>` : ""}
    <p>${esc(r.resumo || "")}</p>
    ${r.percentual_do_estimado !== undefined ? `<p><b>${r.percentual_do_estimado}%</b> do valor estimado do edital.</p>` : ""}
    ${r.exequibilidade?.conclusao && r.exequibilidade.conclusao !== "nao_se_aplica" ? `<p><b>Exequibilidade:</b> ${esc(r.exequibilidade.analise)}</p>` : ""}
    <h3>Apontamentos confirmados</h3>
    ${(r.apontamentos || []).length ? r.apontamentos.map((ap) => apontamentoHtml({
      id: ap.id, titulo: ap.tema, gravidade: ap.forca, pagina: ap.pagina, fundamento: ap.fundamento, corpo: ap.descricao,
      verificacao: ap.verificacao,
    })).join("") : "<p class='fraco'>Nenhum apontamento confirmado neste documento.</p>"}
    ${(r.cruzamentos_historico || []).length ? `<h3 style="margin-top:16px">Cruzamento com o histórico da empresa</h3>
      <p class="fraco">Hipóteses a conferir, a partir do dossiê completo (inabilitações e documentos de outros certames).</p>
      ${r.cruzamentos_historico.map((z) => apontamentoHtml({ id: z.id, titulo: z.tema, gravidade: z.forca, fundamento: (z.fontes || []).join(", "),
        corpo: `${z.o_que_o_historico_mostra || ""} — Conferir: ${z.o_que_conferir_no_documento_atual || ""}` })).join("")}` : ""}
    ${(r.sugestoes || []).length ? `<h3 style="margin-top:16px">Sugestões de peça</h3>
      ${r.sugestoes.map((sg) => apontamentoHtml({ id: sg.id, titulo: `${({ recurso: "Recurso", contrarrazoes: "Contrarrazões", intencao_recurso: "Intenção de recorrer", pedido_diligencia: "Pedido de diligência", impugnacao: "Impugnação", representacao: "Representação" })[sg.peca] || sg.peca}: ${sg.tema}`,
        gravidade: sg.forca, fundamento: sg.fundamento, corpo: sg.argumento })).join("")}` : ""}
    ${r.usou_historico === false ? `<p class="fraco" style="margin-top:12px">Dica: monte o <a href="#/concorrentes/${a.concorrente_id}">dossiê completo</a> deste concorrente para a IA cruzar com inabilitações e documentos de outros certames.</p>` : ""}
    ${(r.descartados || []).length ? `<details style="margin-top:10px"><summary class="fraco">${r.descartados.length} apontamento(s) descartado(s) pelo DoubleCheck™</summary>
      ${r.descartados.map((ap) => apontamentoHtml({ titulo: ap.tema, gravidade: ap.forca, corpo: ap.descricao, verificacao: ap.verificacao, semSelecao: true })).join("")}</details>` : ""}
    `, acoes: `<button class="botao secundario" data-fechar>Fechar</button>
      ${(r.apontamentos || []).length || (r.sugestoes || []).length ? `<button class="botao" id="usar-em-peca">Usar em recurso/contrarrazões</button>` : ""}`,
  });
  const bp = $("#usar-em-peca", m);
  if (bp) bp.onclick = () => {
    const marcados = $$(".sel-clausula:checked", m).map((c) => c.value);
    const ids = marcados.length ? marcados : [...(r.apontamentos || []), ...(r.sugestoes || [])].map((ap) => ap.id);
    sessionStorage.setItem("nova_peca", JSON.stringify({ edital_id: a.edital_id, analise_concorrente_id: a.id, itens: ids }));
    m.fechar(); location.hash = "#/pecas";
  };
}

// A análise roda em segundo plano no servidor (editais grandes levam alguns minutos).
// Esta função mostra o andamento e consulta a situação a cada poucos segundos.
function acompanharAnalise(el, ed, a) {
  const botao = $("#analisar", el);
  if (botao) botao.disabled = true;
  let caixa = $("#andamento-analise", el);
  if (!caixa) {
    caixa = document.createElement("div");
    caixa.id = "andamento-analise";
    caixa.className = "aviso info andamento-analise";
    caixa.setAttribute("role", "status");
    $("#corpo-analise", el).before(caixa);
  }
  const inicio = new Date(a.criado_em + (a.criado_em.endsWith("Z") ? "" : "Z"));
  const desenhar = (x) => {
    const seg = Math.max(0, Math.round((Date.now() - inicio) / 1000));
    const tempo = seg < 60 ? `${seg}s` : `${Math.floor(seg / 60)} min ${String(seg % 60).padStart(2, "0")}s`;
    caixa.innerHTML = `<span class="girando" aria-hidden="true"></span><div><b>Analisando o edital…</b> ${esc(x.etapa || "")} · ${tempo}
      <br><small>Editais longos levam de 2 a 6 minutos. Pode sair desta tela: a análise continua e fica salva aqui.</small></div>`;
  };
  desenhar(a);
  const passo = async () => {
    if (!document.body.contains(caixa)) return; // usuário saiu da tela
    let x;
    try { x = await api("GET", `/api/editais/${ed.id}/analises/${a.id}`); } catch { setTimeout(passo, 8000); return; }
    if (x.status === "processando") { a.etapa = x.etapa; desenhar(x); setTimeout(passo, 4000); return; }
    if (x.status === "concluida") {
      marcar("edital_analyzed", { decisao: x.resultado?.recomendacao?.decisao || "" });
      await atualizarConta();
      toast("Análise concluída.", "ok");
      // Reabre a tela inteira: a análise pode ter classificado tipo de objeto/segmento e gerado prazos.
      V.edital($("#conteudo"), ed.id);
      return;
    }
    caixa.className = "aviso erro";
    caixa.textContent = x.erro || "A análise não foi concluída. Tente novamente.";
    if (botao) botao.disabled = false;
  };
  const relogio = setInterval(() => { if (!document.body.contains(caixa) || !caixa.querySelector(".girando")) clearInterval(relogio); else desenhar(a); }, 1000);
  setTimeout(passo, 3000);
}

// Abre o PDF do edital numa nova aba. A janela é aberta no clique (antes da chamada) para o navegador não bloquear.
async function abrirDocumentoEdital(id, botao) {
  const janela = window.open("", "_blank");
  if (janela) janela.document.write("<p style='font-family:sans-serif;padding:24px'>Carregando o edital…</p>");
  const original = botao?.innerHTML;
  if (botao) botao.disabled = true;
  try {
    const r = await api("GET", `/api/editais/${id}/documento`);
    const blob = await r.blob();
    const url = URL.createObjectURL(blob);
    const pdf = (blob.type || "").includes("pdf") || (blob.type || "").startsWith("text/");
    const nomeArq = decodeURIComponent(/filename\*?=(?:UTF-8'')?"?([^";]+)/i.exec(r.headers.get("Content-Disposition") || "")?.[1] || "edital.pdf");
    if (pdf && janela) {
      janela.document.open();
      janela.document.write(`<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>${esc(nomeArq)}</title>
        <style>html,body{margin:0;height:100%;font-family:Inter,Arial,sans-serif}header{display:flex;justify-content:space-between;align-items:center;padding:8px 14px;background:#071D2D;color:#fff;font-size:14px}
        header a{color:#11B8C8}iframe{border:0;width:100%;height:calc(100% - 38px)}</style></head>
        <body><header><span>${esc(nomeArq)}</span><a href="${url}" download="${esc(nomeArq)}">Baixar</a></header><iframe src="${url}" title="${esc(nomeArq)}"></iframe></body></html>`);
      janela.document.close();
    } else {
      if (janela) janela.close();
      const a = document.createElement("a"); a.href = url; a.download = nomeArq; a.click();
    }
    setTimeout(() => URL.revokeObjectURL(url), 30 * 60000);
  } catch (e) {
    if (janela) janela.close();
    if (e.codigo === "sem_documento") modalEditalSemDocumento(id, e.dados || {});
    else avisarErro(e);
  }
  finally { if (botao) { botao.disabled = false; botao.innerHTML = original; } }
}

// O PDF não veio do PNCP (arquivo zipado de outro jeito, escaneado ou fora do ar): abrir no portal ou enviar o PDF
function modalEditalSemDocumento(id, d) {
  const lista = d.arquivos_pncp || [];
  const m = modal({ titulo: "Abrir o edital", corpo: `
    <p>${esc(d.erro || "Não consegui abrir o edital por aqui.")}</p>
    ${lista.length ? `<h3>Arquivos publicados no PNCP</h3><ul class="rel-lista">${lista.map((a) => `<li><a href="${esc(a.url)}" target="_blank" rel="noopener">${esc(a.titulo)}</a>${a.tipo && a.tipo !== a.titulo ? ` <small class="fraco">(${esc(a.tipo)})</small>` : ""}</li>`).join("")}</ul>`
      : d.link ? `<p><a class="botao secundario" href="${esc(d.link)}" target="_blank" rel="noopener">Ver a contratação no PNCP</a></p>` : ""}
    <h3>Enviar o PDF do edital</h3>
    <p class="fraco">Baixou o edital no portal? Envie aqui: ele fica guardado e a IA passa a poder analisá-lo.</p>
    <form id="form-pdf-edital"><div class="campo"><label for="pdf-ed">Arquivo (PDF, DOCX ou TXT)</label><input id="pdf-ed" name="arquivo" type="file" accept=".pdf,.docx,.txt" required></div>
      <button class="botao" type="submit">${icone("upload", 15)} Enviar edital</button></form>` });
  $("#form-pdf-edital", m).onsubmit = async (ev) => {
    ev.preventDefault();
    const b = ev.target.querySelector("button");
    await ocupado(b, "Enviando…", async () => {
      try { const r = await api("PATCH", `/api/editais/${id}`, new FormData(ev.target)); m.fechar(); toast(r.aviso || "Edital enviado.", r.aviso ? "erro" : "ok"); if (location.hash.startsWith(`#/editais/${id}`)) V.edital($("#conteudo"), id); }
      catch (e2) { avisarErro(e2); }
    });
  };
}

// ---------------------------------------------------------------- possíveis concorrentes (histórico do PNCP)
function blocoPrecosItens(pc) {
  const lista = pc.precos_itens || [];
  if (!pc.itens_edital) return `<div class="aviso info" style="margin-top:14px">Para ver o preço médio dos concorrentes em cada item, o Kasiski precisa da lista de itens do edital:
    crie uma proposta comercial para este edital (os itens são lidos do PDF) ou traga o edital pelo Radar (itens do PNCP) e avalie de novo.</div>`;
  const com = lista.filter((p) => p.n);
  const pct = (v) => (v === null || v === undefined ? "—" : `${fmt.num(v, 0)}%`);
  return `<h3 style="margin-top:20px">Preço médio dos concorrentes nos itens deste edital</h3>
    <p class="fraco">Preço unitário homologado em ${pc.amostras_preco || 0} resultado(s) de itens parecidos nas atas e contratações anteriores. Cada empresa conta uma vez por item (média das médias). Confira a unidade: itens com unidade diferente foram descartados.</p>
    ${com.length ? `<div class="tabela-rolagem"><table class="tabela-precos-conc"><thead><tr><th>Item</th><th>Descrição</th><th>Unid.</th><th>Estimado</th><th>Média dos concorrentes</th><th>Menor média</th><th>Média / estimado</th><th>Empresas</th></tr></thead>
      <tbody>${lista.map((p, k) => `<tr>
        <td>${esc(p.numero || "—")}</td><td>${esc((p.descricao || "").slice(0, 120))}</td><td>${esc(p.unidade || "—")}</td>
        <td>${p.estimado ? fmt.moeda(p.estimado) : "—"}</td>
        <td>${p.n ? `<b>${fmt.moeda(p.media)}</b>` : '<small class="fraco">sem histórico</small>'}</td>
        <td>${p.n ? fmt.moeda(p.minimo) : "—"}</td>
        <td>${p.pct_estimado ? `<span class="${p.pct_estimado < 75 ? "texto-alerta" : ""}">${pct(p.pct_estimado)}</span>` : "—"}</td>
        <td>${p.n ? `<button class="botao pequeno texto" data-precos-item="${k}" aria-expanded="false">${p.n_empresas} empresa(s)</button>` : "—"}</td></tr>
        ${p.n ? `<tr class="oculto" data-precos-linha="${k}"><td colspan="8"><ul class="exemplos-conc">${p.empresas.map((e) => `<li><b>${esc(e.nome || fmt.cnpj(e.cnpj))}</b>: média ${fmt.moeda(e.media)} · menor ${fmt.moeda(e.minimo)} <small class="fraco">(${e.n} preço(s))</small></li>`).join("")}</ul>
          ${(p.exemplos || []).length ? `<small class="fraco">Exemplos: ${p.exemplos.map((x) => `${esc((x.descricao || "").slice(0, 70))} — ${fmt.moeda(x.valor_unitario)}/${esc(x.unidade || "un")} (${esc(x.nome || "")}${x.orgao ? ", " + esc(x.orgao) : ""}${x.data ? ", " + fmt.data(x.data) : ""})`).join(" · ")}</small>` : ""}</td></tr>` : ""}`).join("")}</tbody></table></div>
      <p class="fraco"><small>Esses preços entram automaticamente como referência na proposta comercial deste edital (botão <b>Precificar pelo edital</b>).</small></p>`
      : `<p class="fraco">Não encontramos preços homologados de itens parecidos nas contratações anteriores.</p>`}`;
}

const RELEVANCIA_CONC = { alta: ["Alta", "aviso"], media: ["Média", "oficio"], baixa: ["Baixa", "neutro"] };

function desenharPossiveis(el, ed) {
  if (!el) return;
  const pc = ed.possiveis_concorrentes;
  const buscando = pc?.status === "buscando";
  const itens = pc?.itens || [];
  const pl = S.plano || {}, lim = pl.possiveis, usados = pl.uso?.possiveis ?? 0;
  const esgotado = !lim || usados >= lim;
  const cota = lim ? `${usados} de ${lim} ${lim === 1 ? "avaliação usada" : "avaliações usadas"} neste mês` : "Não incluído no seu plano";
  const cab = `<div class="bloco-titulo"><h2>Possíveis concorrentes</h2>
      <div class="acoes nao-imprimir">${itens.length ? carimbo(`${itens.length} empresa(s)`, "neutro") : ""}
        <button class="botao pequeno ${pc ? "secundario" : ""}" id="buscar-possiveis" ${buscando || !ed.objeto ? "disabled" : ""}>${buscando ? "Avaliando…" : pc ? "Avaliar novamente" : "Avaliar possíveis concorrentes"}</button></div></div>
    <p class="fraco nao-imprimir" style="margin:-4px 0 8px"><small>${esc(cota)}${esgotado && lim !== undefined ? ` · <a href="#/conta">Ver planos</a>` : ""}</small></p>
    <p class="fraco">Empresas que venceram contratações com objeto parecido no PNCP (contratos e atas de registro de preços),
      ordenadas por quantas vezes venceram, semelhança do objeto, mesma UF, mesmo órgão e data. É um indicativo de quem costuma disputar esse objeto.</p>`;
  let corpo;
  if (buscando) corpo = `<div class="andamento-analise"><span class="carregando">Consultando atas e contratos anteriores no PNCP… isso leva até 2 minutos.</span></div>`;
  else if (!pc) corpo = `<p class="fraco">${ed.objeto ? "Clique em <b>Avaliar possíveis concorrentes</b> para consultar no PNCP quem venceu contratações com objeto parecido. Cada avaliação conta no limite mensal do seu plano." : "Analise o edital (ou preencha o objeto) para avaliar os possíveis concorrentes."}</p>`;
  else if (!itens.length) corpo = `<div class="aviso ${pc.status === "erro" ? "erro" : "info"}">${esc(pc.erro || pc.aviso || "Nenhuma empresa encontrada.")}</div>`;
  else corpo = `${pc.status === "erro" ? `<div class="aviso erro">${esc(pc.erro)}</div>` : ""}
    <div class="tabela-rolagem"><table class="tabela-possiveis"><thead><tr><th>Empresa</th><th>Relevância</th><th>Vitórias</th><th>Valor contratado</th><th>Preço nos itens do edital</th><th>Onde atua</th><th>Última</th><th class="nao-imprimir"></th></tr></thead>
    <tbody>${itens.map((c, i) => `<tr>
      <td><b>${esc(c.nome)}</b><br><small class="fraco">${fmt.cnpj(c.cnpj)}</small>
        ${c.mesmo_orgao ? `<br><small class="etiqueta-conc">já venceu neste órgão</small>` : c.mesma_uf ? `<br><small class="etiqueta-conc">atua em ${esc(ed.uf)}</small>` : ""}</td>
      <td>${carimboStatus(RELEVANCIA_CONC, c.relevancia)}</td>
      <td>${c.vitorias}<br><small class="fraco">${[c.contratos ? `${c.contratos} contrato(s)` : "", c.atas ? `${c.atas} ata(s)` : ""].filter(Boolean).join(" · ")}</small></td>
      <td>${c.valor_total ? fmt.moeda(c.valor_total) : "—"}</td>
      <td>${(c.precos || []).length ? `${c.pct_medio_estimado ? `<b>${fmt.num(c.pct_medio_estimado, 0)}%</b> do estimado<br>` : ""}<small class="fraco">em ${c.precos.length} item(ns)</small>` : '<small class="fraco">—</small>'}</td>
      <td><small>${esc((c.ufs || []).join(", ") || "—")}${c.orgaos?.length ? `<br><span class="fraco">${esc(c.orgaos.join("; ")).slice(0, 160)}</span>` : ""}</small></td>
      <td style="white-space:nowrap">${c.ultima_data ? fmt.data(c.ultima_data) : "—"}</td>
      <td class="nao-imprimir"><div class="acoes-conc">
        <button class="botao pequeno texto" data-exemplos="${i}" aria-expanded="false">Contratações</button>
        ${c.concorrente_id ? `<a class="botao pequeno secundario" href="#/concorrentes/${c.concorrente_id}">Ver dossiê</a>`
          : `<button class="botao pequeno secundario" data-dossie="${esc(c.cnpj)}">Montar dossiê</button>`}
        <button class="botao pequeno texto" data-analisar-doc="${esc(c.cnpj)}">Analisar documento</button></div></td></tr>
      <tr class="oculto" data-exemplos-linha="${i}"><td colspan="8">
        ${(c.precos || []).length ? `<p style="margin:4px 0 6px"><b>Preço unitário médio praticado por esta empresa</b></p><ul class="exemplos-conc">${c.precos.map((x) => `<li>Item ${esc(x.numero || "—")} · ${esc((x.descricao || "").slice(0, 90))}: <b>${fmt.moeda(x.media)}</b>${x.pct_estimado ? ` (${fmt.num(x.pct_estimado, 0)}% do estimado)` : ""} <small class="fraco">${x.n} preço(s)</small></li>`).join("")}</ul>` : ""}<ul class="exemplos-conc">${(c.exemplos || []).map((x) => `<li>
        <b>${x.tipo === "ata" ? "Ata/registro de preços" : "Contrato"}</b> · ${esc(x.orgao || "—")}${x.uf ? "/" + esc(x.uf) : ""} · ${x.data ? fmt.data(x.data) : "—"}${x.valor ? " · " + fmt.moeda(x.valor) : ""}
        <br><span class="fraco">${esc(x.objeto || "")}</span>${x.link ? ` <a href="${esc(x.link)}" target="_blank" rel="noopener">Ver no PNCP</a>` : ""}</li>`).join("")}</ul></td></tr>`).join("")}</tbody></table></div>
    ${blocoPrecosItens(pc)}
    <p class="fraco" style="margin-top:10px"><small>Termos pesquisados: ${esc((pc.termos || []).join(" · "))} · ${pc.documentos_analisados || 0} contratação(ões) conferida(s) · consultado em ${fmt.dataHora(pc.consultado_em + "Z")}</small></p>`;
  el.innerHTML = `<section class="bloco">${cab}${corpo}</section>`;

  const b = $("#buscar-possiveis", el);
  if (b) b.onclick = async () => {
    if (esgotado) {
      toast(lim ? `Você já usou ${lim === 1 ? "a avaliação" : `as ${lim} avaliações`} de possíveis concorrentes deste mês. Faça upgrade ou aguarde a renovação.` : "Seu plano não inclui a avaliação de possíveis concorrentes.", "erro");
      return;
    }
    if (pc && !(await confirmar(`Avaliar novamente usa 1 das ${lim} avaliações do mês (${usados} já usada(s)). Continuar?`, "Avaliar"))) return;
    try { ed.possiveis_concorrentes = await api("POST", `/api/editais/${ed.id}/possiveis-concorrentes`); desenharPossiveis(el, ed); }
    catch (e) { avisarErro(e); }
  };
  $$("[data-precos-item]", el).forEach((x) => x.onclick = () => {
    const linha = $(`[data-precos-linha="${x.dataset.precosItem}"]`, el);
    x.setAttribute("aria-expanded", String(linha.classList.toggle("oculto") === false));
  });
  $$("[data-exemplos]", el).forEach((x) => x.onclick = () => {
    const linha = $(`[data-exemplos-linha="${x.dataset.exemplos}"]`, el);
    const abrir = linha.classList.toggle("oculto") === false;
    x.setAttribute("aria-expanded", String(abrir));
  });
  $$("[data-dossie]", el).forEach((x) => x.onclick = () => ocupado(x, "Criando…", async () => {
    try { const c = await api("POST", "/api/concorrentes", { cnpj: x.dataset.dossie }); location.hash = `#/concorrentes/${c.id}`; }
    catch (e) { avisarErro(e); }
  }));
  $$("[data-analisar-doc]", el).forEach((x) => x.onclick = () => {
    sessionStorage.setItem("cnpj_concorrente_" + ed.id, x.dataset.analisarDoc);
    sessionStorage.setItem("edital_aba_" + ed.id, "concorrentes");
    V.edital($("#conteudo"), ed.id);
  });
  if (buscando) {
    clearTimeout(desenharPossiveis.t);
    desenharPossiveis.t = setTimeout(async () => {
      if (!document.body.contains(el)) return;
      try {
        const d = await api("GET", `/api/editais/${ed.id}`); ed.possiveis_concorrentes = d.edital.possiveis_concorrentes;
        if (ed.possiveis_concorrentes?.status !== "buscando") await atualizarConta();
      } catch { /* tenta de novo */ }
      if (document.body.contains(el)) desenharPossiveis(el, ed);
    }, 4000);
  }
}
