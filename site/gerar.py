"""Gera o site público do Kasiski (kasiski.com.br) em publico/ — HTML estático com URLs limpas.

Uso:  python site/gerar.py          (requer: pip install markdown)
Saída: publico/ (publique esta pasta no site do Netlify de kasiski.com.br).
O aplicativo fica em frontend/ (publicado em app.kasiski.com.br). Arquivos compartilhados — js/config.js,
js/rastreio.js, chat/ e assets/ — são copiados do frontend/ para o publico/ a cada geração.
"""
import html
import json
import os
import re
import shutil
from datetime import date

import markdown

import conteudo as C

RAIZ = os.path.dirname(os.path.abspath(__file__))
PROJETO = os.path.dirname(RAIZ)
SAIDA = os.path.join(PROJETO, "publico")
APP_DIR = os.path.join(PROJETO, "frontend")
geradas = []  # (url, prioridade)

esc = html.escape


def simbolo(tamanho=30):
    rects = [(70, 105, 20, "c"), (115, 105, 130, "n"), (280, 105, 105, "n"), (70, 153, 125, "c"), (220, 153, 100, "c"), (345, 153, 75, "n"),
             (70, 201, 70, "c"), (165, 201, 105, "c"), (295, 201, 80, "n"), (70, 249, 20, "c"), (115, 249, 130, "c"), (265, 249, 75, "n"),
             (70, 297, 55, "n"), (145, 297, 70, "c"), (235, 297, 100, "c"), (360, 297, 20, "n"), (405, 297, 20, "c"), (70, 345, 85, "g"),
             (175, 345, 65, "n"), (265, 345, 105, "c"), (390, 345, 55, "n"), (70, 393, 20, "g"), (115, 393, 145, "n"), (285, 393, 105, "n")]
    cor = {"n": "", "c": ' fill="#11B8C8"', "g": ' fill="#91A5B3"'}
    r = "".join(f'<rect x="{x-70}" y="{y-105}" width="{w}" height="20" rx="10"{cor[c]}/>' for x, y, w, c in rects)
    return f'<svg class="s-simbolo" width="{tamanho}" height="{round(tamanho*308/375)}" viewBox="0 0 375 308" fill="currentColor" aria-hidden="true">{r}</svg>'


FAVICON = "/favicon.svg"


def cabecalho(minimo=False):
    if minimo:  # landing pages: só a marca, sem menu (um único objetivo)
        return f'<header class="s-topo s-topo-min"><a class="s-marca" href="/">{simbolo(30)}<span><b>KASISKI</b><small>PUBLIC MARKET INTELLIGENCE</small></span></a></header>'
    menu_sol = "".join(f'<a href="/{s["slug"]}/">{esc(s["nome"])}</a>' for s in C.SOLUCOES)
    return f'''<header class="s-topo"><a class="s-marca" href="/">{simbolo(30)}<span><b>KASISKI</b><small>PUBLIC MARKET INTELLIGENCE</small></span></a>
  <button class="s-menu-btn" aria-expanded="false" aria-controls="s-nav">Menu</button>
  <nav id="s-nav" class="s-nav">
    <div class="s-drop"><button type="button" aria-haspopup="true">Soluções</button><div class="s-drop-menu">{menu_sol}</div></div>
    <div class="s-drop"><button type="button" aria-haspopup="true">Ferramentas grátis</button><div class="s-drop-menu">
      <a href="/analisar-edital/">Analisar edital</a><a href="/consultar-concorrente/">Consultar concorrente</a><a href="/newsletter/">Kasiski Intelligence (newsletter)</a></div></div>
    <a href="/inteligencia/">Inteligência</a><a href="/consultorias/">Consultorias</a><a href="/#planos" data-cta="menu_planos">Planos</a>
    <a class="s-entrar" href="{C.APP_ENTRAR}">Entrar</a><a class="s-botao" href="{C.APP_CADASTRO}" data-cta="menu_testar">Testar grátis</a>
  </nav></header>'''


