"""Prompts do Certame. Cada função devolve (sistema, usuario, demo)."""
import json

BASE = (
    "Você é especialista em licitações e contratos administrativos no Brasil: Lei 14.133/2021, "
    "LC 123/2006 (tratamento de ME/EPP), decretos regulamentadores e jurisprudência do TCU. "
    "Escreva em português do Brasil, com precisão técnica. Nunca invente fatos, números, datas, "
    "artigos ou acórdãos: se algo não constar do documento, diga que não consta. Sempre que possível, "
    "indique a página do documento no formato 'pág. N' (o texto traz marcas [pág. N])."
)


def _j(obj):
    return json.dumps(obj, ensure_ascii=False, default=str)


# ---------------------------------------------------------------- extração do edital (IA barata)
def extracao_edital(texto):
    sistema = BASE + " Sua tarefa agora é apenas EXTRAIR dados, sem opinar."
    usuario = f"""Extraia do edital abaixo os dados no formato JSON:
{{
 "orgao": "", "numero": "", "objeto": "", "modalidade": "", "criterio_julgamento": "",
 "tipo_objeto": "obra | servico_engenharia | servico_comum | servico_continuado | fornecimento | fornecimento_continuado | outro",
 "segmento": "saude | educacao | ti | alimentacao | transporte | limpeza | seguranca | obras | outro",
 "valor_estimado": null, "data_abertura": "AAAA-MM-DDTHH:MM ou null", "portal_disputa": "",
 "obra_ou_servico_engenharia": false, "exclusivo_me_epp": false, "grande_vulto": false,
 "exigencias_habilitacao": [{{"categoria": "juridica|fiscal|trabalhista|economica|tecnica|declaracao|setorial",
   "descricao": "", "pagina": ""}}],
 "exigencias_tecnicas_objeto": [""], "garantia_proposta": "", "garantia_contrato": "",
 "penalidades": [""], "prazo_execucao": "", "condicoes_pagamento": "", "reajuste": "",
 "termos_busca_pncp": ["2 ou 3 expressões curtas (2 a 4 palavras) com o núcleo do objeto, como aparecem em contratos públicos, para achar contratações parecidas. Ex.: 'limpeza predial', 'conservação e limpeza'"]
}}

Regras de classificação:
- "tipo_objeto": obra (construção/reforma/ampliação); servico_engenharia (serviço técnico de engenharia sem ser obra, ex. projeto, manutenção predial complexa); servico_comum (serviço sem mão de obra residente, ex. um evento); servico_continuado (serviço com dedicação de mão de obra ou continuidade, ex. limpeza, portaria, gestão terceirizada); fornecimento (compra pontual de bens); fornecimento_continuado (registro de preços ou entrega parcelada recorrente); outro se não se encaixar.
- "segmento": identifique pelo objeto e pelo órgão contratante o segmento setorial predominante. Use "saude" para hospitais, UBS, farmácias, serviços médicos; "educacao" para escolas, merenda, transporte escolar; "outro" se genérico.
- Exigências de habilitação com natureza setorial (ex.: registro na ANVISA, ART/RRT, licença sanitária, certificação de condutor escolar) vão na categoria "setorial", não em "tecnica".
- "grande_vulto": true se o edital mencionar expressamente contratação de grande vulto ou se o valor estimado for muito elevado para o tipo de objeto (ex.: obra acima de R$ 200 milhões, parâmetro do art. 6º, XXII, sujeito a atualização).

EDITAL:
{texto}"""
    demo = {
        "orgao": "Prefeitura Municipal de Exemplo", "numero": "Pregão Eletrônico 45/2026",
        "objeto": "Prestação de serviços contínuos de limpeza e conservação predial",
        "modalidade": "Pregão eletrônico", "criterio_julgamento": "Menor preço global",
        "tipo_objeto": "servico_continuado", "segmento": "limpeza",
        "valor_estimado": 1850000.0, "data_abertura": None, "portal_disputa": "BLL Compras",
        "obra_ou_servico_engenharia": False, "exclusivo_me_epp": False, "grande_vulto": False,
        "exigencias_habilitacao": [
            {"categoria": "juridica", "descricao": "Contrato social e alterações", "pagina": "12"},
            {"categoria": "fiscal", "descricao": "CND federal conjunta (RFB/PGFN)", "pagina": "13"},
            {"categoria": "fiscal", "descricao": "CRF do FGTS", "pagina": "13"},
            {"categoria": "trabalhista", "descricao": "CNDT", "pagina": "13"},
            {"categoria": "economica", "descricao": "Balanço dos 2 últimos exercícios, LG, SG e LC > 1", "pagina": "14"},
            {"categoria": "economica", "descricao": "Patrimônio líquido mínimo de 10% do valor estimado", "pagina": "14"},
            {"categoria": "tecnica", "descricao": "Atestado de execução de 100% da área licitada", "pagina": "15"},
        ],
        "exigencias_tecnicas_objeto": ["Equipe mínima de 24 serventes", "Uniformes e EPIs por conta da contratada"],
        "garantia_proposta": "Não exigida", "garantia_contrato": "5% do valor do contrato",
        "termos_busca_pncp": ["limpeza predial", "limpeza e conservação"],
        "penalidades": ["Multa de 0,5% ao dia de atraso", "Impedimento de licitar por até 3 anos"],
        "prazo_execucao": "12 meses, prorrogável", "condicoes_pagamento": "Até 30 dias após o atesto",
        "reajuste": "Repactuação anual (mão de obra) e IPCA (insumos)",
    }
    return sistema, usuario, demo


