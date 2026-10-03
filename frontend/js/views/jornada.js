// Jornada da licitação (#/editais/:id/jornada): o que falta em cada fase, montado pelo servidor a partir das fontes
// (análise, Cofre, prazos, concorrentes, proposta, peças, salas de disputa, contrato). Esta tela só lê e encaminha
// para onde cada coisa é feita.

const JN_DECISAO = { participar: ["Participar", "ok"], participar_com_ressalvas: ["Participar com ressalvas", "aviso"], nao_participar: ["Não participar", "erro"] };
const JN_MEDIDA = { esclarecimento: "Pedido de esclarecimento", impugnacao: "Impugnação" };
const JN_STATUS_EXIG = { atende: ["Atende", "ok"], falta: ["Falta", "erro"], vencido: ["Vencido", "erro"], verificar: ["Verificar", "aviso"] };
const JN_COR_FAIXA = { ok: "g-ok", aviso: "g-aviso", erro: "g-erro", neutro: "", info: "g-info" };

const jnDataCurta = (iso) => { if (!iso) return "—"; const d = new Date(iso.length === 10 ? iso + "T12:00" : iso);
  return isNaN(d) ? "—" : d.toLocaleDateString("pt-BR", { day: "2-digit", month: "short" }).replace(".", "").toUpperCase(); };
const jnUteis = (n) => (n === null || n === undefined ? "" : n < 0 ? "encerrado" : n === 0 ? "hoje" : `${n} dia${n === 1 ? "" : "s"} út${n === 1 ? "il" : "eis"}`);
const jnLinha = (cor, titulo, sub, fim = "") => `<li class="${JN_COR_FAIXA[cor] ?? ""}"><span class="fx"></span><span><b>${titulo}</b>${sub ? `<small>${sub}</small>` : ""}</span><span class="fim">${fim}</span></li>`;
const jnAbaEdital = (id, aba) => `data-aba-edital="${aba}" href="#/editais/${id}"`;

