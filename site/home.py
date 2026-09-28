"""Página inicial estática de kasiski.com.br (chamada por gerar.py)."""
import html

import conteudo as C

esc = html.escape


def _qtd(n, s, p):
    return f"{n} {s if n == 1 else p}"


def cartao_plano(codigo, v):
    destaque = bool(v.get("destaque"))
    selo = "Mais escolhido" if destaque else None

    def item(ok, texto, campo=None):
        dc = f' data-campo="{campo}"' if campo else ""
        return f'<li class="{"" if ok else "fora"}"{dc}><span aria-hidden="true">{"✓" if ok else "–"}</span><span>{esc(texto)}</span></li>'

    itens = [
        item(True, f'{_qtd(v["empresas"], "empresa", "empresas")} · {_qtd(v["usuarios"], "usuário", "usuários")}', "empresas"),
        item(True, f'{_qtd(v["analises"], "análise", "análises")} de edital com IA por mês', "analises"),
        item(bool(v["concorrentes"]), f'{_qtd(v["concorrentes"], "análise", "análises")} de concorrente por mês', "concorrentes"),
        item(True, "Radar limitado aos 10 melhores editais" if v.get("radar_max") else "Radar completo no PNCP"),
        item(True, "Diagnóstico B2G, checklist e cofre básico" if v.get("cofre_max") else "Cofre, checklist, agenda e pipeline"),
        item(v["precos"], "Inteligência de preços e propostas com IA"),
        item(bool(v["pecas"]), f'{v["pecas"]} peças com IA por mês' if v["pecas"] else "Peças com IA"),
        item(bool(v["contratos"]), f'Gestão de até {v["contratos"]} contratos' if v["contratos"] else "Gestão de contratos"),
    ]
    if v.get("prioridade"):
        itens.append(item(True, "Prioridade de processamento e suporte"))
    if v.get("marca"):
        itens.append(item(True, "Relatórios com a marca do escritório"))
    if v.get("empresa_extra"):
        itens.append(item(True, f'Empresa adicional por R$ {v["empresa_extra"]}/mês'))
    preco = f'R$ {v["preco"]:,.0f}'.replace(",", ".")
    selo_html = f'<span class="s-selo">{esc(selo)}</span>' if selo else ""
    cta = "Criar conta grátis" if codigo == "free" else ("Experimentar por 7 dias" if codigo == "profissional" else "Começar grátis")
    return (f'<div class="s-plano{" destaque" if destaque else ""}" data-plano="{codigo}">{selo_html}'
            f'<h3>{esc(v["nome"])}</h3><p class="s-plano-publico">{esc(v.get("slogan", ""))}</p>'
            f'<p class="s-preco"><span data-preco>{preco}</span><small>/mês</small></p><ul>{"".join(itens)}</ul>'
            f'<a class="s-botao{"" if destaque else " s-botao-sec"}" href="{C.APP_CADASTRO}" data-cta="plano_{codigo}">{cta}</a></div>')


def tabela_comparativa():
    ks = [k for k in C.ORDEM_PLANOS if k != "enterprise"]
    P = C.PLANOS

    def v(x):
        return "✓" if x is True else "—" if x in (False, 0, None) else esc(str(x))
    linhas = [("Preço/mês", lambda p: "R$ 0" if not p["preco"] else f'R$ {p["preco"]:,.0f}'.replace(",", ".")),
              ("Empresas", lambda p: p["empresas"]), ("Usuários", lambda p: p["usuarios"]),
              ("Diagnóstico B2G e checklist", lambda p: True), ("Radar", lambda p: "Limitado" if p["radar_max"] else True),
              ("Cofre", lambda p: "Básico" if p["cofre_max"] else True), ("Editais com IA/mês", lambda p: p["analises"]),
              ("Go/No-Go", lambda p: "Básico" if p["analises"] <= 5 else True),
              ("Concorrentes/mês", lambda p: p["concorrentes"]), ("Preços", lambda p: p["precos"]), ("Propostas", lambda p: p["propostas"]),
              ("Peças com IA/mês", lambda p: p["pecas"]), ("Contratos", lambda p: p["contratos"]),
              ("Multiempresa", lambda p: p["empresas"] if p["empresas"] > 1 else False)]
    cab = "".join(f"<th>{esc(P[k]['nome'])}</th>" for k in ks)
    corpo = "".join(f"<tr><td>{esc(r)}</td>" + "".join(f"<td>{v(f(P[k]))}</td>" for k in ks) + "</tr>" for r, f in linhas)
    return f'<div class="s-tabela-rolagem"><table class="s-comparativo"><thead><tr><th></th>{cab}</tr></thead><tbody>{corpo}</tbody></table></div>'