def rodape():
    ano = date.today().year
    return f'''<footer class="s-rodape"><div class="s-rodape-grade">
  <div><a class="s-marca s-marca-clara" href="/">{simbolo(28)}<span><b>KASISKI</b><small>PUBLIC MARKET INTELLIGENCE</small></span></a>
    <p>Inteligência para vender ao poder público: radar de editais, análise com IA, concorrentes, preços, propostas e contratos.</p>
    <form class="s-news-mini" data-form="newsletter" novalidate><label for="nl-rod">Kasiski Intelligence: o mercado público toda semana</label>
      <div><input id="nl-rod" name="email" type="email" required placeholder="seu@email.com.br" autocomplete="email"><button type="submit">Assinar</button></div>
      <label class="s-check"><input type="checkbox" name="consentimento" required> <span>Concordo com a <a href="/privacidade/">Política de Privacidade</a></span></label>
      <input class="s-hp" name="site" tabindex="-1" autocomplete="off" aria-hidden="true"><p class="s-msg" role="status"></p></form></div>
  <div><h3>Soluções</h3>{"".join(f'<a href="/{s["slug"]}/">{esc(s["nome"])}</a>' for s in C.SOLUCOES)}</div>
  <div><h3>Grátis</h3><a href="/analisar-edital/">Analisar edital</a><a href="/consultar-concorrente/">Consultar concorrente</a><a href="/newsletter/">Newsletter</a>
    <h3>Conteúdo</h3><a href="/inteligencia/">Inteligência</a><a href="/glossario/">Glossário</a></div>
  <div><h3>Kasiski</h3><a href="/consultorias/">Para consultorias</a><a href="/#planos">Planos</a><a href="{C.APP_ENTRAR}">Entrar</a>
    <h3>Legal</h3><a href="/privacidade/">Privacidade</a><a href="/cookies/">Cookies</a><a href="/termos/">Termos de uso</a><a href="/termos-ia/">Termos de IA</a>
    <a href="#" data-preferencias-cookies>Preferências de cookies</a></div>
  </div><p class="s-copy">© {ano} Kasiski Public Market Intelligence · {esc(C.EMPRESA["razao"])}{" · CNPJ " + esc(C.EMPRESA["cnpj"]) if C.EMPRESA["cnpj"] else ""}</p></footer>'''


def pagina(caminho, titulo, descricao, corpo, *, minimo=False, jsonld=None, prioridade="0.6", og_tipo="website", indexar=True, extra_head=""):
    url = C.SITE_URL + caminho
    ld = "".join(f'<script type="application/ld+json">{json.dumps(j, ensure_ascii=False)}</script>' for j in (jsonld or []))
    doc = f'''<!doctype html>
<html lang="pt-BR"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(titulo)}</title>
<meta name="description" content="{esc(descricao)}">
<link rel="canonical" href="{url}">
{'' if indexar else '<meta name="robots" content="noindex">'}
<meta property="og:type" content="{og_tipo}"><meta property="og:site_name" content="Kasiski Public Market Intelligence">
<meta property="og:title" content="{esc(titulo)}"><meta property="og:description" content="{esc(descricao)}">
<meta property="og:url" content="{url}"><meta property="og:image" content="{C.SITE_URL}/assets/og-kasiski.png"><meta property="og:locale" content="pt_BR">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="{FAVICON}" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/site/site.css">
{ld}{extra_head}
<script src="/js/config.js"></script><script src="/js/rastreio.js"></script>
</head><body class="{'s-lp' if minimo else ''}">
{cabecalho(minimo)}
<main id="conteudo">{corpo}</main>
{rodape()}
<script src="/site/site.js"></script>
{'' if minimo else '<link rel="stylesheet" href="/chat/widget.css"><script src="/chat/widget.js"></script>'}
</body></html>'''
    destino = os.path.join(SAIDA, caminho.strip("/"), "index.html") if caminho != "/404" else os.path.join(SAIDA, "404.html")
    os.makedirs(os.path.dirname(destino), exist_ok=True)
    with open(destino, "w", encoding="utf-8") as f:
        f.write(doc)
    if indexar and caminho != "/404":
        geradas.append((caminho, prioridade))


def migalhas(itens):
    """Breadcrumbs visíveis + JSON-LD."""
    vis = " <span>›</span> ".join(f'<a href="{u}">{esc(n)}</a>' if u else f"<span>{esc(n)}</span>" for n, u in itens)
    ld = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": n, **({"item": C.SITE_URL + u} if u else {})} for i, (n, u) in enumerate(itens)]}
    return f'<nav class="s-migalhas" aria-label="Você está em">{vis}</nav>', ld


