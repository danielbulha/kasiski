"""Sugestão de palavras-chave do radar e de segmentos a partir dos CNAEs da empresa.

Os termos foram escolhidos pelo jeito como os órgãos descrevem o objeto nos editais do PNCP
(ex.: CNAE 8121-4/00 "Limpeza em prédios e em domicílios" -> "limpeza predial", "conservação").
Ordem de busca: subclasse/classe (4 dígitos) -> grupo (3) -> divisão (2) -> texto do próprio CNAE.
O radar usa só os 8 primeiros termos, por isso os do CNAE principal vêm primeiro.
"""
import re
import unicodedata

# (termos para o radar, segmentos da empresa)
POR_CLASSE = {
    # Obras e engenharia
    "4120": (["construção de edificações", "reforma predial", "obras civis"], ["obras"]),
    "4211": (["pavimentação", "recapeamento asfáltico", "obras viárias"], ["obras"]),
    "4213": (["obras de arte especiais", "pontes e viadutos"], ["obras"]),
    "4221": (["rede de energia elétrica", "iluminação pública"], ["obras"]),
    "4222": (["rede de água e esgoto", "saneamento", "drenagem"], ["obras"]),
    "4292": (["montagem industrial"], ["obras"]),
    "4299": (["obras de infraestrutura", "urbanização"], ["obras"]),
    "4311": (["demolição", "terraplenagem"], ["obras"]),
    "4313": (["terraplenagem", "movimentação de terra"], ["obras"]),
    "4321": (["instalações elétricas", "manutenção elétrica predial"], ["obras", "servicos_comuns"]),
    "4329": (["manutenção predial", "instalação de equipamentos"], ["obras", "servicos_comuns"]),
    "4330": (["pintura predial", "acabamento de obras", "reforma"], ["obras"]),
    "4391": (["fundações", "estaqueamento"], ["obras"]),
    "4399": (["manutenção predial", "impermeabilização", "reforma"], ["obras"]),
    "7111": (["projeto arquitetônico", "arquitetura"], ["servicos_comuns"]),
    "7112": (["projeto de engenharia", "fiscalização de obras", "consultoria de engenharia"], ["servicos_comuns"]),
    "7119": (["topografia", "georreferenciamento", "sondagem"], ["servicos_comuns"]),
    "7120": (["ensaios laboratoriais", "controle tecnológico"], ["servicos_comuns"]),
    # Serviços continuados com mão de obra
    "8111": (["facilities", "apoio administrativo predial", "recepção"], ["servicos_continuados"]),
    "8112": (["condomínio", "administração predial"], ["servicos_continuados"]),
    "8121": (["limpeza predial", "conservação", "limpeza e conservação"], ["servicos_continuados"]),
    "8122": (["dedetização", "controle de pragas", "desratização"], ["servicos_comuns"]),
    "8130": (["jardinagem", "roçada", "manutenção de áreas verdes", "paisagismo"], ["servicos_continuados"]),
    "8011": (["vigilância patrimonial", "segurança armada", "vigilância desarmada"], ["servicos_continuados", "seguranca"]),
    "8012": (["transporte de valores", "escolta armada"], ["seguranca"]),
    "8020": (["monitoramento eletrônico", "CFTV", "alarme"], ["seguranca", "ti"]),
    "7810": (["recrutamento", "seleção de pessoal"], ["servicos_comuns"]),
    "7820": (["mão de obra temporária", "terceirização de mão de obra"], ["servicos_continuados"]),
    "7830": (["terceirização de mão de obra", "apoio administrativo", "postos de trabalho"], ["servicos_continuados"]),
    "8211": (["apoio administrativo", "serviços administrativos"], ["servicos_continuados"]),
    "8219": (["reprografia", "cópias e impressões", "digitalização de documentos"], ["servicos_comuns"]),
    "8220": (["call center", "teleatendimento", "central de atendimento"], ["servicos_continuados"]),
    "8230": (["organização de eventos", "cerimonial", "estrutura para eventos"], ["servicos_comuns"]),
    "8291": (["cobrança", "recuperação de crédito"], ["servicos_comuns"]),
    "8299": (["serviços administrativos", "apoio operacional"], ["servicos_comuns"]),
    "5620": (["refeições", "fornecimento de alimentação", "marmitex", "coffee break"], ["alimentacao", "servicos_continuados"]),
    "5611": (["refeições", "restaurante"], ["alimentacao"]),
    "5612": (["refeições prontas", "alimentação"], ["alimentacao"]),
    # Transporte e veículos
    "4921": (["transporte coletivo", "transporte de passageiros"], ["transporte"]),
    "4922": (["transporte intermunicipal", "fretamento"], ["transporte"]),
    "4923": (["táxi", "transporte por aplicativo"], ["transporte"]),
    "4924": (["transporte escolar"], ["transporte", "educacao"]),
    "4929": (["fretamento", "transporte de passageiros", "locação de ônibus"], ["transporte"]),
    "4930": (["transporte de cargas", "frete", "mudanças"], ["transporte"]),
    "5211": (["armazenagem", "guarda de bens"], ["servicos_comuns"]),
    "5229": (["logística", "remoção de veículos", "guincho"], ["transporte"]),
    "5320": (["entrega de correspondências", "malote", "motofrete"], ["servicos_comuns"]),
    "7711": (["locação de veículos", "locação de frota", "veículos sem motorista"], ["transporte"]),
    "7719": (["locação de máquinas", "locação de equipamentos"], ["fornecimento"]),
    "7732": (["locação de máquinas pesadas", "locação de equipamentos de construção"], ["obras"]),
    "7739": (["locação de equipamentos", "locação de máquinas"], ["fornecimento"]),
    "4520": (["manutenção de veículos", "manutenção de frota", "mecânica automotiva"], ["servicos_comuns", "transporte"]),
    "4530": (["peças automotivas", "autopeças"], ["fornecimento", "transporte"]),
    "4511": (["aquisição de veículos"], ["fornecimento", "transporte"]),
    "4731": (["combustíveis", "gasolina", "óleo diesel", "abastecimento de frota"], ["fornecimento", "transporte"]),
    "4681": (["combustíveis", "óleo diesel", "lubrificantes"], ["fornecimento"]),
    "8622": (["remoção de pacientes", "ambulância"], ["saude", "transporte"]),
    # TI e comunicação
    "6201": (["desenvolvimento de software", "sistema sob medida"], ["ti"]),
    "6202": (["desenvolvimento de software", "customização de sistemas"], ["ti"]),
    "6203": (["licença de software", "software"], ["ti"]),
    "6204": (["consultoria em tecnologia da informação", "suporte técnico de TI"], ["ti"]),
    "6209": (["suporte técnico de TI", "service desk", "manutenção de computadores"], ["ti"]),
    "6311": (["hospedagem", "data center", "computação em nuvem"], ["ti"]),
    "6319": (["portal", "serviços de internet"], ["ti"]),
    "6110": (["telefonia", "link de dados"], ["ti"]),
    "6120": (["telefonia móvel", "linhas móveis"], ["ti"]),
    "6190": (["link de internet", "conectividade", "fibra óptica"], ["ti"]),
    "9511": (["manutenção de computadores", "manutenção de impressoras"], ["ti", "servicos_comuns"]),
    "9512": (["manutenção de equipamentos de comunicação"], ["ti"]),
    "4751": (["equipamentos de informática", "computadores", "suprimentos de informática"], ["fornecimento", "ti"]),
    "4651": (["equipamentos de informática", "computadores", "notebooks"], ["fornecimento", "ti"]),
    "4652": (["componentes eletrônicos", "equipamentos de telecomunicação"], ["fornecimento", "ti"]),
    "2621": (["computadores", "equipamentos de informática"], ["fornecimento", "ti"]),
    "7311": (["publicidade", "agência de propaganda", "comunicação institucional"], ["servicos_comuns"]),
    "7319": (["marketing", "divulgação"], ["servicos_comuns"]),
    "7320": (["pesquisa de opinião", "pesquisa de mercado"], ["servicos_comuns"]),
    "5911": (["produção audiovisual", "vídeo institucional"], ["servicos_comuns"]),
    "1813": (["serviços gráficos", "impressão gráfica", "material gráfico"], ["servicos_comuns", "fornecimento"]),
    "1811": (["impressão", "serviços gráficos"], ["servicos_comuns"]),
    # Saúde
    "8610": (["serviços hospitalares", "gestão hospitalar", "leitos de UTI"], ["saude"]),
    "8621": (["UTI móvel", "atendimento pré-hospitalar"], ["saude"]),
    "8630": (["consultas médicas", "plantão médico", "serviços médicos"], ["saude"]),
    "8640": (["exames laboratoriais", "diagnóstico por imagem", "análises clínicas"], ["saude"]),
    "8650": (["fisioterapia", "serviços de enfermagem", "psicologia"], ["saude"]),
    "8660": (["apoio à gestão de saúde"], ["saude"]),
    "8690": (["serviços de saúde", "atenção à saúde"], ["saude"]),
    "8711": (["instituição de longa permanência", "acolhimento"], ["saude"]),
    "3250": (["materiais médico-hospitalares", "órteses e próteses", "instrumentos cirúrgicos"], ["fornecimento", "saude"]),
    "2121": (["medicamentos"], ["fornecimento", "saude"]),
    "4644": (["medicamentos", "produtos farmacêuticos"], ["fornecimento", "saude"]),
    "4645": (["materiais médico-hospitalares", "insumos hospitalares", "materiais de laboratório"], ["fornecimento", "saude"]),
    "4664": (["equipamentos médico-hospitalares", "equipamentos odontológicos"], ["fornecimento", "saude"]),
    "4771": (["medicamentos", "farmácia"], ["fornecimento", "saude"]),
    "4773": (["artigos médicos e ortopédicos"], ["fornecimento", "saude"]),
    "3812": (["coleta de resíduos de saúde", "resíduos hospitalares"], ["saude", "servicos_comuns"]),
    "7500": (["serviços veterinários"], ["servicos_comuns"]),
    # Educação
    "8511": (["educação infantil", "creche"], ["educacao"]),
    "8512": (["educação infantil", "pré-escola"], ["educacao"]),
    "8513": (["ensino fundamental"], ["educacao"]),
    "8520": (["ensino médio"], ["educacao"]),
    "8531": (["ensino superior"], ["educacao"]),
    "8541": (["educação profissional", "cursos técnicos"], ["educacao"]),
    "8591": (["treinamento", "capacitação"], ["educacao"]),
    "8593": (["ensino de idiomas", "curso de idiomas"], ["educacao"]),
    "8599": (["capacitação", "treinamento", "cursos"], ["educacao"]),
    "8550": (["apoio à educação", "material pedagógico"], ["educacao"]),
    "5811": (["livros", "publicações"], ["fornecimento", "educacao"]),
    "4761": (["material escolar", "livros", "papelaria"], ["fornecimento", "educacao"]),
    # Fornecimento de bens
    "4647": (["material de escritório", "papelaria", "material de expediente"], ["fornecimento"]),
    "4639": (["gêneros alimentícios", "alimentos"], ["fornecimento", "alimentacao"]),
    "4637": (["gêneros alimentícios", "café", "açúcar"], ["fornecimento", "alimentacao"]),
    "4631": (["leite", "laticínios"], ["fornecimento", "alimentacao"]),
    "4632": (["cereais", "gêneros alimentícios"], ["fornecimento", "alimentacao"]),
    "4633": (["hortifrutigranjeiros", "frutas e verduras"], ["fornecimento", "alimentacao"]),
    "4634": (["carnes", "gêneros alimentícios"], ["fornecimento", "alimentacao"]),
    "4635": (["água mineral", "bebidas"], ["fornecimento", "alimentacao"]),
    "4711": (["gêneros alimentícios", "cesta básica"], ["fornecimento", "alimentacao"]),
    "4712": (["gêneros alimentícios"], ["fornecimento", "alimentacao"]),
    "1091": (["pães", "panificação"], ["fornecimento", "alimentacao"]),
    "4641": (["tecidos", "cama mesa e banho", "enxoval"], ["fornecimento"]),
    "4642": (["uniformes", "vestuário", "fardamento"], ["fornecimento"]),
    "4643": (["calçados", "botinas"], ["fornecimento"]),
    "1412": (["uniformes", "confecção de uniformes", "fardamento"], ["fornecimento"]),
    "1413": (["uniformes profissionais", "vestuário"], ["fornecimento"]),
    "3292": (["equipamentos de proteção individual", "EPI"], ["fornecimento"]),
    "4744": (["material de construção", "materiais elétricos", "materiais hidráulicos"], ["fornecimento", "obras"]),
    "4672": (["ferragens", "ferramentas"], ["fornecimento"]),
    "4673": (["material elétrico"], ["fornecimento"]),
    "4679": (["material de construção"], ["fornecimento", "obras"]),
    "4684": (["produtos químicos"], ["fornecimento"]),
    "4686": (["papel", "embalagens"], ["fornecimento"]),
    "4687": (["resíduos recicláveis", "sucata"], ["fornecimento"]),
    "2061": (["produtos de limpeza", "saneantes"], ["fornecimento"]),
    "2062": (["produtos de limpeza", "saneantes", "material de higiene"], ["fornecimento"]),
    "4772": (["produtos de higiene", "cosméticos"], ["fornecimento"]),
    "3101": (["mobiliário", "móveis para escritório", "cadeiras"], ["fornecimento"]),
    "3102": (["mobiliário", "móveis"], ["fornecimento"]),
    "3103": (["colchões"], ["fornecimento"]),
    "4754": (["mobiliário", "móveis", "eletrodomésticos"], ["fornecimento"]),
    "4753": (["eletrodomésticos", "equipamentos de áudio e vídeo"], ["fornecimento"]),
    "4661": (["máquinas agrícolas", "tratores"], ["fornecimento"]),
    "4662": (["máquinas e equipamentos", "equipamentos industriais"], ["fornecimento"]),
    "4663": (["máquinas e equipamentos industriais"], ["fornecimento"]),
    "4623": (["ração animal", "insumos agropecuários"], ["fornecimento"]),
    "4683": (["fertilizantes", "defensivos agrícolas", "insumos agrícolas"], ["fornecimento"]),
    "2330": (["artefatos de concreto", "blocos de concreto", "tubos de concreto"], ["fornecimento", "obras"]),
    "2391": (["pedra britada", "brita"], ["fornecimento", "obras"]),
    "0810": (["areia", "pedra britada", "agregados"], ["fornecimento", "obras"]),
    "1921": (["combustíveis", "derivados de petróleo"], ["fornecimento"]),
    "2710": (["geradores", "transformadores"], ["fornecimento"]),
    "2740": (["luminárias", "iluminação LED"], ["fornecimento"]),
    "2751": (["eletrodomésticos"], ["fornecimento"]),
    "2823": (["ar condicionado", "climatização"], ["fornecimento"]),
    # Meio ambiente e resíduos
    "3811": (["coleta de lixo", "coleta de resíduos sólidos", "limpeza urbana"], ["servicos_continuados"]),
    "3821": (["tratamento de resíduos", "aterro sanitário"], ["servicos_comuns"]),
    "3822": (["resíduos perigosos", "destinação de resíduos"], ["servicos_comuns"]),
    "3831": (["reciclagem"], ["servicos_comuns"]),
    "3900": (["descontaminação", "remediação ambiental"], ["servicos_comuns"]),
    "3600": (["abastecimento de água", "caminhão pipa"], ["servicos_comuns"]),
    "3701": (["esgotamento sanitário", "limpeza de fossas"], ["servicos_comuns"]),
    "3702": (["limpeza de fossas", "desentupimento"], ["servicos_comuns"]),
    "8129": (["limpeza urbana", "varrição", "higienização", "limpeza hospitalar"], ["servicos_continuados"]),
    # Consultoria e serviços profissionais
    "6911": (["assessoria jurídica", "serviços advocatícios"], ["servicos_comuns"]),
    "6912": (["cartório", "serviços notariais"], ["servicos_comuns"]),
    "6920": (["assessoria contábil", "auditoria", "consultoria tributária"], ["servicos_comuns"]),
    "7020": (["consultoria em gestão", "assessoria técnica", "consultoria"], ["servicos_comuns"]),
    "7210": (["pesquisa e desenvolvimento", "estudos técnicos"], ["servicos_comuns"]),
    "7410": (["design", "identidade visual"], ["servicos_comuns"]),
    "7420": (["fotografia", "cobertura fotográfica"], ["servicos_comuns"]),
    "7490": (["assessoria técnica", "tradução", "consultoria"], ["servicos_comuns"]),
    "6619": (["correspondente bancário", "gestão de pagamentos"], ["servicos_comuns"]),
    "6622": (["seguros", "corretagem de seguros"], ["servicos_comuns"]),
    "6512": (["seguro de veículos", "seguro patrimonial"], ["servicos_comuns"]),
    "7911": (["agência de viagens", "passagens aéreas", "reserva de hospedagem"], ["servicos_comuns"]),
    "5510": (["hospedagem", "hotel"], ["servicos_comuns"]),
    "9311": (["gestão de instalações esportivas"], ["servicos_comuns"]),
    "9329": (["eventos", "recreação"], ["servicos_comuns"]),
    "9001": (["apresentações artísticas", "shows", "eventos culturais"], ["servicos_comuns"]),
    "9003": (["sonorização", "iluminação cênica", "palco"], ["servicos_comuns"]),
    "9601": (["lavanderia", "lavagem de roupas hospitalares"], ["servicos_continuados", "saude"]),
    "9603": (["serviços funerários", "urnas funerárias"], ["servicos_comuns"]),
    "8424": (["segurança pública"], ["seguranca"]),
    "3314": (["manutenção de máquinas e equipamentos", "manutenção de ar condicionado", "manutenção de elevadores"], ["servicos_comuns"]),
    "3313": (["manutenção de equipamentos eletrônicos"], ["servicos_comuns"]),
    "3312": (["manutenção de equipamentos médico-hospitalares", "calibração"], ["servicos_comuns", "saude"]),
    "3319": (["manutenção de equipamentos"], ["servicos_comuns"]),
    "3321": (["instalação de máquinas e equipamentos"], ["servicos_comuns"]),
    "4322": (["ar condicionado", "climatização", "instalações hidráulicas"], ["obras", "servicos_comuns"]),
}