PASSOS = [("01", "Detectar", "Todo dia útil, o radar consulta o PNCP e separa os editais abertos que combinam com as palavras-chave, os estados e a faixa de valor da sua empresa."),
          ("02", "Interpretar", "A análise lê o edital inteiro, extrai exigências e prazos, compara a habilitação com os documentos do seu cofre e aponta cláusulas restritivas."),
          ("03", "Agir", "Você recebe a recomendação de participar ou não, os prazos na agenda e a minuta da peça pronta para revisão — esclarecimento, impugnação ou recurso.")]
RECURSOS = [("Radar de editais", "Busca diária no PNCP com nota de aderência de 0 a 100 para cada edital encontrado.", "/radar-licitacoes/"),
            ("Análise do edital", "Resumo, checklist de habilitação, riscos e recomendação de participar, com a página de cada ponto.", "/analisar-edital/"),
            ("Verificação cruzada", "Um modelo de IA analisa, outro de fornecedor diferente confere. O que não se confirma, você vê como não confirmado.", None),
            ("Pipeline Go / No-Go", "Kanban da oportunidade, do edital identificado ao contrato ativo, com fit, risco e movimentação automática pelo PNCP.", "/go-no-go/"),
            ("Cofre de habilitação", "Certidões e atestados com controle de validade. Alerta antes de vencer, não depois.", "/habilitacao/"),
            ("Inteligência de concorrentes", "Possíveis concorrentes, dossiê do CNPJ, sanções no TCU e na CGU e análise da habilitação e da proposta do adversário.", "/concorrentes/"),
            ("Gerador de peças", "Minutas de esclarecimento, impugnação, recurso, contrarrazões, reequilíbrio e defesa prévia.", None),
            ("Preços e proposta comercial", "Preços praticados, tabelas oficiais (SINAPI, CMED, convenções coletivas) e a minuta da proposta com BDI e checagem de exequibilidade.", "/propostas/"),
            ("Gestão de contratos", "Envie o PDF: a IA preenche vigência, garantia, reajuste, medição e faturamento e avisa antes de cada prazo.", "/gestao-contratos/")]
SETORES = ["Obras e engenharia", "Serviços continuados", "Fornecimento e registro de preços", "Saúde", "Educação", "Tecnologia da informação",
           "Segurança e vigilância", "Transporte e frota", "Alimentação", "Dispensa e inexigibilidade"]
DUVIDAS = [("O Kasiski substitui um advogado?", "Não. As peças são minutas fundamentadas para você revisar antes de protocolar. Se preferir, é possível solicitar dentro do sistema a revisão por advogado, contratada à parte."),
           ("Qual a diferença entre o Kasiski e um buscador de licitações?", "Buscadores encontram editais; o Kasiski ajuda a decidir onde competir. Depois da busca vêm a aderência, a leitura do edital, a habilitação, o Go/No-Go, os preços, os concorrentes, a proposta, as peças, os prazos e o contrato — tudo no mesmo lugar."),
           ("Como funciona a proposta comercial com IA?", "A partir do Profissional, o Kasiski lê no edital o que a proposta precisa conter, ajuda a formar o preço com custos, BDI e tributos, compara com preços praticados e tabelas oficiais, avisa riscos de inexequibilidade e entrega a minuta em Word."),
           ("De onde vêm os dados?", "De fontes públicas oficiais: PNCP (editais, contratos e atas), Receita Federal, TCU e Portal da Transparência (sanções) e Compras.gov.br (preços praticados). Editais fora do PNCP podem ser enviados em PDF."),
           ("Como a IA evita erros?", "Cada cláusula restritiva, risco ou falha de concorrente apontada por um modelo é conferida por um segundo modelo, de outro fornecedor. O resultado aparece ao lado de cada ponto, com a página do documento de origem."),
           ("Funciona para dispensa e inexigibilidade?", "Sim. Nesses casos o sistema não aplica os prazos de pregão: calcula o prazo de divulgação do aviso de contratação direta e avalia se a hipótese legal está bem enquadrada."),
           ("Posso atender várias empresas?", "Sim, no plano Consultor: até 10 CNPJs na mesma conta, com cofre, radar e agenda separados por empresa e relatórios com a marca do seu escritório."),
           ("Meus documentos ficam separados de outras empresas?", "Sim. Cada conta só acessa as próprias empresas, editais e documentos."),
           ("O plano Free é grátis mesmo?", "Sim, para sempre e sem cartão: diagnóstico B2G, checklist de habilitação, cofre básico, radar limitado e 1 análise de edital por mês. Dentro dele você pode experimentar o Profissional por 7 dias; no fim, a conta volta ao Free sem perder nada."),
           ("Como funciona o plano anual?", "Você paga 10 mensalidades e usa 12 meses, em qualquer plano pago."),
           ("E se eu passar do limite do mês?", "Você pode fazer upgrade ou comprar um Pacote de inteligência (+10 análises de edital e +5 de concorrentes por R$ 97), sem mudar de plano.")]


