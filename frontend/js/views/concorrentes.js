// Concorrentes: dossiê público + dossiê completo (atas e decisões no PNCP, acervo de documentos de outros
// certames e análises anteriores, consolidados pela IA em inabilitações, atestados, índices e pontos de ataque).
V.concorrentes = async (el) => {
  const lista = await api("GET", "/api/concorrentes");
  el.innerHTML = `
    <div class="cabecalho"><div><h1>Concorrentes</h1><p>Dossiês públicos consultados, de todos os editais.</p></div>
      <button class="botao" id="novo-dossie">${icone("buscar")} Consultar CNPJ</button></div>
    ${guia(`<p>O dossiê reúne dados públicos (Receita, sanções no TCU e na CGU, contratos no PNCP). No <b>dossiê completo</b>, o Kasiski
      também procura atas e decisões de julgamento no PNCP, lê os documentos que você juntar de outros certames (atas, habilitações,
      balanços, atestados) e as análises já feitas, e consolida inabilitações anteriores, atestados, índices e pontos de ataque.
      Esse histórico entra automaticamente nas próximas análises de habilitação e proposta do concorrente.</p>`)}
    <section class="bloco tabela-rolagem">
      ${lista.length ? `<table><thead><tr><th>Empresa</th><th>CNPJ</th><th>Situação</th><th>Sanções</th><th>Inabilitações conhecidas</th><th>Análises</th><th>Atualizado</th></tr></thead>
        <tbody>${lista.map(linhaConcorrente).join("")}</tbody></table>` : vazio("Nenhum concorrente pesquisado", "Consulte um CNPJ ou analise um documento na aba Concorrentes de um edital.")}
    </section>`;
  $$("tr.clicavel", el).forEach((tr) => tr.onclick = () => { location.hash = `#/concorrentes/${tr.dataset.id}`; });
  $("#novo-dossie", el).onclick = () => modalNovoDossie();
};

function linhaConcorrente(c) {
  const rec = c.dossie?.receita || {};
  const sancoes = (c.dossie?.sancoes_cgu?.registros?.length || 0) + ((c.dossie?.sancoes_tcu?.alerta) ? 1 : 0);
  return `<tr class="clicavel" data-id="${c.id}"><td>${esc(c.razao_social || rec.razao_social || "—")}</td><td>${fmt.cnpj(c.cnpj)}</td>
    <td>${rec.situacao ? carimbo(rec.situacao, rec.situacao === "ATIVA" ? "ok" : "erro") : "—"}</td>
    <td>${sancoes ? carimbo(`${sancoes} registro(s)`, "erro") : carimbo("Nada consta", "ok")}</td>
    <td>${c.perfil?.inabilitacoes?.length ? carimbo(`${c.perfil.inabilitacoes.length}`, "aviso") : c.perfil?.resumo ? "0" : "<span class='fraco'>sem dossiê completo</span>"}</td>
    <td>${c.analises}</td><td>${fmt.data(c.atualizado_em)}</td></tr>`;
}

function modalNovoDossie() {
  const m = modal({
    titulo: "Consultar CNPJ", corpo: `<form id="form-dossie">
      <div class="campo"><label for="cnpj_d">CNPJ do concorrente</label><input id="cnpj_d" name="cnpj" required placeholder="00.000.000/0000-00"></div>
      <div id="erro-dossie"></div><button class="botao" style="width:100%" type="submit">Consultar</button></form>`,
  });
  $("#form-dossie", m).onsubmit = async (ev) => {
    ev.preventDefault();
    const b = ev.target.querySelector("button");
    await ocupado(b, "Consultando bases públicas…", async () => {
      try { const c = await api("POST", "/api/concorrentes", { cnpj: $("#cnpj_d", m).value }); await atualizarConta(); m.fechar(); location.hash = `#/concorrentes/${c.id}`; }
      catch (e) { $("#erro-dossie", m).innerHTML = erroTela(e); }
    });
  };
}

const FORCA_ROT = { forte: ["Forte", "erro"], medio: ["Médio", "aviso"], fraco: ["Fraco", "neutro"] };
const STATUS_DOC_CONC = { pendente: ["Na fila", "neutro"], lido: ["Lido", "ok"], sem_mencao: ["Não cita a empresa", "neutro"], erro: ["Erro na leitura", "erro"] };

