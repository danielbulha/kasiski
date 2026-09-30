// Relatórios executivos, Arquivo de licitações, Lixeira, documentos da licitação (atas → peças) e painel da carteira de contratos.
const relPct = (v) => (v === null || v === undefined ? "—" : `${v}%`);
const relQtd = (v) => Number(v || 0).toLocaleString("pt-BR");
const mesCurto = (k) => { const [a, m] = k.split("-"); return `${["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"][Number(m) - 1]}/${a.slice(2)}`; };
const moedaK = (v) => (typeof moedaCurta === "function" ? moedaCurta(v) : fmt.moeda(v));

// ---------------------------------------------------------------- Relatórios (alta administração)
V.relatorios = async (el) => {
  const f = V.relatorios.f || (V.relatorios.f = { empresa: S.empresas.length > 1 ? "todas" : String(S.empresaId || "todas"), meses: 12 });
  el.innerHTML = `<p class="carregando">Montando o relatório…</p>`;
  const r = await api("GET", `/api/relatorios/executivo?empresa=${f.empresa}&meses=${f.meses}`);
  const k = r.kpis, ct = r.contratos;
  const nomeEscopo = f.empresa === "todas" ? (S.empresas.length > 1 ? `${S.empresas.length} empresas` : esc(S.empresas[0]?.razao_social || "")) : esc(S.empresas.find((e) => String(e.id) === f.empresa)?.razao_social || "");
  el.innerHTML = `
    <div class="cabecalho"><div><h1>Relatórios</h1><p>Visão geral para a alta administração · ${nomeEscopo} · últimos ${r.periodo.meses} meses · gerado em ${fmt.dataHora(r.gerado_em + "Z")}</p></div>
      <div class="acoes nao-imprimir">
        ${S.empresas.length > 1 ? `<select id="rel-emp" aria-label="Empresa"><option value="todas" ${f.empresa === "todas" ? "selected" : ""}>Todas as empresas</option>${S.empresas.map((e) => `<option value="${e.id}" ${String(e.id) === f.empresa ? "selected" : ""}>${esc(e.razao_social)}</option>`).join("")}</select>` : ""}
        <select id="rel-meses" aria-label="Período">${[6, 12, 24].map((m) => `<option value="${m}" ${f.meses === m ? "selected" : ""}>Últimos ${m} meses</option>`).join("")}</select>
        <button class="botao secundario" id="rel-imprimir">${icone("imprimir")} Imprimir / PDF</button></div></div>
    <h2 class="rel-sec">Licitações</h2>
    <div class="kpis">
      ${kpi("Oportunidades ativas", relQtd(k.ativas), `${moedaK(k.valor_pipeline)} em valor estimado`)}
      ${kpi("Em disputa agora", relQtd(k.em_disputa), "sessão, julgamento ou recurso")}
      ${kpi("Taxa de sucesso", relPct(k.taxa_sucesso), `${k.vitorias} vitória(s) · ${k.perdas} perda(s)`, k.taxa_sucesso === null ? "" : k.taxa_sucesso >= 30 ? "bom" : "atencao")}
      ${kpi("Valor ganho", moedaK(k.valor_ganho), "estimado das licitações vencidas")}
      ${kpi("Decisões Go / No-Go", `${k.go} / ${k.no_go}`, `${k.desistencias} desistência(s)`)}
    </div>
    <div class="grade-graficos">
      <section class="bloco">${graficoColunas({ titulo: "Novas oportunidades por mês", dados: r.serie.map((s) => ({ rotulo: mesCurto(s.mes), novas: s.novas })),
        series: [{ chave: "novas", nome: "Novas oportunidades" }], formato: relQtd, legendaTabela: "Mês" })}</section>
      <section class="bloco">${graficoColunas({ titulo: "Vitórias e perdas por mês", dados: r.serie.map((s) => ({ rotulo: mesCurto(s.mes), vitorias: s.vitorias, perdas: s.perdas })),
        series: [{ chave: "vitorias", nome: "Vitórias" }, { chave: "perdas", nome: "Perdas" }], formato: relQtd, legendaTabela: "Mês" })}</section>
    </div>
    <div class="grade-graficos">
      <section class="bloco">${graficoBarras({ titulo: "Funil: licitações por etapa", itens: r.funil.filter((x) => x.qtd).map((x) => ({ rotulo: x.nome, valor: x.qtd, detalhe: moedaK(x.valor) })), formato: relQtd })}</section>
      <section class="bloco">${graficoBarras({ titulo: "Órgãos com mais participações", itens: r.orgaos.map((x) => ({ rotulo: x.orgao, valor: x.qtd, detalhe: "participações" })), formato: relQtd })}
        <h3 class="rel-sub">Principais motivos de perda e desistência</h3>
        ${r.motivos_perda.length ? `<ul class="rel-lista">${r.motivos_perda.map((m) => `<li><b>${m.qtd}×</b> ${esc(m.motivo)}</li>`).join("")}</ul>` : `<p class="fraco">Nenhum motivo registrado.</p>`}</section>
    </div>
    <h2 class="rel-sec">Contratos</h2>
    <div class="kpis">
      ${kpi("Contratos ativos", relQtd(ct.ativos), `${ct.encerrados} encerrado(s)`)}
      ${kpi("Carteira ativa", moedaK(ct.valor_carteira), `${moedaK(ct.receita_mensal)} por mês (estimado)`)}
      ${kpi("Vencem em 90 dias", relQtd(ct.vencendo["90"]), `${ct.vencendo["30"]} em 30 dias`, ct.vencendo["30"] ? "atencao" : "")}
      ${kpi("Pagamentos em atraso", fmt.moeda(ct.pagamentos.atrasado), ct.pagamentos.qtd_atrasados ? `${ct.pagamentos.qtd_atrasados} fatura(s) · maior atraso ${ct.pagamentos.maior_atraso_dias} dias` : "nenhum", ct.pagamentos.atrasado ? "alerta" : "bom")}
      ${kpi("Recebido em 12 meses", fmt.moeda(ct.pagamentos.recebido_12m), `${fmt.moeda(ct.pagamentos.a_receber)} a receber`)}
    </div>
    <div class="grade-graficos">
      <section class="bloco"><h3 class="rel-sub">Próximos 15 dias</h3>
        ${r.prazos.length ? `<ul class="rel-lista">${r.prazos.map((p) => `<li><b>${fmt.dataHora(p.data)}</b> — ${esc(p.titulo)}${f.empresa === "todas" && S.empresas.length > 1 ? ` <small class="fraco">(${esc(p.empresa || "")})</small>` : ""}</li>`).join("")}</ul>` : `<p class="fraco">Nenhum prazo nos próximos 15 dias.</p>`}</section>
      <section class="bloco"><h3 class="rel-sub">Produtividade no período</h3>
        <div class="kpis kpis-compactos">${kpi("Análises de edital", relQtd(r.produtividade.analises))}${kpi("Peças geradas", relQtd(r.produtividade.pecas))}${kpi("Propostas", relQtd(r.produtividade.propostas))}</div></section>
    </div>
    ${r.por_empresa.length > 1 ? `<section class="bloco"><h2>Por empresa</h2><div class="tabela-rolagem"><table class="tabela-faixas"><thead><tr><th>Empresa</th><th>Ativas</th><th>Pipeline</th><th>Vitórias</th><th>Perdas</th><th>Taxa</th><th>Contratos</th><th>Carteira</th><th>Em atraso</th></tr></thead>
      <tbody>${r.por_empresa.map((e) => `<tr><td>${esc(e.nome)}</td><td>${e.ativas}</td><td>${moedaK(e.valor_pipeline)}</td><td>${e.vitorias}</td><td>${e.perdas}</td><td>${relPct(e.taxa)}</td><td>${e.contratos_ativos}</td><td>${moedaK(e.carteira)}</td><td>${e.atrasado ? fmt.moeda(e.atrasado) : "—"}</td></tr>`).join("")}</tbody></table></div></section>` : ""}
    <p class="fraco rel-nota">Taxa de sucesso = vitórias ÷ (vitórias + perdas). Valores são os estimados dos editais; a receita mensal dos contratos usa o valor mensal lido do contrato ou o valor total dividido pela vigência.</p>`;
  ligarDicas(el);
  const emp = $("#rel-emp", el); if (emp) emp.onchange = (ev) => { f.empresa = ev.target.value; V.relatorios(el); };
  $("#rel-meses", el).onchange = (ev) => { f.meses = Number(ev.target.value); V.relatorios(el); };
  $("#rel-imprimir", el).onclick = () => { $$(".g-tabela", el).forEach((d) => { d.open = true; }); window.print(); };
};

