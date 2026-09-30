// KASISKI DoubleCheck™: protocolo de verificação cruzada. Uma IA analisa, outra confere, você decide.
// Três estados, sempre com símbolo + texto (a cor nunca é a única pista):
//   confirmado  (✓)  os modelos convergiram       — ciano
//   divergencia (⇄)  interpretações diferentes    — contorno ciano, fundo claro
//   revisao     (!)  análise humana recomendada   — azul profundo
// Na interface não aparecem nomes de fornecedores de IA: "KASISKI Analysis Engine" e "KASISKI Verification Engine".

// Símbolo: três linhas (o documento e as duas leituras) convergem para um ponto de verificação e seguem adiante.
function dcSimbolo(tam = 18, { seta = false } = {}) {
  const w = seta ? 44 : 38;
  return `<svg class="dc-simbolo" width="${Math.round((tam * w) / 28)}" height="${tam}" viewBox="0 0 ${w} 28" fill="none" aria-hidden="true" focusable="false">
    <path d="M6 5c8 0 10 9 18 9M6 23c8 0 10-9 18-9" stroke="var(--dc-linha, #11B8C8)" stroke-width="2.4" stroke-linecap="round"/>
    <path d="M6 14h18" stroke="var(--dc-apoio, #91A5B3)" stroke-width="2.4" stroke-linecap="round"/>
    <circle cx="4" cy="5" r="2.6" fill="var(--dc-linha, #11B8C8)"/><circle cx="4" cy="23" r="2.6" fill="var(--dc-linha, #11B8C8)"/><circle cx="4" cy="14" r="2.6" fill="var(--dc-apoio, #91A5B3)"/>
    <circle cx="29.5" cy="14" r="4.6" stroke="currentColor" stroke-width="2.6"/>
    ${seta ? `<path d="M35.5 14H42M39 10.8 42.2 14 39 17.2" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>` : ""}
  </svg>`;
}

const DC_ESTADOS = {
  confirmado: { rotulo: "Confirmado", marca: "✓", titulo: "Concordância entre modelos", texto: "O verificador independente chegou à mesma conclusão, com a fonte localizada." },
  divergencia: { rotulo: "Divergência", marca: "⇄", titulo: "Divergência identificada", texto: "Os modelos chegaram a interpretações diferentes. Confira a fonte antes de decidir." },
  revisao: { rotulo: "Revisão recomendada", marca: "!", titulo: "Revisão humana recomendada", texto: "O documento não permitiu concluir com segurança. Verifique a fonte." },
};

// Aceita verificações novas ({estado}) e antigas ({confirmado: true/false/null})
function dcEstado(v) {
  if (!v) return null;
  if (DC_ESTADOS[v.estado]) return v.estado;
  return v.confirmado === true ? "confirmado" : v.confirmado === false ? "divergencia" : "revisao";
}

// Guarda o contexto de cada selo para abrir o detalhe da verificação sem refazer a consulta
const DC_ITENS = new Map();
let dcSeq = 0;

function dcSelo(v, primaria = {}, { compacto = false } = {}) {
  const est = dcEstado(v);
  if (!est) return "";
  const chave = `dc${++dcSeq}`;
  DC_ITENS.set(chave, { v, primaria, estado: est });
  const e = DC_ESTADOS[est];
  return `<button type="button" class="dc-selo dc-${est}${compacto ? " compacto" : ""}" data-dc="${chave}" title="${esc(e.titulo)} — ver a verificação">
    ${dcSimbolo(compacto ? 13 : 15)}<span class="dc-nome">DoubleCheck<sup>™</sup></span><span class="dc-estado">${esc(e.rotulo)}</span><span class="dc-marca" aria-hidden="true">${e.marca}</span></button>`;
}

// Linha completa abaixo de um apontamento: selo + fonte + confiança + "Ver verificação"
function dcLinha(v, primaria = {}) {
  const est = dcEstado(v);
  if (!est) return "";
  const pag = v.pagina || primaria.pagina;
  const conf = est === "confirmado" ? "Alta" : est === "divergencia" ? "Baixa" : "Indefinida";
  return `<div class="dc-linha">${dcSelo(v, primaria)}
    <span class="dc-meta"><small>Fonte</small>${pag ? `Pág. ${esc(pag)}` : esc(primaria.origem || "Documento")}${primaria.fonte ? ` · ${esc(primaria.fonte)}` : ""}</span>
    <span class="dc-meta"><small>Confiança</small>${conf} <i class="dc-barras b${est}" aria-hidden="true"><b></b><b></b><b></b></i></span>
    ${v.leitura_alternativa && est === "divergencia" ? `<span class="dc-alt"><b>Leitura do verificador:</b> ${esc(v.leitura_alternativa)}</span>` : ""}</div>`;
}

