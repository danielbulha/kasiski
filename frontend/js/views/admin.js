// Administração: CRM de contas (testes e assinaturas), funil de conversão, receitas e revisões.
const ETAPAS_CRM = {
  cadastrado: ["Cadastrado", "neutro"], ativado: ["Empresa cadastrada", "neutro"], engajado: ["Usou a IA", "oficio"],
  teste_expirado: ["Teste expirado", "aviso"], assinante: ["Assinante", "ok"], cancelando: ["Cancelou (ainda ativo)", "aviso"],
  inadimplente: ["Inadimplente", "erro"], cancelado: ["Cancelado", "neutro"], suspenso: ["Suspenso", "erro"],
};
const FILTROS_CRM = [
  ["todos", "Todos", () => true],
  ["teste", "Em teste", (c) => c.plano === "trial" && c.etapa !== "teste_expirado"],
  ["expirando", "Teste acaba em 48h", (c) => c.dias_trial !== null && c.dias_trial >= 0 && c.dias_trial <= 2],
  ["expirado", "Teste expirado", (c) => c.etapa === "teste_expirado"],
  ["assinantes", "Assinantes", (c) => ["assinante", "cancelando"].includes(c.etapa)],
  ["inadimplentes", "Inadimplentes", (c) => ["inadimplente", "suspenso"].includes(c.etapa)],
  ["cancelados", "Cancelados", (c) => ["cancelado", "cancelando"].includes(c.etapa)],
];

V.admin = async (el) => {
  const aba = V.admin.aba || "crm";
  el.innerHTML = `
    <div class="cabecalho"><h1>Administração</h1><button class="botao pequeno secundario" id="teste-email">Testar envio de e-mail</button></div>
    <div class="abas" role="tablist">
      ${[["crm", "Clientes e testes"], ["funil", "Funil de conversão"], ["receitas", "Receitas"], ["tabelas", "Tabelas de preços"], ["revisoes", "Pedidos de advogado"], ["logs", "Logs de erros"]]
        .map(([k, t]) => `<button role="tab" data-a-aba="${k}" class="${aba === k ? "ativa" : ""}" aria-selected="${aba === k}">${t}</button>`).join("")}
    </div>
    <div id="painel-admin"><p class="carregando">Carregando…</p></div>`;
  $$("[data-a-aba]", el).forEach((b) => b.onclick = () => { V.admin.aba = b.dataset.aAba; V.admin(el); });
  $("#teste-email", el).onclick = () => {
    const m = modal({ titulo: "Testar envio de e-mail", corpo: `<form id="form-teste-email">
      <p class="fraco">Envia um e-mail de teste pelo Resend e mostra a resposta exata do serviço.</p>
      <div class="campo"><label for="te-para">Enviar para</label><input id="te-para" name="para" type="email" value="${esc(S.usuario.email)}"></div>
      <button class="botao" type="submit">Enviar teste</button><div id="te-resultado" style="margin-top:14px"></div></form>` });
    $("#form-teste-email", m).onsubmit = async (ev) => {
      ev.preventDefault();
      const b = ev.target.querySelector("button");
      await ocupado(b, "Enviando…", async () => {
        try {
          const r = await api("POST", "/api/admin/teste-email", dadosForm(ev.target));
          $("#te-resultado", m).innerHTML = `<div class="aviso ${r.ok ? "ok" : "erro"}"><b>${r.ok ? "Enviado. Confira a caixa de entrada (e o spam)." : "O envio falhou."}</b><br>
            Remetente usado: ${esc(r.remetente)}${r.remetente_valido ? "" : " <b>(formato inválido)</b>"}${r.remetente_limpo_diferente ? `<br><small>Valor original no Render: ${esc(r.remetente_bruto)} (limpo automaticamente)</small>` : ""}<br>Chave: ${r.chave_configurada ? esc(r.chave_inicio) : "não configurada"}${r.status ? ` · HTTP ${r.status}` : ""}
            <pre style="white-space:pre-wrap;margin:8px 0 0;font-size:.8rem">${esc(r.resposta || "")}</pre></div>`;
        } catch (e) { $("#te-resultado", m).innerHTML = erroTela(e); }
      });
    };
  };
  const painel = $("#painel-admin", el);
  try {
    if (aba === "crm") await abaCrm(painel);
    else if (aba === "funil") await abaFunil(painel);
    else if (aba === "receitas") await abaReceitas(painel);
    else if (aba === "tabelas") await abaTabelasAdmin(painel);
    else if (aba === "logs") await abaLogs(painel);
    else desenharRevisoes(painel, await api("GET", "/api/admin/revisoes"));
  } catch (e) { painel.innerHTML = erroTela(e); }
};

const indicador = (valor, rotulo, alerta = false) => `<div class="indicador ${alerta ? "alerta" : ""}"><b>${valor}</b><span>${esc(rotulo)}</span></div>`;
const pct = (a, b) => (b ? Math.round((100 * a) / b) : 0);