V.jornada = async (el, id) => {
  const j = await api("GET", `/api/editais/${id}/jornada`);
  const fases = Object.fromEntries(j.fases.map((f) => [f.id, f]));
  let fase = sessionStorage.getItem("jornada_fase_" + id) || j.fase_atual;
  if (!fases[fase]) fase = j.fase_atual;
  const primeiraAberta = (f) => (fases[f].etapas.find((e) => e.estado !== "feita" && e.estado !== "bloqueada") || fases[f].etapas[0]).id;
  let etapa = sessionStorage.getItem("jornada_etapa_" + id);
  if (!fases[fase].etapas.some((e) => e.id === etapa)) etapa = primeiraAberta(fase);
  const ed = j.edital;

  // destaque: na preparação, a sessão; depois, o próximo prazo
  const [dVal, dRot, urgente] = fase === "preparacao" && j.sessao.data
    ? [jnDataCurta(j.sessao.data), `Sessão · ${jnUteis(j.sessao.dias_uteis)}`, j.sessao.dias_uteis !== null && j.sessao.dias_uteis <= 10]
    : j.proximo_prazo ? [jnDataCurta(j.proximo_prazo.data), `${j.proximo_prazo.titulo} · ${jnUteis(j.proximo_prazo.dias_uteis)}`, j.proximo_prazo.dias_uteis <= 3]
    : ["—", "Sem prazo aberto", false];
  const f = fases[fase];
  const pct = Math.round((f.concluidas / f.etapas.length) * 100);

  el.innerHTML = `
    <nav class="trilha" aria-label="Você está em"><a href="#/oportunidades/${ed.id}">${icone("chevronEsquerda", 14)} Oportunidades</a><span aria-hidden="true">/</span><a href="#/editais/${ed.id}">${esc(ed.numero || "Licitação")}</a><span aria-hidden="true">/</span><span>Jornada</span></nav>
    <section class="jn-cab">
      <div><div class="jn-meta">${carimbo(ed.etapa_nome || "—", "oficio")}${ed.modalidade ? `<span>${esc(ed.modalidade)}</span>` : ""}${ed.responsavel ? `<span>Responsável: <b>${esc(ed.responsavel)}</b></span>` : ""}</div>
        <h1>${esc(ed.numero || "Licitação")}</h1>
        <p class="fraco" style="margin:0">${esc(ed.orgao || "")}${ed.objeto ? " · " + esc(ed.objeto.slice(0, 180)) : ""}${ed.valor_estimado ? " · " + fmt.moeda(ed.valor_estimado) : ""}</p></div>
      <div class="jn-numeros">
        <div class="${urgente ? "urgente" : ""}"><b>${esc(dVal)}</b><small class="fraco">${esc(dRot)}</small></div>
        <div><b>${f.concluidas}/${f.etapas.length}</b><small class="fraco">Etapas concluídas</small></div>
        <div><b>${f.pendencias}</b><small class="fraco">Pendências</small></div></div>
      <div class="jn-barra" role="progressbar" aria-valuenow="${pct}" aria-valuemin="0" aria-valuemax="100" aria-label="Andamento da fase"><i style="width:${pct}%"></i></div>
    </section>
    ${ed.alerta_datas ? `<div class="aviso erro" style="margin-top:12px">As datas desta licitação não batem entre as fontes. <a href="#/editais/${ed.id}">Confira as datas</a> antes de seguir os prazos.</div>` : ""}
    <div class="jn-fases" role="tablist" aria-label="Fases da licitação">${j.fases.map((x) => `<button class="jn-fase" role="tab" data-fase="${x.id}" aria-selected="${x.id === fase}">
      ${esc(x.nome)}${x.pendencias ? `<span class="n ${x.id === j.fase_atual ? "alerta" : ""}">${x.pendencias}</span>` : ""}${x.id === j.fase_atual ? `<span class="atual">agora</span>` : ""}</button>`).join("")}</div>
    <div class="jn">
      <ol class="jn-etapas" aria-label="Etapas">${f.etapas.map((e, i) => `<li class="${e.estado}"><button class="jn-etapa" data-etapa="${e.id}" ${e.id === etapa ? 'aria-current="step"' : ""}>
        <span class="jn-bola">${e.estado === "feita" ? "✓" : i + 1}</span>
        <span><b>${esc(e.nome)}</b><small class="fraco">${esc(e.sub)}</small>${carimbo(e.rotulo, e.cor)}</span></button></li>`).join("")}</ol>
      <section class="jn-trab" id="jn-trab" aria-live="polite"></section>
    </div>`;

  $$("[data-fase]", el).forEach((b) => b.onclick = () => { sessionStorage.setItem("jornada_fase_" + id, b.dataset.fase); sessionStorage.removeItem("jornada_etapa_" + id); V.jornada(el, id); });
  $$("[data-etapa]", el).forEach((b) => b.onclick = () => { sessionStorage.setItem("jornada_etapa_" + id, b.dataset.etapa); sessionStorage.setItem("jornada_fase_" + id, fase); V.jornada(el, id); });
  const e = f.etapas.find((x) => x.id === etapa);
  const trab = $("#jn-trab", el);
  trab.innerHTML = jnTela(e, ed, j);
  jnLigar(trab, e, ed, el, id);
};

function jnCab(e, texto) {
  return `<header class="jn-trab-cab"><div><h2>${esc(e.nome)}</h2><p>${texto}</p></div>${carimbo(e.rotulo, e.cor)}</header>`;
}
function jnAcao(texto, botoes = "") {
  return `<div class="jn-acao"><p>${texto}</p><div class="botoes">${botoes}</div></div>`;
}

function jnTela(e, ed, j) {
  const d = e.dados || {};
  const T = JN_TELAS[e.id];
  return T ? T(e, d, ed, j) : jnCab(e, "");
}

