// Adaptador do Compras.gov.br: onde ficam, na tela da sala de disputa do fornecedor, os dados que a extensão lê.
//
// PREENCHER com a página real: ainda não temos uma cópia da sala de disputa logada, então os seletores abaixo
// estão vazios e a extensão fica em "aguardando configuração" (não envia nada). Para preencher, use o botão
// "Copiar estrutura da página" no popup da extensão durante uma sessão (os números saem mascarados) ou salve a
// página e envie ao time do Kasiski. Se o portal mudar o layout, só este arquivo precisa ser atualizado.
const SELETORES_COMPRASGOV = {
  sala: "",          // elemento que só existe na sala de disputa (evita ler outras telas do portal)
  item: "",          // cada bloco/linha de item ou lote na sala
  itemNumero: "",    // dentro do bloco do item: número do item
  melhorLance: "",   // dentro do bloco do item: melhor lance (valor ou desconto)
  meuLance: "",      // dentro do bloco do item: o seu último lance
  posicao: "",       // dentro do bloco do item: sua posição/classificação
  fase: "",          // dentro do bloco do item (ou na página): situação da disputa (aberta, prorrogação, encerrada...)
  mensagem: "",      // cada mensagem do pregoeiro/sistema
  mensagemHora: "",  // dentro da mensagem: data/hora
  mensagemTexto: "", // dentro da mensagem: texto
  mensagemItem: "",  // dentro da mensagem (opcional): item a que a mensagem se refere
};

const AdaptadorComprasGov = {
  nome: "Compras.gov.br",
  seletores: SELETORES_COMPRASGOV,
  configurado() {
    const s = this.seletores;
    return Boolean(s.sala && s.item && s.itemNumero && (s.melhorLance || s.meuLance));
  },
  // { itens: [{item, melhor_lance, meu_lance, posicao, fase}], mensagens: [{item, hora, texto}] } ou null fora da sala
  ler() {
    const s = this.seletores;
    if (!this.configurado()) return { erro: "aguardando_configuracao" };
    if (!document.querySelector(s.sala)) return null;
    const dentro = (raiz, sel) => (sel ? raiz.querySelector(sel) : null);
    const faseGeral = s.fase ? Kasiski.texto(document.querySelector(s.fase)) : "";
    const itens = [...document.querySelectorAll(s.item)].map((b) => ({
      item: Kasiski.texto(dentro(b, s.itemNumero)),
      melhor_lance: Kasiski.valorBR(Kasiski.texto(dentro(b, s.melhorLance))),
      meu_lance: Kasiski.valorBR(Kasiski.texto(dentro(b, s.meuLance))),
      posicao: Kasiski.valorBR(Kasiski.texto(dentro(b, s.posicao))),
      fase: Kasiski.texto(dentro(b, s.fase)) || faseGeral,
    })).filter((x) => x.item);
    const mensagens = s.mensagem ? [...document.querySelectorAll(s.mensagem)].map((m) => ({
      item: Kasiski.texto(dentro(m, s.mensagemItem)),
      hora: Kasiski.texto(dentro(m, s.mensagemHora)),
      texto: s.mensagemTexto ? Kasiski.texto(dentro(m, s.mensagemTexto)) : Kasiski.texto(m),
    })).filter((x) => x.texto) : [];
    return { itens, mensagens };
  },
};

window.KasiskiAdaptador = AdaptadorComprasGov;