// ---------------------------------------------------------------- CRM
async function abaCrm(el) {
  const d = await api("GET", "/api/admin/crm");
  const r = d.resumo;
  const estado = { filtro: V.admin.filtro || "todos", busca: "" };
  el.innerHTML = `
    <section class="bloco"><div class="grade grade-4 grade-kpi">
      ${indicador(r.testes_ativos, "testes grátis ativos")}
      ${indicador(r.testes_expirando, "testes terminando em 48h", r.testes_expirando > 0)}
      ${indicador(r.assinantes, "assinantes")}
      ${indicador(r.inadimplentes, "inadimplentes", r.inadimplentes > 0)}
    </div><p class="fraco" style="margin:12px 0 0">${r.total} contas no total · ${r.novos_7d} novas nos últimos 7 dias · ${r.testes_expirados} testes expirados sem assinar</p></section>
    <div class="filtros-admin">
      <div class="chips" role="group" aria-label="Filtrar contas">${FILTROS_CRM.map(([k, t]) => `<button data-filtro="${k}" aria-pressed="${estado.filtro === k}">${t}</button>`).join("")}</div>
      <input type="search" id="busca-crm" placeholder="Buscar nome, e-mail ou origem" aria-label="Buscar contas">
    </div>
    <section class="bloco tabela-rolagem" id="tabela-crm"></section>`;
  const desenhar = () => {
    const f = FILTROS_CRM.find((x) => x[0] === estado.filtro)[2];
    const b = estado.busca.toLowerCase();
    const lista = d.contas.filter(f).filter((c) => !b || [c.nome, c.origem, ...c.usuarios.map((u) => u.email)].join(" ").toLowerCase().includes(b));
    $$("[data-filtro]", el).forEach((x) => x.setAttribute("aria-pressed", x.dataset.filtro === estado.filtro));
    $("#tabela-crm", el).innerHTML = lista.length ? `<table><thead><tr><th>Conta</th><th>Etapa</th><th>Plano</th><th>Teste / acesso</th>
      <th>Análises (mês)</th><th>Receita total</th><th>Custo IA (mês)</th><th>Último acesso</th><th></th></tr></thead>
      <tbody>${lista.map(linhaCrm).join("")}</tbody></table>` : vazio("Nenhuma conta neste filtro", "");
    $$("[data-conta]", el).forEach((x) => x.onclick = () => modalConta(Number(x.dataset.conta), () => abaCrm(el)));
  };
  $$("[data-filtro]", el).forEach((x) => x.onclick = () => { estado.filtro = V.admin.filtro = x.dataset.filtro; desenhar(); });
  $("#busca-crm", el).oninput = (ev) => { estado.busca = ev.target.value; desenhar(); };
  desenhar();
}

function linhaCrm(c) {
  const email = c.usuarios[0]?.email || "";
  let acesso = "—";
  if (c.plano === "trial" && c.dias_trial !== null) acesso = c.dias_trial < 0 ? `acabou há ${-c.dias_trial}d` : c.dias_trial === 0 ? "acaba hoje" : `${c.dias_trial} dia(s)`;
  else if (c.pago_ate) acesso = `até ${fmt.data(c.pago_ate)}`;
  const limite = typeof c.limite_analises === "number" ? ` / ${c.limite_analises}` : "";
  return `<tr>
    <td><b>${esc(c.nome)}</b><br><small>${esc(email)}${c.origem ? ` · ${esc(c.origem)}` : ""}</small>${c.usuarios[0] && !c.usuarios[0].verificado ? `<br>${carimbo("e-mail não confirmado", "aviso")}` : ""}${c.etiqueta_crm ? `<br>${carimbo(c.etiqueta_crm, "oficio")}` : ""}</td>
    <td>${carimboStatus(ETAPAS_CRM, c.etapa)}${c.iniciou_checkout && !c.receita_total ? `<br><small>abriu o pagamento</small>` : ""}</td>
    <td>${esc(c.plano_nome)}${c.ciclo ? `<br><small>${c.ciclo}${c.metodo_pagamento === "recorrente" ? " · cartão auto" : c.metodo_pagamento === "avulso" ? " · Pix/avulso" : ""}</small>` : ""}</td>
    <td>${acesso}</td><td>${c.analises_mes}${limite}</td><td>${fmt.moeda(c.receita_total)}</td><td>${fmt.moeda(c.custo_ia_mes_brl)}</td>
    <td>${c.ultimo_acesso ? fmt.data(c.ultimo_acesso) : "nunca"}</td>
    <td><button class="botao pequeno secundario" data-conta="${c.id}">Abrir</button></td></tr>`;
}

