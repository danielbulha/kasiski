// Kanban da oportunidade: o ciclo comercial do edital (Identificada → Contrato ativo) com duas saídas laterais.
// O cartão mostra o essencial; ao abrir, o dossiê completo em um painel lateral.
const RISCO_OP = { alto: ["Alto", "erro"], medio: ["Médio", "aviso"], baixo: ["Baixo", "ok"] };
const PRE_DISPUTA_OP = ["identificada", "em_analise", "decisao", "preparacao", "pronta"];
const ETAPA_NOMES_OP = { identificada: "Identificada", em_analise: "Em análise", decisao: "Decisão Go / No-Go", preparacao: "Preparação",
  pronta: "Pronta para disputa", em_disputa: "Em disputa", classificada: "Classificada / Habilitação", recurso: "Recurso / Contrarrazões",
  homologada: "Adjudicada / Homologada", contratacao: "Contratação", contrato_ativo: "Contrato ativo", perdida: "Perdida", desistencia: "Desistência / No-Go" };

const moedaCurta = (v) => {
  if (!v) return "Valor não informado";
  if (v >= 1e9) return `R$ ${(v / 1e9).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} bi`;
  if (v >= 1e6) return `R$ ${(v / 1e6).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} milhões`;
  if (v >= 1e3) return `R$ ${Math.round(v / 1e3).toLocaleString("pt-BR")} mil`;
  return fmt.moeda(v);
};
const sessaoCurta = (iso) => {
  if (!iso) return "Sessão a definir";
  const d = new Date(iso);
  const h = d.getHours(), m = d.getMinutes();
  return `${d.toLocaleDateString("pt-BR")} — ${String(h).padStart(2, "0")}h${m ? String(m).padStart(2, "0") : ""}`;
};
function prazoCartao(c) {
  if (PRE_DISPUTA_OP.includes(c.etapa) && c.dias !== null && c.dias !== undefined) {
    if (c.dias > 1) return [`Faltam ${c.dias} dias`, c.dias <= 5 ? "aviso" : "neutro"];
    if (c.dias === 1) return ["Sessão amanhã", "erro"];
    if (c.dias === 0) return ["Sessão hoje", "erro"];
    return [`Sessão há ${-c.dias} dia(s)`, "neutro"];
  }
  if (c.etapa_em) {
    const n = Math.max(0, Math.floor((Date.now() - new Date(c.etapa_em + "Z")) / 864e5));
    return [n ? `Nesta etapa há ${n} dia(s)` : "Entrou hoje nesta etapa", "neutro"];
  }
  return ["", "neutro"];
}
const tituloCartao = (c) => {
  const n = c.numero || "";
  if (!n) return c.modalidade || "Edital sem número";
  return /preg|concorr|dispensa|inexig|leil|di[aá]logo|credenc/i.test(n) || !c.modalidade ? n : `${c.modalidade} nº ${n}`;
};

