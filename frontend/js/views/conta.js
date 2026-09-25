// Conta, planos, assinatura (Mercado Pago) e preferências.
const ROTULO_ASSINATURA = { ativa: ["Ativa", "ok"], pendente: ["Aguardando pagamento", "aviso"], pausada: ["Pausada", "aviso"],
  cancelada: ["Cancelada", "neutro"], inadimplente: ["Pagamento recusado", "erro"] };
const ROTULO_COBRANCA = { aprovado: ["Pago", "ok"], pendente: ["Pendente", "aviso"], recusado: ["Recusado", "erro"],
  estornado: ["Estornado", "erro"], cancelado: ["Cancelado", "neutro"] };
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
  const msgRetorno = !retorno ? "" : ["approved", ""].includes(retorno.status) && ["profissional", "essencial", "consultor"].includes(p.codigo)
    ? `<div class="aviso ok">Pagamento confirmado. Seu plano ${esc(p.nome)} está ativo.</div>`
    : ["rejected", "null", "failure"].includes(retorno.status)
      ? `<div class="aviso erro">O pagamento não foi concluído. Você pode tentar de novo com outra forma de pagamento.</div>`
      : `<div class="aviso info">Recebemos seu pedido. Assim que o Mercado Pago confirmar (Pix: segundos; boleto: até 2 dias úteis), seu plano é liberado automaticamente.</div>`;

  el.innerHTML = `
    <div class="cabecalho"><div><h1>Plano e conta</h1><p>${esc(S.usuario.nome)} · ${esc(S.usuario.email)}</p></div></div>
    ${msgRetorno}
    ${assinaturaHtml(p, a)}
    <section class="bloco"><h2>Uso deste mês</h2>
      <div class="grade grade-3">
        ${barraUso("Análises de edital", p.uso.analises, p.analises)}
        ${barraUso("Análises de concorrente", p.uso.concorrentes, p.concorrentes)}
        ${barraUso("Empresas cadastradas", p.uso.empresas, p.empresas)}
      </div></section>
    <section class="bloco"><div class="bloco-titulo"><h2>Planos</h2>
      <div class="alternador" role="group" aria-label="Ciclo de cobrança">
        <button data-ciclo="mensal" class="${ciclo === "mensal" ? "ativo" : ""}" aria-pressed="${ciclo === "mensal"}">Mensal</button>
        <button data-ciclo="anual" class="${ciclo === "anual" ? "ativo" : ""}" aria-pressed="${ciclo === "anual"}">Anual <small>${12 - S.cobranca.anual_meses_pagos} meses grátis</small></button>
      </div></div>
      <div class="grade grade-4">${["trial", "essencial", "profissional", "consultor"].filter((k) => S.planos[k]).map((k) => planoHtml(k, S.planos[k], p.codigo, ciclo)).join("")}</div>
    </section>
    ${cobrancas.length ? `<section class="bloco"><h2>Histórico de pagamentos</h2><div class="tabela-rolagem"><table>
      <thead><tr><th>Data</th><th>Descrição</th><th>Forma</th><th>Valor</th><th>Situação</th></tr></thead>
      <tbody>${cobrancas.map((c) => `<tr><td>${fmt.data(c.pago_em || c.criado_em)}</td><td>${esc(c.descricao || "")}</td>
        <td>${esc(ROTULO_MEIO[c.meio] || c.meio || "—")}</td><td>${fmt.moeda(c.valor)}</td><td>${carimboStatus(ROTULO_COBRANCA, c.status)}</td></tr>`).join("")}</tbody></table></div></section>` : ""}
    <section class="bloco"><h2>Preferências</h2>
      <form id="form-pref">
        <label class="check"><input type="checkbox" name="modo_guiado" ${S.usuario.modo_guiado ? "checked" : ""}> Mostrar explicações do modo guiado em cada tela</label>
        ${p.marca ? `<div class="campo" style="margin-top:12px"><label for="marca_rel">Nome do escritório nos relatórios</label>
          <input id="marca_rel" name="marca_relatorio" value="${esc(S.conta.marca_relatorio || "")}"></div>` : ""}
        <button class="botao" style="margin-top:12px" type="submit">Salvar preferências</button></form></section>
    <section class="bloco"><h2>Alterar senha</h2>
      <form id="form-senha" class="linha-campos" style="align-items:flex-end">
        <div class="campo"><label for="senha_atual">Senha atual</label><input id="senha_atual" name="senha_atual" type="password"></div>
        <div class="campo"><label for="nova_senha">Nova senha</label><input id="nova_senha" name="nova_senha" type="password" minlength="8"></div>
        <button class="botao secundario" type="submit">Alterar</button></form>
      <div id="erro-senha"></div></section>`;
  $("#form-pref", el).onsubmit = async (ev) => { ev.preventDefault(); await api("PATCH", "/api/conta", dadosForm(ev.target)); await carregarConta(); toast("Preferências salvas.", "ok"); };
  $("#form-senha", el).onsubmit = async (ev) => {
    ev.preventDefault();
    try { await api("PATCH", "/api/conta", dadosForm(ev.target)); ev.target.reset(); toast("Senha alterada.", "ok"); }
    catch (e) { $("#erro-senha", el).innerHTML = erroTela(e); }
  };
  $$("[data-ciclo]", el).forEach((b) => b.onclick = () => { V.conta.ciclo = b.dataset.ciclo; V.conta(el); });
  $$("[data-assinar]", el).forEach((b) => b.onclick = () => modalCheckout(b.dataset.assinar, V.conta.ciclo || "mensal"));
  const canc = $("#cancelar-assinatura", el);
  if (canc) canc.onclick = async () => {
    if (!(await confirmar(`A renovação automática será cancelada. Você continua com acesso ao plano até ${fmt.data(a.pago_ate)}.`, "Cancelar renovação"))) return;
    try { await api("POST", "/api/billing/cancelar"); toast("Renovação cancelada.", "ok"); V.conta(el); } catch (e) { avisarErro(e); }
  };
};