// ---------------------------------------------------------------- Arquivo de licitações encerradas
V.arquivo = async (el) => {
  if (!S.empresaId) { el.innerHTML = exigirEmpresa(); return; }
  const q = V.arquivo.q || "";
  const lista = await api("GET", `/api/empresas/${S.empresaId}/arquivo${q ? `?q=${encodeURIComponent(q)}` : ""}`);
  const nomes = ETAPA_NOMES_OP;
  el.innerHTML = `
    <div class="cabecalho"><div><h1>Arquivo de licitações</h1><p>Licitações encerradas de ${esc(empresaAtual().razao_social)}, com todos os documentos reunidos</p></div>
      <div class="acoes"><input type="search" id="arq-q" placeholder="Buscar por órgão, objeto ou número" value="${esc(q)}" aria-label="Buscar no arquivo"></div></div>
    ${guia(`<p>Quando uma licitação termina (<b>perdida</b>, <b>desistência</b> ou <b>contrato ativo</b>), ela vem para o Arquivo com tudo o que foi reunido:
      edital, anexos, atas, análises, peças, propostas e contrato. O cartão ainda fica ${15} dias no quadro de Oportunidades e depois sai de lá.
      Você pode baixar a pasta completa em ZIP ou reabrir a licitação.</p>`)}
    <section class="bloco">${lista.length ? `<div class="tabela-rolagem"><table class="tabela-faixas"><thead><tr><th>Licitação</th><th>Órgão</th><th>Resultado</th><th>Arquivada em</th><th>Conteúdo</th><th></th></tr></thead>
      <tbody>${lista.map((e) => `<tr class="faixa-${e.etapa === "contrato_ativo" ? "ganho" : e.etapa === "perdida" ? "perdido" : "descartado"}">
        <td style="max-width:320px"><b>${esc(e.numero || e.numero_controle || "Sem número")}</b><br><small>${esc((e.objeto || "").slice(0, 140))}</small></td>
        <td>${esc(e.orgao || "—")}</td><td>${carimbo(nomes[e.etapa] || e.etapa || "—", e.etapa === "contrato_ativo" ? "ok" : e.etapa === "perdida" ? "erro" : "neutro")}</td>
        <td>${fmt.data(e.arquivado_em)}</td>
        <td><small>${e.qtd_documentos} documento(s) · ${e.qtd_pecas} peça(s) · ${e.qtd_propostas} proposta(s)${e.contrato ? " · contrato" : ""}</small></td>
        <td class="acoes-celula"><button class="botao pequeno secundario" data-dossie="${e.id}">Abrir</button>
          <button class="botao pequeno texto" data-zip="${e.id}">${icone("baixar", 14)} ZIP</button></td></tr>`).join("")}</tbody></table></div>`
      : vazio("Nada arquivado ainda", "As licitações encerradas aparecem aqui automaticamente.")}</section>`;
  let t; $("#arq-q", el).oninput = (ev) => { clearTimeout(t); t = setTimeout(() => { V.arquivo.q = ev.target.value; V.arquivo(el); }, 350); };
  $$("[data-zip]", el).forEach((b) => b.onclick = () => baixarDossie(b.dataset.zip, b));
  $$("[data-dossie]", el).forEach((b) => b.onclick = () => abrirDossie(Number(b.dataset.dossie), () => V.arquivo(el)));
};