V.oportunidades = async (el, abrirId) => {
  if (!S.empresas.length) { el.innerHTML = exigirEmpresa(); return; }
  if (abrirId) V.oportunidades.abrir = Number(abrirId);
  const d = await api("GET", `/api/empresas/${S.empresaId}/oportunidades`);
  const f = V.oportunidades.filtro || { q: "", resp: "", saidas: true };
  V.oportunidades.filtro = f;
  V.oportunidades.dados = d;
  const sinc = d.sincronizacao || {};
  const sincronizando = sinc.status === "sincronizando";
  el.innerHTML = `
    <div class="cabecalho"><div><h1>Oportunidades</h1><p>${esc(empresaAtual()?.razao_social || "")} · pipeline do ciclo comercial das licitações</p></div>
      <div class="acoes">
        ${d.radar_novos ? `<a class="botao secundario" href="#/radar">${icone("radar")} ${d.radar_novos} nova(s) no radar</a>` : ""}
        <button class="botao secundario" id="op-sinc" ${sincronizando ? "disabled" : ""}>${sincronizando ? "Sincronizando…" : "Sincronizar com o PNCP"}</button>
        <button class="botao" id="op-novo">Novo edital</button></div></div>
    ${guia(`<p>Cada cartão é uma licitação acompanhada. Arraste entre as colunas ou abra o cartão para ver o dossiê completo.
      O Kasiski move os cartões sozinho quando detecta um evento: edital capturado → <b>Identificada</b>; análise → <b>Em análise</b> e <b>Decisão</b>;
      Go → <b>Preparação</b>; sessão iniciada → <b>Em disputa</b>; resultado, homologação e contrato no PNCP → etapas finais. A sincronização com o PNCP roda todo dia.</p>`)}
    <div class="op-filtros">
      <input type="search" id="op-q" placeholder="Buscar por órgão, objeto ou número" value="${esc(f.q)}" aria-label="Buscar oportunidades">
      <select id="op-resp" aria-label="Filtrar por responsável">
        <option value="">Todos os responsáveis</option><option value="__meus" ${f.resp === "__meus" ? "selected" : ""}>Meus cartões</option>
        <option value="__sem" ${f.resp === "__sem" ? "selected" : ""}>Sem responsável</option>
        ${[...new Set(d.cartoes.map((c) => c.responsavel).filter(Boolean))].map((r) => `<option value="${esc(r)}" ${f.resp === r ? "selected" : ""}>${esc(r)}</option>`).join("")}
      </select>
      <label class="check"><input type="checkbox" id="op-saidas" ${f.saidas ? "checked" : ""}> Mostrar perdidas e desistências</label>
      <span class="fraco op-sinc-info">${sinc.concluido_em ? `Última sincronização: ${fmt.dataHora(sinc.concluido_em + "Z")}${sinc.movidos ? ` · ${sinc.movidos} cartão(ões) movido(s)` : ""}` : ""}</span>
    </div>
    <div class="kanban" id="kanban" aria-label="Quadro de oportunidades"></div>`;
  desenharQuadro(el);
  const rec = () => V.oportunidades(el);
  let t; $("#op-q", el).oninput = (ev) => { clearTimeout(t); t = setTimeout(() => { f.q = ev.target.value; desenharQuadro(el); }, 200); };
  $("#op-resp", el).onchange = (ev) => { f.resp = ev.target.value; desenharQuadro(el); };
  $("#op-saidas", el).onchange = (ev) => { f.saidas = ev.target.checked; desenharQuadro(el); };
  $("#op-novo", el).onclick = () => modalNovoEdital();
  $("#op-sinc", el).onclick = async (ev) => {
    try { await api("POST", `/api/empresas/${S.empresaId}/oportunidades/sincronizar`); ev.target.disabled = true; ev.target.textContent = "Sincronizando…"; acompanharSinc(el); }
    catch (e) { avisarErro(e); }
  };
  if (sincronizando) acompanharSinc(el);
  if (V.oportunidades.abrir) { const id = V.oportunidades.abrir; V.oportunidades.abrir = null; abrirOportunidade(id, rec); }
};

function acompanharSinc(el) {
  clearTimeout(acompanharSinc.t);
  acompanharSinc.t = setTimeout(async () => {
    if (!document.body.contains(el) || !$("#kanban", el)) return;
    const d = await api("GET", `/api/empresas/${S.empresaId}/oportunidades`).catch(() => null);
    if (d && d.sincronizacao?.status !== "sincronizando") {
      toast(d.sincronizacao?.status === "erro" ? "Não foi possível consultar o PNCP agora." : `Sincronização concluída${d.sincronizacao?.movidos ? `: ${d.sincronizacao.movidos} cartão(ões) movido(s)` : ": nenhuma mudança"}.`, d.sincronizacao?.status === "erro" ? "erro" : "ok");
      V.oportunidades(el);
    } else acompanharSinc(el);
  }, 4000);
}

function filtrarCartoes(cartoes) {
  const f = V.oportunidades.filtro, q = (f.q || "").toLowerCase();
  return cartoes.filter((c) => {
    if (q && ![c.orgao, c.objeto, c.numero, c.modalidade, c.municipio].join(" ").toLowerCase().includes(q)) return false;
    if (f.resp === "__meus") return c.responsavel_id === S.usuario.id || (c.responsavel && c.responsavel === S.usuario.nome);
    if (f.resp === "__sem") return !c.responsavel;
    if (f.resp) return c.responsavel === f.resp;
    return true;
  });
}

