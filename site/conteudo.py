"""Conteúdo do site público do Kasiski (páginas geradas por site/gerar.py em frontend/).

Edite aqui textos de soluções, landing pages, glossário e dados do controlador (LGPD). Artigos de
/inteligencia ficam em site/artigos/*.md (front matter simples: titulo, descricao, categoria, data).
"""

SITE_URL = "https://kasiski.com.br"            # site público (esta pasta gera publico/)
APP_URL = "https://app.kasiski.com.br"         # aplicativo (pasta frontend/)
APP_CADASTRO = APP_URL + "/#/cadastro"
APP_ENTRAR = APP_URL + "/#/entrar"

# Planos exibidos na página inicial. A fonte oficial é backend/planos.py: a página confere os valores na API
# (/api/planos) ao carregar, então mudanças de preço aparecem mesmo sem gerar o site de novo.
TRIAL_DIAS = 7
PLANOS = {
    "trial": {"nome": "Teste grátis", "preco": 0, "empresas": 1, "analises": 2, "concorrentes": 1, "possiveis": 1, "pecas": True, "precos": True, "propostas": False, "contratos": 1, "marca": False},
    "essencial": {"nome": "Essencial", "preco": 197, "empresas": 1, "analises": 5, "concorrentes": 0, "possiveis": 2, "pecas": False, "precos": False, "propostas": False, "contratos": 0, "marca": False},
    "profissional": {"nome": "Profissional", "preco": 497, "empresas": 1, "analises": 20, "concorrentes": 5, "possiveis": 5, "pecas": True, "precos": True, "propostas": False, "contratos": 10, "marca": False},
    "avancado": {"nome": "Avançado", "preco": 799, "empresas": 3, "analises": 40, "concorrentes": 15, "possiveis": 15, "pecas": True, "precos": True, "propostas": True, "contratos": 30, "marca": False},
    "consultor": {"nome": "Consultor", "preco": 1290, "empresas": 10, "analises": 60, "concorrentes": 30, "possiveis": 25, "pecas": True, "precos": True, "propostas": True, "contratos": 50, "marca": True},
}
PUBLICO_PLANO = {"essencial": "Para quem está começando a licitar", "profissional": "Para empresas que disputam todo mês",
                 "avancado": "Para quem quer a proposta pronta, com preço calculado", "consultor": "Para escritórios e consultorias de licitação"}
SELO_PLANO = {"profissional": "Indicado para PMEs", "avancado": "Proposta comercial com IA"}

# Controlador dos dados pessoais (Política de Privacidade, Termos). Preencha CNPJ e endereço antes de publicar.
EMPRESA = {
    "razao": "D.B.C. Consultoria e Serviços Ltda.",
    "cnpj": "01.152.886/0001-51",            # ex.: "00.000.000/0001-00"
    "endereco": "Rua Pamplona, 145, cj 02 - São Paulo/SP - CEP 01405-900",        # ex.: "Rua X, 123 — Juquitiba/SP — CEP 00000-000"
    "email_contato": "contato@kasiski.com.br",
    "email_privacidade": "privacidade@kasiski.com.br",
    "encarregado": "Encarregado pelo tratamento de dados (DPO) do Kasiski",
    "foro": "Comarca de São Paulo/SP",
    "atualizado": "26/09/2026",
}