async function baixarDossie(id, botao) {
  await ocupado(botao, "Gerando…", async () => {
    try {
      const resp = await api("GET", `/api/editais/${id}/dossie.zip`);
      const url = URL.createObjectURL(await resp.blob());
      const a = document.createElement("a"); a.href = url; a.download = `licitacao-${id}.zip`; a.click();
      setTimeout(() => URL.revokeObjectURL(url), 3000);
    } catch (e) { avisarErro(e); }
  });
}

async function abrirDossie(id, depois) {
  const d = await api("GET", `/api/editais/${id}/dossie`);
  const ed = d.edital;
  const m = modal({ titulo: `Licitação ${ed.numero || ed.numero_controle || ed.id}`, largo: true, corpo: `
    <p><b>${esc(ed.orgao || "")}</b><br>${esc(ed.objeto || "")}</p>
    <p class="fraco">Resultado: ${esc(ETAPA_NOMES_OP[ed.etapa] || ed.etapa || "—")}${ed.motivo_saida ? ` — ${esc(ed.motivo_saida)}` : ""} · arquivada em ${fmt.data(ed.arquivado_em)}</p>
    <h3>Documentos</h3>${ed.tem_documento ? `<p><button class="botao pequeno texto" data-ver-edital>${icone("olho", 14)} Edital</button></p>` : ""}
    ${d.documentos.length ? `<ul class="rel-lista">${d.documentos.map((x) => `<li><b>${esc(ROTULO_DOC_LIC[x.tipo] || x.tipo)}</b> — ${esc(x.titulo || x.nome_arquivo || "")} ${x.tem_arquivo ? `<button class="botao pequeno texto" data-abrir-doc="${x.id}">abrir</button>` : ""}</li>`).join("")}</ul>` : `<p class="fraco">Nenhum documento enviado.</p>`}
    <h3>Peças</h3>${d.pecas.length ? `<ul class="rel-lista">${d.pecas.map((p) => `<li><a href="#/pecas/${p.id}" data-fechar>${esc(p.titulo || "Peça " + p.id)}</a></li>`).join("")}</ul>` : `<p class="fraco">Nenhuma peça.</p>`}
    ${d.contratos.length ? `<h3>Contrato</h3><ul class="rel-lista">${d.contratos.map((k) => `<li><a href="#/contratos/${k.id}" data-fechar>Contrato ${esc(k.numero || k.id)}</a>${k.valor ? " · " + fmt.moeda(k.valor) : ""}</li>`).join("")}</ul>` : ""}
    <h3>Linha do tempo</h3>${d.movimentos.length ? `<ol class="op-linha-tempo">${d.movimentos.map((x) => `<li class="${x.autor === "Kasiski" ? "automatico" : ""}"><small>${fmt.dataHora(x.criado_em + "Z")} · ${esc(x.autor || "")}</small><div>${esc(ETAPA_NOMES_OP[x.para] || x.para)}</div>${x.motivo ? `<div class="fraco">${esc(x.motivo)}</div>` : ""}</li>`).join("")}</ol>` : `<p class="fraco">Sem movimentações.</p>`}`,
    acoes: `<button class="botao secundario" data-reabrir>Reabrir licitação</button><button class="botao" data-zip-m>${icone("baixar", 15)} Baixar pasta (ZIP)</button>` });
  const ve = $("[data-ver-edital]", m); if (ve) ve.onclick = () => abrirDocumentoEdital(ed.id, ve);
  $$("[data-abrir-doc]", m).forEach((b) => b.onclick = () => abrirArquivoApi(`/api/documentos-licitacao/${b.dataset.abrirDoc}/arquivo`, b));
  $("[data-zip-m]", m).onclick = (ev) => baixarDossie(ed.id, ev.currentTarget);
  $("[data-reabrir]", m).onclick = async () => {
    try { await api("POST", `/api/editais/${ed.id}/reabrir`); m.fechar(); toast("Licitação reaberta: ela volta ao quadro de Oportunidades.", "ok"); if (depois) depois(); } catch (e) { avisarErro(e); }
  };
}

