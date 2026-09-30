// Tour guiado do primeiro acesso a cada plano. No Free, apresenta o caminho básico; ao subir de plano, mostra só
// o que o novo plano libera. O progresso fica no usuário (servidor), então não se repete em outro navegador.
// Pode ser pulado a qualquer momento e refeito em Plano e conta.
const _tourMenu = (h) => `#lateral a[href="${h}"]`;
const TOUR_PASSOS = {
  free: [
    { titulo: "Bem-vindo ao Kasiski", texto: "Em menos de 2 minutos você conhece o caminho: encontrar editais, decidir se vale participar, preparar a documentação e disputar sem perder prazo." },
    { alvo: _tourMenu("#/empresas"), titulo: "Sua empresa", texto: "Comece pelo CNPJ: o Kasiski puxa os dados da Receita, mostra o histórico de vitórias no PNCP e sugere os segmentos que o radar vai buscar." },
    { alvo: _tourMenu("#/radar"), titulo: "Radar de editais", texto: "O radar procura editais com propostas abertas que combinam com a empresa e dá uma nota de aderência de 0 a 100. No Free, 1 busca por dia com os 10 mais aderentes." },
    { alvo: _tourMenu("#/oportunidades"), titulo: "Oportunidades", texto: "Tudo o que você decidiu acompanhar fica aqui, com o andamento de cada licitação. Clique no cartão para o resumo e em \"Ver todos os detalhes\" para a análise, os prazos, os documentos e as peças." },
    { titulo: "DoubleCheck™", texto: "Uma IA analisa. Outra confere. Você decide. Cada exigência, risco e peça traz o selo DoubleCheck: Confirmado, Divergência ou Revisão recomendada. Clique no selo para ver as duas leituras e o trecho do edital.", dc: true },
    { alvo: _tourMenu("#/cofre"), titulo: "Cofre de documentos", texto: "Guarde certidões e documentos de habilitação com a validade. O Kasiski avisa antes de vencer e confere cada edital contra o que você tem." },
    { alvo: _tourMenu("#/agenda"), titulo: "Agenda de prazos", texto: "Esclarecimento, impugnação, sessão e recurso entram sozinhos na agenda. Confira sempre as datas no edital: o órgão às vezes cadastra errado no PNCP." },
    { alvo: "#primeiros-passos", rota: "#/painel", titulo: "Seus primeiros passos", texto: "Esta lista marca sozinha o que você já fez. Siga na ordem e, em poucos minutos, a primeira licitação estará analisada." },
  ],
  essencial: [
    { titulo: "Bem-vindo ao Essencial", texto: "Seu plano agora busca editais sozinho e sem limite, acompanha quantas licitações você quiser e analisa até 5 editais por mês com a IA. Veja o que mudou." },
    { alvo: _tourMenu("#/radar"), titulo: "Radar automático", texto: "Todo dia útil, cedo, o radar consulta o PNCP e traz todos os editais aderentes, não só os 10 primeiros. Exclua os de aderência baixa com um clique." },
    { alvo: _tourMenu("#/concorrentes"), titulo: "Concorrentes", texto: "Consulte o CNPJ de concorrentes: sanções, histórico de contratos e onde costumam vencer." },
  ],
  profissional: [
    { titulo: "Bem-vindo ao Profissional", texto: "Agora você tem as ferramentas para disputar e executar: preços, propostas, peças e contratos." },
    { alvo: _tourMenu("#/precos"), titulo: "Preços e propostas", texto: "Pesquise preços praticados em contratações públicas e monte a proposta comercial a partir do edital." },
    { alvo: _tourMenu("#/pecas"), titulo: "Peças", texto: "A IA redige esclarecimentos, impugnações, recursos e contrarrazões com base no edital e na lei, e o DoubleCheck™ (uma segunda IA) procura erro factual, argumento sem suporte e referência errada antes de chegar a você." },
    { alvo: _tourMenu("#/contratos"), titulo: "Gestão de contratos", texto: "Cadastre os contratos ganhos: vigência, pagamentos, reajustes e alertas de atraso." },
    { alvo: _tourMenu("#/conta"), titulo: "Equipe", texto: "Convide até 3 pessoas em Plano e conta → Equipe e distribua as licitações por responsável." },
  ],
  business: [
    { titulo: "Bem-vindo ao Business", texto: "Seu plano é para uma operação estruturada: mais empresas, mais pessoas e visão gerencial." },
    { alvo: _tourMenu("#/relatorios"), titulo: "Relatórios", texto: "Painel para a diretoria: funil de licitações, taxa de sucesso, valores disputados e contratos." },
    { alvo: "#sel-empresa", titulo: "Várias empresas", texto: "Cadastre até 3 empresas e troque entre elas aqui. Cada uma tem o seu radar, cofre e quadro." },
  ],
  consultor: [
    { titulo: "Bem-vindo ao Consultor", texto: "Feito para quem atende clientes: até 10 empresas e relatórios com a sua marca." },
    { alvo: _tourMenu("#/empresas"), titulo: "Empresas atendidas", texto: "Cadastre cada cliente pelo CNPJ. O seletor no topo do menu troca de empresa em um clique." },
    { alvo: _tourMenu("#/conta"), titulo: "Sua marca nos relatórios", texto: "Em Plano e conta, defina a marca do escritório que aparece nos relatórios impressos para os clientes." },
  ],
  enterprise: [
    { titulo: "Bem-vindo ao Enterprise", texto: "Sua operação tem limites ampliados e suporte dedicado. Fale com a gente para integrações e treinamento da equipe." },
  ],
};
const TOUR_ORDEM = ["free", "essencial", "profissional", "business", "consultor", "enterprise"];

