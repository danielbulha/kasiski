"""Glossário de licitações e contratos públicos (/glossario/ e /glossario/<termo>/).

Cada termo: definição → exemplo → legislação → aplicação → ferramenta Kasiski, com categoria, sinônimos
(ajudam a busca e os links automáticos), termos relacionados e perguntas frequentes opcionais.
Os 10 termos originais continuam em conteudo.GLOSSARIO; aqui ficam os complementos e os termos novos.
Referências legais conferidas na Lei 14.133/2021; valores atualizados por decreto são citados como "valor original".
"""
import unicodedata

import conteudo as C

RADAR = ("Radar de licitações", "/radar-licitacoes/")
ANALISE = ("Análise gratuita de edital", "/analisar-edital/")
GNG = ("Decisão Go / No-Go", "/go-no-go/")
CONC = ("Inteligência de concorrentes", "/concorrentes/")
CONSULTA = ("Consulta gratuita de concorrente", "/consultar-concorrente/")
HAB = ("Habilitação e cofre de documentos", "/habilitacao/")
CHECK = ("Checklist de habilitação grátis", "/checklist-habilitacao/")
PRECOS = ("Inteligência de preços", "/precos/")
PROP = ("Propostas comerciais", "/propostas/")
CONTR = ("Gestão de contratos", "/gestao-contratos/")

CATEGORIAS = ["Modalidades e procedimentos", "Planejamento e edital", "Habilitação", "Propostas e preços",
              "Sessão, julgamento e recursos", "Contratos", "Sanções e controle", "Sistemas e tabelas", "Estratégia"]

# complementos dos termos que já existiam em conteudo.GLOSSARIO
EXTRAS = {
    "pncp": dict(curto="PNCP", cat="Sistemas e tabelas", sin=["Portal Nacional de Contratações Públicas"],
                 rel=["compras-gov-br", "lei-14133", "edital", "ata-de-registro-de-precos"],
                 perguntas=[("Todo órgão público é obrigado a publicar no PNCP?",
                             "Sim. A Lei 14.133/2021 exige a divulgação no PNCP dos editais, avisos de contratação direta, atas e contratos de todos os entes federativos; municípios de até 20 mil habitantes tiveram prazo de transição (art. 176).")]),
    "pregao-eletronico": dict(curto="pregão eletrônico", cat="Modalidades e procedimentos", sin=["pregão"],
                              rel=["modo-de-disputa", "concorrencia", "bens-e-servicos-comuns", "pregoeiro", "negociacao"],
                              perguntas=[("Qual a diferença entre pregão e concorrência?",
                                          "O pregão é para bens e serviços comuns, sempre por menor preço ou maior desconto. A concorrência atende bens e serviços especiais e obras e serviços de engenharia, e admite também técnica e preço, melhor técnica e maior retorno econômico.")]),
    "go-no-go": dict(curto="Go / No-Go", cat="Estratégia", sin=["go no go", "decisão de participar"],
                     rel=["edital", "matriz-de-riscos", "atestado-capacidade-tecnica", "taxa-de-sucesso"]),
    "atestado-capacidade-tecnica": dict(curto="atestado de capacidade técnica", cat="Habilitação", sin=["atestado técnico", "capacidade técnica"],
                                        rel=["habilitacao", "diligencia", "consorcio", "subcontratacao"],
                                        perguntas=[("O atestado precisa ser registrado no CREA ou em outro conselho?",
                                                    "Depende do objeto: em obras e serviços de engenharia, a capacidade técnico-profissional costuma ser comprovada por certidão de acervo técnico (CAT) do conselho; para a capacidade da empresa, a exigência de registro do atestado em conselho é tema com jurisprudência restritiva do TCU. Leia o edital e, se a exigência parecer excessiva, avalie impugnar.")]),
    "inexequibilidade": dict(curto="inexequibilidade", cat="Propostas e preços", sin=["preço inexequível", "proposta inexequível"],
                             rel=["diligencia", "valor-estimado", "planilha-de-custos", "bdi", "sobrepreco"]),
    "impugnacao": dict(curto="impugnação ao edital", cat="Sessão, julgamento e recursos", sin=["impugnação", "impugnar edital"],
                       rel=["pedido-de-esclarecimento", "edital", "representacao-tribunal-de-contas", "recurso-administrativo"],
                       perguntas=[("Qual o prazo para impugnar um edital pela Lei 14.133?",
                                   "Até 3 dias úteis antes da data de abertura do certame. A Administração deve responder em até 3 dias úteis, limitado ao último dia útil anterior à abertura (art. 164).")]),
    "recurso-administrativo": dict(curto="recurso administrativo", cat="Sessão, julgamento e recursos", sin=["recurso", "recurso em licitação"],
                                   rel=["intencao-de-recurso", "pedido-de-reconsideracao", "habilitacao", "adjudicacao-e-homologacao"],
                                   perguntas=[("Qual o prazo do recurso na Lei 14.133?",
                                               "3 dias úteis, contados da intimação ou da lavratura da ata. No pregão e nas licitações com fase recursal única, a intenção de recorrer deve ser manifestada imediatamente, sob pena de preclusão (art. 165).")]),
    "sicaf": dict(curto="SICAF", cat="Sistemas e tabelas", sin=["Sistema de Cadastramento Unificado de Fornecedores"],
                  rel=["registro-cadastral", "regularidade-fiscal", "compras-gov-br", "habilitacao"]),
    "bdi": dict(curto="BDI", cat="Propostas e preços", sin=["Benefícios e Despesas Indiretas", "LDI"],
                rel=["sinapi", "sicro", "planilha-de-custos", "inexequibilidade"],
                perguntas=[("Qual é o BDI referencial do TCU?",
                            "O Acórdão 2.622/2013-Plenário traz faixas de BDI por tipo de obra (quartis). Valores fora da faixa não são proibidos, mas precisam de justificativa na composição.")]),
    "sinapi": dict(curto="SINAPI", cat="Sistemas e tabelas", sin=["Sistema Nacional de Pesquisa de Custos e Índices da Construção Civil"],
                   rel=["sicro", "bdi", "orcamento-de-referencia", "valor-estimado"]),
}


def T(slug, termo, curto, cat, definicao, exemplo, legislacao, aplicacao, ferramenta, rel, sin=(), perguntas=()):
    return {"slug": slug, "termo": termo, "curto": curto, "cat": cat, "definicao": definicao, "exemplo": exemplo,
            "legislacao": legislacao, "aplicacao": aplicacao, "ferramenta": ferramenta, "rel": list(rel),
            "sin": list(sin), "perguntas": list(perguntas)}