// Abre um arquivo protegido (precisa do token) numa aba nova
async function abrirArquivoApi(url, botao) {
  const janela = window.open("", "_blank");
  const tarefa = async () => {
    try {
      const resp = await api("GET", url);
      const blob = await resp.blob();
      const link = URL.createObjectURL(blob);
      if (janela) janela.location.href = link; else window.open(link, "_blank");
      setTimeout(() => URL.revokeObjectURL(link), 60000);
    } catch (e) { if (janela) janela.close(); avisarErro(e); }
  };
  if (botao) await ocupado(botao, "Abrindo…", tarefa); else await tarefa();
}

// ---------------------------------------------------------------- Lixeira
V.lixeira = async (el) => {
  const r = await api("GET", "/api/lixeira");
  el.innerHTML = `
    <div class="cabecalho"><div><h1>Lixeira</h1><p>Itens excluídos ficam aqui por ${r.dias} dias e depois são apagados de vez, com os arquivos</p></div>
      <div class="acoes">${r.itens.length ? `<button class="botao secundario perigo-texto" id="esvaziar">${icone("lixeira", 15)} Esvaziar lixeira</button>` : ""}</div></div>
    <section class="bloco">${r.itens.length ? `<div class="tabela-rolagem"><table><thead><tr><th>Item</th><th>Tipo</th><th>Excluído em</th><th>Apagado de vez em</th><th></th></tr></thead>
      <tbody>${r.itens.map((i) => `<tr><td style="max-width:380px">${esc(i.titulo)}${i.arrasta ? `<br><small class="fraco">+ ${i.arrasta} item(ns) ligado(s) (prazos, peças, documentos…)</small>` : ""}</td>
        <td>${esc(i.rotulo)}</td><td>${fmt.data(i.excluido_em)}<br><small class="fraco">${esc(i.excluido_por || "")}</small></td>
        <td>${fmt.data(i.apaga_em)} <small class="fraco">(${fmt.prazo ? fmt.prazo(i.apaga_em) : ""})</small></td>
        <td class="acoes-celula"><button class="botao pequeno" data-restaurar="${i.tipo}:${i.id}">${icone("restaurar", 14)} Restaurar</button>
          <button class="botao pequeno texto" data-apagar="${i.tipo}:${i.id}">Apagar de vez</button></td></tr>`).join("")}</tbody></table></div>`
      : vazio("A lixeira está vazia", "Tudo o que você excluir fica aqui por 30 dias, para restaurar se precisar.")}</section>
    <p class="fraco">Os arquivos na lixeira ainda contam no armazenamento do plano. Esvazie para liberar espaço.</p>`;
  $$("[data-restaurar]", el).forEach((b) => b.onclick = async () => {
    const [t, id] = b.dataset.restaurar.split(":");
    try { await api("POST", `/api/lixeira/${t}/${id}/restaurar`); toast("Restaurado.", "ok"); V.lixeira(el); } catch (e) { avisarErro(e); }
  });
  $$("[data-apagar]", el).forEach((b) => b.onclick = async () => {
    const [t, id] = b.dataset.apagar.split(":");
    if (!(await confirmar("Apagar de vez? Não será possível recuperar este item nem os arquivos dele.", "Apagar de vez"))) return;
    try { await api("DELETE", `/api/lixeira/${t}/${id}`); toast("Apagado.", "ok"); V.lixeira(el); } catch (e) { avisarErro(e); }
  });
  const esv = $("#esvaziar", el);
  if (esv) esv.onclick = async () => {
    if (!(await confirmar(`Apagar de vez os ${r.itens.length} item(ns) da lixeira? Não há como desfazer.`, "Esvaziar"))) return;
    try { const x = await api("DELETE", "/api/lixeira"); toast(`${x.apagados} item(ns) apagado(s).`, "ok"); V.lixeira(el); } catch (e) { avisarErro(e); }
  };
};

