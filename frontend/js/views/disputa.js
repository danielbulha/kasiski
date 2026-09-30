// Sala de disputa: vários pregões ao mesmo tempo, cada item com a sua estratégia de lances.
// O Kasiski calcula o próximo lance, respeita o piso e conta os intervalos; o lance é dado por você no portal.
const SITUACAO_DISPUTA = {
  aguardando: ["Aguardando lances", "neutro"], cobrir: ["Você foi superado", "aviso"], lider: ["Você lidera", "ok"],
  no_piso: ["Último lance: piso", "aviso"], parar: ["Piso atingido: pare", "erro"],
};
const RESULTADO_DISPUTA = { vencedor: "Melhor lance (vencedor)", classificado: "Classificado", perdeu: "Não venceu", desistiu: "Desistiu" };

const valorBR = (t) => { // "93.400,50" | "93400.5" | "93400" -> 93400.5
  const s = String(t ?? "").trim().replace(/[R$\s]/g, "");
  if (!s) return null;
  const n = s.includes(",") ? Number(s.replace(/\./g, "").replace(",", ".")) : Number(s);
  return Number.isFinite(n) ? n : null;
};
const fmtLance = (v, criterio) => (v === null || v === undefined ? "—" : criterio === "maior_desconto" ? `${fmt.num(v, 2)}%` : fmt.moeda(v));

V.disputa = async (el) => {
  if (!S.empresaId) { el.innerHTML = exigirEmpresa(); return; }
  if (S.plano && !S.plano.disputa) {
    el.innerHTML = `<div class="cabecalho"><div><h1>Sala de disputa</h1><p>Dispute vários pregões ao mesmo tempo, com estratégia por item e o próximo lance calculado na hora.</p></div></div>
      <section class="bloco">${vazio("Disponível a partir do plano Profissional", "Estratégia de lances por item, piso a partir da proposta comercial, intervalos entre lances controlados e vários pregões na mesma tela.", `<a class="botao" href="#/conta">Ver planos</a>`)}</section>`;
    return;
  }
  const [d, cfg] = await Promise.all([api("GET", `/api/empresas/${S.empresaId}/disputas`), V.disputa.cfg || api("GET", "/api/disputa/config")]);
  V.disputa.cfg = cfg;
  V.disputa.lista = d.disputas;
  V.disputa.buscadoEm = Date.now();
  const som = localStorage.getItem("kasiski_disputa_som") === "1";
  el.innerHTML = `
    <div class="cabecalho"><div><h1>Sala de disputa</h1><p>Dispute vários pregões ao mesmo tempo, com estratégia por item e o próximo lance calculado na hora.</p></div>
      <div class="acoes"><label class="check"><input type="checkbox" id="ds-som" ${som ? "checked" : ""}> Aviso sonoro</label>
        <button class="botao" id="ds-nova">${icone("adicionar")} Nova sala</button></div></div>
    <div class="aviso info ds-aviso"><b>Você dá o lance; o Kasiski faz as contas.</b> Registre aqui o melhor lance que aparecer no portal: o sistema calcula o próximo pela sua estratégia,
      não deixa passar do piso e avisa quando o intervalo entre lances libera. Os lances não são enviados ao portal automaticamente. Confira no edital o modo de disputa e o intervalo mínimo entre lances.</div>
    ${d.proximas.length ? `<section class="ds-proximas" aria-label="Próximas sessões"><b>Próximas sessões</b>${d.proximas.map((p) => `
      <div class="ds-prox"><span><b>${esc(p.numero || p.objeto?.slice(0, 40) || "Licitação")}</b><small>${esc(p.orgao || "")}</small></span>
        <span class="ds-cont" data-ate="${esc(p.data_abertura)}">${fmt.dataHora(p.data_abertura)}</span>
        ${p.tem_sala ? `<span class="fraco">sala pronta</span>` : `<button class="botao pequeno secundario" data-preparar="${p.id}">Preparar sala</button>`}</div>`).join("")}</section>` : ""}
    <section class="ds-grade" id="ds-grade">${d.disputas.length ? d.disputas.map(cartaoDisputa).join("")
      : vazio("Nenhuma sala aberta", "Abra uma sala para cada item ou lote que vai disputar. Você pode acompanhar vários pregões ao mesmo tempo.", `<button class="botao" data-nova-vazia>Abrir a primeira sala</button>`)}</section>
    <p class="fraco ds-rodape">Regras gerais (Lei 14.133 e IN SEGES/ME 73/2022): no modo aberto, lances por 10 minutos com prorrogação de 2 minutos a cada lance nos 2 minutos finais;
      no aberto e fechado, 15 minutos, encerramento aleatório em até 10 minutos e lance final fechado para quem estiver até 10% do melhor. O edital sempre prevalece.</p>`;
  $("#ds-som", el).onchange = (ev) => { try { localStorage.setItem("kasiski_disputa_som", ev.target.checked ? "1" : "0"); } catch { /* ok */ } if (ev.target.checked) bipDisputa(); };
  $("#ds-nova", el).onclick = () => modalNovaDisputa(el);
  const nv = $("[data-nova-vazia]", el); if (nv) nv.onclick = () => modalNovaDisputa(el);
  $$("[data-preparar]", el).forEach((b) => b.onclick = () => modalNovaDisputa(el, Number(b.dataset.preparar)));
  ligarCartoesDisputa(el);
  const prep = sessionStorage.getItem("ds_preparar");
  if (prep) { sessionStorage.removeItem("ds_preparar"); modalNovaDisputa(el, Number(prep)); }
  clearInterval(V.disputa.relogio);
  V.disputa.relogio = setInterval(() => { if (!document.body.contains(el)) { clearInterval(V.disputa.relogio); return; } tickDisputa(el); }, 1000);
  tickDisputa(el);
};

