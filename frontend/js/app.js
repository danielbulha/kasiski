// Roteador, layout com navegação por fase da licitação e telas de entrada/cadastro.
const ROTAS = [
  [/^#\/painel$/, "painel"], [/^#\/radar$/, "radar"], [/^#\/editais$/, "editais"], [/^#\/editais\/(\d+)$/, "edital"],
  [/^#\/cofre$/, "cofre"], [/^#\/concorrentes$/, "concorrentes"], [/^#\/concorrentes\/(\d+)$/, "concorrente"],
  [/^#\/pecas$/, "pecas"], [/^#\/pecas\/(\d+)$/, "peca"], [/^#\/agenda$/, "agenda"],
  [/^#\/contratos$/, "contratos"], [/^#\/contratos\/(\d+)$/, "contrato"], [/^#\/precos$/, "precos"],
  [/^#\/empresas$/, "empresas"], [/^#\/conta$/, "conta"], [/^#\/glossario$/, "glossario"], [/^#\/admin$/, "admin"],
];

const NAV = [
  ["Antes da disputa", [["#/radar", "Radar de editais", "radar"], ["#/editais", "Editais", "editais"], ["#/cofre", "Cofre de documentos", "cofre"]]],
  ["Na disputa", [["#/concorrentes", "Concorrentes", "concorrentes"], ["#/pecas", "Peças", "pecas"], ["#/agenda", "Agenda de prazos", "agenda"]]],
  ["Depois da disputa", [["#/contratos", "Contratos", "contratos"], ["#/precos", "Preços praticados", "precos"]]],
];

function layout() {
  const opcoes = S.empresas.map((e) => `<option value="${e.id}" ${e.id === S.empresaId ? "selected" : ""}>${esc(e.razao_social)}</option>`).join("");
  const rota = location.hash.split("/").slice(0, 2).join("/");
  const link = ([h, t, ic], badge) => `<a href="${h}" class="${rota === h ? "ativo" : ""}">
    <span class="rotulo">${ic ? icone(ic, 17) : ""}${esc(t)}</span>${badge ? `<span class="contador">${badge}</span>` : ""}</a>`;
  const aviso = [];
  if (S.demo) aviso.push(`<div class="faixa-aviso"><span><b>Modo demonstração.</b> As respostas de IA são exemplos. Configure as chaves de IA no servidor para análises reais.</span></div>`);
  if (S.plano?.teste_expirado) aviso.push(`<div class="faixa-aviso"><span>Seu teste grátis terminou. Seus dados continuam salvos.</span><a href="#/conta">Escolher um plano</a></div>`);
  else if (S.plano?.codigo === "trial") aviso.push(`<div class="faixa-aviso"><span>Teste grátis até ${fmt.data(S.plano.trial_fim)}: ${S.plano.uso.analises} de ${S.plano.analises} análises usadas.</span><a href="#/conta">Ver planos</a></div>`);
  return `
  <div class="topo-movel"><a class="marca" href="#/painel">${simboloMarca(22)}<strong>${esc(CERTAME.NOME)}</strong></a>
    <button id="abrir-menu" aria-label="Abrir menu">${icone("menu", 16)} Menu</button></div>
  <div class="app">
    <aside class="lateral" id="lateral">
      <a class="marca" href="#/painel">${simboloMarca(26)}<span class="texto"><strong>${esc(CERTAME.NOME)}</strong><span>public market intelligence</span></span></a>
      ${S.empresas.length ? `<div class="seletor-empresa"><label for="sel-empresa">Empresa</label>
        <select id="sel-empresa">${opcoes}</select></div>` : ""}
      <nav class="nav-grupo">${link(["#/painel", "Painel", "painel"])}</nav>
      ${NAV.map(([g, itens]) => `<nav class="nav-grupo"><span>${g}</span>${itens.map((it) => link(it, it[0] === "#/radar" ? S.resumoNav?.radar_novos : 0)).join("")}</nav>`).join("")}
      <nav class="nav-grupo"><span>Conta</span>
        ${link(["#/empresas", S.plano?.empresas > 1 ? "Empresas atendidas" : "Minha empresa", "empresa"])}
        ${link(["#/conta", "Plano e conta", "conta"])}${link(["#/glossario", "Glossário", "glossario"])}
        ${S.usuario?.admin ? link(["#/admin", "Administração", "admin"]) : ""}
      </nav>
      <div class="lateral-rodape">${esc(S.usuario?.nome || "")}<br><button id="sair">${icone("sair", 14)} Sair</button></div>
    </aside>
    <main class="principal" id="principal" tabindex="-1">${aviso.join("")}<div id="conteudo"><p class="carregando">Carregando…</p></div></main>
  </div>`;
}

async function navegar() {
  $$(".fundo-modal").forEach((m) => (m.fechar ? m.fechar() : m.remove())); // fecha modais abertos ao trocar de tela
  const hash = location.hash && location.hash !== "#" ? location.hash : "#/";
  const raiz = $("#raiz");
  if (hash === "#/" || hash === "#/inicio") {
    if (S.token) { location.hash = "#/painel"; return; }
    document.body.classList.add("publico");
    await V.inicio(raiz);
    window.scrollTo(0, 0);
    return;
  }
  document.body.classList.remove("publico");
  if (["#/entrar", "#/cadastro"].includes(hash)) {
    if (S.token) { location.hash = "#/painel"; return; }
    raiz.innerHTML = telaEntrada(hash === "#/cadastro");
    ligarEntrada(hash === "#/cadastro");
    return;
  }
  if (!S.token) { location.hash = "#/entrar"; return; }
  if (!S.usuario) {
    try { await carregarConta(); } catch (e) { raiz.innerHTML = `<div style="padding:40px">${erroTela(e)}</div>`; return; }
  }
  let view = null, params = [];
  for (const [re, nome] of ROTAS) { const m = hash.match(re); if (m) { view = nome; params = m.slice(1); break; } }
  if (!view) { location.hash = "#/painel"; return; }
  raiz.innerHTML = layout();
  ligarLayout();
  const el = $("#conteudo");
  try { await V[view](el, ...params); }
  catch (e) { el.innerHTML = erroTela(e); }
  window.scrollTo(0, 0);
  requestAnimationFrame(marcarRolagem);
}

function ligarLayout() {
  const sel = $("#sel-empresa");
  if (sel) sel.onchange = () => { S.empresaId = Number(sel.value); localStorage.setItem("certame_empresa", S.empresaId); navegar(); };
  $("#sair").onclick = () => sair();
  $("#abrir-menu").onclick = () => $("#lateral").classList.toggle("aberta");
  $$("#lateral a").forEach((a) => a.addEventListener("click", () => $("#lateral").classList.remove("aberta")));
}

// Ligado uma única vez (não a cada navegação): fecha o menu mobile ao tocar fora dele.
document.addEventListener("click", (ev) => {
  const lateral = $("#lateral");
  if (!lateral || !lateral.classList.contains("aberta")) return;
  if (lateral.contains(ev.target) || ev.target.closest("#abrir-menu")) return;
  lateral.classList.remove("aberta");
});

// Recarrega conta/plano (após ações que consomem limite) sem perder a tela
async function atualizarConta() { try { await carregarConta(); } catch { /* segue */ } }

// ---------------------------------------------------------------- entrada e cadastro
function telaEntrada(cadastro) {
  return `<div class="entrada">
    <section class="entrada-lado">
      <div class="entrada-topo"><a class="marca-completa" href="#/">${simboloMarca(30)}<span class="texto"><strong>${esc(CERTAME.NOME)}</strong><span>public market intelligence</span></span></a>
        <a class="entrada-voltar" href="#/">← Conhecer o Kasiski</a></div>
      <div>
        <p style="color:var(--ciano);font-weight:600;font-size:.95rem;margin-bottom:6px">Encontre o padrão. Descubra a oportunidade.</p>
        <h1>Participe de licitações sem perder prazo nem documento.</h1>
        <p>O Kasiski é uma plataforma de inteligência para o mercado público: monitora editais no PNCP, confere sua
        habilitação, aponta falhas dos concorrentes e redige impugnações e recursos. Cada conclusão da IA é conferida
        por um segundo modelo antes de chegar a você.</p>
        <div>${carimbo("Habilitação conferida", "neutro")}${carimbo("Prazo calculado", "neutro")}${carimbo("Verificação cruzada", "neutro")}</div>
      </div>
      <small style="color:var(--linha-forte)">Lei 14.133/2021 · dados públicos do PNCP, Receita e CGU</small>
    </section>
    <section class="entrada-form">
      <form id="form-entrada" novalidate>
        <h2>${cadastro ? "Comece seu teste de 7 dias" : "Entrar"}</h2>
        <p class="fraco">${cadastro ? "Duas análises de edital incluídas, sem cartão." : "Use o e-mail e a senha da sua conta."}</p>
        <div id="erro-entrada"></div>
        ${cadastro ? `<div class="campo"><label for="nome">Seu nome</label><input id="nome" name="nome" required autocomplete="name"></div>
          <div class="campo"><label for="nome_conta">Empresa ou escritório</label><input id="nome_conta" name="nome_conta" autocomplete="organization"></div>` : ""}
        <div class="campo"><label for="email">E-mail</label><input id="email" name="email" type="email" required autocomplete="email"></div>
        <div class="campo"><label for="senha">Senha</label><input id="senha" name="senha" type="password" required minlength="8" autocomplete="${cadastro ? "new-password" : "current-password"}">
          ${cadastro ? "<small>Mínimo de 8 caracteres.</small>" : ""}</div>
        ${cadastro ? `<div class="campo"><label for="perfil">Experiência com licitações</label>
          <select id="perfil" name="perfil"><option value="iniciante">Estou começando: quero explicações em cada tela</option>
          <option value="experiente">Já participo: prefiro telas diretas</option></select></div>` : ""}
        <button class="botao" style="width:100%" type="submit">${cadastro ? "Criar conta e começar" : "Entrar"}</button>
        <p style="margin-top:16px;text-align:center">${cadastro ? `Já tem conta? <a href="#/entrar">Entrar</a>` : `Ainda não usa? <a href="#/cadastro">Criar conta grátis</a>`}</p>
      </form>
    </section></div>`;
}

function ligarEntrada(cadastro) {
  const f = $("#form-entrada");
  f.onsubmit = async (ev) => {
    ev.preventDefault();
    const b = f.querySelector("button[type=submit]");
    await ocupado(b, "Aguarde…", async () => {
      try {
        const d = await api("POST", cadastro ? "/api/auth/registro" : "/api/auth/login", dadosForm(f));
        S.token = d.token; localStorage.setItem("certame_token", d.token);
        S.usuario = null;
        location.hash = cadastro ? "#/empresas" : "#/painel";
      } catch (e) { $("#erro-entrada").innerHTML = erroTela(e); }
    });
  };
}

window.addEventListener("hashchange", navegar);
navegar();
