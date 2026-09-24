// Empresas atendidas pela conta e edição do perfil (usado no radar e na análise).
V.empresas = async (el) => {
  el.innerHTML = `
    <div class="cabecalho"><div><h1>${S.plano?.empresas > 1 ? "Empresas atendidas" : "Minha empresa"}</h1>
      <p>Cada empresa tem seu próprio cofre, radar, editais e contratos.</p></div>
      <button class="botao" id="nova-empresa">${icone("adicionar")} Cadastrar empresa</button></div>
    <section class="bloco">${S.empresas.length ? S.empresas.map(linhaEmpresa).join("") : vazio("Nenhuma empresa cadastrada", "Cadastre a primeira empresa para começar a usar o Kasiski.")}</section>`;
  $("#nova-empresa", el).onclick = () => modalEmpresa();
  $$("[data-editar-emp]", el).forEach((b) => b.onclick = () => modalEmpresa(S.empresas.find((e) => e.id == b.dataset.editarEmp)));
  $$("[data-excluir-emp]", el).forEach((b) => b.onclick = async () => {
    if (await confirmar("Excluir esta empresa apaga todos os editais, documentos, peças e contratos dela. Continuar?", "Excluir empresa")) {
      await api("DELETE", `/api/empresas/${b.dataset.excluirEmp}`); await carregarConta(); V.empresas(el);
    }
  });
};

function linhaEmpresa(e) {
  const segs = (e.segmentos || "").split(",").map((s) => s.trim()).filter(Boolean);
  const nomesSeg = Object.fromEntries(ROTULOS.segmentosEmpresa);
  return `<div class="lista-item"><div class="corpo"><b>${esc(e.razao_social)}</b>
    <p>${fmt.cnpj(e.cnpj)} · porte ${esc(e.porte)}${e.ufs ? " · " + esc(e.ufs) : ""}</p>
    ${segs.length ? `<p class="fraco">Segmentos: ${segs.map((s) => esc(nomesSeg[s] || s)).join(", ")}</p>` : ""}
    ${e.palavras_chave ? `<p class="fraco">Radar: ${esc(e.palavras_chave)}</p>` : `<p class="fraco">Radar sem palavras-chave configuradas</p>`}</div>
    <div class="acoes"><button class="botao pequeno secundario" data-editar-emp="${e.id}">${icone("editar",14)} Editar</button>
      <button class="botao texto pequeno" data-excluir-emp="${e.id}">${icone("excluir",14)} Excluir</button></div></div>`;
}

const PALAVRAS_POR_SEGMENTO = {
  obras: "construção, reforma, ampliação, engenharia civil", servicos_comuns: "prestação de serviços",
  servicos_continuados: "limpeza, conservação, portaria, vigilância", fornecimento: "aquisição, fornecimento",
  saude: "hospitalar, saúde, medicamentos, materiais médicos", educacao: "escolar, merenda, transporte escolar",
  ti: "tecnologia da informação, software, infraestrutura de TI", alimentacao: "alimentação, gêneros alimentícios, nutrição",
  transporte: "transporte, frota, locação de veículos", seguranca: "segurança, vigilância patrimonial",
};