async function modalConta(id, aoSalvar) {
  const c = await api("GET", `/api/admin/crm/${id}`);
  const u = c.usuarios[0] || {};
  const zap = (c.telefone || "").replace(/\D/g, "");
  const m = modal({
    titulo: c.nome, largo: true, corpo: `
    <div class="meta" style="margin:0 0 14px">${carimboStatus(ETAPAS_CRM, c.etapa)}<span>${esc(u.nome || "")} · ${esc(u.email || "")}</span>
      <span>cadastro ${fmt.data(c.criado_em)}</span><span>origem: ${esc(c.origem || "direto")}${c.campanha ? ` / ${esc(c.campanha)}` : ""}</span></div>
    <div class="acoes" style="margin-bottom:16px">
      ${u.email ? `<a class="botao pequeno secundario" href="mailto:${esc(u.email)}">${icone("editar", 14)} E-mail</a>` : ""}
      ${zap ? `<a class="botao pequeno secundario" target="_blank" rel="noopener" href="https://wa.me/${zap.length <= 11 ? "55" + zap : zap}">WhatsApp</a>` : ""}
    </div>
    <div class="grade grade-4 grade-kpi" style="margin-bottom:18px">
      ${indicador(c.analises_total, "análises de edital (total)")}${indicador(c.empresas, "empresas cadastradas")}
      ${indicador(fmt.moeda(c.receita_total), "receita total")}${indicador(fmt.moeda(c.custo_ia_total_brl), "custo de IA total")}
    </div>
    <form id="form-crm">
      <div class="linha-campos">
        <div class="campo"><label for="crm-plano">Plano</label><select id="crm-plano" name="plano">${Object.keys(S.planos).map((k) => `<option value="${k}" ${c.plano === k ? "selected" : ""}>${esc(S.planos[k].nome)}</option>`).join("")}</select></div>
        <div class="campo"><label for="crm-status">Situação da assinatura</label><select id="crm-status" name="assinatura_status">
          ${[["", "—"], ["ativa", "Ativa"], ["pendente", "Aguardando pagamento"], ["pausada", "Pausada"], ["inadimplente", "Inadimplente"], ["cancelada", "Cancelada"]]
            .map(([k, t]) => `<option value="${k}" ${(c.assinatura_status || "") === k ? "selected" : ""}>${t}</option>`).join("")}</select></div>
        <div class="campo"><label for="crm-ciclo">Ciclo</label><select id="crm-ciclo" name="ciclo"><option value="mensal" ${c.ciclo !== "anual" ? "selected" : ""}>Mensal</option><option value="anual" ${c.ciclo === "anual" ? "selected" : ""}>Anual</option></select></div>
      </div>
      <div class="linha-campos">
        <div class="campo"><label for="crm-pago">Acesso pago até</label><input id="crm-pago" type="date" name="pago_ate" value="${fmt.paraInput(c.pago_ate)}"></div>
        <div class="campo"><label for="crm-trial">Fim do teste grátis</label><input id="crm-trial" type="date" name="trial_fim" value="${fmt.paraInput(c.trial_fim)}"></div>
        <div class="campo"><label for="crm-tel">Telefone</label><input id="crm-tel" name="telefone" value="${esc(c.telefone || "")}"></div>
        <div class="campo"><label for="crm-etq">Etiqueta</label><input id="crm-etq" name="etiqueta_crm" list="etiquetas-crm" value="${esc(c.etiqueta_crm || "")}">
          <datalist id="etiquetas-crm"><option value="quente"><option value="negociando"><option value="sem resposta"><option value="perdido"></datalist></div>
      </div>
      <div class="campo"><label for="crm-notas">Anotações</label><textarea id="crm-notas" name="notas_crm" rows="4" placeholder="Conversas, objeções, próximos passos">${esc(c.notas_crm || "")}</textarea></div>
      <div class="acoes"><button class="botao" type="submit">Salvar</button>
        <button class="botao secundario" type="button" id="estender-trial">+7 dias de teste</button></div>
    </form>
    <h3 style="margin-top:22px">Uso da IA por recurso</h3>
    <p class="fraco">${Object.entries(c.uso_recursos).map(([k, n]) => `${esc(k)}: ${n}`).join(" · ") || "Nenhum uso ainda."}</p>
    <h3 style="margin-top:18px">Pagamentos</h3>
    ${c.cobrancas.length ? `<div class="tabela-rolagem"><table><thead><tr><th>Data</th><th>Descrição</th><th>Forma</th><th>Valor</th><th>Situação</th></tr></thead><tbody>
      ${c.cobrancas.map((x) => `<tr><td>${fmt.data(x.pago_em || x.criado_em)}</td><td>${esc(x.descricao || "")}${x.origem === "manual" ? " <small>(manual)</small>" : ""}</td>
        <td>${esc(ROTULO_MEIO[x.meio] || x.meio || "—")}</td><td>${fmt.moeda(x.valor)}</td><td>${carimboStatus(ROTULO_COBRANCA, x.status)}</td></tr>`).join("")}</tbody></table></div>`
      : `<p class="fraco">Nenhum pagamento registrado.</p>`}
    ${c.mp_assinatura_id ? `<p class="fraco" style="margin-top:8px">Assinatura no Mercado Pago: ${esc(c.mp_assinatura_id)}</p>` : ""}`,
  });
  const salvar = async (extra = {}) => {
    const d = { ...dadosForm($("#form-crm", m)), ...extra };
    if (!d.trial_fim) delete d.trial_fim;
    if (extra.estender_trial_dias) { delete d.trial_fim; delete d.plano; }
    try { await api("PATCH", `/api/admin/contas/${id}`, d); m.fechar(); toast("Conta atualizada.", "ok"); aoSalvar(); } catch (e) { avisarErro(e); }
  };
  $("#form-crm", m).onsubmit = (ev) => { ev.preventDefault(); salvar(); };
  $("#estender-trial", m).onclick = () => salvar({ estender_trial_dias: 7 });
}

// ---------------------------------------------------------------- funil
async function abaFunil(el) {
  const dias = V.admin.dias || 30;
  const d = await api("GET", `/api/admin/funil?dias=${dias}`);
  const topo = Math.max(1, ...d.etapas.map((e) => e.total));
  const cad = d.etapas.find((e) => e.chave === "cadastros").total;
  const pag = d.etapas.find((e) => e.chave === "pagantes").total;
  const vis = d.etapas.find((e) => e.chave === "visitas").total;
  el.innerHTML = `
    <div class="filtros-admin"><div class="chips" role="group" aria-label="Período">
      ${[7, 30, 90, 365].map((n) => `<button data-dias="${n}" aria-pressed="${n === dias}">${n === 365 ? "12 meses" : `${n} dias`}</button>`).join("")}</div></div>
    <section class="bloco"><div class="grade grade-4 grade-kpi">
      ${indicador(vis, "visitantes na página inicial")}${indicador(cad, "contas criadas")}
      ${indicador(pct(pag, cad) + "%", "de conversão teste → assinante")}
      ${indicador(d.dias_ate_pagar === null ? "—" : `${fmt.num(d.dias_ate_pagar, 1)} d`, "tempo médio até pagar")}
    </div></section>
    <section class="bloco"><h2>Funil dos últimos ${dias} dias</h2>
      <p class="fraco">Contas criadas no período, acompanhadas até hoje. Cada barra mostra quantas pessoas chegaram a essa etapa.</p>
      <div class="funil">${d.etapas.map((e, i) => {
        const ant = i ? d.etapas[i - 1].total : null;
        return `<div class="funil-linha"><span class="funil-rotulo">${esc(e.rotulo)}</span>
          <div class="funil-trilho" title="${esc(e.rotulo)}: ${e.total}"><i style="width:${Math.max(e.total ? 1.5 : 0, (100 * e.total) / topo)}%"></i></div>
          <span class="funil-valor"><b>${e.total}</b>${ant !== null ? `<small>${ant ? pct(e.total, ant) + "% da anterior" : "—"}</small>` : ""}</span></div>`;
      }).join("")}</div>
      <p class="fraco" style="margin-top:10px">Visitas e cliques contam só visitantes a partir de agora (o rastreamento começou com esta versão).</p></section>
    <div class="grade grade-2">
      <section class="bloco"><h2>Por origem</h2>${d.por_origem.length ? `<div class="tabela-rolagem"><table><thead><tr><th>Origem</th><th>Cadastros</th><th>Usaram a IA</th><th>Assinaram</th><th>Conversão</th></tr></thead>
        <tbody>${d.por_origem.map((o) => `<tr><td>${esc(o.origem)}</td><td>${o.cadastros}</td><td>${o.engajados}</td><td>${o.pagantes}</td><td>${pct(o.pagantes, o.cadastros)}%</td></tr>`).join("")}</tbody></table></div>
        <p class="fraco" style="margin-top:10px">Use links com <code>?utm_source=instagram&amp;utm_campaign=nome</code> para separar as origens.</p>` : vazio("Sem cadastros no período", "")}</section>
      <section class="bloco"><h2>Leads para abordar agora</h2>${d.leads.length ? d.leads.slice(0, 15).map((l) => `<div class="lista-item"><div class="corpo">
        <b>${esc(l.nome)}</b> ${carimbo(l.temperatura, l.temperatura === "quente" ? "erro" : l.temperatura === "morno" ? "aviso" : "neutro")}
        <p>${esc(l.usuarios[0]?.email || "")} · ${l.analises_total} análise(s) · ${l.dias_trial === null ? "" : l.dias_trial < 0 ? `teste acabou há ${-l.dias_trial}d` : `teste acaba em ${l.dias_trial}d`}${l.iniciou_checkout ? " · abriu o pagamento" : ""}</p></div>
        <button class="botao pequeno secundario" data-conta="${l.id}">Abrir</button></div>`).join("") : vazio("Nenhum lead em teste", "")}</section>
    </div>`;
  $$("[data-dias]", el).forEach((b) => b.onclick = () => { V.admin.dias = Number(b.dataset.dias); abaFunil(el); });
  $$("[data-conta]", el).forEach((b) => b.onclick = () => modalConta(Number(b.dataset.conta), () => abaFunil(el)));
}

