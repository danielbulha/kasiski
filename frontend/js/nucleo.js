// Núcleo: estado global, chamadas à API e componentes de interface reutilizáveis.
const S = {
  token: localStorage.getItem("certame_token"),
  usuario: null, conta: null, plano: null, planos: {}, demo: false,
  empresas: [], empresaId: Number(localStorage.getItem("certame_empresa")) || null,
};
const V = {}; // views registradas pelos arquivos em js/views

// ---------------------------------------------------------------- utilidades
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const $ = (sel, raiz = document) => raiz.querySelector(sel);
const $$ = (sel, raiz = document) => [...raiz.querySelectorAll(sel)];

const fmt = {
  moeda: (v) => (v === null || v === undefined || v === "" ? "—" : Number(v).toLocaleString("pt-BR", { style: "currency", currency: "BRL" })),
  num: (v, casas = 2) => (v === null || v === undefined ? "—" : Number(v).toLocaleString("pt-BR", { maximumFractionDigits: casas })),
  data: (iso) => { if (!iso) return "—"; const d = new Date(iso.length === 10 ? iso + "T12:00" : iso); return isNaN(d) ? "—" : d.toLocaleDateString("pt-BR"); },
  dataHora: (iso) => { if (!iso) return "—"; const d = new Date(iso); return isNaN(d) ? "—" : d.toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" }); },
  cnpj: (c) => (c || "").replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, "$1.$2.$3/$4-$5"),
  dias: (iso) => {
    if (!iso) return null;
    const alvo = new Date(iso.length === 10 ? iso + "T23:59" : iso); const hoje = new Date();
    return Math.ceil((alvo.setHours(0, 0, 0, 0) - hoje.setHours(0, 0, 0, 0)) / 86400000);
  },
  prazo: (iso) => {
    const n = fmt.dias(iso);
    if (n === null) return "";
    if (n < 0) return `venceu há ${-n} dia${n === -1 ? "" : "s"}`;
    if (n === 0) return "vence hoje";
    if (n === 1) return "vence amanhã";
    return `em ${n} dias`;
  },
  paraInput: (iso) => (iso ? String(iso).slice(0, 10) : ""),
  paraInputHora: (iso) => (iso ? String(iso).slice(0, 16) : ""),
};

function carimbo(texto, tipo = "neutro", grande = false) {
  return `<span class="carimbo carimbo-${tipo}${grande ? " carimbo-grande" : ""}">${esc(texto)}</span>`;
}

function carimboPrazo(iso) {
  const n = fmt.dias(iso);
  if (n === null) return "";
  if (n < 0) return carimbo("Vencido", "erro");
  if (n <= 3) return carimbo(fmt.prazo(iso), "erro");
  if (n <= 10) return carimbo(fmt.prazo(iso), "aviso");
  return carimbo(fmt.prazo(iso), "neutro");
}

function guia(texto) {
  if (!S.usuario || !S.usuario.modo_guiado) return "";
  return `<details class="guia"><summary>Como funciona esta tela</summary>${texto}</details>`;
}

function vazio(titulo, texto, botaoHtml = "") {
  return `<div class="vazio"><h3>${esc(titulo)}</h3><p>${esc(texto)}</p>${botaoHtml}</div>`;
}

function toast(msg, tipo = "info") {
  const t = document.createElement("div");
  t.className = `toast ${tipo}`;
  t.setAttribute("role", "status");
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), tipo === "erro" ? 7000 : 3500);
}

function erroTela(e) {
  const upgrade = e.status === 402
    ? ` <a href="#/conta">Ver planos</a>` : "";
  return `<div class="aviso erro">${esc(e.message)}${upgrade}</div>`;
}

function avisarErro(e) {
  if (e.status === 402) {
    modal({
      titulo: "Recurso fora do seu plano",
      corpo: `<p>${esc(e.message)}</p>`,
      acoes: `<a class="botao" href="#/conta" data-fechar>Ver planos</a>`,
    });
  } else toast(e.message, "erro");
}