# Divisões (2 dígitos): usada quando a classe não está no mapa acima
POR_DIVISAO = {
    "01": (["insumos agrícolas", "agricultura"], ["fornecimento"]), "02": (["mudas", "reflorestamento"], ["fornecimento"]),
    "03": (["pescados"], ["fornecimento", "alimentacao"]), "08": (["agregados", "areia", "pedra britada"], ["fornecimento", "obras"]),
    "10": (["gêneros alimentícios", "alimentos"], ["fornecimento", "alimentacao"]), "11": (["bebidas", "água mineral"], ["fornecimento", "alimentacao"]),
    "13": (["tecidos", "artigos têxteis"], ["fornecimento"]), "14": (["uniformes", "vestuário"], ["fornecimento"]),
    "15": (["calçados", "artigos de couro"], ["fornecimento"]), "16": (["madeira", "artefatos de madeira"], ["fornecimento"]),
    "17": (["papel", "embalagens"], ["fornecimento"]), "18": (["serviços gráficos", "impressão"], ["servicos_comuns"]),
    "20": (["produtos químicos", "saneantes"], ["fornecimento"]), "21": (["medicamentos"], ["fornecimento", "saude"]),
    "22": (["artefatos de borracha", "artefatos de plástico"], ["fornecimento"]), "23": (["material de construção"], ["fornecimento", "obras"]),
    "24": (["produtos siderúrgicos", "aço"], ["fornecimento"]), "25": (["estruturas metálicas", "artefatos de metal"], ["fornecimento"]),
    "26": (["equipamentos eletrônicos", "equipamentos de informática"], ["fornecimento", "ti"]),
    "27": (["materiais elétricos", "equipamentos elétricos"], ["fornecimento"]), "28": (["máquinas e equipamentos"], ["fornecimento"]),
    "29": (["veículos", "carrocerias"], ["fornecimento", "transporte"]), "30": (["equipamentos de transporte"], ["fornecimento", "transporte"]),
    "31": (["mobiliário", "móveis"], ["fornecimento"]), "32": (["artigos diversos"], ["fornecimento"]),
    "33": (["manutenção de máquinas e equipamentos"], ["servicos_comuns"]), "35": (["energia elétrica", "geração de energia"], ["servicos_comuns"]),
    "36": (["abastecimento de água"], ["servicos_comuns"]), "37": (["esgotamento sanitário"], ["servicos_comuns"]),
    "38": (["coleta de resíduos", "tratamento de resíduos"], ["servicos_comuns"]), "39": (["remediação ambiental"], ["servicos_comuns"]),
    "41": (["construção de edificações", "obras civis"], ["obras"]), "42": (["obras de infraestrutura", "pavimentação"], ["obras"]),
    "43": (["serviços de engenharia", "reforma", "instalações"], ["obras"]),
    "45": (["veículos", "manutenção de veículos", "peças automotivas"], ["fornecimento", "transporte"]),
    "46": (["aquisição", "fornecimento de materiais"], ["fornecimento"]), "47": (["aquisição", "fornecimento de materiais"], ["fornecimento"]),
    "49": (["transporte", "fretamento"], ["transporte"]), "50": (["transporte aquaviário"], ["transporte"]),
    "51": (["transporte aéreo", "fretamento de aeronaves"], ["transporte"]), "52": (["armazenagem", "logística"], ["servicos_comuns"]),
    "53": (["correspondências", "entregas"], ["servicos_comuns"]), "55": (["hospedagem"], ["servicos_comuns"]),
    "56": (["alimentação", "refeições"], ["alimentacao"]), "58": (["livros", "publicações"], ["fornecimento"]),
    "59": (["produção audiovisual"], ["servicos_comuns"]), "60": (["radiodifusão", "publicidade legal"], ["servicos_comuns"]),
    "61": (["telecomunicações", "link de internet"], ["ti"]), "62": (["tecnologia da informação", "software"], ["ti"]),
    "63": (["serviços de informação", "hospedagem de sistemas"], ["ti"]), "64": (["serviços financeiros"], ["servicos_comuns"]),
    "65": (["seguros"], ["servicos_comuns"]), "66": (["serviços financeiros"], ["servicos_comuns"]),
    "68": (["locação de imóveis", "administração de imóveis"], ["servicos_comuns"]),
    "69": (["assessoria jurídica", "assessoria contábil"], ["servicos_comuns"]), "70": (["consultoria em gestão"], ["servicos_comuns"]),
    "71": (["engenharia consultiva", "projetos de engenharia"], ["servicos_comuns"]), "72": (["pesquisa e desenvolvimento"], ["servicos_comuns"]),
    "73": (["publicidade", "comunicação"], ["servicos_comuns"]), "74": (["serviços técnicos especializados"], ["servicos_comuns"]),
    "75": (["serviços veterinários"], ["servicos_comuns"]), "77": (["locação de equipamentos", "locação de veículos"], ["fornecimento"]),
    "78": (["terceirização de mão de obra"], ["servicos_continuados"]), "79": (["agência de viagens", "passagens"], ["servicos_comuns"]),
    "80": (["vigilância", "segurança"], ["servicos_continuados", "seguranca"]), "81": (["limpeza", "conservação", "facilities"], ["servicos_continuados"]),
    "82": (["serviços administrativos", "apoio administrativo"], ["servicos_comuns"]), "84": (["administração pública"], ["servicos_comuns"]),
    "85": (["educação", "capacitação"], ["educacao"]), "86": (["serviços de saúde"], ["saude"]), "87": (["assistência social", "acolhimento"], ["saude"]),
    "88": (["assistência social"], ["servicos_comuns"]), "90": (["eventos culturais", "apresentações artísticas"], ["servicos_comuns"]),
    "91": (["patrimônio cultural", "museus"], ["servicos_comuns"]), "93": (["esportes", "recreação", "eventos"], ["servicos_comuns"]),
    "94": (["associação"], ["outro"]), "95": (["manutenção de equipamentos"], ["servicos_comuns"]),
    "96": (["lavanderia", "serviços pessoais"], ["servicos_comuns"]),
}