function cartaoDisputa(x) {
  const s = x.sugestao || {}, crit = x.criterio;
  const [rot, tipo] = SITUACAO_DISPUTA[s.situacao] || SITUACAO_DISPUTA.aguardando;
  const ed = x.edital;
  const titulo = ed ? (ed.numero || ed.objeto || "Licitação") : "Disputa avulsa";
  const encerrada = x.status === "encerrada";
  const margem = s.margem_pct;
  const barra = margem === null || margem === undefined ? "" : `<div class="ds-margem" title="Folga em relação ao piso"><i style="width:${Math.max(3, Math.min(100, crit === "maior_desconto" ? 100 - margem * 10 : margem * 10))}%"></i></div>
    <small class="fraco">${crit === "maior_desconto" ? `Folga até o desconto máximo: ${fmt.num(margem, 2)} p.p.` : `Folga sobre o piso: ${fmt.num(margem, 2)}%`}${s.lances_ate_piso !== null && s.lances_ate_piso !== undefined ? ` · cerca de ${s.lances_ate_piso} lance(s) até o piso` : ""}</small>`;
  return `<article class="ds-cartao ds-${esc(s.situacao || "aguardando")}${encerrada ? " encerrada" : ""}" data-disputa="${x.id}" aria-label="Disputa ${esc(titulo)} item ${esc(x.item || "")}">
    <header><div><b>${esc(titulo)}</b> · item ${esc(x.item || "—")}<small>${esc(ed?.orgao || "")}${x.descricao ? ` · ${esc(x.descricao.slice(0, 90))}` : ""}</small></div>
      ${encerrada ? carimbo(RESULTADO_DISPUTA[x.resultado] || "Encerrada", x.resultado === "vencedor" ? "ok" : "neutro") : carimbo(rot, tipo)}</header>
    <div class="ds-chips"><span>${esc(x.portal_nome)}</span><span>${esc(V.disputa.cfg?.modos?.[x.modo]?.nome || x.modo)}</span><span>${esc(V.disputa.cfg?.estrategias?.[x.estrategia]?.nome || x.estrategia)}</span>${crit === "maior_desconto" ? "<span>Maior desconto</span>" : ""}</div>
    <div class="ds-numeros"><div><small>Melhor do portal</small><b>${fmtLance(x.melhor_lance, crit)}</b></div>
      <div><small>Meu último</small><b>${fmtLance(x.meu_ultimo, crit)}</b></div>
      <div><small>${crit === "maior_desconto" ? "Desconto máximo" : "Piso"}</small><b>${fmtLance(x.preco_piso, crit)}</b></div></div>
    ${encerrada ? "" : `<div class="ds-proximo">
      <div><small>${esc(s.mensagem || "")}</small>${s.proximo !== null && s.proximo !== undefined ? `<strong>${fmtLance(s.proximo, crit)}</strong>` : ""}</div>
      ${s.proximo !== null && s.proximo !== undefined ? `<div class="ds-prox-acoes"><span class="ds-espera" data-espera="${s.espera_s || 0}" aria-live="polite"></span>
        <button class="botao pequeno secundario" data-copiar-lance="${s.proximo}">Copiar</button>
        <button class="botao pequeno" data-dei="${s.proximo}">Dei este lance</button></div>` : ""}</div>
    ${barra}
    ${resumoAnaliseLances(x)}
    <form class="ds-registro" data-registro="${x.id}"><label class="oculto-visual" for="ds-v-${x.id}">Valor do lance</label>
      <input id="ds-v-${x.id}" inputmode="decimal" placeholder="${crit === "maior_desconto" ? "Ex.: 12,5" : "Ex.: 93.400,00"}" autocomplete="off">
      <button type="submit" class="botao pequeno secundario" data-tipo="mercado" title="Um concorrente deu este lance no portal">Melhor do portal</button>
      <button type="submit" class="botao pequeno secundario" data-tipo="meu" title="Você deu este lance no portal">Dei este lance</button></form>`}
    <footer>${x.portal_url && !encerrada ? `<a href="${esc(x.portal_url)}" target="_blank" rel="noopener">Abrir o portal</a>` : ""}
      ${ed ? `<a href="#/oportunidades/${ed.id}">Oportunidade</a>` : ""}
      <button class="botao texto pequeno" data-analise-ds="${x.id}">${dcSimbolo(12)} Análise de lances</button>
      <button class="botao texto pequeno" data-estrategia="${x.id}">Estratégia</button>
      ${!encerrada ? `<button class="botao texto pequeno" data-encerrar="${x.id}">Encerrar</button>` : ""}
      <button class="botao texto pequeno" data-excluir-ds="${x.id}">${icone("excluir", 13)}</button></footer>
    ${(x.lances || []).length ? `<details class="ds-hist"><summary>Histórico (${x.lances.length})</summary><ol>${x.lances.slice().reverse().slice(0, 20).map((l) => `<li><span>${new Date(l.em + "Z").toLocaleTimeString("pt-BR")}</span>
      <b>${fmtLance(l.valor, crit)}</b> ${l.tipo === "meu" ? "meu lance" : "melhor do portal"}</li>`).join("")}</ol>
      ${!encerrada ? `<button class="botao texto pequeno" data-desfazer="${x.id}">Desfazer o último registro</button>` : ""}</details>` : ""}
  </article>`;
}