// ---------------------------------------------------------------- receitas
async function abaReceitas(el) {
  const meses = V.admin.meses || 12;
  const d = await api("GET", `/api/admin/receitas?meses=${meses}`);
  const k = d.indicadores;
  const nomeMes = (m) => new Date(m + "-15").toLocaleDateString("pt-BR", { month: "short", year: "2-digit" }).replace(". de ", "/").replace(".", "");
  const maximo = Math.max(1, ...d.serie.map((s) => s.assinaturas + s.servicos));
  el.innerHTML = `
    <div class="filtros-admin"><div class="chips" role="group" aria-label="Período">
      ${[6, 12, 24].map((n) => `<button data-meses="${n}" aria-pressed="${n === meses}">${n} meses</button>`).join("")}</div>
      <button class="botao pequeno" id="lancar-receita">${icone("editar", 14)} Lançar receita manual</button></div>
    <section class="bloco"><div class="grade grade-4 grade-kpi">
      ${indicador(fmt.moeda(k.mrr), `receita recorrente mensal (MRR) · ${k.assinantes} assinante(s)`)}
      ${indicador(fmt.moeda(k.receita_mes), "recebido neste mês")}
      ${indicador(fmt.moeda(k.resultado_mes), "resultado do mês (após tarifas e IA)", k.resultado_mes < 0)}
      ${indicador(k.churn_mes + "%", `cancelamentos no mês (${k.cancelamentos_mes})`, k.churn_mes > 5)}
    </div>
    <p class="fraco" style="margin:12px 0 0">ARR ${fmt.moeda(k.arr)} · ticket médio ${fmt.moeda(k.ticket_medio)}/mês · custo de IA no mês ${fmt.moeda(k.custo_ia_mes)} (US$ 1 = ${fmt.moeda(k.usd_brl)}) · ${fmt.moeda(k.receita_periodo)} recebidos em ${meses} meses${k.pendentes ? ` · ${k.pendentes} pagamento(s) pendente(s)` : ""}</p></section>
    <section class="bloco"><div class="bloco-titulo"><h2>Receita por mês</h2>
      <div class="legenda"><span><i style="background:var(--serie-1)"></i>Assinaturas</span><span><i style="background:var(--serie-2)"></i>Serviços e outros</span></div></div>
      <div class="colunas" role="img" aria-label="Receita por mês, detalhada na tabela abaixo">
        ${d.serie.map((s) => {
          const total = s.assinaturas + s.servicos;
          return `<div class="coluna" tabindex="0">
            <div class="coluna-dica"><b>${nomeMes(s.mes)}</b>Assinaturas ${fmt.moeda(s.assinaturas)}<br>Serviços ${fmt.moeda(s.servicos)}<br>Custo IA ${fmt.moeda(s.custo_ia)}<br>Resultado ${fmt.moeda(s.resultado)}</div>
            <div class="coluna-barra">${s.servicos ? `<i class="s2" style="height:${(100 * s.servicos) / maximo}%"></i>` : ""}${s.assinaturas ? `<i class="s1" style="height:${(100 * s.assinaturas) / maximo}%"></i>` : ""}</div>
            <span class="coluna-rotulo">${nomeMes(s.mes)}</span>${total ? `<span class="coluna-valor">${fmt.num(total / 1000, 1)}k</span>` : ""}</div>`;
        }).join("")}</div>
      <details style="margin-top:14px"><summary>Ver em tabela</summary><div class="tabela-rolagem"><table><thead><tr><th>Mês</th><th>Assinaturas</th><th>Serviços</th><th>Estornos</th><th>Tarifas MP</th><th>Custo IA</th><th>Resultado</th></tr></thead>
        <tbody>${d.serie.slice().reverse().map((s) => `<tr><td>${nomeMes(s.mes)}</td><td>${fmt.moeda(s.assinaturas)}</td><td>${fmt.moeda(s.servicos)}</td><td>${fmt.moeda(s.estornos)}</td>
          <td>${fmt.moeda(s.tarifas)}</td><td>${fmt.moeda(s.custo_ia)}</td><td><b>${fmt.moeda(s.resultado)}</b></td></tr>`).join("")}</tbody></table></div></details></section>
    <div class="grade grade-2">
      <section class="bloco"><h2>MRR por plano</h2>${d.mrr_por_plano.length ? d.mrr_por_plano.map((p) => barraValor(p.nome, p.mrr, k.mrr)).join("") : vazio("Nenhum assinante ativo", "")}</section>
      <section class="bloco"><h2>Recebido por forma de pagamento</h2>${d.por_meio.length ? d.por_meio.map((p, _, arr) => barraValor(ROTULO_MEIO[p.meio] || p.meio, p.valor, arr.reduce((a, b) => a + b.valor, 0))).join("") : vazio("Nada recebido no período", "")}</section>
    </div>
    <section class="bloco"><h2>Últimos lançamentos</h2>${d.cobrancas.length ? `<div class="tabela-rolagem"><table><thead><tr><th>Data</th><th>Conta</th><th>Descrição</th><th>Forma</th><th>Valor</th><th>Líquido</th><th>Situação</th><th></th></tr></thead>
      <tbody>${d.cobrancas.map((c) => `<tr><td>${fmt.data(c.pago_em || c.criado_em)}</td><td>${esc(c.conta || "—")}</td><td>${esc(c.descricao || "")}${c.origem === "manual" ? " <small>(manual)</small>" : ""}</td>
        <td>${esc(ROTULO_MEIO[c.meio] || c.meio || "—")}</td><td>${fmt.moeda(c.valor)}</td><td>${fmt.moeda(c.valor_liquido)}</td><td>${carimboStatus(ROTULO_COBRANCA, c.status)}</td>
        <td>${c.origem === "manual" ? `<button class="botao texto" data-excluir="${c.id}" aria-label="Excluir lançamento">Excluir</button>` : ""}</td></tr>`).join("")}</tbody></table></div>`
      : vazio("Nenhum pagamento ainda", "Os pagamentos do Mercado Pago aparecem aqui automaticamente.")}</section>
    <p class="fraco">Revisões profissionais concluídas entram como receita de serviço pelo valor combinado. Não lance a mesma revisão também como receita manual.</p>`;
  $$("[data-meses]", el).forEach((b) => b.onclick = () => { V.admin.meses = Number(b.dataset.meses); abaReceitas(el); });
  $("#lancar-receita", el).onclick = () => modalReceita(() => abaReceitas(el));
  $$("[data-excluir]", el).forEach((b) => b.onclick = async () => {
    if (!(await confirmar("Excluir este lançamento manual?", "Excluir"))) return;
    await api("DELETE", `/api/admin/receitas/${b.dataset.excluir}`); toast("Lançamento excluído.", "ok"); abaReceitas(el);
  });
}