NOVOS = [
    # ------------------------------------------------------------ modalidades e procedimentos
    T("lei-14133", "Lei 14.133/2021 — Nova Lei de Licitações e Contratos", "Lei 14.133", "Modalidades e procedimentos",
      "Lei geral de licitações e contratos administrativos da União, dos estados, do Distrito Federal e dos municípios. Substituiu a Lei 8.666/1993, a Lei do Pregão (10.520/2002) e o RDC (Lei 12.462/2011), que deixaram de reger novas contratações a partir de 30 de dezembro de 2023.",
      "Um edital publicado em 2026 por uma prefeitura segue a Lei 14.133: fases do art. 17, habilitação dos arts. 62 a 70, recursos do art. 165 e sanções do art. 156.",
      "Lei 14.133/2021; prazo de transição prorrogado pela Lei Complementar 198/2023 (art. 193, II, com a redação dada). Empresas estatais seguem a Lei 13.303/2016.",
      "Contratos assinados sob a lei antiga continuam regidos por ela até o fim; para novas disputas, os prazos, documentos e sanções são os da Lei 14.133.",
      ANALISE, ["pncp", "fases-da-licitacao", "lei-das-estatais", "pregao-eletronico"], sin=["Lei 14.133/2021", "Nova Lei de Licitações", "NLLC", "lei 14133"]),
    T("concorrencia", "Concorrência", "concorrência", "Modalidades e procedimentos",
      "Modalidade de licitação para contratar bens e serviços especiais e obras e serviços comuns e especiais de engenharia, com critério de julgamento por menor preço, melhor técnica ou conteúdo artístico, técnica e preço, maior retorno econômico ou maior desconto.",
      "A construção de uma escola é licitada por concorrência eletrônica com critério de menor preço; um projeto de arquitetura complexo pode ir a concorrência por técnica e preço.",
      "Lei 14.133/2021, art. 6º, XXXVIII (definição), art. 28, II, e art. 29 (mesmo rito procedimental do pregão).",
      "Na Lei 14.133, pregão e concorrência seguem o mesmo rito; o que muda é o objeto e os critérios de julgamento possíveis.",
      ANALISE, ["pregao-eletronico", "criterio-de-julgamento", "tecnica-e-preco", "regime-de-execucao"], sin=["concorrência eletrônica"]),
    T("concurso", "Concurso (modalidade de licitação)", "concurso", "Modalidades e procedimentos",
      "Modalidade de licitação para escolha de trabalho técnico, científico ou artístico, cujo critério de julgamento é a melhor técnica ou o melhor conteúdo artístico, com prêmio ou remuneração ao vencedor.",
      "Um município abre concurso para escolher o projeto arquitetônico de uma praça; o vencedor recebe o prêmio e cede os direitos patrimoniais do projeto.",
      "Lei 14.133/2021, art. 6º, XXXIX, e art. 30; cessão de direitos patrimoniais no art. 93.",
      "Não confundir com concurso público de pessoal: aqui se premia um trabalho, não se preenche um cargo.",
      RADAR, ["concorrencia", "criterio-de-julgamento", "leilao"]),
    T("leilao", "Leilão", "leilão", "Modalidades e procedimentos",
      "Modalidade de licitação para alienação de imóveis ou de bens móveis inservíveis ou legalmente apreendidos, vencida por quem oferecer o maior lance.",
      "Um órgão federal leiloa veículos antigos da frota; o edital traz a descrição, o valor mínimo, a forma de pagamento e as condições de retirada.",
      "Lei 14.133/2021, art. 6º, XL, e art. 31; alienação de bens nos arts. 76 e 77.",
      "É uma via de compra para a empresa: bens públicos podem ser arrematados com as condições do edital.",
      RADAR, ["concorrencia", "criterio-de-julgamento"]),
    T("dialogo-competitivo", "Diálogo competitivo", "diálogo competitivo", "Modalidades e procedimentos",
      "Modalidade de licitação em que a Administração dialoga com licitantes previamente selecionados para desenvolver alternativas capazes de atender às suas necessidades, e depois pede propostas finais com base na solução escolhida.",
      "Um estado precisa de uma solução tecnológica ainda não disponível de forma padronizada no mercado: seleciona empresas, conduz reuniões de diálogo e só então abre a fase competitiva.",
      "Lei 14.133/2021, art. 6º, XLII, e art. 32 (hipóteses de cabimento e rito).",
      "Exige preparo técnico e sigilo das soluções apresentadas; é incomum, mas relevante em inovação e infraestrutura.",
      RADAR, ["concorrencia", "procedimento-de-manifestacao-de-interesse", "estudo-tecnico-preliminar"]),
    T("contratacao-direta", "Contratação direta", "contratação direta", "Modalidades e procedimentos",
      "Contratação feita sem licitação, nas hipóteses de inexigibilidade ou de dispensa previstas em lei, com processo que ainda exige justificativa de preço, escolha do fornecedor e demais documentos.",
      "Uma autarquia contrata um curso de capacitação com instrutor de notória especialização por inexigibilidade, instruindo o processo com a justificativa de preço.",
      "Lei 14.133/2021, arts. 72 a 75; art. 72 (documentos do processo); art. 73 (responsabilidade por contratação direta indevida).",
      "Contratações diretas também são publicadas no PNCP e podem ser acompanhadas: são sinal de demanda e de preços praticados.",
      RADAR, ["dispensa-de-licitacao", "inexigibilidade", "dispensa-eletronica", "pncp"], sin=["sem licitação"]),
    T("dispensa-de-licitacao", "Dispensa de licitação", "dispensa de licitação", "Modalidades e procedimentos",
      "Hipótese em que a competição seria possível, mas a lei autoriza contratar sem licitação — por baixo valor, emergência, licitação deserta ou fracassada, entre outras situações listadas em lei.",
      "Um órgão contrata a manutenção de ar-condicionado abaixo do limite de valor por dispensa, divulgando antes um aviso para receber propostas de outros interessados.",
      "Lei 14.133/2021, art. 75. Valores originais: R$ 100 mil para obras, serviços de engenharia e manutenção de veículos (inciso I) e R$ 50 mil para demais compras e serviços (inciso II), atualizados anualmente por decreto (art. 182). Emergência: inciso VIII, com contrato de até 1 ano.",
      "Os limites são somados por objeto de mesma natureza no exercício (art. 75, §1º). Confira sempre o decreto de atualização vigente.",
      RADAR, ["dispensa-eletronica", "contratacao-direta", "inexigibilidade", "licitacao-deserta-e-fracassada"], sin=["dispensa", "compra direta"],
      perguntas=[("Empresa pode participar de dispensa de licitação?",
                  "Sim. Nas dispensas por valor, o aviso costuma ser divulgado por pelo menos 3 dias úteis para receber propostas (art. 75, §3º); na dispensa eletrônica federal, há disputa de lances pelo Compras.gov.br.")]),
    T("dispensa-eletronica", "Dispensa eletrônica", "dispensa eletrônica", "Modalidades e procedimentos",
      "Procedimento eletrônico para contratações por dispensa de licitação, em que o órgão divulga o aviso e os fornecedores enviam propostas e lances em sistema, de forma parecida com um pregão simplificado.",
      "Uma universidade federal divulga no Compras.gov.br a compra de reagentes por dispensa; os fornecedores cadastrados disputam lances por algumas horas e o melhor preço é chamado a enviar documentos.",
      "Lei 14.133/2021, art. 75, §3º (divulgação prévia por no mínimo 3 dias úteis); Instrução Normativa SEGES/ME 67/2021 (dispensa eletrônica no âmbito federal).",
      "Volume alto e prazos curtos: quem monitora avisos diariamente e tem documentação pronta sai na frente.",
      RADAR, ["dispensa-de-licitacao", "compras-gov-br", "sicaf"]),
    T("inexigibilidade", "Inexigibilidade de licitação", "inexigibilidade", "Modalidades e procedimentos",
      "Hipótese de contratação direta em que a competição é inviável, como fornecedor exclusivo, artista consagrado, serviço técnico especializado de natureza predominantemente intelectual com notória especialização, credenciamento e aquisição de imóvel com características únicas.",
      "Um município contrata show de artista consagrado pela crítica ou pelo público por meio do empresário exclusivo, com justificativa do preço pelos valores cobrados em outros eventos.",
      "Lei 14.133/2021, art. 74 (hipóteses), §1º (exclusividade), §3º (notória especialização); art. 72 (instrução do processo).",
      "Para consultorias e escritórios, a notória especialização abre portas, mas precisa ser demonstrada com trabalhos anteriores, publicações e equipe.",
      RADAR, ["contratacao-direta", "dispensa-de-licitacao", "credenciamento"], sin=["inexigível"]),
    T("credenciamento", "Credenciamento", "credenciamento", "Modalidades e procedimentos",
      "Procedimento auxiliar em que a Administração convoca interessados para, cumpridos os requisitos, se credenciarem e prestarem serviços ou fornecerem bens de forma paralela e não excludente, a preços definidos pelo órgão ou em mercados fluidos.",
      "Um estado credencia clínicas para exames de saúde ocupacional a preço tabelado; qualquer clínica que atenda aos requisitos pode aderir, e a demanda é distribuída por critério objetivo.",
      "Lei 14.133/2021, art. 78, I, e art. 79 (hipóteses e regras); a contratação resultante é por inexigibilidade (art. 74, IV).",
      "Não há disputa de preço: a vantagem está em cumprir os requisitos e manter a documentação válida durante o prazo do edital.",
      RADAR, ["inexigibilidade", "pre-qualificacao", "procedimentos-auxiliares"]),
    T("procedimentos-auxiliares", "Procedimentos auxiliares", "procedimentos auxiliares", "Modalidades e procedimentos",
      "Instrumentos previstos na Lei 14.133 para apoiar licitações e contratações: credenciamento, pré-qualificação, procedimento de manifestação de interesse, sistema de registro de preços e registro cadastral.",
      "Antes de licitar uma solução complexa, o órgão faz um PMI; depois pré-qualifica licitantes e, por fim, registra preços para compras futuras.",
      "Lei 14.133/2021, art. 78 (lista) e arts. 79 a 88 (regras de cada procedimento).",
      "Cada procedimento abre uma porta diferente para o fornecedor: acompanhar só pregões deixa oportunidades de fora.",
      RADAR, ["credenciamento", "pre-qualificacao", "procedimento-de-manifestacao-de-interesse", "sistema-de-registro-de-precos", "registro-cadastral"]),
    T("pre-qualificacao", "Pré-qualificação", "pré-qualificação", "Modalidades e procedimentos",
      "Procedimento técnico-administrativo para selecionar previamente licitantes que reúnam condições de habilitação ou bens que atendam às exigências técnicas ou de qualidade, para licitações futuras.",
      "Um tribunal pré-qualifica marcas de toner que atendem ao padrão de qualidade; nas licitações seguintes, só os produtos pré-qualificados podem ser ofertados.",
      "Lei 14.133/2021, art. 78, II, e art. 80 (validade de até 1 ano e possibilidade de restringir licitação aos pré-qualificados, §10).",
      "Estar pré-qualificado reduz concorrência e trabalho em cada disputa; perder a janela pode excluir a empresa por um ano.",
      RADAR, ["procedimentos-auxiliares", "amostra-e-prova-de-conceito", "habilitacao"]),
    T("procedimento-de-manifestacao-de-interesse", "PMI — Procedimento de Manifestação de Interesse", "PMI", "Modalidades e procedimentos",
      "Procedimento pelo qual a Administração convida a iniciativa privada a apresentar estudos, investigações, levantamentos e projetos de soluções inovadoras que contribuam com questões de relevância pública.",
      "Um município publica PMI para receber estudos de modelagem de iluminação pública; o autor do estudo aproveitado é ressarcido pelo vencedor da licitação posterior.",
      "Lei 14.133/2021, art. 78, III, e art. 81 (o estudo não gera direito de preferência nem obriga a Administração a licitar).",
      "Participar de PMIs é forma de influenciar a modelagem de futuras licitações e de conhecer a demanda antes do edital.",
      RADAR, ["procedimentos-auxiliares", "dialogo-competitivo", "estudo-tecnico-preliminar"], sin=["manifestação de interesse"]),
    T("sistema-de-registro-de-precos", "Sistema de Registro de Preços (SRP)", "registro de preços", "Modalidades e procedimentos",
      "Conjunto de procedimentos para registrar formalmente preços de bens e serviços em ata, para contratações futuras, sem obrigar a Administração a comprar as quantidades estimadas.",
      "Uma secretaria de saúde registra preços de 300 medicamentos por um ano e emite pedidos conforme o consumo; o fornecedor fica obrigado a entregar nos preços registrados.",
      "Lei 14.133/2021, art. 6º, XLV, e arts. 82 a 86; Decreto 11.462/2023 (regulamento federal).",
      "No SRP a quantidade é estimativa, não garantia: dimensione estoque e capacidade de entrega para o pior e o melhor cenário.",
      RADAR, ["ata-de-registro-de-precos", "adesao-a-ata", "intencao-de-registro-de-precos", "orgao-gerenciador"], sin=["SRP", "registro de preço"]),
    T("ata-de-registro-de-precos", "Ata de registro de preços", "ata de registro de preços", "Modalidades e procedimentos",
      "Documento vinculativo e obrigacional, com característica de compromisso para futura contratação, em que se registram o objeto, os preços, os fornecedores, os órgãos participantes e as condições das contratações.",
      "Após o pregão, a empresa vencedora assina a ata com vigência de 1 ano; a cada necessidade, o órgão emite um contrato ou nota de empenho baseado nela.",
      "Lei 14.133/2021, art. 6º, XLVI; art. 84 (vigência de 1 ano, prorrogável por igual período se o preço continuar vantajoso).",
      "A ata não garante compra, mas obriga o fornecedor; acompanhe o consumo e o equilíbrio do preço registrado ao longo da vigência.",
      CONTR, ["sistema-de-registro-de-precos", "adesao-a-ata", "orgao-gerenciador", "reajuste"], sin=["ARP", "ata de registro de preço"]),
    T("adesao-a-ata", "Adesão à ata de registro de preços (carona)", "adesão à ata", "Modalidades e procedimentos",
      "Utilização de uma ata de registro de preços por órgão que não participou da licitação, mediante justificativa de vantagem, consulta ao órgão gerenciador e aceite do fornecedor.",
      "Uma prefeitura adere à ata de um consórcio intermunicipal para comprar ambulâncias, evitando uma nova licitação.",
      "Lei 14.133/2021, art. 86, §§2º a 5º: cada órgão não participante pode adquirir até 50% dos quantitativos registrados, e o total das adesões não pode passar do dobro do quantitativo de cada item.",
      "Para o fornecedor, a ata vira ativo comercial: órgãos que precisam do mesmo item podem aderir, e o fornecedor pode aceitar ou não.",
      RADAR, ["ata-de-registro-de-precos", "orgao-gerenciador", "sistema-de-registro-de-precos"], sin=["carona", "adesão a ata"]),
    T("intencao-de-registro-de-precos", "IRP — Intenção de Registro de Preços", "IRP", "Modalidades e procedimentos",
      "Procedimento público, na fase preparatória do registro de preços, em que o órgão gerenciador divulga a futura licitação para que outros órgãos informem suas demandas e passem a ser participantes.",
      "Antes de licitar mobiliário escolar, uma secretaria estadual abre IRP; dez municípios incluem quantidades e a licitação sai com escala maior.",
      "Lei 14.133/2021, art. 86, caput e §1º; Decreto 11.462/2023 (regras federais da IRP).",
      "Acompanhar IRPs antecipa a demanda: você sabe o que será licitado e em que volume antes do edital.",
      RADAR, ["sistema-de-registro-de-precos", "orgao-gerenciador", "plano-de-contratacoes-anual"]),
    T("orgao-gerenciador", "Órgão gerenciador e órgão participante", "órgão gerenciador", "Modalidades e procedimentos",
      "No registro de preços, o órgão gerenciador conduz a licitação e gerencia a ata; os órgãos participantes integram a ata desde a fase preparatória; os não participantes só podem aderir depois (carona).",
      "Um ministério é gerenciador da ata de notebooks; três autarquias vinculadas são participantes e um instituto federal, não participante, pede adesão.",
      "Lei 14.133/2021, art. 6º, XLVII a XLIX; art. 86.",
      "Saber quem é gerenciador e quem participa ajuda a mapear o potencial real de uma ata.",
      RADAR, ["sistema-de-registro-de-precos", "adesao-a-ata", "intencao-de-registro-de-precos"], sin=["órgão participante", "órgão não participante"]),
    T("registro-cadastral", "Registro cadastral", "registro cadastral", "Modalidades e procedimentos",
      "Cadastro unificado de licitantes, público e permanentemente aberto, com documentos de habilitação e avaliação de desempenho contratual, que os órgãos usam em suas contratações.",
      "Com o cadastro atualizado, a empresa participa de licitações restritas a cadastrados e evita reapresentar documentos a cada certame.",
      "Lei 14.133/2021, arts. 87 e 88 (registro unificado no PNCP, atualização anual e anotação de desempenho).",
      "A avaliação de desempenho registrada pode virar critério de desempate (art. 60, II): cumprir bem os contratos passa a valer ponto.",
      HAB, ["sicaf", "habilitacao", "criterios-de-desempate"], sin=["cadastro de fornecedores"]),
]

