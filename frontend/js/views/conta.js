// Conta, planos, assinatura (Mercado Pago) e preferências.
const ROTULO_ASSINATURA = { ativa: ["Ativa", "ok"], pendente: ["Aguardando pagamento", "aviso"], pausada: ["Pausada", "aviso"],
  cancelada: ["Cancelada", "neutro"], inadimplente: ["Pagamento recusado", "erro"] };
const ROTULO_COBRANCA = { aprovado: ["Pago", "ok"], pendente: ["Pendente", "aviso"], recusado: ["Recusado", "erro"],
  estornado: ["Estornado", "erro"], cancelado: ["Cancelado", "neutro"] };
const PAGOS_FRONT = ["essencial", "profissional", "business", "consultor", "enterprise"];
const ORDEM_PLANOS = ["free", "essencial", "profissional", "business", "consultor"];
const ROTULO_MEIO = { pix: "Pix", cartao: "Cartão", boleto: "Boleto", saldo_mp: "Saldo Mercado Pago", outro: "Outro" };

V.conta = async (el) => {
  await atualizarConta();
  const retorno = (() => { try { const v = sessionStorage.getItem("kasiski_retorno_mp"); sessionStorage.removeItem("kasiski_retorno_mp"); return v ? JSON.parse(v) : null; } catch { return null; } })();
  if (retorno) {
    try { await api("POST", "/api/billing/sincronizar", retorno); await carregarConta(); } catch { /* o webhook resolve */ }
  }
  let cobrancas = [];
  try { cobrancas = await api("GET", "/api/billing/cobrancas"); } catch { /* tela segue sem histórico */ }
  const p = S.plano, a = p.assinatura || {};
  const ciclo = V.conta.ciclo || "mensal";
  if (retorno && ["approved", ""].includes(retorno.status) && PAGOS_FRONT.includes(p.codigo_base || p.codigo))
    marcar("purchase", { currency: "BRL", value: p.preco, transaction_id: retorno.payment_id || retorno.collection_id || "", items: [{ item_id: p.codigo, item_name: p.nome }] });
  const msgRetorno = !retorno ? "" : ["approved", ""].includes(retorno.status) && PAGOS_FRONT.includes(p.codigo_base || p.codigo)
    ? `<div class="aviso ok">Pagamento confirmado. Seu plano ${esc(p.nome)} está ativo.</div>`
    : ["rejected", "null", "failure"].includes(retorno.status)
      ? `<div class="aviso erro">O pagamento não foi concluído. Você pode tentar de novo com outra forma de pagamento.</div>`
      : `<div class="aviso info">Recebemos seu pedido. Assim que o Mercado Pago confirmar (Pix: segundos; boleto: até 2 dias úteis), seu plano é liberado automaticamente.</div>`;

  el.innerHTML = `
    <div class="cabecalho"><div><h1>Plano e conta</h1><p>${esc(S.usuario.nome)} · ${esc(S.usuario.email)}</p></div></div>
    ${msgRetorno}
    ${testeHtml(p)}
    ${assinaturaHtml(p, a)}
    <section class="bloco"><h2>Uso deste mês</h2>
      <div class="grade grade-3">
        ${barraUso("Análises de edital", p.uso.analises, p.analises)}
        ${barraUso("Análises de concorrente", p.uso.concorrentes, p.concorrentes)}
        ${barraUso("Possíveis concorrentes", p.uso.possiveis ?? 0, p.possiveis)}
        ${barraUso("Peças com IA", p.uso.pecas ?? 0, p.pecas)}
        ${barraUso("Empresas cadastradas", p.uso.empresas, p.empresas)}
        ${barraUso("Usuários", (p.uso.usuarios ?? 1) + (p.uso.convites ?? 0), p.usuarios)}
        ${barraUso("Contratos em gestão", p.uso.contratos ?? 0, p.limite_contratos)}
        ${p.armazenamento ? barraArmazenamento(p.armazenamento) : ""}
      </div></section>
      ${p.creditos?.saldo ? `<p class="fraco" style="margin-top:10px">Créditos do Pacote de inteligência: <b>${p.creditos.saldo}</b>, válidos até ${fmt.data(p.creditos.validade)}. Eles cobrem o uso acima do limite do plano.</p>` : ""}
    ${creditosHtml(p)}
    ${empresasExtrasHtml(p)}
    ${pacotesHtml(p)}
    <section class="bloco" id="dados-fiscais"><div class="bloco-titulo"><h2>Dados para a nota fiscal</h2><span id="nf-selo"></span></div>
      <div id="nf-corpo"><p class="carregando">Carregando…</p></div></section>
    <section class="bloco" id="equipe"><div class="bloco-titulo"><h2>Equipe</h2></div><div id="equipe-corpo"><p class="carregando">Carregando…</p></div></section>
    <section class="bloco"><div class="bloco-titulo"><h2>Planos</h2>
      <div class="alternador" role="group" aria-label="Ciclo de cobrança">
        <button data-ciclo="mensal" class="${ciclo === "mensal" ? "ativo" : ""}" aria-pressed="${ciclo === "mensal"}">Mensal</button>
        <button data-ciclo="anual" class="${ciclo === "anual" ? "ativo" : ""}" aria-pressed="${ciclo === "anual"}">Anual <small>${12 - S.cobranca.anual_meses_pagos} meses grátis</small></button>
      </div></div>
      <div class="grade-planos grade-planos-5">${ORDEM_PLANOS.filter((k) => S.planos[k]).map((k) => planoHtml(k, S.planos[k], p.codigo_base || p.codigo, ciclo, p)).join("")}</div>
      <div class="plano-enterprise"><div><b>Kasiski Enterprise</b> · sob consulta<br><small class="fraco">Para grandes operações: muitos CNPJs e usuários, grandes volumes, integrações e API, SSO, SLA, onboarding e suporte dedicado.</small></div>
        <a class="botao secundario" href="mailto:${esc(CERTAME.EMAIL_COMERCIAL || "contato@kasiski.com.br")}?subject=Kasiski%20Enterprise">Falar com a gente</a></div>
      <details class="comparar-planos"><summary>Comparar todos os recursos</summary>${tabelaComparativa()}</details>
    </section>
    ${cobrancas.length ? `<section class="bloco"><h2>Histórico de pagamentos</h2><div class="tabela-rolagem"><table>
      <thead><tr><th>Data</th><th>Descrição</th><th>Forma</th><th>Valor</th><th>Situação</th></tr></thead>
      <tbody>${cobrancas.map((c) => `<tr><td>${fmt.data(c.pago_em || c.criado_em)}</td><td>${esc(c.descricao || "")}</td>
        <td>${esc(ROTULO_MEIO[c.meio] || c.meio || "—")}</td><td>${fmt.moeda(c.valor)}</td><td>${carimboStatus(ROTULO_COBRANCA, c.status)}</td></tr>`).join("")}</tbody></table></div></section>` : ""}
    <section class="bloco"><h2>Preferências</h2>
      <form id="form-pref">
        <label class="check"><input type="checkbox" name="modo_guiado" ${S.usuario.modo_guiado ? "checked" : ""}> Mostrar explicações do modo guiado em cada tela</label>
        <p style="margin:10px 0 0"><button type="button" class="botao secundario pequeno" id="refazer-tour">Refazer o tour guiado</button>
          <small class="fraco">Mostra de novo o passo a passo do sistema e do seu plano.</small></p>
        ${p.marca ? `<div class="campo" style="margin-top:12px"><label for="marca_rel">Nome do escritório nos relatórios</label>
          <input id="marca_rel" name="marca_relatorio" value="${esc(S.conta.marca_relatorio || "")}"></div>` : ""}
        <button class="botao" style="margin-top:12px" type="submit">Salvar preferências</button></form></section>
    <section class="bloco"><h2>Alterar senha</h2>
      <form id="form-senha" class="linha-campos" style="align-items:flex-end">
        <div class="campo"><label for="senha_atual">Senha atual</label><input id="senha_atual" name="senha_atual" type="password"></div>
        <div class="campo"><label for="nova_senha">Nova senha</label><input id="nova_senha" name="nova_senha" type="password" minlength="8"></div>
        <button class="botao secundario" type="submit">Alterar</button></form>
      <div id="erro-senha"></div></section>`;
  $("#refazer-tour", el).onclick = () => refazerTour();
  $("#form-pref", el).onsubmit = async (ev) => { ev.preventDefault(); await api("PATCH", "/api/conta", dadosForm(ev.target)); await carregarConta(); toast("Preferências salvas.", "ok"); };
  $("#form-senha", el).onsubmit = async (ev) => {
    ev.preventDefault();
    try { await api("PATCH", "/api/conta", dadosForm(ev.target)); ev.target.reset(); toast("Senha alterada.", "ok"); }
    catch (e) { $("#erro-senha", el).innerHTML = erroTela(e); }
  };
  $$("[data-ciclo]", el).forEach((b) => b.onclick = () => { V.conta.ciclo = b.dataset.ciclo; V.conta(el); });
  $$("[data-assinar]", el).forEach((b) => b.onclick = () => modalCheckout(b.dataset.assinar, V.conta.ciclo || "mensal"));
  ligarExtras(el, p);
  carregarEquipe($("#equipe-corpo", el));
  carregarDadosFiscais(el);
  const cp = $("#comprar-pacote", el);
  if (cp) cp.onclick = () => modalPacote(p);
  const cpc = $("#cancelar-pacote", el);
  if (cpc) cpc.onclick = async () => {
    if (!(await confirmar(`A renovação dos pacotes será cancelada. Os contratos extras seguem liberados até ${fmt.data(p.pacotes.ate)}.`, "Cancelar renovação"))) return;
    try { await api("POST", "/api/billing/pacotes/cancelar"); toast("Renovação dos pacotes cancelada.", "ok"); V.conta(el); } catch (e) { avisarErro(e); }
  };
  const canc = $("#cancelar-assinatura", el);
  if (canc) canc.onclick = async () => {
    if (!(await confirmar(`A renovação automática será cancelada. Você continua com acesso ao plano até ${fmt.data(a.pago_ate)}.`, "Cancelar renovação"))) return;
    try { await api("POST", "/api/billing/cancelar"); toast("Renovação cancelada.", "ok"); V.conta(el); } catch (e) { avisarErro(e); }
  };
};

