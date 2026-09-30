// Painel: visão geral da empresa ativa (ou de todas, para consultores).
V.painel = async (el) => {
  if (!S.empresas.length) { el.innerHTML = exigirEmpresa(); return; }
  const multi = S.empresas.length > 1;
  const todas = multi && sessionStorage.getItem("painel_todas") === "1";
  const p = await api("GET", "/api/painel" + (todas ? "" : `?empresa_id=${S.empresaId}`));
  const e = p.editais;
  el.innerHTML = `
    <div class="cabecalho"><div><h1>Painel</h1><p>${todas ? "Todas as empresas atendidas" : esc(empresaAtual()?.razao_social)}</p></div>
      <div class="acoes">${multi ? `<label class="check"><input type="checkbox" id="todas" ${todas ? "checked" : ""}> Ver todas as empresas</label>` : ""}
      <a class="botao" href="#/radar">${icone("radar")} Ver radar</a></div></div>
    ${guia(`<p>O painel reúne o que exige atenção: prazos próximos, documentos vencendo e pagamentos atrasados.
      O caminho natural é: <b>Radar</b> (encontrar editais) → <b>Oportunidades</b> (acompanhar, analisar e decidir) → <b>Peças</b> e <b>Agenda</b> (agir no prazo) → <b>Contratos</b> (receber em dia).</p>`)}
    ${htmlPrimeirosPassos(p.primeiros_passos)}
    ${p.doublecheck?.total ? `<section class="bloco dc-painel">${dcResumoHtml(p.doublecheck, { titulo: `DoubleCheck™ · ${fmt.num(p.doublecheck.total, 0)} itens verificados`, sub: `em ${p.doublecheck.analises} análise(s) e peça(s)` })}
      ${p.doublecheck.divergencia + p.doublecheck.revisao ? `<p class="dc-destaque">O DoubleCheck identificou <b>${p.doublecheck.divergencia + p.doublecheck.revisao}</b> ponto(s) que pediam atenção antes de chegarem à sua equipe.</p>` : `<p class="dc-destaque">Todas as conclusões verificadas até aqui tiveram concordância entre os modelos.</p>`}</section>` : ""}
    <div class="acoes-rapidas">
      <a href="#/radar" class="acao-rapida"><span class="icone-caixa">${icone("radar")}</span><span>Buscar editais no radar</span></a>
      <a href="#" class="acao-rapida" data-acao="novo-edital"><span class="icone-caixa">${icone("editais")}</span><span>Novo edital</span></a>
      <a href="#" class="acao-rapida" data-acao="consultar-cnpj"><span class="icone-caixa">${icone("buscar")}</span><span>Consultar CNPJ de concorrente</span></a>
      <a href="#" class="acao-rapida" data-acao="novo-prazo"><span class="icone-caixa">${icone("agenda")}</span><span>Novo prazo na agenda</span></a>
    </div>
    <div class="grade grade-4 bloco">
      <div class="indicador"><b>${p.radar_novos}</b><span>editais novos no radar</span></div>
      <div class="indicador"><b>${e.acompanhando + e.participando}</b><span>em acompanhamento ou disputa</span></div>
      <div class="indicador"><b>${p.taxa_sucesso === null ? "—" : p.taxa_sucesso + "%"}</b><span>taxa de sucesso (${e.ganho} ganhos, ${e.perdido} perdidos)</span></div>
      <div class="indicador ${p.pagamentos_atrasados.quantidade ? "alerta" : ""}"><b>${fmt.moeda(p.pagamentos_atrasados.valor)}</b><span>${p.pagamentos_atrasados.quantidade} pagamento(s) em atraso</span></div>
    </div>
    ${todas ? "" : await resumoPipelineHtml()}
    <div class="grade grade-2">
      <section class="bloco"><div class="bloco-titulo"><h2>Próximos prazos</h2><a href="#/agenda">Agenda completa</a></div>
        ${p.proximos_prazos.length ? p.proximos_prazos.map((x) => `<div class="lista-item"><div class="corpo"><b>${esc(x.titulo)}</b>
          <p>${fmt.dataHora(x.data)} · ${esc(x.fundamento || "")}</p></div>${carimboPrazo(x.data)}</div>`).join("")
          : vazio("Nenhum prazo pela frente", "Os prazos aparecem aqui quando você acompanha um edital ou cadastra um contrato.")}
      </section>
      <section class="bloco"><div class="bloco-titulo"><h2>Documentos que exigem ação</h2><a href="#/cofre">Abrir cofre</a></div>
        ${p.documentos_alerta.length ? p.documentos_alerta.map((d) => `<div class="lista-item"><div class="corpo"><b>${esc(d.tipo)}</b>
          <p>Validade ${fmt.data(d.validade)}</p></div>${d.situacao === "vencido" ? carimbo("Vencido", "erro") : carimbo("Vencendo", "aviso")}</div>`).join("")
          : vazio("Cofre em dia", "Nenhum documento vence nos próximos 30 dias.")}
      </section>
    </div>`;
  const t = $("#todas", el);
  if (t) t.onchange = () => { sessionStorage.setItem("painel_todas", t.checked ? "1" : "0"); V.painel(el); };
  const rt = $("[data-refazer-tour]", el); if (rt) rt.onclick = () => refazerTour();
  const fpp = $("[data-fechar-pp]", el);
  if (fpp) fpp.onclick = () => { try { localStorage.setItem(`kasiski_pp_${S.usuario.id}`, "1"); } catch { /* ok */ } $("#primeiros-passos", el).remove(); };
  $('[data-acao="novo-edital"]', el).onclick = (ev) => { ev.preventDefault(); modalNovoEdital(); };
  $('[data-acao="consultar-cnpj"]', el).onclick = (ev) => { ev.preventDefault(); modalNovoDossie(); };
  $('[data-acao="novo-prazo"]', el).onclick = (ev) => { ev.preventDefault(); modalNovoPrazo(); };
};