# ---------------------------------------------------------------- análise do edital (Claude)
def analise_edital(texto, extracao, empresa, cofre, contexto_legal):
    sistema = BASE + (" Você atua como consultor da EMPRESA LICITANTE, avaliando riscos, pendências de "
                      "habilitação e cláusulas que restringem indevidamente a competição (art. 9º da Lei 14.133). "
                      "O edital pode ser de obra, serviço de engenharia, serviço comum, serviço continuado, "
                      "fornecimento pontual ou registro de preços — adapte a análise ao tipo de objeto informado, "
                      "e quando houver segmento setorial (saúde, educação etc.), avalie também as exigências "
                      "regulatórias próprias desse setor usando as referências fornecidas. Se a modalidade indicar "
                      "dispensa ou inexigibilidade de licitação (contratação direta), NÃO trate o processo como um "
                      "pregão: não há sessão de disputa nem prazo de impugnação/recurso nos moldes dos arts. 164 e "
                      "165 — o que existe é, quando cabível, um aviso de contratação direta com prazo mínimo de 3 "
                      "dias úteis de divulgação prévia (art. 75, §3º). Nesse caso, avalie sobretudo se a hipótese "
                      "legal de dispensa/inexigibilidade está bem enquadrada e se o preço e a habilitação do "
                      "contratado estão justificados, e diga isso claramente no resumo.")
    usuario = f"""Analise o edital para a empresa abaixo.

EMPRESA: {_j(empresa)}
DOCUMENTOS NO COFRE DA EMPRESA (tipo, categoria, validade, situação): {_j(cofre)}
DADOS JÁ EXTRAÍDOS DO EDITAL (inclui tipo_objeto e segmento): {_j(extracao)}
REFERÊNCIAS LEGAIS (base de conhecimento, inclui regras gerais e, quando aplicável, do tipo de objeto/segmento):
{contexto_legal}

Devolva JSON:
{{
 "resumo": "até 6 linhas, linguagem de negócio, mencionando o tipo de objeto",
 "checklist": [{{"exigencia": "", "categoria": "", "pagina": "", "status": "atende|falta|vencido|verificar",
   "documento_cofre": "tipo do documento do cofre que atende ou null", "observacao": ""}}],
 "checklist_setorial": [{{"exigencia": "", "pagina": "", "status": "atende|falta|vencido|verificar",
   "observacao": "", "fundamento": "norma ou razão"}}],
 "clausulas_restritivas": [{{"clausula": "descrição objetiva", "pagina": "", "por_que_restringe": "",
   "fundamento": "artigo/súmula", "gravidade": "alta|media|baixa", "medida": "esclarecimento|impugnacao"}}],
 "riscos": [{{"tema": "", "descricao": "", "nivel": "alto|medio|baixo", "pagina": ""}}],
 "beneficios_me_epp": "o que se aplica ao porte da empresa, ou 'não se aplica'",
 "recomendacao": {{"decisao": "participar|participar_com_ressalvas|nao_participar", "justificativa": ""}},
 "proximos_passos": [""]
}}
Regras: compare cada exigência de habilitação PADRÃO (jurídica/fiscal/trabalhista/econômica/técnica) com o cofre
no campo "checklist"; documento vencido na data da sessão = "vencido"; exigência sem documento correspondente =
"falta"; quando não der para concluir = "verificar". Exigências de natureza SETORIAL (regulatória do tipo de
objeto ou do segmento — ex.: ART/RRT, registro ANVISA, licença sanitária, certificação de condutor escolar,
matriz de riscos de obra) vão em "checklist_setorial", separado do checklist padrão, e podem ficar "verificar"
quando o cofre não tiver documento equivalente para comparar. Se o edital for um objeto genérico sem exigência
setorial identificável, devolva "checklist_setorial" como lista vazia. Só aponte cláusula restritiva se houver
fundamento concreto.

EDITAL:
{texto}"""
    demo = {
        "resumo": ("Serviço contínuo de limpeza com valor estimado de R$ 1,85 milhão por 12 meses. A empresa atende "
                   "à maior parte da habilitação, mas falta o atestado técnico e a CNDT está vencida. Há exigência "
                   "de atestado de 100% da área, acima do limite legal de 50% dos quantitativos, o que justifica "
                   "impugnação."),
        "checklist": [
            {"exigencia": "Contrato social e alterações", "categoria": "juridica", "pagina": "12", "status": "atende",
             "documento_cofre": "Contrato social consolidado", "observacao": ""},
            {"exigencia": "CND federal conjunta", "categoria": "fiscal", "pagina": "13", "status": "atende",
             "documento_cofre": "CND Federal", "observacao": "Válida até a data da sessão"},
            {"exigencia": "CNDT", "categoria": "trabalhista", "pagina": "13", "status": "vencido",
             "documento_cofre": "CNDT", "observacao": "Emitir nova certidão antes da sessão"},
            {"exigencia": "Balanço e índices LG, SG e LC > 1", "categoria": "economica", "pagina": "14",
             "status": "verificar", "documento_cofre": None, "observacao": "Conferir índices no último balanço"},
            {"exigencia": "Atestado de 100% da área", "categoria": "tecnica", "pagina": "15", "status": "falta",
             "documento_cofre": None, "observacao": "Nenhum atestado compatível no cofre"},
        ],
        "checklist_setorial": [],
        "clausulas_restritivas": [
            {"clausula": "Atestado de capacidade técnica com 100% da área licitada", "pagina": "15",
             "por_que_restringe": "A exigência de quantitativos mínimos está limitada a 50% das parcelas de maior relevância.",
             "fundamento": "Lei 14.133, art. 67, §2º", "gravidade": "alta", "medida": "impugnacao"},
            {"clausula": "Visita técnica obrigatória em data única", "pagina": "16",
             "por_que_restringe": "A lei admite substituir a vistoria por declaração de conhecimento das condições.",
             "fundamento": "Lei 14.133, art. 63, §§2º e 3º", "gravidade": "media", "medida": "esclarecimento"},
        ],
        "riscos": [
            {"tema": "Multa diária", "descricao": "Multa de 0,5% ao dia sem teto definido.", "nivel": "medio", "pagina": "22"},
            {"tema": "Repactuação", "descricao": "Edital não indica a convenção coletiva de referência.", "nivel": "alto", "pagina": "19"},
        ],
        "beneficios_me_epp": "Empresa de porte 'demais': os benefícios da LC 123 não se aplicam.",
        "recomendacao": {"decisao": "participar_com_ressalvas",
                         "justificativa": "Objeto aderente, mas depende de impugnar o atestado ou obter atestado compatível."},
        "proximos_passos": ["Protocolar impugnação do item do atestado", "Emitir nova CNDT", "Conferir índices contábeis"],
    }
    return sistema, usuario, demo