NOVOS += [
    # ------------------------------------------------------------ planejamento e edital
    T("plano-de-contratacoes-anual", "PCA — Plano de Contratações Anual", "PCA", "Planejamento e edital",
      "Documento em que cada órgão consolida as contratações que pretende realizar no exercício seguinte, publicado em sítio oficial e usado para orientar o planejamento orçamentário e as licitações.",
      "O PCA de uma universidade lista compra de equipamentos de laboratório no 2º trimestre; fornecedores que acompanham o plano se preparam antes do edital.",
      "Lei 14.133/2021, art. 12, VII, e §1º (publicação no sítio oficial); Decreto 10.947/2022 (PCA no âmbito federal).",
      "O PCA é o radar de longo prazo: mostra demanda futura, valores estimados e datas previstas.",
      RADAR, ["estudo-tecnico-preliminar", "intencao-de-registro-de-precos", "fase-preparatoria"], sin=["plano anual de contratações"]),
    T("fase-preparatoria", "Fase preparatória da licitação", "fase preparatória", "Planejamento e edital",
      "Etapa interna do processo em que o órgão define a necessidade, elabora estudo técnico preliminar, termo de referência ou projeto, estima o valor, analisa riscos e redige o edital e a minuta do contrato.",
      "Antes do pregão de vigilância, o órgão faz o ETP, a pesquisa de preços, o mapa de riscos e o parecer jurídico; só então publica o edital.",
      "Lei 14.133/2021, art. 18 (conteúdo da fase preparatória) e art. 53 (controle prévio de legalidade pelo órgão de assessoramento jurídico).",
      "Os documentos da fase preparatória (ETP, TR, pesquisa de preços) costumam ser anexos do processo e revelam o que o órgão realmente quer.",
      ANALISE, ["estudo-tecnico-preliminar", "termo-de-referencia", "pesquisa-de-precos", "matriz-de-riscos"], sin=["fase interna"]),
    T("estudo-tecnico-preliminar", "ETP — Estudo Técnico Preliminar", "ETP", "Planejamento e edital",
      "Documento da fase preparatória que caracteriza o interesse público, analisa as soluções de mercado e demonstra a viabilidade técnica e econômica da contratação, servindo de base para o termo de referência ou o projeto.",
      "O ETP de uma contratação de software compara licenças, desenvolvimento próprio e SaaS, estima custos e conclui pela contratação de serviço em nuvem.",
      "Lei 14.133/2021, art. 6º, XX, e art. 18, §1º (elementos) e §2º (elementos obrigatórios); IN SEGES/ME 58/2022 (ETP digital na esfera federal).",
      "Ler o ETP ajuda a entender por que o edital pede o que pede e a fundamentar impugnações e propostas.",
      ANALISE, ["termo-de-referencia", "fase-preparatoria", "matriz-de-riscos"], sin=["estudo técnico preliminar"]),
    T("termo-de-referencia", "Termo de referência", "termo de referência", "Planejamento e edital",
      "Documento que define o objeto a ser contratado para bens e serviços, com especificações, quantidades, prazos, modelo de execução e de gestão do contrato, critérios de medição e de pagamento e forma de seleção do fornecedor.",
      "O TR de serviço de limpeza traz as áreas, a produtividade por m², o uniforme, os materiais, os níveis mínimos de serviço e as glosas por descumprimento.",
      "Lei 14.133/2021, art. 6º, XXIII (conteúdo mínimo) e art. 40, §1º (compras).",
      "O TR é onde estão as obrigações que viram custo: produtividade, SLA, prazos de entrega e penalidades por nível de serviço.",
      ANALISE, ["estudo-tecnico-preliminar", "projeto-basico", "edital", "acordo-de-nivel-de-servico"], sin=["TR"]),
    T("projeto-basico", "Projeto básico e projeto executivo", "projeto básico", "Planejamento e edital",
      "O projeto básico reúne os elementos necessários para caracterizar a obra ou serviço de engenharia, com nível de precisão suficiente para estimar custos e prazos; o projeto executivo detalha a execução completa conforme as normas técnicas.",
      "Uma reforma é licitada com projeto básico, planilha orçamentária e cronograma; o projeto executivo pode ficar a cargo do contratado se o edital permitir.",
      "Lei 14.133/2021, art. 6º, XXV (projeto básico) e XXVI (projeto executivo); art. 46, §§1º e 2º (projetos nas contratações integrada e semi-integrada).",
      "Projeto básico deficiente é risco de aditivos e de reequilíbrio: avalie antes de dar o lance.",
      ANALISE, ["termo-de-referencia", "regime-de-execucao", "anteprojeto", "sinapi"], sin=["projeto executivo"]),
    T("anteprojeto", "Anteprojeto", "anteprojeto", "Planejamento e edital",
      "Peça técnica com os parâmetros mínimos da obra ou serviço, usada na contratação integrada, em que o contratado elabora o projeto básico e o executivo.",
      "Um hospital é licitado por contratação integrada a partir de anteprojeto com programa de necessidades, padrão de acabamento e prazos; o vencedor projeta e constrói.",
      "Lei 14.133/2021, art. 6º, XXIV, e art. 46, §2º.",
      "Na contratação integrada, o risco de projeto passa para a empresa: a matriz de riscos precisa refletir isso no preço.",
      ANALISE, ["regime-de-execucao", "projeto-basico", "matriz-de-riscos"]),
    T("matriz-de-riscos", "Matriz de riscos", "matriz de riscos", "Planejamento e edital",
      "Cláusula contratual que define os riscos e as responsabilidades entre as partes e caracteriza o equilíbrio econômico-financeiro inicial do contrato, com os eventos supervenientes que podem afetá-lo.",
      "Em uma obra, a matriz atribui ao contratado o risco de variação de produtividade e à Administração o risco de desapropriação atrasada.",
      "Lei 14.133/2021, art. 6º, XXVII; art. 22 (obrigatória em obras e serviços de grande vulto e nas contratações integrada e semi-integrada); art. 103.",
      "Risco alocado ao contratado não gera reequilíbrio depois: ele precisa estar no preço desde a proposta.",
      GNG, ["reequilibrio-economico-financeiro", "anteprojeto", "go-no-go"]),
    T("edital", "Edital de licitação", "edital", "Planejamento e edital",
      "Instrumento convocatório que torna pública a licitação e fixa o objeto, as regras de participação, o julgamento, a habilitação, os recursos, as penalidades, a fiscalização, a gestão do contrato, a entrega e o pagamento.",
      "O edital de um pregão traz, além do texto principal, anexos como termo de referência, modelo de proposta, minuta de contrato e declarações.",
      "Lei 14.133/2021, art. 25 (conteúdo), art. 54 (publicidade no PNCP) e art. 55 (prazos mínimos entre a divulgação e a apresentação de propostas).",
      "Ler o edital inteiro, com os anexos, antes de decidir é o que separa uma participação lucrativa de uma multa.",
      ANALISE, ["termo-de-referencia", "impugnacao", "pedido-de-esclarecimento", "go-no-go"], sin=["edital de licitação", "instrumento convocatório"],
      perguntas=[("Qual o prazo mínimo entre a publicação do edital e a sessão?",
                  "Depende do objeto e do critério. Para aquisição de bens por menor preço ou maior desconto, 8 dias úteis; para serviços comuns e obras e serviços comuns de engenharia pelo mesmo critério, 10 dias úteis (art. 55).")]),
    T("pedido-de-esclarecimento", "Pedido de esclarecimento", "pedido de esclarecimento", "Planejamento e edital",
      "Solicitação feita à Administração para esclarecer dúvida sobre o edital, sem pedir a sua alteração; a resposta costuma vincular todos os licitantes.",
      "O TR não diz se o preço deve incluir frete para cada unidade; a empresa pede esclarecimento e a resposta passa a valer para todos.",
      "Lei 14.133/2021, art. 164 (mesmo prazo da impugnação: até 3 dias úteis antes da abertura) e parágrafo único (resposta em sítio eletrônico oficial).",
      "Use o esclarecimento para eliminar ambiguidades que afetam preço; quando a regra é ilegal, o caminho é a impugnação.",
      ANALISE, ["impugnacao", "edital", "termo-de-referencia"], sin=["esclarecimento"]),
    T("valor-estimado", "Valor estimado da contratação", "valor estimado", "Planejamento e edital",
      "Valor que a Administração calcula na fase preparatória, a partir de pesquisa de preços, para orientar o orçamento, a escolha da modalidade e o julgamento de propostas.",
      "Um pregão de papel A4 tem valor estimado calculado pela mediana de preços do Painel de Preços e de três cotações de fornecedores.",
      "Lei 14.133/2021, art. 23 (parâmetros), §1º (bens e serviços em geral) e §2º (obras e serviços de engenharia); art. 24 (orçamento sigiloso).",
      "Comparar o valor estimado com seu custo real é a primeira triagem de margem de um edital.",
      PRECOS, ["pesquisa-de-precos", "orcamento-sigiloso", "sobrepreco", "inexequibilidade"], sin=["preço estimado", "valor de referência", "preço de referência"]),
    T("orcamento-sigiloso", "Orçamento sigiloso", "orçamento sigiloso", "Planejamento e edital",
      "Possibilidade de a Administração manter em sigilo o valor estimado da contratação até o fim do julgamento, desde que justificado, divulgando apenas as quantidades e as demais informações necessárias às propostas.",
      "Em um pregão com orçamento sigiloso, os licitantes disputam sem conhecer o teto; o valor só é divulgado após o julgamento.",
      "Lei 14.133/2021, art. 24 (sigilo não prevalece para órgãos de controle; nos critérios de maior desconto, o preço de referência consta do edital).",
      "Sem teto conhecido, o histórico de preços praticados e o preço dos concorrentes viram a principal referência.",
      PRECOS, ["valor-estimado", "pesquisa-de-precos", "painel-de-precos"]),
    T("pesquisa-de-precos", "Pesquisa de preços", "pesquisa de preços", "Planejamento e edital",
      "Procedimento usado para estimar o valor da contratação a partir de parâmetros definidos em lei, como contratações públicas similares, bancos oficiais de preços, mídia especializada, cotações diretas e notas fiscais.",
      "O órgão consulta o Painel de Preços, três contratações similares e duas cotações de fornecedores, descarta valores inexequíveis e excessivos e adota a mediana.",
      "Lei 14.133/2021, art. 23, §1º (parâmetros para bens e serviços); Instrução Normativa SEGES/ME 65/2021 (pesquisa de preços na esfera federal).",
      "Empresas que respondem cotações influenciam o valor estimado; responder com preço realista evita tetos baixos depois.",
      PRECOS, ["painel-de-precos", "valor-estimado", "catmat-catser", "cotacao"]),
    T("cotacao", "Cotação (pedido de orçamento)", "cotação", "Planejamento e edital",
      "Solicitação formal de preço feita pelo órgão diretamente a fornecedores, usada como um dos parâmetros da pesquisa de preços.",
      "O setor de compras envia e-mail a cinco fornecedores pedindo preço de cadeiras com especificação, prazo de validade e CNPJ; três respondem.",
      "Lei 14.133/2021, art. 23, §1º, IV (pesquisa direta com no mínimo 3 fornecedores, com justificativa da escolha, e sem cotações com mais de 6 meses).",
      "Cotação não é proposta, mas é relacionamento: órgãos lembram de quem responde bem e rápido.",
      PRECOS, ["pesquisa-de-precos", "valor-estimado"], sin=["pedido de cotação", "orçamento"]),
    T("bens-e-servicos-comuns", "Bens e serviços comuns", "bens e serviços comuns", "Planejamento e edital",
      "Bens e serviços cujos padrões de desempenho e qualidade podem ser objetivamente definidos pelo edital, por meio de especificações usuais de mercado. São licitados por pregão.",
      "Material de expediente, combustível, limpeza e vigilância são exemplos típicos de objetos comuns.",
      "Lei 14.133/2021, art. 6º, XIII (comuns) e XIV (especiais); art. 29 (pregão para comuns).",
      "Se o edital trata como comum algo que exige solução técnica complexa, há espaço para esclarecimento ou impugnação.",
      ANALISE, ["pregao-eletronico", "concorrencia", "servico-continuo"], sin=["bem comum", "serviço comum", "bens e serviços especiais"]),
    T("servico-continuo", "Serviço contínuo", "serviço contínuo", "Planejamento e edital",
      "Serviço contratado para a manutenção da atividade administrativa, decorrente de necessidades permanentes ou prolongadas, como limpeza, vigilância, manutenção predial e suporte de TI.",
      "Um contrato de manutenção de elevadores é serviço contínuo: pode ter vigência de até 5 anos e ser prorrogado até 10.",
      "Lei 14.133/2021, art. 6º, XV; arts. 106 e 107 (vigência de até 5 anos e prorrogação até 10 anos).",
      "Receita recorrente: contratos contínuos bem executados rendem anos de faturamento e atestados.",
      CONTR, ["dedicacao-exclusiva-de-mao-de-obra", "vigencia-e-prorrogacao", "repactuacao"], sin=["serviços contínuos"]),
    T("dedicacao-exclusiva-de-mao-de-obra", "Dedicação exclusiva de mão de obra", "dedicação exclusiva de mão de obra", "Planejamento e edital",
      "Regime de serviço em que os empregados do contratado ficam à disposição nas dependências do órgão, sem compartilhamento com outros contratos, e sob fiscalização do cumprimento das obrigações trabalhistas.",
      "Recepção, vigilância e limpeza com postos fixos são contratações com dedicação exclusiva; a proposta é feita em planilha de custos por posto.",
      "Lei 14.133/2021, art. 6º, XVI; art. 121, §§2º e 3º (responsabilidade da Administração e garantias como conta vinculada); art. 135 (repactuação).",
      "Planilha, convenção coletiva e conta vinculada definem a margem: erro de encargo vira prejuízo por 5 anos.",
      PRECOS, ["planilha-de-custos", "convencao-coletiva", "conta-vinculada", "repactuacao"], sin=["terceirização", "mão de obra dedicada"]),
    T("regime-de-execucao", "Regime de execução de obras e serviços de engenharia", "regime de execução", "Planejamento e edital",
      "Forma de contratação e de pagamento de obras e serviços de engenharia: empreitada por preço unitário, empreitada por preço global, empreitada integral, contratação por tarefa, contratação integrada, contratação semi-integrada e fornecimento e prestação de serviço associado.",
      "Na empreitada por preço unitário, paga-se pelas quantidades medidas; na global, pelo preço certo e total das etapas concluídas.",
      "Lei 14.133/2021, art. 6º, XXVIII a XXXIV (definições) e art. 46.",
      "O regime muda quem assume o risco de quantidade e de projeto: leia antes de montar a planilha.",
      ANALISE, ["projeto-basico", "anteprojeto", "matriz-de-riscos", "bdi"], sin=["empreitada por preço global", "empreitada por preço unitário", "contratação integrada", "contratação semi-integrada"]),
    T("obra-de-grande-vulto", "Obras, serviços e fornecimentos de grande vulto", "grande vulto", "Planejamento e edital",
      "Contratações cujo valor estimado supera o limite legal de grande vulto (valor original de R$ 200 milhões, atualizado anualmente por decreto) e que atraem exigências adicionais.",
      "Uma rodovia estimada acima do limite exige matriz de riscos, programa de integridade do vencedor em até 6 meses e pode prever seguro-garantia de até 30%.",
      "Lei 14.133/2021, art. 6º, XXII; art. 22, §3º (matriz de riscos); art. 25, §4º (programa de integridade); art. 99 (seguro-garantia com cláusula de retomada).",
      "Grandes contratos pedem estrutura de compliance, garantias e capacidade financeira desde a proposta.",
      GNG, ["programa-de-integridade", "matriz-de-riscos", "seguro-garantia"]),
]