ORG = {"@context": "https://schema.org", "@type": "Organization", "name": "Kasiski Public Market Intelligence", "url": C.SITE_URL,
       "logo": C.SITE_URL + "/assets/kasiski-logo.svg", "email": C.EMPRESA["email_contato"]}
SOFT = {"@context": "https://schema.org", "@type": "SoftwareApplication", "name": "Kasiski", "applicationCategory": "BusinessApplication",
        "operatingSystem": "Web", "offers": {"@type": "Offer", "price": "0", "priceCurrency": "BRL", "description": "Teste grátis de 7 dias"}}


# ---------------------------------------------------------------- blocos das ferramentas
def form_analisar(origem):
    return f'''<form class="s-ferramenta" data-form="analisar" data-origem="{origem}" novalidate>
  <label class="s-upload" for="arq-edital"><input id="arq-edital" name="arquivo" type="file" accept="application/pdf,.pdf" required>
    <b>Envie o PDF do edital</b><span>Arraste aqui ou clique para escolher · até 15 MB</span><em data-arquivo></em></label>
  <div class="s-linha"><div class="s-campo"><label for="an-nome">Seu nome</label><input id="an-nome" name="nome" required autocomplete="name"></div>
    <div class="s-campo"><label for="an-email">E-mail profissional</label><input id="an-email" name="email" type="email" required autocomplete="email"></div></div>
  <div class="s-campo"><label for="an-emp">Empresa <small>(opcional)</small></label><input id="an-emp" name="empresa" autocomplete="organization"></div>
  <label class="s-check"><input type="checkbox" name="consentimento" required> <span>Concordo com a <a href="/privacidade/">Política de Privacidade</a> e com o tratamento do edital para a análise.</span></label>
  <label class="s-check"><input type="checkbox" name="newsletter"> <span>Quero receber a newsletter Kasiski Intelligence.</span></label>
  <input class="s-hp" name="site" tabindex="-1" autocomplete="off" aria-hidden="true"><div class="s-turnstile"></div>
  <button class="s-botao s-botao-grande" type="submit" data-cta="analisar_edital">Analisar edital gratuitamente</button>
  <p class="s-msg" role="status"></p>
  <p class="s-nota">O arquivo é apagado em 7 dias. Não pedimos cartão.</p></form>
  <div class="s-resultado" data-resultado hidden></div>'''


def form_concorrente(origem):
    return f'''<form class="s-ferramenta s-ferramenta-cnpj" data-form="concorrente" data-origem="{origem}" novalidate>
  <div class="s-campo"><label for="cc-cnpj">CNPJ do concorrente</label><input id="cc-cnpj" name="cnpj" required inputmode="numeric" placeholder="00.000.000/0001-00" autocomplete="off"></div>
  <input class="s-hp" name="site" tabindex="-1" autocomplete="off" aria-hidden="true"><div class="s-turnstile"></div>
  <button class="s-botao s-botao-grande" type="submit" data-cta="consultar_concorrente">Consultar</button><p class="s-msg" role="status"></p></form>
  <div class="s-resultado" data-resultado hidden></div>'''


def form_consultorias():
    return '''<form class="s-ferramenta" data-form="lead" data-magnet="consultorias" novalidate>
  <div class="s-linha"><div class="s-campo"><label for="co-nome">Nome</label><input id="co-nome" name="nome" required autocomplete="name"></div>
    <div class="s-campo"><label for="co-email">E-mail</label><input id="co-email" name="email" type="email" required autocomplete="email"></div></div>
  <div class="s-linha"><div class="s-campo"><label for="co-wa">WhatsApp</label><input id="co-wa" name="whatsapp" inputmode="tel" autocomplete="tel"></div>
    <div class="s-campo"><label for="co-emp">Consultoria / escritório</label><input id="co-emp" name="empresa" autocomplete="organization"></div></div>
  <div class="s-campo"><label for="co-msg">Quantos clientes você atende e o que quer resolver?</label><textarea id="co-msg" name="mensagem" rows="3"></textarea></div>
  <label class="s-check"><input type="checkbox" name="consentimento" required> <span>Concordo com a <a href="/privacidade/">Política de Privacidade</a>.</span></label>
  <input class="s-hp" name="site" tabindex="-1" autocomplete="off" aria-hidden="true">
  <div class="s-acoes"><button class="s-botao s-botao-grande" type="submit" data-cta="consultorias_contato">Falar com um especialista</button>
    <a class="s-botao s-botao-sec" href="https://app.kasiski.com.br/#/cadastro" data-cta="consultorias_teste">Testar para consultorias</a></div>
  <p class="s-msg" role="status"></p></form>'''


