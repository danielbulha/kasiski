// Adaptador do Compras.gov.br: onde ficam, na tela da sala de disputa do fornecedor, os dados que a extensão lê.
//
// Seletores levantados no código público do aplicativo do portal (Angular, comprasnet-web, out/2026): componentes
// app-disputa-fornecedor / app-disputa-fornecedor-itens e os atributos data-test que o próprio portal usa nos testes
// (valor-geral, valor-fornec, situacao-item, tempo-restante). Ainda NÃO foram conferidos numa sala de disputa real:
// confira com o botão "Copiar estrutura da página" na primeira sessão. Se o portal mudar o layout, só este arquivo
// precisa ser atualizado.
const SELETORES_COMPRASGOV = {
  sala: "app-disputa-fornecedor",                                          // só existe na sala de disputa do fornecedor
  item: "app-disputa-fornecedor-itens .cp-itens-disputa",                  // cada item/grupo na lista da disputa
  itemNumero: "app-identificacao-item .dots > span:not(.text-uppercase):not(.pr-1)",  // número do item
  melhorLance: '[data-test="valor-geral"]',                                // "Melhor valor"
  meuLance: '[data-test="valor-fornec"]',                                  // "Meu valor"
  situacao: "i.fa-thumbs-up, i.fa-thumbs-down, i.fa-hand-paper",           // ganhando / perdendo / empatado (no title)
  posicao: "",                                                             // o portal mostra a situação, não a posição
  fase: '[data-test="situacao-item"]',                                     // fase do item (aberto para lances, encerrado...)
  tempo: '[data-test="tempo-restante"]',                                   // contagem do item
  mensagem: ".cp-mensagens-compra",                                        // cada mensagem do chat da compra
  mensagemHora: ".mensagens-data",
  mensagemTexto: ".mensagens-texto",
  mensagemItem: "",                                                        // o chat da compra não separa por item
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
    const itens = [...document.querySelectorAll(s.item)].map((b) => {
      const icone = dentro(b, s.situacao);
      const situacao = icone ? (icone.getAttribute("title") || (icone.classList.contains("fa-thumbs-up") ? "Ganhando"
        : icone.classList.contains("fa-thumbs-down") ? "Perdendo" : "Empatado")) : "";
      const fase = Kasiski.texto(dentro(b, s.fase)) || faseGeral;
      return {
        item: Kasiski.texto(dentro(b, s.itemNumero)),
        melhor_lance: Kasiski.valorBR(Kasiski.texto(dentro(b, s.melhorLance))),
        meu_lance: Kasiski.valorBR(Kasiski.texto(dentro(b, s.meuLance))),
        posicao: s.posicao ? Kasiski.valorBR(Kasiski.texto(dentro(b, s.posicao))) : null,   // ganhando/perdendo vai na fase
        fase: [fase, situacao].filter(Boolean).join(" · "),
      };
    }).filter((x) => x.item);
    const mensagens = s.mensagem ? [...document.querySelectorAll(s.mensagem)].map((m) => ({
      item: Kasiski.texto(dentro(m, s.mensagemItem)),
      hora: Kasiski.texto(dentro(m, s.mensagemHora)),
      texto: s.mensagemTexto ? Kasiski.texto(dentro(m, s.mensagemTexto)) : Kasiski.texto(m),
    })).filter((x) => x.texto) : [];
    return { itens, mensagens };
  },
};

window.KasiskiAdaptador = AdaptadorComprasGov;