function ligarCartoesDisputa(el) {
  const atualizar = (x) => {
    const i = V.disputa.lista.findIndex((y) => y.id === x.id);
    x.edital = V.disputa.lista[i]?.edital;
    V.disputa.lista[i] = x;
    const c = $(`[data-disputa="${x.id}"]`, el);
    c.outerHTML = cartaoDisputa(x);
    ligarCartoesDisputa(el);
    const novo = $(`[data-disputa="${x.id}"]`, el);
    if (novo) { novo.dataset.recebido = Date.now(); tickDisputa(el); }
  };
  const registrar = async (id, valor, tipo, confirmar = false) => {
    try { atualizar(await api("POST", `/api/disputas/${id}/lance`, { valor, tipo, confirmar_abaixo_piso: confirmar })); }
    catch (e) {
      if (e.codigo === "abaixo_piso" && (await confirmar_(e.message))) return registrar(id, valor, tipo, true);
      if (e.codigo !== "abaixo_piso") avisarErro(e);
    }
  };
  const confirmar_ = (msg) => confirmar(msg, "Registrar mesmo assim");
  $$("[data-registro]", el).forEach((f) => {
    if (f.dataset.ligado) return; f.dataset.ligado = "1";
    f.onsubmit = (ev) => {
      ev.preventDefault();
      const tipo = ev.submitter?.dataset.tipo || "mercado";
      const v = valorBR($("input", f).value);
      if (v === null) { toast("Digite o valor do lance.", "erro"); $("input", f).focus(); return; }
      registrar(Number(f.dataset.registro), v, tipo);
    };
  });
  $$("[data-dei]", el).forEach((b) => b.onclick = () => registrar(Number(b.closest("[data-disputa]").dataset.disputa), Number(b.dataset.dei), "meu"));
  $$("[data-copiar-lance]", el).forEach((b) => b.onclick = () => {
    const x = V.disputa.lista.find((y) => y.id === Number(b.closest("[data-disputa]").dataset.disputa));
    const v = Number(b.dataset.copiarLance);
    copiar(x?.criterio === "maior_desconto" ? v.toFixed(2).replace(".", ",") : v.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }));
  });
  $$("[data-desfazer]", el).forEach((b) => b.onclick = async () => { try { atualizar(await api("POST", `/api/disputas/${b.dataset.desfazer}/desfazer`)); } catch (e) { avisarErro(e); } });
  $$("[data-analise-ds]", el).forEach((b) => b.onclick = () => modalAnaliseLances(Number(b.dataset.analiseDs), el));
  $$("[data-estrategia]", el).forEach((b) => b.onclick = () => modalEstrategia(V.disputa.lista.find((y) => y.id === Number(b.dataset.estrategia)), el));
  $$("[data-encerrar]", el).forEach((b) => b.onclick = () => modalEncerrarDisputa(Number(b.dataset.encerrar), el));
  $$("[data-excluir-ds]", el).forEach((b) => b.onclick = () => excluirParaLixeira({ url: `/api/disputas/${b.dataset.excluirDs}`, nome: "esta sala de disputa", tipo: "disputa", depois: () => V.disputa(el) }));
}