function modalDoubleCheck(chave) {
  const it = DC_ITENS.get(chave);
  if (!it) return;
  const { v, primaria, estado } = it;
  const e = DC_ESTADOS[estado];
  const pag = v.pagina || primaria.pagina;
  modal({ titulo: "KASISKI DoubleCheck™", corpo: `
    <div class="dc-detalhe">
      <ol class="dc-trilha">
        <li><span class="dc-ponto">${dcSimbolo(14)}</span><div><b>Análise primária</b><small>KASISKI Analysis Engine</small>
          ${primaria.titulo ? `<p><b>${esc(primaria.titulo)}</b></p>` : ""}${primaria.texto ? `<p>${esc(primaria.texto)}</p>` : ""}
          ${pag ? `<p class="fraco">Fonte indicada: pág. ${esc(pag)}</p>` : ""}</div></li>
        <li><span class="dc-ponto verif" aria-hidden="true"></span><div><b>Verificação independente</b><small>${esc(v.motor || "KASISKI Verification Engine")}</small>
          <p>${esc(v.comentario || "Sem comentário do verificador.")}</p>
          ${v.leitura_alternativa ? `<p><b>Outra leitura possível:</b> ${esc(v.leitura_alternativa)}</p>` : ""}</div></li>
        <li><span class="dc-ponto res dc-${estado}" aria-hidden="true">${e.marca}</span><div><b>Resultado</b>
          <p><span class="dc-resultado dc-${estado}">${esc(e.titulo)}</span></p><p class="fraco">${esc(e.texto)}</p>
          ${estado === "confirmado" ? `<p class="fraco">2 análises independentes · fonte rastreável</p>` : ""}</div></li>
      </ol>
      ${v.trecho ? `<figure class="dc-trecho"><figcaption>Trecho do documento${pag ? ` · pág. ${esc(pag)}` : ""}</figcaption><blockquote>“${esc(v.trecho)}”</blockquote></figure>` : ""}
      <p class="dc-aviso">O DoubleCheck reduz o risco de inconsistências, mas não garante a ausência de erros. A decisão é sempre sua.</p>
    </div>`, acoes: `<button class="botao" data-fechar>Entendi</button>` });
}

// Rodapé para relatórios impressos e peças
function dcRodape() {
  return `<p class="dc-rodape">${dcSimbolo(12)} <b>KASISKI DoubleCheck™</b> — as conclusões com o selo DoubleCheck passaram pelo protocolo de verificação cruzada automatizada da plataforma.
    O processo reduz o risco de inconsistências, mas não constitui garantia de ausência de erros nem substitui a avaliação profissional.</p>`;
}

// Resumo para o painel e para o topo da análise
function dcResumoHtml(n, { titulo = "DoubleCheck™", sub = "" } = {}) {
  if (!n || !n.total) return "";
  return `<div class="dc-resumo" role="group" aria-label="Resumo do DoubleCheck">
    <div class="dc-resumo-cab">${dcSimbolo(20)}<div><b>${esc(titulo)}</b>${sub ? `<small>${esc(sub)}</small>` : ""}</div></div>
    <ul><li class="dc-confirmado"><b>${n.confirmado}</b> ✓ concordância${n.confirmado === 1 ? "" : "s"}</li>
      <li class="dc-divergencia"><b>${n.divergencia}</b> ⇄ divergência${n.divergencia === 1 ? "" : "s"} detectada${n.divergencia === 1 ? "" : "s"}</li>
      <li class="dc-revisao"><b>${n.revisao}</b> ! revis${n.revisao === 1 ? "ão recomendada" : "ões recomendadas"}</li></ul></div>`;
}

// Um único ouvinte para todos os selos da página
document.addEventListener("click", (ev) => {
  const b = ev.target.closest("[data-dc]");
  if (b) { ev.preventDefault(); ev.stopPropagation(); modalDoubleCheck(b.dataset.dc); }
});