NOVOS += [
    # ------------------------------------------------------------ habilitação
    T("habilitacao", "Habilitação", "habilitação", "Habilitação",
      "Fase da licitação em que se verifica se o licitante tem aptidão para executar o contrato, por documentos de habilitação jurídica, técnica, fiscal, social e trabalhista e econômico-financeira.",
      "No pregão, depois dos lances, só o primeiro colocado envia os documentos; se for inabilitado, o próximo é chamado.",
      "Lei 14.133/2021, arts. 62 a 70; art. 63 (declarações e documentos do vencedor); art. 17 (habilitação após o julgamento, como regra).",
      "Inabilitação é a principal causa de derrota evitável: documento vencido, atestado incompatível ou índice contábil abaixo do exigido.",
      CHECK, ["habilitacao-juridica", "atestado-capacidade-tecnica", "regularidade-fiscal", "qualificacao-economico-financeira", "diligencia"], sin=["documentos de habilitação", "inabilitação"],
      perguntas=[("Quais documentos de habilitação a Lei 14.133 pede?",
                  "Os documentos de habilitação jurídica (art. 66), técnica (art. 67), fiscal, social e trabalhista (art. 68) e econômico-financeira (art. 69), na medida em que o edital exigir. O edital pode dispensar parte deles em contratações de menor valor ou para entrega imediata (art. 70, III).")]),
    T("habilitacao-juridica", "Habilitação jurídica", "habilitação jurídica", "Habilitação",
      "Parte da habilitação que comprova a existência jurídica da pessoa e, quando cabível, a autorização para exercer a atividade a ser contratada.",
      "A empresa apresenta o contrato social consolidado e, para vigilância, a autorização de funcionamento da Polícia Federal.",
      "Lei 14.133/2021, art. 66.",
      "Mantenha contrato social consolidado e autorizações setoriais atualizadas; alterações recentes de sócios ou objeto geram questionamentos.",
      HAB, ["habilitacao", "regularidade-fiscal"]),
    T("regularidade-fiscal", "Regularidade fiscal, social e trabalhista", "regularidade fiscal", "Habilitação",
      "Conjunto de documentos que comprova inscrição no CNPJ e regularidade perante as Fazendas federal, estadual e municipal, o FGTS e a Justiça do Trabalho, além do cumprimento das regras sobre trabalho de menores.",
      "O pregoeiro consulta a CND federal, o CRF do FGTS e a CNDT; uma certidão vencida leva a diligência ou à inabilitação.",
      "Lei 14.133/2021, art. 68; Lei Complementar 123/2006, art. 43, §1º (prazo para ME e EPP regularizarem a situação fiscal).",
      "Automatize o controle de vencimento das certidões: é a falha de habilitação mais fácil de evitar.",
      HAB, ["cndt", "habilitacao", "me-epp", "sicaf"], sin=["certidões negativas", "CND", "certidão negativa de débitos", "CRF do FGTS"]),
    T("cndt", "CNDT — Certidão Negativa de Débitos Trabalhistas", "CNDT", "Habilitação",
      "Certidão emitida pela Justiça do Trabalho que comprova a inexistência de débitos inadimplidos perante ela, exigida para a regularidade trabalhista em licitações.",
      "A empresa com débito trabalhista garantido por penhora obtém certidão positiva com efeito de negativa, aceita para habilitação.",
      "Lei 14.133/2021, art. 68, V; CLT, art. 642-A.",
      "Validade de 180 dias; processos trabalhistas antigos podem gerar pendência inesperada.",
      HAB, ["regularidade-fiscal", "habilitacao"]),
    T("qualificacao-economico-financeira", "Qualificação econômico-financeira", "qualificação econômico-financeira", "Habilitação",
      "Parte da habilitação que demonstra a capacidade financeira do licitante para cumprir o contrato, por meio de balanço patrimonial, índices contábeis, certidão negativa de falência e, se exigido, capital social ou patrimônio líquido mínimo.",
      "O edital exige liquidez geral maior que 1 e patrimônio líquido mínimo de 10% do valor estimado; a empresa com índice menor pode comprovar pelo patrimônio líquido, se o edital permitir.",
      "Lei 14.133/2021, art. 69 (balanço dos 2 últimos exercícios, índices justificados no processo, capital ou patrimônio líquido de até 10% do valor estimado, §4º).",
      "Índices exigidos acima do usual sem justificativa são impugnáveis; balanço mal elaborado é causa frequente de inabilitação.",
      CHECK, ["balanco-patrimonial", "habilitacao", "garantia-contratual", "consorcio"], sin=["índices contábeis", "índice de liquidez", "patrimônio líquido mínimo", "capacidade financeira"]),
    T("balanco-patrimonial", "Balanço patrimonial", "balanço patrimonial", "Habilitação",
      "Demonstração contábil que mostra a posição financeira da empresa (ativos, passivos e patrimônio líquido) e serve de base para calcular os índices exigidos na qualificação econômico-financeira.",
      "O edital pede balanço dos dois últimos exercícios sociais; a empresa apresenta o SPED ECD com termo de abertura e encerramento.",
      "Lei 14.133/2021, art. 69, I (balanço dos 2 últimos exercícios sociais) e §6º (empresa constituída há menos de 2 anos apresenta os documentos do último exercício).",
      "Peça ao contador os índices calculados antes de participar: é mais fácil corrigir um erro de classificação do que reverter uma inabilitação.",
      HAB, ["qualificacao-economico-financeira", "habilitacao"], sin=["demonstrações contábeis", "SPED contábil"]),
    T("diligencia", "Diligência", "diligência", "Habilitação",
      "Providência adotada pelo agente de contratação ou pela comissão para esclarecer ou complementar informações da proposta ou da habilitação, inclusive para sanar erros ou falhas que não alterem a substância dos documentos.",
      "O atestado não informa a área executada; o pregoeiro diligencia e a empresa apresenta o contrato que deu origem ao atestado.",
      "Lei 14.133/2021, art. 64 (vedada a substituição ou apresentação de novos documentos, salvo para complementar informações ou atualizar documentos vencidos) e §1º (saneamento); Acórdão TCU 1.211/2021-Plenário (documento que comprova condição preexistente).",
      "Responder rápido e com prova documental a uma diligência salva a classificação; ignorar o prazo leva à desclassificação.",
      HAB, ["habilitacao", "inexequibilidade", "atestado-capacidade-tecnica"], sin=["saneamento de falhas", "diligência em licitação"]),
    T("amostra-e-prova-de-conceito", "Amostra e prova de conceito", "amostra", "Habilitação",
      "Exigência de que o licitante provisoriamente vencedor apresente amostra do produto, faça demonstração ou prova de conceito para comprovar que o objeto ofertado atende às especificações.",
      "Em um pregão de software, o primeiro colocado tem 5 dias para demonstrar as funcionalidades obrigatórias em ambiente de teste, conforme roteiro do edital.",
      "Lei 14.133/2021, art. 17, §3º (exigência do provisoriamente vencedor) e art. 41, II (amostra ou prova de conceito na aquisição de bens).",
      "Prepare a amostra ou o ambiente antes da sessão; os prazos após a convocação são curtos.",
      ANALISE, ["pre-qualificacao", "habilitacao", "termo-de-referencia"], sin=["prova de conceito", "PoC"]),
    T("vistoria-tecnica", "Vistoria técnica", "vistoria técnica", "Habilitação",
      "Visita ao local de execução para conhecimento das condições do objeto. Quando o edital a prevê, deve admitir sua substituição por declaração formal do responsável técnico de que conhece as condições locais.",
      "Para uma reforma, o edital permite vistoria agendada ou declaração de pleno conhecimento das condições do prédio.",
      "Lei 14.133/2021, art. 63, §§2º a 4º.",
      "Exigir vistoria obrigatória sem alternativa de declaração é motivo de impugnação.",
      ANALISE, ["habilitacao", "impugnacao"], sin=["visita técnica"]),
    T("consorcio", "Consórcio de empresas", "consórcio", "Habilitação",
      "Reunião de empresas para participar de uma licitação e executar o contrato em conjunto, somando qualificações técnicas e econômicas, com responsabilidade solidária.",
      "Uma construtora e uma empresa de tecnologia formam consórcio para licitar um centro de monitoramento, somando atestados de obra e de sistemas.",
      "Lei 14.133/2021, art. 15 (admitido salvo vedação justificada; acréscimo de 10% a 30% sobre a exigência econômico-financeira, §1º, que não se aplica a consórcios formados só por ME e EPP, §2º).",
      "Consórcio amplia o alcance, mas exige compromisso de constituição, empresa líder e governança clara.",
      GNG, ["subcontratacao", "atestado-capacidade-tecnica", "qualificacao-economico-financeira"]),
    T("me-epp", "ME e EPP — tratamento diferenciado em licitações", "ME e EPP", "Habilitação",
      "Benefícios da Lei Complementar 123/2006 para microempresas e empresas de pequeno porte em licitações: regularização fiscal tardia, empate ficto, licitações exclusivas até R$ 80 mil por item e cota reservada de até 25% em bens divisíveis.",
      "Em um pregão, a EPP que ficou até 5% acima do primeiro colocado (empresa de maior porte) pode cobrir o lance e vencer o item.",
      "Lei Complementar 123/2006, arts. 42 a 49; Lei 14.133/2021, art. 4º (aplicação e limites: benefício afastado quando o valor estimado do item superar a receita bruta máxima de EPP, e para quem já celebrou contratos acima desse valor no ano).",
      "Enquadramento correto e declaração verdadeira são essenciais: declarar-se ME/EPP sem cumprir os requisitos gera sanção.",
      HAB, ["empate-ficto", "regularidade-fiscal", "criterios-de-desempate"], sin=["microempresa", "empresa de pequeno porte", "cota reservada", "licitação exclusiva"]),
    T("empate-ficto", "Empate ficto", "empate ficto", "Habilitação",
      "Preferência de contratação para ME e EPP: considera-se empate quando a proposta da pequena empresa é até 10% superior à melhor proposta de empresa de maior porte (até 5% no pregão), dando-lhe o direito de cobrir a oferta.",
      "Melhor lance de uma grande empresa: R$ 100 mil. A ME com R$ 104 mil é convocada no pregão e oferece R$ 99,9 mil, vencendo o item.",
      "Lei Complementar 123/2006, arts. 44 e 45; Lei 14.133/2021, art. 4º.",
      "Se você é ME/EPP, fique atento à convocação: o prazo para cobrir o lance no pregão é curto (em regra, 5 minutos).",
      CONC, ["me-epp", "criterios-de-desempate", "modo-de-disputa"]),
    T("subcontratacao", "Subcontratação", "subcontratação", "Habilitação",
      "Transferência a terceiro de parte da execução do contrato, dentro do limite autorizado pela Administração, sem prejuízo da responsabilidade do contratado.",
      "Em um contrato de manutenção predial, o edital autoriza subcontratar até 30% dos serviços de elevadores, desde que o subcontratado comprove capacidade técnica.",
      "Lei 14.133/2021, art. 122.",
      "Se o edital não autoriza, subcontratar pode levar a sanção e rescisão; se autoriza, pode ampliar o alcance da empresa.",
      CONTR, ["consorcio", "atestado-capacidade-tecnica", "extincao-do-contrato"]),
]