# ---------------------------------------------------------------- páginas
def pg_analisar():
    corpo = f'''<section class="s-heroi s-heroi-ferramenta"><div class="s-heroi-texto"><p class="s-sobre">Ferramenta gratuita</p>
  <h1>Descubra os riscos do seu edital antes de decidir participar</h1>
  <p class="s-lead">Envie o PDF. O Kasiski identifica exigências, documentos, prazos e possíveis pontos de atenção.</p>
  <ul class="s-provas"><li>Documentos de habilitação por categoria</li><li>Cláusulas que podem restringir a competição</li><li>Nota de participação de 0 a 100</li></ul></div>
  <div class="s-cartao">{form_analisar("analisar_edital")}</div></section>
  <section class="s-secao s-como"><h2>Como funciona</h2><ol class="s-passos">
    <li><b>Envie o edital</b><span>PDF com texto selecionável, até 15 MB.</span></li>
    <li><b>A IA lê o edital</b><span>Exigências, prazos, critério de julgamento e cláusulas sensíveis.</span></li>
    <li><b>Receba o resumo</b><span>Nota, documentos e o principal ponto de atenção — na tela e por e-mail.</span></li>
    <li><b>Veja tudo no Kasiski</b><span>Crie a conta com o mesmo e-mail: o edital é importado e a análise completa roda de cortesia.</span></li></ol></section>'''
    pagina("/analisar-edital/", "Analisar edital de licitação grátis com IA | Kasiski",
           "Envie o PDF do edital e descubra exigências de habilitação, documentos, prazos e pontos de atenção antes de decidir participar. Grátis.",
           corpo, prioridade="0.9", jsonld=[SOFT])


def pg_concorrente():
    corpo = f'''<section class="s-heroi s-heroi-ferramenta"><div class="s-heroi-texto"><p class="s-sobre">Ferramenta gratuita</p>
  <h1>Quem é seu concorrente no mercado público?</h1>
  <p class="s-lead">Digite o CNPJ e veja a situação cadastral, os contratos públicos encontrados, os órgãos contratantes e as sanções.</p>
  <ul class="s-provas"><li>Receita Federal</li><li>Contratos e atas no PNCP</li><li>Sanções no TCU, CEIS e CNEP</li></ul></div>
  <div class="s-cartao">{form_concorrente("consultar_concorrente")}</div></section>'''
    pagina("/consultar-concorrente/", "Consultar concorrente em licitações pelo CNPJ | Kasiski",
           "Consulta gratuita de concorrente: situação na Receita, contratos públicos no PNCP, órgãos contratantes e sanções pelo CNPJ.",
           corpo, prioridade="0.9", jsonld=[SOFT])


def pg_newsletter():
    corpo = '''<section class="s-heroi s-heroi-centro"><p class="s-sobre">Newsletter semanal</p><h1>Kasiski Intelligence</h1>
  <p class="s-lead">Inteligência sobre o mercado público brasileiro: quanto o governo está comprando, setores em destaque, as maiores oportunidades da semana e o radar regulatório.</p>
  <div class="s-aviso" data-status-news hidden></div>
  <form class="s-ferramenta s-news" data-form="newsletter" novalidate><div class="s-linha">
    <div class="s-campo"><label for="nl-email">E-mail</label><input id="nl-email" name="email" type="email" required autocomplete="email"></div>
    <div class="s-campo"><label for="nl-nome">Nome <small>(opcional)</small></label><input id="nl-nome" name="nome" autocomplete="name"></div></div>
    <label class="s-check"><input type="checkbox" name="consentimento" required> <span>Concordo com a <a href="/privacidade/">Política de Privacidade</a> e aceito receber a newsletter. Descadastro com um clique.</span></label>
    <input class="s-hp" name="site" tabindex="-1" autocomplete="off" aria-hidden="true">
    <button class="s-botao s-botao-grande" type="submit" data-cta="newsletter">Quero receber</button><p class="s-msg" role="status"></p></form></section>
  <section class="s-secao"><div class="s-grade3">
    <div class="s-item"><b>Dado da semana</b><p>Volume de editais e valor em oportunidades publicadas no PNCP.</p></div>
    <div class="s-item"><b>5 maiores oportunidades</b><p>As licitações de maior valor abertas na semana, por setor.</p></div>
    <div class="s-item"><b>Radar regulatório</b><p>Mudanças na Lei 14.133, decretos, instruções normativas e jurisprudência do TCU.</p></div></div></section>'''
    pagina("/newsletter/", "Kasiski Intelligence — newsletter do mercado público", "Newsletter semanal com dados do mercado público brasileiro, maiores oportunidades e radar regulatório das licitações.",
           corpo, prioridade="0.7")