# ---------------------------------------------------------------- soluções (/radar-licitacoes etc.)
SOLUCOES = [
    {"slug": "radar-licitacoes", "nome": "Radar de licitações", "icone": "radar",
     "titulo": "Encontre as licitações certas para a sua empresa, todos os dias",
     "descricao": "O Radar do Kasiski busca editais no PNCP pelas palavras-chave, CNAEs, UFs e faixa de valor da sua empresa e dá uma nota de aderência a cada oportunidade.",
     "pontos": [("Busca diária no PNCP", "Editais recebendo propostas, filtrados pelo perfil de cada empresa — sem planilhas e sem garimpo manual."),
                ("Nota de aderência", "Cada edital recebe uma nota de 0 a 100 e o motivo, para você decidir rápido o que vale analisar."),
                ("Do radar ao pipeline", "Um clique leva o edital para o quadro de oportunidades, com prazos de esclarecimento e impugnação calculados.")],
     "cta": "Configurar meu radar grátis", "lp": "/lp/radar/"},
    {"slug": "go-no-go", "nome": "Decisão Go / No-Go", "icone": "decisao",
     "titulo": "Decida com critério se vale a pena disputar cada licitação",
     "descricao": "Fit, risco e recomendação da IA para cada edital, e um pipeline comercial que registra quem decidiu, quando e por quê.",
     "pontos": [("Fit da oportunidade", "Aderência da habilitação da sua empresa ao edital, combinada com a recomendação da IA."),
                ("Risco em um olhar", "Cláusulas restritivas e riscos contratuais classificados por gravidade, conferidos por uma segunda IA."),
                ("Histórico de decisões", "Go e No-Go com motivo registrado: a próxima decisão fica mais rápida e melhor.")],
     "cta": "Testar grátis", "lp": "/lp/analisar-edital/"},
    {"slug": "concorrentes", "nome": "Inteligência de concorrentes", "icone": "concorrentes",
     "titulo": "Saiba quem você vai enfrentar antes da sessão",
     "descricao": "Dossiê do concorrente com dados da Receita, sanções no TCU e na CGU, contratos e atas no PNCP, inabilitações anteriores e pontos de ataque para recursos.",
     "pontos": [("Possíveis concorrentes", "Empresas que venceram contratações com objeto parecido, ordenadas por frequência, região e órgão."),
                ("Dossiê completo", "Histórico público, sanções, atestados e decisões de outros certames consolidados pela IA."),
                ("Análise de habilitação e proposta", "Envie os documentos do adversário e receba apontamentos confirmados para recurso.")],
     "cta": "Consultar um concorrente grátis", "lp": "/consultar-concorrente/"},
    {"slug": "habilitacao", "nome": "Habilitação e cofre de documentos", "icone": "cofre",
     "titulo": "Nunca mais seja inabilitado por um documento vencido",
     "descricao": "Cofre com certidões, balanços e atestados da empresa, com controle de validade e conferência automática contra as exigências de cada edital.",
     "pontos": [("Validade sob controle", "Alertas antes de cada certidão vencer, no painel e por e-mail."),
                ("Checklist por edital", "A análise cruza cada exigência de habilitação com o que está no cofre: atende, falta, vencido ou verificar."),
                ("Exigências setoriais", "ANVISA, ART/RRT, PNAE e outras exigências próprias do objeto identificadas à parte.")],
     "cta": "Organizar meu cofre", "lp": "/lp/analisar-edital/"},
    {"slug": "precos", "nome": "Inteligência de preços", "icone": "precos",
     "titulo": "Preço competitivo e exequível, com base em dados",
     "descricao": "Preços praticados no governo, tabelas de referência (SINAPI, CMED, CCT), BDI pela fórmula do TCU e alertas de inexequibilidade.",
     "pontos": [("Preços praticados", "Pesquisa por CATMAT/CATSER e referências oficiais carregadas pela equipe Kasiski."),
                ("BDI e tributos", "Formação de preço com BDI (fórmula do Acórdão TCU 2.622/2013) e tributos do regime da empresa."),
                ("Alerta de exequibilidade", "Aviso quando o preço fica abaixo dos limites que costumam levar à desclassificação.")],
     "cta": "Testar grátis", "lp": "/lp/software-licitacoes/"},
    {"slug": "propostas", "nome": "Propostas comerciais", "icone": "propostas",
     "titulo": "Proposta comercial pronta em minutos, no padrão do edital",
     "descricao": "Itens com formação de preço, minuta redigida pela IA a partir das regras do edital e exportação para Word.",
     "pontos": [("Regras do edital lidas pela IA", "Validade, prazo de entrega, garantia e declarações exigidas entram na minuta."),
                ("Planilha e texto juntos", "Formação de preço item a item e a proposta redigida no mesmo lugar."),
                ("Exportação para Word", "Documento pronto para revisar, assinar e enviar ao portal.")],
     "cta": "Testar grátis", "lp": "/lp/software-licitacoes/"},
    {"slug": "gestao-contratos", "nome": "Gestão de contratos", "icone": "contratos",
     "titulo": "Contrato ganho é contrato bem gerido",
     "descricao": "Envie o PDF do contrato: a IA extrai vigência, garantia, reajuste e rotinas; o Kasiski avisa prorrogações, reajustes e pagamentos atrasados.",
     "pontos": [("Prazos preventivos", "Prorrogação avisada com 120 e 60 dias de antecedência, renovação da garantia e data-base do reajuste."),
                ("Rotinas mensais", "Medição, faturamento e envio de documentos com lembrete diário por e-mail."),
                ("Pagamentos em atraso", "Controle de recebimentos e requerimento de pagamento gerado pela IA.")],
     "cta": "Testar grátis", "lp": "/lp/software-licitacoes/"},
]