function pacotesHtml(p) {
  const pk = p.pacotes || {};
  if (!p.contratos || !PAGOS_FRONT.includes(p.codigo_base)) return "";
  return `<section class="bloco"><div class="bloco-titulo"><h2>Contratos extras</h2>${pk.ativos ? carimbo(`${pk.ativos} pacote(s) ativo(s)`, "ok") : ""}</div>
    <p>Seu plano inclui <b>${p.contratos}</b> contratos em gestão. Precisa de mais? Cada pacote soma <b>+${pk.contratos} contratos</b> por <b>${fmt.moeda(pk.preco)}/mês</b>.</p>
    ${pk.ativos ? `<p class="fraco">Total liberado hoje: ${p.limite_contratos} contratos · ${pk.metodo === "recorrente" ? (pk.status === "cancelada" ? "renovação cancelada, válido" : "renova automaticamente, próximo ciclo") : "pago por Pix/boleto, válido"} até ${fmt.data(pk.ate)}</p>` : ""}
    <div class="acoes"><button class="botao" id="comprar-pacote">${pk.ativos ? (pk.metodo === "recorrente" && pk.status === "ativa" ? "Mudar quantidade" : "Renovar ou mudar") : "Contratar pacote"}</button>
      ${pk.metodo === "recorrente" && pk.status === "ativa" ? `<button class="botao texto" id="cancelar-pacote">Cancelar renovação dos pacotes</button>` : ""}</div></section>`;
}