_PREFIXOS = re.compile(
    r"^(comércio (atacadista|varejista) (especializado )?(de|em)|fabricação de|serviços? (combinados )?de|atividades? de|"
    r"outras atividades de|outros serviços de|obras de|instalação de|manutenção e reparação de|reparação e manutenção de|"
    r"produção de|confecção de|representantes comerciais e agentes do comércio de|cultivo de|criação de|"
    r"aluguel de|locação de|preparação de|construção de|edição de|impressão de|incorporação de)\s+", re.I)
_CORTE = re.compile(r"\b(exceto|não especificad[oa]s?|n[ãa]o especificad|anteriormente|associad[oa]s? a|de uso)\b.*$", re.I)


def formatar(codigo):
    """'4120400' -> '4120-4/00' (com zero à esquerda restaurado)."""
    c = re.sub(r"\D", "", str(codigo or "")).zfill(7)[-7:]
    return f"{c[:4]}-{c[4]}/{c[5:]}"


def _do_texto(descricao):
    """Fallback: termos curtos extraídos da descrição oficial do CNAE."""
    t = _CORTE.sub("", (descricao or "").strip())
    t = _PREFIXOS.sub("", t).strip(" ,;-")
    partes = [p.strip(" ,;-").lower() for p in re.split(r",|;|\be\b", t) if p.strip(" ,;-")]
    termos = []
    for p in partes:
        p = re.sub(r"^(de|do|da|dos|das|em|para|e)\s+", "", p)
        if 3 <= len(p) and len(p.split()) <= 4 and not re.match(r"(outr[oa]s?|diversos|demais|em geral)\b", p):
            termos.append(p)
    return termos[:3]


