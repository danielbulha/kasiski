// Gráficos leves em HTML/CSS (sem biblioteca externa): colunas por mês, barras horizontais e indicadores.
// Regras: uma cor por série na ordem fixa (--serie-1, --serie-2, validadas para daltonismo), legenda com 2+ séries,
// rótulo direto só no maior valor, dica ao passar o mouse ou focar pelo teclado e sempre uma tabela com os números.
const CORES_SERIE = ["var(--serie-1)", "var(--serie-2)"];

function _dicaGrafico() {
  let d = document.getElementById("g-dica");
  if (!d) {
    d = document.createElement("div");
    d.id = "g-dica"; d.className = "g-dica"; d.setAttribute("role", "tooltip"); d.hidden = true;
    document.body.appendChild(d);
  }
  return d;
}

function ligarDicas(raiz) {
  const dica = _dicaGrafico();
  const mostrar = (alvo) => {
    const linhas = JSON.parse(alvo.dataset.dica || "[]");
    dica.replaceChildren();
    linhas.forEach(([rotulo, valor, cor], i) => {
      const l = document.createElement("div");
      l.className = i === 0 && !cor ? "g-dica-titulo" : "g-dica-linha";
      if (cor) { const k = document.createElement("i"); k.style.background = cor; l.appendChild(k); }
      const v = document.createElement("b"); v.textContent = valor ?? "";
      const r = document.createElement("span"); r.textContent = rotulo;
      if (i === 0 && !cor) l.appendChild(r); else { l.appendChild(v); l.appendChild(r); }
      dica.appendChild(l);
    });
    const b = alvo.getBoundingClientRect();
    dica.hidden = false;
    const w = dica.offsetWidth;
    dica.style.left = `${Math.max(8, Math.min(window.innerWidth - w - 8, b.left + b.width / 2 - w / 2))}px`;
    dica.style.top = `${Math.max(8, b.top - dica.offsetHeight - 8)}px`;
    alvo.classList.add("g-ativo");
  };
  const esconder = (alvo) => { dica.hidden = true; alvo.classList.remove("g-ativo"); };
  raiz.querySelectorAll("[data-dica]").forEach((m) => {
    m.addEventListener("pointerenter", () => mostrar(m));
    m.addEventListener("pointerleave", () => esconder(m));
    m.addEventListener("focus", () => mostrar(m));
    m.addEventListener("blur", () => esconder(m));
  });
}

const _jsonAttr = (x) => esc(JSON.stringify(x));

// Colunas agrupadas por categoria (ex.: meses). series: [{chave, nome}], dados: [{rotulo, <chave>: número}]
function graficoColunas({ titulo, dados, series, formato = (v) => String(v), altura = 160, legendaTabela = "Categoria" }) {
  const max = Math.max(1, ...dados.flatMap((d) => series.map((s) => d[s.chave] || 0)));
  let topo = null;
  dados.forEach((d, i) => series.forEach((s, j) => { const v = d[s.chave] || 0; if (v && (!topo || v > topo.v)) topo = { i, j, v }; }));
  const legenda = series.length > 1 ? `<div class="g-legenda">${series.map((s, j) => `<span><i style="background:${CORES_SERIE[j]}"></i>${esc(s.nome)}</span>`).join("")}</div>` : "";
  const colunas = dados.map((d, i) => `<div class="g-grupo" style="--n:${series.length}">
      <div class="g-barras" style="height:${altura}px">${series.map((s, j) => {
        const v = d[s.chave] || 0;
        const h = v ? Math.max(3, Math.round((v / max) * (altura - 18))) : 0;
        const dica = [[d.rotulo], ...series.map((x, k) => [x.nome, formato(d[x.chave] || 0), CORES_SERIE[k]])];
        return `<div class="g-col" tabindex="0" data-dica="${_jsonAttr(dica)}" aria-label="${esc(`${d.rotulo}: ${s.nome} ${formato(v)}`)}">
          ${topo && topo.i === i && topo.j === j ? `<span class="g-rotulo" style="bottom:${h + 2}px">${esc(formato(v))}</span>` : ""}
          <span class="g-marca" style="height:${h}px;background:${CORES_SERIE[j]}"></span></div>`;
      }).join("")}</div><small>${esc(d.rotulo)}</small></div>`).join("");
  const tabela = `<details class="g-tabela"><summary>Ver em tabela</summary><div class="tabela-rolagem"><table><thead><tr><th>${esc(legendaTabela)}</th>${series.map((s) => `<th>${esc(s.nome)}</th>`).join("")}</tr></thead>
    <tbody>${dados.map((d) => `<tr><td>${esc(d.rotulo)}</td>${series.map((s) => `<td>${esc(formato(d[s.chave] || 0))}</td>`).join("")}</tr>`).join("")}</tbody></table></div></details>`;
  return `<figure class="g-figura">${titulo ? `<figcaption>${esc(titulo)}</figcaption>` : ""}${legenda}<div class="g-colunas">${colunas}</div>${tabela}</figure>`;
}

// Barras horizontais de uma série (ranking, funil). itens: [{rotulo, valor, detalhe?}]
function graficoBarras({ titulo, itens, formato = (v) => String(v), vazio: textoVazio = "Sem dados no período." }) {
  if (!itens.length) return `<figure class="g-figura">${titulo ? `<figcaption>${esc(titulo)}</figcaption>` : ""}<p class="fraco">${esc(textoVazio)}</p></figure>`;
  const max = Math.max(1, ...itens.map((x) => x.valor || 0));
  return `<figure class="g-figura">${titulo ? `<figcaption>${esc(titulo)}</figcaption>` : ""}<div class="g-hbarras">${itens.map((x) => `
    <div class="g-hlinha" tabindex="0" data-dica="${_jsonAttr([[x.rotulo], [x.detalhe || "", formato(x.valor || 0), CORES_SERIE[0]]])}">
      <span class="g-hrotulo">${esc(x.rotulo)}</span>
      <span class="g-htrilho"><span class="g-hmarca" style="width:${x.valor ? Math.max(2, (100 * x.valor) / max) : 0}%"></span></span>
      <b class="g-hvalor">${esc(formato(x.valor || 0))}</b></div>`).join("")}</div></figure>`;
}

function kpi(rotulo, valor, sub = "", tom = "") {
  return `<div class="kpi ${tom}"><span>${esc(rotulo)}</span><b>${esc(valor)}</b>${sub ? `<small>${esc(sub)}</small>` : ""}</div>`;
}