function barraValor(rotulo, valor, total) {
  return `<div style="margin-bottom:12px"><div class="meta" style="justify-content:space-between;margin:0"><span>${esc(rotulo)}</span><span>${fmt.moeda(valor)} · ${pct(valor, total)}%</span></div>
    <div class="barra barra-serie"><i style="width:${pct(valor, total)}%"></i></div></div>`;
}

async function modalReceita(aoSalvar) {
  let contas = [];
  try { contas = (await api("GET", "/api/admin/crm")).contas; } catch { /* segue sem vínculo */ }
  const m = modal({
    titulo: "Lançar receita manual", corpo: `<form id="form-receita">
      <p class="fraco">Para valores recebidos fora do Mercado Pago (transferência, consultoria, contrato fechado por fora).</p>
      <div class="linha-campos">
        <div class="campo"><label for="rc-valor">Valor (R$)</label><input id="rc-valor" name="valor" inputmode="decimal" required></div>
        <div class="campo"><label for="rc-data">Recebido em</label><input id="rc-data" name="pago_em" type="date" value="${new Date().toISOString().slice(0, 10)}"></div>
      </div>
      <div class="linha-campos">
        <div class="campo"><label for="rc-tipo">Tipo</label><select id="rc-tipo" name="tipo"><option value="servico">Serviço</option><option value="assinatura">Assinatura</option><option value="outro">Outro</option></select></div>
        <div class="campo"><label for="rc-meio">Forma</label><select id="rc-meio" name="meio"><option value="pix">Pix</option><option value="boleto">Boleto</option><option value="cartao">Cartão</option><option value="outro">Transferência / outro</option></select></div>
      </div>
      <div class="campo"><label for="rc-conta">Cliente (opcional)</label><select id="rc-conta" name="conta_id"><option value="">—</option>${contas.map((c) => `<option value="${c.id}">${esc(c.nome)}</option>`).join("")}</select></div>
      <div class="campo"><label for="rc-desc">Descrição</label><input id="rc-desc" name="descricao" placeholder="Ex.: consultoria de habilitação"></div>
      <div id="erro-receita"></div><button class="botao" style="width:100%" type="submit">Lançar</button></form>`,
  });
  $("#form-receita", m).onsubmit = async (ev) => {
    ev.preventDefault();
    try { await api("POST", "/api/admin/receitas", dadosForm(ev.target)); m.fechar(); toast("Receita lançada.", "ok"); aoSalvar(); }
    catch (e) { $("#erro-receita", m).innerHTML = erroTela(e); }
  };
}