function htmlCartao(c) {
  const [prazo, tipoPrazo] = prazoCartao(c);
  const fit = c.fit === null || c.fit === undefined ? "—" : `${c.fit}%`;
  const classeFit = c.fit >= 75 ? "alto" : c.fit >= 50 ? "medio" : c.fit !== null && c.fit !== undefined ? "baixo" : "";
  return `<article class="op-cartao" draggable="true" tabindex="0" data-cartao="${c.id}" aria-label="${esc(tituloCartao(c))} — ${esc(c.orgao || "")}">
    <div class="op-cartao-topo"><b>${esc(tituloCartao(c))}</b>${c.decisao === "go" ? `<span class="op-go">GO</span>` : ""}</div>
    <div class="op-orgao">${esc(c.orgao || "Órgão não informado")}</div>
    <div class="op-objeto">${esc(c.objeto || "Objeto a extrair na análise")}</div>
    <div class="op-valor">${esc(moedaCurta(c.valor_estimado))}</div>
    <div class="op-linha">Sessão: ${esc(sessaoCurta(c.data_abertura))}</div>
    <div class="op-linha">Responsável: ${c.responsavel ? esc(c.responsavel) : `<span class="fraco">definir</span>`}</div>
    <div class="op-linha"><span class="op-fit ${classeFit}" title="${c.fit_fonte === "radar" ? "Nota do radar (ainda sem análise)" : "Aderência da habilitação + recomendação da IA"}">Fit: ${fit}</span>
      <span class="op-sep">|</span> Risco: ${c.risco ? `<span class="op-risco ${c.risco}">${RISCO_OP[c.risco][0]}</span>` : "—"}</div>
    ${prazo ? `<div class="op-prazo ${tipoPrazo}">${esc(prazo)}</div>` : ""}
    ${c.motivo_saida && ["perdida", "desistencia"].includes(c.etapa) ? `<div class="op-motivo">${esc(c.motivo_saida).slice(0, 140)}</div>` : ""}
  </article>`;
}

function desenharQuadro(el) {
  const d = V.oportunidades.dados, f = V.oportunidades.filtro;
  const cartoes = filtrarCartoes(d.cartoes);
  const coluna = (e, saida) => {
    const lista = cartoes.filter((c) => c.etapa === e.codigo);
    const total = lista.reduce((a, c) => a + (c.valor_estimado || 0), 0);
    return `<section class="op-coluna${saida ? " saida " + e.codigo : ""}" data-coluna="${e.codigo}" aria-label="${esc(e.nome)}">
      <header title="${esc(e.descricao)}"><div><h3>${esc(e.nome)}</h3><small>${lista.length} · ${total ? esc(moedaCurta(total)) : "—"}</small></div></header>
      <div class="op-lista" data-lista="${e.codigo}">${lista.map(htmlCartao).join("") || `<p class="op-vazia">${saida ? "Nenhuma" : "Arraste um cartão para cá"}</p>`}</div></section>`;
  };
  const k = $("#kanban", el);
  k.innerHTML = d.etapas.map((e) => coluna(e, false)).join("") +
    (f.saidas ? `<div class="op-divisor" aria-hidden="true"><span>Saídas</span></div>${d.saidas.map((e) => coluna(e, true)).join("")}` : "");
  if (!d.cartoes.length) {
    k.insertAdjacentHTML("beforebegin", "");
    $("[data-lista=identificada]", k).innerHTML = `<div class="op-vazia">Nenhuma licitação ainda.<br><a href="#/radar">Buscar no radar</a> ou use <b>Novo edital</b>.</div>`;
  }
  const rec = () => V.oportunidades(el);
  $$("[data-cartao]", k).forEach((c) => {
    c.onclick = () => abrirOportunidade(Number(c.dataset.cartao), rec);
    c.onkeydown = (ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); abrirOportunidade(Number(c.dataset.cartao), rec); } };
    c.ondragstart = (ev) => { ev.dataTransfer.setData("text/plain", c.dataset.cartao); ev.dataTransfer.effectAllowed = "move"; c.classList.add("arrastando"); };
    c.ondragend = () => c.classList.remove("arrastando");
  });
  $$("[data-coluna]", k).forEach((col) => {
    col.ondragover = (ev) => { ev.preventDefault(); col.classList.add("alvo"); };
    col.ondragleave = (ev) => { if (!col.contains(ev.relatedTarget)) col.classList.remove("alvo"); };
    col.ondrop = async (ev) => {
      ev.preventDefault(); col.classList.remove("alvo");
      const id = Number(ev.dataTransfer.getData("text/plain"));
      const c = d.cartoes.find((x) => x.id === id);
      if (!c || c.etapa === col.dataset.coluna) return;
      await moverCartao(c, col.dataset.coluna, () => desenharQuadro(el));
    };
  });
}

// Move o cartão; saídas pedem motivo. Atualiza o cartão local e chama `depois`.
async function moverCartao(c, etapa, depois) {
  const d = V.oportunidades.dados;
  const nomes = Object.fromEntries([...d.etapas, ...d.saidas].map((e) => [e.codigo, e.nome]));
  let motivo = null;
  if (["perdida", "desistencia"].includes(etapa)) {
    motivo = await pedirMotivo(etapa === "perdida" ? "Por que a oportunidade foi perdida?" : "Por que desistir desta licitação?",
      etapa === "perdida" ? "Ex.: preço acima do vencedor; inabilitada por atestado; licitação revogada." : "Ex.: margem baixa; exigência técnica que não atendemos; prazo curto.");
    if (motivo === null) return;
  }
  try {
    const novo = await api("PATCH", `/api/oportunidades/${c.id}`, { etapa, motivo });
    Object.assign(c, novo);
    toast(`Movido para ${nomes[etapa]}.`, "ok");
    depois && depois();
  } catch (e) { avisarErro(e); }
}

