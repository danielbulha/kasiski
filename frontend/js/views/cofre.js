// Cofre de habilitação: documentos da empresa com controle de validade.
V.cofre = async (el) => {
  if (!S.empresaId) { el.innerHTML = exigirEmpresa(); return; }
  const docs = await api("GET", `/api/empresas/${S.empresaId}/documentos`);
  const grupos = {};
  docs.forEach((d) => { (grupos[d.categoria] ||= []).push(d); });
  const ordem = ["juridica", "fiscal", "trabalhista", "economica", "tecnica", "declaracao", "setorial", "outro"];
  const pendentes = docs.filter((d) => d.situacao === "pendente").length;
  el.innerHTML = `
    <div class="cabecalho"><div><h1>Cofre de habilitação</h1><p>Documentos de ${esc(empresaAtual().razao_social)}, usados para conferir cada edital.</p></div>
      <div class="acoes"><button class="botao secundario" id="montar-checklist">Montar pelo checklist</button>
      <button class="botao" id="novo-doc">${icone("adicionar")} Novo documento</button></div></div>
    ${pendentes ? `<div class="aviso">Há <b>${pendentes} documento(s) pendente(s)</b> vindos do checklist: anexe o arquivo ou informe a validade quando providenciar.</div>` : ""}
    ${guia(`<p>Mantenha aqui os documentos de habilitação com a validade atualizada. Na análise de cada edital, o Kasiski
      confronta as exigências com o que está neste cofre e aponta o que falta, o que está vencido e o que precisa de conferência manual.</p>`)}
    ${docs.length ? ordem.filter((c) => grupos[c]).map((c) => `<section class="bloco"><h3>${esc(ROTULOS.categoriaDoc[c])}</h3>
        ${grupos[c].map(linhaDocumento).join("")}</section>`).join("")
      : vazio("Cofre vazio", "Cadastre os documentos de habilitação da empresa para as análises compararem automaticamente.")}`;
  $("#novo-doc", el).onclick = () => modalDocumento();
  $("#montar-checklist", el).onclick = () => modalChecklist(docs);
  $$("[data-editar-doc]", el).forEach((b) => b.onclick = () => modalDocumento(docs.find((d) => d.id == b.dataset.editarDoc)));
  $$("[data-baixar-doc]", el).forEach((b) => b.onclick = () => baixar(`/api/documentos/${b.dataset.baixarDoc}/arquivo`, b.dataset.nome));
  $$("[data-excluir-doc]", el).forEach((b) => b.onclick = async () => {
    await excluirParaLixeira({ url: `/api/documentos/${b.dataset.excluirDoc}`, nome: "este documento do cofre", tipo: "documento", depois: () => V.cofre(el) });
  });
};

function linhaDocumento(d) {
  const sit = { valido: ["Válido", "ok"], vencendo: ["Vence em breve", "aviso"], vencido: ["Vencido", "erro"], sem_validade: ["Sem validade", "neutro"],
    pendente: ["Pendente", "aviso"] }[d.situacao] || ["—", "neutro"];
  return `<div class="lista-item"><div class="corpo"><b>${esc(d.tipo)}</b>
    <p>${d.validade ? `Válido até ${fmt.data(d.validade)}` : "Sem data de validade"}${d.descricao ? " · " + esc(d.descricao) : ""}</p></div>
    <div class="acoes">${carimbo(sit[0], sit[1])}
      ${d.tem_arquivo ? `<button class="botao texto pequeno" data-baixar-doc="${d.id}" data-nome="${esc(d.nome_arquivo)}">${icone("baixar",14)} Baixar</button>` : ""}
      <button class="botao secundario pequeno" data-editar-doc="${d.id}">${icone("editar",14)} Editar</button>
      <button class="botao texto pequeno" data-excluir-doc="${d.id}" aria-label="Excluir">${icone("excluir",14)} Excluir</button></div></div>`;
}