// Planos cujo tour ainda falta, até o plano atual (quem entra direto num plano maior vê o básico também)
function tourPendentes() {
  const atual = S.plano?.codigo;
  const i = TOUR_ORDEM.indexOf(atual);
  if (i < 0 || !S.usuario) return [];
  const feito = S.usuario.tour || {};
  return TOUR_ORDEM.slice(0, i + 1).filter((p) => !feito[p]);
}

function montarPassosTour(planosTour) {
  // boas-vindas só do plano atual; depois os destaques de cada plano, na ordem; "primeiros passos" por último
  const boas = (TOUR_PASSOS[planosTour[planosTour.length - 1]] || []).find((x) => !x.alvo && !x.dc);
  const meio = [], fim = [];
  planosTour.forEach((p) => (TOUR_PASSOS[p] || []).forEach((x) => {
    if (!x.alvo && !x.dc) return;
    (x.alvo === "#primeiros-passos" ? fim : meio).push(x);
  }));
  return [...(boas ? [boas] : []), ...meio, ...fim];
}

function verificarTour() {
  if (verificarTour.aberto || document.querySelector(".tour-fundo")) return;
  const pend = tourPendentes();
  if (!pend.length || !S.empresas) return;
  iniciarTour(pend);
}

async function salvarTour(planosTour, estado) {
  S.usuario.tour = { ...(S.usuario.tour || {}) };
  planosTour.forEach((p) => { S.usuario.tour[p] = estado; });
  try { await api("PATCH", "/api/conta", { tour: { planos: planosTour, estado } }); } catch { /* segue: no pior caso aparece de novo */ }
}

