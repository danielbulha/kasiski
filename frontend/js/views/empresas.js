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
    ${e.termos_radar?.length ? `<p class="fraco">Radar busca: ${esc(e.termos_radar.join(", "))}</p>` : `<p class="fraco">Radar sem segmentos nem palavras-chave</p>`}</div>
    <div class="acoes"><button class="botao pequeno secundario" data-editar-emp="${e.id}">${icone("editar",14)} Editar</button>
      <button class="botao texto pequeno" data-excluir-emp="${e.id}">${icone("excluir",14)} Excluir</button></div></div>`;
}

// Mesmos termos de backend/services/cnae.py (TERMOS_SEGMENTO): os segmentos marcados entram direto na busca do radar.
const TERMOS_SEGMENTO = {
  obras: ["obras de engenharia", "reforma predial", "pavimentação", "construção"],
  servicos_continuados: ["limpeza", "conservação predial", "portaria", "recepção"],
  saude: ["medicamentos", "material hospitalar", "equipamentos médicos", "serviços de saúde"],
  educacao: ["material escolar", "merenda escolar", "transporte escolar", "mobiliário escolar"],
  ti: ["software", "tecnologia da informação", "equipamentos de informática", "licenciamento"],
  alimentacao: ["gêneros alimentícios", "fornecimento de refeições", "alimentação"],
  transporte: ["locação de veículos", "transporte", "combustível", "manutenção de frota"],
  seguranca: ["vigilância patrimonial", "segurança eletrônica", "monitoramento"],
};
const MAX_TERMOS_RADAR = 12;
function termosRadar(segmentos, palavras) {
  const norm = (t) => t.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").trim();
  const segs = segmentos.filter(Boolean), kws = palavras.split(",").map((x) => x.trim()).filter(Boolean);
  const termos = [], vistos = new Set();
  const add = (t) => { const k = norm(t); if (k && !vistos.has(k) && termos.length < MAX_TERMOS_RADAR) { vistos.add(k); termos.push(t); } };
  const dosSeg = [];
  for (let r = 0; r < 4; r++) segs.forEach((s) => { const l = TERMOS_SEGMENTO[s] || []; if (r < l.length) dosSeg.push(l[r]); });
  const teto = kws.length ? Math.floor(MAX_TERMOS_RADAR / 2) : MAX_TERMOS_RADAR;
  dosSeg.slice(0, teto).forEach(add); kws.forEach(add); dosSeg.slice(teto).forEach(add);
  return termos;
}

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
        <small>Sugeridos pelos CNAEs; marque e desmarque à vontade. <b>Os segmentos marcados entram direto na busca do radar</b> e orientam a nota de aderência e as exigências setoriais da análise (ex.: ANVISA para saúde, PNAE para educação).</small></div>
      <div class="campo"><label for="palavras_e">Palavras-chave para o radar</label><textarea id="palavras_e" name="palavras_chave" rows="3" placeholder="Ex.: limpeza, conservação predial, jardinagem">${esc(e?.palavras_chave || "")}</textarea>
        <small id="contador-palavras"></small>
        <div class="acoes" style="gap:4px">
          <button type="button" class="botao texto pequeno" id="sugerir-cnae" style="padding-left:0">Sugerir a partir dos CNAEs</button>
          </div>
        <div class="previa-radar" id="previa-radar" aria-live="polite"></div></div>
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
    $("#contador-palavras", m).textContent = !n ? "Opcional se houver segmento marcado. Separe por vírgula para detalhar o que buscar."
      : `${n} termo(s). Use para detalhar o que os segmentos não cobrem (ex.: jardinagem, controle de pragas).`;
    const segs = $$(".seg-empresa:checked", m).map((c) => c.value);
    const t = termosRadar(segs, campoPalavras.value);
    const fora = lista(campoPalavras.value).filter((x) => !t.some((y) => y.toLowerCase() === x.toLowerCase()));
    $("#previa-radar", m).innerHTML = t.length
      ? `<b>O radar vai buscar no PNCP:</b> ${t.map((x) => `<span class="chip-termo">${esc(x)}</span>`).join(" ")}${fora.length ? `<br><small class="fraco">Ficaram de fora (limite de ${MAX_TERMOS_RADAR} termos): ${esc(fora.join(", "))}. Remova termos menos importantes ou desmarque segmentos.</small>` : ""}`
      : `<span class="fraco">Marque um segmento ou escreva palavras-chave para o radar funcionar.</span>`;
  };
  campoPalavras.addEventListener("input", contar);
  $$(".seg-empresa", m).forEach((c) => c.addEventListener("change", contar));
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
  $("#form-empresa", m).onsubmit = async (ev) => {
    ev.preventDefault();
    const b = ev.target.querySelector("button[type=submit]");
    await ocupado(b, "Salvando…", async () => {
      try {
        const dados = dadosForm(ev.target);
        dados.segmentos = $$(".seg-empresa:checked", m).map((c) => c.value).join(",");
        const escopo = (x) => [x?.segmentos || "", (x?.palavras_chave || "").trim(), (x?.ufs || "").replace(/\s/g, "").toUpperCase(), String(x?.valor_min ?? ""), String(x?.valor_max ?? "")].join("|");
        const salvo = await api(e ? "PATCH" : "POST", e ? `/api/empresas/${e.id}` : "/api/empresas", dados);
        if (e && escopo(e) !== escopo(salvo) && salvo.termos_radar?.length) {
          toast("Radar ajustado aos novos segmentos. Buscando editais no PNCP…");
          api("POST", `/api/empresas/${salvo.id}/radar/atualizar`).then((r) => toast(`Radar atualizado: ${r.novos} edital(is) encontrado(s).`, "ok")).catch(() => {});
        }
        if (!e) marcar("company_created");
        if ((dados.palavras_chave || "").trim() && !(e && (e.palavras_chave || "").trim())) marcar("radar_configured");
        await carregarConta(); m.fechar(); V.empresas($("#conteudo"));
      } catch (err) { $("#erro-empresa", m).innerHTML = erroTela(err); }
    });
  };
}