def pg_consultorias():
    corpo = f'''<section class="s-heroi"><div class="s-heroi-texto"><p class="s-sobre">Para consultorias e escritórios</p>
  <h1>Gerencie todos os seus clientes de licitação em um único lugar</h1>
  <p class="s-lead">Cada cliente com radar, cofre, editais, prazos e contratos próprios — e relatórios com a marca do seu escritório.</p>
  <div class="s-acoes"><a class="s-botao s-botao-grande" href="https://app.kasiski.com.br/#/cadastro" data-cta="consultorias_heroi">Testar Kasiski para consultorias</a></div></div>
  <div class="s-painel-demo" aria-label="Exemplo do painel multiempresa">
    <div><b>CLIENTE A</b><span>Radar → 21 oportunidades</span></div><div><b>CLIENTE B</b><span>3 editais em análise</span></div>
    <div><b>CLIENTE C</b><span class="s-alerta">Proposta amanhã</span></div><div><b>CLIENTE D</b><span>Contrato vence em 92 dias</span></div></div></section>
  <section class="s-secao"><div class="s-grade3">
    <div class="s-item"><b>Multiempresa de verdade</b><p>Troque de cliente em um clique; radar, cofre e pipeline ficam separados por CNPJ.</p></div>
    <div class="s-item"><b>Produtividade com IA</b><p>Análise de edital, dossiê de concorrente e peças (impugnação, recurso, contrarrazões) em minutos.</p></div>
    <div class="s-item"><b>Sua marca</b><p>Relatórios de análise com o nome do escritório, prontos para enviar ao cliente.</p></div></div></section>
  <section class="s-secao s-secao-clara"><h2>Fale com a gente</h2><p>Mostramos o Kasiski com os editais dos seus clientes e montamos o plano ideal para a sua carteira.</p>
    <div class="s-cartao s-cartao-largo">{form_consultorias()}</div></section>'''
    pagina("/consultorias/", "Kasiski para consultorias de licitação | multiempresa com IA",
           "Gerencie todos os clientes de licitação em um só lugar: radar, editais, prazos, peças e contratos por cliente, com relatórios na sua marca.",
           corpo, prioridade="0.8")


def pg_solucao(s):
    cab, ld = migalhas([("Início", "/"), ("Soluções", None), (s["nome"], None)])
    pontos = "".join(f'<div class="s-item"><b>{esc(t)}</b><p>{esc(d)}</p></div>' for t, d in s["pontos"])
    corpo = f'''{cab}<section class="s-heroi"><div class="s-heroi-texto"><p class="s-sobre">{esc(s["nome"])}</p><h1>{esc(s["titulo"])}</h1>
  <p class="s-lead">{esc(s["descricao"])}</p>
  <div class="s-acoes"><a class="s-botao s-botao-grande" href="{C.APP_CADASTRO}" data-cta="solucao_{s["slug"]}">{esc(s["cta"]) if s["cta"] == "Testar grátis" else "Testar grátis por 7 dias"}</a>
  <a class="s-botao s-botao-sec" href="{s["lp"]}">{esc(s["cta"]) if s["cta"] != "Testar grátis" else "Ver na prática"}</a></div></div></section>
  <section class="s-secao"><div class="s-grade3">{pontos}</div></section>
  <section class="s-secao s-faixa"><h2>Teste grátis por 7 dias</h2><p>Sem cartão de crédito. Seus dados continuam salvos ao fim do teste.</p>
    <a class="s-botao s-botao-grande" href="{C.APP_CADASTRO}" data-cta="solucao_rodape_{s["slug"]}">Começar agora</a></section>'''
    pagina(f"/{s['slug']}/", f"{s['nome']} | Kasiski", s["descricao"], corpo, prioridade="0.8", jsonld=[ld, SOFT])


