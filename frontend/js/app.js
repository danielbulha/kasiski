// Roteador, layout com navegação por fase da licitação e telas de entrada/cadastro.
const ROTAS = [
  [/^#\/painel$/, "painel"], [/^#\/oportunidades$/, "oportunidades"], [/^#\/oportunidades\/(\d+)$/, "oportunidades"], [/^#\/radar$/, "radar"], [/^#\/editais$/, "editais"], [/^#\/editais\/(\d+)$/, "edital"],
  [/^#\/cofre$/, "cofre"], [/^#\/concorrentes$/, "concorrentes"], [/^#\/concorrentes\/(\d+)$/, "concorrente"],
  [/^#\/pecas$/, "pecas"], [/^#\/pecas\/advogado$/, "advogado"], [/^#\/pecas\/(\d+)$/, "peca"], [/^#\/agenda$/, "agenda"],
  [/^#\/contratos$/, "contratos"], [/^#\/contratos\/(\d+)$/, "contrato"], [/^#\/precos$/, "precos"], [/^#\/propostas\/(\d+)$/, "proposta"],
  [/^#\/empresas$/, "empresas"], [/^#\/conta$/, "conta"], [/^#\/glossario$/, "glossario"], [/^#\/admin$/, "admin"],
];

const NAV = [
  ["Antes da disputa", [["#/radar", "Radar de editais", "radar"], ["#/editais", "Editais", "editais"], ["#/cofre", "Cofre de documentos", "cofre"]]],
  ["Na disputa", [["#/precos", "Preços e propostas", "precos"], ["#/concorrentes", "Concorrentes", "concorrentes"], ["#/pecas", "Peças", "pecas"], ["#/agenda", "Agenda de prazos", "agenda"]]],
  ["Depois da disputa", [["#/contratos", "Gestão de contratos", "contratos"]]],
];

function layout() {
  const opcoes = S.empresas.map((e) => `<option value="${e.id}" ${e.id === S.empresaId ? "selected" : ""}>${esc(e.razao_social)}</option>`).join("");
  let rota = location.hash.split("/").slice(0, 2).join("/");
  if (rota === "#/propostas") rota = "#/precos";
  const link = ([h, t, ic], badge) => `<a href="${h}" class="${rota === h ? "ativo" : ""}">
    <span class="rotulo">${ic ? icone(ic, 17) : ""}${esc(t)}</span>${badge ? `<span class="contador">${badge}</span>` : ""}</a>`;
  const aviso = [];
  if (S.demo) aviso.push(`<div class="faixa-aviso"><span><b>Modo demonstração.</b> As respostas de IA são exemplos. Configure as chaves de IA no servidor para análises reais.</span></div>`);
  if (S.plano?.teste_expirado) aviso.push(`<div class="faixa-aviso"><span>Seu teste grátis terminou. Seus dados continuam salvos.</span><a href="#/conta">Escolher um plano</a></div>`);
  else if (S.plano?.codigo === "suspenso") aviso.push(`<div class="faixa-aviso"><span>Seu acesso está suspenso por falta de pagamento. Seus dados continuam salvos.</span><a href="#/conta">Regularizar</a></div>`);
  else if (S.plano?.assinatura?.status === "inadimplente") aviso.push(`<div class="faixa-aviso"><span>Não conseguimos cobrar seu cartão. Atualize o pagamento para não perder o acesso.</span><a href="#/conta">Resolver</a></div>`);
  else if (S.plano?.assinatura?.pago_ate && !S.plano.assinatura.recorrente && fmt.dias(S.plano.assinatura.pago_ate) <= 5)
    aviso.push(`<div class="faixa-aviso"><span>Seu plano vence ${fmt.prazo(S.plano.assinatura.pago_ate)} (${fmt.data(S.plano.assinatura.pago_ate)}).</span><a href="#/conta">Renovar</a></div>`);
  else if (S.plano?.codigo === "trial") aviso.push(`<div class="faixa-aviso"><span>Teste grátis até ${fmt.data(S.plano.trial_fim)}: ${S.plano.uso.analises} de ${S.plano.analises} análises usadas.</span><a href="#/conta">Ver planos</a></div>`);
  return `
  <div class="topo-movel"><a class="marca" href="#/painel">${simboloMarca(28)}<strong>${esc(CERTAME.NOME)}</strong></a>
    <button id="abrir-menu" aria-label="Abrir menu">${icone("menu", 16)} Menu</button></div>
  <div class="app">
    <aside class="lateral" id="lateral">
      <a class="marca" href="#/painel">${simboloMarca(34)}<span class="texto"><strong>${esc(CERTAME.NOME)}</strong><span>public market intelligence</span></span></a>
      ${S.empresas.length ? `<div class="seletor-empresa"><label for="sel-empresa">Empresa</label>
        <select id="sel-empresa">${opcoes}</select></div>` : ""}
      <nav class="nav-grupo">${link(["#/painel", "Painel", "painel"])}${link(["#/oportunidades", "Oportunidades", "kanban"])}</nav>
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
  let hash = location.hash && location.hash !== "#" ? location.hash.split("?")[0] : "#/";  // ?utm_... no hash não muda a rota
  const raiz = $("#raiz");
  // A apresentação pública mora no site (kasiski.com.br); o app abre direto no login ou no painel.
  if (hash === "#planos" || hash === "#/inicio") { location.replace(CERTAME.SITE_URL + "/" + (hash === "#planos" ? "#planos" : "")); return; }
  if (hash === "#/") { location.hash = S.token ? "#/painel" : "#/entrar"; return; }
  document.body.classList.remove("publico");
  if (hash === "#/verificar") {
    if (S.token) { location.hash = "#/painel"; return; }
    telaVerificacao(raiz);
    return;
  }
  if (["#/entrar", "#/cadastro"].includes(hash)) {
    if (S.token) { location.hash = "#/painel"; return; }
    raiz.innerHTML = telaEntrada(hash === "#/cadastro");
    try { // pré-preenche com o que a pessoa já informou nas ferramentas gratuitas do site
      const pre = window.Kasiski ? Kasiski.lerJson("kasiski_cadastro") : JSON.parse(localStorage.getItem("kasiski_cadastro") || "null");
      if (pre) { const n = $("#nome"), e = $("#email"); if (n && !n.value) n.value = pre.nome || ""; if (e && !e.value) e.value = pre.email || ""; }
    } catch { /* ok */ }
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
      <div class="entrada-topo"><a class="marca-completa" href="#/">${simboloMarca(40)}<span class="texto"><strong>${esc(CERTAME.NOME)}</strong><span>public market intelligence</span></span></a>
        <a class="entrada-voltar" href="${CERTAME.SITE_URL}/">← Conhecer o Kasiski</a></div>
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
        ${cadastro ? `<div class="campo"><label for="telefone">WhatsApp <small>(opcional)</small></label><input id="telefone" name="telefone" type="tel" autocomplete="tel" inputmode="tel"></div>` : ""}
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
        const corpo = dadosForm(f);
        if (cadastro) Object.assign(corpo, { visitante: FUNIL.visitante, origem: FUNIL.origem(), campanha: FUNIL.campanha(),
          aquisicao: window.Kasiski ? Kasiski.aquisicao() : null });
        const d = await api("POST", cadastro ? "/api/auth/registro" : "/api/auth/login", corpo);
        marcar(cadastro ? "sign_up" : "login", { method: "email" });
        if (d.verificacao_pendente) {
          try { sessionStorage.setItem("kasiski_verificacao", JSON.stringify({ token: d.token_verificacao, email: d.email, novo: d.novo_cadastro, aviso: d.aviso })); } catch { /* segue */ }
          location.hash = "#/verificar";
          return;
        }
        entrarComToken(d.token, cadastro);
      } catch (e) { $("#erro-entrada").innerHTML = erroTela(e); }
    });
  };
}

// Volta do Mercado Pago: a URL chega como /?pagamento=retorno&payment_id=... (sem hash).
// Guarda os dados, limpa a URL e leva o cliente para a tela do plano, que confere o pagamento.
(() => {
  const q = new URLSearchParams(location.search);
  if (q.get("pagamento") !== "retorno") return;
  const info = { payment_id: q.get("payment_id") || q.get("collection_id") || "", status: q.get("status") || q.get("collection_status") || "" };
  const advogado = q.get("destino") === "advogado";
  try { sessionStorage.setItem(advogado ? "kasiski_retorno_advogado" : "kasiski_retorno_mp", JSON.stringify(info)); } catch { /* segue */ }
  history.replaceState(null, "", location.pathname + (advogado ? "#/pecas/advogado" : "#/conta"));
})();

function entrarComToken(token, novo) {
  S.token = token; localStorage.setItem("certame_token", token);
  S.usuario = null;
  try { sessionStorage.removeItem("kasiski_verificacao"); } catch { /* segue */ }
  location.hash = novo ? "#/empresas" : "#/painel";
}

// ---------------------------------------------------------------- verificação do e-mail (primeiro acesso)
function telaVerificacao(raiz) {
  let v = null;
  try { v = JSON.parse(sessionStorage.getItem("kasiski_verificacao") || "null"); } catch { /* segue */ }
  if (!v?.token) { location.hash = "#/entrar"; return; }
  raiz.innerHTML = `<div class="entrada">
    <section class="entrada-lado">
      <div class="entrada-topo"><a class="marca-completa" href="#/">${simboloMarca(40)}<span class="texto"><strong>${esc(CERTAME.NOME)}</strong><span>public market intelligence</span></span></a></div>
      <div><h1>Falta só confirmar seu e-mail.</h1>
        <p>Assim garantimos que só você acessa a conta e que os avisos de prazos e editais chegam no endereço certo.</p></div>
      <small style="color:var(--linha-forte)">O código vale por 15 minutos.</small>
    </section>
    <section class="entrada-form">
      <form id="form-codigo" novalidate>
        <h2>Digite o código</h2>
        <p class="fraco">Enviamos um código de 6 números para <b>${esc(v.email)}</b>. Confira também a caixa de spam.</p>
        <div id="erro-codigo">${v.aviso ? `<div class="aviso info">${esc(v.aviso)}</div>` : ""}</div>
        <div class="campo"><label for="codigo">Código de verificação</label>
          <input id="codigo" name="codigo" class="campo-codigo" inputmode="numeric" autocomplete="one-time-code" maxlength="7" pattern="[0-9 ]*" required placeholder="000000"></div>
        <button class="botao" style="width:100%" type="submit">Confirmar e entrar</button>
        <p style="margin-top:16px;text-align:center"><button type="button" class="botao texto" id="reenviar">Reenviar código</button></p>
        <p style="text-align:center"><a href="#/${v.novo ? "cadastro" : "entrar"}" id="trocar">Usar outro e-mail</a></p>
      </form>
    </section></div>`;
  const campo = $("#codigo"), erro = $("#erro-codigo"), reenviar = $("#reenviar");
  campo.focus();
  campo.oninput = () => {
    campo.value = campo.value.replace(/\D/g, "").slice(0, 6);
    if (campo.value.length === 6) $("#form-codigo").requestSubmit();
  };
  $("#trocar").onclick = () => { try { sessionStorage.removeItem("kasiski_verificacao"); } catch { /* segue */ } };
  const falhou = (e) => {
    erro.innerHTML = erroTela(e);
    if (["verificacao_expirada"].includes(e.codigo)) setTimeout(() => { location.hash = "#/entrar"; }, 2500);
  };
  $("#form-codigo").onsubmit = async (ev) => {
    ev.preventDefault();
    if (campo.value.length !== 6) { erro.innerHTML = `<div class="aviso erro">Digite os 6 números do código.</div>`; return; }
    const b = ev.target.querySelector("button[type=submit]");
    await ocupado(b, "Conferindo…", async () => {
      try { const d = await api("POST", "/api/auth/verificar", { token_verificacao: v.token, codigo: campo.value }); entrarComToken(d.token, v.novo); }
      catch (e) { falhou(e); campo.select(); }
    });
  };
  let espera = 0, relogio = null;
  const contar = (seg) => {
    espera = seg; clearInterval(relogio);
    const tick = () => {
      reenviar.disabled = espera > 0;
      reenviar.textContent = espera > 0 ? `Reenviar código em ${espera}s` : "Reenviar código";
      if (espera-- <= 0) clearInterval(relogio);
    };
    tick(); relogio = setInterval(tick, 1000);
  };
  contar(60);
  reenviar.onclick = async () => {
    try {
      const d = await api("POST", "/api/auth/reenviar-codigo", { token_verificacao: v.token });
      if (d.ja_verificado) { location.hash = "#/entrar"; toast("Seu e-mail já está confirmado. Entre com sua senha.", "ok"); return; }
      erro.innerHTML = `<div class="aviso ok">Enviamos um novo código para ${esc(v.email)}.</div>`; contar(60); campo.value = ""; campo.focus();
    } catch (e) {
      falhou(e);
      const m = /(\d+) segundos/.exec(e.message || ""); if (m) contar(Number(m[1]));
    }
  };
}

window.addEventListener("hashchange", navegar);
navegar();
