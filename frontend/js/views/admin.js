// Administração: CRM de contas (testes e assinaturas), funil de conversão, receitas e revisões.
const ETAPAS_CRM = {
  cadastrado: ["Cadastrado", "neutro"], ativado: ["Empresa cadastrada", "neutro"], engajado: ["Usou a IA", "oficio"],
  em_teste: ["Testando o Profissional", "oficio"], teste_expirado: ["Voltou ao Free", "aviso"], assinante: ["Assinante", "ok"], cancelando: ["Cancelou (ainda ativo)", "aviso"],
  inadimplente: ["Inadimplente", "erro"], cancelado: ["Cancelado", "neutro"], suspenso: ["Suspenso", "erro"],
};
const FILTROS_CRM = [
  ["todos", "Todos", () => true],
  ["teste", "Testando o Profissional", (c) => c.etapa === "em_teste"],
  ["free", "Free", (c) => c.plano === "free" && c.etapa !== "em_teste"],
  ["expirando", "Teste acaba em 48h", (c) => c.dias_trial !== null && c.dias_trial >= 0 && c.dias_trial <= 2],
  ["expirado", "Teste acabou (Free)", (c) => c.etapa === "teste_expirado"],
  ["assinantes", "Assinantes", (c) => ["assinante", "cancelando"].includes(c.etapa)],
  ["inadimplentes", "Inadimplentes", (c) => ["inadimplente", "suspenso"].includes(c.etapa)],
  ["cancelados", "Cancelados", (c) => ["cancelado", "cancelando"].includes(c.etapa)],
];