def _linha(txt, rot, tipo):
    return f'<div class="s-previa-linha"><span>{esc(txt)}</span><em class="s-carimbo {tipo}">{esc(rot)}</em></div>'


def previa():
    return ('<div class="s-previa" aria-hidden="true"><div class="s-previa-capa"><div><small>Pregão eletrônico 45/2026 · Prefeitura Municipal</small>'
            '<b>Serviços contínuos de limpeza predial</b></div><em class="s-carimbo aviso grande">Com ressalvas</em></div>'
            '<div class="s-previa-corpo"><p class="s-previa-titulo">Checklist de habilitação</p>'
            + _linha("CND federal conjunta", "Atende", "ok") + _linha("CRF do FGTS", "Atende", "ok")
            + _linha("CNDT", "Vencido", "erro") + _linha("Atestado de capacidade técnica", "Falta", "erro")
            + '<p class="s-previa-titulo">Cláusula restritiva</p><div class="s-previa-ponto"><b>Atestado de 100% da área licitada</b>'
              '<span>Lei 14.133, art. 67, §2º · pág. 15</span><span>Verificação cruzada <em class="s-carimbo ok">Confirmado</em></span></div>'
              '<p class="s-previa-titulo">Prazos</p>' + _linha("Último dia para impugnar", "Em 4 dias", "aviso") + "</div></div>")


# Links antigos do app (kasiski.com.br/#/painel) e retornos (pagamento, verificação) seguem para o app.
REDIRECIONA_APP = ('<script>(function(){var h=location.hash||"",q=location.search||"",a=(window.CERTAME&&CERTAME.APP_URL)||"%s";'
                   'if(h.indexOf("#/")===0||/pagamento=|verificar=/.test(q)){location.replace(a+"/"+q+h);}})();</script>') % C.APP_URL