NOVOS += [
    # ------------------------------------------------------------ propostas e preços
    T("proposta-comercial", "Proposta comercial em licitação", "proposta comercial", "Propostas e preços",
      "Documento em que o licitante oferta o objeto com preço, marca e modelo quando exigidos, prazos e demais condições do edital; vincula a empresa pelo prazo de validade indicado.",
      "Após o pregão, o vencedor envia a proposta ajustada ao lance final, com preços unitários, marca, prazo de entrega e validade de 60 dias.",
      "Lei 14.133/2021, art. 59 (hipóteses de desclassificação: vícios insanáveis, desconformidade com o edital, preço inexequível ou acima do orçamento) e art. 63.",
      "Erros de preenchimento que não alteram a substância podem ser corrigidos em diligência; omitir item obrigatório geralmente não.",
      PROP, ["inexequibilidade", "negociacao", "valor-estimado", "desclassificacao"], sin=["proposta de preços", "proposta"]),
    T("desclassificacao", "Desclassificação da proposta", "desclassificação", "Propostas e preços",
      "Exclusão da proposta do certame por vícios insanáveis, desconformidade com as exigências do edital, preço inexequível ou acima do orçamento estimado, ou falta de demonstração de exequibilidade quando exigida.",
      "O produto ofertado não atende à especificação técnica do termo de referência; a proposta é desclassificada e o próximo colocado é chamado.",
      "Lei 14.133/2021, art. 59, I a V.",
      "Desclassificação pode ser discutida em recurso; guarde as fichas técnicas que comprovam o atendimento às especificações.",
      PROP, ["proposta-comercial", "inexequibilidade", "recurso-administrativo", "habilitacao"], sin=["proposta desclassificada"]),
    T("sobrepreco", "Sobrepreço e superfaturamento", "sobrepreço", "Propostas e preços",
      "Sobrepreço é o preço orçado, licitado ou contratado expressivamente superior aos de referência de mercado; superfaturamento é o dano efetivo ao patrimônio público, como pagar por quantidade não entregue ou por qualidade inferior.",
      "Um item de obra orçado 40% acima do SINAPI indica sobrepreço; medir e pagar 1.000 m² quando foram executados 800 m² é superfaturamento.",
      "Lei 14.133/2021, art. 6º, LVI (sobrepreço) e LVII (superfaturamento); art. 59, §3º.",
      "Preço muito acima das referências atrai desclassificação e fiscalização dos tribunais de contas.",
      PRECOS, ["inexequibilidade", "valor-estimado", "sinapi", "representacao-tribunal-de-contas"], sin=["superfaturamento"]),
    T("planilha-de-custos", "Planilha de custos e formação de preços", "planilha de custos", "Propostas e preços",
      "Documento que detalha a composição do preço de serviços, especialmente com dedicação exclusiva de mão de obra: remuneração, encargos sociais e trabalhistas, benefícios, insumos, custos indiretos, tributos e lucro.",
      "Para um posto de vigilância 12x36, a planilha parte do piso da convenção coletiva, soma adicional noturno, encargos, vale-transporte, uniformes, custos indiretos, lucro e tributos.",
      "Instrução Normativa SEGES/MP 5/2017 (Anexo VII-D, modelo de planilha na esfera federal); Lei 14.133/2021, art. 59, §3º, e art. 135 (repactuação).",
      "Erros de planilha levam a desclassificação ou a prejuízo durante todo o contrato; confira a convenção coletiva da base territorial.",
      PRECOS, ["convencao-coletiva", "dedicacao-exclusiva-de-mao-de-obra", "repactuacao", "inexequibilidade"], sin=["planilha de formação de preços", "planilha de custos e formação de preços"]),
    T("convencao-coletiva", "Convenção coletiva de trabalho (CCT)", "convenção coletiva", "Propostas e preços",
      "Acordo entre sindicatos de empregados e de empregadores que fixa pisos salariais, benefícios e condições de trabalho de uma categoria em uma base territorial, e que orienta o custo de mão de obra nas propostas.",
      "O edital de limpeza indica a CCT dos trabalhadores de asseio da capital; a planilha usa o piso e os benefícios dela.",
      "Lei 14.133/2021, art. 135 (repactuação vinculada à data do acordo, convenção ou dissídio); IN SEGES/MP 5/2017.",
      "Nova convenção com reajuste de piso dá direito a pedir repactuação; acompanhe a data-base da categoria.",
      PRECOS, ["planilha-de-custos", "repactuacao", "dedicacao-exclusiva-de-mao-de-obra"], sin=["CCT", "acordo coletivo", "dissídio coletivo"]),
    T("margem-de-preferencia", "Margem de preferência", "margem de preferência", "Propostas e preços",
      "Percentual que permite à Administração contratar bens manufaturados nacionais e serviços nacionais que atendam a normas técnicas brasileiras mesmo com preço superior ao de produtos estrangeiros, dentro do limite legal.",
      "Com margem de 10% prevista em decreto, um equipamento nacional a R$ 108 mil pode vencer um importado a R$ 100 mil.",
      "Lei 14.133/2021, art. 26 (até 10%, e até 20% para bens e serviços resultantes de desenvolvimento e inovação tecnológica no País, §2º).",
      "Só se aplica quando houver regulamentação e previsão no edital; verifique o decreto que trata do seu produto.",
      PRECOS, ["criterios-de-desempate", "me-epp"]),
    T("criterio-de-julgamento", "Critério de julgamento", "critério de julgamento", "Sessão, julgamento e recursos",
      "Regra que define como a proposta vencedora será escolhida: menor preço, maior desconto, melhor técnica ou conteúdo artístico, técnica e preço, maior lance (leilão) ou maior retorno econômico.",
      "Um pregão de passagens aéreas é julgado por maior desconto sobre a tarifa; um projeto de engenharia consultiva, por técnica e preço.",
      "Lei 14.133/2021, art. 33 (lista) e arts. 34 a 39 (regras de cada critério).",
      "O critério define a estratégia: em técnica e preço, a nota técnica pesa tanto quanto o preço.",
      ANALISE, ["tecnica-e-preco", "maior-desconto", "maior-retorno-economico", "modo-de-disputa"], sin=["menor preço", "tipo de licitação"]),
    T("tecnica-e-preco", "Técnica e preço", "técnica e preço", "Sessão, julgamento e recursos",
      "Critério de julgamento que pondera a nota da proposta técnica e a do preço, usado quando o fator técnico é relevante para a Administração, como em serviços de natureza predominantemente intelectual.",
      "Com peso 70 para técnica e 30 para preço, uma consultoria com equipe mais qualificada pode vencer mesmo com preço 15% maior.",
      "Lei 14.133/2021, art. 36 (cabimento) e §2º (proporção máxima de 70% para a proposta técnica); art. 37 (avaliação técnica).",
      "Invista na proposta técnica: atestados, currículos e metodologia valem pontos que o desconto não compensa.",
      PROP, ["criterio-de-julgamento", "concorrencia", "atestado-capacidade-tecnica"], sin=["melhor técnica"]),
    T("maior-desconto", "Maior desconto", "maior desconto", "Sessão, julgamento e recursos",
      "Critério de julgamento em que vence quem oferecer o maior percentual de desconto sobre o preço global fixado no edital ou sobre uma tabela de referência, aplicado também aos eventuais termos aditivos.",
      "Um pregão de medicamentos julga pelo maior desconto sobre a tabela CMED; outro, de peças automotivas, sobre a tabela do fabricante.",
      "Lei 14.133/2021, art. 33, II, e art. 34, §2º (desconto estendido aos aditivos); art. 24, parágrafo único (preço de referência no edital).",
      "Calcule o desconto sobre o preço aplicável de cada item, não sobre a média: itens com margem negativa podem destruir o contrato.",
      PRECOS, ["criterio-de-julgamento", "cmed", "pregao-eletronico"], sin=["desconto sobre tabela"]),
    T("maior-retorno-economico", "Maior retorno econômico", "maior retorno econômico", "Sessão, julgamento e recursos",
      "Critério usado exclusivamente em contratos de eficiência, em que vence a proposta que proporcionar a maior economia para a Administração, e a remuneração do contratado é um percentual dessa economia.",
      "Uma empresa de eficiência energética propõe reduzir 30% da conta de energia de um hospital e recebe parte da economia efetivamente obtida.",
      "Lei 14.133/2021, art. 6º, LIII (contrato de eficiência), art. 33, VI, e art. 39.",
      "Exige medição de linha de base confiável e metas contratuais claras; a remuneração depende do resultado.",
      PROP, ["criterio-de-julgamento", "matriz-de-riscos"], sin=["contrato de eficiência"]),
    T("modo-de-disputa", "Modo de disputa: aberto, fechado e combinado", "modo de disputa", "Sessão, julgamento e recursos",
      "Forma de apresentação das propostas: no modo aberto, os licitantes dão lances públicos e sucessivos; no fechado, as propostas ficam em sigilo até a abertura; os modos podem ser combinados.",
      "No modo aberto e fechado, a disputa começa com lances livres e termina com os melhores colocados enviando um lance final fechado.",
      "Lei 14.133/2021, art. 56 (modo fechado vedado isoladamente para menor preço ou maior desconto; modo aberto vedado isoladamente para técnica e preço) e art. 57 (intervalo mínimo entre lances).",
      "Defina antes o preço mínimo por item: nos minutos finais de um modo aberto não há tempo para refazer contas.",
      CONC, ["pregao-eletronico", "negociacao", "criterio-de-julgamento", "empate-ficto"], sin=["lances", "fase de lances", "disputa aberta"]),
    T("negociacao", "Negociação", "negociação", "Sessão, julgamento e recursos",
      "Após a definição do resultado do julgamento, a Administração pode negociar condições mais vantajosas com o primeiro colocado, e com os demais, pela ordem, quando o preço do primeiro permanecer acima do orçamento estimado.",
      "O primeiro colocado ficou 6% acima do valor estimado; o pregoeiro negocia no chat e a empresa reduz o preço até o limite.",
      "Lei 14.133/2021, art. 61, caput e §1º (negociação com os demais classificados quando o primeiro não atingir o orçamento); §2º (divulgação do resultado).",
      "Tenha o preço mínimo por item em mãos durante a sessão; a negociação acontece em tempo real.",
      PROP, ["modo-de-disputa", "valor-estimado", "proposta-comercial"]),
    T("criterios-de-desempate", "Critérios de desempate", "critérios de desempate", "Sessão, julgamento e recursos",
      "Regras aplicadas, pela ordem, quando duas ou mais propostas empatam: disputa final, avaliação de desempenho contratual prévio, ações de equidade entre homens e mulheres no ambiente de trabalho e programa de integridade.",
      "Duas propostas empatam após os lances; a disputa final não desempata e vence a empresa com melhor avaliação de desempenho registrada no cadastro.",
      "Lei 14.133/2021, art. 60 (critérios na ordem legal e, depois, preferências do §1º); benefícios de ME e EPP da LC 123/2006 aplicados antes.",
      "Registro de desempenho e programa de integridade deixam de ser só compliance e passam a desempatar licitações.",
      CONC, ["empate-ficto", "programa-de-integridade", "registro-cadastral", "margem-de-preferencia"], sin=["desempate"]),
    T("agente-de-contratacao", "Agente de contratação", "agente de contratação", "Sessão, julgamento e recursos",
      "Pessoa designada, preferencialmente entre servidores efetivos ou empregados públicos, para tomar decisões, acompanhar o trâmite da licitação e conduzir a sessão até a homologação. No pregão, é chamado de pregoeiro.",
      "O agente de contratação conduz a concorrência eletrônica, analisa as propostas com apoio da equipe técnica e envia o processo à autoridade para homologar.",
      "Lei 14.133/2021, art. 6º, LX, e art. 8º (§2º comissão de contratação com no mínimo 3 membros para bens e serviços especiais; §5º pregoeiro).",
      "Mensagens claras e tempestivas ao agente, pelo chat e nos prazos, evitam desclassificações por mal-entendido.",
      ANALISE, ["pregoeiro", "comissao-de-contratacao", "adjudicacao-e-homologacao"]),
    T("pregoeiro", "Pregoeiro", "pregoeiro", "Sessão, julgamento e recursos",
      "Agente de contratação responsável por conduzir o pregão: abre a sessão, conduz os lances, negocia, analisa aceitabilidade e habilitação e decide sobre a intenção de recurso.",
      "Durante a sessão, o pregoeiro convoca o primeiro colocado pelo chat do sistema para enviar a proposta ajustada em 2 horas.",
      "Lei 14.133/2021, art. 8º, §5º.",
      "Acompanhe o chat da sessão: convocações e prazos são comunicados ali, e perdê-los gera desclassificação.",
      ANALISE, ["agente-de-contratacao", "pregao-eletronico", "negociacao"]),
    T("comissao-de-contratacao", "Comissão de contratação", "comissão de contratação", "Sessão, julgamento e recursos",
      "Conjunto de agentes públicos, com no mínimo 3 membros, que substitui o agente de contratação em licitações de bens ou serviços especiais e em outros casos previstos em regulamento.",
      "Em uma concorrência de técnica e preço, a comissão avalia as propostas técnicas e atribui as notas.",
      "Lei 14.133/2021, art. 6º, L, e art. 8º, §2º.",
      "Decisões colegiadas costumam ser mais formais: fundamente pedidos e recursos com clareza técnica.",
      ANALISE, ["agente-de-contratacao", "tecnica-e-preco"]),
    T("fases-da-licitacao", "Fases da licitação", "fases da licitação", "Sessão, julgamento e recursos",
      "Sequência do processo licitatório na Lei 14.133: preparatória, divulgação do edital, apresentação de propostas e lances, julgamento, habilitação, recursal e homologação.",
      "Em um pregão típico: publicação no PNCP, sessão de lances, aceitação da proposta, habilitação do vencedor, prazo de recurso e homologação.",
      "Lei 14.133/2021, art. 17; §1º (inversão de fases, com habilitação antes do julgamento, mediante justificativa); §2º (forma eletrônica como regra).",
      "Saber em que fase está o processo diz quais prazos correm e quais providências cabem.",
      ANALISE, ["fase-preparatoria", "habilitacao", "recurso-administrativo", "adjudicacao-e-homologacao"], sin=["etapas da licitação", "inversão de fases"]),
    T("intencao-de-recurso", "Intenção de recurso", "intenção de recurso", "Sessão, julgamento e recursos",
      "Manifestação imediata, na sessão, de que o licitante pretende recorrer do julgamento ou da habilitação, requisito para apresentar depois as razões do recurso.",
      "Ao ser declarado o vencedor, a empresa registra no sistema a intenção de recorrer contra a habilitação dele e apresenta as razões em 3 dias úteis.",
      "Lei 14.133/2021, art. 165, §1º, I (manifestação imediata, sob pena de preclusão).",
      "Sem a intenção registrada na hora, o direito de recorrer se perde: tenha alguém acompanhando o encerramento da sessão.",
      CONC, ["recurso-administrativo", "pedido-de-reconsideracao", "adjudicacao-e-homologacao"], sin=["manifestação de recurso"]),
    T("pedido-de-reconsideracao", "Pedido de reconsideração", "pedido de reconsideração", "Sessão, julgamento e recursos",
      "Meio de impugnar ato da Administração do qual não cabe recurso hierárquico, dirigido à própria autoridade que o praticou.",
      "A empresa pede reconsideração de uma decisão de aplicação de advertência no contrato.",
      "Lei 14.133/2021, art. 165, II (prazo de 3 dias úteis); art. 167 (reconsideração da declaração de inidoneidade, em 15 dias úteis).",
      "Verifique qual meio cabe antes de protocolar: usar o instrumento errado pode custar o prazo.",
      CONTR, ["recurso-administrativo", "sancoes-administrativas"]),
    T("adjudicacao-e-homologacao", "Adjudicação e homologação", "homologação", "Sessão, julgamento e recursos",
      "Adjudicação é a atribuição do objeto ao vencedor; homologação é o ato da autoridade superior que confirma a regularidade do procedimento e encerra a licitação, permitindo a convocação para assinar o contrato.",
      "Após os recursos, a autoridade adjudica o item à empresa vencedora e homologa o resultado; em seguida, a empresa é convocada a assinar a ata ou o contrato.",
      "Lei 14.133/2021, art. 71, IV; art. 90 (convocação para assinatura; recusa injustificada gera sanção).",
      "Homologação não é contrato: prepare garantia e documentos para a assinatura dentro do prazo da convocação.",
      CONTR, ["fases-da-licitacao", "contrato-administrativo", "revogacao-e-anulacao"], sin=["adjudicação", "homologado", "adjudicado"]),
    T("revogacao-e-anulacao", "Revogação e anulação da licitação", "revogação", "Sessão, julgamento e recursos",
      "Revogação é o desfazimento da licitação por motivo de conveniência e oportunidade decorrente de fato superveniente; anulação é o desfazimento por ilegalidade insanável.",
      "Um órgão revoga um pregão porque a necessidade deixou de existir após reestruturação; outro anula uma concorrência por vício no edital.",
      "Lei 14.133/2021, art. 71, II e III, §§1º a 3º (prévia manifestação dos interessados); art. 165, I, d (cabe recurso).",
      "Antes da revogação ou anulação, a empresa deve ser ouvida: use a oportunidade para defender o resultado.",
      CONTR, ["adjudicacao-e-homologacao", "recurso-administrativo"], sin=["anulação", "licitação revogada"]),
    T("licitacao-deserta-e-fracassada", "Licitação deserta e licitação fracassada", "licitação deserta", "Sessão, julgamento e recursos",
      "Licitação deserta é aquela em que nenhum interessado apareceu; fracassada é aquela em que houve participantes, mas nenhum foi classificado ou habilitado. Ambas podem autorizar contratação direta em até 1 ano.",
      "Um pregão de manutenção em área remota fica deserto; o órgão contrata por dispensa, mantendo as condições do edital.",
      "Lei 14.133/2021, art. 75, III.",
      "Editais desertos e fracassados são oportunidades: o órgão ainda precisa contratar e as condições são conhecidas.",
      RADAR, ["dispensa-de-licitacao", "contratacao-direta", "go-no-go"], sin=["licitação fracassada", "pregão deserto"]),
]

