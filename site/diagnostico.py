"""Página do diagnóstico de maturidade B2G (/diagnostico/) — perguntas vêm de backend/data/diagnostico.json."""
import html
import json
import os

esc = html.escape
ARQ = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend", "data", "diagnostico.json")


def pg_diagnostico(pagina, SOFT):
    d = json.load(open(ARQ, encoding="utf-8"))
    eixos = [e["nome"] for e in d["eixos"]]
    corpo = f"""<section class="s-heroi s-heroi-ferramenta" data-diag-intro><div class="s-heroi-texto"><p class="s-sobre">Ferramenta gratuita · 3 minutos</p>
  <h1>Qual é a maturidade da sua empresa para vender ao governo?</h1>
  <p class="s-lead">Responda {len(d["perguntas"])} perguntas e receba uma nota de 0 a 100 em cinco eixos — {esc(", ".join(eixos[:-1]))} e {esc(eixos[-1])} — com o plano de ação para começar.</p>
  <ul class="s-provas"><li>Nota geral e por eixo</li><li>Comparação com outras empresas do mercado público</li><li>Plano de ação com as 3 prioridades</li></ul></div>
  <div class="s-cartao"><div class="s-diag" data-diag>
    <div class="s-diag-progresso" aria-hidden="true"><i></i></div>
    <p class="s-diag-passo" data-diag-passo></p>
    <div data-diag-corpo></div>
    <p class="s-msg" role="status"></p>
    <div class="s-diag-nav"><button type="button" class="s-botao s-botao-sec" data-diag-voltar hidden>Voltar</button>
      <button type="button" class="s-botao" data-diag-avancar>Começar</button></div>
    <input class="s-hp" name="site" tabindex="-1" autocomplete="off" aria-hidden="true">
  </div></div></section>
<section class="s-secao" data-diag-resultado hidden></section>
<script type="application/json" id="diag-def">{json.dumps(d, ensure_ascii=False)}</script>"""
    pagina("/diagnostico/", "Diagnóstico de maturidade B2G grátis | vendas para o governo — Kasiski",
           "Descubra em 3 minutos a maturidade da sua empresa para vender ao governo: nota de 0 a 100 em oportunidades, documentação, estratégia, concorrência e contratos, com plano de ação.",
           corpo, prioridade="0.9", jsonld=[SOFT])
