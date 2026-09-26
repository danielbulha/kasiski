"""Página inicial estática de kasiski.com.br (chamada por gerar.py)."""
import html

import conteudo as C

esc = html.escape


def _qtd(n, s, p):
    return f"{n} {s if n == 1 else p}"


def cartao_plano(codigo, v):
    destaque = codigo == "profissional"
    selo = C.SELO_PLANO.get(codigo)

    def item(ok, texto, campo=None, novo=False):
        dc = f' data-campo="{campo}"' if campo else ""
        nv = ' <b class="s-novo">novo</b>' if novo and ok else ""
        return f'<li class="{"" if ok else "fora"}"{dc}><span aria-hidden="true">{"✓" if ok else "–"}</span><span>{esc(texto)}{nv}</span></li>'

    itens = [
        item(True, _qtd(v["empresas"], "empresa (CNPJ)", "empresas (CNPJs)"), "empresas"),
        item(True, f'{_qtd(v["analises"], "análise", "análises")} de edital por mês', "analises"),
        item(bool(v["concorrentes"]), f'{_qtd(v["concorrentes"], "análise", "análises")} de concorrente por mês' if v["concorrentes"] else "Análise de concorrentes", "concorrentes"),
        item(bool(v.get("possiveis")), f'{_qtd(v.get("possiveis", 0), "avaliação", "avaliações")} de possíveis concorrentes por mês', "possiveis"),
        item(True, "Radar diário, cofre e agenda de prazos"),
        item(v["pecas"], "Gerador de peças"),
        item(v["precos"], "Inteligência de preços"),
        item(v["propostas"], "Proposta comercial com IA e exportação em Word", novo=True),
        item(bool(v["contratos"]), f'Gestão de contratos com IA (até {v["contratos"]})' if v["contratos"] else "Gestão de contratos", "contratos"),
    ]
    if v.get("marca"):
        itens.append(item(True, "Relatórios com a marca do escritório"))
    preco = f'R$ {v["preco"]:,.0f}'.replace(",", ".")
    selo_html = f'<span class="s-selo">{esc(selo)}</span>' if selo else ""
    return (f'<div class="s-plano{" destaque" if destaque else ""}" data-plano="{codigo}">{selo_html}'
            f'<h3>{esc(v["nome"])}</h3><p class="s-plano-publico">{esc(C.PUBLICO_PLANO.get(codigo, ""))}</p>'
            f'<p class="s-preco"><span data-preco>{preco}</span><small>/mês</small></p><ul>{"".join(itens)}</ul>'
            f'<a class="s-botao{"" if destaque else " s-botao-sec"}" href="{C.APP_CADASTRO}" data-cta="plano_{codigo}">Começar pelo teste grátis</a></div>')


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
           ("Como funciona a proposta comercial com IA?", "Nos planos Avançado e Consultor, o Kasiski lê no edital o que a proposta precisa conter, ajuda a formar o preço com custos, BDI e tributos, compara com preços praticados e tabelas oficiais, avisa riscos de inexequibilidade e entrega a minuta em Word."),
           ("De onde vêm os dados?", "De fontes públicas oficiais: PNCP (editais, contratos e atas), Receita Federal, TCU e Portal da Transparência (sanções) e Compras.gov.br (preços praticados). Editais fora do PNCP podem ser enviados em PDF."),
           ("Como a IA evita erros?", "Cada cláusula restritiva, risco ou falha de concorrente apontada por um modelo é conferida por um segundo modelo, de outro fornecedor. O resultado aparece ao lado de cada ponto, com a página do documento de origem."),
           ("Funciona para dispensa e inexigibilidade?", "Sim. Nesses casos o sistema não aplica os prazos de pregão: calcula o prazo de divulgação do aviso de contratação direta e avalia se a hipótese legal está bem enquadrada."),
           ("Posso atender várias empresas?", "Sim, no plano Consultor: até 10 CNPJs na mesma conta, com cofre, radar e agenda separados por empresa e relatórios com a marca do seu escritório."),
           ("Meus documentos ficam separados de outras empresas?", "Sim. Cada conta só acessa as próprias empresas, editais e documentos."),
           ("Preciso de cartão para testar?", "Não. O teste é gratuito e não pede cartão. Para continuar depois, basta escolher um plano.")]


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
    t = C.PLANOS["trial"]
    ta = f'<span data-trial-analises>{t["analises"]}</span>'
    faq_ld = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": p, "acceptedAnswer": {"@type": "Answer", "text": r}} for p, r in DUVIDAS]}
    pagos = [k for k in ("essencial", "profissional", "avancado", "consultor") if k in C.PLANOS]
    passos = "".join(f'<div class="s-passo-escuro"><span>{n}</span><b>{esc(ti)}</b><p>{esc(tx)}</p></div>' for n, ti, tx in PASSOS)
    recursos = "".join((f'<a class="s-item s-item-link" href="{u}">' if u else '<div class="s-item">') + f'<b>{esc(ti)}</b><p>{esc(tx)}</p>' + ("</a>" if u else "</div>")
                       for ti, tx, u in RECURSOS)
    setores = "".join(f"<span>{esc(s)}</span>" for s in SETORES)
    duvidas = "".join(f'<details class="s-duvida"><summary>{esc(p)}</summary><p>{esc(r)}</p></details>' for p, r in DUVIDAS)
    planos = "".join(cartao_plano(k, C.PLANOS[k]) for k in pagos)
    cad = C.APP_CADASTRO
    corpo = f"""{REDIRECIONA_APP}
<section class="s-heroi"><div class="s-heroi-texto"><p class="s-sobre">Encontre o padrão. Descubra a oportunidade.</p>
  <h1>Inteligência para vender ao poder público.</h1>
  <p class="s-lead">O Kasiski monitora os editais publicados no PNCP, confere a habilitação da sua empresa, analisa concorrentes e redige impugnações e recursos — com cada conclusão da IA conferida por um segundo modelo.</p>
  <div class="s-acoes"><a class="s-botao s-botao-grande" href="{cad}" data-cta="home_heroi">Testar grátis por {C.TRIAL_DIAS} dias</a>
    <a class="s-botao s-botao-sec s-botao-grande" href="/analisar-edital/" data-cta="home_analisar">Analisar um edital grátis</a></div>
  <p class="s-nota">{ta} análises de edital incluídas no teste · sem cartão de crédito · cancele quando quiser</p></div>
  {previa()}</section>
<section class="s-secao s-faixa s-faixa-esq" id="como"><p class="s-sobre s-sobre-claro">Do ruído ao sinal</p>
  <h2>Milhares de editais por semana. Poucos fazem sentido para você.</h2><div class="s-grade3">{passos}</div></section>
<section class="s-secao" id="recursos"><p class="s-sobre">Recursos</p><h2>Tudo o que a disputa exige, do edital ao contrato.</h2><div class="s-grade3">{recursos}</div></section>
<section class="s-secao s-secao-clara"><p class="s-sobre">Setores</p><h2>Regras gerais da Lei 14.133 e exigências de cada setor.</h2>
  <p class="s-lead">Além da habilitação padrão, a análise considera as exigências regulatórias do tipo de objeto e do segmento — como ANVISA na saúde, PNAE na educação, ART/RRT em obras e autorização da Polícia Federal na vigilância.</p>
  <div class="s-setores">{setores}</div></section>
<section class="s-secao s-faixa"><h2>{C.TRIAL_DIAS} dias para analisar editais reais da sua empresa.</h2>
  <p>O teste inclui {ta} análises completas de edital, análise de concorrente, o gerador de peças e a inteligência de preços. Sem cartão de crédito.</p>
  <a class="s-botao s-botao-grande" href="{cad}" data-cta="home_faixa">Criar conta grátis</a></section>
<section class="s-secao" id="planos"><p class="s-sobre">Planos</p><h2>Preço fixo por mês. Sem taxa de êxito.</h2>
  <div class="s-planos">{planos}</div>
  <p class="s-nota s-centro">Valores mensais. No plano anual você paga 10 meses e leva 12. Precisa de mais contratos? Pacotes de +10 contratos por R$ 169,90/mês.</p></section>
<section class="s-secao s-secao-clara" id="duvidas"><div class="s-estreito"><p class="s-sobre">Dúvidas frequentes</p><h2>Antes de começar</h2>{duvidas}</div></section>
<section class="s-secao s-faixa"><h2>Encontre o padrão. Descubra a oportunidade.</h2>
  <p>Comece com {ta} análises gratuitas e veja o que o Kasiski encontra nos editais do seu setor.</p>
  <a class="s-botao s-botao-grande" href="{cad}" data-cta="home_final">Testar grátis por {C.TRIAL_DIAS} dias</a></section>"""
    pagina("/", "Kasiski — inteligência para vender ao poder público | licitações com IA",
           "Radar de editais no PNCP, análise de edital com IA, Go/No-Go, concorrentes, preços, propostas e gestão de contratos. Teste grátis por 7 dias, sem cartão.",
           corpo, prioridade="1.0", jsonld=[ORG, SOFT, faq_ld])