def pg_home(pagina, ORG, SOFT):
    f = C.PLANOS["free"]
    ta = f'<span data-free-analises>{f["analises"]}</span>'
    faq_ld = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": p, "acceptedAnswer": {"@type": "Answer", "text": r}} for p, r in DUVIDAS]}
    visiveis = [k for k in C.ORDEM_PLANOS if k != "enterprise" and k in C.PLANOS]
    passos = "".join(f'<div class="s-passo-escuro"><span>{n}</span><b>{esc(ti)}</b><p>{esc(tx)}</p></div>' for n, ti, tx in PASSOS)
    recursos = "".join((f'<a class="s-item s-item-link" href="{u}">' if u else '<div class="s-item">') + f'<b>{esc(ti)}</b><p>{esc(tx)}</p>' + ("</a>" if u else "</div>")
                       for ti, tx, u in RECURSOS)
    setores = "".join(f"<span>{esc(s)}</span>" for s in SETORES)
    duvidas = "".join(f'<details class="s-duvida"><summary>{esc(p)}</summary><p>{esc(r)}</p></details>' for p, r in DUVIDAS)
    planos = "".join(cartao_plano(k, C.PLANOS[k]) for k in visiveis)
    cad = C.APP_CADASTRO
    corpo = f"""{REDIRECIONA_APP}
<section class="s-heroi"><div class="s-heroi-texto"><p class="s-sobre">Buscadores encontram editais. O Kasiski ajuda a decidir onde competir.</p>
  <h1>Inteligência para vender ao poder público.</h1>
  <p class="s-lead">O Kasiski monitora os editais publicados no PNCP, confere a habilitação da sua empresa, analisa concorrentes e redige impugnações e recursos — com cada conclusão da IA conferida por um segundo modelo.</p>
  <div class="s-acoes"><a class="s-botao s-botao-grande" href="{cad}" data-cta="home_heroi">Criar conta grátis</a>
    <a class="s-botao s-botao-sec s-botao-grande" href="/diagnostico/" data-cta="home_diagnostico">Fazer o diagnóstico B2G</a></div>
  <p class="s-nota">Free para sempre · {ta} análise de edital por mês · experimente o Profissional por {C.TRIAL_DIAS} dias · sem cartão</p></div>
  {previa()}</section>
<section class="s-secao s-faixa s-faixa-esq" id="como"><p class="s-sobre s-sobre-claro">Do ruído ao sinal</p>
  <h2>Milhares de editais por semana. Poucos fazem sentido para você.</h2><div class="s-grade3">{passos}</div></section>
<section class="s-secao" id="recursos"><p class="s-sobre">Recursos</p><h2>Tudo o que a disputa exige, do edital ao contrato.</h2><div class="s-grade3">{recursos}</div></section>
<section class="s-secao s-secao-clara"><p class="s-sobre">Setores</p><h2>Regras gerais da Lei 14.133 e exigências de cada setor.</h2>
  <p class="s-lead">Além da habilitação padrão, a análise considera as exigências regulatórias do tipo de objeto e do segmento — como ANVISA na saúde, PNAE na educação, ART/RRT em obras e autorização da Polícia Federal na vigilância.</p>
  <div class="s-setores">{setores}</div></section>
<section class="s-secao s-faixa"><h2>Comece grátis. Evolua quando fizer sentido.</h2>
  <p>A conta Free não expira: diagnóstico, checklist, cofre, radar e {ta} análise completa de edital por mês. Quando quiser, experimente o Profissional por {C.TRIAL_DIAS} dias — no fim, a conta volta ao Free sem perder nada.</p>
  <a class="s-botao s-botao-grande" href="{cad}" data-cta="home_faixa">Criar conta grátis</a></section>
<section class="s-secao" id="planos"><p class="s-sobre">Planos</p><h2>Preço fixo por mês. Sem taxa de êxito.</h2>
  <div class="s-planos s-planos-5">{planos}</div>
  <div class="s-enterprise"><div><b>Kasiski Enterprise</b> · sob consulta<br><small>Muitos CNPJs e usuários, grandes volumes, integrações e API, SSO, SLA, onboarding e suporte dedicado.</small></div>
    <a class="s-botao s-botao-sec" href="mailto:{C.EMPRESA["email_contato"]}?subject=Kasiski%20Enterprise" data-cta="plano_enterprise">Falar com a gente</a></div>
  <details class="s-comparar"><summary>Comparar todos os recursos</summary>{tabela_comparativa()}</details>
  <p class="s-nota s-centro">Valores mensais. No anual você paga 10 meses e usa 12. Acabou o limite do mês? Pacote de inteligência (+10 análises de edital e +5 de concorrentes) por R$ 97.</p></section>
<section class="s-secao s-secao-clara" id="duvidas"><div class="s-estreito"><p class="s-sobre">Dúvidas frequentes</p><h2>Antes de começar</h2>{duvidas}</div></section>
<section class="s-secao s-faixa"><h2>Encontre o padrão. Descubra a oportunidade.</h2>
  <p>Crie sua conta Free e veja o que o Kasiski encontra nos editais do seu setor.</p>
  <a class="s-botao s-botao-grande" href="{cad}" data-cta="home_final">Criar conta grátis</a></section>"""
    pagina("/", "Kasiski — inteligência para vender ao poder público | licitações com IA",
           "Radar de editais no PNCP, análise de edital com IA, Go/No-Go, concorrentes, preços, propostas e gestão de contratos. Plano Free para sempre; Profissional por R$ 247/mês.",
           corpo, prioridade="1.0", jsonld=[ORG, SOFT, faq_ld])