// ---------------------------------------------------------------- documentos da licitação (atas → sugestão de peças)
const ROTULO_DOC_LIC = { ata_sessao: "Ata da sessão", ata_julgamento: "Ata de julgamento / habilitação", decisao: "Decisão / resultado",
  recurso: "Recurso ou contrarrazões (de terceiros)", proposta: "Proposta enviada", habilitacao: "Documentos de habilitação enviados", anexo: "Anexo do edital",
  esclarecimento: "Resposta a esclarecimento / impugnação", homologacao: "Adjudicação / homologação", contrato: "Contrato / ata de registro de preços", outro: "Outro" };
const DOC_ANALISAVEIS = ["ata_sessao", "ata_julgamento", "decisao", "recurso", "homologacao"];
const NOME_PECA = { intencao_recurso: "Intenção de recorrer", recurso: "Recurso", contrarrazoes: "Contrarrazões" };
const SITUACAO_EMPRESA = { vencedora: ["Vencedora", "ok"], classificada: ["Classificada", "neutro"], desclassificada: ["Desclassificada", "erro"],
  inabilitada: ["Inabilitada", "erro"], nao_participou: ["Não participou", "neutro"], nao_identificada: ["Não identificada na ata", "neutro"] };

async function painelDocumentosEdital(el, ed) {
  const docs = await api("GET", `/api/editais/${ed.id}/documentos`);
  const arm = S.plano?.armazenamento;
  el.innerHTML = `
    <form class="bloco form-doc-lic" id="form-doc-lic">
      <h3>Enviar documento da licitação</h3>
      <p class="fraco">Guarde aqui atas, decisões, anexos, propostas e recursos. <b>Atas e decisões são analisadas pela IA</b>, que resume o resultado, calcula o prazo de recurso e sugere as peças cabíveis (intenção de recorrer, recurso ou contrarrazões).</p>
      <div class="linha-campos">
        <div class="campo"><label for="dl-tipo">Tipo</label><select id="dl-tipo" name="tipo">${Object.entries(ROTULO_DOC_LIC).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("")}</select></div>
        <div class="campo"><label for="dl-titulo">Descrição <small class="fraco">(opcional)</small></label><input id="dl-titulo" name="titulo" maxlength="300" placeholder="Ex.: Ata da sessão de 12/10"></div>
        <div class="campo"><label for="dl-arq">Arquivo (PDF, DOCX, TXT ou imagem)</label><input id="dl-arq" name="arquivo" type="file" accept=".pdf,.docx,.doc,.txt,.png,.jpg,.jpeg" required></div>
      </div>
      <button class="botao" type="submit">${icone("upload", 15)} Enviar</button>
      ${arm ? `<small class="fraco" style="margin-left:10px">Armazenamento do plano: ${tamanhoArquivo(arm.usado)} de ${tamanhoArquivo(arm.limite)}</small>` : ""}
    </form>
    <div id="lista-doc-lic">${docs.length ? docs.map(cartaoDocLic).join("") : vazio("Nenhum documento ainda", "Envie a ata da sessão assim que ela for publicada.")}</div>`;
  $("#form-doc-lic", el).onsubmit = async (ev) => {
    ev.preventDefault();
    const b = ev.target.querySelector("button[type=submit]");
    await ocupado(b, "Enviando…", async () => {
      try {
        const r = await api("POST", `/api/editais/${ed.id}/documentos`, new FormData(ev.target));
        toast(r.aviso || (r.analise_status === "processando" ? "Documento guardado. A IA está lendo a ata…" : "Documento guardado."), r.aviso ? "erro" : "ok");
        await atualizarConta();
        painelDocumentosEdital(el, ed);
      } catch (e) { avisarErro(e); }
    });
  };
  ligarDocsLic(el, ed, docs);
}