function modal({ titulo, corpo, acoes = "", largo = false }) {
  const fundo = document.createElement("div");
  fundo.className = "fundo-modal";
  fundo.innerHTML = `<div class="modal${largo ? " largo" : ""}" role="dialog" aria-modal="true" aria-label="${esc(titulo)}">
    <div class="bloco-titulo"><h2>${esc(titulo)}</h2><button class="botao texto" data-fechar aria-label="Fechar">Fechar</button></div>
    <div class="modal-corpo">${corpo}</div>
    ${acoes ? `<div class="modal-rodape">${acoes}</div>` : ""}</div>`;
  const fechar = () => { fundo.remove(); document.removeEventListener("keydown", esc_); };
  const esc_ = (ev) => { if (ev.key === "Escape") fechar(); };
  fundo.addEventListener("click", (ev) => { if (ev.target === fundo || ev.target.closest("[data-fechar]")) fechar(); });
  document.addEventListener("keydown", esc_);
  document.body.appendChild(fundo);
  const primeiro = fundo.querySelector("input, select, textarea");
  if (primeiro) primeiro.focus();
  fundo.fechar = fechar;
  return fundo;
}

function confirmar(texto, rotulo = "Confirmar") {
  return new Promise((ok) => {
    const m = modal({ titulo: "Confirme", corpo: `<p>${esc(texto)}</p>`,
      acoes: `<button class="botao secundario" data-fechar>Cancelar</button><button class="botao perigo" data-sim>${esc(rotulo)}</button>` });
    m.querySelector("[data-sim]").onclick = () => { m.fechar(); ok(true); };
  });
}

function dadosForm(form) {
  const d = {};
  new FormData(form).forEach((v, k) => { if (!(v instanceof File)) d[k] = v; });
  $$("input[type=checkbox]", form).forEach((c) => { d[c.name] = c.checked; });
  return d;
}

async function ocupado(botao, texto, fn) {
  const original = botao.innerHTML;
  botao.disabled = true;
  botao.textContent = texto;
  try { return await fn(); } finally { botao.disabled = false; botao.innerHTML = original; }
}

// ---------------------------------------------------------------- API
async function api(metodo, caminho, corpo) {
  const opt = { method: metodo, headers: {} };
  if (S.token) opt.headers.Authorization = "Bearer " + S.token;
  if (corpo instanceof FormData) opt.body = corpo;
  else if (corpo !== undefined) { opt.headers["Content-Type"] = "application/json"; opt.body = JSON.stringify(corpo); }
  let r;
  try { r = await fetch(CERTAME.API_URL + caminho, opt); }
  catch (e) {
    reportarErro({ tipo: "rede", mensagem: `Sem conexão com o servidor (${e.message || "falha de rede"})`, chamada: caminho.split("?")[0], metodo });
    throw new Error("Sem conexão com o servidor. Verifique a internet e tente de novo.");
  }
  if (r.status >= 500 && !caminho.startsWith("/api/logs")) {
    const copia = r.clone();
    copia.text().then((t) => reportarErro({ tipo: "servidor", mensagem: `Erro ${r.status} em ${metodo} ${caminho.split("?")[0]}: ${t.slice(0, 300)}`,
      chamada: caminho.split("?")[0], metodo, status: r.status })).catch(() => {});
  }
  if (r.status === 401 && S.token && !caminho.startsWith("/api/auth")) { sair("#/entrar"); throw new Error("Sua sessão expirou. Entre novamente."); }
  const ct = r.headers.get("content-type") || "";
  if (!ct.includes("json")) { if (!r.ok) throw new Error(`Erro ${r.status} no servidor.`); return r; }
  const d = await r.json();
  if (!r.ok) { const e = new Error(d.erro || "Não foi possível concluir a operação."); e.status = r.status; e.codigo = d.codigo; throw e; }
  return d;
}

async function baixar(caminho, nome) {
  const r = await api("GET", caminho);
  const blob = await r.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = nome || "arquivo";
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}

function sair(destino = "#/") {
  localStorage.removeItem("certame_token");
  S.token = null; S.usuario = null;
  location.hash = destino;
}