def _chave(t):
    return unicodedata.normalize("NFKD", t.lower()).encode("ascii", "ignore").decode().strip()


def sugerir(cnaes, limite=12):
    """cnaes: [{'codigo','descricao','principal'}] -> palavras-chave (ordenadas) e segmentos."""
    ordenados = sorted(cnaes or [], key=lambda c: not c.get("principal"))
    termos, vistos, segmentos = [], set(), []
    for c in ordenados:
        cod = re.sub(r"\D", "", str(c.get("codigo") or "")).zfill(7)
        if cod == "0000000":
            continue
        achado = POR_CLASSE.get(cod[:4]) or POR_DIVISAO.get(cod[:2])
        lista, segs = achado if achado else ([], [])
        # divisões genéricas de comércio (46/47): o texto do CNAE diz mais que o termo genérico
        if not POR_CLASSE.get(cod[:4]) and cod[:2] in ("46", "47", "32", "74", "82", "96"):
            lista = _do_texto(c.get("descricao"))  # termos genéricos ("aquisição") poluem o radar
        elif not lista:
            lista = _do_texto(c.get("descricao"))
        for t in (lista if c.get("principal") else lista[:2]):  # secundários: 2 termos cada, para variar
            k = _chave(t)
            if k and k not in vistos:
                vistos.add(k)
                termos.append(t)
        for s in segs:
            if s not in segmentos:
                segmentos.append(s)
    return {"palavras_chave": termos[:limite], "segmentos": segmentos}


def texto_cnaes(cnaes):
    """Um CNAE por linha, principal primeiro — formato salvo no campo 'cnaes' da empresa."""
    ordenados = sorted(cnaes or [], key=lambda c: not c.get("principal"))
    return "\n".join(f"{formatar(c.get('codigo'))} {c.get('descricao') or ''}{' (principal)' if c.get('principal') else ''}".strip()
                     for c in ordenados if re.sub(r"\D", "", str(c.get("codigo") or "")).strip("0"))