function modalEmpresa(e) {
  const m = modal({
    titulo: e ? "Editar empresa" : "Cadastrar empresa", largo: true, corpo: `<form id="form-empresa">
      <div class="linha-campos">
        <div class="campo"><label for="cnpj_e">CNPJ</label><input id="cnpj_e" name="cnpj" required value="${esc(e?.cnpj || "")}" ${e ? "readonly" : ""} placeholder="00.000.000/0000-00">
          ${!e ? `<button type="button" class="botao texto pequeno" id="buscar-cnpj" style="align-self:flex-start;padding-left:0">Buscar dados na Receita</button>` : ""}</div>
        <div class="campo"><label for="porte_e">Porte</label><select id="porte_e" name="porte">
          <option value="ME" ${e?.porte === "ME" ? "selected" : ""}>Microempresa (ME)</option>
          <option value="EPP" ${e?.porte === "EPP" ? "selected" : ""}>Empresa de pequeno porte (EPP)</option>
          <option value="demais" ${(!e || e.porte === "demais") ? "selected" : ""}>Demais portes</option></select></div></div>
      <div class="campo"><label for="razao_e">Razão social</label><input id="razao_e" name="razao_social" required value="${esc(e?.razao_social || "")}"></div>
      <div class="campo"><label>Segmentos de atuação</label>
        <div class="linha-campos" style="row-gap:6px">
          ${ROTULOS.segmentosEmpresa.map(([k, v]) => `<label class="check"><input type="checkbox" class="seg-empresa" value="${k}"
            ${(e?.segmentos || "").split(",").map((s) => s.trim()).includes(k) ? "checked" : ""}> ${esc(v)}</label>`).join("")}
        </div>
        <small>Usado para sugerir exigências setoriais na análise (ex.: ANVISA para saúde, PNAE para educação).</small></div>
      <div class="campo"><label for="cnaes_e">CNAEs (opcional)</label><input id="cnaes_e" name="cnaes" value="${esc(e?.cnaes || "")}" placeholder="Separe por vírgula"></div>
      <div class="campo"><label for="palavras_e">Palavras-chave para o radar</label><textarea id="palavras_e" name="palavras_chave" placeholder="Ex.: limpeza, conservação predial, jardinagem">${esc(e?.palavras_chave || "")}</textarea>
        <small>Separe por vírgula. São os termos buscados diariamente no PNCP.</small>
        <button type="button" class="botao texto pequeno" id="sugerir-palavras" style="align-self:flex-start;padding-left:0">Sugerir a partir dos segmentos marcados</button></div>
      <div class="linha-campos">
        <div class="campo"><label for="ufs_e">Estados de interesse</label><input id="ufs_e" name="ufs" value="${esc(e?.ufs || "")}" placeholder="Ex.: SP, MG (em branco = todo o Brasil)"></div>
        <div class="campo"><label for="vmin_e">Valor mínimo (R$)</label><input id="vmin_e" name="valor_min" inputmode="decimal" value="${e?.valor_min ?? ""}"></div>
        <div class="campo"><label for="vmax_e">Valor máximo (R$)</label><input id="vmax_e" name="valor_max" inputmode="decimal" value="${e?.valor_max ?? ""}"></div></div>
      <div id="erro-empresa"></div><button class="botao" style="width:100%" type="submit">Salvar</button></form>`,
  });
  const bc = $("#buscar-cnpj", m);
  if (bc) bc.onclick = () => ocupado(bc, "Buscando…", async () => {
    try { const d = await api("GET", `/api/cnpj/${$("#cnpj_e", m).value.replace(/\D/g, "")}`);
      if (d.status === "ok") { $("#razao_e", m).value = d.razao_social || ""; if (d.porte) { const map = { "MICRO EMPRESA": "ME", "EMPRESA DE PEQUENO PORTE": "EPP" }; $("#porte_e", m).value = map[d.porte] || "demais"; } toast("Dados preenchidos.", "ok"); }
      else toast("CNPJ não encontrado na Receita.", "erro");
    } catch (e2) { toast(e2.message, "erro"); }
  });
  $("#sugerir-palavras", m).onclick = () => {
    const marcados = $$(".seg-empresa:checked", m).map((c) => c.value);
    if (!marcados.length) { toast("Marque ao menos um segmento primeiro."); return; }
    const sugestao = [...new Set(marcados.flatMap((k) => (PALAVRAS_POR_SEGMENTO[k] || "").split(",").map((s) => s.trim()).filter(Boolean)))];
    const campo = $("#palavras_e", m);
    const atuais = campo.value.split(",").map((s) => s.trim()).filter(Boolean);
    campo.value = [...new Set([...atuais, ...sugestao])].join(", ");
  };
  $("#form-empresa", m).onsubmit = async (ev) => {
    ev.preventDefault();
    const b = ev.target.querySelector("button[type=submit]");
    await ocupado(b, "Salvando…", async () => {
      try {
        const dados = dadosForm(ev.target);
        dados.segmentos = $$(".seg-empresa:checked", m).map((c) => c.value).join(",");
        await api(e ? "PATCH" : "POST", e ? `/api/empresas/${e.id}` : "/api/empresas", dados);
        await carregarConta(); m.fechar(); V.empresas($("#conteudo"));
      } catch (err) { $("#erro-empresa", m).innerHTML = erroTela(err); }
    });
  };
}