NOVOS += [
    # ------------------------------------------------------------ contratos
    T("contrato-administrativo", "Contrato administrativo", "contrato administrativo", "Contratos",
      "Ajuste firmado entre a Administração e o particular para execução do objeto licitado ou contratado diretamente, regido por cláusulas que garantem prerrogativas à Administração, como alterar e extinguir unilateralmente, fiscalizar e aplicar sanções.",
      "Após a homologação, a empresa assina o contrato de prestação de serviços com cláusulas de vigência, preço, reajuste, garantias, fiscalização e penalidades.",
      "Lei 14.133/2021, art. 89 e seguintes; art. 92 (cláusulas necessárias); art. 104 (prerrogativas da Administração); art. 94 (divulgação no PNCP como condição de eficácia).",
      "O contrato é onde o lucro se confirma ou se perde: acompanhe prazos, medições, reajustes e notificações desde o primeiro dia.",
      CONTR, ["nota-de-empenho", "vigencia-e-prorrogacao", "aditivo-contratual", "fiscal-de-contrato"], sin=["contrato público", "contrato com a administração"]),
    T("nota-de-empenho", "Nota de empenho", "nota de empenho", "Contratos",
      "Documento orçamentário que reserva recurso para uma despesa e, em certas hipóteses, substitui o instrumento de contrato, como em compras com entrega imediata e integral sem obrigações futuras.",
      "Em uma compra de materiais com entrega em 10 dias e sem assistência técnica, o órgão emite nota de empenho em vez de contrato.",
      "Lei 14.133/2021, art. 95 (substituição do instrumento de contrato); Lei 4.320/1964, arts. 58 a 61 (empenho da despesa).",
      "Só entregue após receber a nota de empenho: sem empenho, não há garantia orçamentária de pagamento.",
      CONTR, ["contrato-administrativo", "recebimento-provisorio-e-definitivo", "pagamento-ordem-cronologica"], sin=["empenho"]),
    T("vigencia-e-prorrogacao", "Vigência e prorrogação do contrato", "prorrogação de contrato", "Contratos",
      "Prazo durante o qual o contrato produz efeitos e as regras para estendê-lo. Serviços e fornecimentos contínuos podem ter vigência de até 5 anos e ser prorrogados até 10 anos, se vantajosos e com crédito orçamentário.",
      "Um contrato de TI assinado por 30 meses é prorrogado por mais 30, após pesquisa que confirma a vantajosidade do preço.",
      "Lei 14.133/2021, arts. 105 a 114; art. 106 (contínuos até 5 anos); art. 107 (prorrogação até 10 anos); art. 111 (contratos por escopo prorrogados automaticamente quando o objeto não é concluído no prazo).",
      "Negocie a prorrogação com antecedência: o órgão precisa de manifestação do contratado e de pesquisa de vantajosidade.",
      CONTR, ["servico-continuo", "aditivo-contratual", "reajuste"], sin=["vigência contratual", "prorrogação contratual", "renovação de contrato"]),
    T("aditivo-contratual", "Termo aditivo e alteração contratual", "termo aditivo", "Contratos",
      "Instrumento que formaliza alterações no contrato, unilaterais ou por acordo, como acréscimos e supressões de quantidades, mudanças de projeto, prorrogações e reequilíbrio.",
      "O órgão acrescenta 20% nas quantidades de um contrato de manutenção; o termo aditivo registra o novo valor e o cronograma.",
      "Lei 14.133/2021, art. 124 (hipóteses); art. 125 (acréscimos e supressões de até 25%, e até 50% para acréscimos em reforma de edifício ou equipamento); art. 136 (situações registradas por apostilamento).",
      "Acima do limite legal, o contratado não é obrigado a aceitar; abaixo, é. Precifique a margem para acréscimos.",
      CONTR, ["apostilamento", "reequilibrio-economico-financeiro", "vigencia-e-prorrogacao"], sin=["aditivo", "alteração contratual", "acréscimo de 25%"]),
    T("apostilamento", "Apostilamento", "apostilamento", "Contratos",
      "Registro simples, sem necessidade de termo aditivo, de alterações previstas no próprio contrato, como reajuste por índice, compensações e atualizações de dotação orçamentária.",
      "Completado um ano da data do orçamento, o reajuste pelo IPCA é registrado por apostila e o valor mensal é atualizado.",
      "Lei 14.133/2021, art. 136.",
      "Peça o apostilamento do reajuste assim que completar a anualidade: pagamentos com valor desatualizado reduzem a margem.",
      CONTR, ["reajuste", "aditivo-contratual"], sin=["apostila"]),
    T("reajuste", "Reajuste", "reajuste", "Contratos",
      "Atualização do valor do contrato pela aplicação de índice de preços previsto no edital, com data-base vinculada à data do orçamento estimado e periodicidade anual.",
      "Um contrato de fornecimento de alimentação, com orçamento de março de 2025, é reajustado pelo IPCA a partir de março de 2026.",
      "Lei 14.133/2021, art. 6º, LVIII; art. 25, §7º (índice obrigatório no edital, independentemente do prazo de duração); art. 92, V.",
      "A anualidade conta da data do orçamento, não da assinatura: acompanhe para não perder meses de reajuste.",
      CONTR, ["repactuacao", "reequilibrio-economico-financeiro", "apostilamento"], sin=["reajuste contratual", "reajustamento"]),
    T("repactuacao", "Repactuação", "repactuação", "Contratos",
      "Forma de manutenção do equilíbrio de contratos de serviços contínuos com dedicação exclusiva de mão de obra, pela demonstração analítica da variação dos custos, como novo piso salarial da convenção coletiva.",
      "A nova CCT dos vigilantes aumenta o piso em 6%; a empresa pede repactuação com a planilha atualizada e o órgão recalcula o valor dos postos.",
      "Lei 14.133/2021, art. 6º, LIX, e art. 135 (anualidade a partir da data do acordo, convenção ou dissídio para custos de mão de obra).",
      "O pedido deve ser feito durante a vigência; deixar para depois da prorrogação pode configurar preclusão.",
      CONTR, ["convencao-coletiva", "planilha-de-custos", "reajuste", "dedicacao-exclusiva-de-mao-de-obra"]),
    T("reequilibrio-economico-financeiro", "Reequilíbrio econômico-financeiro", "reequilíbrio econômico-financeiro", "Contratos",
      "Revisão do valor do contrato para restabelecer a relação original entre encargos e remuneração, diante de fatos imprevisíveis, ou previsíveis de consequências incalculáveis, força maior, caso fortuito ou fato do príncipe.",
      "Um aumento extraordinário do preço do asfalto, fora da álea ordinária, justifica pedido de reequilíbrio com notas fiscais e composição de custos.",
      "Lei 14.133/2021, art. 124, II, d; art. 131 (pedido durante a vigência e antes de eventual prorrogação); art. 103, §5º (riscos da matriz).",
      "Documente o impacto com notas, índices e composições; riscos assumidos na matriz não geram reequilíbrio.",
      CONTR, ["matriz-de-riscos", "reajuste", "repactuacao", "aditivo-contratual"], sin=["revisão contratual", "reequilíbrio", "equilíbrio econômico-financeiro"]),
    T("garantia-contratual", "Garantia contratual", "garantia contratual", "Contratos",
      "Garantia exigida do contratado para assegurar a execução do contrato, nas modalidades caução em dinheiro ou títulos da dívida pública, seguro-garantia ou fiança bancária, à escolha do contratado.",
      "O edital exige garantia de 5% do valor do contrato; a empresa apresenta apólice de seguro-garantia antes da assinatura.",
      "Lei 14.133/2021, art. 96 (modalidades); art. 98 (até 5% do valor inicial, podendo chegar a 10% conforme complexidade e riscos); art. 99 (obras de grande vulto: seguro-garantia de até 30%).",
      "Inclua o custo da garantia no preço e providencie a apólice com antecedência: seguradoras analisam o balanço.",
      CONTR, ["seguro-garantia", "garantia-de-proposta", "obra-de-grande-vulto"], sin=["garantia de execução", "caução", "fiança bancária"]),
    T("seguro-garantia", "Seguro-garantia", "seguro-garantia", "Contratos",
      "Modalidade de garantia em que uma seguradora assegura o fiel cumprimento das obrigações do contratado; em obras de grande vulto, pode incluir cláusula de retomada (step-in), em que a seguradora assume a execução em caso de inadimplemento.",
      "Em uma obra de grande vulto, a seguradora assume a conclusão quando o contratado abandona a execução.",
      "Lei 14.133/2021, art. 96, §1º, II, e art. 97; art. 102 (cláusula de retomada).",
      "O custo do prêmio depende do rating da empresa: planeje o limite de crédito com a seguradora antes das disputas.",
      CONTR, ["garantia-contratual", "obra-de-grande-vulto"], sin=["step-in"]),
    T("garantia-de-proposta", "Garantia de proposta", "garantia de proposta", "Contratos",
      "Garantia que o edital pode exigir como requisito de pré-habilitação, no valor de até 1% do valor estimado, para assegurar a seriedade da proposta.",
      "Em uma concorrência de obra, o licitante apresenta seguro-garantia de proposta de 1% do valor estimado com a proposta.",
      "Lei 14.133/2021, art. 58 (até 1% do valor estimado; devolução em até 10 dias úteis após a assinatura do contrato ou a data em que for declarada fracassada a licitação; execução se o vencedor se recusar a assinar).",
      "Custo pequeno, mas o prazo de emissão pode inviabilizar a participação se deixado para a última hora.",
      CONTR, ["garantia-contratual", "seguro-garantia"]),
    T("fiscal-de-contrato", "Gestor e fiscal de contrato", "fiscal de contrato", "Contratos",
      "Agentes públicos designados para acompanhar e fiscalizar a execução do contrato, anotar ocorrências, determinar correções e atestar a execução para pagamento.",
      "O fiscal registra atraso na entrega e notifica a empresa; sem correção no prazo, o caso é levado ao gestor para abertura de processo sancionador.",
      "Lei 14.133/2021, art. 117.",
      "Mantenha um canal formal com o fiscal: respostas por escrito às notificações são sua principal defesa depois.",
      CONTR, ["acordo-de-nivel-de-servico", "recebimento-provisorio-e-definitivo", "sancoes-administrativas"], sin=["gestor de contrato", "fiscalização do contrato"]),
    T("acordo-de-nivel-de-servico", "Acordo de nível de serviço (ANS/SLA) e IMR", "acordo de nível de serviço", "Contratos",
      "Critérios objetivos de medição da qualidade do serviço, com indicadores e metas, que ajustam o pagamento ao resultado; na esfera federal também se usa o Instrumento de Medição de Resultado (IMR).",
      "Um contrato de suporte de TI prevê atendimento de chamados críticos em 4 horas; cada descumprimento reduz um percentual da fatura do mês.",
      "Lei 14.133/2021, art. 6º, XXIII, f e g (modelo de gestão e critérios de medição e pagamento no TR) e art. 144 (remuneração variável vinculada ao desempenho); IN SEGES/MP 5/2017.",
      "Glosas por nível de serviço corroem a margem silenciosamente: precifique os indicadores antes do lance.",
      CONTR, ["termo-de-referencia", "fiscal-de-contrato", "servico-continuo"], sin=["SLA", "ANS", "IMR", "glosa"]),
    T("recebimento-provisorio-e-definitivo", "Recebimento provisório e definitivo", "recebimento do objeto", "Contratos",
      "Etapas formais de aceitação do objeto: o recebimento provisório verifica a entrega e o definitivo confirma que o objeto atende às exigências do contrato, liberando o pagamento.",
      "O almoxarifado recebe os computadores provisoriamente; após testes, a comissão emite o termo de recebimento definitivo.",
      "Lei 14.133/2021, art. 140.",
      "Guarde canhotos e termos de recebimento: são a prova de entrega em caso de atraso no pagamento.",
      CONTR, ["pagamento-ordem-cronologica", "fiscal-de-contrato", "nota-de-empenho"], sin=["recebimento provisório", "recebimento definitivo", "atesto"]),
    T("pagamento-ordem-cronologica", "Pagamento em ordem cronológica", "ordem cronológica de pagamentos", "Contratos",
      "Regra que obriga a Administração a pagar suas obrigações observando a ordem cronológica de exigibilidade, por fonte de recursos e categoria de contrato, com exceções justificadas e publicadas.",
      "Uma empresa com nota atestada em janeiro deve receber antes de outra com nota de março na mesma categoria, salvo justificativa publicada.",
      "Lei 14.133/2021, art. 141 (ordem cronológica e hipóteses de alteração justificada); art. 137, §2º, IV (atraso superior a 2 meses dá direito à extinção pelo contratado).",
      "Acompanhe a lista de pagamentos do órgão e cobre formalmente quando a ordem não for respeitada.",
      CONTR, ["recebimento-provisorio-e-definitivo", "extincao-do-contrato"], sin=["atraso de pagamento"]),
    T("conta-vinculada", "Conta vinculada", "conta vinculada", "Contratos",
      "Conta bancária bloqueada para movimentação, na qual a Administração deposita parte do valor mensal de contratos com dedicação exclusiva de mão de obra para pagar férias, 13º e verbas rescisórias.",
      "Do pagamento mensal de um contrato de limpeza, o órgão retém os percentuais de férias e 13º e os deposita na conta vinculada; a empresa pede liberação ao pagar esses direitos.",
      "Lei 14.133/2021, art. 121, §3º, II; IN SEGES/MP 5/2017 (Anexo XII, na esfera federal).",
      "A retenção afeta o caixa: considere no fluxo financeiro e peça as liberações com a documentação completa.",
      CONTR, ["dedicacao-exclusiva-de-mao-de-obra", "planilha-de-custos"], sin=["conta depósito vinculada"]),
    T("extincao-do-contrato", "Extinção do contrato (rescisão)", "extinção do contrato", "Contratos",
      "Encerramento do contrato antes do prazo, por ato unilateral da Administração, por acordo entre as partes ou por decisão arbitral ou judicial, nas hipóteses legais, com direito a defesa prévia.",
      "Depois de atrasos reiterados e notificações sem resposta, a Administração extingue unilateralmente o contrato e abre processo sancionador.",
      "Lei 14.133/2021, arts. 137 a 139; art. 137, §2º (hipóteses em que o contratado pode pedir a extinção, como atraso de pagamento superior a 2 meses).",
      "Documente as falhas do órgão também: atrasos de pagamento e ordens de paralisação dão direito ao contratado.",
      CONTR, ["sancoes-administrativas", "pagamento-ordem-cronologica", "fiscal-de-contrato"], sin=["rescisão contratual", "rescisão"]),
]