async function carregarConta() {
  const d = await api("GET", "/api/conta");
  Object.assign(S, { usuario: d.usuario, conta: d.conta, plano: d.plano, planos: d.planos, demo: d.modo_demonstracao,
    cobranca: d.cobranca || { online: false, anual_meses_pagos: 10 } });
  S.empresas = await api("GET", "/api/empresas");
  if (!S.empresas.find((e) => e.id === S.empresaId)) S.empresaId = S.empresas[0]?.id || null;
  if (S.empresaId) localStorage.setItem("certame_empresa", S.empresaId);
  S.resumoNav = { radar_novos: 0 };
  if (S.empresaId) {
    try { const p = await api("GET", `/api/painel?empresa_id=${S.empresaId}`); S.resumoNav.radar_novos = p.radar_novos || 0; }
    catch { /* badge é um extra — uma falha aqui não deve travar a navegação */ }
  }
}

const empresaAtual = () => S.empresas.find((e) => e.id === S.empresaId);

function exigirEmpresa() {
  if (S.empresaId) return "";
  return vazio("Cadastre a primeira empresa", "Tudo no Kasiski é organizado por CNPJ: editais, documentos, prazos e contratos.",
    `<a class="botao" href="#/empresas">Cadastrar empresa</a>`);
}

// Rótulos usados em várias telas
const ROTULOS = {
  statusEdital: { acompanhando: "Acompanhando", participando: "Participando", ganho: "Ganho", perdido: "Perdido", descartado: "Descartado" },
  decisao: { participar: ["Participar", "ok"], participar_com_ressalvas: ["Com ressalvas", "aviso"], nao_participar: ["Não participar", "erro"] },
  checklist: { atende: ["Atende", "ok"], falta: ["Falta", "erro"], vencido: ["Vencido", "erro"], verificar: ["Verificar", "aviso"] },
  forca: { forte: ["Forte", "erro"], medio: ["Médio", "aviso"], fraco: ["Fraco", "neutro"] },
  gravidade: { alta: ["Alta", "erro"], media: ["Média", "aviso"], baixa: ["Baixa", "neutro"],
    alto: ["Alto", "erro"], medio: ["Médio", "aviso"], baixo: ["Baixo", "neutro"] },
  categoriaDoc: { juridica: "Jurídica", fiscal: "Fiscal", trabalhista: "Trabalhista", economica: "Econômico-financeira", tecnica: "Técnica", declaracao: "Declarações", setorial: "Setorial/regulatória", outro: "Outros" },
  tipoObjeto: { obra: "Obra", servico_engenharia: "Serviço de engenharia", servico_comum: "Serviço comum",
    servico_continuado: "Serviço continuado", fornecimento: "Fornecimento", fornecimento_continuado: "Registro de preços",
    outro: "Outro" },
  segmento: { saude: "Saúde", educacao: "Educação", ti: "TI", alimentacao: "Alimentação", transporte: "Transporte",
    limpeza: "Limpeza e conservação", seguranca: "Segurança", obras: "Obras", outro: "Outro" },
  segmentosEmpresa: [["obras", "Obras"], ["servicos_comuns", "Serviços comuns"], ["servicos_continuados", "Serviços continuados (mão de obra)"],
    ["fornecimento", "Fornecimento de bens"], ["saude", "Saúde"], ["educacao", "Educação"], ["ti", "TI"],
    ["alimentacao", "Alimentação"], ["transporte", "Transporte"], ["seguranca", "Segurança"], ["outro", "Outro"]],
};

function carimboStatus(mapa, chave) {
  const v = mapa[chave];
  return v ? carimbo(v[0], v[1]) : carimbo(chave || "—", "neutro");
}

function revisorHtml(v) {
  if (!v) return "";
  const estado = v.confirmado === true ? carimbo("Confirmado", "ok") : v.confirmado === false ? carimbo("Não confirmado", "erro") : carimbo("Sem revisão", "neutro");
  return `<div class="revisor">Verificação cruzada ${estado} ${v.modelo ? `<small>(${esc(v.modelo)})</small>` : ""} ${esc(v.comentario || "")}</div>`;
}

// Marca tabelas com conteúdo além da largura visível para mostrar o gradiente de "arraste para o lado".
// O gradiente some quando o usuário já rolou até o fim. Um observer cobre telas trocadas por
// navegação e conteúdo injetado em modais, sem precisar chamar isto manualmente em cada view.
function marcarRolagem() {
  $$(".tabela-rolagem").forEach((el) => {
    el.classList.toggle("tem-mais", el.scrollWidth - el.clientWidth - el.scrollLeft > 2);
    if (!el.dataset.rolagemLigada) { el.dataset.rolagemLigada = "1"; el.addEventListener("scroll", () => marcarRolagem(), { passive: true }); }
  });
}
window.addEventListener("resize", () => requestAnimationFrame(marcarRolagem));
new MutationObserver(() => requestAnimationFrame(marcarRolagem)).observe(document.body, { childList: true, subtree: true });

