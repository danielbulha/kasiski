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
        <div class="campo"><label for="cnpj_e">CNPJ</label><input id="cnpj_e" name="cnpj" required value="${esc(e ? fmt.cnpj(e.cnpj) : "")}" ${e ? "readonly" : ""} placeholder="00.000.000/0000-00" inputmode="numeric" autocomplete="off">
          <small id="cnpj-estado">${e ? "" : "Ao digitar o CNPJ, buscamos razão social, porte e CNAEs na Receita."}</small>
          <button type="button" class="botao texto pequeno" id="buscar-cnpj" style="align-self:flex-start;padding-left:0">${e ? "Atualizar CNAEs pela Receita" : "Buscar dados na Receita"}</button></div>
        <div class="campo"><label for="porte_e">Porte</label><select id="porte_e" name="porte">
          <option value="ME" ${e?.porte === "ME" ? "selected" : ""}>Microempresa (ME)</option>
          <option value="EPP" ${e?.porte === "EPP" ? "selected" : ""}>Empresa de pequeno porte (EPP)</option>
          <option value="demais" ${(!e || e.porte === "demais") ? "selected" : ""}>Demais portes</option></select></div></div>
      <div id="receita-info"></div>
      <div class="campo"><label for="razao_e">Razão social</label><input id="razao_e" name="razao_social" required value="${esc(e?.razao_social || "")}"></div>
      <div class="campo"><label for="cnaes_e">CNAEs</label><textarea id="cnaes_e" name="cnaes" rows="4" placeholder="Um por linha. Ex.: 8121-4/00 Limpeza em prédios e em domicílios">${esc(e?.cnaes || "")}</textarea>
        <small>Preenchido pela Receita. Pode editar: a IA usa esta lista para conferir se o objeto do edital é compatível com a empresa.</small></div>
      <div class="campo"><label>Segmentos de atuação</label>
        <div class="linha-campos" style="row-gap:6px">
          ${ROTULOS.segmentosEmpresa.map(([k, v]) => `<label class="check"><input type="checkbox" class="seg-empresa" value="${k}"
            ${(e?.segmentos || "").split(",").map((s) => s.trim()).includes(k) ? "checked" : ""}> ${esc(v)}</label>`).join("")}
        </div>
        <small>Marcados a partir dos CNAEs; ajuste se precisar. Usado para sugerir exigências setoriais na análise (ex.: ANVISA para saúde, PNAE para educação).</small></div>
      <div class="campo"><label for="palavras_e">Palavras-chave para o radar</label><textarea id="palavras_e" name="palavras_chave" rows="3" placeholder="Ex.: limpeza, conservação predial, jardinagem">${esc(e?.palavras_chave || "")}</textarea>
        <small id="contador-palavras"></small>
        <div class="acoes" style="gap:4px">
          <button type="button" class="botao texto pequeno" id="sugerir-cnae" style="padding-left:0">Sugerir a partir dos CNAEs</button>
          <button type="button" class="botao texto pequeno" id="sugerir-palavras">Sugerir a partir dos segmentos</button></div></div>
      <div class="linha-campos">
        <div class="campo"><label for="ufs_e">Estados de interesse</label><input id="ufs_e" name="ufs" value="${esc(e?.ufs || "")}" placeholder="Ex.: SP, MG (em branco = todo o Brasil)"></div>
        <div class="campo"><label for="vmin_e">Valor mínimo (R$)</label><input id="vmin_e" name="valor_min" inputmode="decimal" value="${e?.valor_min ?? ""}"></div>
        <div class="campo"><label for="vmax_e">Valor máximo (R$)</label><input id="vmax_e" name="valor_max" inputmode="decimal" value="${e?.valor_max ?? ""}"></div></div>
      <div id="erro-empresa"></div><button class="botao" style="width:100%" type="submit">Salvar</button></form>`,
  });

  const campoPalavras = $("#palavras_e", m);
  const lista = (v) => v.split(",").map((x) => x.trim()).filter(Boolean);
  const juntar = (atuais, novas) => {
    const vistos = new Set(atuais.map((x) => x.toLowerCase()));
    return [...atuais, ...novas.filter((x) => !vistos.has(x.toLowerCase()) && vistos.add(x.toLowerCase()))];
  };
  const contar = () => {
    const n = lista(campoPalavras.value).length;
    $("#contador-palavras", m).textContent = !n ? "Separe por vírgula. São os termos buscados diariamente no PNCP."
      : n > 8 ? `${n} termos. O radar busca os 8 primeiros; deixe os mais importantes no começo.`
        : `${n} termo(s), separados por vírgula. São buscados diariamente no PNCP.`;
  };
  campoPalavras.addEventListener("input", contar);
  contar();

  let ultima = null; // última consulta à Receita, para o botão "Sugerir a partir dos CNAEs"
  const aplicarReceita = (d, { completo }) => {
    if (completo) {
      if (d.razao_social) $("#razao_e", m).value = d.razao_social;
      if (d.porte_codigo) $("#porte_e", m).value = d.porte_codigo;
      if (d.uf && !$("#ufs_e", m).value.trim()) $("#ufs_e", m).value = d.uf;
    }
    if (d.cnaes_texto) $("#cnaes_e", m).value = d.cnaes_texto;
    (d.sugestao?.segmentos || []).forEach((k) => { const c = $(`.seg-empresa[value="${k}"]`, m); if (c) c.checked = true; });
    campoPalavras.value = juntar(lista(campoPalavras.value), d.sugestao?.palavras_chave || []).join(", ");
    contar();
    const ativa = (d.situacao || "").toUpperCase() === "ATIVA";
    $("#receita-info", m).innerHTML = `<div class="aviso ${ativa ? "info" : "erro"}">
      <b>${esc(d.nome_fantasia || d.razao_social || "")}</b> · situação ${esc(d.situacao || "não informada")}${d.municipio ? ` · ${esc(d.municipio)}/${esc(d.uf || "")}` : ""}
      ${d.opcao_simples ? " · optante do Simples" : ""} · ${(d.cnaes || []).length} CNAE(s)
      ${ativa ? "" : "<br>Empresas com situação diferente de ATIVA não conseguem se habilitar em licitações."}
      <br><small>CNAEs, segmentos e palavras-chave foram sugeridos a partir da Receita. Revise antes de salvar.</small></div>`;
  };
  const buscar = async ({ completo, silencioso }) => {
    const cnpj = $("#cnpj_e", m).value.replace(/\D/g, "");
    if (cnpj.length !== 14) { if (!silencioso) toast("Digite os 14 números do CNPJ."); return; }
    const estado = $("#cnpj-estado", m);
    estado.textContent = "Consultando a Receita…";
    try {
      const d = await api("GET", `/api/cnpj/${cnpj}`);
      if (d.status === "ok") { ultima = d; aplicarReceita(d, { completo }); estado.textContent = ""; }
      else if (d.status === "nao_encontrado") estado.textContent = "CNPJ não encontrado na Receita. Preencha os dados manualmente.";
      else estado.textContent = "A consulta à Receita está indisponível agora. Preencha manualmente ou tente de novo.";
    } catch (err) { estado.textContent = err.message; }
  };
  const bc = $("#buscar-cnpj", m);
  bc.onclick = () => ocupado(bc, "Buscando…", () => buscar({ completo: !e }));
  if (!e) {
    let consultado = "";
    $("#cnpj_e", m).addEventListener("input", (ev) => {
      const n = ev.target.value.replace(/\D/g, "").slice(0, 14);
      ev.target.value = fmt.cnpj(n) || n;
      if (n.length === 14 && n !== consultado) { consultado = n; buscar({ completo: true, silencioso: true }); }
    });
  }
  $("#sugerir-cnae", m).onclick = async () => {
    if (!ultima) { await ocupado($("#sugerir-cnae", m), "Buscando…", () => buscar({ completo: false })); return; }
    campoPalavras.value = juntar(lista(campoPalavras.value), ultima.sugestao?.palavras_chave || []).join(", "); contar();
  };
  $("#sugerir-palavras", m).onclick = () => {
    const marcados = $$(".seg-empresa:checked", m).map((c) => c.value);
    if (!marcados.length) { toast("Marque ao menos um segmento primeiro."); return; }
    const sugestao = [...new Set(marcados.flatMap((k) => (PALAVRAS_POR_SEGMENTO[k] || "").split(",").map((s) => s.trim()).filter(Boolean)))];
    const campo = $("#palavras_e", m);
    const atuais = campo.value.split(",").map((s) => s.trim()).filter(Boolean);
    campo.value = [...new Set([...atuais, ...sugestao])].join(", ");
    contar();
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