# ---------------------------------------------------------------- verificação cruzada (outra IA)
def verificacao(texto, itens):
    sistema = BASE + (" Você é o REVISOR independente de outra IA. Confira cada apontamento contra o documento "
                      "original e contra a lei. Seja cético: só confirme o que o texto sustenta.")
    usuario = f"""Confira os apontamentos abaixo. Para cada um, devolva se o documento e a lei sustentam o que foi dito.

APONTAMENTOS: {_j(itens)}

Devolva JSON: {{"verificacoes": [{{"id": "", "confirmado": true, "comentario": "curto, dizendo o que confere ou o que está errado"}}]}}

DOCUMENTO:
{texto}"""
    demo = {"verificacoes": [{"id": i["id"], "confirmado": True, "comentario": "Confere com o documento."}
                             for i in itens]}
    if len(itens) > 2:
        demo["verificacoes"][-1] = {"id": itens[-1]["id"], "confirmado": False,
                                    "comentario": "Não localizei esse trecho no documento."}
    return sistema, usuario, demo


# ---------------------------------------------------------------- peças
TIPOS_PECA = {
    "esclarecimento": "Pedido de esclarecimento",
    "impugnacao": "Impugnação ao edital",
    "intencao_recurso": "Manifestação de intenção de recorrer",
    "recurso": "Recurso administrativo (razões recursais)",
    "contrarrazoes": "Contrarrazões ao recurso",
    "reequilibrio": "Pedido de reequilíbrio econômico-financeiro",
    "cobranca_pagamento": "Requerimento de pagamento em atraso",
    "defesa_previa": "Defesa prévia em processo sancionador",
}