# ---------------------------------------------------------------- landing pages de campanha (/lp/...)
LPS = [
    {"slug": "analisar-edital", "titulo": "Descubra os riscos do seu edital antes de decidir participar",
     "subtitulo": "Envie o PDF. O Kasiski identifica exigências, documentos, prazos e pontos de atenção — em minutos e de graça.",
     "descricao": "Análise gratuita de edital de licitação com IA: exigências de habilitação, cláusulas restritivas e pontos de atenção.",
     "ferramenta": "analisar_edital",
     "provas": ["Checklist de habilitação por categoria", "Cláusulas restritivas à luz da Lei 14.133/2021", "Nota de participação de 0 a 100"]},
    {"slug": "software-licitacoes", "titulo": "O software de licitações que decide com você",
     "subtitulo": "Radar no PNCP, análise de edital com IA, concorrentes, preços, propostas e contratos em um só lugar. Teste grátis por 7 dias, sem cartão.",
     "descricao": "Software de licitações com IA: radar de editais no PNCP, análise de edital, Go/No-Go, concorrentes, preços e gestão de contratos.",
     "ferramenta": "cadastro",
     "provas": ["Radar diário no PNCP com nota de aderência", "Análise de edital conferida por uma segunda IA", "Pipeline de oportunidades do edital ao contrato"]},
    {"slug": "radar", "titulo": "Receba as licitações da sua empresa todos os dias",
     "subtitulo": "O Radar do Kasiski procura no PNCP os editais que combinam com o seu CNPJ, e dá uma nota para cada um.",
     "descricao": "Buscar licitações no PNCP por palavra-chave, CNAE e UF, com nota de aderência — radar de editais do Kasiski.",
     "ferramenta": "cadastro",
     "provas": ["CNAEs e palavras-chave a partir do CNPJ", "Filtro por UF e faixa de valor", "Nota de aderência e motivo em cada edital"]},
    {"slug": "consultorias", "titulo": "Todos os seus clientes de licitação em um só lugar",
     "subtitulo": "Radar, editais, prazos e contratos separados por cliente, com relatórios na marca do seu escritório.",
     "descricao": "Kasiski para consultorias de licitação: gestão multiempresa de radar, editais, prazos, peças e contratos.",
     "ferramenta": "consultorias",
     "provas": ["Até 10 empresas no plano Consultor", "Relatórios com a marca do escritório", "Prazos de todos os clientes em uma agenda"]},
    {"slug": "concorrentes", "titulo": "Quem é o seu concorrente no mercado público?",
     "subtitulo": "Digite o CNPJ e veja situação, contratos públicos, órgãos contratantes e sanções — grátis.",
     "descricao": "Consulta gratuita de concorrente em licitações: contratos no PNCP, órgãos contratantes e sanções pelo CNPJ.",
     "ferramenta": "concorrente",
     "provas": ["Receita Federal e situação cadastral", "Contratos e atas no PNCP", "Sanções no TCU, CEIS e CNEP"]},
]

