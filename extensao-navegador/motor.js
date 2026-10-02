// Motor de leitura: aplica na página a configuração do portal (adaptadores/padrao.json ou a versão baixada do
// Kasiski). A configuração é só dado — seletores CSS e nomes de colunas —, nunca código. A extensão só LÊ a tela.
const KasiskiMotor = (() => {
  const norm = (t) => String(t || "").normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/\s+/g, " ").trim().toLowerCase();
  const dentro = (raiz, sel) => (sel ? raiz.querySelector(sel) : null);

  function lerSeletores(L) {
    const faseGeral = L.fase ? Kasiski.texto(document.querySelector(L.fase)) : "";
    return [...document.querySelectorAll(L.item)].map((b) => {
      const icone = dentro(b, L.situacao);
      let situacao = "";
      if (icone) {
        situacao = icone.getAttribute("title") || "";
        if (!situacao) for (const [classe, texto] of Object.entries(L.situacaoTextos || {})) if (icone.classList.contains(classe)) situacao = texto;
      }
      const fase = Kasiski.texto(dentro(b, L.fase)) || faseGeral;
      return {
        item: Kasiski.texto(dentro(b, L.itemNumero)),
        melhor_lance: Kasiski.valorBR(Kasiski.texto(dentro(b, L.melhorLance))),
        meu_lance: Kasiski.valorBR(Kasiski.texto(dentro(b, L.meuLance))),
        posicao: L.posicao ? Kasiski.valorBR(Kasiski.texto(dentro(b, L.posicao))) : null,
        fase: [fase, situacao].filter(Boolean).join(" · "),
      };
    });
  }

  // Tabela sem marcadores: acha cada coluna pelo texto do cabeçalho (ex.: "Melhor proposta / Lance").
  function lerTabela(L, sala) {
    const cab = [...sala.querySelectorAll(L.cabecalho)].map((c) => norm(c.textContent));
    const idx = {};
    for (const [campo, rotulo] of Object.entries(L.colunas || {})) idx[campo] = cab.findIndex((h) => h.includes(norm(rotulo)));
    if (!(idx.item >= 0)) return [];
    return [...sala.querySelectorAll(L.linha)].map((linha) => {
      const cel = [...linha.querySelectorAll(L.celula)];
      const txt = (campo) => (idx[campo] >= 0 && cel[idx[campo]] ? Kasiski.texto(cel[idx[campo]]) : "");
      return {
        item: txt("item"),
        melhor_lance: Kasiski.valorBR(txt("melhorLance")),
        meu_lance: Kasiski.valorBR(txt("meuLance")),
        posicao: Kasiski.valorBR(txt("posicao")),
        fase: txt("fase"),
      };
    });
  }

  function lerMensagens(M) {
    if (!M?.mensagem) return [];
    return [...document.querySelectorAll(M.mensagem)].map((m) => ({
      item: Kasiski.texto(dentro(m, M.item)),
      hora: Kasiski.texto(dentro(m, M.hora)),
      texto: M.texto ? Kasiski.texto(dentro(m, M.texto)) : Kasiski.texto(m),
    })).filter((x) => x.texto);
  }

  return {
    // portal: um item de "portais" da configuração
    criar(portal) {
      const L = portal.leitura, M = portal.mensagens;
      return {
        nome: portal.nome,
        // { itens: [{item, melhor_lance, meu_lance, posicao, fase}], mensagens: [{item, hora, texto}] } ou null fora da sala
        ler() {
          if (!L) return { erro: "aguardando_configuracao" };
          const sala = document.querySelector(L.sala);
          if (!sala) return null;
          const itens = (L.tipo === "tabela" ? lerTabela(L, sala) : lerSeletores(L)).filter((x) => x.item);
          return { itens, mensagens: lerMensagens(M) };
        },
      };
    },
  };
})();