const JN_TELAS = {
  analise(e, d, ed) {
    const link = `<a class="botao pequeno" ${jnAbaEdital(ed.id, "analise")}>${e.estado === "feita" ? "Abrir a análise completa" : "Ir para a análise"}</a>`;
    if (e.estado !== "feita") return jnCab(e, "O Kasiski lê o edital, confere cada conclusão com o DoubleCheck e aponta a página de onde veio.") +
      jnAcao(e.estado === "atencao" ? `<b>Analisando o edital…</b> ${esc(d.etapa_atual || "")}` : e.estado === "atualizar" ? `<b>A análise falhou.</b> ${esc(d.erro || "Tente de novo.")}` : "<b>Comece pela análise do edital.</b> As outras etapas da preparação dependem dela.", link);
    const [dl, dt] = JN_DECISAO[d.decisao] || [d.decisao || "—", "neutro"];
    return jnCab(e, `Análise de ${fmt.dataHora(d.analisada_em)}${d.demonstracao ? " (demonstração)" : ""}. Cada requisito aponta a página do edital.`) +
      jnAcao(`Recomendação: ${carimbo(dl, dt)} ${esc(d.justificativa || "")}`, link) +
      `<div class="jn-corpo">
        ${d.resumo ? `<div class="jn-grupo"><h3>Resumo</h3><p class="jn-resumo">${esc(d.resumo)}</p></div>` : ""}
        ${(d.riscos || []).length ? `<div class="jn-grupo"><h3>Principais riscos</h3><ul class="jn-lista">${d.riscos.map((r) => jnLinha(r.nivel === "alto" ? "erro" : r.nivel === "medio" ? "aviso" : "neutro",
          esc(r.tema || "Risco"), `${esc(r.descricao || "")}${r.pagina ? ` · pág. ${esc(r.pagina)}` : ""}`, carimbo(r.nivel === "alto" ? "Alto" : r.nivel === "medio" ? "Médio" : "Baixo", r.nivel === "alto" ? "erro" : r.nivel === "medio" ? "aviso" : "neutro"))).join("")}</ul></div>` : ""}
        ${(d.proximos_passos || []).length ? `<div class="jn-grupo"><h3>Próximos passos sugeridos</h3><ul class="jn-lista">${d.proximos_passos.map((p) => jnLinha("info", esc(p), "")).join("")}</ul></div>` : ""}
      </div>`;
  },

  questionamentos(e, d, ed) {
    const prazoTxt = d.prazo ? `Prazo: <b>${fmt.dataHora(d.prazo)}</b> (${jnUteis(d.dias_uteis)})${d.prazo_fundamento ? ` · <small>${esc(d.prazo_fundamento)}</small>` : ""}` : "Prazo: informe a data da sessão para o Kasiski calcular (Lei 14.133, art. 164).";
    const intro = "Dúvidas sobre o edital viram pedido de esclarecimento; cláusulas que restringem a disputa podem ser impugnadas. Qualquer pessoa pode fazer os dois até 3 dias úteis antes da abertura (art. 164).";
    if (e.estado === "bloqueada") return jnCab(e, intro) + jnAcao("<b>Esta etapa começa depois da análise do edital.</b> É ela que encontra as cláusulas restritivas.", `<a class="botao pequeno secundario" ${jnAbaEdital(ed.id, "analise")}>Ir para a análise</a>`);
    const encerrado = d.dias_uteis !== null && d.dias_uteis < 0;
    const qs = d.questoes || [];
    return jnCab(e, intro) +
      jnAcao(qs.length ? `${prazoTxt}${encerrado ? "<br><b>O prazo acabou.</b> Os pontos abaixo ficam como risco para a disputa e para um eventual recurso." : "<br>Escolha os pontos e prepare a minuta. O protocolo é feito no portal ou no e-mail indicado no edital."}` : prazoTxt,
        !encerrado && qs.length ? `<button class="botao pequeno" data-jn-minuta="todas">Preparar minuta com todos</button>` : "") +
      `<div class="jn-corpo">
        ${qs.length ? `<div class="jn-grupo"><h3>Pontos encontrados na análise</h3><ul class="jn-lista">${qs.map((q) => {
          const [gl, gt] = ROTULOS.gravidade[q.gravidade] || [q.gravidade || "—", "neutro"];
          return jnLinha(gt === "neutro" ? "info" : gt, esc(q.clausula || "Cláusula"),
            `${esc(q.por_que || "")}${q.pagina ? ` · pág. ${esc(q.pagina)}` : ""}${q.fundamento ? ` · ${esc(q.fundamento)}` : ""}`,
            `${carimbo(JN_MEDIDA[q.medida] || q.medida, q.medida === "impugnacao" ? "erro" : "oficio")}${carimbo(gl, gt)}${!encerrado && q.id ? `<button class="botao pequeno secundario" data-jn-minuta="${esc(q.id)}" data-tipo="${esc(q.medida)}">Preparar minuta</button>` : ""}`);
        }).join("")}</ul></div>` : `<p class="fraco">A análise não encontrou cláusulas restritivas nem pontos que peçam esclarecimento.</p>`}
        ${(d.pecas || []).length ? `<div class="jn-grupo"><h3>Minutas desta licitação</h3><ul class="jn-lista">${d.pecas.map((p) => jnLinha("ok", esc(p.titulo || JN_MEDIDA[p.tipo]), `Criada em ${fmt.data(p.criado_em)}`, `<a class="botao pequeno secundario" href="#/pecas/${p.id}">Abrir</a>`)).join("")}</ul></div>` : ""}
        <p class="fraco"><small>Em breve: registrar o protocolo e a resposta do órgão aqui. Se uma impugnação for aceita e o edital mudar, a análise volta para "Requer atualização".</small></p>
      </div>`;
  },

  mercado(e, d, ed) {
    const intro = "Quem costuma vencer este tipo de compra e por quanto fecha, a partir de contratações parecidas homologadas no PNCP.";
    const link = `<a class="botao pequeno secundario" ${jnAbaEdital(ed.id, "analise")}>${e.estado === "" ? "Consultar no PNCP" : "Ver detalhes"}</a>`;
    if (!d.concorrentes) return jnCab(e, intro) +
      jnAcao(e.estado === "atencao" ? "<b>Consultando o PNCP…</b>" : e.estado === "atualizar" ? `<b>A consulta falhou.</b> ${esc(d.erro || "")}` : "<b>Consulte os possíveis concorrentes.</b> A consulta fica na página da licitação, junto da análise.", link);
    const acima = (d.precos || []).filter((p) => p.acima_media).length;
    return jnCab(e, intro) +
      jnAcao(acima ? `<b>${acima} item(ns) da sua proposta estão acima da média que os concorrentes praticaram.</b> Revise antes da disputa.` : `Consulta de ${fmt.data(d.consultado_em)}.${d.aviso ? " " + esc(d.aviso) : ""}`, link) +
      `<div class="jn-corpo">
        ${(d.concorrentes || []).length ? `<div class="jn-grupo"><h3>Possíveis concorrentes</h3><ul class="jn-lista">${d.concorrentes.map((c) => {
          const [rl, rt] = RELEVANCIA_CONC[c.relevancia] || ["—", "neutro"];
          return jnLinha(rt === "neutro" ? "" : rt === "oficio" ? "info" : rt, esc(c.nome || fmt.cnpj(c.cnpj)),
            `${c.vitorias || 0} vitória(s) parecida(s)${c.mesmo_orgao ? " · já venceu neste órgão" : c.mesma_uf ? " · mesma UF" : ""}${c.pct_medio_estimado ? ` · pratica em média ${fmt.num(c.pct_medio_estimado, 0)}% do estimado` : ""}`,
            `${carimbo(rl, rt)}${c.concorrente_id ? `<a class="botao pequeno secundario" href="#/concorrentes/${c.concorrente_id}">Dossiê</a>` : ""}`);
        }).join("")}</ul></div>` : ""}
        ${(d.precos || []).length ? `<div class="jn-grupo"><h3>Preço praticado por item</h3><div class="tabela-rolagem"><table class="jn-tabela">
          <thead><tr><th>Item</th><th>Descrição</th><th class="num">Estimado</th><th class="num">Média dos concorrentes</th><th class="num">Menor média</th><th class="num">Sua proposta</th></tr></thead>
          <tbody>${d.precos.map((p) => `<tr><td>${esc(p.numero || "—")}</td><td>${esc(p.descricao || "")}</td><td class="num">${fmt.moeda(p.estimado)}</td>
            <td class="num">${p.n ? fmt.moeda(p.media) : '<small class="fraco">sem histórico</small>'}</td><td class="num">${p.n ? fmt.moeda(p.minimo) : "—"}</td>
            <td class="num ${p.acima_media ? "acima" : ""}">${p.meu ? fmt.moeda(p.meu) : "—"}${p.acima_media ? " ▲" : ""}</td></tr>`).join("")}</tbody></table></div>
          <p class="fraco"><small>▲ acima da média dos concorrentes. Cada empresa conta uma vez por item.</small></p></div>` : ""}
      </div>`;
  },

  habilitacao(e, d, ed, j) {
    const intro = `Cada exigência do edital comparada com o Cofre, com a validade conferida na data da sessão${j.sessao.data ? ` (${fmt.data(j.sessao.data)})` : ""}.`;
    if (e.estado === "bloqueada") return jnCab(e, intro) + jnAcao("<b>Esta etapa começa depois da análise do edital.</b>", `<a class="botao pequeno secundario" ${jnAbaEdital(ed.id, "analise")}>Ir para a análise</a>`);
    const ex = d.exigencias || [];
    const graves = ex.filter((x) => ["falta", "vencido"].includes(x.status)).length;
    return jnCab(e, intro) +
      jnAcao(graves ? `<b>${graves} exigência(s) sem documento válido para a sessão.</b> Providencie e envie ao Cofre: a Jornada atualiza sozinha.` : e.pend ? "<b>Confira os itens marcados para verificar.</b>" : "<b>Tudo o que o edital pede está no Cofre e vale na data da sessão.</b>",
        `<a class="botao pequeno secundario" href="#/cofre">Abrir o Cofre</a>`) +
      `<div class="jn-corpo">${ex.length ? `<ul class="jn-lista">${ex.map((x) => {
        const [sl, st] = JN_STATUS_EXIG[x.status] || [x.status, "neutro"];
        const doc = x.documento ? `${esc(x.documento.tipo)}${x.documento.validade ? ` · válido até ${fmt.data(x.documento.validade)}` : ""}` : "";
        return jnLinha(st, esc(x.exigencia || "Exigência"), [doc, esc(x.observacao || ""), x.pagina ? `pág. ${esc(x.pagina)}` : "", x.grupo === "setorial" ? "exigência do setor" : ""].filter(Boolean).join(" · "), carimbo(sl, st));
      }).join("")}</ul>` : `<p class="fraco">A análise não listou exigências de habilitação.</p>`}</div>`;
  },

  proposta(e, d) {
    const intro = "Itens, formação de preço e minuta da proposta comercial.";
    if (!d.proposta_id) return jnCab(e, intro) + jnAcao("<b>Crie a proposta comercial.</b> O Kasiski lê os itens do edital e usa o preço dos concorrentes como referência.", `<a class="botao pequeno" href="#/precos">Criar proposta</a>`);
    return jnCab(e, intro) +
      jnAcao(d.sem_preco ? `<b>${d.sem_preco} item(ns) ainda sem preço.</b>` : d.status === "pronta" ? "<b>Proposta pronta.</b>" : "<b>Proposta em rascunho.</b> Revise os preços e gere a minuta.", `<a class="botao pequeno" href="#/propostas/${d.proposta_id}">Abrir a proposta</a>`) +
      `<div class="jn-corpo"><ul class="jn-lista">
        ${jnLinha("info", esc(d.titulo || "Proposta"), `${d.itens} item(ns) · atualizada em ${fmt.dataHora(d.atualizado_em)}`, d.total ? `<b>${fmt.moeda(d.total)}</b>` : "")}
        ${d.alertas ? jnLinha("aviso", `${d.alertas} ponto(s) de atenção`, "Apontados pela IA e pelas regras de exequibilidade") : ""}</ul>
        <p class="fraco"><small>Em breve: declarações (marcar no portal × anexar), assinatura e pacote final para envio.</small></p></div>`;
  },

  conferencia(e, d, ed) {
    const pronta = e.estado === "feita";
    return jnCab(e, "Conferência de tudo o que a preparação pede antes da sessão.") +
      jnAcao(pronta ? "<b>Licitação marcada como pronta para a disputa.</b>" : d.pendencias ? `<b>Ainda há ${d.pendencias} pendência(s).</b> Resolva-as ou marque como pronta assim mesmo, se já tratou fora do Kasiski.` : "<b>Sem pendências.</b> Marque como pronta: o cartão anda no quadro de oportunidades.",
        pronta ? "" : `<button class="botao pequeno ${d.pendencias ? "secundario" : ""}" data-jn-pronta>Marcar como pronta para disputa</button>`) +
      `<div class="jn-corpo"><ul class="jn-lista">${(d.linhas || []).map((l) => jnLinha(l.cor === "neutro" ? "" : l.cor, esc(l.nome), l.pend ? `${l.pend} pendência(s)` : "Sem pendências",
        `${carimbo(l.rotulo, l.cor)}<button class="botao pequeno texto" data-ir-etapa="${l.id}">Ver</button>`)).join("")}</ul></div>`;
  },

  disputa(e, d) {
    const intro = "Salas de disputa desta licitação: estratégia, lances e o que a extensão do navegador registrou.";
    if (!(d.salas || []).length) return jnCab(e, intro) + jnAcao("<b>Nenhuma sala de disputa ainda.</b> Prepare uma por item ou lote antes da sessão.", `<a class="botao pequeno" href="#/disputa">Abrir a sala de disputa</a>`);
    return jnCab(e, intro) + jnAcao(e.rotulo, `<a class="botao pequeno secundario" href="#/disputa">Abrir a sala de disputa</a>`) +
      `<div class="jn-corpo"><ul class="jn-lista">${d.salas.map((s) => jnLinha(s.resultado === "vencedor" || s.posicao === 1 ? "ok" : s.status === "em_disputa" ? "aviso" : "",
        `Item ${esc(s.item || "—")}${s.descricao ? " · " + esc(s.descricao.slice(0, 80)) : ""}`,
        [s.posicao ? `${s.posicao}º lugar` : "", s.meu_ultimo ? `seu lance ${fmt.moeda(s.meu_ultimo)}` : "", s.melhor_lance ? `melhor ${fmt.moeda(s.melhor_lance)}` : ""].filter(Boolean).join(" · "),
        carimbo(s.resultado || (s.status === "em_disputa" ? "Em disputa" : s.status === "encerrada" ? "Encerrada" : "Preparando"), s.resultado === "vencedor" ? "ok" : "neutro"))).join("")}</ul></div>`;
  },

  documentos(e, d, ed) {
    const intro = "Atas, decisões e diligências da sessão. A IA lê cada uma e sugere a peça cabível.";
    return jnCab(e, intro) + jnAcao((d.documentos || []).length ? e.rotulo : "<b>Envie a ata da sessão</b> quando ela sair.", `<a class="botao pequeno secundario" ${jnAbaEdital(ed.id, "documentos")}>Documentos e atas</a>`) +
      ((d.documentos || []).length ? `<div class="jn-corpo"><ul class="jn-lista">${d.documentos.map((x) => jnLinha(x.sugestoes ? "aviso" : "ok", esc(x.titulo || x.tipo), `Enviado em ${fmt.data(x.criado_em)}`,
        x.sugestoes ? carimbo(`${x.sugestoes} sugestão(ões)`, "aviso") : x.analise_status === "processando" ? carimbo("Lendo", "neutro") : "")).join("")}</ul></div>` : "");
  },

  recurso(e, d) {
    const intro = "Intenção de recorrer na sessão; razões em 3 dias úteis; contrarrazões em 3 dias úteis depois (Lei 14.133, art. 165).";
    return jnCab(e, intro) + jnAcao(e.estado === "atualizar" ? "<b>Há prazo de recurso correndo.</b>" : (d.pecas || []).length ? "Peças desta fase abaixo." : "Sem recurso registrado nesta licitação.",
      `<a class="botao pequeno ${e.estado === "atualizar" ? "" : "secundario"}" href="#/pecas">Gerar peça</a>`) +
      `<div class="jn-corpo">
        ${(d.prazos || []).length ? `<div class="jn-grupo"><h3>Prazos</h3><ul class="jn-lista">${d.prazos.map((p) => jnLinha(p.concluido ? "ok" : "erro", esc(p.titulo), esc(p.fundamento || ""), `<b>${fmt.dataHora(p.data)}</b>`)).join("")}</ul></div>` : ""}
        ${(d.pecas || []).length ? `<div class="jn-grupo"><h3>Peças</h3><ul class="jn-lista">${d.pecas.map((p) => jnLinha("info", esc(p.titulo), "", `<a class="botao pequeno secundario" href="#/pecas/${p.id}">Abrir</a>`)).join("")}</ul></div>` : ""}
      </div>`;
  },

  resultado(e, d, ed) {
    return jnCab(e, "Resultado oficial: adjudicação e homologação. O Kasiski acompanha o PNCP e move o cartão sozinho.") +
      jnAcao(e.rotulo === "Aguardando" ? "<b>Aguardando o resultado.</b>" : `<b>${esc(e.rotulo)}.</b>${d.motivo_saida ? " " + esc(d.motivo_saida) : ""}`, `<a class="botao pequeno secundario" href="#/oportunidades/${ed.id}">Ver no quadro</a>`) +
      (d.pncp_situacao || d.resultado_em ? `<div class="jn-corpo"><ul class="jn-lista">${d.pncp_situacao ? jnLinha("info", "Situação no PNCP", esc(d.pncp_situacao)) : ""}${d.resultado_em ? jnLinha("ok", "Resultado em", fmt.data(d.resultado_em)) : ""}</ul></div>` : "");
  },

  contratacao(e, d) {
    if (d.contrato_id) return jnCab(e, "A partir daqui, prazos, aditivos e pagamentos ficam na Gestão de contratos.") +
      jnAcao(`<b>Contrato ${esc(d.numero || "")} ativo.</b>${d.valor ? " " + fmt.moeda(d.valor) : ""}${d.fim ? ` · vigência até ${fmt.data(d.fim)}` : ""}`, `<a class="botao pequeno" href="#/contratos/${d.contrato_id}">Abrir na Gestão de contratos</a>`);
    return jnCab(e, "Assinatura da ata ou do contrato, com a garantia que o edital exigir.") +
      jnAcao(e.estado === "atencao" ? "<b>Cadastre o contrato assinado</b> para acompanhar prazos e pagamentos." : "<b>Esta etapa começa depois da homologação.</b>", e.estado === "atencao" ? `<a class="botao pequeno" href="#/contratos">Cadastrar contrato</a>` : "");
  },
};