function assinaturaHtml(p, a) {
  if (!a.status && !["essencial", "profissional", "consultor", "suspenso"].includes(p.codigo)) return "";
  const pago = !!a.pago_ate;
  const forma = a.metodo === "recorrente" ? "Cartão · renova automaticamente" : a.metodo === "avulso" ? "Pix, boleto ou cartão · renovação manual" : "Definido pelo suporte";
  let acao = "";
  if (a.recorrente) acao = `<button class="botao texto" id="cancelar-assinatura">Cancelar renovação automática</button>`;
  else if (["essencial", "profissional", "consultor"].includes(p.codigo) && a.metodo === "avulso")
    acao = `<button class="botao" data-assinar="${p.codigo}">Renovar agora</button>`;
  else if (p.codigo === "suspenso") acao = `<span class="fraco">Escolha um plano abaixo para reativar.</span>`;
  return `<section class="bloco"><div class="bloco-titulo"><h2>Sua assinatura</h2>${a.status ? carimboStatus(ROTULO_ASSINATURA, a.status) : ""}</div>
    <div class="grade grade-3">
      <div class="indicador"><b>${esc(p.nome)}</b><span>${a.ciclo === "anual" ? "Cobrança anual" : "Cobrança mensal"}</span></div>
      <div class="indicador ${pago && fmt.dias(a.pago_ate) < 0 ? "alerta" : ""}"><b>${pago ? fmt.data(a.pago_ate) : "—"}</b>
        <span>${a.recorrente ? "próxima cobrança" : a.status === "cancelada" ? "acesso garantido até" : "acesso pago até"}</span></div>
      <div class="indicador"><b style="font-size:1rem;padding-top:8px">${esc(forma)}</b><span>forma de pagamento</span></div>
    </div>${acao ? `<div style="margin-top:14px">${acao}</div>` : ""}</section>`;
}

function precoCiclo(v, ciclo) { return ciclo === "anual" ? v.preco * S.cobranca.anual_meses_pagos : v.preco; }

function modalCheckout(plano, ciclo) {
  const v = S.planos[plano];
  if (!S.cobranca.online) { window.open(CERTAME.LINK_ASSINATURA, "_blank"); return; }
  const total = precoCiclo(v, ciclo);
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
    try { const d = await api("POST", "/api/billing/checkout", { plano, ciclo, metodo: b.dataset.metodo }); location.href = d.url; }
    catch (e) { $("#erro-checkout", m).innerHTML = erroTela(e); }
  }));
}