function cartaoDocLic(d) {
  const a = d.analise || {};
  const nossa = a.nossa_empresa || {};
  const sit = SITUACAO_EMPRESA[nossa.situacao];
  let analise = "";
  if (d.analise_status === "processando") analise = `<p class="carregando">A IA está lendo o documento…</p>`;
  else if (d.analise_status === "erro") analise = `<div class="aviso erro">${esc(d.analise_erro || "Falha na análise.")}</div>`;
  else if (d.analise_status === "concluida") analise = `
    <div class="doc-analise">
      <p>${esc(a.resumo || "")}</p>
      <p class="fraco">${sit ? `Sua empresa: ${carimbo(sit[0], sit[1])}${nossa.posicao ? ` (${nossa.posicao}º lugar)` : ""}${nossa.motivo ? ` — ${esc(nossa.motivo)}` : ""} · ` : ""}
        ${a.vencedor?.nome ? `Vencedor: <b>${esc(a.vencedor.nome)}</b>${a.vencedor.valor ? ` · ${fmt.moeda(a.vencedor.valor)}` : ""}` : ""}${a.data_ata ? ` · Ata de ${fmt.data(a.data_ata)}` : ""}</p>
      ${(a.intencoes_recurso || []).length ? `<p><b>Intenções de recurso registradas:</b> ${a.intencoes_recurso.map((x) => `${esc(x.empresa)}${x.contra ? ` contra ${esc(x.contra)}` : ""}${x.motivo ? ` (${esc(x.motivo)})` : ""}`).join("; ")}</p>` : ""}
      ${(a.sugestoes_peca || []).length ? `<h4>Peças sugeridas</h4>${a.sugestoes_peca.map((s) => `
        <div class="sug-peca">
          <div><b>${esc(NOME_PECA[s.peca] || s.peca)}: ${esc(s.tema || "")}</b> ${carimbo(ROTULOS.forca[s.forca]?.[0] || s.forca || "", ROTULOS.forca[s.forca]?.[1] || "neutro")}
            ${s.verificacao ? dcSelo(s.verificacao, { titulo: `${NOME_PECA[s.peca] || s.peca}: ${s.tema || ""}`, texto: s.descricao || "", pagina: s.pagina }, { compacto: true }) : ""}
            <p class="fraco">${esc(s.descricao || "")}${s.fundamento ? ` <i>${esc(s.fundamento)}</i>` : ""}${s.pagina ? ` · ${esc(s.pagina)}` : ""}${s.prazo ? ` · Prazo: ${esc(s.prazo)}` : ""}</p></div>
          <button class="botao pequeno" data-gerar-sug="${d.id}:${s.id}">Gerar ${esc((NOME_PECA[s.peca] || "peça").toLowerCase())}</button></div>`).join("")}`
        : `<p class="fraco">Nenhuma peça sugerida com base nesta ata.</p>`}
    </div>`;
  return `<article class="bloco doc-lic" data-doc-lic="${d.id}">
    <div class="doc-lic-topo"><div><b>${esc(ROTULO_DOC_LIC[d.tipo] || d.tipo)}</b> — ${esc(d.titulo || d.nome_arquivo || "")}
      <br><small class="fraco">${fmt.dataHora(d.criado_em + "Z")}${d.enviado_por ? ` · ${esc(d.enviado_por)}` : ""}${d.tamanho ? ` · ${Math.max(1, Math.round(d.tamanho / 1024)).toLocaleString("pt-BR")} KB` : ""}</small></div>
      <div class="acoes">${d.tem_arquivo ? `<button class="botao pequeno texto" data-abrir-doc="${d.id}">${icone("olho", 14)} Abrir</button>` : ""}
        ${DOC_ANALISAVEIS.includes(d.tipo) && d.tem_texto && d.analise_status !== "processando" ? `<button class="botao pequeno secundario" data-analisar-doc="${d.id}">${d.analise_status === "concluida" ? "Analisar de novo" : "Analisar com IA"}</button>` : ""}
        <button class="botao pequeno texto" data-excluir-doc-lic="${d.id}" aria-label="Excluir documento">${icone("excluir", 14)} Excluir</button></div></div>
    ${!d.tem_texto && DOC_ANALISAVEIS.includes(d.tipo) ? `<p class="fraco">Sem texto selecionável (imagem ou PDF escaneado): o documento fica guardado, mas a IA não consegue ler.</p>` : ""}
    ${analise}</article>`;
}