// Checklist do primeiro uso: marcado pelo que a conta já fez de verdade. Some quando tudo está feito ou se a pessoa fechar.
function htmlPrimeirosPassos(passos) {
  if (!passos?.length) return "";
  let fechado = false;
  try { fechado = localStorage.getItem(`kasiski_pp_${S.usuario.id}`) === "1"; } catch { /* ok */ }
  const feitos = passos.filter((x) => x.feito).length;
  if (fechado || feitos === passos.length) return "";
  const prox = passos.find((x) => !x.feito);
  return `<section class="bloco primeiros-passos" id="primeiros-passos" aria-labelledby="pp-titulo">
    <div class="bloco-titulo"><h2 id="pp-titulo">Primeiros passos</h2><span class="fraco">${feitos} de ${passos.length}</span></div>
    <div class="pp-barra" role="progressbar" aria-valuemin="0" aria-valuemax="${passos.length}" aria-valuenow="${feitos}" aria-label="Progresso dos primeiros passos"><i style="width:${Math.round((100 * feitos) / passos.length)}%"></i></div>
    <ol class="pp-lista">${passos.map((x) => `<li class="${x.feito ? "feito" : x === prox ? "proximo" : ""}">
      <span class="pp-marca" aria-hidden="true">${x.feito ? icone("ok", 16) : ""}</span>
      ${x.feito ? `<span>${esc(x.titulo)}</span><span class="oculto-visual">(feito)</span>` : `<a href="${esc(x.link)}">${esc(x.titulo)}</a>${x === prox ? ` <small class="pp-agora">próximo</small>` : ""}`}</li>`).join("")}</ol>
    <div class="acoes"><button class="botao texto pequeno" type="button" data-refazer-tour>Ver o tour de novo</button>
      <button class="botao texto pequeno" type="button" data-fechar-pp>Não mostrar mais</button></div></section>`;
}
