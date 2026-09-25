// Página inicial pública (visitantes sem login): apresentação, recursos, setores, planos e dúvidas.
// Tom de voz conforme o manual da marca: precisa, clara, proativa e sóbria — sem superlativos.

const PLANOS_RESERVA = { // usado só se a API estiver fora do ar; a fonte oficial é GET /api/planos
  trial: { nome: "Teste grátis", preco: 0, empresas: 1, analises: 2, concorrentes: 1, pecas: true, precos: true, contratos: true, marca: false },
  essencial: { nome: "Essencial", preco: 197, empresas: 1, analises: 5, concorrentes: 0, pecas: false, precos: false, contratos: true, marca: false },
  profissional: { nome: "Profissional", preco: 497, empresas: 1, analises: 20, concorrentes: 5, pecas: true, precos: true, contratos: true, marca: false },
  consultor: { nome: "Consultor", preco: 1290, empresas: 10, analises: 60, concorrentes: 30, pecas: true, precos: true, contratos: true, marca: true },
};

const PUBLICO_PLANO = {
  essencial: "Para quem está começando a licitar",
  profissional: "Para empresas que disputam todo mês",
  consultor: "Para escritórios e consultorias de licitação",
};

V.inicio = async (raiz) => {
  rastrear("visita");
  let planos = PLANOS_RESERVA, trialDias = 7;
  try { const d = await api("GET", "/api/planos"); planos = d.planos; trialDias = d.trial_dias; } catch { /* segue com a reserva */ }
  const pago = ["essencial", "profissional", "consultor"].filter((k) => planos[k]);
  const trial = planos.trial || PLANOS_RESERVA.trial;

  raiz.innerHTML = `
  <div class="lp">
    <header class="lp-topo">
      <div class="lp-conteiner lp-topo-linha">
        <a class="lp-marca" href="#/">${simboloMarca(26)}<span class="texto"><strong>${esc(CERTAME.NOME)}</strong><span>public market intelligence</span></span></a>
        <nav class="lp-ancoras" aria-label="Seções">
          <button data-rolar="como">Como funciona</button><button data-rolar="recursos">Recursos</button>
          <button data-rolar="planos">Planos</button><button data-rolar="duvidas">Dúvidas</button>
        </nav>
        <div class="lp-topo-acoes"><a class="lp-link" href="#/entrar">Entrar</a><a class="botao" href="#/cadastro">Testar grátis</a></div>
      </div>
    </header>

    <section class="lp-hero">
      <div class="lp-conteiner lp-hero-grade">
        <div>
          <p class="lp-sobretitulo">Encontre o padrão. Descubra a oportunidade.</p>
          <h1>Inteligência para vender ao poder público.</h1>
          <p class="lp-lead">O Kasiski monitora os editais publicados no PNCP, confere a habilitação da sua empresa,
            analisa concorrentes e redige impugnações e recursos — com cada conclusão da IA conferida por um segundo modelo.</p>
          <div class="lp-cta">
            <a class="botao lp-botao-grande" href="#/cadastro">${icone("chevronDireita")} Testar grátis por ${trialDias} dias</a>
            <button class="botao secundario lp-botao-grande" data-rolar="planos">Ver planos</button>
          </div>
          <p class="lp-nota">${trial.analises} análises de edital incluídas no teste · sem cartão de crédito · cancele quando quiser</p>
        </div>
        ${previaProduto()}
      </div>
    </section>

    <section class="lp-faixa" id="como">
      <div class="lp-conteiner">
        <p class="lp-rotulo">Do ruído ao sinal</p>
        <h2>Milhares de editais por semana. Poucos fazem sentido para você.</h2>
        <div class="lp-passos">
          ${passo("01", "Detectar", "Todo dia útil, o radar consulta o PNCP e separa os editais abertos que combinam com as palavras-chave, os estados e a faixa de valor da sua empresa.")}
          ${passo("02", "Interpretar", "A análise lê o edital inteiro, extrai exigências e prazos, compara a habilitação com os documentos do seu cofre e aponta cláusulas restritivas.")}
          ${passo("03", "Agir", "Você recebe a recomendação de participar ou não, os prazos na agenda e a minuta da peça pronta para revisão — esclarecimento, impugnação ou recurso.")}
        </div>
      </div>
    </section>

    <section class="lp-secao" id="recursos">
      <div class="lp-conteiner">
        <p class="lp-rotulo">Recursos</p>
        <h2>Tudo o que a disputa exige, do edital ao contrato.</h2>
        <div class="lp-recursos">
          ${recurso("radar", "Radar de editais", "Busca diária no PNCP com nota de aderência de 0 a 100 para cada edital encontrado.")}
          ${recurso("editais", "Análise do edital", "Resumo, checklist de habilitação, riscos e recomendação de participar, com a página de cada ponto.")}
          ${recurso("ok", "Verificação cruzada", "Um modelo de IA analisa, outro de fornecedor diferente confere. O que não se confirma, você vê como não confirmado.")}
          ${recurso("cofre", "Cofre de habilitação", "Certidões e atestados com controle de validade. Alerta antes de vencer, não depois.")}
          ${recurso("concorrentes", "Inteligência de concorrentes", "Dossiê público do CNPJ, sanções no TCU e na CGU e análise da habilitação e da proposta do adversário.")}
          ${recurso("pecas", "Gerador de peças", "Minutas de esclarecimento, impugnação, recurso, contrarrazões, reequilíbrio e defesa prévia.")}
          ${recurso("agenda", "Agenda de prazos", "Prazos da Lei 14.133 contados em dias úteis, com feriados nacionais, a partir da data da sessão.")}
          ${recurso("contratos", "Contratos e pagamentos", "Vigência, garantia, reajuste e notas em atraso — com a peça de cobrança a um clique.")}
          ${recurso("precos", "Preços praticados", "Mediana e faixa competitiva a partir de compras públicas já homologadas.")}
        </div>
      </div>
    </section>

    <section class="lp-secao lp-secao-clara">
      <div class="lp-conteiner">
        <p class="lp-rotulo">Setores</p>
        <h2>Regras gerais da Lei 14.133 e exigências de cada setor.</h2>
        <p class="lp-texto">Além da habilitação padrão, a análise considera as exigências regulatórias do tipo de objeto e do segmento — como ANVISA na saúde, PNAE na educação, ART/RRT em obras e autorização da Polícia Federal na vigilância.</p>
        <div class="lp-setores">
          ${["Obras e engenharia", "Serviços continuados", "Fornecimento e registro de preços", "Saúde", "Educação", "Tecnologia da informação", "Segurança e vigilância", "Transporte e frota", "Alimentação", "Dispensa e inexigibilidade"]
            .map((s) => `<span>${esc(s)}</span>`).join("")}
        </div>
      </div>
    </section>

    <section class="lp-destaque">
      <div class="lp-conteiner lp-destaque-grade">
        <div>
          <p class="lp-sobretitulo">Teste grátis</p>
          <h2>${trialDias} dias para analisar editais reais da sua empresa.</h2>
          <p>O teste inclui ${trial.analises} análises completas de edital, ${trial.concorrentes} análise de concorrente, o gerador de peças e a inteligência de preços. Não pedimos cartão de crédito. No fim do período, seus dados continuam salvos.</p>
        </div>
        <div class="lp-destaque-cta"><a class="botao lp-botao-grande lp-botao-ciano" href="#/cadastro">Criar conta grátis</a></div>
      </div>
    </section>

    <section class="lp-secao" id="planos">
      <div class="lp-conteiner">
        <p class="lp-rotulo">Planos</p>
        <h2>Preço fixo por mês. Sem taxa de êxito.</h2>
        <div class="lp-planos">${pago.map((k) => cartaoPlano(k, planos[k])).join("")}</div>
        <p class="lp-nota lp-centro">Valores mensais. Análises adicionais podem ser contratadas em pacotes avulsos.</p>
      </div>
    </section>

    <section class="lp-secao lp-secao-clara" id="duvidas">
      <div class="lp-conteiner lp-estreito">
        <p class="lp-rotulo">Dúvidas frequentes</p>
        <h2>Antes de começar</h2>
        ${duvida("O Kasiski substitui um advogado?", "Não. As peças são minutas fundamentadas para você revisar antes de protocolar. Se preferir, é possível solicitar dentro do sistema a revisão por advogado, contratada à parte.")}
        ${duvida("De onde vêm os dados?", "De fontes públicas oficiais: PNCP (editais, contratos e atas), Receita Federal (dados cadastrais), TCU e Portal da Transparência (sanções) e Compras.gov.br (preços praticados). Editais fora do PNCP podem ser enviados em PDF.")}
        ${duvida("Como a IA evita erros?", "Cada cláusula restritiva, risco ou falha de concorrente apontada por um modelo é conferida por um segundo modelo, de outro fornecedor. O resultado da conferência aparece ao lado de cada ponto, com a página do documento de origem.")}
        ${duvida("Funciona para dispensa e inexigibilidade?", "Sim. Nesses casos o sistema não aplica os prazos de pregão: calcula o prazo de divulgação do aviso de contratação direta e avalia se a hipótese legal está bem enquadrada.")}
        ${duvida("Posso atender várias empresas?", "Sim, no plano Consultor: até 10 CNPJs na mesma conta, com cofre, radar e agenda separados por empresa, painel consolidado e relatórios com a marca do seu escritório.")}
        ${duvida("Meus documentos ficam separados de outras empresas?", "Sim. Cada conta só acessa as próprias empresas, editais e documentos.")}
        ${duvida("Preciso de cartão para testar?", `Não. O teste de ${trialDias} dias é gratuito e não pede cartão. Para continuar depois, basta escolher um plano.`)}
      </div>
    </section>

    <section class="lp-final">
      <div class="lp-conteiner lp-centro">
        <h2>Encontre o padrão. Descubra a oportunidade.</h2>
        <p>Comece com ${trial.analises} análises gratuitas e veja o que o Kasiski encontra nos editais do seu setor.</p>
        <a class="botao lp-botao-grande lp-botao-ciano" href="#/cadastro">Testar grátis por ${trialDias} dias</a>
      </div>
    </section>

    <footer class="lp-rodape">
      <div class="lp-conteiner lp-rodape-linha">
        <span class="lp-marca">${simboloMarca(20)}<span class="texto"><strong>${esc(CERTAME.NOME)}</strong><span>public market intelligence</span></span></span>
        <span>Rua Pamplona, 145, Conj. 02 - Jardim Paulista - São Paulo/SP - CEP 01405-900</span>
        <span><a href="#/entrar">Entrar</a> · <a href="#/cadastro">Criar conta</a></span>
      </div>
    </footer>
  </div>`;

  $$("[data-rolar]", raiz).forEach((b) => b.onclick = () => {
    document.getElementById(b.dataset.rolar)?.scrollIntoView({ behavior: "smooth", block: "start" });
  });
};