// Relógio: intervalo entre lances e contagem regressiva das sessões
function tickDisputa(el) {
  const agora = Date.now();
  $$(".ds-espera", el).forEach((s) => {
    const card = s.closest("[data-disputa]");
    const base = Number(card.dataset.recebido || V.disputa.buscadoEm);
    const resta = Math.max(0, Math.ceil(Number(s.dataset.espera) - (agora - base) / 1000));
    const liberou = resta === 0;
    s.textContent = liberou ? "Liberado para lançar" : `Aguarde ${resta}s`;
    s.classList.toggle("liberado", liberou);
    card.querySelectorAll("[data-dei]").forEach((b) => { b.disabled = !liberou; });
    if (liberou && !card.dataset.avisou && card.classList.contains("ds-cobrir")) {
      card.dataset.avisou = "1";
      if (localStorage.getItem("kasiski_disputa_som") === "1") bipDisputa();
    }
  });
  $$(".ds-cont", el).forEach((c) => {
    const ms = new Date(c.dataset.ate) - agora;
    if (ms <= 0) { c.textContent = "Sessão aberta"; c.classList.add("agora"); return; }
    const h = Math.floor(ms / 36e5), m = Math.floor((ms % 36e5) / 6e4), s = Math.floor((ms % 6e4) / 1000);
    c.textContent = h >= 48 ? `em ${Math.floor(h / 24)} dias` : `em ${h ? `${h}h ` : ""}${String(m).padStart(2, "0")}min${h ? "" : ` ${String(s).padStart(2, "0")}s`}`;
  });
}

function bipDisputa() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const o = ctx.createOscillator(), g = ctx.createGain();
    o.frequency.value = 880; g.gain.value = 0.08; o.connect(g); g.connect(ctx.destination);
    o.start(); o.stop(ctx.currentTime + 0.18);
  } catch { /* navegador sem áudio */ }
}

async function modalNovaDisputa(el, edId = null) {
  let ops;
  try { ops = await api("GET", `/api/empresas/${S.empresaId}/oportunidades`); } catch (e) { avisarErro(e); return; }
  const cfg = V.disputa.cfg;
  const elegiveis = ops.cartoes.filter((c) => ["decisao", "preparacao", "pronta", "em_disputa", "classificada"].includes(c.etapa) || c.id === edId);
  const m = modal({ titulo: "Nova sala de disputa", largo: true, corpo: `<form id="form-ds">
    <div class="campo"><label for="ds-ed">Licitação</label><select id="ds-ed" name="edital_id" required>
      <option value="">Escolha uma oportunidade</option>
      ${elegiveis.map((c) => `<option value="${c.id}" ${c.id === edId ? "selected" : ""}>${esc(tituloCartao(c))} · ${esc(c.orgao || "")} · ${esc(sessaoCurta(c.data_abertura))}</option>`).join("")}</select>
      <small>Aparecem as oportunidades em decisão, preparação, prontas ou em disputa. Não achou? Mova o cartão em <a href="#/oportunidades">Oportunidades</a>.</small></div>
    <div class="linha-campos">
      <div class="campo"><label for="ds-portal">Portal</label><select id="ds-portal" name="portal"><option value="">Detectar pelo edital</option>${Object.entries(cfg.portais).map(([k, p]) => `<option value="${k}">${esc(p.nome)}</option>`).join("")}</select></div>
      <div class="campo"><label for="ds-modo">Modo de disputa</label><select id="ds-modo" name="modo">${Object.entries(cfg.modos).map(([k, p]) => `<option value="${k}">${esc(p.nome)}</option>`).join("")}</select></div>
      <div class="campo"><label for="ds-crit">Critério</label><select id="ds-crit" name="criterio"><option value="menor_preco">Menor preço</option><option value="maior_desconto">Maior desconto</option></select></div></div>
    <div class="campo"><label>Itens</label>
      <label class="check"><input type="radio" name="escopo" value="global" checked> Valor global (uma sala)</label>
      <label class="check"><input type="radio" name="escopo" value="itens"> Por item ou lote</label>
      <div id="ds-itens" hidden></div></div>
    <div id="erro-ds"></div><button class="botao" type="submit" style="width:100%">Abrir a sala</button></form>` });
  const box = $("#ds-itens", m);
  const carregarItens = async () => {
    const id = $("#ds-ed", m).value;
    if (!id) { box.innerHTML = `<p class="fraco">Escolha a licitação primeiro.</p>`; return; }
    box.innerHTML = `<p class="carregando">Buscando os itens no PNCP…</p>`;
    const r = await api("GET", `/api/oportunidades/${id}/itens`).catch(() => ({ itens: [] }));
    box.innerHTML = r.itens?.length ? `<div class="ds-itens-lista">${r.itens.slice(0, 50).map((i) => `<label class="check"><input type="checkbox" class="ds-item" value="${esc(i.numero)}" data-desc="${esc(i.descricao || "")}" data-ref="${i.valor_total ?? ""}" checked>
      Item ${esc(i.numero)} · ${esc((i.descricao || "").slice(0, 90))} · ${fmt.moeda(i.valor_total)}</label>`).join("")}</div>`
      : `<p class="fraco">${esc(r.aviso || "Não encontrei os itens no PNCP.")} Informe o item:</p><div class="linha-campos"><div class="campo"><label for="ds-item-n">Item/lote</label><input id="ds-item-n" value="1"></div>
        <div class="campo"><label for="ds-item-d">Descrição</label><input id="ds-item-d"></div></div>`;
  };
  $$("[name=escopo]", m).forEach((r) => r.onchange = () => {
    const porItem = $("[name=escopo]:checked", m).value === "itens";
    box.hidden = !porItem;
    if (porItem) carregarItens();
  });
  $("#ds-ed", m).onchange = () => { if (!box.hidden) carregarItens(); };
  $("#form-ds", m).onsubmit = async (ev) => {
    ev.preventDefault();
    const f = dadosForm(ev.target);
    if (!f.edital_id) { $("#erro-ds", m).innerHTML = `<div class="aviso erro">Escolha a licitação.</div>`; return; }
    const corpo = { edital_id: Number(f.edital_id), modo: f.modo, criterio: f.criterio };
    if (f.portal) corpo.portal = f.portal;
    if ($("[name=escopo]:checked", m).value === "itens") {
      const marcados = $$(".ds-item:checked", m);
      corpo.itens = marcados.length ? marcados.map((c) => ({ item: c.value, descricao: c.dataset.desc, valor_referencia: c.dataset.ref ? Number(c.dataset.ref) : null }))
        : [{ item: $("#ds-item-n", m)?.value || "1", descricao: $("#ds-item-d", m)?.value || "" }];
    }
    await ocupado(ev.target.querySelector("[type=submit]"), "Abrindo…", async () => {
      try {
        const r = await api("POST", `/api/empresas/${S.empresaId}/disputas`, corpo);
        m.fechar();
        await V.disputa(el);
        const primeira = V.disputa.lista.find((y) => y.id === r.disputas[0].id);
        toast(r.disputas.length > 1 ? `${r.disputas.length} salas abertas. Defina o piso de cada item.` : "Sala aberta. Confira a estratégia e o piso.", "ok");
        if (primeira) modalEstrategia(primeira, el, r.proposta);
      } catch (e) { $("#erro-ds", m).innerHTML = erroTela(e); }
    });
  };
}