// ---------------------------------------------------------------- funil: origem do visitante
// Um id aleatório por navegador (sem dado pessoal) liga a visita ao cadastro. A origem vem do
// utm_source/utm_campaign do link (ex.: ?utm_source=instagram) ou do site que trouxe o visitante.
const FUNIL = (() => {
  const ler = (k) => { try { return localStorage.getItem(k); } catch { return null; } };
  const gravar = (k, v) => { try { localStorage.setItem(k, v); } catch { /* navegação privada */ } };
  let vid = ler("kasiski_visitante");
  if (!vid) { vid = (crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random().toString(16).slice(2)).slice(0, 36); gravar("kasiski_visitante", vid); }
  const q = new URLSearchParams(location.search);
  let ref = "";
  try { ref = document.referrer ? new URL(document.referrer).hostname : ""; } catch { /* ignora */ }
  if (ref === location.hostname) ref = "";
  // Primeiro toque vence: não sobrescreve a origem já registrada neste navegador
  if (!ler("kasiski_origem") && (q.get("utm_source") || ref)) gravar("kasiski_origem", q.get("utm_source") || ref);
  if (!ler("kasiski_campanha") && q.get("utm_campaign")) gravar("kasiski_campanha", q.get("utm_campaign"));
  return { visitante: vid, origem: () => ler("kasiski_origem") || "", campanha: () => ler("kasiski_campanha") || "" };
})();

const _rastreados = new Set();
function rastrear(tipo) {
  if (S.token || _rastreados.has(tipo)) return; // só visitantes; uma vez por carregamento
  _rastreados.add(tipo);
  fetch(CERTAME.API_URL + "/api/eventos", {
    method: "POST", headers: { "Content-Type": "application/json" }, keepalive: true,
    body: JSON.stringify({ tipo, visitante: FUNIL.visitante, origem: FUNIL.origem(), campanha: FUNIL.campanha(),
      pagina: location.hash || "#/", referencia: document.referrer || "" }),
  }).catch(() => { /* funil é acessório */ });
}
document.addEventListener("click", (ev) => { if (ev.target.closest('a[href="#/cadastro"]')) rastrear("cta"); });

// ---------------------------------------------------------------- registro de erros (área Logs do admin)
// Envia ao servidor erros de JavaScript e falhas de chamada que o usuário encontrou. Sem dados de formulário.
const _errosEnviados = new Set();
function reportarErro(e) {
  try {
    const chave = `${e.tipo}|${e.mensagem}`.slice(0, 300);
    if (_errosEnviados.has(chave) || _errosEnviados.size > 25) return; // uma vez por erro, no máximo 25 por página
    _errosEnviados.add(chave);
    const cab = { "Content-Type": "application/json" };
    if (S.token) cab.Authorization = "Bearer " + S.token;
    fetch(CERTAME.API_URL + "/api/logs", { method: "POST", headers: cab, keepalive: true,
      body: JSON.stringify({ ...e, tela: location.hash || "#/", mensagem: String(e.mensagem || "").slice(0, 1000), pilha: String(e.pilha || "").slice(0, 8000) }) }).catch(() => {});
  } catch { /* o registro de erro nunca pode quebrar a tela */ }
}
window.addEventListener("error", (ev) => {
  if (!ev.message) return;
  reportarErro({ tipo: "javascript", mensagem: `${ev.message} (${String(ev.filename || "").split("/").pop()}:${ev.lineno || 0})`, pilha: ev.error?.stack || "" });
});
window.addEventListener("unhandledrejection", (ev) => {
  const r = ev.reason || {};
  if (r.status && r.status < 500) return; // erros de validação/plano já mostrados ao usuário
  reportarErro({ tipo: "javascript", mensagem: `Promessa não tratada: ${r.message || String(r)}`, pilha: r.stack || "" });
});
