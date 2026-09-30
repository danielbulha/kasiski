"""KASISKI DoubleCheck™ no site: seção da home e página própria (/doublecheck/).

Mensagem: redução de risco e identificação de divergências — nunca "verdade" ou "ausência de erro".
Os fornecedores de IA não aparecem: KASISKI Analysis Engine e KASISKI Verification Engine.
"""
from html import escape as esc

import conteudo as C

ASSINATURA = "Uma IA analisa. Outra confere. Você decide."
MANIFESTO = "Confiança não se presume. Verifica-se."


def simbolo(tam=28, seta=False, classe="s-dc-simbolo"):
    """Três linhas (o documento e as duas leituras) convergem para um ponto de verificação."""
    w = 44 if seta else 38
    ponta = ('<path d="M35.5 14H42M39 10.8 42.2 14 39 17.2" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>'
             if seta else "")
    return (f'<svg class="{classe}" width="{round(tam * w / 28)}" height="{tam}" viewBox="0 0 {w} 28" fill="none" aria-hidden="true" focusable="false">'
            '<path d="M6 5c8 0 10 9 18 9M6 23c8 0 10-9 18-9" stroke="#11B8C8" stroke-width="2.4" stroke-linecap="round"/>'
            '<path d="M6 14h18" stroke="#91A5B3" stroke-width="2.4" stroke-linecap="round"/>'
            '<circle cx="4" cy="5" r="2.6" fill="#11B8C8"/><circle cx="4" cy="23" r="2.6" fill="#11B8C8"/><circle cx="4" cy="14" r="2.6" fill="#91A5B3"/>'
            f'<circle cx="29.5" cy="14" r="4.6" stroke="currentColor" stroke-width="2.6"/>{ponta}</svg>')


def selo(escuro=False):
    """Selo horizontal completo: símbolo + KASISKI DoubleCheck™ + AI Cross-Verification Protocol."""
    return (f'<span class="s-dc-selo{" escuro" if escuro else ""}">{simbolo(34, seta=True)}<span><small>KASISKI</small>'
            '<b>Double<em>Check</em><sup>™</sup></b><i>AI Cross-Verification Protocol</i></span></span>')


def diagrama(animado=False):
    """IA 01 analisa · IA 02 confere → DoubleCheck confronta → fonte + conclusão → você decide."""
    a = " s-dc-anima" if animado else ""
    return f'''<figure class="s-dc-diagrama{a}" aria-label="Como funciona o DoubleCheck: uma IA analisa, outra confere, o sistema confronta os resultados com a fonte e você decide">
  <div class="s-dc-no s-dc-n1"><span class="s-dc-tag">Documento</span><b>Edital, ata ou peça</b><small>o texto original, página por página</small></div>
  <div class="s-dc-par">
    <div class="s-dc-no s-dc-n2"><span class="s-dc-tag">IA 01 · Analisa</span><b>KASISKI Analysis Engine</b><small>identifica exigências, riscos e oportunidades</small></div>
    <div class="s-dc-no s-dc-n3"><span class="s-dc-tag">IA 02 · Confere</span><b>KASISKI Verification Engine</b><small>relê o documento de forma independente e cética</small></div>
  </div>
  <div class="s-dc-no s-dc-centro s-dc-n4">{simbolo(26)}<b>DoubleCheck™</b><small>confronta os resultados e identifica divergências</small></div>
  <div class="s-dc-par">
    <div class="s-dc-no s-dc-n5"><span class="s-dc-tag">Fonte + conclusão</span><b>Trecho e página do documento</b><small>cada conclusão fica ligada à origem</small></div>
    <div class="s-dc-no s-dc-n6 s-dc-voce"><span class="s-dc-tag">Você decide</span><b>Com a divergência à vista</b><small>nada é escondido: o que não bate aparece como não bate</small></div>
  </div>
</figure>'''


ESTADOS = [("confirmado", "✓", "Confirmado", "Os modelos convergiram e a fonte foi localizada."),
           ("divergencia", "⇄", "Divergência", "Interpretações diferentes. As duas leituras aparecem para você comparar."),
           ("revisao", "!", "Revisão recomendada", "O documento não permite concluir com segurança. Olhar humano primeiro.")]


def estados_html():
    return "".join(f'<div class="s-dc-estado s-dc-{k}"><span class="s-dc-chip">{simbolo(14)}<b>DoubleCheck™</b> {esc(n)} <i>{m}</i></span>'
                   f'<p>{esc(t)}</p></div>' for k, m, n, t in ESTADOS)