function modalEstrategia(x, el, proposta = null) {
  const cfg = V.disputa.cfg, desc = x.criterio === "maior_desconto";
  const m = modal({ titulo: `Estratégia · item ${x.item || ""}`, largo: true, corpo: `<form id="form-est">
    <fieldset class="campo ds-estrategias"><legend>Estratégia de lances</legend>${Object.entries(cfg.estrategias).map(([k, e]) => `
      <label class="ds-est"><input type="radio" name="estrategia" value="${k}" ${x.estrategia === k ? "checked" : ""}><span><b>${esc(e.nome)}${e.decremento ? ` · ${fmt.num(e.decremento, 2)}${desc ? " p.p." : "%"} por lance` : ""}</b><small>${esc(e.descricao)}</small></span></label>`).join("")}</fieldset>
    <div class="linha-campos" id="est-pers" ${x.estrategia === "personalizada" ? "" : "hidden"}>
      <div class="campo"><label for="est-dtipo">Decremento em</label><select id="est-dtipo" name="decremento_tipo"><option value="percentual" ${x.decremento_tipo !== "valor" ? "selected" : ""}>${desc ? "Pontos percentuais" : "Percentual (%)"}</option><option value="valor" ${x.decremento_tipo === "valor" ? "selected" : ""}>${desc ? "Pontos fixos" : "Valor fixo (R$)"}</option></select></div>
      <div class="campo"><label for="est-dec">Decremento por lance</label><input id="est-dec" name="decremento" inputmode="decimal" value="${x.decremento ?? ""}"></div></div>
    <div class="linha-campos">
      <div class="campo"><label for="est-ini">${desc ? "Desconto da proposta (%)" : "Lance inicial / proposta (R$)"}</label><input id="est-ini" name="lance_inicial" inputmode="decimal" value="${x.lance_inicial ?? ""}"></div>
      <div class="campo"><label for="est-piso">${desc ? "Desconto máximo que aceita (%)" : "Piso: menor valor que aceita (R$)"}</label><input id="est-piso" name="preco_piso" inputmode="decimal" value="${x.preco_piso ?? ""}" required>
        <small>${proposta?.piso ? `Pela sua proposta comercial, o ponto de equilíbrio é ${fmt.moeda(proposta.piso)} (custo ${fmt.moeda(proposta.custo)} + tributos). Abaixo disso, prejuízo.` : "Abaixo deste valor o Kasiski manda parar. Use o custo da proposta com a margem mínima que aceita."}</small></div>
      <div class="campo"><label for="est-ref">${desc ? "Referência" : "Valor estimado do item (R$)"}</label><input id="est-ref" name="valor_referencia" inputmode="decimal" value="${x.valor_referencia ?? ""}"></div></div>
    <div class="linha-campos">
      <div class="campo"><label for="est-dif">Diferença mínima entre lances (edital)</label><input id="est-dif" name="diferenca_minima" inputmode="decimal" value="${x.diferenca_minima ?? ""}" placeholder="${desc ? "Ex.: 0,5" : "Ex.: 50,00"}"></div>
      <div class="campo"><label for="est-i1">Intervalo entre os seus lances (s)</label><input id="est-i1" name="intervalo_proprio_s" type="number" min="0" max="600" value="${x.intervalo_proprio_s ?? 20}"></div>
      <div class="campo"><label for="est-i2">Intervalo após o último lance (s)</label><input id="est-i2" name="intervalo_outros_s" type="number" min="0" max="600" value="${x.intervalo_outros_s ?? 3}"></div></div>
    <div class="linha-campos">
      <div class="campo"><label for="est-portal">Portal</label><select id="est-portal" name="portal">${Object.entries(cfg.portais).map(([k, p]) => `<option value="${k}" ${x.portal === k ? "selected" : ""}>${esc(p.nome)}</option>`).join("")}</select></div>
      <div class="campo"><label for="est-modo">Modo</label><select id="est-modo" name="modo">${Object.entries(cfg.modos).map(([k, p]) => `<option value="${k}" ${x.modo === k ? "selected" : ""}>${esc(p.nome)}</option>`).join("")}</select>
        <small id="est-modo-regra">${esc(cfg.modos[x.modo]?.regra || "")}</small></div></div>
    <div class="campo"><label for="est-notas">Anotações</label><textarea id="est-notas" name="notas" rows="2">${esc(x.notas || "")}</textarea></div>
    <div id="erro-est"></div><button class="botao" type="submit" style="width:100%">Salvar estratégia</button></form>` });
  $$("[name=estrategia]", m).forEach((r) => r.onchange = () => { $("#est-pers", m).hidden = $("[name=estrategia]:checked", m).value !== "personalizada"; });
  $("#est-modo", m).onchange = (ev) => { $("#est-modo-regra", m).textContent = cfg.modos[ev.target.value]?.regra || ""; };
  $("#form-est", m).onsubmit = async (ev) => {
    ev.preventDefault();
    const f = dadosForm(ev.target);
    ["lance_inicial", "preco_piso", "valor_referencia", "decremento", "diferenca_minima"].forEach((k) => { f[k] = valorBR(f[k]); });
    if (f.preco_piso === null) { $("#erro-est", m).innerHTML = `<div class="aviso erro">Defina o piso: é ele que impede um lance que dá prejuízo.</div>`; return; }
    try { await api("PATCH", `/api/disputas/${x.id}`, f); m.fechar(); toast("Estratégia salva.", "ok"); V.disputa(el); }
    catch (e) { $("#erro-est", m).innerHTML = erroTela(e); }
  };
}