function ligarDocsLic(el, ed, docs) {
  const recarregar = () => painelDocumentosEdital(el, ed);
  $$("[data-abrir-doc]", el).forEach((b) => b.onclick = () => abrirArquivoApi(`/api/documentos-licitacao/${b.dataset.abrirDoc}/arquivo`, b));
  $$("[data-excluir-doc-lic]", el).forEach((b) => b.onclick = () => excluirParaLixeira({ url: `/api/documentos-licitacao/${b.dataset.excluirDocLic}`, nome: "este documento", tipo: "doc_licitacao", depois: recarregar }));
  $$("[data-analisar-doc]", el).forEach((b) => b.onclick = () => ocupado(b, "Enviando…", async () => {
    try { await api("POST", `/api/documentos-licitacao/${b.dataset.analisarDoc}/analisar`); recarregar(); } catch (e) { avisarErro(e); }
  }));
  $$("[data-gerar-sug]", el).forEach((b) => b.onclick = () => ocupado(b, "Redigindo a peça…", async () => {
    const [did, sid] = b.dataset.gerarSug.split(":");
    const d = docs.find((x) => String(x.id) === did);
    const s = (d.analise.sugestoes_peca || []).find((x) => x.id === sid);
    try {
      const p = await api("POST", `/api/empresas/${ed.empresa_id}/pecas`, { tipo: s.peca, edital_id: ed.id,
        pontos: [{ clausula: s.tema, descricao: s.descricao, fundamento: s.fundamento, pagina: s.pagina }],
        instrucoes: `Peça baseada na ${ROTULO_DOC_LIC[d.tipo] || "ata"}${d.analise.data_ata ? ` de ${fmt.data(d.analise.data_ata)}` : ""}. Resumo da ata: ${d.analise.resumo || ""}` });
      toast("Peça gerada. Revise antes de protocolar.", "ok");
      location.hash = `#/pecas/${p.id}`;
    } catch (e) { avisarErro(e); }
  }));
  if (docs.some((d) => d.analise_status === "processando")) {
    clearTimeout(ligarDocsLic.t);
    ligarDocsLic.t = setTimeout(() => { if (document.body.contains(el)) recarregar(); }, 4000);
  }
}