NOVOS += [
    # ------------------------------------------------------------ sanções e controle
    T("sancoes-administrativas", "Sanções administrativas em licitações e contratos", "sanções administrativas", "Sanções e controle",
      "Penalidades aplicáveis a licitantes e contratados por infrações como inexecução do contrato, recusa injustificada em assinar, fraude ou declaração falsa: advertência, multa, impedimento de licitar e contratar e declaração de inidoneidade.",
      "A empresa que não mantém a proposta e não assina o contrato recebe multa e impedimento de licitar e contratar com o ente por 1 ano.",
      "Lei 14.133/2021, art. 155 (infrações), art. 156 (sanções e dosimetria), art. 157 (defesa em 15 dias úteis para multa), art. 158 (processo de responsabilização) e art. 163 (reabilitação).",
      "Sanção fica registrada no CEIS ou no CNEP e aparece em qualquer consulta ao CNPJ: afeta toda a carteira de contratos.",
      CONSULTA, ["multa-contratual", "impedimento-de-licitar", "declaracao-de-inidoneidade", "ceis-e-cnep"], sin=["penalidades", "sanções em licitação", "advertência"]),
    T("multa-contratual", "Multa em licitações e contratos", "multa", "Sanções e controle",
      "Sanção pecuniária calculada na forma do edital ou do contrato, entre 0,5% e 30% do valor do contrato licitado ou celebrado, que pode ser cumulada com as demais sanções.",
      "Por atraso de 15 dias na entrega, o contrato prevê multa moratória de 0,33% ao dia, limitada a 10%; a empresa apresenta defesa demonstrando a causa do atraso.",
      "Lei 14.133/2021, art. 156, II e §3º (entre 0,5% e 30%); art. 162 (multa de mora); art. 156, §7º (cumulação); art. 156, §8º (desconto da garantia ou dos pagamentos).",
      "Leia a cláusula de multas antes de participar: multa diária sem teto é um dos principais riscos de um edital.",
      CONTR, ["sancoes-administrativas", "garantia-contratual", "go-no-go"], sin=["multa moratória", "multa compensatória"]),
    T("impedimento-de-licitar", "Impedimento de licitar e contratar", "impedimento de licitar e contratar", "Sanções e controle",
      "Sanção que impede o responsável de licitar ou contratar no âmbito da Administração direta e indireta do ente federativo que a aplicou, pelo prazo máximo de 3 anos.",
      "Uma empresa impedida por um município não pode participar de licitações daquele município durante o prazo, mas pode disputar editais de outros entes.",
      "Lei 14.133/2021, art. 156, III e §4º.",
      "Antes de contratar parceiros ou subcontratados, consulte sanções: participar com empresa impedida pode contaminar a proposta.",
      CONSULTA, ["declaracao-de-inidoneidade", "sancoes-administrativas", "ceis-e-cnep"], sin=["suspensão de licitar", "impedida de licitar"]),
    T("declaracao-de-inidoneidade", "Declaração de inidoneidade", "declaração de inidoneidade", "Sanções e controle",
      "Sanção mais grave da Lei 14.133, que impede o responsável de licitar ou contratar com toda a Administração Pública, de todos os entes federativos, por 3 a 6 anos, aplicada em infrações graves como fraude e declaração falsa.",
      "Uma empresa que apresentou atestado falso é declarada inidônea e fica impedida de contratar com qualquer órgão público do país por 4 anos.",
      "Lei 14.133/2021, art. 156, IV e §5º; art. 163 (reabilitação após reparação do dano, cumprimento de condições e, em certos casos, programa de integridade).",
      "Consulte a situação de concorrentes: uma empresa inidônea classificada à sua frente pode ser afastada por recurso.",
      CONSULTA, ["impedimento-de-licitar", "ceis-e-cnep", "programa-de-integridade", "recurso-administrativo"], sin=["empresa inidônea", "inidoneidade"]),
    T("ceis-e-cnep", "CEIS e CNEP", "CEIS e CNEP", "Sanções e controle",
      "Cadastros mantidos pela Controladoria-Geral da União: o CEIS (Cadastro Nacional de Empresas Inidôneas e Suspensas) reúne sanções que restringem o direito de licitar e contratar; o CNEP (Cadastro Nacional de Empresas Punidas) reúne sanções da Lei Anticorrupção.",
      "Antes de habilitar o vencedor, o pregoeiro consulta o CEIS, o CNEP e o cadastro de licitantes inidôneos do TCU.",
      "Lei 12.846/2013, arts. 22 e 23; Lei 14.133/2021, art. 161 (registro das sanções em até 15 dias úteis).",
      "Consultar concorrentes nesses cadastros é rotina de inteligência competitiva e base para recursos.",
      CONSULTA, ["declaracao-de-inidoneidade", "impedimento-de-licitar", "lei-anticorrupcao"], sin=["CEIS", "CNEP", "cadastro de empresas inidôneas"]),
    T("lei-anticorrupcao", "Lei Anticorrupção (Lei 12.846/2013)", "Lei Anticorrupção", "Sanções e controle",
      "Lei que responsabiliza objetivamente, nas esferas administrativa e civil, as pessoas jurídicas por atos lesivos contra a Administração Pública, inclusive fraudes em licitações e contratos.",
      "Uma empresa que combina preços com concorrentes em uma licitação responde por ato lesivo, com multa de até 20% do faturamento bruto e publicação da decisão.",
      "Lei 12.846/2013, art. 5º, IV (atos lesivos em licitações e contratos) e art. 6º (sanções); Decreto 11.129/2022 (regulamento).",
      "Programa de integridade efetivo reduz a multa e passa a pesar em licitações.",
      CONSULTA, ["programa-de-integridade", "ceis-e-cnep", "sancoes-administrativas"], sin=["Lei 12.846", "lei da empresa limpa"]),
    T("programa-de-integridade", "Programa de integridade (compliance)", "programa de integridade", "Sanções e controle",
      "Conjunto de mecanismos internos de integridade, auditoria, canal de denúncias e aplicação de código de ética para prevenir e detectar irregularidades, que a Lei 14.133 usa como exigência, critério de desempate e atenuante.",
      "O vencedor de uma obra de grande vulto implanta o programa em até 6 meses após a assinatura; em outra licitação, o programa desempata duas propostas.",
      "Lei 14.133/2021, art. 25, §4º (obrigatório em contratações de grande vulto), art. 60, IV (desempate), art. 156, §1º, V (dosimetria) e art. 163, parágrafo único (reabilitação); Decreto 11.129/2022.",
      "Integridade virou vantagem competitiva, não só custo: documente políticas, treinamentos e canal de denúncias.",
      GNG, ["criterios-de-desempate", "obra-de-grande-vulto", "lei-anticorrupcao"], sin=["compliance", "integridade"]),
    T("representacao-tribunal-de-contas", "Representação ao Tribunal de Contas", "representação ao tribunal de contas", "Sanções e controle",
      "Instrumento pelo qual qualquer licitante, contratado ou pessoa física ou jurídica leva ao tribunal de contas ou ao controle interno irregularidades na aplicação da Lei 14.133, podendo resultar em medida cautelar que suspende o certame.",
      "Com a impugnação negada, uma empresa representa ao TCE contra exigência restritiva, e o tribunal suspende a licitação cautelarmente.",
      "Lei 14.133/2021, art. 170, §4º; art. 171 (suspensão cautelar e prazos de decisão).",
      "É complementar à impugnação e ao recurso, não substituto: fundamente com o edital, a lei e a jurisprudência do tribunal.",
      ANALISE, ["impugnacao", "recurso-administrativo", "sobrepreco"], sin=["representação ao TCU", "denúncia ao tribunal de contas", "TCE", "TCU"]),

    # ------------------------------------------------------------ sistemas e tabelas
    T("compras-gov-br", "Compras.gov.br", "Compras.gov.br", "Sistemas e tabelas",
      "Sistema de compras do Governo Federal, também usado por estados e municípios que aderem, onde ocorrem pregões, concorrências e dispensas eletrônicas, com cadastro no SICAF e ferramentas de pesquisa de preços.",
      "Um fornecedor cadastrado no SICAF acessa o Compras.gov.br, envia proposta para um pregão de uma universidade federal e disputa os lances na sessão.",
      "Lei 14.133/2021, art. 17, §2º (forma eletrônica); Instrução Normativa SEGES/ME 73/2022 (licitação eletrônica por menor preço ou maior desconto na esfera federal).",
      "Estados e municípios também usam outras plataformas; mapear onde seus clientes compram é parte do radar.",
      RADAR, ["sicaf", "pncp", "dispensa-eletronica", "plataformas-de-licitacao"], sin=["Comprasnet", "ComprasNet", "compras governamentais"]),
    T("plataformas-de-licitacao", "Plataformas de licitação eletrônica", "plataformas de licitação", "Sistemas e tabelas",
      "Sistemas em que órgãos públicos realizam licitações eletrônicas, públicos ou privados, integrados ao PNCP. Além do Compras.gov.br, há plataformas estaduais e privadas usadas por estados e municípios.",
      "Um estado usa sistema próprio, um município usa uma plataforma privada credenciada e outro usa o Compras.gov.br; todos publicam os editais no PNCP.",
      "Lei 14.133/2021, art. 17, §2º, e art. 175 (sistemas eletrônicos próprios ou de terceiros, integrados ao PNCP).",
      "Cada plataforma exige cadastro próprio e às vezes certificado digital: cadastre-se antes de precisar.",
      RADAR, ["compras-gov-br", "pncp"], sin=["portal de licitações", "BLL", "Licitações-e", "BNC"]),
    T("catmat-catser", "CATMAT e CATSER", "CATMAT", "Sistemas e tabelas",
      "Catálogos padronizados de materiais (CATMAT) e de serviços (CATSER) do Governo Federal, que atribuem um código a cada item e permitem comparar compras e preços entre órgãos.",
      "O item \"papel A4, 75 g/m²\" tem um código CATMAT; com ele, é possível ver todos os preços praticados em pregões federais.",
      "Catálogo de materiais e serviços do Compras.gov.br; Instrução Normativa SEGES/ME 65/2021 (uso na pesquisa de preços).",
      "Conhecer os códigos CATMAT/CATSER do seu portfólio facilita o monitoramento de editais e de preços.",
      PRECOS, ["painel-de-precos", "pesquisa-de-precos", "compras-gov-br"], sin=["CATSER", "código CATMAT", "catálogo de materiais"]),
    T("painel-de-precos", "Painel de Preços e Pesquisa de Preços do Compras.gov.br", "Painel de Preços", "Sistemas e tabelas",
      "Ferramentas do Governo Federal que reúnem os preços praticados em compras homologadas no Compras.gov.br, por código CATMAT ou CATSER, usadas como parâmetro prioritário na pesquisa de preços.",
      "O órgão pesquisa o código do item, filtra por período e UF e usa a mediana dos preços homologados como referência.",
      "Lei 14.133/2021, art. 23, §1º, I; Instrução Normativa SEGES/ME 65/2021.",
      "Os mesmos dados que formam o teto do órgão mostram o preço que você precisa bater.",
      PRECOS, ["pesquisa-de-precos", "catmat-catser", "valor-estimado", "banco-de-precos-em-saude"], sin=["Painel de Preços", "Pesquisa de Preços"]),
    T("sicro", "SICRO", "SICRO", "Sistemas e tabelas",
      "Sistema de Custos Referenciais de Obras do DNIT, com custos de insumos e composições de serviços de infraestrutura de transportes, usado como referência obrigatória em obras rodoviárias, ferroviárias e hidroviárias.",
      "O orçamento de uma pavimentação rodoviária usa as composições do SICRO da região e o BDI referencial.",
      "Lei 14.133/2021, art. 23, §2º, I (SICRO para obras e serviços de infraestrutura de transportes); Decreto 7.983/2013.",
      "Compare suas composições com o SICRO para identificar sobrepreço no orçamento ou risco de inexequibilidade.",
      PRECOS, ["sinapi", "bdi", "valor-estimado"], sin=["Sistema de Custos Referenciais de Obras"]),
    T("cmed", "Tabela CMED", "CMED", "Sistemas e tabelas",
      "Lista de preços máximos de medicamentos definida pela Câmara de Regulação do Mercado de Medicamentos, com Preço Fábrica (PF) e Preço Máximo de Venda ao Governo (PMVG) por alíquota de ICMS.",
      "Em um pregão de medicamentos, o preço ofertado de um item sujeito ao CAP não pode superar o PMVG da alíquota de ICMS do estado do órgão.",
      "Lei 10.742/2003 (CMED); Resolução CMED 3/2011 (Coeficiente de Adequação de Preços — CAP e PMVG); desonerações do Convênio ICMS 87/2002.",
      "Use o preço aplicável correto (PF ou PMVG, na coluna de ICMS da UF) e converta embalagem para unidade antes do lance.",
      PRECOS, ["pmvg-e-cap", "maior-desconto", "banco-de-precos-em-saude"], sin=["tabela CMED", "preço fábrica", "PF"]),
    T("pmvg-e-cap", "PMVG e CAP", "PMVG", "Sistemas e tabelas",
      "O CAP (Coeficiente de Adequação de Preços) é um desconto mínimo obrigatório sobre o Preço Fábrica em vendas de certos medicamentos a entes públicos; o PMVG (Preço Máximo de Venda ao Governo) é o resultado dessa aplicação.",
      "Um medicamento oncológico com PF de R$ 1.000 e CAP vigente tem PMVG menor; a proposta ao hospital público não pode superá-lo.",
      "Resolução CMED 3/2011 e atualizações do percentual do CAP pela CMED.",
      "Ofertar acima do PMVG leva a desclassificação e a sanções da CMED; confira quais itens estão sujeitos ao CAP.",
      PRECOS, ["cmed", "banco-de-precos-em-saude"], sin=["CAP", "Coeficiente de Adequação de Preços", "Preço Máximo de Venda ao Governo"]),
    T("banco-de-precos-em-saude", "BPS — Banco de Preços em Saúde", "BPS", "Sistemas e tabelas",
      "Sistema do Ministério da Saúde que registra compras públicas e privadas de medicamentos e produtos para a saúde, usado como parâmetro de pesquisa de preços.",
      "Um município consulta o BPS para estimar o preço de seringas antes de licitar.",
      "Lei 14.133/2021, art. 23, §1º, I (banco de preços em saúde como parâmetro).",
      "Útil para distribuidores: mostra preços praticados por região e por comprador.",
      PRECOS, ["cmed", "painel-de-precos", "pesquisa-de-precos"], sin=["Banco de Preços em Saúde"]),
    T("orcamento-de-referencia", "Orçamento de referência de obras", "orçamento de referência", "Sistemas e tabelas",
      "Orçamento elaborado pela Administração para obras e serviços de engenharia, com custos unitários baseados em sistemas oficiais como SINAPI e SICRO, acrescidos de BDI e encargos sociais.",
      "A planilha orçamentária de uma creche soma as composições SINAPI de cada serviço, o BDI de 22% e os encargos desonerados.",
      "Lei 14.133/2021, art. 23, §2º; Decreto 7.983/2013.",
      "Revise composições e quantitativos: erros no orçamento viram sobrepreço, inexequibilidade ou aditivos.",
      PRECOS, ["sinapi", "sicro", "bdi", "valor-estimado"], sin=["planilha orçamentária", "orçamento estimativo"]),
    T("lei-das-estatais", "Lei das Estatais (Lei 13.303/2016)", "Lei das Estatais", "Sistemas e tabelas",
      "Lei que rege licitações e contratos de empresas públicas e sociedades de economia mista, com regulamento interno de licitações e contratos (RILC) próprio de cada estatal.",
      "Uma licitação da Petrobras ou de uma companhia estadual de saneamento segue a Lei 13.303 e o regulamento da empresa, não a Lei 14.133.",
      "Lei 13.303/2016, arts. 28 a 84; art. 40 (regulamento interno).",
      "Leia o RILC da estatal: prazos, recursos e habilitação podem ser diferentes dos da Lei 14.133.",
      RADAR, ["lei-14133", "pncp"], sin=["Lei 13.303", "RILC", "estatais"]),

    T("portal-da-disputa", "Portal da disputa", "portal da disputa", "Sistemas e tabelas",
      "Sistema eletrônico em que a sessão pública da licitação efetivamente acontece, com envio de propostas, lances, chat com o pregoeiro e envio de documentos. Pode ser diferente do PNCP, que apenas divulga o edital.",
      "O edital de uma prefeitura está no PNCP, mas a disputa ocorre em uma plataforma privada credenciada; a empresa precisa de cadastro nessa plataforma para dar lances.",
      "Lei 14.133/2021, art. 17, §2º (forma eletrônica) e art. 175, §1º (sistemas de terceiros integrados ao PNCP).",
      "Confira no edital qual é o portal da disputa e faça o cadastro com antecedência: sem ele, não há como participar da sessão.",
      RADAR, ["plataformas-de-licitacao", "compras-gov-br", "pncp"], sin=["sistema da disputa", "plataforma da sessão"]),

    # ------------------------------------------------------------ estratégia
    T("taxa-de-sucesso", "Taxa de sucesso em licitações", "taxa de sucesso", "Estratégia",
      "Indicador comercial que mede a proporção de licitações vencidas sobre as disputadas, idealmente separado por órgão, objeto e motivo de perda.",
      "A empresa disputou 40 pregões e venceu 6 (15%); ao analisar, percebe que 10 derrotas foram por inabilitação, um problema interno.",
      "Não é instituto legal: é métrica de gestão comercial.",
      "Medir motivos de perda mostra onde agir: preço, documentação, escolha de editais ou execução.",
      GNG, ["go-no-go", "habilitacao", "inteligencia-competitiva"], sin=["win rate", "taxa de vitória"]),
    T("inteligencia-competitiva", "Inteligência competitiva em licitações", "inteligência competitiva", "Estratégia",
      "Coleta e análise sistemática de dados públicos sobre concorrentes, compradores e preços — resultados de licitações, contratos, atas e sanções — para decidir onde disputar e como precificar.",
      "Antes de um pregão de uniformes, a empresa levanta quem venceu os últimos 20 certames do órgão, com que desconto e se há sanções contra os vencedores.",
      "Baseada em dados públicos de transparência: Lei 14.133/2021, art. 174 (PNCP) e Lei 12.527/2011 (acesso à informação).",
      "Saber quem são os concorrentes prováveis e os preços que praticam transforma o lance em decisão, não em aposta.",
      CONC, ["taxa-de-sucesso", "pncp", "painel-de-precos", "ceis-e-cnep"], sin=["análise de concorrentes", "benchmarking de preços"]),
    T("b2g", "B2G — vendas para o governo", "B2G", "Estratégia",
      "Modelo de negócio business-to-government, em que a empresa vende produtos ou serviços para órgãos públicos, por licitação ou contratação direta.",
      "Uma empresa de software que vendia só para empresas cria uma área B2G com radar de editais, documentação de habilitação e processo de propostas.",
      "Regido pela Lei 14.133/2021 e, no caso de estatais, pela Lei 13.303/2016.",
      "B2G exige processos próprios: monitoramento diário, documentação sempre válida, precificação com regras públicas e gestão de contratos.",
      GNG, ["go-no-go", "taxa-de-sucesso", "inteligencia-competitiva", "lei-14133"], sin=["vender para o governo", "mercado público", "business to government"]),
]