def secao_home():
    return f'''<section class="s-secao s-dc-home" id="doublecheck"><div class="s-dc-home-texto">
  {selo()}
  <h2>IA é poderosa. Mas não é infalível.</h2>
  <p class="s-lead">Por isso criamos o <b>KASISKI DoubleCheck™</b>. Em cada análise crítica, um modelo de inteligência artificial faz a análise e um
    segundo modelo atua como verificador independente. O Kasiski confronta os resultados, identifica divergências e mantém cada informação
    ligada à sua fonte no documento original.</p>
  <p class="s-dc-assinatura">{esc(ASSINATURA)}</p>
  <div class="s-acoes"><a class="s-botao s-botao-sec" href="/doublecheck/" data-cta="home_doublecheck">Como o DoubleCheck funciona</a></div></div>
  {diagrama()}</section>'''


FAQ = [("O DoubleCheck garante que a análise está certa?",
        "Não. Ele reduz o risco de inconsistências e mostra onde os modelos discordam, mas não constitui garantia de ausência de erros. "
        "Por isso cada conclusão vem com a fonte e a decisão fica com você."),
       ("Por que usar duas IAs em vez de uma?",
        "Modelos de linguagem podem afirmar com segurança algo que o documento não diz. Um segundo modelo, instruído a ser cético e a reler o "
        "documento, funciona como verificador independente e expõe esses casos."),
       ("O que acontece quando os modelos discordam?",
        "O item aparece com o selo Divergência e as duas leituras lado a lado, com o trecho e a página do documento. Na análise de concorrentes, "
        "o que não se confirma não entra no parecer nem nas sugestões de recurso."),
       ("Quais modelos de IA o Kasiski usa?",
        "O protocolo usa modelos de fornecedores diferentes para a análise e para a verificação, e pode trocá-los conforme a qualidade de cada "
        "um evolui. Por isso, na plataforma, eles aparecem como KASISKI Analysis Engine e KASISKI Verification Engine."),
       ("O DoubleCheck substitui a revisão de um advogado?",
        "Não. Ele aumenta a confiabilidade, mas decisões e peças devem ser revisadas por quem conhece o caso. Se quiser, você pode pedir a revisão "
        "de um advogado dentro do Kasiski."),
       ("Em quais planos o DoubleCheck está disponível?",
        "Em todos, inclusive no Free: toda análise de edital, de concorrente e de ata, e toda peça gerada no Kasiski passam pela verificação.")]

ONDE = [("Análise do edital", "Cada exigência de habilitação e setorial, cada cláusula restritiva e cada risco recebe o selo, com a página de origem."),
        ("Cofre de documentos", "A correspondência entre o que o edital exige e o documento do seu cofre também é conferida."),
        ("Concorrentes", "Falhas na habilitação ou na proposta do adversário só entram no parecer depois de confirmadas."),
        ("Atas da licitação", "As peças sugeridas a partir da ata (recurso, contrarrazões) vêm com o resultado da verificação."),
        ("Peças e impugnações", "Depois de redigida, a minuta passa por um verificador que procura erro factual, argumento sem suporte, referência errada e contradição."),
        ("Painel", "Você vê quantos itens foram conferidos e quantas divergências o DoubleCheck encontrou antes de chegarem à sua equipe.")]