function passo(n, titulo, texto) {
  return `<div class="lp-passo"><span class="lp-passo-n">${n}</span><h3>${esc(titulo)}</h3><p>${esc(texto)}</p></div>`;
}

function recurso(ic, titulo, texto) {
  return `<div class="lp-recurso"><span class="icone-caixa">${icone(ic)}</span><h3>${esc(titulo)}</h3><p>${esc(texto)}</p></div>`;
}

function duvida(p, r) {
  return `<details class="lp-duvida"><summary>${esc(p)}</summary><p>${esc(r)}</p></details>`;
}

function cartaoPlano(codigo, v) {
  const destaque = codigo === "profissional";
  const item = (ok, texto) => `<li class="${ok ? "" : "fora"}">${icone(ok ? "ok" : "fechar", 15)} ${esc(texto)}</li>`;
  const qtd = (n, s, p) => `${n} ${n === 1 ? s : p}`;
  return `<div class="lp-plano ${destaque ? "destaque" : ""}">
    ${destaque ? `<span class="lp-selo">Indicado para PMEs</span>` : ""}
    <h3>${esc(v.nome)}</h3>
    <p class="lp-plano-publico">${esc(PUBLICO_PLANO[codigo] || "")}</p>
    <p class="lp-preco">${fmt.moeda(v.preco).replace(",00", "")}<small>/mês</small></p>
    <ul>
      ${item(true, qtd(v.empresas, "empresa (CNPJ)", "empresas (CNPJs)"))}
      ${item(true, `${qtd(v.analises, "análise", "análises")} de edital por mês`)}
      ${item(!!v.concorrentes, v.concorrentes ? `${qtd(v.concorrentes, "análise", "análises")} de concorrente por mês` : "Análise de concorrentes")}
      ${item(true, "Radar diário, cofre e agenda de prazos")}
      ${item(!!v.pecas, "Gerador de peças")}
      ${item(!!v.precos, "Preços praticados")}
      ${item(!!v.contratos, "Gestão de contratos")}
      ${v.marca ? item(true, "Relatórios com a marca do escritório") : ""}
    </ul>
    <a class="botao ${destaque ? "" : "secundario"}" href="#/cadastro">Começar pelo teste grátis</a>
  </div>`;
}

