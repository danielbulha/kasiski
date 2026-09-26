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
      O caminho natural é: <b>Radar</b> (encontrar editais) → <b>Editais</b> (analisar e decidir) → <b>Peças</b> e <b>Agenda</b> (agir no prazo) → <b>Contratos</b> (receber em dia).</p>`)}
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
  $('[data-acao="novo-edital"]', el).onclick = (ev) => { ev.preventDefault(); modalNovoEdital(); };
  $('[data-acao="consultar-cnpj"]', el).onclick = (ev) => { ev.preventDefault(); modalNovoDossie(); };
  $('[data-acao="novo-prazo"]', el).onclick = (ev) => { ev.preventDefault(); modalNovoPrazo(); };
};