// ---------------------------------------------------------------- revisões profissionais
function desenharRevisoes(el, revisoes) {
  const ordem = { pendente: 0, em_andamento: 1, aguardando_pagamento: 2 };
  const pendentes = revisoes.filter((r) => r.status !== "concluida" && r.status !== "cancelada")
    .sort((a, b) => (ordem[a.status] ?? 9) - (ordem[b.status] ?? 9) || String(a.prazo_desejado || "9").localeCompare(String(b.prazo_desejado || "9")));
  el.innerHTML = `<section class="bloco">${pendentes.length ? pendentes.map((r) => `<div class="lista-item"><div class="corpo">
      <b>${esc(r.peca_titulo)}</b> ${carimbo(r.servico === "elaboracao" ? "Elaboração" : "Revisão", "oficio")}
      <p>${esc(r.conta)}${r.email ? ` (${esc(r.email)})` : ""} · ${carimbo({ aguardando_pagamento: "aguardando pagamento", pendente: "pago · a fazer", em_andamento: "em andamento" }[r.status] || r.status, r.status === "pendente" ? "erro" : "aviso")} ${r.valor ? "· " + fmt.moeda(r.valor) : ""}
      ${r.prazo_desejado ? " · prazo " + fmt.data(r.prazo_desejado) : ""}</p>${r.observacoes ? `<p class="fraco">${esc(r.observacoes)}</p>` : ""}</div>
      <button class="botao pequeno secundario" data-rev="${r.id}">${icone("editar", 14)} Gerenciar</button></div>`).join("")
    : vazio("Nenhuma revisão pendente", "")}</section>`;
  $$("[data-rev]", el).forEach((b) => b.onclick = () => modalRevisaoAdmin(revisoes.find((r) => r.id == b.dataset.rev), el));
}