function modalEncerrarDisputa(id, el) {
  const m = modal({ titulo: "Encerrar a disputa", corpo: `<form id="form-enc">
    <div class="campo"><label for="enc-res">Resultado</label><select id="enc-res" name="resultado">${Object.entries(RESULTADO_DISPUTA).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("")}</select></div>
    <div class="campo"><label for="enc-pos">Posição final</label><input id="enc-pos" name="posicao" type="number" min="1" max="99"></div>
    <p class="fraco">Com "Melhor lance", o cartão avança para Classificada / Habilitação em Oportunidades. Lembre-se de enviar a proposta ajustada e os documentos no prazo do edital.</p>
    <button class="botao" type="submit" style="width:100%">Encerrar</button></form>` });
  $("#form-enc", m).onsubmit = async (ev) => {
    ev.preventDefault();
    try { await api("PATCH", `/api/disputas/${id}`, { ...dadosForm(ev.target), status: "encerrada" }); m.fechar(); toast("Disputa encerrada.", "ok"); V.disputa(el); }
    catch (e) { avisarErro(e); }
  };
}

// ---------------------------------------------------------------- análise de lances com IA + DoubleCheck
function resumoAnaliseLances(x) {
  const a = x.analise;
  if (!a || x.status === "encerrada") return "";
  if (a.status === "processando") return `<div class="ds-ia"><small class="carregando">${esc(a.etapa || "Analisando o histórico de preços…")}</small></div>`;
  if (a.status !== "concluida" || !a.calculo?.suficiente) return "";
  const c = a.calculo, crit = x.criterio;
  return `<div class="ds-ia">${dcSimbolo(13)}<span>IA sugere <b>${fmtLance(c.proposta_inicial, crit)}</b> de proposta e alvo de <b>${fmtLance(c.alvo_fechamento, crit)}</b>
    · estratégia ${esc(V.disputa.cfg?.estrategias?.[a.ia?.estrategia || c.estrategia]?.nome || c.estrategia || "")}</span>
    <button class="botao texto pequeno" data-analise-ds="${x.id}">Ver análise</button></div>`;
}