V.concorrente = async (el, id) => {
  const c = await api("GET", `/api/concorrentes/${id}`);
  const rec = c.dossie?.receita || {};
  const nomeConhecido = c.razao_social || rec.razao_social;
  const tcu = c.dossie?.sancoes_tcu || {};
  const cgu = c.dossie?.sancoes_cgu || {};
  const p = c.perfil || {};
  const atualizando = c.perfil_status === "atualizando";
  const fonte = (f) => (Array.isArray(f) ? f : [f]).filter(Boolean).map((x) => `<small class="fonte">${esc(x)}</small>`).join(" ");
  const eco = p.economico || {};
  el.innerHTML = `
    <div class="cabecalho"><div><p class="fraco" style="margin:0"><a href="#/concorrentes">← Concorrentes</a></p>
      <h1>${esc(nomeConhecido || "Empresa não identificada")}</h1><p>${fmt.cnpj(c.cnpj)} · dados públicos de ${fmt.data(c.atualizado_em)}${c.perfil_em ? ` · dossiê completo de ${fmt.data(c.perfil_em)}` : ""}</p></div>
      <div class="acoes"><button class="botao" id="dossie-completo" ${atualizando ? "disabled" : ""}>${icone("atualizar", 15)} ${p.resumo ? "Atualizar dossiê completo" : "Montar dossiê completo"}</button></div></div>
    ${atualizando ? `<div class="aviso info andamento-analise" role="status"><span class="girando" aria-hidden="true"></span><div><b>Montando o dossiê…</b> ${esc(c.perfil_etapa || "")}<br><small>Pode levar alguns minutos. Pode sair desta tela: o trabalho continua.</small></div></div>` : ""}
    ${c.perfil_status === "erro" ? `<div class="aviso erro">${esc(c.perfil_erro || "Não foi possível montar o dossiê.")}</div>` : ""}
    ${c.perfil_status === "desatualizado" && !atualizando ? `<div class="aviso info">Há análises ou documentos novos que ainda não entraram no dossiê. <button class="botao texto pequeno" id="reconsolidar">Atualizar o consolidado</button></div>` : ""}
    ${!p.resumo && !atualizando ? `<section class="bloco destaque-plano"><h2>Dossiê completo</h2>
      <p>Procura atas e decisões de julgamento no PNCP que citem esta empresa, lê os documentos que você juntar de outros certames e as análises
      já feitas, e consolida inabilitações anteriores, atestados, índices contábeis, certidões e os <b>pontos de ataque</b> para recursos e contrarrazões.
      Conta como 1 análise de concorrente do seu plano.</p></section>` : ""}
    ${p.resumo ? `<section class="bloco"><div class="bloco-titulo"><h2>Visão geral</h2>
        <span class="fraco">${p.fontes ? `${p.fontes.documentos} documento(s) · ${p.fontes.analises} análise(s) · ${p.fontes.contratos_pncp} contrato(s) no PNCP` : ""}</span></div>
        <p>${esc(p.resumo)}</p></section>
      ${(p.pontos_de_ataque || []).length ? `<section class="bloco"><h2>Pontos de ataque</h2>
        <p class="fraco">Onde esta empresa costuma ser vulnerável. As próximas análises de habilitação e proposta dela já recebem esta lista.</p>
        ${p.pontos_de_ataque.map((x) => `<div class="lista-item"><div class="corpo"><b>${esc(x.tema)}</b> ${carimboStatus(FORCA_ROT, x.forca)} ${fonte(x.fontes)}
          <p>${esc(x.argumento)}</p>${x.como_verificar ? `<p class="fraco"><b>Conferir:</b> ${esc(x.como_verificar)}</p>` : ""}${x.fundamento ? `<p class="fraco">${esc(x.fundamento)}</p>` : ""}</div></div>`).join("")}</section>` : ""}
      <div class="grade grade-2">
        <section class="bloco"><h2>Inabilitações e desclassificações</h2>
          ${(p.inabilitacoes || []).length ? p.inabilitacoes.map((x) => `<div class="lista-item"><div class="corpo"><b>${esc(x.orgao || "Órgão não informado")}</b> ${esc(x.certame || "")} ${fonte(x.fonte)}
            <p>${carimbo(x.fase === "proposta" ? "Proposta" : x.fase === "habilitacao" ? "Habilitação" : "Outra", "aviso")} ${esc(x.motivo || "")}</p>
            <p class="fraco">${[x.data ? fmt.data(x.data) : "", x.desfecho].filter(Boolean).map(esc).join(" · ")}</p></div></div>`).join("")
            : `<p class="fraco">Nenhuma encontrada nas fontes disponíveis. Junte atas de outros certames no acervo abaixo.</p>`}</section>
        <section class="bloco"><h2>Qualificação econômico-financeira</h2>
          ${Object.values(eco).some((v) => v !== null && v !== "") ? `<dl class="capa-campos" style="border:0">
            ${[["Exercício", eco.exercicio], ["Patrimônio líquido", eco.patrimonio_liquido != null ? fmt.moeda(eco.patrimonio_liquido) : ""], ["Capital social", eco.capital_social != null ? fmt.moeda(eco.capital_social) : ""],
               ["Liquidez geral", eco.liquidez_geral], ["Liquidez corrente", eco.liquidez_corrente], ["Solvência geral", eco.solvencia_geral]]
              .filter(([, v]) => v !== null && v !== undefined && v !== "").map(([k, v]) => `<div style="border:0"><dt>${k}</dt><dd>${esc(typeof v === "number" ? fmt.num(v) : v)}</dd></div>`).join("")}</dl>
            ${eco.observacoes ? `<p class="fraco">${esc(eco.observacoes)} ${fonte(eco.fonte)}</p>` : fonte(eco.fonte)}`
            : `<p class="fraco">Sem dados. Junte balanços ou documentos de habilitação no acervo.</p>`}</section>
      </div>
      <div class="grade grade-2">
        <section class="bloco"><h2>Atestados conhecidos</h2>
          ${(p.atestados || []).length ? `<div class="tabela-rolagem"><table><thead><tr><th>Emissor</th><th>Objeto</th><th>Quantitativo</th><th>Período</th></tr></thead>
            <tbody>${p.atestados.map((x) => `<tr><td>${esc(x.emissor || "—")} ${fonte(x.fonte)}</td><td>${esc(x.objeto || "—")}</td><td>${esc(x.quantitativo || "—")}</td><td>${esc(x.periodo || "—")}</td></tr>`).join("")}</tbody></table></div>`
            : `<p class="fraco">Nenhum atestado identificado ainda.</p>`}</section>
        <section class="bloco"><h2>Certidões, responsáveis técnicos e fragilidades</h2>
          ${(p.certidoes || []).map((x) => `<p>${carimbo(x.tipo || "Certidão", "neutro")} ${esc([x.situacao, x.validade ? "válida até " + fmt.data(x.validade) : ""].filter(Boolean).join(" · "))} ${fonte(x.fonte)}</p>`).join("")}
          ${(p.responsaveis_tecnicos || []).map((x) => `<p><b>RT:</b> ${esc(x.nome)}${x.registro ? ` (${esc(x.registro)})` : ""} ${fonte(x.fonte)}</p>`).join("")}
          ${(p.fragilidades_recorrentes || []).map((x) => `<p><b>${esc(x.tema)}</b>${x.ocorrencias > 1 ? ` · ${x.ocorrencias}x` : ""}: ${esc(x.descricao)} ${fonte(x.fontes)}</p>`).join("")}
          ${!(p.certidoes || []).length && !(p.responsaveis_tecnicos || []).length && !(p.fragilidades_recorrentes || []).length ? `<p class="fraco">Nada identificado ainda.</p>` : ""}</section>
      </div>
      ${(p.lacunas || []).length ? `<section class="bloco"><h2>O que falta saber</h2>${p.lacunas.map((x) => `<p class="fraco">• ${esc(x)}</p>`).join("")}</section>` : ""}` : ""}
    <section class="bloco"><div class="bloco-titulo"><h2>Acervo de documentos de outros certames</h2>
      <button class="botao pequeno" id="add-doc-conc" ${atualizando ? "disabled" : ""}>${icone("upload", 14)} Juntar documento</button></div>
      <p class="fraco">Atas de julgamento, decisões de recurso, habilitações, balanços e atestados que você conseguir (portal da disputa, pedido via Lei de Acesso à Informação, processos).
        Os marcados "PNCP" foram encontrados sozinhos. A fonte <code>doc#N</code> nas listas acima aponta para o documento N.</p>
      ${c.documentos.length ? `<div class="tabela-rolagem"><table><thead><tr><th>#</th><th>Documento</th><th>Tipo</th><th>Órgão / certame</th><th>Data</th><th>Situação</th><th></th></tr></thead>
        <tbody>${c.documentos.map((d) => `<tr><td>doc#${d.id}</td><td>${esc(d.titulo || d.nome_arquivo || "Documento")}${d.origem === "pncp" ? ` ${carimbo("PNCP", "oficio")}` : ""}
            ${d.extracao?.resumo ? `<br><small class="fraco">${esc(d.extracao.resumo.slice(0, 180))}</small>` : ""}</td>
          <td>${esc(c.tipos_documento[d.tipo] || d.tipo)}</td><td>${esc([d.orgao, d.certame].filter(Boolean).join(" · ") || "—")}</td><td>${fmt.data(d.data_documento)}</td>
          <td>${carimboStatus(STATUS_DOC_CONC, d.status)}</td>
          <td class="acoes-celula">${d.tem_arquivo ? `<button class="botao-icone" data-abrir-doc="${d.id}" title="Abrir" aria-label="Abrir documento">${icone("olho", 16)}</button>` : ""}
            <button class="botao texto pequeno" data-excluir-doc="${d.id}" aria-label="Excluir documento">${icone("excluir", 14)}</button></td></tr>`).join("")}</tbody></table></div>`
        : vazio("Nenhum documento no acervo", "Junte atas e documentos de outros certames para enriquecer o dossiê.")}</section>
    <div class="grade grade-2">
      <section class="bloco"><h2>Receita Federal</h2>
        ${rec.status === "ok" ? `<dl class="capa-campos" style="border:0"><div style="border:0"><dt>Situação</dt><dd>${carimbo(rec.situacao, rec.situacao === "ATIVA" ? "ok" : "erro")}</dd></div>
          <div style="border:0"><dt>Abertura</dt><dd>${fmt.data(rec.abertura)}</dd></div>
          <div style="border:0"><dt>Capital social</dt><dd>${fmt.moeda(rec.capital_social)}</dd></div>
          <div style="border:0"><dt>Porte</dt><dd>${esc(rec.porte || "—")}</dd></div></dl>
          <p><b>CNAEs:</b> ${(rec.cnaes || []).map((cn) => esc(cn.codigo + " " + (cn.descricao || ""))).join("; ") || "—"}</p>
          <p><b>Sócios:</b> ${(rec.socios || []).map((s) => esc(s.nome)).join(", ") || "—"}</p>`
          : `<p class="fraco">${rec.status === "nao_encontrado" ? "CNPJ não encontrado na base da Receita." : "Consulta indisponível no momento."}</p>`}</section>
      <section class="bloco"><h2>Sanções e impedimentos</h2>
        ${tcu.alerta ? tcu.certidoes.filter((x) => !String(x.situacao || "").toLowerCase().includes("nada consta"))
          .map((x) => `<p>${carimbo(x.emissor, "erro")} ${esc(x.situacao)}</p>`).join("") : ""}
        ${(cgu.registros || []).map((s) => `<p>${carimbo(s.cadastro, "erro")} ${esc(s.tipo)} — ${esc(s.orgao)} (${fmt.data(s.inicio)} a ${fmt.data(s.fim)})</p>`).join("")}
        ${!tcu.alerta && !(cgu.registros || []).length ? `<p>${carimbo("Nada consta nas bases consultadas", "ok")}</p>` : ""}
        ${cgu.status === "sem_chave" ? `<p class="fraco">Cadastre a chave do Portal da Transparência no servidor para consultar CEIS/CNEP.</p>` : ""}
      </section>
    </div>
    <section class="bloco"><h2>Contratos no PNCP</h2>
      ${(c.dossie?.historico_pncp || []).length ? c.dossie.historico_pncp.map((h) => `<div class="lista-item"><div class="corpo">
        <b>${esc(h.objeto || "")}</b><p>${esc(h.orgao || "")} · ${esc(h.uf || "")} · ${fmt.data(h.data)}</p></div>${fmt.moeda(h.valor)}</div>`).join("")
        : vazio("Sem histórico encontrado", "Não há contratos ou atas deste CNPJ na busca do PNCP.")}</section>
    <section class="bloco"><h2>Análises neste concorrente</h2>
      ${c.analises.length ? c.analises.map((a) => `<div class="lista-item"><div class="corpo"><b>${a.tipo === "habilitacao" ? "Habilitação" : "Proposta"}</b>
        <p>${fmt.dataHora(a.criado_em)} · ${(a.resultado.apontamentos || []).length} apontamento(s)${(a.resultado.sugestoes || []).length ? ` · ${a.resultado.sugestoes.length} sugestão(ões) de peça` : ""}</p></div>
        <button class="botao pequeno secundario" data-ver="${a.id}">${icone("olho",14)} Ver parecer</button></div>`).join("")
        : vazio("Nenhuma análise ainda", "Analise a habilitação ou a proposta deste concorrente em um edital.")}</section>`;
  $("#dossie-completo", el).onclick = async () => {
    try { await api("POST", `/api/concorrentes/${id}/dossie-completo`, {}); await atualizarConta(); V.concorrente(el, id); } catch (e) { avisarErro(e); }
  };
  const rc = $("#reconsolidar", el); if (rc) rc.onclick = async () => { try { await api("POST", `/api/concorrentes/${id}/reconsolidar`); V.concorrente(el, id); } catch (e) { avisarErro(e); } };
  $("#add-doc-conc", el).onclick = () => modalDocConcorrente(c, () => V.concorrente(el, id));
  $$("[data-abrir-doc]", el).forEach((b) => b.onclick = async () => {
    const d = c.documentos.find((x) => x.id == b.dataset.abrirDoc);
    try { const r = await api("GET", `/api/documentos-concorrente/${d.id}/arquivo`); const url = URL.createObjectURL(await r.blob()); window.open(url, "_blank"); setTimeout(() => URL.revokeObjectURL(url), 600000); }
    catch (e) { avisarErro(e); }
  });
  $$("[data-excluir-doc]", el).forEach((b) => b.onclick = async () => {
    if (!(await confirmar("Excluir este documento do acervo?", "Excluir"))) return;
    await api("DELETE", `/api/documentos-concorrente/${b.dataset.excluirDoc}`); V.concorrente(el, id);
  });
  $$("[data-ver]", el).forEach((b) => b.onclick = () => abrirParecerConcorrente(c.analises.find((a) => a.id == b.dataset.ver)));
  if (atualizando) setTimeout(() => { if (location.hash === `#/concorrentes/${id}`) V.concorrente(el, id); }, 5000);
};