function barraUso(rotulo, usado, limite) {
  const ilimitado = limite === true || limite === undefined;
  const pct = ilimitado || !limite ? 0 : Math.min(100, Math.round((usado / limite) * 100));
  return `<div><div class="meta" style="justify-content:space-between"><span>${esc(rotulo)}</span><span>${usado}${ilimitado ? "" : ` / ${limite}`}</span></div>
    ${ilimitado ? "" : `<div class="barra"><i style="width:${pct}%;${pct >= 100 ? "background:var(--carimbo)" : ""}"></i></div>`}</div>`;
}

function planoHtml(codigo, v, atual, ciclo = "mensal") {
  const limite = (n, unid) => (n === true ? `${unid} ilimitado(a)s` : n === false || n === 0 ? `Sem ${unid}` : `${n} ${unid}${n > 1 ? "s" : ""}/mês`);
  const valor = precoCiclo(v, ciclo);
  const preco = !v.preco ? "Grátis" : ciclo === "anual"
    ? `${fmt.moeda(valor / 12)}<small>/mês</small><span class="preco-nota">${fmt.moeda(valor)} por ano</span>`
    : `${fmt.moeda(valor)}<small>/mês</small>`;
  const botao = codigo === atual ? carimbo("Seu plano", "ok")
    : codigo === "trial" ? "" : `<button class="botao ${codigo === "profissional" ? "" : "secundario"}" data-assinar="${codigo}">Assinar</button>`;
  return `<div class="plano ${codigo === atual ? "atual" : ""}"><h3>${esc(v.nome)}</h3><div class="preco">${preco}</div>
    <ul><li>${v.empresas} empresa(s)</li><li>${limite(v.analises, "análise de edital")}</li><li>${limite(v.concorrentes, "análise de concorrente")}</li>
      <li>${v.pecas ? "Gerador de peças" : "Sem gerador de peças"}</li><li>${v.precos ? "Inteligência de preços" : "Sem inteligência de preços"}</li>
      ${v.marca ? "<li>Relatórios com sua marca</li>" : ""}</ul>
    ${botao}</div>`;
}

// ---------------------------------------------------------------- glossário
const GLOSSARIO = [
  ["Pregão eletrônico", "Modalidade mais comum para bens e serviços comuns, com disputa por lances em ambiente eletrônico."],
  ["Habilitação", "Conjunto de documentos que comprovam que a empresa pode contratar com o poder público: jurídicos, fiscais, trabalhistas, econômico-financeiros e técnicos."],
  ["Impugnação", "Pedido para corrigir uma ilegalidade do edital, feito até 3 dias úteis antes da sessão."],
  ["Pedido de esclarecimento", "Pergunta formal sobre um ponto do edital que não está claro, no mesmo prazo da impugnação."],
  ["Intenção de recorrer", "Manifestação, feita na própria sessão, de que a empresa vai recorrer do resultado — sem ela, perde-se o direito ao recurso."],
  ["Recurso administrativo", "Peça com as razões do recurso, protocolada em até 3 dias úteis após a intenção de recorrer."],
  ["Inexequibilidade", "Quando o preço da proposta é tão baixo que não cobre os custos mínimos de execução do contrato."],
  ["CATMAT / CATSER", "Códigos do catálogo de materiais e serviços do governo federal, usados para pesquisar preços praticados."],
  ["CEIS / CNEP", "Cadastros públicos de empresas impedidas ou declaradas inidôneas para contratar com o poder público."],
  ["Reequilíbrio econômico-financeiro", "Ajuste do contrato para recompor um desequilíbrio causado por fato imprevisível, distinto do reajuste anual."],
  ["Repactuação", "Forma de reajuste específica dos contratos de serviço contínuo com mão de obra, baseada na variação real dos custos."],
  ["Portal da disputa", "Sistema onde a sessão pública efetivamente ocorre (pode ser diferente do PNCP, que apenas publica o edital)."],
];
V.glossario = async (el) => {
  el.innerHTML = `<div class="cabecalho"><h1>Glossário</h1></div><section class="bloco">
    ${GLOSSARIO.map(([t, d]) => `<div class="lista-item"><div class="corpo"><b>${esc(t)}</b><p>${esc(d)}</p></div></div>`).join("")}</section>`;
};

