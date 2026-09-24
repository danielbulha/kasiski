// Cofre de habilitação: documentos da empresa com controle de validade.
V.cofre = async (el) => {
  if (!S.empresaId) { el.innerHTML = exigirEmpresa(); return; }
  const docs = await api("GET", `/api/empresas/${S.empresaId}/documentos`);
  const grupos = {};
  docs.forEach((d) => { (grupos[d.categoria] ||= []).push(d); });
  const ordem = ["juridica", "fiscal", "trabalhista", "economica", "tecnica", "declaracao", "outro"];
  el.innerHTML = `
    <div class="cabecalho"><div><h1>Cofre de habilitação</h1><p>Documentos de ${esc(empresaAtual().razao_social)}, usados para conferir cada edital.</p></div>
      <button class="botao" id="novo-doc">${icone("adicionar")} Novo documento</button></div>
    ${guia(`<p>Mantenha aqui os documentos de habilitação com a validade atualizada. Na análise de cada edital, o Kasiski
      confronta as exigências com o que está neste cofre e aponta o que falta, o que está vencido e o que precisa de conferência manual.</p>`)}
    ${docs.length ? ordem.filter((c) => grupos[c]).map((c) => `<section class="bloco"><h3>${esc(ROTULOS.categoriaDoc[c])}</h3>
        ${grupos[c].map(linhaDocumento).join("")}</section>`).join("")
      : vazio("Cofre vazio", "Cadastre os documentos de habilitação da empresa para as análises compararem automaticamente.")}`;
  $("#novo-doc", el).onclick = () => modalDocumento();
  $$("[data-editar-doc]", el).forEach((b) => b.onclick = () => modalDocumento(docs.find((d) => d.id == b.dataset.editarDoc)));
  $$("[data-baixar-doc]", el).forEach((b) => b.onclick = () => baixar(`/api/documentos/${b.dataset.baixarDoc}/arquivo`, b.dataset.nome));
  $$("[data-excluir-doc]", el).forEach((b) => b.onclick = async () => {
    if (await confirmar("Excluir este documento do cofre?", "Excluir")) { await api("DELETE", `/api/documentos/${b.dataset.excluirDoc}`); V.cofre(el); }
  });
};

function linhaDocumento(d) {
  const sit = { valido: ["Válido", "ok"], vencendo: ["Vence em breve", "aviso"], vencido: ["Vencido", "erro"], sem_validade: ["Sem validade", "neutro"] }[d.situacao];
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
