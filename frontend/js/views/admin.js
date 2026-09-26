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
      ${[["crm", "Clientes e testes"], ["marketing", "Marketing"], ["funil", "Funil de conversão"], ["receitas", "Receitas"], ["tabelas", "Tabelas de preços"], ["revisoes", "Pedidos de advogado"], ["atendimento", "Atendimento"], ["logs", "Logs de erros"]]
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
    else if (aba === "marketing") await abaMarketing(painel);
    else if (aba === "receitas") await abaReceitas(painel);
    else if (aba === "tabelas") await abaTabelasAdmin(painel);
    else if (aba === "logs") await abaLogs(painel);
    else if (aba === "atendimento") await abaAtendimento(painel);
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

// ---------------------------------------------------------------- atendimento (assistente virtual)
const STATUS_CHAT = { bot: ["Só com o assistente", "neutro"], encaminhada: ["Aguardando equipe", "aviso"],
  em_atendimento: ["Em atendimento", "oficio"], resolvida: ["Resolvida", "ok"] };
const PAPEL_CHAT = { usuario: "Cliente", assistente: "Assistente", sistema: "Sistema", atendente: "Equipe" };

async function abaAtendimento(el) {
  const f = V.admin.filtroChat || { status: "encaminhada", dias: 30 };
  V.admin.filtroChat = f;
  const d = await api("GET", `/api/admin/atendimentos?status=${f.status}&dias=${f.dias}`);
  el.innerHTML = `
    <section class="bloco"><div class="grade grade-4 grade-kpi">
      ${indicador(d.abertos, "chamados aguardando a equipe", d.abertos > 0)}${indicador(d.conversas_7d, "conversas com o assistente em 7 dias")}
      ${indicador(d.conversas.length, "conversas neste filtro")}${indicador(d.conversas.filter((c) => c.conta_id).length, "de clientes logados")}
    </div><p class="fraco" style="margin:12px 0 0">Quando o visitante pede para falar com a equipe, o chamado aparece aqui e um e-mail é enviado aos administradores. Abra a conversa para ver o histórico completo e responder por e-mail ou WhatsApp.</p></section>
    <div class="filtros-admin">
      <div class="chips" role="group" aria-label="Situação">${[["encaminhada", "Chamados abertos"], ["resolvida", "Resolvidos"], ["bot", "Só com o assistente"], ["todos", "Todas"]].map(([k, t]) => `<button data-cst="${k}" aria-pressed="${f.status === k}">${t}</button>`).join("")}</div>
      <div class="chips" role="group" aria-label="Período">${[[7, "7 dias"], [30, "30 dias"], [90, "90 dias"]].map(([k, t]) => `<button data-cdias="${k}" aria-pressed="${f.dias == k}">${t}</button>`).join("")}</div>
    </div>
    <section class="bloco tabela-rolagem">${d.conversas.length ? `<table><thead><tr><th>Atualizada</th><th>Situação</th><th>Contato</th><th>Assunto</th><th>Msgs</th><th>Página</th><th></th></tr></thead>
      <tbody>${d.conversas.map((c) => `<tr>
        <td style="white-space:nowrap">${fmt.dataHora(c.atualizado_em + "Z")}</td><td>${carimboStatus(STATUS_CHAT, c.status)}</td>
        <td>${esc(c.nome || "Visitante")}<br><small class="fraco">${esc(c.email || c.usuario_email || "—")}</small></td>
        <td style="max-width:360px">${esc((c.assunto || "—").slice(0, 160))}</td><td>${c.n_mensagens || 0}</td>
        <td><small>${esc(c.pagina || "—")}</small></td>
        <td class="acoes-celula"><button class="botao pequeno secundario" data-ver-chat="${esc(c.id)}">Abrir</button></td></tr>`).join("")}</tbody></table>`
      : vazio("Nenhuma conversa neste filtro", f.status === "encaminhada" ? "Nenhum chamado aguardando a equipe." : "")}</section>`;
  const recarregar = () => abaAtendimento(el);
  $$("[data-cst]", el).forEach((b) => b.onclick = () => { f.status = b.dataset.cst; recarregar(); });
  $$("[data-cdias]", el).forEach((b) => b.onclick = () => { f.dias = Number(b.dataset.cdias); recarregar(); });
  $$("[data-ver-chat]", el).forEach((b) => b.onclick = () => modalAtendimento(b.dataset.verChat, recarregar));
}

async function modalAtendimento(id, aoSalvar) {
  const c = await api("GET", `/api/admin/atendimentos/${encodeURIComponent(id)}`);
  const email = c.email || c.usuario_email;
  const fone = (c.telefone || "").replace(/\D/g, "");
  const wa = fone ? `https://wa.me/${fone.length <= 11 ? "55" + fone : fone}` : "";
  const assuntoMail = encodeURIComponent("Kasiski — seu atendimento");
  const m = modal({ titulo: `Atendimento — ${c.nome || "Visitante"}`, largo: true, corpo: `
    <div class="meta" style="margin:0 0 12px">${carimboStatus(STATUS_CHAT, c.status)}<span>iniciada ${fmt.dataHora(c.criado_em + "Z")}</span>
      ${c.encaminhada_em ? `<span>encaminhada ${fmt.dataHora(c.encaminhada_em + "Z")}</span>` : ""}<span>${esc(c.pagina || "")}</span></div>
    <p>${email ? `<a href="mailto:${esc(email)}?subject=${assuntoMail}">${esc(email)}</a>` : "Sem e-mail"}${c.telefone ? ` · ${wa ? `<a href="${wa}" target="_blank" rel="noopener">WhatsApp ${esc(c.telefone)}</a>` : esc(c.telefone)}` : ""}${c.usuario_email && c.usuario_email !== c.email ? ` · conta: ${esc(c.usuario_email)}` : ""}</p>
    ${c.assunto ? `<div class="aviso"><b>Assunto:</b> ${esc(c.assunto)}</div>` : ""}
    <h3>Conversa</h3>
    <div class="transcricao-chat">${c.mensagens.map((x) => `<div class="msg-chat ${x.papel}"><small>${esc(PAPEL_CHAT[x.papel] || x.papel)} · ${fmt.dataHora(x.criado_em + "Z")}</small><div>${esc(String(x.texto || "").replace(/\*\*(.+?)\*\*/g, "$1").replace(/`([^`]+)`/g, "$1"))}</div></div>`).join("") || "<p class='fraco'>Sem mensagens.</p>"}</div>
    <form id="form-chat-adm" style="margin-top:14px">
      <div class="campo"><label for="chat-status">Situação</label><select id="chat-status" name="status">${Object.entries(STATUS_CHAT).map(([k, [t]]) => `<option value="${k}"${c.status === k ? " selected" : ""}>${t}</option>`).join("")}</select></div>
      <div class="campo"><label for="chat-notas">Anotações internas</label><textarea id="chat-notas" name="notas" rows="3">${esc(c.notas || "")}</textarea></div>
    </form>`,
    acoes: `${email ? `<a class="botao secundario" href="mailto:${esc(email)}?subject=${assuntoMail}">Responder por e-mail</a>` : ""}<button class="botao" data-salvar-chat>Salvar</button>` });
  $("[data-salvar-chat]", m).onclick = async (ev) => ocupado(ev.target, "Salvando…", async () => {
    await api("PATCH", `/api/admin/atendimentos/${encodeURIComponent(id)}`, dadosForm($("#form-chat-adm", m)));
    toast("Atendimento atualizado.", "ok"); m.fechar(); aoSalvar();
  });
}

// ---------------------------------------------------------------- marketing (aquisição → receita)
const STATUS_LEAD = { novo: ["Novo", "neutro"], engajado: ["Engajado", "neutro"], mql: ["MQL", "aviso"], sql: ["SQL — quente", "erro"],
  trial: ["Trial", "oficio"], ativado: ["Ativado", "oficio"], oportunidade: ["Oportunidade", "aviso"], assinante: ["Assinante", "ok"], perdido: ["Perdido", "neutro"] };
const NOMES_CANAL_ADM = { busca_paga: "Busca paga (Google Ads)", social_pago: "Social pago", busca_organica: "Busca orgânica (SEO)", social: "Redes sociais",
  email: "E-mail / newsletter", parceiro: "Parceiros", indicacao: "Sites que indicaram", direto: "Direto / desconhecido" };
const ISCAS = { analisar_edital: "Analisador de edital", consultar_concorrente: "Consulta de concorrente", newsletter: "Newsletter", consultorias: "Página de consultorias",
  contato: "Contato", checklist: "Checklist", "cadastro direto": "Cadastro direto" };
const moedaOuTraco = (v) => (v === null || v === undefined ? "—" : fmt.moeda(v));
const pctOuTraco = (v) => (v === null || v === undefined ? "—" : `${fmt.num(v, 1)}%`);

async function abaMarketing(el) {
  const sub = V.admin.mk || "visao";
  el.innerHTML = `<div class="chips mk-abas" role="tablist" aria-label="Marketing">${[["visao", "Visão geral"], ["canais", "Canais e campanhas"], ["leads", "Leads"],
    ["ferramentas", "Ferramentas grátis"], ["automacoes", "Automações de e-mail"], ["investimentos", "Investimentos"]]
    .map(([k, t]) => `<button data-mk="${k}" aria-pressed="${sub === k}">${t}</button>`).join("")}</div><div id="mk-corpo"><p class="carregando">Carregando…</p></div>`;
  $$("[data-mk]", el).forEach((b) => b.onclick = () => { V.admin.mk = b.dataset.mk; abaMarketing(el); });
  const c = $("#mk-corpo", el);
  try {
    if (sub === "leads") await mkLeads(c);
    else if (sub === "automacoes") await mkAutomacoes(c);
    else if (sub === "investimentos") await mkInvestimentos(c);
    else await mkVisao(c, sub);
  } catch (e) { c.innerHTML = erroTela(e); }
}

async function mkVisao(el, sub) {
  const dias = V.admin.mkDias || 30;
  const d = await api("GET", `/api/admin/marketing/visao?dias=${dias}`);
  const periodo = `<div class="filtros-admin"><div class="chips" role="group" aria-label="Período">${[7, 30, 90, 365].map((n) => `<button data-mdias="${n}" aria-pressed="${n === dias}">${n === 365 ? "12 meses" : `${n} dias`}</button>`).join("")}</div></div>`;
  const i = d.indicadores;
  let corpo = "";
  if (sub === "visao") {
    const topo = Math.max(1, ...d.funil.map((e) => e.total));
    corpo = `
      <section class="bloco"><h2>Funil — últimos ${dias} dias</h2>
        <div class="funil">${d.funil.map((e, k) => {
          const ant = k ? d.funil[k - 1].total : null;
          return `<div class="funil-linha"><span class="funil-rotulo">${esc(e.rotulo)}</span>
            <div class="funil-trilho"><i style="width:${Math.max(e.total ? 1.5 : 0, (100 * e.total) / topo)}%"></i></div>
            <span class="funil-valor"><b>${fmt.num(e.total)}</b>${ant !== null ? `<small>${ant && e.total <= ant ? `↓ ${fmt.num((100 * e.total) / ant, 1)}%` : "—"}</small>` : ""}</span></div>`;
        }).join("")}</div>
        <p class="fraco" style="margin-top:10px">Visitantes = navegadores únicos com visita registrada (site público e página inicial). Trials, ativados e assinantes contam as contas criadas no período, acompanhadas até hoje.</p></section>
      <section class="bloco"><h2>Indicadores de receita</h2><div class="grade grade-4 grade-kpi">
        ${indicador(fmt.moeda(i.mrr), "MRR (receita recorrente mensal)")}${indicador(fmt.moeda(i.arr), "ARR (MRR × 12)")}
        ${indicador(moedaOuTraco(i.arpu), `ARPU (${i.pagantes} pagante(s))`)}${indicador(fmt.moeda(i.mrr_novo), "MRR novo no período")}
        ${indicador(moedaOuTraco(i.cac), `CAC (investimento ${fmt.moeda(i.investimento)})`)}${indicador(moedaOuTraco(i.ltv), "LTV (ARPU ÷ churn)")}
        ${indicador(i.payback_meses === null ? "—" : `${fmt.num(i.payback_meses, 1)} mês(es)`, "Payback do CAC")}${indicador(pctOuTraco(i.churn_mensal), "Churn mensal")}
        ${indicador(pctOuTraco(i.visitante_para_lead), "Visitante → lead")}${indicador(pctOuTraco(i.lead_para_trial), "Lead → trial")}
        ${indicador(pctOuTraco(i.ativacao), "Taxa de ativação")}${indicador(pctOuTraco(i.trial_para_pago), "Trial → pago")}</div>
        <p class="fraco" style="margin-top:12px">O CAC usa os valores lançados em <b>Investimentos</b>. Sem investimento lançado, CAC e payback ficam em branco.</p></section>
      <section class="bloco"><div class="bloco-titulo"><h2>Leads quentes — entrar em contato</h2><button class="botao pequeno texto" data-ir-leads>Ver todos os leads</button></div>
        ${d.leads_quentes.length ? d.leads_quentes.map((l) => `<div class="lista-item"><div class="corpo"><b>${esc(l.nome || l.email)}</b> ${carimboStatus(STATUS_LEAD, l.status)} <small class="fraco">score ${l.score}</small>
          <p>${esc(l.email || "")}${l.empresa ? " · " + esc(l.empresa) : ""} · ${esc(NOMES_CANAL_ADM[l.canal] || l.canal || "—")}${l.utm_campaign ? " · " + esc(l.utm_campaign) : ""}</p></div>
          <button class="botao pequeno secundario" data-lead="${l.id}">Abrir</button></div>`).join("") : vazio("Nenhum lead quente agora", "Leads com score acima de 50 (MQL) ou 80 (SQL) aparecem aqui.")}</section>`;
  } else if (sub === "canais") {
    corpo = `
      <section class="bloco tabela-rolagem"><h2>Por canal</h2>${d.canais.length ? `<table><thead><tr><th>Canal</th><th>Visitantes</th><th>Leads</th><th>Trials</th><th>Ativados</th><th>Assinantes</th><th>MRR</th><th>Investido</th><th>CAC</th></tr></thead>
        <tbody>${d.canais.map((c) => `<tr><td><b>${esc(c.nome)}</b></td><td>${fmt.num(c.visitantes)}</td><td>${c.leads}</td><td>${c.trials}</td><td>${c.ativados}</td><td>${c.assinantes}</td>
          <td>${fmt.moeda(c.mrr)}</td><td>${c.investimento ? fmt.moeda(c.investimento) : "—"}</td><td>${moedaOuTraco(c.cac)}</td></tr>`).join("")}</tbody></table>` : vazio("Sem dados no período", "")}
        <p class="fraco" style="margin-top:10px">O canal vem do primeiro toque (UTM, gclid, site de origem ou <code>?ref=</code> de parceiro) e acompanha a pessoa até a assinatura.</p></section>
      <section class="bloco tabela-rolagem"><h2>Por campanha (utm_campaign)</h2>${d.campanhas.length ? `<table><thead><tr><th>Campanha</th><th>Leads</th><th>Trials</th><th>Ativados</th><th>Assinantes</th><th>Trial → pago</th></tr></thead>
        <tbody>${d.campanhas.map((c) => `<tr><td>${esc(c.campanha)}</td><td>${c.leads}</td><td>${c.trials}</td><td>${c.ativados}</td><td>${c.assinantes}</td><td>${c.trials ? pct(c.assinantes, c.trials) + "%" : "—"}</td></tr>`).join("")}</tbody></table>`
        : vazio("Nenhuma campanha com UTM no período", "Use links como ?utm_source=google&utm_medium=cpc&utm_campaign=analise_edital.")}</section>
      <section class="bloco tabela-rolagem"><h2>Cohort: trials de 60+ dias atrás</h2>${d.cohorts.length ? `<table><thead><tr><th>Canal</th><th>Trials</th><th>Pagaram</th><th>Seguem pagando</th><th>Retenção</th></tr></thead>
        <tbody>${d.cohorts.map((c) => `<tr><td>${esc(c.nome)}</td><td>${c.trials}</td><td>${c.pagaram}</td><td>${c.retidos}</td><td>${c.pagaram ? pct(c.retidos, c.pagaram) + "%" : "—"}</td></tr>`).join("")}</tbody></table>`
        : vazio("Ainda sem contas com 60 dias", "")}
        <p class="fraco" style="margin-top:10px">Responde qual canal traz clientes que <b>permanecem</b> assinantes, e não só quem clica.</p></section>`;
  } else {
    const f = d.ferramentas;
    corpo = `<section class="bloco"><div class="grade grade-4 grade-kpi">
        ${indicador(f.analises_gratuitas, "análises gratuitas de edital")}${indicador("US$ " + fmt.num(f.custo_ia_analises_usd, 2), "custo de IA dessas análises")}
        ${indicador(f.consultas_concorrente, "consultas de concorrente")}${indicador(f.newsletter_ativos, "assinantes da newsletter (confirmados)")}</div></section>
      <section class="bloco tabela-rolagem"><h2>Leads por isca</h2>${f.por_isca.length ? `<table><thead><tr><th>Isca</th><th>Leads</th><th>Viraram trial</th><th>Assinaram</th><th>Lead → trial</th></tr></thead>
        <tbody>${f.por_isca.map((x) => `<tr><td>${esc(ISCAS[x.isca] || x.isca)}</td><td>${x.leads}</td><td>${x.trials}</td><td>${x.assinantes}</td><td>${pct(x.trials, x.leads)}%</td></tr>`).join("")}</tbody></table>` : vazio("Sem leads no período", "")}</section>
      <section class="bloco"><h2>Newsletter</h2><p class="fraco">Exporte a lista de inscritos confirmados para enviar a edição da semana pela sua ferramenta de e-mail.</p>
        <button class="botao secundario" data-csv="newsletter">${icone("baixar", 14)} Baixar inscritos (.csv)</button></section>`;
  }
  el.innerHTML = periodo + corpo;
  $$("[data-mdias]", el).forEach((b) => b.onclick = () => { V.admin.mkDias = Number(b.dataset.mdias); mkVisao(el, sub); });
  $$("[data-lead]", el).forEach((b) => b.onclick = () => modalLead(Number(b.dataset.lead), () => mkVisao(el, sub)));
  const ir = $("[data-ir-leads]", el); if (ir) ir.onclick = () => { V.admin.mk = "leads"; V.admin.mkFiltro = { status: "quentes", q: "" }; abaMarketing(el.parentElement); };
  $$("[data-csv]", el).forEach((b) => b.onclick = () => baixarCsv(b.dataset.csv === "newsletter"));
}

async function baixarCsv(soNewsletter) {
  const r = await api("GET", `/api/admin/marketing/leads.csv${soNewsletter ? "?newsletter=1" : ""}`);
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([await r.text()], { type: "text/csv" }));
  a.download = soNewsletter ? "kasiski-newsletter.csv" : "kasiski-leads.csv"; a.click();
}

async function mkLeads(el) {
  const f = V.admin.mkFiltro || { status: "", q: "" };
  V.admin.mkFiltro = f;
  const qs = new URLSearchParams({ status: f.status, q: f.q }).toString();
  const d = await api("GET", `/api/admin/marketing/leads?${qs}`);
  const cont = d.contagem || {};
  const quentes = (cont.mql || 0) + (cont.sql || 0) + (cont.oportunidade || 0);
  el.innerHTML = `
    <div class="filtros-admin">
      <div class="chips" role="group" aria-label="Status">${[["", "Todos"], ["quentes", `Quentes (${quentes})`], ...Object.entries(STATUS_LEAD).map(([k, [t]]) => [k, `${t} (${cont[k] || 0})`])]
        .map(([k, t]) => `<button data-lst="${k}" aria-pressed="${f.status === k}">${esc(t)}</button>`).join("")}</div>
      <input type="search" id="busca-lead" placeholder="Buscar nome, e-mail, empresa ou campanha" value="${esc(f.q)}" aria-label="Buscar leads">
      <button class="botao secundario" data-csv>${icone("baixar", 14)} Exportar .csv</button></div>
    <section class="bloco tabela-rolagem">${d.leads.length ? `<table><thead><tr><th>Lead</th><th>Status</th><th>Score</th><th>Canal / campanha</th><th>Isca</th><th>Última visita</th><th></th></tr></thead>
      <tbody>${d.leads.map((l) => `<tr><td><b>${esc(l.nome || "—")}</b><br><small class="fraco">${esc(l.email || "")}${l.empresa ? " · " + esc(l.empresa) : ""}</small></td>
        <td>${carimboStatus(STATUS_LEAD, l.status)}</td><td><b>${l.score}</b></td>
        <td><small>${esc(NOMES_CANAL_ADM[l.canal] || l.canal || "—")}${l.utm_campaign ? "<br>" + esc(l.utm_campaign) : ""}</small></td>
        <td><small>${esc(ISCAS[l.lead_magnet] || l.lead_magnet || "—")}</small></td>
        <td style="white-space:nowrap"><small>${l.ultima_visita ? fmt.dataHora(l.ultima_visita + "Z") : "—"}</small></td>
        <td class="acoes-celula"><button class="botao pequeno secundario" data-lead="${l.id}">Abrir</button></td></tr>`).join("")}</tbody></table>`
      : vazio("Nenhum lead neste filtro", "Os leads chegam pelas ferramentas gratuitas, newsletter, formulários do site e cadastros.")}</section>`;
  const rec = () => mkLeads(el);
  $$("[data-lst]", el).forEach((b) => b.onclick = () => { f.status = b.dataset.lst; rec(); });
  let t; $("#busca-lead", el).oninput = (ev) => { clearTimeout(t); t = setTimeout(() => { f.q = ev.target.value; rec(); }, 400); };
  $$("[data-lead]", el).forEach((b) => b.onclick = () => modalLead(Number(b.dataset.lead), rec));
  $("[data-csv]", el).onclick = () => baixarCsv(false);
}

const NOMES_EVENTO = { page_view: "Visitou o site", cta_click: "Clicou em um CTA", pricing_view: "Viu os planos", generate_lead: "Deixou o contato", tool_started: "Usou uma ferramenta grátis",
  edital_free_analysis: "Análise gratuita de edital", competitor_search: "Consultou concorrente", sign_up: "Criou conta", trial_started: "Iniciou o teste", company_created: "Cadastrou a empresa",
  radar_configured: "Configurou o radar", edital_added: "Adicionou edital", edital_analyzed: "Analisou edital (IA)", competitor_analyzed: "Analisou concorrente", document_uploaded: "Enviou documento ao cofre",
  proposal_generated: "Gerou proposta", legal_document_generated: "Gerou peça", begin_checkout: "Abriu o pagamento", purchase: "Pagou", subscription_cancelled: "Cancelou a assinatura", visita: "Visitou a página inicial", cta: "Clicou em testar grátis" };

async function modalLead(id, aoSalvar) {
  const l = await api("GET", `/api/admin/marketing/leads/${id}`);
  const fone = (l.whatsapp || l.telefone || "").replace(/\D/g, "");
  const m = modal({ titulo: l.nome || l.email || `Lead ${l.id}`, largo: true, corpo: `
    <div class="meta" style="margin:0 0 12px">${carimboStatus(STATUS_LEAD, l.status)}<span>score <b>${l.score}</b></span><span>${esc(NOMES_CANAL_ADM[l.canal] || l.canal || "—")}</span>
      ${l.utm_campaign ? `<span>campanha ${esc(l.utm_campaign)}</span>` : ""}<span>desde ${fmt.data(l.criado_em)}</span></div>
    <p>${l.email ? `<a href="mailto:${esc(l.email)}">${esc(l.email)}</a>` : ""}${fone ? ` · <a href="https://wa.me/${fone.length <= 11 ? "55" + fone : fone}" target="_blank" rel="noopener">WhatsApp ${esc(l.whatsapp || l.telefone)}</a>` : ""}
      ${l.empresa ? ` · ${esc(l.empresa)}` : ""}${l.cargo ? ` · ${esc(l.cargo)}` : ""}</p>
    <p class="fraco">Primeiro toque: ${esc([l.utm_source, l.utm_medium, l.utm_campaign, l.utm_term].filter(Boolean).join(" / ") || l.origem || "direto")} · entrada: ${esc(l.landing_page || "—")}${l.ref_parceiro ? ` · parceiro <b>${esc(l.ref_parceiro)}</b>` : ""}</p>
    ${l.conta ? `<div class="aviso info">Conta <b>${esc(l.conta.nome)}</b> · plano ${esc(l.conta.plano)}${l.conta.trial_fim ? ` · teste até ${fmt.data(l.conta.trial_fim)}` : ""} <button class="botao pequeno texto" data-abrir-conta="${l.conta.id}">Abrir no CRM</button></div>` : ""}
    ${l.analises_gratuitas.length ? `<p><b>Análises gratuitas:</b> ${l.analises_gratuitas.map((a) => `${esc(a.nome_arquivo || "edital")} (nota ${a.nota ?? "—"}, ${fmt.data(a.criado_em)})`).join("; ")}</p>` : ""}
    <h3>Jornada</h3><ol class="op-linha-tempo mk-jornada">${l.eventos.map((e) => `<li><small>${fmt.dataHora(e.criado_em + "Z")}${e.canal ? " · " + esc(NOMES_CANAL_ADM[e.canal] || e.canal) : ""}</small>
      <div>${esc(NOMES_EVENTO[e.tipo] || e.tipo)} ${l.pontos_por_evento[e.tipo] ? `<small class="fraco">+${l.pontos_por_evento[e.tipo]}</small>` : ""}${e.dados?.pagina ? ` <small class="fraco">${esc(e.dados.pagina)}</small>` : ""}</div></li>`).join("") || "<li>Sem eventos.</li>"}</ol>
    <form id="form-lead" style="margin-top:14px"><div class="linha-campos">
      <div class="campo"><label for="ld-status">Status</label><select id="ld-status" name="status">${Object.entries(STATUS_LEAD).map(([k, [t]]) => `<option value="${k}" ${l.status === k ? "selected" : ""}>${t}</option>`).join("")}</select></div>
      <div class="campo"><label for="ld-resp">Responsável</label><input id="ld-resp" name="responsavel" value="${esc(l.responsavel || "")}"></div></div>
      <div class="campo"><label for="ld-notas">Anotações</label><textarea id="ld-notas" name="notas" rows="3">${esc(l.notas || "")}</textarea></div></form>`,
    acoes: `<button class="botao" data-salvar-lead>Salvar</button>` });
  const ac = $("[data-abrir-conta]", m); if (ac) ac.onclick = () => { m.fechar(); modalConta(Number(ac.dataset.abrirConta), aoSalvar); };
  $("[data-salvar-lead]", m).onclick = (ev) => ocupado(ev.target, "Salvando…", async () => {
    await api("PATCH", `/api/admin/marketing/leads/${id}`, dadosForm($("#form-lead", m))); toast("Lead atualizado.", "ok"); m.fechar(); aoSalvar && aoSalvar();
  });
}

const GATILHOS = { cadastro: "após o cadastro", empresa: "após cadastrar a empresa", radar: "após configurar o radar", analise: "após a 1ª análise", trial_fim: "antes do fim do teste" };
const CONDICOES = { sem_empresa: "se ainda não cadastrou a empresa", sem_radar: "se ainda não configurou o radar", sem_analise: "se ainda não analisou edital", em_teste: "se ainda está no teste" };
const tempo = (min) => (min >= 1440 ? `${fmt.num(min / 1440, 1)} dia(s)` : min >= 60 ? `${fmt.num(min / 60, 1)} h` : `${min} min`);

async function mkAutomacoes(el) {
  const d = await api("GET", "/api/admin/marketing/automacoes");
  el.innerHTML = `${d.email_configurado ? "" : `<div class="aviso">O envio de e-mail não está configurado (RESEND_API_KEY). As automações ficam prontas e passam a enviar assim que a chave for preenchida no Render.</div>`}
    <section class="bloco"><div class="bloco-titulo"><h2>Sequência do onboarding e do fim do teste</h2><button class="botao pequeno secundario" id="rodar-auto">Rodar agora</button></div>
      <p class="fraco">Cada e-mail é enviado uma única vez por conta, respeitando o descadastro. O servidor verifica a cada 10 minutos; o job diário faz um reforço.</p>
      <div class="tabela-rolagem"><table><thead><tr><th>Ativa</th><th>E-mail</th><th>Quando</th><th>Assunto</th><th>30 dias</th><th></th></tr></thead>
      <tbody>${d.automacoes.map((a) => `<tr><td><input type="checkbox" data-ativo="${a.id}" ${a.ativo ? "checked" : ""} aria-label="Ativar ${esc(a.nome)}"></td>
        <td><b>${esc(a.nome)}</b></td><td><small>${tempo(a.atraso_min)} ${esc(GATILHOS[a.gatilho] || a.gatilho)}${a.condicao ? `<br>${esc(CONDICOES[a.condicao] || a.condicao)}` : ""}</small></td>
        <td><input value="${esc(a.assunto || "")}" data-assunto="${a.id}" aria-label="Assunto" style="min-width:260px"></td>
        <td><small>${a.enviado || 0} enviado(s)${a.falhou ? ` · <span style="color:var(--carimbo)">${a.falhou} falha(s)</span>` : ""}</small></td>
        <td class="acoes-celula"><button class="botao pequeno texto" data-teste="${a.id}">Enviar teste para mim</button></td></tr>`).join("")}</tbody></table></div></section>`;
  $$("[data-ativo]", el).forEach((c) => c.onchange = async () => { await api("PATCH", `/api/admin/marketing/automacoes/${c.dataset.ativo}`, { ativo: c.checked }); toast(c.checked ? "Automação ativada." : "Automação pausada.", "ok"); });
  $$("[data-assunto]", el).forEach((i) => i.onchange = async () => { await api("PATCH", `/api/admin/marketing/automacoes/${i.dataset.assunto}`, { assunto: i.value }); toast("Assunto salvo.", "ok"); });
  $$("[data-teste]", el).forEach((b) => b.onclick = () => ocupado(b, "Enviando…", async () => {
    try { const r = await api("POST", `/api/admin/marketing/automacoes/${b.dataset.teste}/teste`); toast(`Enviado para ${r.para}.`, "ok"); } catch (e) { avisarErro(e); }
  }));
  $("#rodar-auto", el).onclick = (ev) => ocupado(ev.target, "Rodando…", async () => { const r = await api("POST", "/api/admin/marketing/automacoes/rodar"); toast(`${r.enviados} e-mail(s) enviado(s).`, "ok"); mkAutomacoes(el); });
}

async function mkInvestimentos(el) {
  const lista = await api("GET", "/api/admin/marketing/investimentos");
  const mes = new Date().toISOString().slice(0, 7);
  el.innerHTML = `<section class="bloco"><h2>Lançar investimento</h2><p class="fraco">Quanto foi gasto por canal no mês. É o que alimenta o CAC e o payback. Use o mesmo nome do <code>utm_source</code> (google, linkedin, meta).</p>
    <form id="form-invest"><div class="linha-campos">
      <div class="campo"><label for="iv-mes">Mês</label><input id="iv-mes" name="mes" type="month" value="${mes}" required></div>
      <div class="campo"><label for="iv-canal">Canal</label><input id="iv-canal" name="canal" list="iv-canais" value="google" required><datalist id="iv-canais"><option value="google"><option value="linkedin"><option value="meta"><option value="parceiros"><option value="outros"></datalist></div>
      <div class="campo"><label for="iv-camp">Campanha (opcional)</label><input id="iv-camp" name="campanha"></div>
      <div class="campo"><label for="iv-valor">Valor (R$)</label><input id="iv-valor" name="valor" inputmode="decimal" required></div></div>
      <button class="botao" type="submit">Lançar</button></form></section>
    <section class="bloco tabela-rolagem">${lista.length ? `<table><thead><tr><th>Mês</th><th>Canal</th><th>Campanha</th><th>Valor</th><th></th></tr></thead>
      <tbody>${lista.map((i) => `<tr><td>${esc(i.mes)}</td><td>${esc(i.canal)}</td><td>${esc(i.campanha || "—")}</td><td>${fmt.moeda(i.valor)}</td>
        <td class="acoes-celula"><button class="botao pequeno texto" data-apagar="${i.id}">Excluir</button></td></tr>`).join("")}</tbody></table>` : vazio("Nenhum investimento lançado", "")}</section>`;
  $("#form-invest", el).onsubmit = async (ev) => {
    ev.preventDefault();
    try { await api("POST", "/api/admin/marketing/investimentos", dadosForm(ev.target)); toast("Investimento lançado.", "ok"); mkInvestimentos(el); } catch (e) { avisarErro(e); }
  };
  $$("[data-apagar]", el).forEach((b) => b.onclick = async () => { if (await confirmar("Excluir este lançamento?", "Excluir")) { await api("DELETE", `/api/admin/marketing/investimentos/${b.dataset.apagar}`); mkInvestimentos(el); } });
}