# ================================================================ geração das páginas
import html as _html
import re as _re

esc = _html.escape
NOME_CONJUNTO = "Glossário Kasiski de licitações e contratos públicos"
MAX_LINKS_AUTO = 6


def _norm(t):
    t = unicodedata.normalize("NFD", t.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def termos():
    """Todos os termos (originais + novos), completos e em ordem alfabética."""
    lista = []
    for g in C.GLOSSARIO:
        e = EXTRAS.get(g["slug"], {})
        lista.append({"curto": g["termo"], "cat": "Estratégia", "sin": [], "rel": [], "perguntas": [], **g, **e})
    lista += NOVOS
    return sorted(lista, key=lambda t: _norm(t["termo"]))


def _padroes(lista):
    """Expressões usadas nos links automáticos (nome curto e sinônimos com 4+ letras), da mais longa para a mais curta."""
    pares = []
    for t in lista:
        for nome in dict.fromkeys([t["curto"], *t["sin"]]):  # ordem fixa: a página sai igual a cada geração
            if len(nome) >= 4:
                pares.append((nome, t["slug"]))
    pares.sort(key=lambda p: (-len(p[0]), p[0].lower(), p[1]))
    return [(_re.compile(r"(?<![\w-])" + _re.escape(esc(n)) + r"(?![\w-])", _re.I), s) for n, s in pares]


def _autolink(texto_esc, padroes, proprio, usados):
    """Liga a primeira menção de outros termos do glossário (fora de links já criados)."""
    for rx, slug in padroes:
        if slug == proprio or slug in usados or len(usados) >= MAX_LINKS_AUTO:
            continue
        partes = _re.split(r"(<a [^>]*>.*?</a>)", texto_esc)
        for i, p in enumerate(partes):
            if p.startswith("<a "):
                continue
            m = rx.search(p)
            if m:
                partes[i] = p[:m.start()] + f'<a href="/glossario/{slug}/">{m.group(0)}</a>' + p[m.end():]
                usados.add(slug)
                break
        texto_esc = "".join(partes)
    return texto_esc


def _descricao(t):
    d = t["definicao"]
    if len(d) <= 155:
        return d
    return d[:152].rsplit(" ", 1)[0].rstrip(",;:") + "…"


def _titulo_pergunta(t):
    return f"O que é {t['curto']}?"


def _artigos_relacionados(t, artigos):
    chaves = [_norm(x) for x in dict.fromkeys([t["curto"], *t["sin"]]) if len(x) >= 4]
    achados = [a for a in artigos if any(k in _norm(_re.sub("<[^>]+>", " ", a["html"])) for k in chaves)]
    return achados[:3]


def gerar(pagina, migalhas, cta_cadastro, site_url, artigos=()):
    lista = termos()
    por_slug = {t["slug"]: t for t in lista}
    padroes = _padroes(lista)
    conjunto = {"@type": "DefinedTermSet", "name": NOME_CONJUNTO, "url": site_url + "/glossario/"}

    # ------------------------------------------------ índice
    letras = {}
    for t in lista:
        letras.setdefault(_norm(t["termo"])[0].upper(), []).append(t)
    nav_letras = "".join(f'<a href="#letra-{l.lower()}">{l}</a>' for l in sorted(letras))
    chips = "".join(f'<button type="button" data-gcat="{esc(c)}" aria-pressed="false">{esc(c)}</button>' for c in CATEGORIAS
                    if any(t["cat"] == c for t in lista))

    def cartao(t):
        busca = _norm(" ".join([t["termo"], t["curto"], *t["sin"]]))
        resumo = t["definicao"] if len(t["definicao"]) <= 150 else t["definicao"][:147].rsplit(" ", 1)[0] + "…"
        return (f'<a class="s-termo" href="/glossario/{t["slug"]}/" data-cat="{esc(t["cat"])}" data-busca="{esc(busca)}">'
                f'<small>{esc(t["cat"])}</small><b>{esc(t["termo"])}</b><span>{esc(resumo)}</span></a>')

    grupos = "".join(f'<section class="s-letra" id="letra-{l.lower()}" data-letra><h2>{l}</h2><div class="s-termos">'
                     + "".join(cartao(t) for t in letras[l]) + "</div></section>" for l in sorted(letras))
    cab, ld = migalhas([("Início", "/"), ("Glossário", None)])
    set_ld = {"@context": "https://schema.org", **conjunto, "description": "Termos de licitações e contratos públicos explicados com definição, exemplo, legislação e aplicação prática.",
              "hasDefinedTerm": [{"@type": "DefinedTerm", "name": t["termo"], "url": f"{site_url}/glossario/{t['slug']}/"} for t in lista]}
    corpo = f'''{cab}<section class="s-secao s-glossario"><p class="s-sobre">Glossário</p>
  <h1>Glossário de licitações e contratos públicos</h1>
  <p class="s-lead">{len(lista)} termos do mercado público explicados com definição, exemplo prático, o que diz a lei e como isso afeta a sua empresa — da Lei 14.133 ao PNCP, da habilitação à gestão de contratos.</p>
  <div class="s-gloss-busca"><label for="gloss-q">Buscar termo</label>
    <input id="gloss-q" type="search" placeholder="Ex.: dispensa, atestado, reequilíbrio, SICAF" autocomplete="off" data-gloss-busca></div>
  <div class="s-cats" role="group" aria-label="Categorias"><button type="button" data-gcat="" aria-pressed="true">Todos</button>{chips}</div>
  <nav class="s-letras" aria-label="Letras">{nav_letras}</nav>
  <p class="s-nota" data-gloss-vazio hidden>Nenhum termo encontrado. <a href="/analisar-edital/">Analise um edital grátis</a> ou fale com a gente pelo chat.</p>
  {grupos}</section>
  <section class="s-secao s-faixa"><h2>Transforme os termos em decisões</h2><p>Radar de editais, análise com IA, concorrentes, preços e contratos no mesmo lugar.</p>
    <a class="s-botao s-botao-grande" href="{cta_cadastro}" data-cta="glossario_indice">Criar conta grátis</a></section>'''
    pagina("/glossario/", "Glossário de licitações e contratos públicos (Lei 14.133) | Kasiski",
           f"Glossário com {len(lista)} termos de licitações e contratos públicos explicados: pregão, dispensa, habilitação, SICAF, PNCP, BDI, reequilíbrio, sanções e mais.",
           corpo, prioridade="0.8", jsonld=[ld, set_ld])

    # ------------------------------------------------ páginas dos termos
    for i, t in enumerate(lista):
        usados_auto = set()  # cada termo recebe no máximo um link automático por página

        def lig(txt):
            return _autolink(esc(txt), padroes, t["slug"], usados_auto)
        definicao, exemplo, aplicacao = lig(t["definicao"]), lig(t["exemplo"]), lig(t["aplicacao"])
        cab, bl = migalhas([("Início", "/"), ("Glossário", "/glossario/"), (t["termo"], None)])
        nome_f, url_f = t["ferramenta"]
        sin = f'<p class="s-sinonimos">Também chamado de: {", ".join(esc(s) for s in t["sin"])}</p>' if t["sin"] else ""
        faq = ""
        if t["perguntas"]:
            faq = "<h2>Perguntas frequentes</h2>" + "".join(f"<h3>{esc(q)}</h3><p>{esc(a)}</p>" for q, a in t["perguntas"])
        rel = [por_slug[s] for s in t["rel"] if s in por_slug]
        rel_html = ""
        if rel:
            rel_html = ('<h2>Termos relacionados</h2><div class="s-termos s-termos-rel">'
                        + "".join(f'<a class="s-termo" href="/glossario/{r["slug"]}/"><b>{esc(r["termo"])}</b>'
                                  f'<span>{esc(r["definicao"][:110].rsplit(" ", 1)[0])}…</span></a>' for r in rel) + "</div>")
        arts = _artigos_relacionados(t, artigos)
        arts_html = ""
        if arts:
            arts_html = "<h2>Para se aprofundar</h2><ul>" + "".join(
                f'<li><a href="/inteligencia/{a["slug"]}/">{esc(a.get("titulo", a["slug"]))}</a></li>' for a in arts) + "</ul>"
        ant, prox = lista[i - 1] if i else None, lista[i + 1] if i + 1 < len(lista) else None
        navega = ('<nav class="s-gloss-nav" aria-label="Outros termos">'
                  + (f'<a href="/glossario/{ant["slug"]}/">← {esc(ant["termo"])}</a>' if ant else "<span></span>")
                  + '<a href="/glossario/">Todos os termos</a>'
                  + (f'<a href="/glossario/{prox["slug"]}/">{esc(prox["termo"])} →</a>' if prox else "<span></span>") + "</nav>")
        corpo = f'''{cab}<article class="s-artigo s-verbete"><p class="s-sobre"><a href="/glossario/">Glossário</a> · {esc(t["cat"])}</p>
  <h1>{esc(t["termo"])}</h1>{sin}
  <h2>{esc(_titulo_pergunta(t))}</h2><p class="s-definicao">{definicao}</p>
  <h2>Exemplo prático</h2><p>{exemplo}</p>
  <h2>O que diz a lei</h2><p>{esc(t["legislacao"])}</p>
  <h2>Como isso afeta a sua empresa</h2><p>{aplicacao}</p>
  {faq}
  <aside class="s-caixa-ferramenta"><b>No Kasiski</b><p>Veja como isso funciona na prática em <a href="{url_f}">{esc(nome_f)}</a>.</p>
    <a class="s-botao" href="{cta_cadastro}" data-cta="glossario_{t["slug"]}">Criar conta grátis</a></aside>
  {rel_html}{arts_html}
  <p class="s-nota">Conteúdo informativo, não substitui a análise jurídica do caso concreto. Confira sempre o texto legal e os regulamentos vigentes.</p>
  {navega}</article>'''
        termo_ld = {"@context": "https://schema.org", "@type": "DefinedTerm", "name": t["termo"], "description": t["definicao"],
                    "url": f"{site_url}/glossario/{t['slug']}/", "inDefinedTermSet": conjunto}
        if t["sin"]:
            termo_ld["alternateName"] = t["sin"]
        jl = [bl, termo_ld]
        if t["perguntas"]:
            jl.append({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
                {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in t["perguntas"]]})
        titulo = f"{_titulo_pergunta(t)} Definição, exemplo e lei | Kasiski"
        if len(titulo) > 70:
            titulo = f"{_titulo_pergunta(t)} | Glossário Kasiski"
        pagina(f"/glossario/{t['slug']}/", titulo, _descricao(t), corpo, prioridade="0.6", og_tipo="article", jsonld=jl)
    return len(lista)


def exportar_json(caminho):
    """Mesmo conteúdo do glossário público, para a tela Glossário do aplicativo (frontend/data/glossario.json)."""
    import json
    import os
    lista = [{k: t.get(k) for k in ("slug", "termo", "curto", "cat", "definicao", "exemplo", "legislacao", "aplicacao", "sin", "rel")}
             | {"perguntas": [list(p) for p in t.get("perguntas", [])]} for t in termos()]
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump({"categorias": CATEGORIAS, "termos": lista}, f, ensure_ascii=False, separators=(",", ":"))
    return len(lista)