function modalPacote(p) {
  const pk = p.pacotes;
  const recorrenteAtivo = pk.metodo === "recorrente" && pk.status === "ativa";
  const m = modal({ titulo: "Pacotes de +10 contratos", corpo: `<form id="form-pacote">
    <div class="campo"><label for="pk-qtd">Quantos pacotes</label><select id="pk-qtd" name="quantidade">
      ${[1, 2, 3, 4, 5, 10].map((n) => `<option value="${n}" ${n === (pk.contratados || 1) ? "selected" : ""}>${n} pacote${n > 1 ? "s" : ""} · +${n * pk.contratos} contratos · ${fmt.moeda(n * pk.preco)}/mês</option>`).join("")}</select></div>
    <div class="opcoes-pagamento">
      <button class="opcao-pagamento" type="submit" data-metodo="recorrente" ${recorrenteAtivo ? "disabled" : ""}><b>Cartão, renovação automática</b>
        <span>Cobrado todo mês junto com o uso.${recorrenteAtivo ? " <em>Cancele a renovação atual para mudar a quantidade.</em>" : ""}</span></button>
      <button class="opcao-pagamento" type="submit" data-metodo="avulso"><b>Pix, boleto ou cartão — 1 mês</b><span>Vale 30 dias; renove quando quiser.</span></button>
    </div>
    <p class="fraco" style="margin-top:10px">Se o pacote vencer, os contratos já cadastrados continuam acessíveis, mas não é possível cadastrar novos acima do limite do plano.</p>
    <div id="erro-pacote"></div></form>` });
  $$("[data-metodo]", m).forEach((b) => b.onclick = (ev) => {
    ev.preventDefault();
    ocupado(b, "Abrindo o Mercado Pago…", async () => {
      try { const r = await api("POST", "/api/billing/pacotes", { quantidade: Number($("#pk-qtd", m).value), metodo: b.dataset.metodo }); location.href = r.url; }
      catch (e) { $("#erro-pacote", m).innerHTML = erroTela(e); }
    });
  });
}