// Prévia estática do produto no topo da página: o visual "capa de processo" com carimbos.
function previaProduto() {
  const linha = (txt, rot, tipo) => `<div class="lp-previa-linha"><span>${esc(txt)}</span>${carimbo(rot, tipo)}</div>`;
  return `<div class="lp-previa" aria-hidden="true">
    <div class="lp-previa-capa">
      <div><small>Pregão eletrônico 45/2026 · Prefeitura Municipal</small><b>Serviços contínuos de limpeza predial</b></div>
      ${carimbo("Com ressalvas", "aviso", true)}
    </div>
    <div class="lp-previa-corpo">
      <p class="lp-previa-titulo">Checklist de habilitação</p>
      ${linha("CND federal conjunta", "Atende", "ok")}
      ${linha("CRF do FGTS", "Atende", "ok")}
      ${linha("CNDT", "Vencido", "erro")}
      ${linha("Atestado de capacidade técnica", "Falta", "erro")}
      <p class="lp-previa-titulo">Cláusula restritiva</p>
      <div class="lp-previa-ponto"><b>Atestado de 100% da área licitada</b><span>Lei 14.133, art. 67, §2º · pág. 15</span>
        <span class="lp-previa-verif">Verificação cruzada ${carimbo("Confirmado", "ok")}</span></div>
      <p class="lp-previa-titulo">Prazos</p>
      ${linha("Último dia para impugnar", "Em 4 dias", "aviso")}
    </div>
  </div>`;
}