def pg_lp(lp):
    if lp["ferramenta"] == "analisar_edital":
        acao = f'<div class="s-cartao">{form_analisar("lp_analisar_edital")}</div>'
    elif lp["ferramenta"] == "concorrente":
        acao = f'<div class="s-cartao">{form_concorrente("lp_concorrentes")}</div>'
    elif lp["ferramenta"] == "consultorias":
        acao = f'<div class="s-cartao">{form_consultorias()}</div>'
    else:
        acao = f'''<div class="s-cartao s-cartao-cta"><b>Teste grátis por 7 dias</b><p>Sem cartão. Cadastre a empresa pelo CNPJ e o Radar começa na hora.</p>
          <a class="s-botao s-botao-grande" href="https://app.kasiski.com.br/#/cadastro" data-cta="lp_{lp["slug"]}">Criar minha conta grátis</a>
          <p class="s-nota">Já tem conta? <a href="{C.APP_ENTRAR}">Entrar</a></p></div>'''
    provas = "".join(f"<li>{esc(p)}</li>" for p in lp["provas"])
    corpo = f'''<section class="s-heroi s-heroi-ferramenta"><div class="s-heroi-texto"><h1>{esc(lp["titulo"])}</h1>
  <p class="s-lead">{esc(lp["subtitulo"])}</p><ul class="s-provas">{provas}</ul></div>{acao}</section>'''
    pagina(f"/lp/{lp['slug']}/", f"{lp['titulo']} | Kasiski", lp["descricao"], corpo, minimo=True, indexar=False)


def pg_glossario():
    cab, ld = migalhas([("Início", "/"), ("Glossário", None)])
    itens = "".join(f'<a class="s-termo" href="/glossario/{g["slug"]}/"><b>{esc(g["termo"])}</b><span>{esc(g["definicao"][:140])}…</span></a>' for g in C.GLOSSARIO)
    pagina("/glossario/", "Glossário de licitações e contratos públicos | Kasiski",
           "Termos de licitação explicados: PNCP, pregão eletrônico, Go/No-Go, atestado de capacidade técnica, inexequibilidade, impugnação, recurso, SICAF, BDI e SINAPI.",
           f'{cab}<section class="s-secao"><h1>Glossário Kasiski</h1><p class="s-lead">Os termos do mercado público explicados com definição, exemplo, legislação e aplicação prática.</p><div class="s-termos">{itens}</div></section>',
           prioridade="0.7", jsonld=[ld])
    for g in C.GLOSSARIO:
        cab, ld = migalhas([("Início", "/"), ("Glossário", "/glossario/"), (g["termo"], None)])
        termo_ld = {"@context": "https://schema.org", "@type": "DefinedTerm", "name": g["termo"], "description": g["definicao"],
                    "inDefinedTermSet": C.SITE_URL + "/glossario/"}
        nome_f, url_f = g["ferramenta"]
        corpo = f'''{cab}<article class="s-artigo"><h1>{esc(g["termo"])}</h1>
  <h2>Definição</h2><p>{esc(g["definicao"])}</p><h2>Exemplo</h2><p>{esc(g["exemplo"])}</p>
  <h2>Legislação</h2><p>{esc(g["legislacao"])}</p><h2>Aplicação na prática</h2><p>{esc(g["aplicacao"])}</p>
  <aside class="s-caixa-ferramenta"><b>No Kasiski</b><p>Veja como isso funciona na prática em <a href="{url_f}">{esc(nome_f)}</a>.</p>
    <a class="s-botao" href="{C.APP_CADASTRO}" data-cta="glossario_{g["slug"]}">Testar grátis</a></aside>
  <p class="s-nota">Conteúdo informativo, não substitui a análise jurídica do caso concreto.</p></article>'''
        pagina(f"/glossario/{g['slug']}/", f"{g['termo']}: o que é | Glossário Kasiski", g["definicao"][:155], corpo, prioridade="0.6", jsonld=[ld, termo_ld])