// ---------------------------------------------------------------- painel da carteira de contratos
function painelCarteira(p) {
  if (!p) return "";
  const venc = p.vencendo_lista.slice(0, 6);
  return `<section class="painel-contratos">
    <div class="kpis">
      ${kpi("Contratos ativos", relQtd(p.ativos), `${p.total} no total · ${p.encerrados} encerrado(s)`)}
      ${kpi("Carteira ativa", moedaK(p.valor_carteira), `${moedaK(p.receita_mensal)} por mês (estimado)`)}
      ${kpi("Vencem em 90 dias", relQtd(p.vencendo["90"]), `${p.vencendo["30"]} em 30 · ${p.vencendo["60"]} em 60 dias`, p.vencendo["30"] ? "alerta" : p.vencendo["90"] ? "atencao" : "")}
      ${kpi("Em atraso", fmt.moeda(p.pagamentos.atrasado), p.pagamentos.qtd_atrasados ? `${p.pagamentos.qtd_atrasados} fatura(s) · até ${p.pagamentos.maior_atraso_dias} dias` : "nenhuma fatura atrasada", p.pagamentos.atrasado ? "alerta" : "bom")}
      ${kpi("Recebido em 12 meses", fmt.moeda(p.pagamentos.recebido_12m), `${fmt.moeda(p.pagamentos.a_receber)} a receber`)}
      ${kpi("Reajustes e garantias", `${p.reajustes.length} / ${p.garantias.length}`, "reajustes · garantias nos próximos 60 dias", p.reajustes.length || p.garantias.length ? "atencao" : "")}
    </div>
    <div class="grade-graficos">
      <div class="bloco">${graficoBarras({ titulo: "Carteira ativa por órgão", itens: p.por_orgao.map((x) => ({ rotulo: x.orgao, valor: x.valor, detalhe: "valor dos contratos ativos" })), formato: moedaK, vazio: "Sem contratos ativos com valor." })}</div>
      <div class="bloco"><h3 class="rel-sub">Atenção nos próximos meses</h3>
        ${venc.length || p.reajustes.length || p.garantias.length ? `<ul class="rel-lista">
          ${venc.map((c) => `<li><a href="#/contratos/${c.id}">Contrato ${esc(c.numero || c.id)}</a> vence em <b>${c.dias} dia(s)</b> (${fmt.data(c.fim)}) · ${esc(c.orgao || "")}</li>`).join("")}
          ${p.reajustes.map((r) => `<li><a href="#/contratos/${r.id}">Contrato ${esc(r.numero || r.id)}</a>: reajuste (${esc(r.indice || "índice do contrato")}) em ${fmt.data(r.data)}</li>`).join("")}
          ${p.garantias.map((r) => `<li><a href="#/contratos/${r.id}">Contrato ${esc(r.numero || r.id)}</a>: garantia vence em ${fmt.data(r.data)}</li>`).join("")}</ul>`
          : `<p class="fraco">Nada vencendo, reajustando ou com garantia a renovar nos próximos meses.</p>`}</div>
    </div></section>`;
}