function jnLigar(trab, e, ed, el, id) {
  $$("[data-aba-edital]", trab).forEach((a) => a.onclick = () => sessionStorage.setItem("edital_aba_" + ed.id, a.dataset.abaEdital));
  $$("[data-ir-etapa]", trab).forEach((b) => b.onclick = () => { sessionStorage.setItem("jornada_etapa_" + id, b.dataset.irEtapa); V.jornada(el, id); });
  $$("[data-jn-minuta]", trab).forEach((b) => b.onclick = () => {
    const qs = e.dados.questoes || [];
    const todas = b.dataset.jnMinuta === "todas";
    const ids = todas ? qs.map((q) => q.id).filter(Boolean) : [b.dataset.jnMinuta];
    const tipo = todas ? (qs.some((q) => q.medida === "impugnacao") ? "impugnacao" : "esclarecimento") : b.dataset.tipo;
    sessionStorage.setItem("nova_peca", JSON.stringify({ edital_id: ed.id, analise_id: e.dados.analise_id, itens: ids, tipo }));
    location.hash = "#/pecas";
  });
  const pr = $("[data-jn-pronta]", trab);
  if (pr) pr.onclick = async () => {
    pr.disabled = true;
    try {
      await api("PATCH", `/api/oportunidades/${ed.id}`, { etapa: "pronta", motivo: "Conferência da Jornada" });
      toast("Pronta para disputa. O cartão andou no quadro.", "ok"); V.jornada(el, id);
    } catch (err) { pr.disabled = false; toast(err.message || "Não foi possível marcar agora.", "erro"); }
  };
}