function iniciarTour(planosTour, { manual = false } = {}) {
  const passos = montarPassosTour(planosTour);
  if (!passos.length) return;
  verificarTour.aberto = true;
  let i = 0;
  const fundo = document.createElement("div");
  fundo.className = "tour-fundo";
  fundo.innerHTML = `<div class="tour-foco" hidden></div>
    <div class="tour-balao" role="dialog" aria-modal="true" aria-labelledby="tour-titulo" tabindex="-1">
      <small class="tour-passo"></small><h2 id="tour-titulo"></h2><p class="tour-texto"></p>
      <div class="tour-acoes"><button type="button" class="botao texto pequeno" data-tour="pular">Pular o tour</button>
        <span class="tour-dir"><button type="button" class="botao secundario pequeno" data-tour="voltar">Voltar</button>
        <button type="button" class="botao pequeno" data-tour="seguir">Próximo</button></span></div></div>`;
  document.body.appendChild(fundo);
  document.body.classList.add("tour-ativo");
  const foco = $(".tour-foco", fundo), balao = $(".tour-balao", fundo);
  const fechar = (estado) => {
    fundo.remove(); document.body.classList.remove("tour-ativo"); document.removeEventListener("keydown", tecla); window.removeEventListener("resize", posicionar);
    verificarTour.aberto = false;
    $("#lateral")?.classList.remove("aberta");
    $$(".tour-alvo").forEach((x) => x.classList.remove("tour-alvo"));
    if (!manual || estado === "concluido") salvarTour(planosTour, estado);
    if (estado === "concluido") toast("Pronto! Você pode refazer o tour em Plano e conta.", "ok");
  };
  const tecla = (ev) => {
    if (ev.key === "Escape") fechar("pulado");
    else if (ev.key === "ArrowRight") seguir();
    else if (ev.key === "ArrowLeft" && i > 0) mostrar(i - 1);
  };
  let alvoAtual = null;
  function posicionar() {
    const movel = window.innerWidth <= 800;
    const r = alvoAtual && alvoAtual.getBoundingClientRect();
    const visivel = r && r.width > 0 && r.height > 0 && r.bottom > 0 && r.top < window.innerHeight && r.right > 0 && r.left < window.innerWidth;
    if (!visivel) {
      foco.hidden = true; fundo.classList.add("sem-alvo");
      balao.style.left = balao.style.top = ""; balao.classList.remove("topo"); balao.classList.toggle("centro", !movel); balao.classList.toggle("base", movel);
      return;
    }
    fundo.classList.remove("sem-alvo"); balao.classList.remove("centro", "base", "topo");
    const m = 6;
    Object.assign(foco.style, { left: `${r.left - m}px`, top: `${r.top - m}px`, width: `${r.width + 2 * m}px`, height: `${r.height + 2 * m}px` });
    foco.hidden = false;
    if (movel) { // no celular o balão fica embaixo ou em cima, do lado oposto ao item destacado
      const emCima = r.top + r.height / 2 > window.innerHeight / 2;
      balao.classList.toggle("topo", emCima); balao.classList.toggle("base", !emCima);
      balao.style.left = balao.style.top = ""; return;
    }
    const w = balao.offsetWidth, h = balao.offsetHeight;
    let left = r.right + 16, top = r.top + r.height / 2 - h / 2;
    if (left + w > window.innerWidth - 12) { left = Math.max(12, r.left + r.width / 2 - w / 2); top = r.bottom + 14; }
    if (top + h > window.innerHeight - 12) top = Math.max(12, r.top - h - 14);
    balao.style.left = `${Math.max(12, Math.min(left, window.innerWidth - w - 12))}px`;
    balao.style.top = `${Math.max(12, top)}px`;
  }
  async function mostrar(n) {
    i = n;
    const p = passos[i];
    if (p.rota && location.hash.split("?")[0] !== p.rota) {
      location.hash = p.rota;
      for (let k = 0; k < 30 && !document.querySelector(p.alvo); k++) await new Promise((ok) => setTimeout(ok, 100));
    }
    $$(".tour-alvo").forEach((x) => x.classList.remove("tour-alvo"));
    const lateral = $("#lateral");
    if (lateral && window.innerWidth <= 800) {
      const abrir = Boolean(p.alvo && p.alvo.startsWith("#lateral"));
      if (lateral.classList.contains("aberta") !== abrir) {
        lateral.classList.toggle("aberta", abrir);
        await new Promise((ok) => setTimeout(ok, 260)); // espera a animação do menu antes de medir
      }
    }
    alvoAtual = p.alvo ? document.querySelector(p.alvo) : null;
    if (alvoAtual) { alvoAtual.classList.add("tour-alvo"); alvoAtual.scrollIntoView({ block: "nearest" }); }
    $(".tour-passo", balao).textContent = `${i + 1} de ${passos.length}`;
    $("#tour-titulo", balao).innerHTML = (p.dc ? dcSimbolo(20) + " " : "") + esc(p.titulo);
    $(".tour-texto", balao).textContent = p.texto;
    $('[data-tour="voltar"]', balao).hidden = i === 0;
    $('[data-tour="seguir"]', balao).textContent = i === passos.length - 1 ? "Concluir" : i === 0 ? "Começar" : "Próximo";
    posicionar();
    balao.focus({ preventScroll: true });
  }
  const seguir = () => (i >= passos.length - 1 ? fechar("concluido") : mostrar(i + 1));
  $('[data-tour="seguir"]', balao).onclick = seguir;
  $('[data-tour="voltar"]', balao).onclick = () => mostrar(Math.max(0, i - 1));
  $('[data-tour="pular"]', balao).onclick = () => fechar("pulado");
  document.addEventListener("keydown", tecla);
  window.addEventListener("resize", posicionar);
  mostrar(0);
}

// "Refazer o tour" (Plano e conta): mostra de novo o básico e tudo o que o plano atual inclui
function refazerTour() {
  const i = TOUR_ORDEM.indexOf(S.plano?.codigo);
  if (i < 0) return;
  location.hash = "#/painel";
  setTimeout(() => iniciarTour(TOUR_ORDEM.slice(0, i + 1), { manual: true }), 400);
}