def peca(tipo, empresa, referencia, pontos, instrucoes, contexto_legal):
    nome = TIPOS_PECA[tipo]
    sistema = BASE + (f" Redija uma minuta de '{nome}' em nome da empresa, com linguagem jurídica clara e "
                      "objetiva, pronta para revisão. Estrutura: endereçamento, qualificação, síntese dos fatos, "
                      "fundamentos (com os artigos corretos), pedidos, fecho com local, data e campo de assinatura. "
                      "Use colchetes [ ] para dados que o usuário precisa completar. Não invente jurisprudência: "
                      "cite acórdão ou súmula somente se estiver nas referências fornecidas.")
    usuario = f"""TIPO: {nome}
EMPRESA: {_j(empresa)}
PROCESSO/CONTRATO DE REFERÊNCIA: {_j(referencia)}
PONTOS A SUSTENTAR: {_j(pontos)}
INSTRUÇÕES DO USUÁRIO: {instrucoes or "nenhuma"}
REFERÊNCIAS LEGAIS:
{contexto_legal}

Escreva apenas o texto da peça, em texto simples (sem markdown)."""
    demo = (f"ILUSTRÍSSIMO(A) SENHOR(A) AGENTE DE CONTRATAÇÃO / PREGOEIRO(A) DO(A) "
            f"{(referencia.get('orgao') or '[ÓRGÃO]').upper()}\n\n"
            f"Referência: {referencia.get('numero') or '[número do processo]'}\n\n"
            f"{empresa.get('razao_social')}, inscrita no CNPJ sob o nº {empresa.get('cnpj')}, vem, respeitosamente, "
            f"apresentar {nome.upper()}, pelos fundamentos a seguir.\n\n"
            "I. DOS FATOS\n\n[Modo demonstração: configure as chaves de IA para gerar a peça completa.]\n\n"
            + "\n".join(f"- {p.get('clausula') or p.get('descricao') or p}" for p in (pontos or []))
            + "\n\nII. DO DIREITO\n\n[Fundamentação]\n\nIII. DOS PEDIDOS\n\n[Pedidos]\n\n"
            "[Cidade], [data].\n\n______________________________\n[Representante legal]")
    return sistema, usuario, demo