def ler_artigos():
    pasta = os.path.join(RAIZ, "artigos")
    artigos = []
    for nome in sorted(os.listdir(pasta)) if os.path.isdir(pasta) else []:
        if not nome.endswith(".md"):
            continue
        bruto = open(os.path.join(pasta, nome), encoding="utf-8").read()
        meta, texto = {}, bruto
        m = re.match(r"^---\n(.*?)\n---\n(.*)$", bruto, re.S)
        if m:
            for linha in m.group(1).splitlines():
                if ":" in linha:
                    k, v = linha.split(":", 1)
                    meta[k.strip()] = v.strip()
            texto = m.group(2)
        meta["slug"] = nome[:-3]
        meta["html"] = markdown.markdown(texto, extensions=["tables", "sane_lists"])
        artigos.append(meta)
    artigos.sort(key=lambda a: a.get("data", ""), reverse=True)
    return artigos


CATEGORIAS = ["Mercado Público", "Licitações", "Estratégia", "Concorrência", "Preços", "Lei 14.133", "Contratos", "Dados"]


def pg_inteligencia():
    artigos = ler_artigos()
    cab, ld = migalhas([("Início", "/"), ("Inteligência", None)])
    cats = "".join(f'<button type="button" data-cat="{esc(c)}">{esc(c)}</button>' for c in CATEGORIAS)
    cards = "".join(f'''<a class="s-card-artigo" href="/inteligencia/{a["slug"]}/" data-categoria="{esc(a.get("categoria", ""))}">
      <small>{esc(a.get("categoria", ""))} · {esc(_data_br(a.get("data")))}</small><b>{esc(a.get("titulo", a["slug"]))}</b><span>{esc(a.get("descricao", ""))}</span></a>''' for a in artigos)
    corpo = f'''{cab}<section class="s-secao"><p class="s-sobre">Inteligência</p><h1>Estratégia e dados para vender ao poder público</h1>
  <p class="s-lead">Guias práticos sobre licitações, Lei 14.133, concorrência, preços e contratos — com a visão de quem acompanha o mercado público todo dia.</p>
  <div class="s-cats" role="group" aria-label="Categorias"><button type="button" data-cat="" aria-pressed="true">Todos</button>{cats}</div>
  <div class="s-artigos">{cards or '<p>Em breve.</p>'}</div></section>
  <section class="s-secao s-faixa"><h2>Kasiski Intelligence toda semana no seu e-mail</h2><a class="s-botao s-botao-grande" href="/newsletter/">Assinar a newsletter</a></section>'''
    pagina("/inteligencia/", "Inteligência | Licitações, Lei 14.133 e mercado público — Kasiski",
           "Guias e análises sobre licitações, Lei 14.133/2021, estratégia comercial, concorrência, preços e contratos públicos.", corpo, prioridade="0.8", jsonld=[ld])
    for a in artigos:
        cab, ld = migalhas([("Início", "/"), ("Inteligência", "/inteligencia/"), (a.get("titulo", a["slug"]), None)])
        art_ld = {"@context": "https://schema.org", "@type": "Article", "headline": a.get("titulo"), "description": a.get("descricao"),
                  "datePublished": a.get("data"), "author": {"@type": "Organization", "name": "Kasiski"},
                  "publisher": {"@type": "Organization", "name": "Kasiski", "logo": {"@type": "ImageObject", "url": C.SITE_URL + "/assets/kasiski-logo.svg"}},
                  "mainEntityOfPage": C.SITE_URL + f"/inteligencia/{a['slug']}/"}
        corpo = f'''{cab}<article class="s-artigo"><p class="s-sobre">{esc(a.get("categoria", ""))} · {esc(_data_br(a.get("data")))}</p>
  <h1>{esc(a.get("titulo", ""))}</h1><p class="s-lead">{esc(a.get("descricao", ""))}</p>{a["html"]}
  <aside class="s-caixa-ferramenta"><b>Faça isso no Kasiski</b><p>{esc(a.get("cta_texto", "Teste grátis por 7 dias, sem cartão."))}</p>
    <a class="s-botao" href="{esc(a.get("cta_link", C.APP_CADASTRO))}" data-cta="artigo_{a["slug"]}">{esc(a.get("cta", "Testar grátis"))}</a></aside>
  <p class="s-nota">Conteúdo informativo, não substitui a análise jurídica do caso concreto.</p></article>'''
        pagina(f"/inteligencia/{a['slug']}/", f"{a.get('titulo')} | Kasiski", a.get("descricao", ""), corpo, prioridade="0.7",
               og_tipo="article", jsonld=[ld, art_ld])


def _data_br(v):
    try:
        a, m, d = str(v).split("-")
        return f"{d}/{m}/{a}"
    except ValueError:
        return v or ""


