"""Página do checklist de habilitação (/checklist-habilitacao/) — catálogo em backend/data/checklist_habilitacao.json."""
import html
import json
import os

esc = html.escape
ARQ = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend", "data", "checklist_habilitacao.json")


def pg_checklist(pagina, migalhas):
    d = json.load(open(ARQ, encoding="utf-8"))
    cab, ld = migalhas([("Início", "/"), ("Checklist de habilitação", None)])
    grupos = []
    for c in d["categorias"]:
        itens = [i for i in d["itens"] if i["categoria"] == c["id"]]
        if not itens:
            continue
        linhas = []
        for i in itens:
            seg = " ".join(i.get("segmentos") or [])
            val = (f'<label class="s-ck-val">Válido até <input type="date" data-validade="{i["id"]}" aria-label="Validade de {esc(i["tipo"])}"></label>'
                   if i.get("tem_validade") else "")
            linhas.append(f'''<li class="s-ck-item" data-item="{i["id"]}"{f' data-segmentos="{seg}"' if seg else ""}>
  <label class="s-ck-tem"><input type="checkbox" data-tem="{i["id"]}"><span class="s-ck-caixa" aria-hidden="true"></span>
    <span class="s-ck-texto"><b>{esc(i["tipo"])}</b><small>{esc(i["descricao"])}</small>
    <span class="s-ck-meta"><span>Onde: {esc(i["onde"])}</span><span>Validade: {esc(i["validade"])}</span><span>{esc(i["base"])}</span></span></span></label>{val}</li>''')
        grupos.append(f'''<section class="s-ck-grupo" data-grupo="{c["id"]}"><header><h2>{esc(c["nome"])}</h2><span class="s-ck-cont" data-cont="{c["id"]}"></span></header>
  <p class="s-nota">{esc(c["base"])}</p><ul>{"".join(linhas)}</ul></section>''')
    chips = "".join(f'<button type="button" data-seg="{s["id"]}" aria-pressed="false">{esc(s["nome"])}</button>' for s in d["segmentos"])
    howto = {"@context": "https://schema.org", "@type": "HowTo", "name": "Checklist de habilitação em licitações (Lei 14.133/2021)",
             "step": [{"@type": "HowToStep", "name": c["nome"], "text": "; ".join(i["tipo"] for i in d["itens"] if i["categoria"] == c["id"])}
                      for c in d["categorias"] if any(i["categoria"] == c["id"] for i in d["itens"])]}
    corpo = f"""{cab}<section class="s-heroi s-heroi-centro s-ck-heroi"><p class="s-sobre">Ferramenta gratuita</p>
  <h1>Checklist de habilitação em licitações</h1>
  <p class="s-lead">Os documentos que a Lei 14.133/2021 permite exigir, com onde emitir, validade usual e base legal, mais as exigências do seu setor. Marque o que você já tem e veja o que falta.</p></section>
<section class="s-secao s-ck" data-checklist>
  <div class="s-ck-topo"><div><b>Seu segmento</b><div class="s-cats s-ck-segs" role="group" aria-label="Segmento">{chips}</div></div>
    <div class="s-ck-progresso"><div><b data-total-ok>0</b> de <b data-total>0</b> documentos prontos</div><div class="s-ck-barra"><i data-barra></i></div></div></div>
  {"".join(grupos)}
  <div class="s-ck-acoes" data-ck-acoes><div><b>Leve este checklist com você</b><span class="s-nota">Os itens que faltam viram pendências no Cofre, com alerta de validade.</span></div>
    <div class="s-acoes"><button type="button" class="s-botao s-botao-sec" data-ck-acao="baixar" data-cta="checklist_baixar">Baixar checklist</button>
      <button type="button" class="s-botao" data-ck-acao="importar" data-cta="checklist_importar">Importar para meu Cofre Kasiski</button></div></div>
  <p class="s-nota s-ck-aviso">Conteúdo informativo, com base na Lei 14.133/2021. O edital define o que é exigido em cada licitação: confira sempre o item de habilitação do edital. Atualizado em {esc(d["atualizado"][8:10])}/{esc(d["atualizado"][5:7])}/{esc(d["atualizado"][:4])}.</p>
</section>
<div class="s-fundo" data-ck-modal hidden><div class="s-modal" role="dialog" aria-modal="true" aria-labelledby="ck-titulo">
  <button type="button" class="s-modal-fechar" data-ck-fechar aria-label="Fechar">×</button>
  <h2 id="ck-titulo" data-ck-titulo>Baixar checklist</h2><p class="s-nota" data-ck-sub></p>
  <form class="s-ferramenta" data-form="checklist" novalidate><div class="s-linha">
    <div class="s-campo"><label for="ck-nome">Nome</label><input id="ck-nome" name="nome" required autocomplete="name"></div>
    <div class="s-campo"><label for="ck-email">E-mail</label><input id="ck-email" name="email" type="email" required autocomplete="email"></div></div>
    <div class="s-campo"><label for="ck-emp">Empresa <small>(opcional)</small></label><input id="ck-emp" name="empresa" autocomplete="organization"></div>
    <label class="s-check"><input type="checkbox" name="consentimento" required> <span>Concordo com a <a href="/privacidade/">Política de Privacidade</a>.</span></label>
    <label class="s-check"><input type="checkbox" name="newsletter"> <span>Quero receber a newsletter Kasiski Intelligence.</span></label>
    <input class="s-hp" name="site" tabindex="-1" autocomplete="off" aria-hidden="true">
    <button class="s-botao s-botao-grande" type="submit" data-ck-enviar>Baixar checklist</button><p class="s-msg" role="status"></p></form>
  <div data-ck-feito hidden></div></div></div>
<script type="application/json" id="ck-def">{json.dumps({"itens": [{k: i.get(k) for k in ("id", "categoria", "tipo", "tem_validade", "segmentos")} for i in d["itens"]]}, ensure_ascii=False)}</script>"""
    pagina("/checklist-habilitacao/", "Checklist de habilitação em licitações (Lei 14.133) — grátis | Kasiski",
           "Lista completa dos documentos de habilitação da Lei 14.133/2021: jurídica, fiscal, trabalhista, econômico-financeira, técnica, declarações e exigências por setor. Marque o que tem e importe para o seu cofre.",
           corpo, prioridade="0.9", jsonld=[ld, howto])