def pg_doublecheck(pagina, migalhas, SOFT):
    cab, ld = migalhas([("Início", "/"), ("Soluções", None), ("DoubleCheck™", None)])
    onde = "".join(f'<div class="s-item"><b>{esc(t)}</b><p>{esc(d)}</p></div>' for t, d in ONDE)
    perg = "".join(f'<details class="s-duvida"><summary>{esc(q)}</summary><p>{esc(a)}</p></details>' for q, a in FAQ)
    faq_ld = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in FAQ]}
    exemplo = f'''<div class="s-dc-exemplo" aria-label="Exemplo de verificação">
    <div class="s-dc-ex-cab">{simbolo(18)}<b>KASISKI DoubleCheck™</b></div>
    <ol>
      <li><b>Análise primária</b><small>KASISKI Analysis Engine</small><p>Identificou a exigência de índices LG, SG e LC superiores a 1,00.</p></li>
      <li><b>Verificação independente</b><small>KASISKI Verification Engine</small><p>Confirmou a exigência e a referência no edital. Nenhuma divergência encontrada.</p></li>
      <li><b>Resultado</b><p><span class="s-dc-res">Concordância entre modelos</span></p><p class="s-nota">2 análises independentes · fonte rastreável</p></li>
    </ol>
    <blockquote><small>Trecho do edital · item 9.7.3 · pág. 34</small>“A comprovação da qualificação econômico-financeira deverá ser feita mediante índices LG, SG e LC superiores a 1,00.”</blockquote>
  </div>
  <div class="s-dc-exemplo s-dc-exemplo-div" aria-label="Exemplo de divergência">
    <div class="s-dc-ex-cab">{simbolo(18)}<b>DoubleCheck™ · Divergência</b></div>
    <p>Os modelos chegaram a interpretações diferentes sobre esta exigência.</p>
    <div class="s-dc-lado"><div><small>Modelo de análise</small><p>Entendeu que é exigida experiência mínima de 24 meses.</p></div>
      <div><small>Modelo verificador</small><p>Os 24 meses se referem ao período do contrato, não à experiência mínima.</p></div></div>
    <p class="s-nota">Fonte: edital, item 12.3.1, pág. 47 · <b>Revisão recomendada</b></p>
  </div>'''
    corpo = f'''{cab}<section class="s-heroi s-dc-heroi"><div class="s-heroi-texto">{selo()}
  <p class="s-sobre">Não perguntamos apenas à IA.</p><h1>Nós conferimos a resposta.</h1>
  <p class="s-lead">O <b>KASISKI DoubleCheck™</b> é o protocolo de verificação cruzada do Kasiski: em cada análise crítica, uma IA analisa, outra confere
    de forma independente e o sistema confronta os resultados com o documento original. Onde os modelos concordam, você ganha confiança.
    Onde discordam, você vê a divergência antes de decidir.</p>
  <p class="s-dc-assinatura">{esc(ASSINATURA)}</p>
  <div class="s-acoes"><a class="s-botao s-botao-grande" href="{C.APP_CADASTRO}" data-cta="doublecheck_heroi">Criar conta grátis</a>
    <a class="s-botao s-botao-sec" href="/analisar-edital/">Analisar um edital grátis</a></div></div></section>
<section class="s-secao"><p class="s-sobre">Como funciona</p><h2>Documento → duas análises → confronto → fonte → decisão humana</h2>{diagrama(animado=True)}</section>
<section class="s-secao s-secao-clara"><p class="s-sobre">Três estados</p><h2>O selo diz o que aconteceu. Sem depender só da cor.</h2>
  <div class="s-grade3">{estados_html()}</div></section>
<section class="s-secao"><p class="s-sobre">Na prática</p><h2>Não é um selo decorativo. Dá para abrir a verificação.</h2>
  <div class="s-grade2 s-dc-exemplos">{exemplo}</div></section>
<section class="s-secao s-secao-clara"><p class="s-sobre">Comparativo</p><h2>Decisões importantes merecem uma segunda verificação.</h2>
  <div class="s-grade2 s-dc-compara"><div class="s-item"><b>IA convencional</b><p class="s-dc-fluxo">Documento → IA → resposta</p>
    <p>Uma única leitura. Se o modelo se engana com segurança, o erro chega até você com cara de certeza.</p></div>
    <div class="s-item s-dc-destaque"><b>KASISKI DoubleCheck™</b><p class="s-dc-fluxo">Documento → IA 1 + IA 2 → confronto → fonte → resultado</p>
    <p>Não adicionamos outra IA para parecer mais tecnológico. Adicionamos porque uma leitura errada pode custar uma licitação.</p></div></div></section>
<section class="s-secao"><p class="s-sobre">Onde atua</p><h2>O DoubleCheck está em toda a plataforma</h2><div class="s-grade3">{onde}</div></section>
<section class="s-secao s-secao-clara s-faq-sol"><div class="s-estreito"><h2>Perguntas frequentes</h2>{perg}
  <p class="s-nota">As conclusões com o selo DoubleCheck passaram pelo protocolo de verificação cruzada automatizada da plataforma. O processo reduz o risco
    de inconsistências, mas não constitui garantia de ausência de erros.</p></div></section>
<section class="s-secao s-faixa"><h2>{esc(MANIFESTO)}</h2><p>Uma IA pode errar. Por isso o Kasiski usa duas — e mostra quando elas discordam.</p>
  <a class="s-botao s-botao-grande" href="{C.APP_CADASTRO}" data-cta="doublecheck_rodape">Conhecer o Kasiski</a></section>'''
    pagina("/doublecheck/", "KASISKI DoubleCheck™ — verificação cruzada de IA em licitações | Kasiski",
           "Uma IA analisa. Outra confere. Você decide. Conheça o DoubleCheck, o protocolo de verificação cruzada que confronta duas análises de IA com a fonte do edital.",
           corpo, prioridade="0.9", jsonld=[ld, SOFT, faq_ld])