function pedirMotivo(titulo, dica) {
  return new Promise((ok) => {
    let respondeu = false;
    const m = modal({ titulo, corpo: `<form id="f-motivo"><div class="campo"><label for="motivo-op">Motivo</label>
      <textarea id="motivo-op" name="motivo" rows="3" required placeholder="${esc(dica)}"></textarea></div></form>`,
      acoes: `<button class="botao secundario" data-fechar>Cancelar</button><button class="botao" data-ok>Confirmar</button>` });
    const enviar = () => { const v = $("#motivo-op", m).value.trim(); if (!v) { $("#motivo-op", m).focus(); return; } respondeu = true; m.fechar(); ok(v); };
    $("[data-ok]", m).onclick = enviar;
    $("#f-motivo", m).onsubmit = (ev) => { ev.preventDefault(); enviar(); };
    const fechar = m.fechar; m.fechar = () => { fechar(); if (!respondeu) ok(null); };
    m.addEventListener("click", (ev) => { if ((ev.target === m || ev.target.closest("[data-fechar]")) && !respondeu) ok(null); });
  });
}

// ---------------------------------------------------------------- dossiê (painel lateral)
async function abrirOportunidade(id, aoMudar) {
  $$(".op-gaveta-fundo").forEach((x) => x.remove());
  const fundo = document.createElement("div");
  fundo.className = "op-gaveta-fundo";
  fundo.innerHTML = `<aside class="op-gaveta" role="dialog" aria-modal="true" aria-label="Dossiê da oportunidade"><p class="carregando">Carregando dossiê…</p></aside>`;
  document.body.appendChild(fundo);
  const gaveta = $(".op-gaveta", fundo);
  let mudou = false;
  const fechar = () => { fundo.remove(); document.removeEventListener("keydown", tecla); if (mudou && aoMudar) aoMudar(); };
  const tecla = (ev) => { if (ev.key === "Escape" && !$(".fundo-modal")) fechar(); };
  document.addEventListener("keydown", tecla);
  fundo.addEventListener("click", (ev) => { if (ev.target === fundo) fechar(); });
  let o;
  try { o = await api("GET", `/api/oportunidades/${id}`); } catch (e) { gaveta.innerHTML = erroTela(e); return; }
  const aba = sessionStorage.getItem("op_aba") || "geral";
  const recarregar = async () => { mudou = true; o = await api("GET", `/api/oportunidades/${id}`); desenhar(sessionStorage.getItem("op_aba") || "geral"); };

  function desenhar(abaAtual) {
    const c = o.cartao, ed = o.edital, dados = V.oportunidades.dados || { etapas: [], saidas: [] };
    const etapas = [...dados.etapas, ...dados.saidas];
    const [prazo] = prazoCartao(c);
    const mostrarDecisao = ["identificada", "em_analise", "decisao"].includes(c.etapa);
    const rec = ROTULOS.decisao[c.decisao_ia];
    gaveta.innerHTML = `
      <header class="op-g-cab"><div><small class="fraco">${esc(ed.numero_controle || "Edital enviado por upload")}</small>
          <h2>${esc(tituloCartao(c))}</h2><p>${esc(c.orgao || "")}</p></div>
        <button class="botao texto" data-fechar-gaveta aria-label="Fechar">Fechar</button></header>
      <div class="op-g-controles">
        <div class="campo"><label for="g-etapa">Etapa</label><select id="g-etapa">${etapas.map((e) => `<option value="${e.codigo}" ${c.etapa === e.codigo ? "selected" : ""}>${esc(e.nome)}</option>`).join("")}</select></div>
        <div class="campo"><label for="g-resp">Responsável</label><select id="g-resp">
          <option value="">Sem responsável</option>${o.usuarios.map((u) => `<option value="u:${u.id}" ${c.responsavel_id === u.id ? "selected" : ""}>${esc(u.nome)}</option>`).join("")}
          ${c.responsavel && !c.responsavel_id ? `<option value="t:${esc(c.responsavel)}" selected>${esc(c.responsavel)}</option>` : ""}
          <option value="__outro">Outra pessoa…</option></select></div>
      </div>
      <div class="op-g-kpis">
        <div><span>Valor estimado</span><b>${ed.valor_estimado ? fmt.moeda(ed.valor_estimado) : "—"}</b></div>
        <div><span>Sessão</span><b>${esc(sessaoCurta(c.data_abertura))}</b>${prazo ? `<small>${esc(prazo)}</small>` : ""}</div>
        <div><span>Fit</span><b>${c.fit === null || c.fit === undefined ? "—" : c.fit + "%"}</b><small>${c.fit_fonte === "radar" ? "nota do radar" : c.fit_fonte ? "pela análise" : "analise o edital"}</small></div>
        <div><span>Risco</span><b>${c.risco ? RISCO_OP[c.risco][0] : "—"}</b></div>
      </div>
      ${mostrarDecisao ? `<div class="op-g-decisao"><div><b>Decisão Go / No-Go</b>
          <p class="fraco">${rec ? `A IA recomenda: <b>${esc(rec[0])}</b>.` : "Analise o edital para receber a recomendação da IA."}${c.decisao ? ` Decisão registrada: <b>${c.decisao === "go" ? "Go" : "No-Go"}</b>.` : ""}</p></div>
        <div class="acoes"><button class="botao" data-go>Go — vamos participar</button><button class="botao secundario" data-nogo>No-Go</button></div></div>` : ""}
      <div class="abas op-g-abas" role="tablist">${[["geral", "Visão geral"], ["itens", "Itens e lotes"], ["documentos", "Documentos"], ["concorrentes", "Concorrentes"], ["orgao", "Órgão"], ["historico", "Movimentações"]]
        .map(([k, t]) => `<button role="tab" data-g-aba="${k}" class="${abaAtual === k ? "ativa" : ""}" aria-selected="${abaAtual === k}">${t}</button>`).join("")}</div>
      <div id="g-corpo"></div>
      <footer class="op-g-rodape"><a class="botao secundario" href="#/editais/${ed.id}">Abrir edital completo</a>
        ${ed.numero_controle ? `<button class="botao texto" data-sinc-um>Sincronizar com o PNCP</button>` : ""}</footer>`;
    $("[data-fechar-gaveta]", gaveta).onclick = fechar;
    $$("a[href^='#/']", gaveta).forEach((a) => a.addEventListener("click", () => { fundo.remove(); document.removeEventListener("keydown", tecla); }));
    $("#g-etapa", gaveta).onchange = async (ev) => {
      const alvo = ev.target.value; ev.target.value = c.etapa;
      await moverCartao(V.oportunidades.dados?.cartoes?.find((x) => x.id === c.id) || c, alvo, null);
      await recarregar();
    };
    $("#g-resp", gaveta).onchange = async (ev) => {
      let v = ev.target.value, corpo;
      if (v === "__outro") {
        const nome = await pedirTexto("Responsável", "Nome da pessoa responsável");
        if (!nome) { ev.target.value = c.responsavel_id ? `u:${c.responsavel_id}` : c.responsavel ? `t:${c.responsavel}` : ""; return; }
        corpo = { responsavel: nome, responsavel_id: null };
      } else if (v.startsWith("u:")) corpo = { responsavel_id: Number(v.slice(2)) };
      else if (v.startsWith("t:")) return;
      else corpo = { responsavel: "", responsavel_id: null };
      try { await api("PATCH", `/api/oportunidades/${c.id}`, corpo); toast("Responsável atualizado.", "ok"); await recarregar(); } catch (e) { avisarErro(e); }
    };
    const go = $("[data-go]", gaveta);
    if (go) go.onclick = () => ocupado(go, "Registrando…", async () => {
      try { await api("POST", `/api/oportunidades/${c.id}/decisao`, { decisao: "go" }); toast("Go registrado. O cartão foi para Preparação.", "ok"); await recarregar(); } catch (e) { avisarErro(e); }
    });
    const nogo = $("[data-nogo]", gaveta);
    if (nogo) nogo.onclick = async () => {
      const motivo = await pedirMotivo("Motivo do No-Go", "Ex.: margem baixa; exigência de atestado que não temos; prazo de entrega inviável.");
      if (motivo === null) return;
      try { await api("POST", `/api/oportunidades/${c.id}/decisao`, { decisao: "no_go", motivo }); toast("No-Go registrado.", "ok"); await recarregar(); } catch (e) { avisarErro(e); }
    };
    const s1 = $("[data-sinc-um]", gaveta);
    if (s1) s1.onclick = () => ocupado(s1, "Consultando o PNCP…", async () => {
      try { const r = await api("POST", `/api/oportunidades/${c.id}/sincronizar`); toast(r.movimentos.length ? "O cartão foi movimentado pelo PNCP." : "Nenhum evento novo no PNCP.", "ok"); await recarregar(); } catch (e) { avisarErro(e); }
    });
    $$("[data-g-aba]", gaveta).forEach((b) => b.onclick = () => { sessionStorage.setItem("op_aba", b.dataset.gAba); desenhar(b.dataset.gAba); });
    corpoAba(abaAtual, $("#g-corpo", gaveta));
  }

  function corpoAba(abaAtual, el) {
    const ed = o.edital, a = o.analise;
    const campo = (t, v) => `<div><dt>${esc(t)}</dt><dd>${v === null || v === undefined || v === "" ? "—" : v}</dd></div>`;
    if (abaAtual === "geral") {
      const ch = a?.checklist || {};
      el.innerHTML = `
        <section class="op-g-sec"><h3>Dados da licitação</h3><dl class="op-g-dl">
          ${campo("Órgão", esc(ed.orgao))}${campo("CNPJ do órgão", o.orgao_cnpj ? fmt.cnpj(o.orgao_cnpj) : "")}
          ${campo("UASG / unidade compradora", esc([ed.unidade_codigo, ed.unidade_nome].filter(Boolean).join(" — ")))}
          ${campo("Modalidade", esc(ed.modalidade))}${campo("Número", esc(ed.numero))}
          ${campo("Critério de julgamento", esc(a?.criterio_julgamento))}${campo("Valor estimado", ed.valor_estimado ? fmt.moeda(ed.valor_estimado) : "")}
          ${campo("Local", esc([ed.municipio, ed.uf].filter(Boolean).join("/")))}${campo("Portal da disputa", esc(ed.portal_disputa))}
          ${campo("Situação no PNCP", esc(ed.pncp_situacao))}${campo("Prazo de execução", esc(a?.prazo_execucao))}
          ${campo("Garantia contratual", esc(a?.garantia_contrato))}
          ${campo("Link", ed.link ? `<a href="${esc(ed.link)}" target="_blank" rel="noopener">Ver no PNCP</a>` : "")}
        </dl><p><b>Objeto:</b> ${esc(ed.objeto || "—")}</p></section>
        <section class="op-g-sec"><h3>Datas e prazos</h3>
          ${o.prazos.length ? `<ul class="op-g-lista">${o.prazos.map((p) => `<li><b>${fmt.dataHora(p.data)}</b> — ${esc(p.titulo)}${p.concluido ? " <span class='fraco'>(concluído)</span>" : ""}</li>`).join("")}</ul>` : `<p class="fraco">Sem prazos cadastrados. Informe a data da sessão no edital para gerar os prazos de esclarecimento e impugnação.</p>`}</section>
        <section class="op-g-sec"><h3>Análise do edital</h3>
          ${a ? `<p>${esc(a.resumo || "")}</p>
            <p>${a.recomendacao?.decisao ? carimbo(ROTULOS.decisao[a.recomendacao.decisao][0], ROTULOS.decisao[a.recomendacao.decisao][1]) : ""} <span class="fraco">${esc(a.recomendacao?.justificativa || "")}</span></p>
            <p class="fraco">Habilitação: ${ch.atende || 0} atende · ${ch.verificar || 0} verificar · ${(ch.falta || 0) + (ch.vencido || 0)} falta/vencido · ${a.clausulas} cláusula(s) restritiva(s)</p>
            ${a.riscos.length ? `<ul class="op-g-lista">${a.riscos.slice(0, 6).map((r) => `<li>${carimbo(RISCO_OP[r.nivel]?.[0] || r.nivel || "—", RISCO_OP[r.nivel]?.[1] || "neutro")} ${esc(r.tema)} — <span class="fraco">${esc(r.descricao)}</span></li>`).join("")}</ul>` : ""}
            ${a.exigencias_tecnicas.length ? `<p><b>Exigências técnicas do objeto:</b> ${esc(a.exigencias_tecnicas.join("; "))}</p>` : ""}`
          : `<p class="fraco">Ainda sem análise. <a href="#/editais/${ed.id}">Analisar o edital</a> calcula o fit, os riscos e a recomendação.</p>`}</section>
        <section class="op-g-sec"><h3>Preços e proposta</h3>
          ${o.propostas.length ? `<ul class="op-g-lista">${o.propostas.map((p) => `<li><a href="#/propostas/${p.id}">${esc(p.titulo || "Proposta " + p.id)}</a></li>`).join("")}</ul>` : `<p class="fraco">Nenhuma proposta montada.</p>`}
          <div class="acoes"><button class="botao pequeno secundario" data-proposta>Montar proposta comercial</button><a class="botao pequeno texto" href="#/precos">Consultar preços praticados</a></div></section>`;
      const bp = $("[data-proposta]", el); if (bp) bp.onclick = () => modalNovaProposta(ed.id);
    } else if (abaAtual === "itens") {
      el.innerHTML = `<p class="carregando">Consultando os itens no PNCP…</p>`;
      api("GET", `/api/oportunidades/${ed.id}/itens`).then((r) => {
        el.innerHTML = r.itens.length ? `<div class="tabela-rolagem"><table><thead><tr><th>Item</th><th>Descrição</th><th>Qtd.</th><th>Valor unit. estimado</th><th>Total</th><th>Situação</th></tr></thead>
          <tbody>${r.itens.map((i) => `<tr><td>${esc(i.numero)}</td><td>${esc(i.descricao)}</td><td>${fmt.num ? fmt.num(i.quantidade) : esc(i.quantidade)} ${esc(i.unidade || "")}</td>
            <td>${i.valor_unitario ? fmt.moeda(i.valor_unitario) : "—"}</td><td>${i.valor_total ? fmt.moeda(i.valor_total) : "—"}</td><td><small>${esc(i.situacao || "")}</small></td></tr>`).join("")}</tbody></table></div>`
          : `<p class="fraco">${esc(r.aviso || "Nenhum item publicado no PNCP.")}</p>`;
      }).catch((e) => { el.innerHTML = erroTela(e); });
    } else if (abaAtual === "documentos") {
      const grupos = { esclarecimento: "Esclarecimentos", impugnacao: "Impugnações", intencao_recurso: "Intenções de recurso", recurso: "Recursos", contrarrazoes: "Contrarrazões" };
      el.innerHTML = `<section class="op-g-sec"><h3>Edital</h3>
          ${ed.tem_documento ? `<button class="botao pequeno secundario" data-doc>${icone("olho", 14)} Abrir edital</button> ` : ""}${ed.nome_arquivo ? `<small class="fraco">${esc(ed.nome_arquivo)}</small>` : ""}${!ed.tem_documento ? `<p class="fraco">Sem documento. Envie o PDF na tela do edital.</p>` : ""}</section>
        <section class="op-g-sec"><h3>Impugnações, esclarecimentos e recursos</h3>
          ${o.pecas.length ? `<ul class="op-g-lista">${o.pecas.map((p) => `<li><b>${esc(grupos[p.tipo] || p.tipo)}</b> — <a href="#/pecas/${p.id}">${esc(p.titulo)}</a> <small class="fraco">${fmt.data(p.criado_em)}</small></li>`).join("")}</ul>`
            : `<p class="fraco">Nenhuma peça para este edital.</p>`}
          <a class="botao pequeno secundario" href="#/pecas">Gerar peça</a></section>
        ${o.contratos.length ? `<section class="op-g-sec"><h3>Contrato</h3><ul class="op-g-lista">${o.contratos.map((k) => `<li><a href="#/contratos/${k.id}">Contrato ${esc(k.numero || k.id)}</a>${k.valor ? " · " + fmt.moeda(k.valor) : ""}</li>`).join("")}</ul></section>` : ""}`;
      const bd = $("[data-doc]", el); if (bd) bd.onclick = () => abrirDocumentoEdital(ed.id, bd);
    } else if (abaAtual === "concorrentes") {
      const pc = ed.possiveis_concorrentes;
      el.innerHTML = `<section class="op-g-sec"><h3>Possíveis concorrentes</h3>
          ${pc?.itens?.length ? `<ul class="op-g-lista">${pc.itens.slice(0, 8).map((x) => `<li><b>${esc(x.nome)}</b> <small class="fraco">${fmt.cnpj(x.cnpj)}</small> · ${x.vitorias} vitória(s)${x.mesmo_orgao ? " · já venceu neste órgão" : ""} ${carimboStatus(RELEVANCIA_CONC, x.relevancia)}</li>`).join("")}</ul>`
            : `<p class="fraco">Ainda não avaliado.</p>`}
          <a class="botao pequeno secundario" href="#/editais/${ed.id}">${pc ? "Ver avaliação completa" : "Avaliar possíveis concorrentes"}</a></section>
        <section class="op-g-sec"><h3>Documentos de concorrentes analisados</h3>
          ${o.concorrentes_analisados.length ? `<ul class="op-g-lista">${o.concorrentes_analisados.map((x) => `<li><b>${esc(x.concorrente?.razao_social || fmt.cnpj(x.concorrente?.cnpj))}</b> — ${x.tipo === "habilitacao" ? "Habilitação" : "Proposta"} · ${(x.resultado?.apontamentos || []).length} apontamento(s) · <a href="#/concorrentes/${x.concorrente_id}">dossiê</a></li>`).join("")}</ul>`
            : `<p class="fraco">Nenhum documento de concorrente analisado.</p>`}</section>`;
    } else if (abaAtual === "orgao") {
      el.innerHTML = `<p class="carregando">Consultando o histórico do órgão no PNCP…</p>`;
      api("GET", `/api/oportunidades/${ed.id}/historico-orgao`).then((r) => {
        el.innerHTML = `${r.nossas?.length ? `<section class="op-g-sec"><h3>Suas oportunidades neste órgão</h3><ul class="op-g-lista">${r.nossas.map((x) => `<li><a href="#/editais/${x.id}">${esc(x.numero || "Edital " + x.id)}</a> — ${esc((x.objeto || "").slice(0, 120))} ${carimbo(nomeEtapa(x.etapa), "neutro")}</li>`).join("")}</ul></section>` : ""}
          <section class="op-g-sec"><h3>Contratos recentes do órgão (PNCP)</h3>
          ${r.contratos.length ? `<ul class="op-g-lista">${r.contratos.map((x) => `<li><b>${x.data ? fmt.data(x.data) : "—"}</b> — ${esc((x.objeto || "").slice(0, 200))}${x.valor ? ` · ${fmt.moeda(x.valor)}` : ""}</li>`).join("")}</ul>`
            : `<p class="fraco">${esc(r.aviso || "Nenhum contrato encontrado.")}</p>`}</section>`;
      }).catch((e) => { el.innerHTML = erroTela(e); });
    } else {
      el.innerHTML = o.movimentos.length ? `<ol class="op-linha-tempo">${o.movimentos.map((m) => `<li class="${m.origem}">
          <small>${fmt.dataHora(m.criado_em + "Z")} · ${m.origem === "automatico" ? "automático" : esc(m.autor || "usuário")}</small>
          <div>${m.de && m.de !== m.para ? `${esc(nomeEtapa(m.de))} → <b>${esc(nomeEtapa(m.para))}</b>` : m.de ? "" : `Entrou em <b>${esc(nomeEtapa(m.para))}</b>`}</div>
          ${m.motivo ? `<div class="fraco">${esc(m.motivo)}</div>` : ""}</li>`).join("")}</ol>`
        : `<p class="fraco">Sem movimentações registradas.</p>`;
    }
  }
  desenhar(aba);
}

