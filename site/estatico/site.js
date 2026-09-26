// Site público do Kasiski: menu, formulários das ferramentas gratuitas e eventos do Data Layer.
(() => {
  const API = (window.CERTAME && CERTAME.API_URL) || "";
  const K = window.Kasiski || { evento() {}, visitante: "", toque: () => null };
  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const moeda = (v) => (v || v === 0) ? Number(v).toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 }) : "—";
  const dataBr = (v) => { try { const d = new Date(v); return isNaN(d) ? "—" : d.toLocaleString("pt-BR", { dateStyle: "short", timeStyle: v.length > 10 ? "short" : undefined }); } catch { return "—"; } };
  // cookie no domínio-pai: o que a pessoa digitou aqui pré-preenche o cadastro no app (2 dias)
  const gravar = (k, v) => { if (K.gravar) K.gravar(k, v, 2); else try { localStorage.setItem(k, v); } catch { /* ok */ } };
  const APP = (window.CERTAME && CERTAME.APP_URL) || "https://app.kasiski.com.br";

  // símbolo da marca (usado pelo chat)
  window.simboloMarca = window.simboloMarca || ((t = 28) => { const s = document.querySelector(".s-simbolo"); if (!s) return "≡"; const c = s.cloneNode(true); c.setAttribute("width", t); c.setAttribute("height", Math.round(t * 308 / 375)); return c.outerHTML; });

  // links do app: em produção já vêm prontos; em desenvolvimento/prévia apontam para o APP_URL da configuração
  if (APP !== "https://app.kasiski.com.br") $$('a[href^="https://app.kasiski.com.br"]').forEach((a) => { a.href = a.getAttribute("href").replace("https://app.kasiski.com.br", APP); });

  // planos: confere preços e limites na API (fonte oficial: backend/planos.py)
  if (document.querySelector("[data-plano]")) fetch(API + "/api/planos").then((r) => r.json()).then((d) => {
    const qtd = (n, s1, p) => `${n} ${n === 1 ? s1 : p}`;
    const txt = { empresas: (v) => qtd(v.empresas, "empresa (CNPJ)", "empresas (CNPJs)"), analises: (v) => `${qtd(v.analises, "análise", "análises")} de edital por mês`,
      concorrentes: (v) => (v.concorrentes ? `${qtd(v.concorrentes, "análise", "análises")} de concorrente por mês` : "Análise de concorrentes"),
      possiveis: (v) => `${qtd(v.possiveis || 0, "avaliação", "avaliações")} de possíveis concorrentes por mês`,
      contratos: (v) => (v.contratos ? `Gestão de contratos com IA (até ${v.contratos})` : "Gestão de contratos") };
    $$("[data-plano]").forEach((c) => {
      const v = d.planos && d.planos[c.dataset.plano]; if (!v) return;
      const pr = $("[data-preco]", c); if (pr) pr.textContent = "R$ " + Number(v.preco).toLocaleString("pt-BR", { maximumFractionDigits: 0 });
      $$("[data-campo]", c).forEach((li) => { const f = txt[li.dataset.campo]; if (f) li.lastElementChild.textContent = f(v); });
    });
    if (d.planos && d.planos.trial) $$("[data-trial-analises]").forEach((x) => { x.textContent = d.planos.trial.analises; });
  }).catch(() => { /* fica com os valores gerados */ });

  // ------------------------------------------------------------ navegação
  const btn = $(".s-menu-btn"), nav = $("#s-nav");
  if (btn && nav) btn.onclick = () => { const aberto = nav.classList.toggle("aberto"); btn.setAttribute("aria-expanded", String(aberto)); };
  $$(".s-drop > button").forEach((b) => b.onclick = (ev) => {
    ev.stopPropagation();
    const d = b.parentElement, aberto = d.classList.contains("aberto");
    $$(".s-drop").forEach((x) => x.classList.remove("aberto"));
    if (!aberto) d.classList.add("aberto");
  });
  document.addEventListener("click", () => $$(".s-drop").forEach((x) => x.classList.remove("aberto")));

  K.evento("page_view", { pagina: location.pathname, page_title: document.title });

  // ------------------------------------------------------------ util de formulários
  const iniciados = new Set();
  $$("form[data-form]").forEach((f) => f.addEventListener("focusin", () => {
    if (iniciados.has(f)) return; iniciados.add(f);
    K.evento("lead_form_start", { form: f.dataset.form, pagina: location.pathname });
  }));
  async function enviar(caminho, corpo) {
    const opcoes = { method: "POST" };
    if (corpo instanceof FormData) opcoes.body = corpo;
    else { opcoes.headers = { "Content-Type": "application/json" }; opcoes.body = JSON.stringify(corpo); }
    const r = await fetch(API + caminho, opcoes);
    const d = await r.json().catch(() => ({}));
    if (!r.ok) { const e = new Error(d.erro || "Não foi possível enviar agora. Tente de novo."); e.codigo = d.codigo; throw e; }
    return d;
  }
  const msg = (f, t, tipo = "erro") => { const m = $(".s-msg", f); if (m) { m.textContent = t; m.className = "s-msg " + tipo; } };
  const ocupar = (f, sim, texto) => { const b = $("button[type=submit]", f); if (!b) return; if (sim) { b.dataset.t = b.textContent; b.textContent = texto; b.disabled = true; } else { b.textContent = b.dataset.t || b.textContent; b.disabled = false; } };
  const comum = (dados) => ({ ...dados, visitante: K.visitante, toque: K.toque ? K.toque() : null });

  // Turnstile (opcional)
  if (window.CERTAME?.TURNSTILE_SITEKEY && $(".s-turnstile")) {
    window.kasiskiTurnstile = () => $$(".s-turnstile").forEach((el) => window.turnstile.render(el, { sitekey: CERTAME.TURNSTILE_SITEKEY }));
    const s = document.createElement("script");
    s.src = "https://challenges.cloudflare.com/turnstile/v0/api.js?onload=kasiskiTurnstile"; s.async = true; document.head.appendChild(s);
  }
  const turnstile = (f) => { const i = $("[name='cf-turnstile-response']", f); return i ? i.value : ""; };

  // ------------------------------------------------------------ analisador de edital
  $$("form[data-form=analisar]").forEach((f) => {
    const inp = $("input[type=file]", f), rotulo = $("[data-arquivo]", f), caixa = $(".s-upload", f);
    const mostrar = () => { rotulo.textContent = inp.files[0] ? `${inp.files[0].name} · ${(inp.files[0].size / 1048576).toFixed(1)} MB` : ""; caixa.classList.toggle("com-arquivo", !!inp.files[0]); };
    inp.onchange = mostrar;
    ["dragover", "dragenter"].forEach((t) => caixa.addEventListener(t, (ev) => { ev.preventDefault(); caixa.classList.add("arrastando"); }));
    ["dragleave", "drop"].forEach((t) => caixa.addEventListener(t, () => caixa.classList.remove("arrastando")));
    caixa.addEventListener("drop", (ev) => { ev.preventDefault(); if (ev.dataTransfer.files.length) { inp.files = ev.dataTransfer.files; mostrar(); } });
    f.onsubmit = async (ev) => {
      ev.preventDefault();
      const arq = inp.files[0];
      if (!arq) return msg(f, "Escolha o PDF do edital.");
      if (!/\.pdf$/i.test(arq.name)) return msg(f, "Envie o edital em PDF.");
      if (arq.size > 15 * 1048576) return msg(f, "O PDF passa de 15 MB. Envie só o edital, sem anexos pesados.");
      if (!f.nome.value.trim() || !/^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/.test(f.email.value.trim())) return msg(f, "Informe seu nome e um e-mail válido.");
      if (!f.consentimento.checked) return msg(f, "Para continuar, aceite a Política de Privacidade.");
      const fd = new FormData(f);
      fd.set("consentimento", "1"); fd.set("newsletter", f.newsletter?.checked ? "1" : "0");
      fd.set("visitante", K.visitante); fd.set("toque", JSON.stringify(K.toque ? K.toque() : {}));
      const ts = turnstile(f); if (ts) fd.set("cf-turnstile-response", ts);
      ocupar(f, true, "Enviando o edital…"); msg(f, "", "");
      K.evento("tool_started", { ferramenta: "analisar_edital", origem: f.dataset.origem });
      try {
        const d = await enviar("/api/public/analisar-edital", fd);
        gravar("kasiski_cadastro", JSON.stringify({ nome: f.nome.value.trim(), email: f.email.value.trim() }));
        K.evento("generate_lead", { lead_magnet: "analisar_edital", origem: f.dataset.origem });
        f.hidden = true;
        acompanhar(d.id, f.nextElementSibling);
        try { history.replaceState(null, "", location.pathname + "?r=" + d.id); } catch { /* ok */ }
      } catch (e) { msg(f, e.message); ocupar(f, false); }
    };
  });

  function acompanhar(id, alvo) {
    alvo.hidden = false;
    alvo.innerHTML = `<div class="s-processando"><span class="s-spinner" aria-hidden="true"></span><div><b>Analisando o edital…</b><p data-etapa>Isso leva de 1 a 3 minutos. Enviaremos o resultado também por e-mail.</p></div></div>`;
    const passo = async () => {
      let d;
      try { d = await (await fetch(`${API}/api/public/analisar-edital/${encodeURIComponent(id)}`)).json(); } catch { setTimeout(passo, 5000); return; }
      if (d.status === "processando") { const e = $("[data-etapa]", alvo); if (e && d.etapa) e.textContent = d.etapa + "…"; setTimeout(passo, 3000); return; }
      if (d.status === "erro" || d.erro) { alvo.innerHTML = `<div class="s-aviso erro">${esc(d.erro || "Não conseguimos analisar este edital.")}</div>`; return; }
      K.evento("tool_completed", { ferramenta: "analisar_edital", nota: d.nota });
      alvo.innerHTML = resultadoEdital(d);
      alvo.scrollIntoView({ behavior: "smooth", block: "start" });
    };
    passo();
  }

  function resultadoEdital(d) {
    const e = d.edital || {}, p = d.pontos || {}, docs = d.documentos || {}, prazo = d.prazo || {};
    const cor = d.nota >= 75 ? "ok" : d.nota >= 50 ? "aviso" : "erro";
    const g = { alta: "Alta", media: "Média", baixa: "Baixa" };
    const linha = (ok, t) => `<li class="${ok === true ? "ok" : ok === false ? "aviso" : "neutro"}"><span aria-hidden="true">${ok === true ? "✓" : ok === false ? "⚠" : "•"}</span><div>${t}</div></li>`;
    const cats = Object.entries(docs.por_categoria || {}).map(([k, v]) => `${v} ${({ juridica: "jurídico", fiscal: "fiscal", trabalhista: "trabalhista", economica: "econômico", tecnica: "técnico", setorial: "setorial", declaracao: "declaração" })[k] || k}`).join(" · ");
    const cad = `${APP}/#/cadastro`;
    return `<div class="s-res">
      ${d.demonstracao ? `<p class="s-aviso">Resultado de demonstração (servidor sem chave de IA).</p>` : ""}
      <div class="s-res-topo"><div class="s-nota-circ ${cor}" style="--v:${d.nota || 0}"><b>${d.nota ?? "—"}</b><small>/100</small></div>
        <div><small class="s-sobre">Nota de participação</small><h2>${esc(e.objeto || d.nome_arquivo || "Edital analisado")}</h2>
          <p>${esc([e.orgao, e.modalidade, e.numero].filter(Boolean).join(" · "))}</p>
          <p>${[e.valor_estimado ? "Valor estimado: <b>" + moeda(e.valor_estimado) + "</b>" : "", e.data_abertura ? "Sessão: <b>" + esc(dataBr(e.data_abertura)) + "</b>" : ""].filter(Boolean).join(" · ")}</p></div></div>
      <ul class="s-checks">
        ${linha(true, `<b>${docs.total || 0} documentos</b> de habilitação identificados${cats ? ` <small>(${esc(cats)})</small>` : ""}`)}
        ${linha(p.total ? false : true, `<b>${p.total || 0} ponto(s) de atenção</b>${p.altos ? ` — ${p.altos} de gravidade alta` : ""}`)}
        ${linha(d.documentos_criticos ? false : true, `<b>${d.documentos_criticos || 0} documento(s) crítico(s)</b> (exigência incomum ou difícil de obter)`)}
        ${linha(prazo.suficiente, prazo.dias === null || prazo.dias === undefined ? "Data da sessão não identificada no texto" : prazo.suficiente ? `Prazo suficiente: <b>${prazo.dias} dias</b> até a sessão` : `Prazo curto: <b>${prazo.dias} dia(s)</b> até a sessão`)}
      </ul>
      ${d.resumo ? `<p class="s-res-resumo">${esc(d.resumo)}</p>` : ""}
      ${p.primeiro ? `<h3>Principal ponto de atenção</h3><div class="s-ponto ${esc(p.primeiro.gravidade)}"><header><b>${esc(p.primeiro.titulo)}</b><span>${g[p.primeiro.gravidade] || ""}</span></header>
        <p>${esc(p.primeiro.explicacao || "")}</p>${p.primeiro.pagina ? `<small>Página ${esc(p.primeiro.pagina)} do edital</small>` : ""}</div>` : ""}
      ${(p.bloqueados || []).length ? `<h3>Outros ${p.bloqueados.length} ponto(s)</h3><div class="s-bloqueados">${p.bloqueados.map((b) => `<div class="s-ponto bloqueado ${esc(b.gravidade)}"><header><b>████████████ ██████</b><span>${g[b.gravidade] || ""}</span></header><p>██████ ████████ ██████ ███████████ ████ ██████████.</p></div>`).join("")}
        <div class="s-cadeado"><b>Veja a análise completa</b><p>Todos os pontos com fundamento, o checklist de habilitação conferido com os documentos da sua empresa e a recomendação de participar ou não.</p>
          <a class="s-botao s-botao-grande" href="${cad}" data-cta="ver_analise_completa">Criar conta grátis e ver tudo</a>
          <small>Use o mesmo e-mail: o edital é importado e a análise completa roda de cortesia.</small></div></div>`
        : `<div class="s-cadeado s-cadeado-solto"><a class="s-botao s-botao-grande" href="${cad}" data-cta="ver_analise_completa">Criar conta grátis e ver a análise completa</a></div>`}
    </div>`;
  }
  const r0 = new URLSearchParams(location.search).get("r");
  const alvoInicial = $("form[data-form=analisar]");
  if (r0 && alvoInicial) { alvoInicial.hidden = true; acompanhar(r0, alvoInicial.nextElementSibling); }

  // ------------------------------------------------------------ consulta de concorrente
  $$("form[data-form=concorrente]").forEach((f) => {
    const c = f.cnpj;
    c.addEventListener("input", () => {
      const n = c.value.replace(/\D/g, "").slice(0, 14);
      c.value = n.replace(/^(\d{2})(\d)/, "$1.$2").replace(/^(\d{2})\.(\d{3})(\d)/, "$1.$2.$3").replace(/\.(\d{3})(\d)/, ".$1/$2").replace(/(\d{4})(\d)/, "$1-$2");
    });
    f.onsubmit = async (ev) => {
      ev.preventDefault();
      if (c.value.replace(/\D/g, "").length !== 14) return msg(f, "Informe os 14 dígitos do CNPJ.");
      ocupar(f, true, "Consultando fontes públicas…"); msg(f, "", "");
      K.evento("tool_started", { ferramenta: "consultar_concorrente" });
      try {
        const d = await enviar("/api/public/concorrente", comum({ cnpj: c.value, site: f.site.value, "cf-turnstile-response": turnstile(f) }));
        K.evento("competitor_search", {});
        K.evento("tool_completed", { ferramenta: "consultar_concorrente" });
        const alvo = f.nextElementSibling; alvo.hidden = false; alvo.innerHTML = resultadoConcorrente(d);
        alvo.scrollIntoView({ behavior: "smooth", block: "start" });
      } catch (e) { msg(f, e.message); }
      ocupar(f, false);
    };
  });

  function resultadoConcorrente(d) {
    if (!d.encontrado && !d.razao_social) return `<div class="s-aviso">Não encontramos este CNPJ na Receita Federal agora. Confira o número ou tente de novo em instantes.</div>`;
    const bloq = (t) => `<div class="s-linha-bloq"><span>${esc(t)}</span><b>██████████</b><em>bloqueado</em></div>`;
    const sanc = d.sancoes === null || d.sancoes === undefined ? "Consulta indisponível agora" : d.sancoes ? `<b class="s-alerta">${d.sancoes} registro(s)</b>` : "Nenhuma encontrada";
    return `<div class="s-res s-res-conc"><small class="s-sobre">${esc(d.cnpj.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, "$1.$2.$3/$4-$5"))}</small>
      <h2>${esc(d.razao_social || "")}</h2>${d.nome_fantasia ? `<p>${esc(d.nome_fantasia)}</p>` : ""}
      <dl class="s-dl"><div><dt>Situação</dt><dd>${esc(d.situacao || "—")}</dd></div><div><dt>Porte</dt><dd>${esc(d.porte || "—")}</dd></div>
        <div><dt>Sede</dt><dd>${esc([d.municipio, d.uf].filter(Boolean).join("/") || "—")}</dd></div><div><dt>Atividade principal</dt><dd>${esc(d.cnae_principal || "—")}</dd></div>
        <div><dt>Contratos públicos encontrados</dt><dd><b>${d.contratos}</b>${d.valor_contratos ? ` · ${moeda(d.valor_contratos)}` : ""}</dd></div>
        <div><dt>Atas de registro de preços</dt><dd><b>${d.atas}</b></dd></div><div><dt>Órgãos contratantes</dt><dd><b>${d.orgaos}</b>${d.ufs?.length ? ` · ${esc(d.ufs.join(", "))}` : ""}</dd></div>
        <div><dt>Sanções</dt><dd>${sanc}${d.fontes_sancoes?.length ? ` <small>(${esc(d.fontes_sancoes.join(", "))})</small>` : ""}</dd></div></dl>
      <div class="s-bloqueados">${bloq("Histórico de licitações e preços vencedores")}${bloq("Atestados encontrados")}${bloq("Inabilitações em outros certames")}${bloq("Pontos de ataque para recurso")}
        <div class="s-cadeado"><b>Dossiê completo do concorrente</b><p>Histórico detalhado, atas e decisões do PNCP, documentos de outros certames e sugestões de recurso consolidados pela IA.</p>
          <a class="s-botao s-botao-grande" href="${APP}/#/cadastro" data-cta="ver_dossie">Criar conta e ver o dossiê</a></div></div></div>`;
  }

  // ------------------------------------------------------------ newsletter
  $$("form[data-form=newsletter]").forEach((f) => f.onsubmit = async (ev) => {
    ev.preventDefault();
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/.test(f.email.value.trim())) return msg(f, "Informe um e-mail válido.");
    if (!f.consentimento.checked) return msg(f, "Aceite a Política de Privacidade para assinar.");
    ocupar(f, true, "Enviando…");
    try {
      const d = await enviar("/api/public/newsletter", comum({ email: f.email.value.trim(), nome: f.nome?.value || "", consentimento: true, site: f.site?.value || "" }));
      K.evento("generate_lead", { lead_magnet: "newsletter" });
      msg(f, d.confirmar ? "Quase lá: enviamos um e-mail para você confirmar a inscrição." : "Inscrição confirmada. Até a próxima edição!", "ok");
      f.reset();
    } catch (e) { msg(f, e.message); }
    ocupar(f, false);
  });
  const st = $("[data-status-news]");
  if (st) {
    const q = new URLSearchParams(location.search);
    const t = q.get("confirmado") ? "Inscrição confirmada! Você vai receber o Kasiski Intelligence toda semana." : q.get("saiu") ? "Pronto: você não vai mais receber nossos e-mails de dicas e newsletter." : q.get("erro") ? "Link inválido ou expirado." : "";
    if (t) { st.hidden = false; st.textContent = t; st.className = "s-aviso " + (q.get("erro") ? "erro" : "ok"); }
  }

  // ------------------------------------------------------------ formulário de contato (consultorias etc.)
  $$("form[data-form=lead]").forEach((f) => f.onsubmit = async (ev) => {
    ev.preventDefault();
    if (!f.nome.value.trim() || !/^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/.test(f.email.value.trim())) return msg(f, "Informe seu nome e um e-mail válido.");
    if (!f.consentimento.checked) return msg(f, "Aceite a Política de Privacidade para enviar.");
    ocupar(f, true, "Enviando…");
    try {
      const dados = Object.fromEntries(new FormData(f).entries());
      await enviar("/api/public/leads", comum({ ...dados, consentimento: true, lead_magnet: f.dataset.magnet || "contato" }));
      K.evento("generate_lead", { lead_magnet: f.dataset.magnet || "contato" });
      gravar("kasiski_cadastro", JSON.stringify({ nome: f.nome.value.trim(), email: f.email.value.trim() }));
      f.innerHTML = `<div class="s-aviso ok"><b>Recebemos seu contato.</b> Retornamos em até 1 dia útil. Enquanto isso, você já pode <a href="${APP}/#/cadastro">testar o Kasiski grátis</a>.</div>`;
    } catch (e) { msg(f, e.message); ocupar(f, false); }
  });

  // ------------------------------------------------------------ filtro de categorias (Inteligência)
  $$(".s-cats button").forEach((b) => b.onclick = () => {
    $$(".s-cats button").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
    $$(".s-card-artigo").forEach((c) => { c.hidden = !!b.dataset.cat && c.dataset.categoria !== b.dataset.cat; });
  });
})();