function assinaturaHtml(p, a) {
  if (!a.status && ![...PAGOS_FRONT, "suspenso"].includes(p.codigo_base || p.codigo)) return "";
  const pago = !!a.pago_ate;
  const forma = a.metodo === "recorrente" ? "Cartão · renova automaticamente" : a.metodo === "avulso" ? "Pix, boleto ou cartão · renovação manual" : "Definido pelo suporte";
  let acao = "";
  if (a.recorrente) acao = `<button class="botao texto" id="cancelar-assinatura">Cancelar renovação automática</button>`;
  else if (PAGOS_FRONT.includes(p.codigo_base) && p.codigo_base !== "enterprise" && a.metodo === "avulso")
    acao = `<button class="botao" data-assinar="${p.codigo_base}">Renovar agora</button>`;
  else if (p.codigo === "suspenso") acao = `<span class="fraco">Escolha um plano abaixo para reativar.</span>`;
  return `<section class="bloco"><div class="bloco-titulo"><h2>Sua assinatura</h2>${a.status ? carimboStatus(ROTULO_ASSINATURA, a.status) : ""}</div>
    <div class="grade grade-3">
      <div class="indicador"><b>${esc(p.nome)}</b><span>${a.ciclo === "anual" ? "Cobrança anual" : "Cobrança mensal"}${p.preco_contratado && p.preco_contratado < (p.preco || 0) ? ` · você mantém ${fmt.moeda(p.preco_contratado)}/mês da tabela anterior` : ""}</span></div>
      <div class="indicador ${pago && fmt.dias(a.pago_ate) < 0 ? "alerta" : ""}"><b>${pago ? fmt.data(a.pago_ate) : "—"}</b>
        <span>${a.recorrente ? "próxima cobrança" : a.status === "cancelada" ? "acesso garantido até" : "acesso pago até"}</span></div>
      <div class="indicador"><b style="font-size:1rem;padding-top:8px">${esc(forma)}</b><span>forma de pagamento</span></div>
    </div>${acao ? `<div style="margin-top:14px">${acao}</div>` : ""}</section>`;
}

function precoCiclo(v, ciclo, codigo) {
  let mensal = v.preco || 0;
  if (codigo && codigo === S.plano?.codigo_base && S.plano?.preco_contratado) mensal = Math.min(mensal, S.plano.preco_contratado);
  return ciclo === "anual" ? mensal * S.cobranca.anual_meses_pagos : mensal;
}

function modalCheckout(plano, ciclo) {
  const v = S.planos[plano];
  if (!S.cobranca.online) { window.open(CERTAME.LINK_ASSINATURA, "_blank"); return; }
  const total = precoCiclo(v, ciclo, plano);
  const recorrente = S.plano.assinatura?.recorrente;
  const m = modal({
    titulo: `Assinar ${v.nome} · ${ciclo === "anual" ? "anual" : "mensal"}`,
    corpo: `<p class="preco-checkout">${fmt.moeda(total)}<small>${ciclo === "anual" ? `/ano · equivale a ${fmt.moeda(total / 12)}/mês` : "/mês"}</small></p>
      <div class="opcoes-pagamento">
        <button class="opcao-pagamento" data-metodo="recorrente" ${recorrente ? "disabled" : ""}>
          <b>Cartão de crédito, com renovação automática</b>
          <span>Cobrado ${ciclo === "anual" ? "uma vez por ano" : "todo mês"} sem você precisar lembrar. Cancele quando quiser.${recorrente ? " <em>Você já tem uma renovação automática ativa.</em>" : ""}</span></button>
        <button class="opcao-pagamento" data-metodo="avulso">
          <b>Pix, boleto ou cartão, pagamento único</b>
          <span>Vale por ${ciclo === "anual" ? "12 meses" : "1 mês"}. Para continuar, você renova com um novo pagamento${ciclo === "anual" ? " (cartão em até 12x)" : ""}.</span></button>
      </div>
      <p class="fraco" style="margin-top:12px">Você será levado ao ambiente seguro do Mercado Pago. O plano é liberado assim que o pagamento for confirmado.</p>
      <div id="erro-checkout"></div>`,
  });
  $$("[data-metodo]", m).forEach((b) => b.onclick = () => ocupado(b, "Abrindo o Mercado Pago…", async () => {
    try {
      const d = await api("POST", "/api/billing/checkout", { plano, ciclo, metodo: b.dataset.metodo });
      marcar("begin_checkout", { currency: "BRL", value: d.valor, items: [{ item_id: plano, item_name: plano, item_variant: ciclo }] });
      location.href = d.url;
    }
    catch (e) { $("#erro-checkout", m).innerHTML = erroTela(e); }
  }));
}

function tamanhoArquivo(b) {
  if (b >= 1024 ** 3) return `${(b / 1024 ** 3).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} GB`;
  if (b >= 1024 ** 2) return `${(b / 1024 ** 2).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} MB`;
  return `${Math.max(0, Math.round(b / 1024))} KB`;
}

function barraArmazenamento(a) {
  const pct = Math.min(100, a.pct || 0);
  return `<div><div class="meta" style="justify-content:space-between"><span>Armazenamento de arquivos</span><span>${tamanhoArquivo(a.usado)} / ${tamanhoArquivo(a.limite)}</span></div>
    <div class="barra"><i style="width:${Math.max(pct, a.usado ? 1 : 0)}%;${pct >= 90 ? "background:var(--carimbo)" : ""}"></i></div>
    ${pct >= 80 ? `<small class="fraco">Quase cheio: esvazie a <a href="#/lixeira">Lixeira</a> ou faça upgrade.</small>` : ""}</div>`;
}