async function modalAnaliseLances(id, el) {
  let x = V.disputa.lista.find((y) => y.id === id);
  const m = modal({ titulo: "Análise de lances · DoubleCheck™", largo: true, corpo: `<div id="al-corpo"></div>` });
  const corpo = $("#al-corpo", m);
  const desenhar = () => { corpo.innerHTML = htmlAnaliseLances(x); ligar(); };
  const acompanhar = async () => {
    for (let i = 0; i < 80 && document.body.contains(corpo); i++) {
      await new Promise((ok) => setTimeout(ok, 3000));
      try { x = { ...x, ...(await api("GET", `/api/disputas/${id}`)) }; } catch { continue; }
      if (x.analise?.status !== "processando") break;
      desenhar();
    }
    if (document.body.contains(corpo)) desenhar();
    const i = V.disputa.lista.findIndex((y) => y.id === id); if (i >= 0) V.disputa.lista[i] = { ...V.disputa.lista[i], analise: x.analise };
  };
  const iniciar = async () => {
    try { x = { ...x, ...(await api("POST", `/api/disputas/${id}/analise`)) }; desenhar(); acompanhar(); }
    catch (e) { corpo.innerHTML = erroTela(e); }
  };
  function ligar() {
    const b = $("[data-al-rodar]", corpo); if (b) b.onclick = iniciar;
    $$("[data-al-aplicar]", corpo).forEach((bt) => bt.onclick = async () => {
      const c = x.analise.calculo;
      const corpoPatch = bt.dataset.alAplicar === "proposta" ? { lance_inicial: c.proposta_inicial }
        : { estrategia: x.analise.ia?.estrategia || c.estrategia };
      try { await api("PATCH", `/api/disputas/${id}`, corpoPatch); toast("Aplicado à estratégia da sala.", "ok"); V.disputa(el); }
      catch (e) { avisarErro(e); }
    });
  }
  if (!x.analise || x.analise.status === "erro") { desenhar(); return; }
  desenhar();
  if (x.analise.status === "processando") acompanhar();
}