function modalDocumento(d) {
  const m = modal({
    titulo: d ? "Editar documento" : "Novo documento", corpo: `<form id="form-doc">
      <div class="campo"><label for="tipo_doc">Tipo do documento</label><input id="tipo_doc" name="tipo" required value="${esc(d?.tipo || "")}" placeholder="Ex.: CND Federal, CNDT, Atestado técnico"></div>
      <div class="linha-campos"><div class="campo"><label for="categoria_doc">Categoria</label><select id="categoria_doc" name="categoria">
          ${Object.entries(ROTULOS.categoriaDoc).map(([k, v]) => `<option value="${k}" ${d?.categoria === k ? "selected" : ""}>${v}</option>`).join("")}</select></div>
        <div class="campo"><label for="validade_doc">Validade</label><input id="validade_doc" name="validade" type="date" value="${fmt.paraInput(d?.validade)}"><small>Deixe em branco se não expira.</small></div></div>
      <div class="campo"><label for="descricao_doc">Observação</label><input id="descricao_doc" name="descricao" value="${esc(d?.descricao || "")}"></div>
      <div class="campo"><label for="arquivo_doc">Arquivo (PDF)</label><input id="arquivo_doc" name="arquivo" type="file" accept=".pdf,.jpg,.png,.doc,.docx"></div>
      <div id="erro-doc"></div><button class="botao" style="width:100%" type="submit">Salvar</button></form>`,
  });
  $("#form-doc", m).onsubmit = async (ev) => {
    ev.preventDefault();
    const b = ev.target.querySelector("button");
    await ocupado(b, "Salvando…", async () => {
      try {
        await api(d ? "PATCH" : "POST", d ? `/api/documentos/${d.id}` : `/api/empresas/${S.empresaId}/documentos`, new FormData(ev.target));
        m.fechar(); V.cofre($("#conteudo"));
      } catch (e) { $("#erro-doc", m).innerHTML = erroTela(e); }
    });
  };
}

// Monta o cofre a partir do checklist de habilitação (Lei 14.133 + exigências do setor)
async function modalChecklist(docs) {
  let def;
  try { def = await api("GET", "/api/public/checklist/modelo"); } catch (e) { avisarErro(e); return; }
  const emp = empresaAtual() || {};
  const segsEmp = (emp.segmentos || "").split(",").map((x) => x.trim()).filter(Boolean);
  const ja = new Set(docs.map((d) => d.checklist_id).filter(Boolean));
  const jaNomes = new Set(docs.map((d) => (d.tipo || "").trim().toLowerCase()));
  const noCofre = (i) => ja.has(i.id) || jaNomes.has(i.tipo.trim().toLowerCase());
  let segs = segsEmp.filter((s) => def.segmentos.some((x) => x.id === s));
  const m = modal({ titulo: "Montar o cofre pelo checklist", largo: true, corpo: `
    <p class="fraco">Documentos que a Lei 14.133/2021 permite exigir, mais os do seu setor. Os marcados entram no cofre como <b>pendentes</b> até você anexar o arquivo ou informar a validade. Os que já estão no cofre ficam de fora.</p>
    <div class="chips" role="group" aria-label="Segmentos" style="margin:10px 0">${def.segmentos.map((s) => `<button type="button" data-cseg="${s.id}" aria-pressed="${segs.includes(s.id)}">${esc(s.nome)}</button>`).join("")}</div>
    <div id="ck-lista"></div>`,
    acoes: `<span class="fraco" id="ck-resumo"></span><button class="botao" id="ck-importar">Adicionar ao cofre</button>` });
  const desenhar = () => {
    const itens = def.itens.filter((i) => !i.segmentos || i.segmentos.some((s) => segs.includes(s)));
    $("#ck-lista", m).innerHTML = def.categorias.map((c) => {
      const lista = itens.filter((i) => i.categoria === c.id); if (!lista.length) return "";
      return `<h3 style="margin:14px 0 6px">${esc(c.nome)} <small class="fraco">${esc(c.base)}</small></h3>${lista.map((i) => `<label class="check" style="display:flex;gap:10px;align-items:flex-start;padding:6px 0;border-bottom:1px solid var(--linha)">
        <input type="checkbox" data-ck="${i.id}" ${noCofre(i) ? "disabled" : "checked"}><span><b>${esc(i.tipo)}</b>${noCofre(i) ? ` ${carimbo("Já no cofre", "ok")}` : ""}<br><small class="fraco">${esc(i.onde)} · validade: ${esc(i.validade)} · ${esc(i.base)}</small></span></label>`).join("")}`;
    }).join("");
    const conta = () => { $("#ck-resumo", m).textContent = `${$$("[data-ck]:checked", m).length} documento(s) selecionado(s)`; };
    $$("[data-ck]", m).forEach((c) => c.onchange = conta); conta();
  };
  $$("[data-cseg]", m).forEach((b) => b.onclick = () => {
    segs = segs.includes(b.dataset.cseg) ? segs.filter((s) => s !== b.dataset.cseg) : [...segs, b.dataset.cseg];
    b.setAttribute("aria-pressed", String(segs.includes(b.dataset.cseg))); desenhar();
  });
  desenhar();
  $("#ck-importar", m).onclick = (ev) => ocupado(ev.target, "Adicionando…", async () => {
    const ids = $$("[data-ck]:checked", m).map((c) => ({ id: c.dataset.ck, tem: false }));
    if (!ids.length) { toast("Selecione ao menos um documento."); return; }
    try {
      const r = await api("POST", `/api/empresas/${S.empresaId}/documentos/checklist`, { itens: ids });
      toast(`${r.criados} documento(s) adicionado(s) ao cofre como pendentes.`, "ok"); m.fechar(); V.cofre($("#conteudo"));
    } catch (e) { avisarErro(e); }
  });
}