# ---------------------------------------------------------------- concorrentes
def analise_concorrente(tipo, texto, exigencias, dossie, edital, contexto_legal, valor_proposta=None, historico=None):
    foco = ("DOCUMENTOS DE HABILITAÇÃO do concorrente: confira validade de certidões na data da sessão, "
            "compatibilidade dos atestados (objeto e quantitativos), índices contábeis calculados do balanço, "
            "documentos faltantes e compatibilidade do CNAE/objeto social com o objeto licitado."
            if tipo == "habilitacao" else
            "PROPOSTA do concorrente: exequibilidade, erros de cálculo, planilha de custos (encargos, convenção "
            "coletiva, tributos, BDI), divergência com as especificações e condições do edital.")
    sistema = BASE + (" Você assessora uma empresa que avalia recorrer contra outro licitante. Examine a "
                      f"{foco} Aponte apenas falhas demonstráveis no documento, indicando onde estão.")
    usuario = f"""EDITAL: {_j(edital)}
EXIGÊNCIAS DO EDITAL: {_j(exigencias)}
DOSSIÊ PÚBLICO DO CONCORRENTE: {_j(dossie)}
HISTÓRICO DO CONCORRENTE EM OUTROS CERTAMES (dossiê completo consolidado; cada item cita a fonte): {_j(historico) if historico else "não há histórico consolidado"}
VALOR DA PROPOSTA INFORMADO PELO USUÁRIO: {valor_proposta or "não informado"}
REFERÊNCIAS LEGAIS:
{contexto_legal}

Use o HISTÓRICO para CRUZAR com o documento atual: atestados já conhecidos x atestados apresentados (quantitativos
e períodos), índices contábeis de exercícios anteriores x balanço atual, responsáveis técnicos, certidões,
sanções e motivos de inabilitações anteriores que possam se repetir. Cruzamento é hipótese a conferir: diga o que
conferir e onde; não afirme falha que o documento atual não mostre.

Devolva JSON:
{{"resumo": "", "apontamentos": [{{"tema": "", "descricao": "", "documento": "", "pagina": "",
  "fundamento": "", "forca": "forte|medio|fraco"}}],
  "exequibilidade": {{"conclusao": "exequivel|indicio_inexequivel|inexequivel_presumida|nao_se_aplica", "analise": ""}},
  "cruzamentos_historico": [{{"tema": "", "o_que_o_historico_mostra": "", "o_que_conferir_no_documento_atual": "", "fontes": [""], "forca": "forte|medio|fraco"}}],
  "sugestoes": [{{"peca": "recurso|contrarrazoes|intencao_recurso|pedido_diligencia|impugnacao|representacao",
    "tema": "", "argumento": "tese a sustentar, combinando os apontamentos e o histórico", "base": ["ids ou temas dos apontamentos e fontes do histórico"],
    "fundamento": "", "forca": "forte|medio|fraco"}}]}}

DOCUMENTO DO CONCORRENTE:
{texto}"""
    if tipo == "habilitacao":
        demo = {"resumo": "Foram encontrados indícios de falha na qualificação técnica e uma certidão vencida.",
                "apontamentos": [
                    {"tema": "Certidão vencida", "descricao": "CRF do FGTS com validade anterior à data da sessão.",
                     "documento": "CRF FGTS", "pagina": "4", "fundamento": "Lei 14.133, art. 68, IV",
                     "forca": "forte"},
                    {"tema": "Atestado incompatível", "descricao": "Atestado comprova 3.000 m², abaixo do mínimo exigido.",
                     "documento": "Atestado técnico", "pagina": "9", "fundamento": "Lei 14.133, art. 67, II",
                     "forca": "medio"},
                    {"tema": "Índice contábil", "descricao": "Liquidez corrente aparenta ser inferior a 1.",
                     "documento": "Balanço 2025", "pagina": "15", "fundamento": "Lei 14.133, art. 69",
                     "forca": "fraco"}],
                "exequibilidade": {"conclusao": "nao_se_aplica", "analise": ""},
                "cruzamentos_historico": [{"tema": "Atestados", "o_que_o_historico_mostra": "Inabilitação anterior por atestado abaixo do quantitativo (doc#1)",
                                           "o_que_conferir_no_documento_atual": "Somar os quantitativos dos atestados apresentados", "fontes": ["doc#1"], "forca": "forte"}],
                "sugestoes": [{"peca": "recurso", "tema": "Qualificação técnica insuficiente",
                               "argumento": "O atestado não alcança o quantitativo mínimo, falha já reconhecida contra a mesma empresa em outro certame.",
                               "base": ["Atestado incompatível", "doc#1"], "fundamento": "Lei 14.133, art. 67, II", "forca": "forte"}]}
    else:
        demo = {"resumo": "A proposta tem indícios de inexequibilidade na composição de custos de mão de obra.",
                "apontamentos": [
                    {"tema": "Piso salarial", "descricao": "Salário do servente abaixo do piso da convenção coletiva.",
                     "documento": "Planilha de custos", "pagina": "3", "fundamento": "Lei 14.133, art. 59, III",
                     "forca": "forte"},
                    {"tema": "Encargos", "descricao": "Encargos sociais do Submódulo 2.2 subdimensionados.",
                     "documento": "Planilha de custos", "pagina": "4", "fundamento": "Lei 14.133, art. 59, IV",
                     "forca": "medio"}],
                "exequibilidade": {"conclusao": "indicio_inexequivel",
                                   "analise": "Custos de mão de obra abaixo do mínimo legal indicam inexequibilidade."}}
    return sistema, usuario, demo


