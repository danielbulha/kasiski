// Conta, planos e preferências.
V.conta = async (el) => {
  await atualizarConta();
  const p = S.plano;
  el.innerHTML = `
    <div class="cabecalho"><div><h1>Plano e conta</h1><p>${esc(S.usuario.nome)} · ${esc(S.usuario.email)}</p></div></div>
    <section class="bloco"><h2>Uso deste mês</h2>
      <div class="grade grade-3">
        ${barraUso("Análises de edital", p.uso.analises, p.analises)}
        ${barraUso("Análises de concorrente", p.uso.concorrentes, p.concorrentes)}
        ${barraUso("Empresas cadastradas", p.uso.empresas, p.empresas)}
      </div></section>
    <section class="bloco"><h2>Planos</h2>
      <div class="grade grade-4">${["trial", "essencial", "profissional", "consultor"].filter((k) => S.planos[k]).map((k) => planoHtml(k, S.planos[k], p.codigo)).join("")}</div>
    </section>
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
  $$("[data-assinar]", el).forEach((b) => b.onclick = () => window.open(CERTAME.LINK_ASSINATURA, "_blank"));
};

function barraUso(rotulo, usado, limite) {
  const ilimitado = limite === true || limite === undefined;
  const pct = ilimitado || !limite ? 0 : Math.min(100, Math.round((usado / limite) * 100));
  return `<div><div class="meta" style="justify-content:space-between"><span>${esc(rotulo)}</span><span>${usado}${ilimitado ? "" : ` / ${limite}`}</span></div>
    ${ilimitado ? "" : `<div class="barra"><i style="width:${pct}%;${pct >= 100 ? "background:var(--carimbo)" : ""}"></i></div>`}</div>`;
}

function planoHtml(codigo, v, atual) {
  const limite = (n, unid) => (n === true ? `${unid} ilimitado(a)s` : n === false || n === 0 ? `Sem ${unid}` : `${n} ${unid}${n > 1 ? "s" : ""}/mês`);
  return `<div class="plano ${codigo === atual ? "atual" : ""}"><h3>${esc(v.nome)}</h3><div class="preco">${v.preco ? fmt.moeda(v.preco) : "Grátis"}${v.preco ? "<small>/mês</small>" : ""}</div>
    <ul><li>${v.empresas} empresa(s)</li><li>${limite(v.analises, "análise de edital")}</li><li>${limite(v.concorrentes, "análise de concorrente")}</li>
      <li>${v.pecas ? "Gerador de peças" : "Sem gerador de peças"}</li><li>${v.precos ? "Inteligência de preços" : "Sem inteligência de preços"}</li>
      ${v.marca ? "<li>Relatórios com sua marca</li>" : ""}</ul>
    ${codigo === atual ? carimbo("Seu plano", "ok") : `<button class="botao secundario" data-assinar>Assinar</button>`}</div>`;
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

// ---------------------------------------------------------------- admin
V.admin = async (el) => {
  const [contas, revisoes] = await Promise.all([api("GET", "/api/admin/contas"), api("GET", "/api/admin/revisoes")]);
  el.innerHTML = `
    <div class="cabecalho"><h1>Administração</h1></div>
    <div class="abas" role="tablist"><button class="ativa" data-a-aba="revisoes">Revisões pendentes</button><button data-a-aba="contas">Contas</button></div>
    <div id="painel-admin"></div>`;
  const painel = $("#painel-admin", el);
  const mostrar = (aba) => {
    $$("[data-a-aba]", el).forEach((b) => b.classList.toggle("ativa", b.dataset.aAba === aba));
    if (aba === "revisoes") desenharRevisoes(painel, revisoes); else desenharContas(painel, contas);
  };
  $$("[data-a-aba]", el).forEach((b) => b.onclick = () => mostrar(b.dataset.aAba));
  mostrar("revisoes");
};

function desenharRevisoes(el, revisoes) {
  const pendentes = revisoes.filter((r) => r.status !== "concluida" && r.status !== "cancelada");
  el.innerHTML = `<section class="bloco">${pendentes.length ? pendentes.map((r) => `<div class="lista-item"><div class="corpo">
      <b>${esc(r.peca_titulo)}</b><p>${esc(r.conta)} · ${carimbo(r.status, r.status === "pendente" ? "aviso" : "neutro")} ${r.valor ? "· " + fmt.moeda(r.valor) : ""}
      ${r.prazo_desejado ? " · prazo " + fmt.data(r.prazo_desejado) : ""}</p>${r.observacoes ? `<p class="fraco">${esc(r.observacoes)}</p>` : ""}</div>
      <button class="botao pequeno secundario" data-rev="${r.id}">Gerenciar</button></div>`).join("")
    : vazio("Nenhuma revisão pendente", "")}</section>`;
  $$("[data-rev]", el).forEach((b) => b.onclick = () => modalRevisaoAdmin(revisoes.find((r) => r.id == b.dataset.rev), el, revisoes));
}

function modalRevisaoAdmin(r, elLista, revisoes) {
  const m = modal({
    titulo: r.peca_titulo, largo: true, corpo: `
    <textarea class="editor" id="conteudo-rev" style="min-height:320px">${esc(r.conteudo)}</textarea>
    <form id="form-rev-admin" style="margin-top:14px">
      <div class="linha-campos"><div class="campo"><label>Status</label><select name="status">
        <option value="pendente" ${r.status === "pendente" ? "selected" : ""}>Pendente</option>
        <option value="em_andamento" ${r.status === "em_andamento" ? "selected" : ""}>Em andamento</option>
        <option value="concluida" ${r.status === "concluida" ? "selected" : ""}>Concluída</option>
        <option value="cancelada" ${r.status === "cancelada" ? "selected" : ""}>Cancelada</option></select></div>
        <div class="campo"><label>Valor (R$)</label><input name="valor" value="${r.valor ?? ""}" inputmode="decimal"></div></div>
      <div class="campo"><label>Parecer para o cliente</label><textarea name="parecer">${esc(r.parecer || "")}</textarea></div>
      <button class="botao" style="width:100%" type="submit">Salvar</button></form>`,
  });
  $("#form-rev-admin", m).onsubmit = async (ev) => {
    ev.preventDefault();
    const d = dadosForm(ev.target); d.conteudo_revisado = $("#conteudo-rev", m).value;
    await api("PATCH", `/api/admin/revisoes/${r.id}`, d);
    m.fechar(); toast("Revisão atualizada.", "ok"); V.admin(elLista.closest("#conteudo"));
  };
}

function desenharContas(el, contas) {
  el.innerHTML = `<section class="bloco tabela-rolagem"><table><thead><tr><th>Conta</th><th>Usuários</th><th>Plano</th><th>Uso (análises/mês)</th><th>Custo IA/mês</th><th></th></tr></thead>
    <tbody>${contas.map((c) => `<tr><td>${esc(c.nome)}</td><td>${c.usuarios.map(esc).join(", ")}</td>
      <td><select data-plano="${c.id}">${Object.keys(S.planos).map((k) => `<option value="${k}" ${c.plano === k ? "selected" : ""}>${S.planos[k].nome}</option>`).join("")}</select></td>
      <td>${c.uso.analises}</td><td>$${c.custo_ia_total_usd}</td><td></td></tr>`).join("")}</tbody></table></section>`;
  $$("[data-plano]", el).forEach((s) => s.onchange = async () => { await api("PATCH", `/api/admin/contas/${s.dataset.plano}`, { plano: s.value }); toast("Plano atualizado.", "ok"); });
}