function modalDocConcorrente(c, depois) {
  const m = modal({ titulo: "Juntar documento ao acervo", corpo: `<form id="form-doc-conc">
    <div class="campo"><label for="dc-arq">Arquivo</label><input id="dc-arq" name="arquivo" type="file" accept=".pdf,.docx,.txt" required></div>
    <div class="linha-campos">
      <div class="campo"><label for="dc-tipo">Tipo</label><select id="dc-tipo" name="tipo">${Object.entries(c.tipos_documento).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("")}</select></div>
      <div class="campo"><label for="dc-data">Data do documento</label><input id="dc-data" name="data_documento" type="date"></div></div>
    <div class="linha-campos">
      <div class="campo"><label for="dc-orgao">Órgão</label><input id="dc-orgao" name="orgao" placeholder="Ex.: Prefeitura de Campinas"></div>
      <div class="campo"><label for="dc-cert">Certame</label><input id="dc-cert" name="certame" placeholder="Ex.: PE 12/2025"></div></div>
    <p class="fraco">A IA lê o documento procurando o que diz respeito a ${esc(c.razao_social || "esta empresa")} e atualiza o dossiê.</p>
    <div id="erro-dc"></div><button class="botao" style="width:100%" type="submit">Enviar e ler</button></form>` });
  $("#form-doc-conc", m).onsubmit = async (ev) => {
    ev.preventDefault();
    await ocupado(ev.target.querySelector("button"), "Enviando…", async () => {
      try { await api("POST", `/api/concorrentes/${c.id}/documentos`, new FormData(ev.target)); m.fechar(); toast("Documento enviado. O dossiê está sendo atualizado.", "ok"); depois(); }
      catch (e) { $("#erro-dc", m).innerHTML = erroTela(e); }
    });
  };
}