# ---------------------------------------------------------------- radar (IA barata)
def pontuar_radar(empresa, editais):
    sistema = BASE + " Avalie rapidamente a aderência de editais ao perfil de uma empresa."
    usuario = f"""PERFIL DA EMPRESA: {_j(empresa)}
EDITAIS: {_j(editais)}
Devolva JSON: {{"notas": [{{"numero_controle": "", "nota": 0, "motivo": "uma frase"}}]}}
Nota de 0 a 100: 80+ muito aderente; 50-79 possível; abaixo de 50 pouco aderente."""
    demo = {"notas": [{"numero_controle": e["numero_controle"], "nota": 60, "motivo": "Objeto relacionado às palavras-chave."}
                      for e in editais]}
    return sistema, usuario, demo


def triagem_publica(texto, extracao):
    """Triagem gratuita do site: pontos de atenção do edital, sem dados da empresa (resposta curta e barata)."""
    sistema = BASE + " Você faz uma TRIAGEM rápida do edital para um licitante que ainda não é cliente. Seja objetivo e fiel ao texto."
    usuario = f"""Com base no edital abaixo (e nos dados já extraídos), devolva JSON:
{{
 "resumo": "2 frases sobre o objeto e o que mais chama atenção",
 "pontos_atencao": [{{"titulo": "curto", "gravidade": "alta|media|baixa", "explicacao": "1-2 frases", "pagina": "",
                      "tipo": "clausula_restritiva|risco|exigencia"}}],
 "documentos_criticos": [{{"documento": "", "por_que": "exigência incomum, prazo curto, índice alto etc."}}],
 "prazo_minimo_ok": true
}}
Regras: no máximo 8 pontos de atenção e 5 documentos críticos; só aponte o que está no texto; "gravidade" alta = pode inabilitar ou
restringir indevidamente a competição (Lei 14.133/2021); não invente artigos.

DADOS EXTRAÍDOS: {extracao}

EDITAL:
{texto}"""
    demo = {
        "resumo": "Serviços contínuos de limpeza predial com fornecimento de materiais. Destaque para o atestado de 100% da área e o índice de liquidez elevado.",
        "pontos_atencao": [
            {"titulo": "Atestado de 100% da área licitada", "gravidade": "alta", "tipo": "clausula_restritiva", "pagina": "15",
             "explicacao": "A exigência de atestado com 100% do quantitativo supera o limite usual de 50% e pode ser impugnada."},
            {"titulo": "Liquidez corrente maior que 1,5", "gravidade": "media", "tipo": "exigencia", "pagina": "14",
             "explicacao": "Índice acima do usual sem justificativa no processo."},
            {"titulo": "Multa diária sem teto", "gravidade": "media", "tipo": "risco", "pagina": "22",
             "explicacao": "Multa de 0,5% ao dia sem limite definido aumenta o risco contratual."},
            {"titulo": "Visita técnica obrigatória", "gravidade": "baixa", "tipo": "exigencia", "pagina": "9",
             "explicacao": "A visita obrigatória pode ser substituída por declaração, segundo a jurisprudência do TCU."},
        ],
        "documentos_criticos": [{"documento": "Atestado de capacidade técnica", "por_que": "quantitativo mínimo elevado"},
                                {"documento": "Balanço patrimonial", "por_que": "índices de liquidez acima do usual"}],
        "prazo_minimo_ok": True,
    }
    return sistema, usuario, demo