V.admin = async (el) => {
  const aba = V.admin.aba || "crm";
  el.innerHTML = `
    <div class="cabecalho"><h1>Administração</h1><button class="botao pequeno secundario" id="teste-email">Testar envio de e-mail</button></div>
    <div class="abas" role="tablist">
      ${[["crm", "Clientes e testes"], ["marketing", "Marketing"], ["funil", "Funil de conversão"], ["receitas", "Receitas"], ["faturamento", "Notas fiscais"], ["tabelas", "Tabelas de preços"], ["revisoes", "Pedidos de advogado"], ["atendimento", "Atendimento"], ["planos", "Planos e margem"], ["logs", "Logs de erros"], ["armazenamento", "Armazenamento"]]
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
    else if (aba === "faturamento") await abaFaturamento(painel);
    else if (aba === "tabelas") await abaTabelasAdmin(painel);
    else if (aba === "logs") await abaLogs(painel);
    else if (aba === "armazenamento") await abaArmazenamento(painel);
    else if (aba === "planos") await abaPlanosAdmin(painel);
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
      ${indicador(`${r.testes_ativos} · ${r.contas_free ?? 0}`, "testando o Profissional · contas Free")}
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
  if (c.dias_trial !== null) acesso = c.dias_trial < 0 ? `acabou há ${-c.dias_trial}d` : c.dias_trial === 0 ? "acaba hoje" : `${c.dias_trial} dia(s)`;
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
        <div class="campo"><label for="crm-preco">Valor contratado (legado, R$/mês)</label><input id="crm-preco" name="preco_contratado" inputmode="decimal" value="${c.preco_contratado ?? ""}" placeholder="tabela"></div>
        <div class="campo"><label for="crm-trial">Fim do teste do Profissional</label><input id="crm-trial" type="date" name="trial_fim" value="${fmt.paraInput(c.trial_fim)}"></div>
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
          <td>${esc(t.uf || "todas")}${t.desonerado === true ? "<br><small>desonerado</small>" : t.desonerado === false ? "<br><small>não desonerado</small>" : ""}</td><td>${fmt.data(t.data_base)}</td><td>${fmt.num(t.n_itens, 0)}</td>
          <td>${t.ativa ? carimbo("Ativa", "ok") : t.itens_removidos_em ? carimbo("Itens removidos", "neutro") : carimbo("Inativa", "neutro")}${!t.ativa && t.desativada_em && !t.itens_removidos_em ? `<br><small class="fraco">itens apagados 30 dias após ${fmt.data(t.desativada_em)}</small>` : ""}</td>
          <td class="acoes-celula">${t.itens_removidos_em ? "" : `<button class="botao pequeno secundario" data-ativar="${t.id}" data-valor="${t.ativa ? "0" : "1"}">${t.ativa ? "Desativar" : "Ativar"}</button>`}
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
      <p class="fraco">Cabeçalho encontrado na linha ${pv.linha_cabecalho + 1}.${pv.perfil ? ` Formato reconhecido: <b>${esc(d.fontes[pv.perfil] || pv.perfil)}</b>.` : ""} Confira as colunas.
        Todas as outras colunas também são guardadas: ${pv.colunas_preco.length} coluna(s) de preço${pv.perfil === "cmed" ? " (PF e PMVG por alíquota de ICMS: o Kasiski escolhe a do estado do órgão)" : ""} e as informativas (laboratório, registro, CAP, tarja...).</p>
      <div class="linha-campos mapa-colunas">
        ${[["descricao", "Descrição *"], ["preco", "Preço principal *"], ["codigo", "Código"], ["unidade", "Unidade"], ...(pv.perfil === "cmed" ? [["apresentacao", "Apresentação (junta à descrição)"]] : [])].map(([k, t]) =>
          `<div class="campo"><label for="tb-${k}">${t}</label><select id="tb-${k}" name="col_${k}">${opcoes(pv.sugestao[k])}</select></div>`).join("")}
      </div>
      <div class="tabela-rolagem" style="margin-bottom:14px"><table><thead><tr>${pv.colunas.map((c) => `<th>${esc(c)}</th>`).join("")}</tr></thead>
        <tbody>${pv.exemplos.map((r) => `<tr>${r.map((c) => `<td>${esc(c)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>
      <input type="hidden" name="linha_cabecalho" value="${pv.linha_cabecalho}">
      <div class="linha-campos">
        <div class="campo"><label for="tb-nome">Nome da tabela *</label><input id="tb-nome" name="nome" required value="${esc(nomeArq)}" placeholder="Ex.: SINAPI SP 09/2026 não desonerado"></div>
        <div class="campo"><label for="tb-fonte">Fonte</label><select id="tb-fonte" name="fonte">${Object.entries(d.fontes).map(([k, v]) => `<option value="${k}" ${k === pv.perfil ? "selected" : ""}>${esc(v)}</option>`).join("")}</select></div>
        <div class="campo"><label for="tb-des">Desoneração (SINAPI/SICRO)</label><select id="tb-des" name="desonerado"><option value="">Não se aplica</option><option value="nao">Não desonerado</option><option value="sim">Desonerado</option></select></div>
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
  email: "E-mail / newsletter", outbound: "Prospecção ativa (outbound)", parceiro: "Parceiros", indicacao: "Sites que indicaram", direto: "Direto / desconhecido" };
const ISCAS = { analisar_edital: "Analisador de edital", consultar_concorrente: "Consulta de concorrente", newsletter: "Newsletter", diagnostico: "Diagnóstico B2G", consultorias: "Página de consultorias",
  contato: "Contato", checklist: "Checklist", prospeccao: "Prospecção ativa (PNCP)", "cadastro direto": "Cadastro direto" };
const moedaOuTraco = (v) => (v === null || v === undefined ? "—" : fmt.moeda(v));
const pctOuTraco = (v) => (v === null || v === undefined ? "—" : `${fmt.num(v, 1)}%`);

async function abaMarketing(el) {
  const sub = V.admin.mk || "visao";
  el.innerHTML = `<div class="chips mk-abas" role="tablist" aria-label="Marketing">${[["visao", "Visão geral"], ["canais", "Canais e campanhas"], ["leads", "Leads"],
    ["prospeccao", "Prospecção"], ["ferramentas", "Ferramentas grátis"], ["newsletter", "Newsletter"], ["automacoes", "Automações de e-mail"], ["investimentos", "Investimentos"]]
    .map(([k, t]) => `<button data-mk="${k}" aria-pressed="${sub === k}">${t}</button>`).join("")}</div><div id="mk-corpo"><p class="carregando">Carregando…</p></div>`;
  $$("[data-mk]", el).forEach((b) => b.onclick = () => { V.admin.mk = b.dataset.mk; abaMarketing(el); });
  const c = $("#mk-corpo", el);
  try {
    if (sub === "leads") await mkLeads(c);
    else if (sub === "prospeccao") await mkProspeccao(c);
    else if (sub === "newsletter") await (V.admin.nlEdicao ? mkNewsletterEditor(c, V.admin.nlEdicao) : mkNewsletter(c));
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
      <section class="bloco"><h2>Diagnóstico de maturidade B2G</h2><div class="grade grade-4 grade-kpi">
        ${indicador(f.diagnosticos.total, "diagnósticos feitos")}${indicador(f.diagnosticos.com_email, "deixaram o e-mail")}
        ${indicador(f.diagnosticos.media === null ? "—" : f.diagnosticos.media + "/100", "nota média")}
        ${indicador(["inicial", "em_desenvolvimento", "estruturada", "avancada"].map((k) => f.diagnosticos.por_nivel[k] || 0).join(" · "), "inicial · em desenv. · estruturada · avançada")}</div>
        <p class="fraco" style="margin-top:10px">Empresas com nota baixa em Documentação e Oportunidades são as que mais ganham com o Radar e o Cofre: bom público para abordagem.</p></section>
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

const NOMES_EVENTO = { prospect_report_view: "Abriu o relatório da prospecção", prospect_converted: "Empresa prospectada virou cliente", page_view: "Visitou o site", cta_click: "Clicou em um CTA", pricing_view: "Viu os planos", generate_lead: "Deixou o contato", tool_started: "Usou uma ferramenta grátis",
  edital_free_analysis: "Análise gratuita de edital", diagnostic_completed: "Fez o diagnóstico B2G", checklist_import: "Montou o checklist para importar", checklist_download: "Baixou o checklist", competitor_search: "Consultou concorrente", sign_up: "Criou conta", trial_started: "Iniciou o teste", company_created: "Cadastrou a empresa",
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
    ${(l.diagnosticos || []).length ? `<p><b>Diagnóstico B2G:</b> ${l.diagnosticos.map((x) => `${x.nota}/100 (${esc(x.nivel)}) — ${Object.entries(x.eixos || {}).map(([k, v]) => `${esc(k)} ${v === null ? "n/a" : v}`).join(", ")} · ${fmt.data(x.criado_em)}`).join("; ")}</p>` : ""}
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


// ---------------------------------------------------------------- Newsletter Kasiski Intelligence
const STATUS_NL = { rascunho: ["Rascunho", "neutro"], agendada: ["Agendada", "aviso"], enviando: ["Enviando", "oficio"], enviada: ["Enviada", "ok"] };
const nlMoeda = (v) => {
  v = Number(v || 0);
  for (const [lim, suf] of [[1e9, "bi"], [1e6, "mi"], [1e3, "mil"]]) if (v >= lim) return `R$ ${fmt.num(v / lim, v / lim < 100 ? 1 : 0)} ${suf}`;
  return fmt.moeda(v);
};
const semanaTxt = (e) => `${fmt.data(e.semana_inicio).slice(0, 5)} a ${fmt.data(e.semana_fim)}`;

async function mkNewsletter(el) {
  const d = await api("GET", "/api/admin/marketing/newsletter");
  const linhas = d.edicoes.map((e) => {
    const s = e.stats;
    return `<tr><td><b>#${e.numero}</b></td><td>${semanaTxt(e)}</td><td>${esc(e.assunto || e.titulo || "—")}</td>
      <td>${carimboStatus(STATUS_NL, e.status)}${e.coletando ? ' <small class="fraco">coletando dados…</small>' : ""}${e.status === "agendada" && e.agendada_para ? `<br><small class="fraco">${fmt.dataHora(e.agendada_para)}</small>` : ""}</td>
      <td>${s ? fmt.num(s.enviados, 0) : "—"}</td><td>${s ? pctOuTraco(s.taxa_abertura) : "—"}</td><td>${s ? pctOuTraco(s.taxa_clique) : "—"}</td><td>${s ? fmt.num(s.descadastros, 0) : "—"}</td>
      <td class="acoes-celula"><button class="botao pequeno secundario" data-nl="${e.id}">${e.status === "rascunho" || e.status === "agendada" ? "Editar" : "Ver"}</button></td></tr>`;
  }).join("");
  el.innerHTML = `${d.email_configurado ? "" : `<div class="aviso">O envio de e-mail não está configurado (RESEND_API_KEY). Você pode montar as edições; o envio fica liberado quando a chave for preenchida no Render.</div>`}
    <section class="bloco"><div class="grade grade-4 grade-kpi">
      ${indicador(fmt.num(d.inscritos, 0), "Inscritos ativos (confirmados)")}${indicador(fmt.num(d.novos_30d, 0), "Novos inscritos em 30 dias")}
      ${indicador(pctOuTraco(d.abertura_media), "Abertura média (últimas 8)")}${indicador(pctOuTraco(d.clique_medio), "Clique médio (últimas 8)")}</div>
      ${d.aguardando_confirmacao ? `<p class="fraco" style="margin-top:10px">${d.aguardando_confirmacao} pessoa(s) se inscreveram e ainda não confirmaram o e-mail; elas só recebem depois de confirmar.</p>` : ""}</section>
    <section class="bloco"><div class="bloco-titulo"><h2>Edições</h2>
      <div class="acoes"><button class="botao pequeno secundario" id="nl-csv">Exportar inscritos (CSV)</button>
      <button class="botao pequeno" id="nl-nova">${d.semana_sugerida_existe ? "Nova edição de outra semana" : `Gerar edição da semana de ${fmt.data(d.semana_sugerida).slice(0, 5)}`}</button></div></div>
      <p class="fraco">Toda segunda-feira, às 6h, o Kasiski coleta no PNCP os dados da semana anterior e deixa um rascunho pronto (você recebe um e-mail). Revise as oportunidades, escreva o radar regulatório e envie ou agende.</p>
      <div class="tabela-rolagem">${linhas ? `<table><thead><tr><th>Nº</th><th>Semana</th><th>Assunto</th><th>Status</th><th>Enviados</th><th>Abertura</th><th>Clique</th><th>Saíram</th><th></th></tr></thead><tbody>${linhas}</tbody></table>`
        : vazio("Nenhuma edição ainda", "Gere a primeira edição com os dados da semana passada.")}</div></section>`;
  $$("[data-nl]", el).forEach((b) => b.onclick = () => { V.admin.nlEdicao = Number(b.dataset.nl); mkNewsletterEditor(el, V.admin.nlEdicao); });
  $("#nl-csv", el).onclick = (ev) => ocupado(ev.target, "Exportando…", () => baixar("/api/admin/marketing/leads.csv?newsletter=1", "kasiski-newsletter.csv"));
  $("#nl-nova", el).onclick = async (ev) => {
    let semana = null;
    if (d.semana_sugerida_existe) {
      const m = modal({ titulo: "Nova edição", corpo: `<form id="nl-sem"><div class="campo"><label for="nl-data">Qualquer dia da semana desejada</label><input id="nl-data" name="semana" type="date" required></div></form>`,
        acoes: `<button class="botao secundario" data-fechar>Cancelar</button><button class="botao" form="nl-sem" type="submit">Gerar</button>` });
      semana = await new Promise((ok) => { $("#nl-sem", m).onsubmit = (e2) => { e2.preventDefault(); const v = $("#nl-data", m).value; m.fechar(); ok(v); }; });
      if (!semana) return;
    }
    await ocupado(ev.target, "Gerando…", async () => {
      try { const e = await api("POST", "/api/admin/marketing/newsletter", semana ? { semana } : {}); V.admin.nlEdicao = e.id; toast("Rascunho criado. Coletando os dados do PNCP…", "ok"); mkNewsletterEditor(el, e.id); }
      catch (e) { avisarErro(e); }
    });
  };
}

async function mkNewsletterEditor(el, id) {
  clearTimeout(V.admin.nlTimer);
  let ed;
  try { ed = await api("GET", `/api/admin/marketing/newsletter/${id}`); } catch (e) { V.admin.nlEdicao = null; return mkNewsletter(el); }
  const voltar = `<button class="botao pequeno texto" id="nl-voltar">← Todas as edições</button>`;
  const editavel = ["rascunho", "agendada"].includes(ed.status);
  const m = (ed.dados || {}).metricas || {};
  const ocultas = new Set(ed.ocultas || []);
  const ops = (ed.dados || {}).oportunidades || [];
  const cab = `<div class="bloco-titulo"><div>${voltar}<h2 style="margin-top:6px">Kasiski Intelligence #${ed.numero} <small class="fraco">semana de ${semanaTxt(ed)}</small></h2></div><div>${carimboStatus(STATUS_NL, ed.status)}</div></div>`;

  if (ed.coletando) {
    el.innerHTML = `<section class="bloco">${cab}<p class="carregando">Coletando as contratações da semana no PNCP. Isso leva de 1 a 5 minutos; esta tela atualiza sozinha.</p></section>`;
    $("#nl-voltar", el).onclick = () => { V.admin.nlEdicao = null; clearTimeout(V.admin.nlTimer); mkNewsletter(el); };
    V.admin.nlTimer = setTimeout(() => { if (el.isConnected && V.admin.nlEdicao === id) mkNewsletterEditor(el, id); }, 5000);
    return;
  }

  if (!editavel) {
    const s = ed.stats || {};
    el.innerHTML = `<section class="bloco">${cab}
      <div class="grade grade-4 grade-kpi">${indicador(fmt.num(s.enviados, 0), `Enviados${s.falhas ? ` · ${s.falhas} falha(s)` : ""}`)}${indicador(pctOuTraco(s.taxa_abertura), `Abertura (${fmt.num(s.abertos, 0)} pessoas)`)}
        ${indicador(pctOuTraco(s.taxa_clique), `Clique (${fmt.num(s.clicaram, 0)} pessoas)`)}${indicador(fmt.num(s.descadastros, 0), "Descadastros")}</div>
      <p class="fraco" style="margin-top:10px">${ed.status === "enviando" ? "Envio em andamento. " : `Enviada em ${fmt.dataHora(ed.enviada_em)}. `}Assunto: <b>${esc(ed.assunto)}</b>. A abertura é aproximada: alguns programas de e-mail bloqueiam imagens e outros abrem automaticamente.</p>
      ${s.falhas && ed.status === "enviada" ? `<button class="botao pequeno secundario" id="nl-refalhas">Reenviar para as ${s.falhas} falha(s)</button>` : ""}</section>
      ${(s.links || []).length ? `<section class="bloco tabela-rolagem"><h2>Links mais clicados</h2><table><thead><tr><th>Link</th><th>Pessoas</th></tr></thead>
        <tbody>${s.links.map((l) => `<tr><td><small>${esc(l.url.replace(/[?&]utm_[^&]+/g, "").slice(0, 110))}</small></td><td>${l.pessoas}</td></tr>`).join("")}</tbody></table></section>` : ""}
      <section class="bloco"><h2>Como ficou</h2><iframe class="nl-previa" id="nl-previa" title="Prévia da edição"></iframe></section>`;
    $("#nl-voltar", el).onclick = () => { V.admin.nlEdicao = null; mkNewsletter(el); };
    const rf = $("#nl-refalhas", el);
    if (rf) rf.onclick = () => ocupado(rf, "Reenviando…", async () => { try { await api("POST", `/api/admin/marketing/newsletter/${id}/reenviar-falhas`); toast("Reenvio iniciado.", "ok"); setTimeout(() => mkNewsletterEditor(el, id), 2500); } catch (e) { avisarErro(e); } });
    const p = await api("GET", `/api/admin/marketing/newsletter/${id}/previa`);
    $("#nl-previa", el).srcdoc = p.html;
    if (ed.status === "enviando") V.admin.nlTimer = setTimeout(() => { if (el.isConnected && V.admin.nlEdicao === id) mkNewsletterEditor(el, id); }, 5000);
    return;
  }

  const radar = (ed.radar && ed.radar.length ? ed.radar : [{}]);
  const linhaRadar = (r, k) => `<div class="nl-radar" data-radar="${k}">
      <div class="linha-campos"><div class="campo"><label>Título</label><input name="titulo" value="${esc(r.titulo || "")}" placeholder="Ex.: TCU fixa entendimento sobre exigência de atestado"></div>
      <div class="campo" style="max-width:180px"><label>Fonte</label><input name="fonte" value="${esc(r.fonte || "")}" placeholder="TCU, DOU, SEGES…"></div></div>
      <div class="campo"><label>Resumo (o que muda para quem vende ao governo)</label><textarea name="resumo" rows="2">${esc(r.resumo || "")}</textarea></div>
      <div class="linha-campos"><div class="campo"><label>Link (opcional)</label><input name="link" type="url" value="${esc(r.link || "")}" placeholder="https://"></div>
      <div class="campo" style="flex:0 0 auto;align-self:end"><button type="button" class="botao pequeno texto" data-tirar-radar="${k}">Remover</button></div></div></div>`;
  const erroColeta = (ed.dados || {}).erro_coleta || ((ed.dados || {}).falhas || []).length;
  el.innerHTML = `<section class="bloco">${cab}
      ${erroColeta ? `<div class="aviso">A coleta no PNCP ${ (ed.dados || {}).erro_coleta ? "falhou" : `não leu: ${esc((ed.dados.falhas || []).join(", "))}`}. Tente "Atualizar dados do PNCP" de novo em alguns minutos.</div>` : ""}
      <p class="fraco">${m.publicadas ? `${fmt.num(m.publicadas, 0)} contratações publicadas · ${fmt.num(m.competitivas, 0)} com disputa · ${m.estimado ? "≈ " : ""}${nlMoeda(m.valor_competitivas)} em valor estimado${m.estimado ? ` (projeção a partir de ${fmt.num(m.amostra, 0)} licitações lidas)` : ""} · dados de ${fmt.dataHora(ed.coletado_em)}` : "Sem dados do PNCP ainda."}
      <button class="botao pequeno texto" id="nl-atualizar">Atualizar dados do PNCP</button></p>
      ${ed.status === "agendada" ? `<div class="aviso">Envio agendado para ${fmt.dataHora(ed.agendada_para)} para ${fmt.num(ed.inscritos, 0)} inscrito(s). <button class="botao pequeno texto" id="nl-cancelar">Cancelar agendamento</button></div>` : ""}</section>
    <div class="nl-editor">
      <form id="nl-form" class="bloco">
        <div class="campo"><label for="nl-assunto">Assunto do e-mail</label><input id="nl-assunto" name="assunto" maxlength="200" value="${esc(ed.assunto || "")}"><small class="fraco" data-conta-assunto></small></div>
        <div class="campo"><label for="nl-pre">Pré-cabeçalho (texto que aparece ao lado do assunto)</label><input id="nl-pre" name="pre_cabecalho" maxlength="200" value="${esc(ed.pre_cabecalho || "")}"></div>
        <div class="campo"><label for="nl-titulo">Título da edição</label><input id="nl-titulo" name="titulo" maxlength="200" value="${esc(ed.titulo || "")}"></div>
        <div class="campo"><div class="bloco-titulo" style="margin:0"><label for="nl-abertura">Abertura</label><button type="button" class="botao pequeno texto" id="nl-ia">Sugerir com IA</button></div>
          <textarea id="nl-abertura" name="abertura" rows="6">${esc(ed.abertura || "")}</textarea><small class="fraco">Parágrafos separados por uma linha em branco.</small></div>
        <h3>As 5 maiores oportunidades</h3>
        <p class="fraco">Entram as 5 primeiras marcadas. Desmarque as que não fizerem sentido (valor com erro, objeto genérico) e a próxima da lista sobe.</p>
        <div class="nl-ops">${ops.length ? ops.map((o, k) => `<label class="nl-op"><input type="checkbox" data-op="${esc(o.numero_controle)}" ${ocultas.has(o.numero_controle) ? "" : "checked"}>
          <span><b>${fmt.moeda(o.valor)}</b> · <small>${esc(o.setor)} · ${esc(o.uf || "")} · até ${fmt.data((o.data_encerramento || "").slice(0, 10))}</small><br>${esc((o.objeto || "").slice(0, 160))}<br><small class="fraco">${esc(o.orgao)}</small>
          ${o.link ? ` <a href="${esc(o.link)}" target="_blank" rel="noopener">PNCP</a>` : ""}</span></label>`).join("") : '<p class="fraco">Nenhuma oportunidade aberta encontrada nos dados.</p>'}</div>
        <h3>Radar regulatório</h3>
        <p class="fraco">Até 10 itens: mudanças na Lei 14.133, decretos, instruções normativas, jurisprudência do TCU. Itens sem título não entram no e-mail.</p>
        <div id="nl-radar">${radar.map(linhaRadar).join("")}</div>
        <button type="button" class="botao pequeno secundario" id="nl-mais-radar">Adicionar item</button>
        <div class="acoes nl-acoes"><button class="botao secundario" type="submit">Salvar</button><button class="botao secundario" type="button" id="nl-teste">Enviar teste para mim</button>
          <button class="botao secundario" type="button" id="nl-agendar">Agendar</button><button class="botao" type="button" id="nl-enviar">Enviar para ${fmt.num(ed.inscritos, 0)} inscrito(s)</button>
          <button class="botao texto" type="button" id="nl-excluir"${ed.status === "rascunho" ? "" : " hidden"}>Excluir rascunho</button></div>
      </form>
      <section class="bloco nl-lado"><div class="bloco-titulo"><h2>Prévia</h2><small class="fraco" id="nl-salvo"></small></div><iframe class="nl-previa" id="nl-previa" title="Prévia do e-mail"></iframe></section>
    </div>`;

  const form = $("#nl-form", el);
  const coletar = () => ({
    assunto: form.assunto.value, pre_cabecalho: form.pre_cabecalho.value, titulo: form.titulo.value, abertura: form.abertura.value,
    ocultas: $$("[data-op]", form).filter((c) => !c.checked).map((c) => c.dataset.op),
    radar: $$("[data-radar]", form).map((r) => ({ titulo: $("[name=titulo]", r).value, fonte: $("[name=fonte]", r).value, resumo: $("[name=resumo]", r).value, link: $("[name=link]", r).value })),
  });
  const previa = async () => { const p = await api("GET", `/api/admin/marketing/newsletter/${id}/previa`); const f = $("#nl-previa", el); if (f) f.srcdoc = p.html; };
  const salvar = async (silencioso) => {
    await api("PATCH", `/api/admin/marketing/newsletter/${id}`, coletar());
    const s = $("#nl-salvo", el); if (s) s.textContent = `Salvo às ${new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}`;
    if (!silencioso) toast("Edição salva.", "ok");
    await previa();
  };
  const contaAssunto = () => { const n = form.assunto.value.length; $("[data-conta-assunto]", form).textContent = `${n} caracteres${n > 70 ? " · assuntos até ~70 caracteres aparecem inteiros no celular" : ""}`; };
  form.assunto.oninput = contaAssunto; contaAssunto();
  let t = null;
  form.addEventListener("input", () => { clearTimeout(t); t = setTimeout(() => salvar(true).catch(() => {}), 1200); });
  form.addEventListener("change", (ev) => { if (ev.target.matches("[data-op]")) salvar(true).catch(avisarErro); });
  form.onsubmit = async (ev) => { ev.preventDefault(); try { await salvar(false); } catch (e) { avisarErro(e); } };
  const religarRadar = () => $$("[data-tirar-radar]", form).forEach((b) => b.onclick = () => { b.closest("[data-radar]").remove(); salvar(true).catch(avisarErro); });
  religarRadar();
  $("#nl-mais-radar", el).onclick = () => {
    const box = $("#nl-radar", el);
    if (box.children.length >= 10) return toast("Até 10 itens no radar.", "aviso");
    box.insertAdjacentHTML("beforeend", linhaRadar({}, Date.now())); religarRadar(); $("[data-radar]:last-child [name=titulo]", box).focus();
  };
  $("#nl-voltar", el).onclick = async () => { clearTimeout(t); try { await salvar(true); } catch { /* segue */ } V.admin.nlEdicao = null; mkNewsletter(el); };
  $("#nl-atualizar", el).onclick = async (ev) => {
    if (!(await confirmar("Coletar de novo os dados desta semana no PNCP? Os números e a lista de oportunidades serão atualizados; seus textos e o radar ficam como estão.", "Atualizar"))) return;
    try { await salvar(true); await api("POST", `/api/admin/marketing/newsletter/${id}/atualizar`); mkNewsletterEditor(el, id); } catch (e) { avisarErro(e); }
  };
  $("#nl-ia", el).onclick = (ev) => ocupado(ev.target, "Escrevendo…", async () => {
    try {
      const r = await api("POST", `/api/admin/marketing/newsletter/${id}/sugerir`);
      if (form.abertura.value.trim() && !(await confirmar("Substituir a abertura atual pela sugestão da IA? Revise os números antes de enviar.", "Substituir"))) return;
      form.abertura.value = r.abertura; if (r.assunto) form.assunto.value = r.assunto; contaAssunto(); await salvar(true); toast("Sugestão aplicada. Revise antes de enviar.", "ok");
    } catch (e) { avisarErro(e); }
  });
  $("#nl-teste", el).onclick = (ev) => ocupado(ev.target, "Enviando…", async () => {
    try { await salvar(true); const r = await api("POST", `/api/admin/marketing/newsletter/${id}/teste`); toast(`Teste enviado para ${r.para}.`, "ok"); } catch (e) { avisarErro(e); }
  });
  $("#nl-enviar", el).onclick = async (ev) => {
    try { await salvar(true); } catch (e) { return avisarErro(e); }
    if (!(await confirmar(`Enviar a edição #${ed.numero} agora para ${ed.inscritos} inscrito(s)? Depois de enviada, ela não pode ser alterada.`, "Enviar agora"))) return;
    try { await api("POST", `/api/admin/marketing/newsletter/${id}/enviar`); toast("Envio iniciado.", "ok"); setTimeout(() => mkNewsletterEditor(el, id), 1500); } catch (e) { avisarErro(e); }
  };
  $("#nl-agendar", el).onclick = async () => {
    try { await salvar(true); } catch (e) { return avisarErro(e); }
    const amanha = new Date(Date.now() + 86400000); amanha.setHours(8, 0, 0, 0);
    const local = new Date(amanha.getTime() - amanha.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
    const mm = modal({ titulo: "Agendar envio", corpo: `<form id="nl-ag"><div class="campo"><label for="nl-quando">Data e hora (horário do seu computador)</label><input id="nl-quando" type="datetime-local" value="${local}" required></div>
      <p class="fraco">Terças e quartas entre 7h e 9h costumam ter as melhores taxas de abertura em B2B.</p></form>`,
      acoes: `<button class="botao secundario" data-fechar>Cancelar</button><button class="botao" form="nl-ag" type="submit">Agendar</button>` });
    $("#nl-ag", mm).onsubmit = async (e2) => {
      e2.preventDefault();
      const quando = new Date($("#nl-quando", mm).value);
      try { await api("POST", `/api/admin/marketing/newsletter/${id}/enviar`, { quando: quando.toISOString() }); mm.fechar(); toast("Envio agendado.", "ok"); mkNewsletterEditor(el, id); } catch (e) { avisarErro(e); }
    };
  };
  const canc = $("#nl-cancelar", el);
  if (canc) canc.onclick = async () => { try { await api("POST", `/api/admin/marketing/newsletter/${id}/cancelar`); toast("Agendamento cancelado.", "ok"); mkNewsletterEditor(el, id); } catch (e) { avisarErro(e); } };
  $("#nl-excluir", el).onclick = async () => {
    if (!(await confirmar("Excluir este rascunho?", "Excluir"))) return;
    try { await api("DELETE", `/api/admin/marketing/newsletter/${id}`); V.admin.nlEdicao = null; mkNewsletter(el); } catch (e) { avisarErro(e); }
  };
  await previa();
}

// ---------------------------------------------------------------- Prospecção ativa (PNCP → Lead Score Kasiski)
const STATUS_PROSP = { novo: ["Novo", "neutro"], contatado: ["Contatado", "oficio"], respondeu: ["Respondeu", "aviso"], lead: ["No CRM", "aviso"],
  cliente: ["Cliente", "ok"], descartado: ["Descartado", "neutro"], nao_contatar: ["Não contatar", "erro"] };
const FAIXA_PROSP = { A: ["A", "ok"], B: ["B", "oficio"], C: ["C", "aviso"], D: ["D", "neutro"] };
const PLANO_PROSP = { essencial: "Essencial", profissional: "Profissional", business: "Business", avancado: "Business", consultor: "Consultor" };
const BUSCA_ST = { na_fila: "na fila", buscando: "buscando no PNCP", enriquecendo: "consultando a Receita", concluida: "concluída", erro: "erro" };

async function mkProspeccao(el) {
  clearTimeout(V.admin.prTimer);
  const f = V.admin.prFiltro || { faixa: "", status: "", uf: "", q: "", busca: "", ordem: "score" };
  V.admin.prFiltro = f;
  const qs = new URLSearchParams(Object.entries(f).filter(([, v]) => v)).toString();
  const d = await api("GET", `/api/admin/marketing/prospeccao?${qs}`);
  const k = d.kpi;
  const andamento = d.buscas.find((b) => ["na_fila", "buscando", "enriquecendo"].includes(b.status));
  el.innerHTML = `
    <section class="bloco"><div class="grade grade-4 grade-kpi">
      ${indicador(fmt.num(k.total, 0), "empresas mapeadas")}${indicador(fmt.num(k.faixa_a, 0), "faixa A (maior aderência)")}
      ${indicador(`${fmt.num(k.contatados, 0)} · ${fmt.num(k.relatorios_abertos, 0)}`, "contatadas · abriram o relatório")}${indicador(`${fmt.num(k.leads, 0)} · ${fmt.num(k.clientes, 0)}`, "no CRM · viraram clientes")}</div>
      <p class="fraco" style="margin:12px 0 0">Quem vence licitação é quem precisa do Kasiski. A busca lê no PNCP os contratos e atas do segmento, identifica as empresas vencedoras,
        completa com os dados públicos da Receita e calcula o <b>Lead Score Kasiski</b>: volume, órgãos atendidos, recorrência, recência e porte. Só dados de empresas.
        Abordagem por LinkedIn e telefone, com o relatório gratuito de cada empresa como gancho.</p></section>
    <section class="bloco"><div class="bloco-titulo"><h2>Nova busca</h2>${andamento ? `<span class="carregando">${esc(andamento.nome)}: ${esc(andamento.etapa || BUSCA_ST[andamento.status])}</span>` : ""}</div>
      <form id="pr-form"><div class="chips" style="margin-bottom:10px">${Object.keys(d.segmentos).map((s) => `<button type="button" data-seg="${esc(s)}">${esc(s)}</button>`).join("")}</div>
        <div class="linha-campos">
          <div class="campo" style="grid-column:span 2"><label for="pr-termos">Termos do segmento (separados por vírgula)</label><input id="pr-termos" name="termos" required placeholder="Ex.: limpeza predial, conservação e limpeza"></div>
          <div class="campo"><label for="pr-ufs">UFs (opcional)</label><input id="pr-ufs" name="ufs" placeholder="SP, MG"></div>
          <div class="campo"><label for="pr-meses">Período</label><select id="pr-meses" name="meses"><option value="6">6 meses</option><option value="12" selected>12 meses</option><option value="24">24 meses</option></select></div>
          <div class="campo"><label for="pr-lim">Empresas a completar na Receita</label><select id="pr-lim" name="limite"><option>50</option><option selected>100</option><option>200</option></select></div></div>
        <button class="botao" type="submit" ${andamento ? "disabled" : ""}>Buscar empresas</button> <small class="fraco">Leva de 3 a 10 minutos; pode sair da tela.</small></form>
      ${d.buscas.length ? `<details style="margin-top:12px"><summary class="fraco">Buscas anteriores (${d.buscas.length})</summary><ul class="exemplos-conc">${d.buscas.map((b) => `<li><b>${esc(b.nome)}</b>${b.ufs.length ? " · " + esc(b.ufs.join(", ")) : ""} · ${b.meses} meses · ${esc(BUSCA_ST[b.status] || b.status)} · ${b.documentos} contratações, ${b.empresas} empresas · ${fmt.dataHora(b.criado_em)}
        ${b.status === "concluida" ? ` <button class="botao pequeno texto" data-pr-busca="${b.id}">ver só esta</button>` : ""}${b.erro ? ` <span class="texto-alerta">${esc(b.erro)}</span>` : ""}</li>`).join("")}</ul></details>` : ""}</section>
    <section class="bloco"><div class="filtros-admin">
        <div class="chips" role="group" aria-label="Faixa">${[["", "Todas as faixas"], ["A", "A"], ["A,B", "A e B"], ["C", "C"], ["D", "D"]].map(([v, t]) => `<button data-pr-faixa="${v}" aria-pressed="${f.faixa === v}">${t}</button>`).join("")}</div>
        <div class="chips" role="group" aria-label="Situação">${[["", "Em aberto"], ["novo", "Novos"], ["contatado,respondeu", "Em contato"], ["lead", "No CRM"], ["cliente", "Clientes"], ["descartado,nao_contatar", "Fora da lista"]].map(([v, t]) => `<button data-pr-status="${v}" aria-pressed="${f.status === v}">${t}</button>`).join("")}</div>
        <select id="pr-ordem" aria-label="Ordenar">${[["score", "Maior score"], ["recentes", "Vitória mais recente"], ["valor", "Maior valor"], ["relatorio", "Abriram o relatório"]].map(([v, t]) => `<option value="${v}" ${f.ordem === v ? "selected" : ""}>${t}</option>`).join("")}</select>
        <input id="pr-busca-txt" placeholder="Buscar empresa ou CNPJ" value="${esc(f.q)}" style="max-width:220px"><input id="pr-uf" placeholder="UF" maxlength="2" value="${esc(f.uf)}" style="max-width:70px">
        <button class="botao pequeno secundario" id="pr-csv">Exportar CSV</button>${f.busca ? ` <button class="botao pequeno texto" id="pr-limpa-busca">× busca #${esc(f.busca)}</button>` : ""}</div>
      <div class="tabela-rolagem">${d.prospects.length ? `<table class="tabela-prosp"><thead><tr><th>Score</th><th>Empresa</th><th>Atividade</th><th>Valor contratado</th><th>Plano sugerido</th><th>Contato (Receita)</th><th>Situação</th><th></th></tr></thead>
        <tbody>${d.prospects.map((p) => `<tr>
          <td><div class="score-prosp"><b>${p.score}</b>${carimboStatus(FAIXA_PROSP, p.faixa)}</div><div class="barra-score"><i style="width:${p.score}%"></i></div></td>
          <td><b>${esc(p.nome_fantasia || p.razao_social || "—")}</b><br><small class="fraco">${fmt.cnpj(p.cnpj)} · ${esc(p.porte || "porte ?")}${p.municipio ? " · " + esc(p.municipio) + "/" + esc(p.uf) : ""}</small>
            ${p.relatorio_visto_em ? `<br><small class="etiqueta-conc">abriu o relatório ${fmt.dataHora(p.relatorio_visto_em)}</small>` : ""}</td>
          <td>${(p.contratos || 0) + (p.atas || 0)} vitória(s) · ${p.n_orgaos} órgão(s)<br><small class="fraco">última ${fmt.data(p.ultima_vitoria)}${p.ufs_atuacao.length > 1 ? " · " + esc(p.ufs_atuacao.join(", ")) : ""}</small></td>
          <td>${fmt.moeda(p.valor_total)}</td><td>${esc(PLANO_PROSP[p.plano_sugerido] || "—")}</td>
          <td><small>${esc(p.telefone || "—")}${p.email_empresa ? `<br>${esc(p.email_empresa)}` : ""}</small></td>
          <td>${carimboStatus(STATUS_PROSP, p.status)}</td>
          <td class="acoes-celula"><button class="botao pequeno secundario" data-pr-abrir="${p.id}">Abordar</button></td></tr>`).join("")}</tbody></table>`
        : vazio("Nenhuma empresa na lista", "Faça uma busca por segmento para mapear quem vence licitações.")}</div></section>`;

  const recarregar = () => mkProspeccao(el);
  $$("[data-seg]", el).forEach((b) => b.onclick = () => { $("#pr-termos", el).value = d.segmentos[b.dataset.seg].join(", "); });
  $("#pr-form", el).onsubmit = async (ev) => {
    ev.preventDefault();
    try { await api("POST", "/api/admin/marketing/prospeccao/buscas", dadosForm(ev.target)); toast("Busca iniciada. A lista atualiza sozinha.", "ok"); recarregar(); } catch (e) { avisarErro(e); }
  };
  $$("[data-pr-faixa]", el).forEach((b) => b.onclick = () => { f.faixa = b.dataset.prFaixa; recarregar(); });
  $$("[data-pr-status]", el).forEach((b) => b.onclick = () => { f.status = b.dataset.prStatus; recarregar(); });
  $$("[data-pr-busca]", el).forEach((b) => b.onclick = () => { f.busca = b.dataset.prBusca; recarregar(); });
  const lb = $("#pr-limpa-busca", el); if (lb) lb.onclick = () => { f.busca = ""; recarregar(); };
  $("#pr-ordem", el).onchange = (ev) => { f.ordem = ev.target.value; recarregar(); };
  $("#pr-busca-txt", el).onchange = (ev) => { f.q = ev.target.value; recarregar(); };
  $("#pr-uf", el).onchange = (ev) => { f.uf = ev.target.value; recarregar(); };
  $("#pr-csv", el).onclick = (ev) => ocupado(ev.target, "Exportando…", () => baixar("/api/admin/marketing/prospeccao.csv", "kasiski-prospeccao.csv"));
  $$("[data-pr-abrir]", el).forEach((b) => b.onclick = () => modalProspect(Number(b.dataset.prAbrir), recarregar));
  if (andamento) V.admin.prTimer = setTimeout(() => { if (el.isConnected && (V.admin.mk === "prospeccao")) recarregar(); }, 6000);
}

async function modalProspect(id, aoMudar) {
  let p = await api("GET", `/api/admin/marketing/prospeccao/${id}`);
  const r = p.roteiro;
  const copiar = (txt) => navigator.clipboard.writeText(txt).then(() => toast("Copiado.", "ok"), () => toast("Não foi possível copiar.", "erro"));
  const m = modal({ titulo: p.nome_fantasia || p.razao_social || fmt.cnpj(p.cnpj), largo: true, corpo: `
    <p class="fraco" style="margin-top:0">${esc(p.razao_social || "")} · ${fmt.cnpj(p.cnpj)} · ${esc(p.porte || "porte não informado")} · ${esc(p.cnae_descricao || "")}${p.municipio ? " · " + esc(p.municipio) + "/" + esc(p.uf) : ""}${p.situacao ? " · " + esc(p.situacao) : ""}</p>
    <div class="grade grade-4 grade-kpi">${indicador(`${p.score} · ${p.faixa}`, "Lead Score Kasiski")}${indicador((p.contratos || 0) + (p.atas || 0), `vitórias (${p.contratos} contratos, ${p.atas} atas)`)}
      ${indicador(p.n_orgaos, "órgãos atendidos")}${indicador(esc(PLANO_PROSP[p.plano_sugerido] || "—"), "plano sugerido")}</div>
    <h3>Por que é um bom cliente</h3><ul>${(p.motivos || []).map((x) => `<li>${esc(x)}</li>`).join("")}</ul>
    <h3>Contato</h3>
    <p>${p.telefone ? `Telefone: <b>${esc(p.telefone)}</b>` : "Sem telefone na Receita"}${p.email_empresa ? ` · E-mail: ${esc(p.email_empresa)}` : ""}
      <br><small class="fraco">Contato do cadastro na Receita: muitas vezes é do escritório de contabilidade. Use para achar o responsável por licitações.</small></p>
    ${(p.socios || []).length ? `<p><small>Sócios/administradores (QSA público): ${p.socios.map((s) => `${esc(s.nome)}${s.qualificacao ? ` (${esc(s.qualificacao)})` : ""}`).join(" · ")}</small></p>` : ""}
    <div class="acoes"><a class="botao pequeno secundario" href="https://www.linkedin.com/search/results/companies/?keywords=${encodeURIComponent(p.nome_fantasia || p.razao_social || "")}" target="_blank" rel="noopener">Procurar a empresa no LinkedIn</a>
      <a class="botao pequeno secundario" href="${esc(p.link_relatorio)}&previa=1" target="_blank" rel="noopener">Ver o relatório gratuito</a>
      <button class="botao pequeno secundario" data-copiar="link">Copiar link do relatório</button></div>
    <h3>Mensagens prontas</h3>
    <div class="roteiro"><div class="bloco-titulo"><b>LinkedIn: pedido de conexão</b><button class="botao pequeno texto" data-copiar="conexao">Copiar</button></div><p>${esc(r.linkedin_conexao)}</p></div>
    <div class="roteiro"><div class="bloco-titulo"><b>LinkedIn: mensagem após aceitar</b><button class="botao pequeno texto" data-copiar="mensagem">Copiar</button></div><p style="white-space:pre-line">${esc(r.linkedin_mensagem)}</p></div>
    <div class="roteiro"><b>Roteiro de telefone</b><ol>${r.telefone.map((x) => `<li>${esc(x)}</li>`).join("")}</ol></div>
    <h3>Onde vende</h3><p><small>${Object.entries(p.orgaos || {}).slice(0, 10).map(([o, n]) => `${esc(o)} (${n})`).join(" · ") || "—"}</small></p>
    ${(p.exemplos || []).length ? `<ul class="exemplos-conc">${p.exemplos.slice(0, 6).map((x) => `<li>${x.tipo === "ata" ? "Ata" : "Contrato"} · ${esc(x.orgao || "")} · ${fmt.data(x.data)}${x.valor ? " · " + fmt.moeda(x.valor) : ""}<br><span class="fraco">${esc(x.objeto || "")}</span>${x.link ? ` <a href="${esc(x.link)}" target="_blank" rel="noopener">PNCP</a>` : ""}</li>`).join("")}</ul>` : ""}
    <form id="pr-edit" class="linha-campos" style="margin-top:14px">
      <div class="campo"><label for="pe-st">Situação</label><select id="pe-st" name="status">${Object.entries(STATUS_PROSP).map(([k, [t]]) => `<option value="${k}" ${p.status === k ? "selected" : ""}>${t}</option>`).join("")}</select></div>
      <div class="campo"><label for="pe-resp">Responsável</label><input id="pe-resp" name="responsavel" value="${esc(p.responsavel || "")}"></div>
      <div class="campo" style="grid-column:1/-1"><label for="pe-notas">Anotações</label><textarea id="pe-notas" name="notas" rows="3">${esc(p.notas || "")}</textarea></div></form>`,
    acoes: `<button class="botao texto" id="pe-reav">Atualizar dados da Receita</button>
      ${p.lead_id ? `<span class="fraco">Lead #${p.lead_id} no CRM</span>` : `<button class="botao secundario" id="pe-crm" ${p.status === "nao_contatar" ? "disabled" : ""}>Enviar ao CRM de leads</button>`}
      <button class="botao" id="pe-salvar">Salvar</button>` });
  const textos = { link: p.link_relatorio, conexao: r.linkedin_conexao, mensagem: r.linkedin_mensagem };
  $$("[data-copiar]", m).forEach((b) => b.onclick = () => copiar(textos[b.dataset.copiar]));
  $("#pe-salvar", m).onclick = async () => { try { await api("PATCH", `/api/admin/marketing/prospeccao/${id}`, dadosForm($("#pr-edit", m))); m.fechar(); toast("Salvo.", "ok"); aoMudar(); } catch (e) { avisarErro(e); } };
  const crm = $("#pe-crm", m);
  if (crm) crm.onclick = () => ocupado(crm, "Enviando…", async () => { try { const x = await api("POST", `/api/admin/marketing/prospeccao/${id}/crm`); toast(`Lead #${x.lead_id} criado no CRM (canal Prospecção ativa).`, "ok"); m.fechar(); aoMudar(); } catch (e) { avisarErro(e); } });
  $("#pe-reav", m).onclick = (ev) => ocupado(ev.target, "Consultando…", async () => { try { await api("POST", `/api/admin/marketing/prospeccao/${id}/reavaliar`); m.fechar(); modalProspect(id, aoMudar); aoMudar(); } catch (e) { avisarErro(e); } });
}


// ---------------------------------------------------------------- armazenamento (banco e disco no Render)
const tamanho = (b) => { if (b === null || b === undefined) return "—"; const u = ["B", "KB", "MB", "GB", "TB"]; let i = 0; b = Number(b); while (b >= 1024 && i < u.length - 1) { b /= 1024; i++; } return `${fmt.num(b, b < 10 && i ? 1 : 0)} ${u[i]}`; };

function medidor(titulo, m, legenda) {
  const pct = m.pct ?? 0, alerta = pct >= 70;
  return `<div class="medidor ${alerta ? "alerta" : ""}"><div class="bloco-titulo"><b>${esc(titulo)}</b><span>${m.pct === null || m.pct === undefined ? "—" : `${fmt.num(pct, 1)}%`}</span></div>
    <div class="medidor-trilho" role="img" aria-label="${esc(titulo)}: ${fmt.num(pct, 0)}% usado"><i style="width:${Math.min(100, pct)}%"></i><s style="left:70%" title="alerta em 70%"></s></div>
    <small class="fraco">${tamanho(m.usado)} de ${tamanho(m.limite)}${legenda ? " · " + legenda : ""}</small></div>`;
}

async function abaArmazenamento(el) {
  const d = await api("GET", "/api/admin/armazenamento");
  const b = d.banco, k = d.disco;
  const maior = Math.max(1, ...b.tabelas.map((x) => x.bytes || 0));
  el.innerHTML = `${d.alertas.map((a) => `<div class="aviso erro">${esc(a)}</div>`).join("")}
    <section class="bloco"><div class="grade grade-2">
      ${medidor("Banco de dados (PostgreSQL)", b, "limite definido em DB_LIMITE_GB")}
      ${medidor("Disco de arquivos (PDFs)", k, `${fmt.num(k.arquivos, 0)} arquivo(s), ${tamanho(k.bytes_arquivos)} do Kasiski`)}</div>
      <p class="fraco" style="margin-top:12px">Alerta a partir de 70% (aqui e por e-mail aos administradores, no máximo a cada 3 dias). Para crescer: no Render, <b>Database → Storage</b> (US$ 0,30/GB/mês)
        e <b>serviço da API → Disks</b> (US$ 0,25/GB/mês). O espaço só aumenta, não diminui. Depois de aumentar o banco, atualize a variável <code>DB_LIMITE_GB</code>.</p></section>
    <section class="bloco"><div class="bloco-titulo"><h2>Maiores tabelas do banco</h2><button class="botao pequeno secundario" id="arm-limpar">Rodar limpeza agora</button></div>
      <div class="tabela-rolagem"><table><thead><tr><th>Tabela</th><th>Tamanho</th><th></th><th>Linhas (aprox.)</th></tr></thead>
      <tbody>${b.tabelas.map((x) => `<tr><td><code>${esc(x.tabela)}</code></td><td>${tamanho(x.bytes)}</td>
        <td style="width:40%">${x.bytes !== null ? `<div class="medidor-trilho fino"><i style="width:${(100 * (x.bytes || 0)) / maior}%"></i></div>` : ""}</td><td>${fmt.num(x.linhas, 0)}</td></tr>`).join("")}</tbody></table></div>
      <p class="fraco" style="margin-top:10px">Limpeza automática (todo dia, no job do radar): itens de tabelas de preços desativadas há mais de ${d.limpeza.dias_tabela_inativa} dias
        (a tabela fica no histórico; para usar de novo, reimporte) e eventos de rastreamento com mais de ${d.limpeza.meses_eventos} meses, como diz a política de privacidade.
        ${d.tabelas_inativas.length ? `<br>Tabelas desativadas aguardando limpeza: ${d.tabelas_inativas.map((t) => `${esc(t.nome)} (${fmt.num(t.n_itens, 0)} itens)`).join(" · ")}.` : ""}</p></section>`;
  $("#arm-limpar", el).onclick = (ev) => ocupado(ev.target, "Limpando…", async () => {
    try { const r = await api("POST", "/api/admin/armazenamento/limpar"); toast(`Limpeza: ${r.itens} item(ns) de ${r.tabelas} tabela(s) e ${r.eventos} evento(s) removidos.`, "ok"); abaArmazenamento(el); } catch (e) { avisarErro(e); }
  });
}


// ---------------------------------------------------------------- planos: custo de IA, margem e transição da tabela antiga
async function abaPlanosAdmin(el) {
  const [e, tr] = await Promise.all([api("GET", "/api/admin/planos/economia"), api("GET", "/api/admin/planos/transicao")]);
  const cu = e.custo_por_uso;
  const reduzir = tr.filter((x) => x.reduzir);
  el.innerHTML = `
    <section class="bloco"><h2>Custo de IA por uso</h2>
      <div class="grade grade-4 grade-kpi">${[["analises", "análise de edital"], ["concorrentes", "análise de concorrente"], ["pecas", "peça com IA"], ["propostas", "minuta de proposta"]].map(([k, t]) =>
        indicador(fmt.moeda((cu[k]?.usd || 0) * e.usd_brl), `${t} · ${cu[k]?.real ? `média real de ${cu[k].amostra} usos (90 dias)` : "estimativa (poucos dados ainda)"}`)).join("")}</div>
      <p class="fraco" style="margin-top:10px">Câmbio US$ 1 = ${fmt.moeda(e.usd_brl)} (variável USD_BRL). Estimativas até haver 5 usos reais de cada recurso.</p></section>
    <section class="bloco"><h2>Margem de cada plano no uso máximo</h2>
      <div class="tabela-rolagem"><table><thead><tr><th>Plano</th><th>Preço</th><th>Limites (edital · concorrente · possíveis · peças)</th><th>IA no uso máximo</th><th>CMV máximo</th><th>Margem bruta mínima</th><th>Contas · IA média real/mês</th></tr></thead>
      <tbody>${e.planos.map((p) => `<tr><td><b>${esc(p.nome)}</b></td><td>${fmt.moeda(p.preco)}</td>
        <td>${[p.limites.analises, p.limites.concorrentes, p.limites.possiveis, p.limites.pecas].map((v) => v || 0).join(" · ")}</td>
        <td>${fmt.moeda(p.ia_max_brl)}</td><td>${fmt.moeda(p.cmv_max_brl)}</td>
        <td>${p.margem_uso_maximo === null ? "—" : `<b class="${p.margem_uso_maximo < 60 ? "texto-alerta" : ""}">${fmt.num(p.margem_uso_maximo, 1)}%</b>`}</td>
        <td>${p.contas} · ${p.ia_media_real_brl === null ? "—" : fmt.moeda(p.ia_media_real_brl)}</td></tr>`).join("")}</tbody></table></div>
      <p class="fraco" style="margin-top:10px">CMV = IA no uso máximo + infraestrutura (${fmt.moeda(e.infra_por_conta)}/conta) + taxa de pagamento (${fmt.num(e.taxa_pagamento * 100, 2)}%). Quase ninguém usa 100% do limite: a coluna da direita mostra o gasto real médio.
        Créditos por uso acima do limite: ${Object.entries(e.creditos).map(([k, v]) => `${k} ${v}`).join(" · ")} · pacote ${e.pacote.creditos} créditos por ${fmt.moeda(e.pacote.preco)}.</p></section>
    <section class="bloco"><div class="bloco-titulo"><h2>Assinantes da tabela antiga</h2>${reduzir.length ? `<button class="botao pequeno" id="aplicar-transicao">Reduzir ${reduzir.length} cobrança(s) para a tabela nova</button>` : ""}</div>
      <p class="fraco">Cada assinante mantém o valor que pagava e ganhou o plano novo equivalente ou superior. Quem paga acima da tabela nova (ex.: Consultor R$ 1.290 → R$ 797) tem a cobrança reduzida: o botão ajusta as assinaturas automáticas no Mercado Pago; as pagas por Pix já renovam pelo menor valor.</p>
      ${tr.length ? `<div class="tabela-rolagem"><table><thead><tr><th>Conta</th><th>Plano novo</th><th>Paga hoje</th><th>Tabela nova</th><th>Forma</th><th></th></tr></thead>
        <tbody>${tr.map((x) => `<tr><td><b>${esc(x.nome)}</b><br><small class="fraco">${esc(x.email || "")}</small></td><td>${esc(S.planos[x.plano]?.nome || x.plano)}</td>
          <td>${fmt.moeda(x.preco_contratado)}</td><td>${x.preco_tabela ? fmt.moeda(x.preco_tabela) : "—"}</td><td>${x.recorrente ? "Cartão recorrente" : esc(x.metodo || "—")}</td>
          <td>${x.reduzir ? carimbo("Reduzir", "aviso") : carimbo("Mantém valor menor", "ok")}</td></tr>`).join("")}</tbody></table></div>` : vazio("Nenhum assinante da tabela antiga", "")}</section>`;
  const b = $("#aplicar-transicao", el);
  if (b) b.onclick = async () => {
    if (!(await confirmar(`Reduzir ${reduzir.length} cobrança(s) para o preço da tabela nova? As assinaturas automáticas são alteradas no Mercado Pago a partir da próxima cobrança.`, "Reduzir cobranças"))) return;
    try { const r = await api("POST", "/api/admin/planos/transicao/aplicar"); toast(`${r.ajustados.length} ajustada(s)${r.falhas.length ? `, ${r.falhas.length} falha(s)` : ""}.`, r.falhas.length ? "erro" : "ok"); abaPlanosAdmin(el); } catch (e2) { avisarErro(e2); }
  };
}


// ------------------------------------------------------------ notas fiscais a emitir
const NF_SITUACOES = [["pendente", "A emitir"], ["emitida", "Emitidas"], ["cancelar", "Cancelar nota (estorno)"], ["nao_emitir", "Não emitir"], ["todas", "Todas"]];
const NF_ROTULO = { pendente: ["A emitir", "aviso"], emitida: ["Emitida", "ok"], cancelar: ["Cancelar nota", "erro"], nao_emitir: ["Não emitir", "neutro"], cancelada: ["Nota cancelada", "neutro"] };

async function abaFaturamento(el) {
  const f = abaFaturamento.f || (abaFaturamento.f = { situacao: "pendente", de: "", ate: "" });
  const qs = new URLSearchParams({ situacao: f.situacao, ...(f.de ? { de: f.de } : {}), ...(f.ate ? { ate: f.ate } : {}) }).toString();
  const r = await api("GET", `/api/admin/faturamento?${qs}`);
  const pr = r.prestador || {};
  const faltaPrest = [!pr.inscricao_municipal && "inscrição municipal (NFSE_PRESTADOR_IM)", !pr.codigo_servico && "código do serviço (NFSE_CODIGO_SERVICO)"].filter(Boolean);
  el.innerHTML = `
    <div class="aviso info"><b>Prestador:</b> ${esc(pr.razao_social || "")} · CNPJ ${esc(pr.cnpj || "")} · ${esc(pr.municipio || "")}
      ${pr.inscricao_municipal ? ` · IM ${esc(pr.inscricao_municipal)}` : ""}${pr.codigo_servico ? ` · Serviço ${esc(pr.codigo_servico)}` : ""}
      ${faltaPrest.length ? `<br><small>Falta configurar no Render (defina com o contador): ${faltaPrest.join(" e ")}.</small>` : ""}</div>
    <div class="chips" role="group" aria-label="Situação da nota">${NF_SITUACOES.map(([k, t]) =>
      `<button data-nf-sit="${k}" aria-pressed="${f.situacao === k}">${t}${r.resumo?.[k] ? ` (${r.resumo[k]})` : ""}</button>`).join("")}</div>
    <div class="linha-campos" style="max-width:640px;margin-top:12px">
      <div class="campo"><label for="nf-de">Pago de</label><input type="date" id="nf-de" value="${esc(f.de)}"></div>
      <div class="campo"><label for="nf-ate">até</label><input type="date" id="nf-ate" value="${esc(f.ate)}"></div>
      <div class="campo" style="align-self:end"><button class="botao secundario" id="nf-csv">${icone("baixar")} Baixar planilha (CSV)</button></div>
    </div>
    <section class="bloco tabela-rolagem">
      ${r.itens.length ? `<p class="fraco">${r.itens.length} pagamento(s) · total ${fmt.moeda(r.total)}</p>
      <table class="tabela-faixas tabela-nf"><thead><tr><th>Pago em</th><th>Tomador</th><th>Endereço</th><th>Valor</th><th>Discriminação</th><th>Nota</th><th></th></tr></thead>
      <tbody>${r.itens.map(linhaNf).join("")}</tbody></table>` : vazio("Nada por aqui", f.situacao === "pendente" ? "Todos os pagamentos aprovados já têm nota ou foram marcados como não emitir." : "")}
    </section>`;
  $$("[data-nf-sit]", el).forEach((b) => b.onclick = () => { f.situacao = b.dataset.nfSit; abaFaturamento(el); });
  $("#nf-de", el).onchange = (ev) => { f.de = ev.target.value; abaFaturamento(el); };
  $("#nf-ate", el).onchange = (ev) => { f.ate = ev.target.value; abaFaturamento(el); };
  $("#nf-csv", el).onclick = (ev) => ocupado(ev.currentTarget, "Gerando…", async () => {
    try {
      const resp = await api("GET", `/api/admin/faturamento.csv?${qs}`);
      const url = URL.createObjectURL(await resp.blob());
      const a = document.createElement("a"); a.href = url; a.download = `kasiski-notas-${f.situacao}.csv`; a.click();
      setTimeout(() => URL.revokeObjectURL(url), 2000);
    } catch (e) { avisarErro(e); }
  });
  $$("[data-nf-copiar]", el).forEach((b) => b.onclick = async () => {
    const it = r.itens.find((x) => String(x.id) === b.dataset.nfCopiar);
    const t = it.tomador || {};
    const texto = [`${t.nome || ""} — ${t.documento_formatado || ""}`, t.email, `${t.logradouro || ""}, ${t.numero || ""}${t.complemento ? " " + t.complemento : ""} — ${t.bairro || ""}`,
      `${t.municipio || ""}/${t.uf || ""} — CEP ${t.cep || ""}`, `Valor: ${fmt.moeda(it.valor)}`, it.discriminacao].filter(Boolean).join("\n");
    try { await navigator.clipboard.writeText(texto); toast("Dados copiados.", "ok"); } catch (e) { toast("Não foi possível copiar.", "erro"); }
  });
  $$("[data-nf-emitida]", el).forEach((b) => b.onclick = () => {
    const m = modal({ titulo: "Registrar nota emitida", corpo: `<form id="form-nf"><div class="campo"><label for="nf-numero">Número da NFS-e</label><input id="nf-numero" name="nf_numero" required></div>
      <div class="campo"><label for="nf-obs">Observação <small class="fraco">(opcional)</small></label><input id="nf-obs" name="nf_obs" maxlength="300"></div>
      <button class="botao" type="submit">Salvar</button></form>` });
    $("#form-nf", m).onsubmit = async (ev) => {
      ev.preventDefault();
      try { await api("PATCH", `/api/admin/faturamento/${b.dataset.nfEmitida}`, { nf_status: "emitida", ...dadosForm(ev.target) }); m.fechar(); toast("Nota registrada.", "ok"); abaFaturamento(el); }
      catch (e2) { avisarErro(e2); }
    };
  });
  $$("[data-nf-acao]", el).forEach((b) => b.onclick = async () => {
    const [id, st] = b.dataset.nfAcao.split(":");
    if (st === "nao_emitir" && !(await confirmar("Marcar este pagamento como 'não emitir nota'?", "Marcar"))) return;
    try { await api("PATCH", `/api/admin/faturamento/${id}`, { nf_status: st }); abaFaturamento(el); } catch (e) { avisarErro(e); }
  });
}

function linhaNf(it) {
  const t = it.tomador || {};
  const [rot, tom] = NF_ROTULO[it.nf_status] || [it.nf_status, "neutro"];
  const acoes = it.nf_status === "pendente"
    ? `<button class="botao pequeno" data-nf-emitida="${it.id}">Nota emitida</button><button class="botao texto pequeno" data-nf-acao="${it.id}:nao_emitir">Não emitir</button>`
    : it.nf_status === "cancelar" ? `<button class="botao pequeno" data-nf-acao="${it.id}:cancelada">Nota cancelada</button>`
    : `<button class="botao texto pequeno" data-nf-acao="${it.id}:pendente">Voltar a pendente</button>`;
  return `<tr class="faixa-${it.nf_status === "emitida" ? "ganho" : it.nf_status === "cancelar" ? "perdido" : it.nf_status === "pendente" ? "acompanhando" : "descartado"}">
    <td>${fmt.data(it.pago_em)}<br><small class="fraco">${esc(it.meio || "")}</small></td>
    <td>${it.tomador_completo ? `<b>${esc(t.nome)}</b><br><small>${esc(t.documento_formatado || "")}</small><br><small class="fraco">${esc(t.email || "")}</small>`
      : `${carimbo("Sem dados fiscais", "erro")}<br><small>${esc(it.conta || "—")}</small>`}</td>
    <td style="max-width:220px"><small>${t.logradouro ? `${esc(t.logradouro)}, ${esc(t.numero || "")}${t.complemento ? " " + esc(t.complemento) : ""} — ${esc(t.bairro || "")}<br>${esc(t.municipio || "")}/${esc(t.uf || "")} · CEP ${esc(t.cep || "")}` : "—"}</small></td>
    <td><b>${fmt.moeda(it.valor)}</b></td>
    <td style="max-width:300px"><small>${esc(it.discriminacao)}</small></td>
    <td>${carimbo(rot, tom)}${it.nf_numero ? `<br><small>Nº ${esc(it.nf_numero)}</small>` : ""}${it.nf_obs ? `<br><small class="fraco">${esc(it.nf_obs)}</small>` : ""}</td>
    <td class="acoes-celula" style="flex-direction:column;align-items:flex-start;gap:4px"><button class="botao texto pequeno" data-nf-copiar="${it.id}">Copiar dados</button>${acoes}</td></tr>`;
}