function htmlAnaliseLances(x) {
  const a = x.analise, crit = x.criterio;
  if (!a || a.status === "erro") return `<p>A IA cruza o <b>histórico de preços dos possíveis concorrentes</b> desta licitação (preços homologados no PNCP em contratações parecidas)
      com o valor estimado e o seu piso, e sugere a proposta inicial, o alvo de fechamento e a estratégia. Cada afirmação passa pelo <b>DoubleCheck™</b>.</p>
    ${a?.erro ? `<div class="aviso erro">${esc(a.erro)}</div>` : ""}
    <p class="fraco">Se a licitação ainda não tem os possíveis concorrentes, o Kasiski busca agora (conta uma avaliação de possíveis concorrentes do seu plano).</p>
    <button class="botao" data-al-rodar>${dcSimbolo(14)} Analisar lances com IA</button>`;
  if (a.status === "processando") return `<p class="carregando">${esc(a.etapa || "Analisando…")}</p><p class="fraco">Pode fechar esta janela: a análise continua e aparece no cartão da sala.</p>`;
  const ev = a.evidencias || {}, c = a.calculo || {};
  if (!c.suficiente) return `<div class="aviso info"><b>Sem base suficiente para sugerir valores.</b> ${ev.tem_possiveis ? "Os possíveis concorrentes encontrados não têm preços comparáveis com este item." : "Não encontramos contratações anteriores parecidas no PNCP."}
      ${!ev.base ? " Informe também o valor estimado do item na estratégia." : ""}</div>
    ${(c.alertas || []).map((t) => `<p class="fraco">${esc(t)}</p>`).join("")}<button class="botao secundario" data-al-rodar>Analisar de novo</button>`;
  const pontos = [["Estimado", ev.base, "est"], ["Mediana dos concorrentes", c.mediana, "med"], ["Fechamento provável", c.fechamento_provavel, "fech"],
    ["Menor preço já praticado", c.mais_agressivo, "agr"], ["Seu piso", ev.piso, "piso"], ["Proposta sugerida", c.proposta_inicial, "prop"]].filter((p) => p[1]);
  const vals = pontos.map((p) => p[1]);
  const lo = Math.min(...vals) * 0.97, hi = Math.max(...vals) * 1.01;
  const pos = (v) => `${Math.round(((v - lo) / (hi - lo || 1)) * 1000) / 10}%`;
  const est = x.analise.ia?.estrategia || c.estrategia;
  return `${a.demonstracao ? `<div class="aviso info">Análise de demonstração: configure as chaves de IA para o texto real. Os números abaixo são calculados a partir do PNCP.</div>` : ""}
    ${dcResumoHtml(a.doublecheck, { titulo: "DoubleCheck™ desta análise", sub: "A IA explica; o verificador confere cada afirmação contra os números." })}
    ${c.folga_pct !== undefined && c.folga_pct < 0 ? `<div class="aviso erro"><b>Atenção:</b> o concorrente mais barato costuma fechar abaixo do seu piso. Vencer pode exigir preço com prejuízo: reveja os custos ou avalie não disputar este item.</div>` : ""}
    <div class="al-sugestoes">
      <div><small>Proposta inicial sugerida</small><b>${fmtLance(c.proposta_inicial, crit)}</b><span>${fmt.num(c.proposta_inicial / ev.base * 100, 1)}% do estimado</span>
        <button class="botao pequeno secundario" data-al-aplicar="proposta">Usar como lance inicial</button></div>
      <div><small>Alvo de fechamento</small><b>${fmtLance(c.alvo_fechamento, crit)}</b><span>cobre por pouco o concorrente mais barato</span></div>
      <div><small>Limite (seu piso)</small><b>${fmtLance(ev.piso, crit)}</b><span>${c.folga_pct !== undefined ? `folga de ${fmt.num(c.folga_pct, 1)}% sobre o provável fechamento` : "defina na estratégia"}</span></div>
      <div><small>Estratégia sugerida</small><b>${esc(V.disputa.cfg?.estrategias?.[est]?.nome || est || "—")}</b><span>${esc(a.ia?.por_que || "")}</span>
        <button class="botao pequeno secundario" data-al-aplicar="estrategia">Aplicar estratégia</button></div></div>
    <figure class="al-escala" aria-label="Faixa de preços">
      <figcaption>Faixa de preços (${esc(ev.fonte || "")})</figcaption>
      <div class="al-trilho">${pontos.map(([n, v, k]) => `<span class="al-marca al-${k}" style="left:${pos(v)}" title="${esc(n)}: ${fmtLance(v, crit)}"></span>`).join("")}</div>
      <ul class="al-legenda">${pontos.sort((p, q) => p[1] - q[1]).map(([n, v, k]) => `<li><i class="al-${k}"></i>${esc(n)} <b>${fmtLance(v, crit)}</b>${ev.base ? ` <small>${fmt.num(v / ev.base * 100, 1)}%</small>` : ""}</li>`).join("")}</ul></figure>
    ${a.ia?.resumo ? `<p class="al-resumo">${esc(a.ia.resumo)}</p>` : ""}
    ${(a.itens || []).filter((i) => i.tipo !== "leitura_de_concorrente").map((i) => `<div class="al-afirma"><p>${esc(i.texto)}</p>${revisorHtml(i.verificacao, { titulo: "Análise de lances", texto: i.texto, origem: "Histórico de preços (PNCP)" })}</div>`).join("")}
    <h3 class="al-h">Possíveis concorrentes e os preços que praticaram</h3>
    <div class="tabela-rolagem"><table><thead><tr><th>Empresa</th><th>Preço médio</th><th>Menor preço</th><th>Amostras</th><th>Relevância</th></tr></thead>
      <tbody>${(ev.concorrentes || []).map((k) => `<tr><td>${esc(k.nome || k.cnpj)}${k.mesmo_orgao ? ` <small class="fraco">já venceu neste órgão</small>` : ""}</td>
        <td>${fmt.num(k.pct_medio, 1)}% · ${fmtLance(ev.base * k.pct_medio / 100, crit)}</td><td>${fmt.num(k.pct_minimo, 1)}%</td><td>${k.n || "—"}</td><td>${esc(k.relevancia || "—")}</td></tr>`).join("")}</tbody></table></div>
    ${(a.itens || []).filter((i) => i.tipo === "leitura_de_concorrente").map((i) => `<div class="al-afirma"><p>${esc(i.texto)}</p>${revisorHtml(i.verificacao, { titulo: "Leitura de concorrente", texto: i.texto, origem: "Histórico de preços (PNCP)" })}</div>`).join("")}
    ${[...(c.alertas || []), ...((a.ia?.riscos || []).filter((r) => !(c.alertas || []).includes(r)))].length ? `<h3 class="al-h">Riscos</h3><ul>${[...(c.alertas || []), ...((a.ia?.riscos || []).filter((r) => !(c.alertas || []).includes(r)))].map((r) => `<li>${esc(r)}</li>`).join("")}</ul>` : ""}
    ${(a.ia?.na_sessao || []).length ? `<h3 class="al-h">Na sessão</h3><ul>${a.ia.na_sessao.map((r) => `<li>${esc(r)}</li>`).join("")}</ul>` : ""}
    <p class="dc-aviso">${esc(a.aviso || "")} ${ev.possiveis_consultado_em ? `Histórico consultado em ${fmt.dataHora(ev.possiveis_consultado_em + "Z")}.` : ""}</p>
    <div class="acoes"><button class="botao texto pequeno" data-al-rodar>Analisar de novo</button></div>`;
}