function modalRevisaoAdmin(r, elLista) {
  const m = modal({
    titulo: r.peca_titulo, largo: true, corpo: `
    <textarea class="editor" id="conteudo-rev" style="min-height:320px">${esc(r.conteudo)}</textarea>
    <form id="form-rev-admin" style="margin-top:14px">
      <div class="linha-campos"><div class="campo"><label>Status</label><select name="status">
        <option value="aguardando_pagamento" ${r.status === "aguardando_pagamento" ? "selected" : ""}>Aguardando pagamento</option>
        <option value="pendente" ${r.status === "pendente" ? "selected" : ""}>Pago · a fazer</option>
        <option value="em_andamento" ${r.status === "em_andamento" ? "selected" : ""}>Em andamento</option>
        <option value="concluida" ${r.status === "concluida" ? "selected" : ""}>Concluída</option>
        <option value="cancelada" ${r.status === "cancelada" ? "selected" : ""}>Cancelada</option></select></div>
        <div class="campo"><label>Valor (R$)</label><input name="valor" value="${r.valor ?? ""}" inputmode="decimal"></div></div>
      <p class="fraco">${r.servico === "elaboracao" ? "Elaboração: escreva a peça no campo acima; ao concluir, ela aparece para o cliente." : "Revisão: ajuste a minuta acima e deixe o parecer abaixo."}</p>
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

// ---------------------------------------------------------------- tabelas de preços de referência
async function abaTabelasAdmin(el) {
  const d = await api("GET", "/api/admin/tabelas");
  el.innerHTML = `
    <section class="bloco"><div class="bloco-titulo"><h2>Tabelas carregadas</h2></div>
      <p class="fraco">Consultadas por todos os clientes na formação de preço e pela IA ao revisar as propostas. Ao sair nova data-base, envie a tabela nova e desative a antiga.</p>
      ${d.tabelas.length ? `<div class="tabela-rolagem"><table><thead><tr><th>Tabela</th><th>Fonte</th><th>UF</th><th>Data-base</th><th>Itens</th><th>Situação</th><th></th></tr></thead>
        <tbody>${d.tabelas.map((t) => `<tr><td><b>${esc(t.nome)}</b>${t.observacao ? `<br><small>${esc(t.observacao)}</small>` : ""}</td><td>${esc(d.fontes[t.fonte] || t.fonte)}</td>
          <td>${esc(t.uf || "todas")}</td><td>${fmt.data(t.data_base)}</td><td>${fmt.num(t.n_itens, 0)}</td>
          <td>${t.ativa ? carimbo("Ativa", "ok") : carimbo("Inativa", "neutro")}</td>
          <td class="acoes-celula"><button class="botao pequeno secundario" data-ativar="${t.id}" data-valor="${t.ativa ? "0" : "1"}">${t.ativa ? "Desativar" : "Ativar"}</button>
            <button class="botao texto pequeno" data-excluir-tab="${t.id}">${icone("excluir", 14)} Excluir</button></td></tr>`).join("")}</tbody></table></div>`
        : vazio("Nenhuma tabela ainda", "Envie a primeira planilha abaixo.")}</section>
    <section class="bloco"><h2>Enviar tabela</h2>
      <p class="fraco">Aceita .xlsx ou .csv (salve arquivos .xls antigos como .xlsx). Fontes oficiais: SINAPI (caixa.gov.br), SICRO (gov.br/dnit), CMED (gov.br/anvisa), SIGTAP (sigtap.datasus.gov.br), convenções coletivas (Mediador/MTE).</p>
      <form id="form-tab">
        <div class="campo"><label for="tb-arq">Planilha</label><input id="tb-arq" name="arquivo" type="file" accept=".xlsx,.xlsm,.csv,.txt" required></div>
        <div id="tb-previa"></div>
      </form></section>`;
  $$("[data-ativar]", el).forEach((b) => b.onclick = async () => { await api("PATCH", `/api/admin/tabelas/${b.dataset.ativar}`, { ativa: b.dataset.valor === "1" }); abaTabelasAdmin(el); });
  $$("[data-excluir-tab]", el).forEach((b) => b.onclick = async () => {
    if (!(await confirmar("Excluir esta tabela e todos os itens dela?", "Excluir"))) return;
    await api("DELETE", `/api/admin/tabelas/${b.dataset.excluirTab}`); toast("Tabela excluída.", "ok"); abaTabelasAdmin(el);
  });
  const arq = $("#tb-arq", el), previa = $("#tb-previa", el);
  arq.onchange = async () => {
    if (!arq.files[0]) return;
    previa.innerHTML = `<p class="carregando">Lendo a planilha…</p>`;
    const fd = new FormData(); fd.append("arquivo", arq.files[0]);
    let pv;
    try { pv = await api("POST", "/api/admin/tabelas/previa", fd); } catch (e) { previa.innerHTML = erroTela(e); return; }
    const opcoes = (sel) => `<option value="-1">— não usar —</option>` + pv.colunas.map((c, i) => `<option value="${i}" ${sel === i ? "selected" : ""}>${esc(c || `coluna ${i + 1}`)}</option>`).join("");
    const nomeArq = arq.files[0].name.replace(/\.[^.]+$/, "");
    previa.innerHTML = `
      <p class="fraco">Cabeçalho encontrado na linha ${pv.linha_cabecalho + 1}. Confira as colunas:</p>
      <div class="linha-campos mapa-colunas">
        ${[["descricao", "Descrição *"], ["preco", "Preço *"], ["codigo", "Código"], ["unidade", "Unidade"]].map(([k, t]) =>
          `<div class="campo"><label for="tb-${k}">${t}</label><select id="tb-${k}" name="col_${k}">${opcoes(pv.sugestao[k])}</select></div>`).join("")}
      </div>
      <div class="tabela-rolagem" style="margin-bottom:14px"><table><thead><tr>${pv.colunas.map((c) => `<th>${esc(c)}</th>`).join("")}</tr></thead>
        <tbody>${pv.exemplos.map((r) => `<tr>${r.map((c) => `<td>${esc(c)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>
      <input type="hidden" name="linha_cabecalho" value="${pv.linha_cabecalho}">
      <div class="linha-campos">
        <div class="campo"><label for="tb-nome">Nome da tabela *</label><input id="tb-nome" name="nome" required value="${esc(nomeArq)}" placeholder="Ex.: SINAPI SP 09/2026 não desonerado"></div>
        <div class="campo"><label for="tb-fonte">Fonte</label><select id="tb-fonte" name="fonte">${Object.entries(d.fontes).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("")}</select></div>
        <div class="campo"><label for="tb-uf">UF</label><input id="tb-uf" name="uf" maxlength="2" placeholder="vazio = nacional"></div>
        <div class="campo"><label for="tb-data">Data-base</label><input id="tb-data" name="data_base" type="date"></div>
      </div>
      <div class="campo"><label for="tb-obs">Observação</label><input id="tb-obs" name="observacao" placeholder="Ex.: preços medianos, não desonerado, sem BDI"></div>
      <div id="tb-erro"></div><button class="botao" type="submit">Importar tabela</button>`;
    $("#form-tab", el).onsubmit = async (ev) => {
      ev.preventDefault();
      const b = ev.target.querySelector("button[type=submit]");
      await ocupado(b, "Importando…", async () => {
        try { const t = await api("POST", "/api/admin/tabelas", new FormData(ev.target)); toast(`${fmt.num(t.n_itens, 0)} itens importados.`, "ok"); abaTabelasAdmin(el); }
        catch (e) { $("#tb-erro", el).innerHTML = erroTela(e); }
      });
    };
  };
}

// ---------------------------------------------------------------- logs de erros
const ORIGEM_LOG = { servidor: ["Servidor", "erro"], tarefa: ["Tarefa em 2º plano", "aviso"], navegador: ["Navegador", "oficio"] };

async function abaLogs(el) {
  const f = V.admin.filtroLog || { situacao: "abertos", origem: "", dias: 7, q: "" };
  V.admin.filtroLog = f;
  const qs = new URLSearchParams({ situacao: f.situacao, origem: f.origem, dias: f.dias, q: f.q }).toString();
  const d = await api("GET", `/api/admin/logs?${qs}`);
  el.innerHTML = `
    <section class="bloco"><div class="grade grade-4 grade-kpi">
      ${indicador(d.abertos, "erros em aberto", d.abertos > 0)}${indicador(d.ultimas_24h, "com ocorrência nas últimas 24h")}
      ${indicador(d.logs.reduce((a, l) => a + (l.ocorrencias || 1), 0), "ocorrências na lista")}${indicador(new Set(d.logs.map((l) => l.usuario_email).filter(Boolean)).size, "usuários afetados")}
    </div><p class="fraco" style="margin:12px 0 0">Erros iguais são agrupados. Para pedir uma análise, selecione os erros e clique em <b>Copiar para análise</b>: o texto vai com a mensagem, a rota, o usuário e o rastreamento técnico, pronto para colar na conversa.</p></section>
    <div class="filtros-admin">
      <div class="chips" role="group" aria-label="Situação">${[["abertos", "Em aberto"], ["resolvidos", "Resolvidos"], ["todos", "Todos"]].map(([k, t]) => `<button data-sit="${k}" aria-pressed="${f.situacao === k}">${t}</button>`).join("")}</div>
      <div class="chips" role="group" aria-label="Origem">${[["", "Todas as origens"], ["servidor", "Servidor"], ["tarefa", "Tarefas"], ["navegador", "Navegador"]].map(([k, t]) => `<button data-org="${k}" aria-pressed="${f.origem === k}">${t}</button>`).join("")}</div>
      <div class="chips" role="group" aria-label="Período">${[[1, "24h"], [7, "7 dias"], [30, "30 dias"], [90, "90 dias"]].map(([k, t]) => `<button data-dias="${k}" aria-pressed="${f.dias == k}">${t}</button>`).join("")}</div>
      <input type="search" id="busca-log" placeholder="Buscar mensagem, rota ou e-mail" value="${esc(f.q)}" aria-label="Buscar nos logs">
    </div>
    <div class="acoes" style="margin-bottom:12px">
      <button class="botao" id="copiar-logs">Copiar para análise</button>
      <button class="botao secundario" id="baixar-logs">${icone("baixar", 14)} Baixar .txt</button>
      ${f.situacao !== "resolvidos" && d.abertos ? `<button class="botao texto" id="resolver-todos">Marcar todos como resolvidos</button>` : ""}
      <span class="fraco" id="sel-logs"></span></div>
    <section class="bloco tabela-rolagem">${d.logs.length ? `<table><thead><tr><th><input type="checkbox" id="todos-logs" aria-label="Selecionar todos"></th><th>Último</th><th>Origem</th><th>Erro</th><th>Onde</th><th>Usuário</th><th>Vezes</th><th></th></tr></thead>
      <tbody>${d.logs.map((l) => `<tr${l.resolvido ? ' style="opacity:.55"' : ""}>
        <td><input type="checkbox" data-sel-log="${l.id}" aria-label="Selecionar erro ${l.id}"></td>
        <td style="white-space:nowrap">${fmt.dataHora(l.ultimo_em + "Z")}</td><td>${carimboStatus(ORIGEM_LOG, l.origem)}${l.nivel === "aviso" ? "<br><small class='fraco'>aviso</small>" : ""}</td>
        <td style="max-width:420px">${esc((l.mensagem || "").slice(0, 220))}</td>
        <td><small>${esc([l.metodo, l.rota].filter(Boolean).join(" ") || "—")}${l.status ? ` · ${l.status}` : ""}</small></td>
        <td><small>${esc(l.usuario_email || "—")}</small></td><td>${l.ocorrencias}</td>
        <td class="acoes-celula"><button class="botao pequeno secundario" data-ver-log="${l.id}">Detalhes</button></td></tr>`).join("")}</tbody></table>`
      : vazio("Nenhum erro neste filtro", f.situacao === "abertos" ? "Tudo certo por aqui." : "")}</section>`;
  const recarregar = () => abaLogs(el);
  $$("[data-sit]", el).forEach((b) => b.onclick = () => { f.situacao = b.dataset.sit; recarregar(); });
  $$("[data-org]", el).forEach((b) => b.onclick = () => { f.origem = b.dataset.org; recarregar(); });
  $$("[data-dias]", el).forEach((b) => b.onclick = () => { f.dias = Number(b.dataset.dias); recarregar(); });
  let t; $("#busca-log", el).oninput = (ev) => { clearTimeout(t); t = setTimeout(() => { f.q = ev.target.value; recarregar(); }, 400); };
  const selecionados = () => $$("[data-sel-log]:checked", el).map((c) => c.dataset.selLog);
  const atualizarSel = () => { const n = selecionados().length; $("#sel-logs", el).textContent = n ? `${n} selecionado(s)` : "Sem seleção: vão todos os erros em aberto (até 50)."; };
  $$("[data-sel-log]", el).forEach((c) => c.onchange = atualizarSel);
  const todos = $("#todos-logs", el); if (todos) todos.onchange = () => { $$("[data-sel-log]", el).forEach((c) => { c.checked = todos.checked; }); atualizarSel(); };
  atualizarSel();
  const texto = async () => { const r = await api("GET", `/api/admin/logs/exportar?ids=${selecionados().join(",")}`); return r.text(); };
  $("#copiar-logs", el).onclick = (ev) => ocupado(ev.target, "Copiando…", async () => {
    try { const txt = await texto(); await navigator.clipboard.writeText(txt); toast("Copiado. É só colar na conversa.", "ok"); }
    catch (e) { const txt = await texto().catch(() => ""); modal({ titulo: "Copie o texto abaixo", largo: true, corpo: `<textarea class="editor" style="min-height:360px">${esc(txt)}</textarea>` }); }
  });
  $("#baixar-logs", el).onclick = async () => {
    const txt = await texto(); const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([txt], { type: "text/plain" })); a.download = `kasiski-erros-${new Date().toISOString().slice(0, 10)}.txt`; a.click();
  };
  const rt = $("#resolver-todos", el);
  if (rt) rt.onclick = async () => { if (await confirmar("Marcar todos os erros em aberto como resolvidos?", "Marcar")) { await api("POST", "/api/admin/logs/resolver-todos"); recarregar(); } };
  $$("[data-ver-log]", el).forEach((b) => b.onclick = async () => {
    const l = await api("GET", `/api/admin/logs/${b.dataset.verLog}`);
    const m = modal({ titulo: `Erro #${l.id}`, largo: true, corpo: `
      <div class="meta" style="margin:0 0 12px">${carimboStatus(ORIGEM_LOG, l.origem)}<span>${l.ocorrencias} ocorrência(s)</span>
        <span>primeiro ${fmt.dataHora(l.criado_em + "Z")}</span><span>último ${fmt.dataHora(l.ultimo_em + "Z")}</span></div>
      <p><b>${esc(l.mensagem)}</b></p>
      <p class="fraco">${esc([l.metodo, l.rota].filter(Boolean).join(" ") || "—")}${l.status ? ` · HTTP ${l.status}` : ""} · ${esc(l.usuario_email || "sem usuário")}</p>
      ${l.navegador ? `<p class="fraco"><small>${esc(l.navegador)}</small></p>` : ""}
      ${l.detalhe ? `<h3>Rastreamento técnico</h3><div class="log-detalhe">${esc(l.detalhe)}</div>` : ""}`,
      acoes: `<button class="botao secundario" data-copiar-um>Copiar para análise</button><button class="botao" data-resolver>${l.resolvido ? "Reabrir" : "Marcar como resolvido"}</button>` });
    $("[data-copiar-um]", m).onclick = async () => { const r = await api("GET", `/api/admin/logs/exportar?ids=${l.id}`); await navigator.clipboard.writeText(await r.text()).then(() => toast("Copiado.", "ok")).catch(() => toast("Não foi possível copiar; use Baixar .txt.", "erro")); };
    $("[data-resolver]", m).onclick = async () => { await api("PATCH", `/api/admin/logs/${l.id}`, { resolvido: !l.resolvido }); m.fechar(); recarregar(); };
  });
}