function nomeEtapa(codigo) { return ETAPA_NOMES_OP[codigo] || codigo; }

function pedirTexto(titulo, rotulo) {
  return new Promise((ok) => {
    let feito = false;
    const m = modal({ titulo, corpo: `<form id="f-texto"><div class="campo"><label for="txt-op">${esc(rotulo)}</label><input id="txt-op" maxlength="120" required></div></form>`,
      acoes: `<button class="botao secundario" data-fechar>Cancelar</button><button class="botao" data-ok>Salvar</button>` });
    const enviar = () => { const v = $("#txt-op", m).value.trim(); if (!v) return; feito = true; m.fechar(); ok(v); };
    $("[data-ok]", m).onclick = enviar;
    $("#f-texto", m).onsubmit = (ev) => { ev.preventDefault(); enviar(); };
    const fechar = m.fechar; m.fechar = () => { fechar(); if (!feito) ok(null); };
    m.addEventListener("click", (ev) => { if ((ev.target === m || ev.target.closest("[data-fechar]")) && !feito) ok(null); });
  });
}

// Resumo do pipeline para o Painel
async function resumoPipelineHtml() {
  try {
    const r = await api("GET", `/api/empresas/${S.empresaId}/oportunidades/resumo`);
    const ativas = r.etapas.filter((e) => !["perdida", "desistencia"].includes(e.codigo));
    const total = ativas.reduce((a, e) => a + e.quantidade, 0);
    const valor = ativas.filter((e) => !["contrato_ativo"].includes(e.codigo)).reduce((a, e) => a + e.valor, 0);
    const max = Math.max(1, ...ativas.map((e) => e.quantidade));
    return `<section class="bloco"><div class="bloco-titulo"><h2>Pipeline de oportunidades</h2><a href="#/oportunidades">Abrir o quadro</a></div>
      <p class="fraco">${total} oportunidade(s) ativa(s) · ${moedaCurta(valor)} em valor estimado no pipeline (sem contar contratos ativos)</p>
      <div class="op-funil">${ativas.map((e) => `<a href="#/oportunidades" class="op-funil-etapa" title="${esc(e.nome)}">
        <span class="op-funil-barra" style="height:${Math.round(8 + 52 * e.quantidade / max)}px"></span><b>${e.quantidade}</b><small>${esc(e.nome)}</small></a>`).join("")}</div></section>`;
  } catch { return ""; }
}