function barraUso(rotulo, usado, limite) {
  const ilimitado = limite === true || limite === undefined;
  const pct = ilimitado || !limite ? 0 : Math.min(100, Math.round((usado / limite) * 100));
  return `<div><div class="meta" style="justify-content:space-between"><span>${esc(rotulo)}</span><span>${usado}${ilimitado ? "" : ` / ${limite}`}</span></div>
    ${ilimitado ? "" : `<div class="barra"><i style="width:${pct}%;${pct >= 100 ? "background:var(--carimbo)" : ""}"></i></div>`}</div>`;
}

const QTD = (n, s1, pl) => (n === false || n === 0 || n === null || n === undefined ? null : `${n} ${n === 1 ? s1 : pl}`);

function planoHtml(codigo, v, atual, ciclo = "mensal", resumo = {}) {
  const valor = precoCiclo(v, ciclo, codigo);
  const preco = !v.preco ? "R$ 0" : ciclo === "anual"
    ? `${fmt.moeda(valor / 12)}<small>/mês</small><span class="preco-nota">${fmt.moeda(valor)} por ano (pague 10, use 12)</span>`
    : `${fmt.moeda(valor)}<small>/mês</small>`;
  const eAtual = codigo === atual && !(resumo.em_teste && codigo === "free");
  let botao;
  if (eAtual) botao = carimbo("Seu plano", "ok");
  else if (codigo === "free") botao = `<small class="fraco">${atual === "free" ? "" : "Se a assinatura acabar, a conta volta ao Free sem perder dados."}</small>`;
  else botao = `<button class="botao ${v.destaque ? "" : "secundario"}" data-assinar="${codigo}">${resumo.em_teste && codigo === "profissional" ? "Assinar e manter" : "Assinar"}</button>`;
  if (codigo === "profissional" && resumo.teste_disponivel) botao += `<button class="botao texto pequeno" data-iniciar-teste>ou experimente por ${resumo.teste_dias || 7} dias</button>`;
  const itens = [QTD(v.empresas, "empresa", "empresas") + " · " + QTD(v.usuarios, "usuário", "usuários"),
    `${QTD(v.analises, "análise", "análises")} de edital com IA/mês`, QTD(v.concorrentes, "análise de concorrente/mês", "análises de concorrentes/mês"),
    v.radar_max ? `Radar: 1 busca por dia (${v.radar_max} melhores editais)` : "Radar diário automático", v.cofre_max ? `Cofre básico (${v.cofre_max} arquivos)` : "Cofre com controle de validade", v.armazenamento_mb ? `${v.armazenamento_mb >= 1024 ? (v.armazenamento_mb / 1024).toLocaleString("pt-BR") + " GB" : v.armazenamento_mb + " MB"} de arquivos` : "",
    v.oportunidades_max ? `Até ${v.oportunidades_max} oportunidades acompanhadas` : "Pipeline de oportunidades e agenda",
    v.precos ? "Inteligência de preços e propostas" : null, v.pecas ? `${v.pecas} peças com IA/mês` : null,
    v.contratos ? `Gestão de até ${v.contratos} contratos` : null, v.prioridade ? "Prioridade de processamento e suporte" : null,
    v.marca ? "Relatórios com a marca do escritório" : null, v.empresa_extra ? `Empresa adicional: ${fmt.moeda(v.empresa_extra)}/mês` : null].filter(Boolean);
  return `<div class="plano ${eAtual ? "atual" : ""} ${v.destaque ? "destaque" : ""}">${v.destaque ? '<span class="selo-plano">Mais escolhido</span>' : ""}
    <h3>${esc(v.nome)}</h3><p class="fraco plano-slogan">${esc(v.slogan || "")}</p><div class="preco">${preco}</div>
    <ul>${itens.map((i) => `<li>${esc(i)}</li>`).join("")}</ul>${botao}</div>`;
}