# ---------------------------------------------------------------- glossário (/glossario/<termo>)
# definição → exemplo → legislação → aplicação → ferramenta Kasiski relacionada
GLOSSARIO = [
    {"slug": "pncp", "termo": "PNCP — Portal Nacional de Contratações Públicas",
     "definicao": "Sítio eletrônico oficial, instituído pela Lei 14.133/2021, para a divulgação centralizada e obrigatória dos atos das contratações públicas: editais, avisos de contratação direta, atas de registro de preços, contratos e seus aditivos.",
     "exemplo": "Uma prefeitura publica o edital de um pregão no PNCP; o documento, os itens, os resultados e o contrato assinado ficam consultáveis pelo número de controle PNCP da contratação.",
     "legislacao": "Lei 14.133/2021, art. 174 (criação e conteúdo do PNCP) e art. 54 (publicidade do edital); art. 94 (divulgação do contrato como condição de eficácia).",
     "aplicacao": "Por reunir editais e resultados de todos os entes, o PNCP é a principal fonte para encontrar oportunidades, pesquisar concorrentes e estimar preços praticados.",
     "ferramenta": ("Radar de licitações", "/radar-licitacoes/")},
    {"slug": "pregao-eletronico", "termo": "Pregão eletrônico",
     "definicao": "Modalidade de licitação obrigatória para a aquisição de bens e serviços comuns, cujo critério de julgamento é o menor preço ou o maior desconto, com disputa por lances em sistema eletrônico.",
     "exemplo": "Compra de material de escritório ou contratação de serviço contínuo de limpeza: os licitantes enviam propostas, disputam lances na sessão pública e só o melhor classificado tem a habilitação analisada.",
     "legislacao": "Lei 14.133/2021, art. 6º, XLI (definição), art. 28, I, e art. 29 (cabimento); art. 17, §2º (forma eletrônica como regra).",
     "aplicacao": "No pregão, a fase de lances vem antes da habilitação: preço e documentação precisam estar prontos antes da sessão.",
     "ferramenta": ("Análise gratuita de edital", "/analisar-edital/")},
    {"slug": "go-no-go", "termo": "Go / No-Go",
     "definicao": "Decisão interna, tomada antes de investir na preparação, sobre participar (Go) ou não (No-Go) de uma licitação, com base em aderência, capacidade de atendimento, riscos, margem e concorrência.",
     "exemplo": "O edital exige atestado de 50% de uma área que a empresa não possui e tem multa diária sem teto: a equipe registra No-Go e o motivo; em outro, com fit alto e concorrência conhecida, registra Go e parte para a proposta.",
     "legislacao": "Não é instituto legal: é prática de gestão comercial. Os critérios, porém, dialogam com a Lei 14.133/2021 — exigências de habilitação (arts. 62 a 70) e riscos contratuais (arts. 103, 137 e 155).",
     "aplicacao": "Um processo Go/No-Go consistente evita desperdiçar horas em disputas com pouca chance e melhora a taxa de sucesso.",
     "ferramenta": ("Decisão Go / No-Go", "/go-no-go/")},
    {"slug": "atestado-capacidade-tecnica", "termo": "Atestado de capacidade técnica",
     "definicao": "Documento emitido por pessoa jurídica de direito público ou privado que comprova que a licitante (capacidade técnico-operacional) ou seu profissional (técnico-profissional) já executou objeto compatível com o licitado.",
     "exemplo": "Para um serviço de limpeza de 10 mil m², o edital pode exigir atestado de execução de área compatível — em regra, limitada a até 50% do quantitativo licitado nas parcelas de maior relevância.",
     "legislacao": "Lei 14.133/2021, art. 67, I e II (qualificação técnico-profissional e técnico-operacional), §1º (parcelas de maior relevância ou valor significativo) e §2º (limite de até 50% das parcelas).",
     "aplicacao": "Exigências acima do limite legal ou sem justificativa são motivo frequente de impugnação; atestados que não demonstram compatibilidade são motivo frequente de inabilitação.",
     "ferramenta": ("Habilitação e cofre de documentos", "/habilitacao/")},
    {"slug": "inexequibilidade", "termo": "Inexequibilidade",
     "definicao": "Situação em que o preço proposto é insuficiente para cobrir os custos da execução do contrato, o que pode levar à desclassificação da proposta se o licitante não demonstrar a viabilidade.",
     "exemplo": "Em obra orçada em R$ 1 milhão, proposta de R$ 700 mil fica abaixo de 75% do orçamento da Administração e é considerada inexequível pela regra legal.",
     "legislacao": "Lei 14.133/2021, art. 59, III e §§2º e 4º (obras e serviços de engenharia: abaixo de 75% do valor orçado); para bens e serviços em geral, a IN SEGES/ME 73/2022 trata valores muito inferiores ao orçado como indício, a ser confirmado em diligência.",
     "aplicacao": "Antes do lance final, compare o preço com o orçamento e com seus custos; se ficar abaixo, prepare planilha e documentos para a diligência de exequibilidade.",
     "ferramenta": ("Inteligência de preços", "/precos/")},
    {"slug": "impugnacao", "termo": "Impugnação ao edital",
     "definicao": "Instrumento pelo qual qualquer pessoa aponta irregularidade no edital e pede a sua correção antes da sessão pública.",
     "exemplo": "O edital exige índice de liquidez muito acima do usual sem justificativa; a empresa impugna demonstrando que a exigência restringe indevidamente a competição.",
     "legislacao": "Lei 14.133/2021, art. 164: prazo de até 3 dias úteis antes da data de abertura do certame, com resposta em até 3 dias úteis, limitada ao último dia útil anterior à abertura.",
     "aplicacao": "A impugnação bem fundamentada pode reabrir prazos e ampliar a competitividade; perder o prazo enfraquece a discussão posterior.",
     "ferramenta": ("Análise gratuita de edital", "/analisar-edital/")},
    {"slug": "recurso-administrativo", "termo": "Recurso administrativo",
     "definicao": "Meio pelo qual o licitante contesta, perante a própria Administração, atos como o julgamento das propostas, a habilitação ou inabilitação e a anulação ou revogação da licitação.",
     "exemplo": "O concorrente vencedor apresentou atestado incompatível; a empresa manifesta a intenção de recorrer na sessão e apresenta as razões no prazo.",
     "legislacao": "Lei 14.133/2021, art. 165: prazo de 3 dias úteis da intimação ou da lavratura da ata; intenção de recorrer manifestada imediatamente, sob pena de preclusão (§1º, I); contrarrazões no mesmo prazo (§4º); efeito suspensivo (art. 168).",
     "aplicacao": "O dossiê do concorrente e a análise da habilitação dele são a base de um recurso consistente.",
     "ferramenta": ("Inteligência de concorrentes", "/concorrentes/")},
    {"slug": "sicaf", "termo": "SICAF",
     "definicao": "Sistema de Cadastramento Unificado de Fornecedores do Governo Federal, em que o fornecedor registra dados e documentos de habilitação usados nas contratações federais.",
     "exemplo": "Com o SICAF em dia, a empresa comprova regularidade fiscal e trabalhista em um pregão federal sem reenviar as certidões a cada disputa.",
     "legislacao": "Lei 14.133/2021, art. 87 (registro cadastral unificado, disponível no PNCP); Instrução Normativa SEGES/MP 3/2018 (funcionamento do SICAF).",
     "aplicacao": "Manter o SICAF atualizado reduz o risco de inabilitação por documento vencido; estados e municípios costumam ter cadastros próprios.",
     "ferramenta": ("Habilitação e cofre de documentos", "/habilitacao/")},
    {"slug": "bdi", "termo": "BDI — Benefícios e Despesas Indiretas",
     "definicao": "Percentual aplicado sobre o custo direto para cobrir despesas indiretas (administração central, seguros, garantias, riscos, despesas financeiras), tributos e o lucro, formando o preço de venda.",
     "exemplo": "Custo direto de R$ 100 mil com BDI de 25% resulta em preço de R$ 125 mil; a composição do BDI deve ser detalhada na proposta de obras.",
     "legislacao": "Acórdão TCU 2.622/2013-Plenário (fórmula e faixas referenciais de BDI); Decreto 7.983/2013, art. 9º; Lei 14.133/2021, art. 23, §2º (orçamento de obras e serviços de engenharia).",
     "aplicacao": "BDI fora das faixas referenciais precisa de justificativa; errar no BDI é causa comum de proposta inexequível ou acima do orçado.",
     "ferramenta": ("Inteligência de preços", "/precos/")},
    {"slug": "sinapi", "termo": "SINAPI",
     "definicao": "Sistema Nacional de Pesquisa de Custos e Índices da Construção Civil, mantido pela Caixa e pelo IBGE, com custos de insumos e composições de serviços usados como referência em obras públicas.",
     "exemplo": "O orçamento de uma reforma usa as composições do SINAPI da UF da obra; o licitante confere se os custos unitários da sua proposta são compatíveis.",
     "legislacao": "Lei 14.133/2021, art. 23, §2º, I (custos unitários menores ou iguais à mediana do SINAPI em obras e serviços de engenharia); Decreto 7.983/2013.",
     "aplicacao": "Conhecer o SINAPI da UF ajuda a identificar sobrepreço no orçamento e a montar uma proposta exequível.",
     "ferramenta": ("Inteligência de preços", "/precos/")},
]