def pg_legal():
    import legal
    for caminho, titulo, descricao, html_ in legal.paginas(C.EMPRESA):
        cab, ld = migalhas([("Início", "/"), (titulo, None)])
        pagina(caminho, f"{titulo} | Kasiski", descricao, f'{cab}<article class="s-artigo s-legal"><h1>{esc(titulo)}</h1>'
               f'<p class="s-nota">Última atualização: {esc(C.EMPRESA["atualizado"])}</p>{html_}</article>', prioridade="0.3", jsonld=[ld])


def pg_404():
    pagina("/404", "Página não encontrada | Kasiski", "A página que você procura não existe.",
           '''<section class="s-heroi s-heroi-centro"><h1>Página não encontrada</h1><p class="s-lead">O endereço pode ter mudado. Que tal começar por aqui?</p>
      <div class="s-acoes s-acoes-centro"><a class="s-botao" href="/">Página inicial</a><a class="s-botao s-botao-sec" href="/analisar-edital/">Analisar um edital grátis</a>
      <a class="s-botao s-botao-sec" href="/inteligencia/">Inteligência</a></div></section>''', indexar=False)


def copiar_compartilhados():
    """O site usa os mesmos config.js, rastreio.js, chat e imagens do app (frontend/)."""
    os.makedirs(os.path.join(SAIDA, "js"), exist_ok=True)
    for nome in ("config.js", "rastreio.js"):
        shutil.copy2(os.path.join(APP_DIR, "js", nome), os.path.join(SAIDA, "js", nome))
    for pasta in ("chat", "assets"):
        shutil.copytree(os.path.join(APP_DIR, pasta), os.path.join(SAIDA, pasta), dirs_exist_ok=True)
    shutil.copytree(os.path.join(RAIZ, "estatico"), os.path.join(SAIDA, "site"), dirs_exist_ok=True)


def extras():
    urls = geradas
    hoje = date.today().isoformat()
    sm = "".join(f"<url><loc>{C.SITE_URL}{u}</loc><lastmod>{hoje}</lastmod><priority>{p}</priority></url>" for u, p in urls)
    open(os.path.join(SAIDA, "sitemap.xml"), "w", encoding="utf-8").write(
        f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{sm}</urlset>\n')
    open(os.path.join(SAIDA, "robots.txt"), "w", encoding="utf-8").write(
        f"User-agent: *\nAllow: /\nDisallow: /lp/\n\nSitemap: {C.SITE_URL}/sitemap.xml\n")
    # Netlify: atalhos para o app e para âncoras; 301 de URLs antigas que surgirem vão aqui
    a = C.APP_URL
    open(os.path.join(SAIDA, "_redirects"), "w", encoding="utf-8").write(f"""# Gerado por site/gerar.py — kasiski.com.br (o aplicativo fica em {a})
/entrar            {a}/#/entrar       302
/cadastro          {a}/#/cadastro     302
/app               {a}/#/painel       302
/painel            {a}/#/painel       302
/planos            /#planos           302
/blog              /inteligencia/     301
/blog/*            /inteligencia/:splat 301
/guias             /inteligencia/     301
/ferramentas/analisar-edital      /analisar-edital/        301
/ferramentas/consultar-concorrente /consultar-concorrente/ 301
""")
    ico = simbolo(64).replace('class="s-simbolo" ', 'xmlns="http://www.w3.org/2000/svg" ').replace('fill="currentColor"', 'fill="#071D2D"')
    open(os.path.join(SAIDA, "favicon.svg"), "w", encoding="utf-8").write(ico)


if __name__ == "__main__":
    if os.path.isdir(SAIDA):
        shutil.rmtree(SAIDA)  # publico/ é 100% gerado: não edite arquivos lá dentro
    os.makedirs(SAIDA)
    copiar_compartilhados()
    import home
    home.pg_home(pagina, ORG, SOFT)
    pg_analisar()
    pg_concorrente()
    pg_newsletter()
    pg_consultorias()
    for s in C.SOLUCOES:
        pg_solucao(s)
    for lp in C.LPS:
        pg_lp(lp)
    pg_glossario()
    pg_inteligencia()
    pg_legal()
    pg_404()
    extras()
    print(f"{len(geradas) + 1} páginas indexáveis + landing pages geradas em {SAIDA}")