function tabelaComparativa() {
  const P = S.planos, ks = ORDEM_PLANOS.filter((k) => P[k]);
  const sim = (v) => (v === true ? "✓" : v === false || v === 0 || v === null || v === undefined ? "—" : esc(String(v)));
  const linhas = [["Preço/mês", (v) => (v.preco ? fmt.moeda(v.preco) : "R$ 0")], ["Empresas (CNPJs)", (v) => v.empresas], ["Usuários", (v) => v.usuarios],
    ["Diagnóstico B2G e checklist de habilitação", () => true], ["Radar", (v) => (v.radar_max ? "1 busca/dia" : "Diário automático")], ["Cofre", (v) => (v.cofre_max ? "Básico" : true)], ["Armazenamento", (v) => (v.armazenamento_mb >= 1024 ? `${(v.armazenamento_mb / 1024).toLocaleString("pt-BR")} GB` : `${v.armazenamento_mb} MB`)],
    ["Agenda e pipeline", (v) => (v.oportunidades_max ? `Até ${v.oportunidades_max}` : true)], ["Análises de edital com IA/mês", (v) => v.analises],
    ["Análises de concorrentes/mês", (v) => v.concorrentes], ["Possíveis concorrentes/mês", (v) => v.possiveis],
    ["Inteligência de preços", (v) => v.precos], ["Propostas com IA", (v) => v.propostas], ["Peças com IA/mês", (v) => v.pecas || false],
    ["Gestão de contratos", (v) => v.contratos || false], ["Multiempresa", (v) => (v.empresas > 1 ? v.empresas : false)],
    ["Prioridade e suporte", (v) => v.prioridade], ["Relatórios com a sua marca", (v) => v.marca]];
  return `<div class="tabela-rolagem"><table class="comparativo"><thead><tr><th></th>${ks.map((k) => `<th>${esc(P[k].nome)}</th>`).join("")}</tr></thead>
    <tbody>${linhas.map(([r, f]) => `<tr><td>${esc(r)}</td>${ks.map((k) => `<td>${sim(f(P[k]))}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
}

function testeHtml(p) {
  if (p.em_teste) return `<section class="bloco destaque-plano"><h2>Você está experimentando o Profissional</h2>
    <p>Até <b>${fmt.data(p.trial_fim)}</b> (${fmt.prazo(p.trial_fim).replace("vence", "termina")}), com tudo do Profissional. Depois, a conta volta ao Free sem perder nenhum dado.</p>
    <button class="botao" data-assinar="profissional">Assinar o Profissional</button></section>`;
  if (p.teste_disponivel) return `<section class="bloco destaque-plano"><h2>Experimente o Profissional por ${p.teste_dias} dias</h2>
    <p>Análise de edital com IA, Go/No-Go, preços, concorrentes, propostas e peças, sem cartão. No fim, sua conta volta ao Free sem perder nada.</p>
    <button class="botao" data-iniciar-teste>Começar o teste agora</button></section>`;
  return "";
}

function creditosHtml(p) {
  if (!PAGOS_FRONT.includes(p.codigo_base)) return "";
  const pk = p.creditos.pacote;
  return `<section class="bloco"><div class="bloco-titulo"><h2>Pacote de inteligência</h2>${p.creditos.saldo ? carimbo(`${p.creditos.saldo} créditos`, "ok") : ""}</div>
    <p>Acabou o limite do mês? ${esc(pk.descricao)} por <b>${fmt.moeda(pk.preco)}</b>, pagamento único por Pix, boleto ou cartão. Cada uso acima do limite desconta créditos:
      análise de edital ${p.creditos.custo.analises}, concorrente ${p.creditos.custo.concorrentes}, peça ${p.creditos.custo.pecas}.</p>
    <div class="acoes"><select id="cr-qtd" aria-label="Quantidade">${[1, 2, 3, 5].map((n) => `<option value="${n}">${n} pacote${n > 1 ? "s" : ""} · ${fmt.moeda(n * pk.preco)}</option>`).join("")}</select>
      <button class="botao secundario" id="comprar-creditos">Comprar</button></div></section>`;
}

function empresasExtrasHtml(p) {
  const e = p.empresas_extras;
  if (!e?.disponivel) return "";
  return `<section class="bloco"><div class="bloco-titulo"><h2>Empresas adicionais</h2>${e.ativas ? carimbo(`+${e.ativas} ativa(s)`, "ok") : ""}</div>
    <p>Seu plano inclui ${p.empresas - (e.ativas || 0)} empresas. Cada empresa adicional custa <b>${fmt.moeda(e.preco)}/mês</b>, com cofre, radar e agenda próprios.</p>
    <div class="acoes"><select id="ex-qtd" aria-label="Quantidade">${[1, 2, 3, 5, 10].map((n) => `<option value="${n}" ${n === (e.contratadas || 1) ? "selected" : ""}>${n} empresa${n > 1 ? "s" : ""} · ${fmt.moeda(n * e.preco)}/mês</option>`).join("")}</select>
      <button class="botao secundario" data-extra-metodo="recorrente">Cartão (renova sozinho)</button><button class="botao secundario" data-extra-metodo="avulso">Pix/boleto (1 mês)</button>
      ${e.metodo === "recorrente" && e.status === "ativa" ? `<button class="botao texto" id="cancelar-extras">Cancelar renovação</button>` : ""}</div></section>`;
}

function ligarExtras(el, p) {
  const cc = $("#comprar-creditos", el);
  if (cc) cc.onclick = () => ocupado(cc, "Abrindo o Mercado Pago…", async () => {
    try { const r = await api("POST", "/api/billing/creditos", { quantidade: Number($("#cr-qtd", el).value) }); location.href = r.url; } catch (e) { avisarErro(e); }
  });
  $$("[data-extra-metodo]", el).forEach((b) => b.onclick = () => ocupado(b, "Abrindo o Mercado Pago…", async () => {
    try { const r = await api("POST", "/api/billing/empresas", { quantidade: Number($("#ex-qtd", el).value), metodo: b.dataset.extraMetodo }); location.href = r.url; } catch (e) { avisarErro(e); }
  }));
  const ce = $("#cancelar-extras", el);
  if (ce) ce.onclick = async () => {
    if (!(await confirmar("Cancelar a renovação das empresas adicionais? Elas seguem liberadas até o fim do período pago.", "Cancelar renovação"))) return;
    try { await api("POST", "/api/billing/empresas/cancelar"); toast("Renovação cancelada.", "ok"); V.conta(el); } catch (e) { avisarErro(e); }
  };
}

async function carregarDadosFiscais(el) {
  const corpo = $("#nf-corpo", el), selo = $("#nf-selo", el);
  if (!corpo) return;
  try {
    const r = await api("GET", "/api/conta/dados-fiscais");
    selo.innerHTML = r.completo ? carimbo("Completo", "ok") : carimbo("Pendente", "aviso");
    corpo.innerHTML = `<p class="fraco">Usados na nota fiscal de serviço (NFS-e) emitida a cada pagamento. Pode ser o CNPJ da sua empresa ou o seu CPF.${r.completo ? "" : " <b>Preencha antes de assinar ou comprar um pacote.</b>"}</p>
      ${formDadosFiscais(r.dados, r.posso_editar)}`;
    ligarFormDadosFiscais(corpo, () => carregarDadosFiscais(el));
  } catch (e) { corpo.innerHTML = erroTela(e); }
  if (location.hash.includes("dados-fiscais")) $("#dados-fiscais", el).scrollIntoView({ behavior: "smooth" });
}

async function carregarEquipe(el) {
  if (!el) return;
  let d;
  try { d = await api("GET", "/api/conta/equipe"); } catch (e) { el.innerHTML = erroTela(e); return; }
  const usados = d.membros.length + d.convites.length;
  el.innerHTML = `<p class="fraco">${usados} de ${d.limite} usuário(s) do seu plano. Todos da equipe veem as mesmas empresas, editais, documentos e prazos.</p>
    ${d.membros.map((u) => `<div class="lista-item"><div class="corpo"><b>${esc(u.nome)}</b>${u.voce ? ' <small class="fraco">(você)</small>' : ""} ${u.papel === "dono" ? carimbo("Responsável", "neutro") : ""}
      <p>${esc(u.email)}${u.ultimo_acesso ? ` · último acesso ${fmt.dataHora(u.ultimo_acesso)}` : ""}</p></div>
      ${d.posso_gerenciar && !u.voce && u.papel !== "dono" ? `<button class="botao texto pequeno" data-remover-membro="${u.id}">Remover</button>` : ""}</div>`).join("")}
    ${d.convites.map((c) => `<div class="lista-item"><div class="corpo"><b>${esc(c.email)}</b> ${carimbo("Convite enviado", "aviso")}<p>Vale até ${fmt.data(c.expira_em)}</p></div>
      ${d.posso_gerenciar ? `<button class="botao texto pequeno" data-cancelar-convite="${c.id}">Cancelar</button>` : ""}</div>`).join("")}
    ${d.posso_gerenciar ? (usados < d.limite ? `<form id="form-convite-eq" class="linha-campos" style="align-items:flex-end;margin-top:10px">
        <div class="campo"><label for="cv-email">Convidar por e-mail</label><input id="cv-email" name="email" type="email" required placeholder="nome@empresa.com.br"></div>
        <button class="botao" type="submit">Enviar convite</button></form><div id="cv-link"></div>`
      : `<div class="aviso info">Sua equipe está no limite do plano. <a href="#/conta">Faça upgrade</a> para convidar mais pessoas.</div>`) : ""}`;
  const f = $("#form-convite-eq", el);
  if (f) f.onsubmit = async (ev) => {
    ev.preventDefault();
    try {
      const c = await api("POST", "/api/conta/equipe/convites", dadosForm(f));
      toast(c.email_enviado ? `Convite enviado para ${c.email}.` : "Convite criado. Copie o link e envie para a pessoa.", "ok");
      await carregarEquipe(el);
      if (!c.email_enviado) $("#cv-link", el).innerHTML = `<div class="aviso info">Link do convite (vale 7 dias): <code>${esc(c.link)}</code></div>`;
    } catch (e) { avisarErro(e); }
  };
  $$("[data-remover-membro]", el).forEach((b) => b.onclick = async () => {
    if (!(await confirmar("Remover esta pessoa da equipe? Ela perde o acesso na hora.", "Remover"))) return;
    try { await api("DELETE", `/api/conta/equipe/${b.dataset.removerMembro}`); carregarEquipe(el); } catch (e) { avisarErro(e); }
  });
  $$("[data-cancelar-convite]", el).forEach((b) => b.onclick = async () => {
    try { await api("DELETE", `/api/conta/equipe/convites/${b.dataset.cancelarConvite}`); carregarEquipe(el); } catch (e) { avisarErro(e); }
  });
}

// ---------------------------------------------------------------- glossário
// Mesmo conteúdo do glossário público (kasiski.com.br/glossario), gerado por site/gerar.py em data/glossario.json.
V.glossario = async (el) => {
  if (!V.glossario.dados) {
    const r = await fetch("data/glossario.json", { cache: "no-cache" });
    if (!r.ok) throw new Error("Não foi possível carregar o glossário.");
    V.glossario.dados = await r.json();
  }
  const { categorias, termos } = V.glossario.dados;
  const porSlug = Object.fromEntries(termos.map((t) => [t.slug, t]));
  const norm = (t) => (t || "").toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
  const st = V.glossario.estado || (V.glossario.estado = { q: "", cat: "", aberto: null });
  el.innerHTML = `<div class="cabecalho"><div><h1>Glossário</h1><p>${termos.length} termos de licitações e contratos públicos, com definição, exemplo, lei e aplicação prática.</p></div></div>
    <div class="gl-filtros"><input type="search" id="gl-q" placeholder="Buscar termo (ex.: dispensa, atestado, reequilíbrio)" value="${esc(st.q)}" aria-label="Buscar no glossário">
      <div class="chips" role="group" aria-label="Categorias"><button data-gl-cat="" aria-pressed="${!st.cat}">Todos</button>
        ${categorias.map((c) => `<button data-gl-cat="${esc(c)}" aria-pressed="${st.cat === c}">${esc(c)}</button>`).join("")}</div></div>
    <section class="bloco gl-lista" id="gl-lista"></section>`;
  const lista = $("#gl-lista", el);
  const detalhe = (t) => `<div class="gl-detalhe">
      ${t.sin?.length ? `<p class="fraco">Também chamado de: ${esc(t.sin.join(", "))}</p>` : ""}
      <h4>Exemplo prático</h4><p>${esc(t.exemplo)}</p>
      <h4>O que diz a lei</h4><p>${esc(t.legislacao)}</p>
      <h4>Como isso afeta a sua empresa</h4><p>${esc(t.aplicacao)}</p>
      ${(t.perguntas || []).map(([q, a]) => `<h4>${esc(q)}</h4><p>${esc(a)}</p>`).join("")}
      ${t.rel?.length ? `<p class="gl-rel"><b>Relacionados:</b> ${t.rel.filter((s) => porSlug[s]).map((s) => `<button class="botao texto pequeno" data-gl-ir="${s}">${esc(porSlug[s].termo)}</button>`).join(" ")}</p>` : ""}
      <p><a href="${CERTAME.SITE_URL}/glossario/${t.slug}/" target="_blank" rel="noopener">Abrir página completa no site</a></p></div>`;
  const desenhar = () => {
    const q = norm(st.q);
    const vis = termos.filter((t) => (!st.cat || t.cat === st.cat) &&
      (!q || norm([t.termo, t.curto, ...(t.sin || [])].join(" ")).includes(q) || (q.length > 3 && norm(t.definicao).includes(q))));
    lista.innerHTML = vis.length ? vis.map((t) => `<article class="gl-termo${st.aberto === t.slug ? " aberto" : ""}" id="gl-${t.slug}">
        <button class="gl-cab" data-gl-abrir="${t.slug}" aria-expanded="${st.aberto === t.slug}"><span><b>${esc(t.termo)}</b><small>${esc(t.cat)}</small></span><span class="gl-seta" aria-hidden="true">${icone("chevronDireita", 16)}</span></button>
        <p class="gl-def">${esc(t.definicao)}</p>${st.aberto === t.slug ? detalhe(t) : ""}</article>`).join("")
      : vazio("Nenhum termo encontrado", "Tente outra palavra ou escolha outra categoria.");
    $$("[data-gl-abrir]", lista).forEach((b) => b.onclick = () => { st.aberto = st.aberto === b.dataset.glAbrir ? null : b.dataset.glAbrir; desenhar(); });
    $$("[data-gl-ir]", lista).forEach((b) => b.onclick = () => {
      st.aberto = b.dataset.glIr; st.q = ""; st.cat = ""; $("#gl-q", el).value = "";
      $$("[data-gl-cat]", el).forEach((x) => x.setAttribute("aria-pressed", String(!x.dataset.glCat)));
      desenhar(); const alvo = $(`#gl-${st.aberto}`, el); if (alvo) alvo.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  };
  let t0; $("#gl-q", el).oninput = (ev) => { clearTimeout(t0); t0 = setTimeout(() => { st.q = ev.target.value; desenhar(); }, 150); };
  $$("[data-gl-cat]", el).forEach((b) => b.onclick = () => { st.cat = b.dataset.glCat; $$("[data-gl-cat]", el).forEach((x) => x.setAttribute("aria-pressed", String(x === b))); desenhar(); });
  desenhar();
};

