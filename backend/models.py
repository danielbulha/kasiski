"""Modelos do banco. Toda informação de cliente pertence a uma Conta (multi-tenant)."""
from datetime import datetime, date
from extensions import db


def _iso(v):
    if v is None:
        return None
    return v.isoformat()


class Conta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200), nullable=False)
    plano = db.Column(db.String(30), default="trial")  # trial, essencial, profissional, avancado, consultor, suspenso
    trial_fim = db.Column(db.DateTime)
    marca_relatorio = db.Column(db.String(200))  # plano Consultor: nome do escritório nos relatórios
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    # Cobrança (Mercado Pago)
    ciclo = db.Column(db.String(10))              # mensal, anual
    metodo_pagamento = db.Column(db.String(20))   # recorrente (cartão, renova sozinho) ou avulso (Pix/boleto/cartão)
    assinatura_status = db.Column(db.String(20))  # pendente, ativa, pausada, cancelada, inadimplente
    mp_assinatura_id = db.Column(db.String(60), index=True)
    pago_ate = db.Column(db.DateTime)             # acesso pago garantido até esta data
    assinante_desde = db.Column(db.DateTime)
    cancelado_em = db.Column(db.DateTime)

    # CRM / funil
    telefone = db.Column(db.String(30))
    notas_crm = db.Column(db.Text)
    etiqueta_crm = db.Column(db.String(30))       # livre: quente, negociando, sem_resposta...
    origem = db.Column(db.String(80))             # utm_source ou site de origem
    campanha = db.Column(db.String(120))          # utm_campaign
    visitante_id = db.Column(db.String(40), index=True)

    # Pacotes extras de contratos (mensal)
    pacotes_contratos = db.Column(db.Integer, default=0)
    pacotes_ate = db.Column(db.DateTime)
    pacotes_status = db.Column(db.String(20))   # pendente, ativa, cancelada, inadimplente
    pacotes_metodo = db.Column(db.String(20))   # recorrente, avulso
    pacotes_mp_assinatura_id = db.Column(db.String(60), index=True)
    ultimo_aviso_contratos = db.Column(db.Date)

    def to_dict(self):
        return {"id": self.id, "nome": self.nome, "plano": self.plano, "trial_fim": _iso(self.trial_fim),
                "marca_relatorio": self.marca_relatorio, "criado_em": _iso(self.criado_em),
                "ciclo": self.ciclo, "metodo_pagamento": self.metodo_pagamento,
                "assinatura_status": self.assinatura_status, "pago_ate": _iso(self.pago_ate),
                "assinante_desde": _iso(self.assinante_desde), "cancelado_em": _iso(self.cancelado_em)}


class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    conta_id = db.Column(db.Integer, db.ForeignKey("conta.id"), nullable=False, index=True)
    nome = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(200), unique=True, nullable=False, index=True)
    senha_hash = db.Column(db.String(300), nullable=False)
    modo_guiado = db.Column(db.Boolean, default=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    ultimo_acesso = db.Column(db.DateTime)
    # Segurança do acesso. email_verificado = None em contas anteriores à verificação (tratadas como
    # confirmadas); False nos cadastros novos até digitarem o código recebido por e-mail.
    email_verificado = db.Column(db.Boolean)
    falhas_login = db.Column(db.Integer, default=0)
    bloqueado_ate = db.Column(db.DateTime)
    conta = db.relationship("Conta")

    @property
    def verificado(self):
        return self.email_verificado is not False

    def to_dict(self, admin=False):
        return {"id": self.id, "nome": self.nome, "email": self.email, "modo_guiado": self.modo_guiado, "admin": admin}


class TrialCnpj(db.Model):
    """Garante um único teste grátis por CNPJ."""
    id = db.Column(db.Integer, primary_key=True)
    cnpj = db.Column(db.String(14), unique=True, nullable=False)
    conta_id = db.Column(db.Integer, nullable=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)


class Empresa(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    conta_id = db.Column(db.Integer, db.ForeignKey("conta.id"), nullable=False, index=True)
    razao_social = db.Column(db.String(250), nullable=False)
    cnpj = db.Column(db.String(14), nullable=False)
    porte = db.Column(db.String(20), default="demais")  # ME, EPP, demais
    cnaes = db.Column(db.Text, default="")
    segmentos = db.Column(db.String(200), default="")  # obras, servicos_comuns, servicos_continuados, fornecimento, saude, educacao, ti, alimentacao, transporte, outro
    palavras_chave = db.Column(db.Text, default="")  # segmentos de interesse, separados por vírgula
    ufs = db.Column(db.String(200), default="")  # ex.: SP,MG
    valor_min = db.Column(db.Float)
    valor_max = db.Column(db.Float)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {"id": self.id, "razao_social": self.razao_social, "cnpj": self.cnpj, "porte": self.porte,
                "cnaes": self.cnaes, "segmentos": self.segmentos, "palavras_chave": self.palavras_chave, "ufs": self.ufs,
                "valor_min": self.valor_min, "valor_max": self.valor_max}


class Documento(db.Model):
    """Cofre de habilitação."""
    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresa.id"), nullable=False, index=True)
    categoria = db.Column(db.String(40))  # juridica, fiscal, trabalhista, economica, tecnica, declaracao, outro
    tipo = db.Column(db.String(120), nullable=False)
    descricao = db.Column(db.Text, default="")
    validade = db.Column(db.Date)
    arquivo = db.Column(db.String(300))
    nome_arquivo = db.Column(db.String(250))
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    def situacao(self, referencia=None):
        if not self.validade:
            return "sem_validade"
        ref = referencia or date.today()
        if self.validade < ref:
            return "vencido"
        if (self.validade - ref).days <= 30:
            return "vencendo"
        return "valido"

    def to_dict(self):
        return {"id": self.id, "empresa_id": self.empresa_id, "categoria": self.categoria, "tipo": self.tipo,
                "descricao": self.descricao, "validade": _iso(self.validade), "situacao": self.situacao(),
                "nome_arquivo": self.nome_arquivo, "tem_arquivo": bool(self.arquivo), "criado_em": _iso(self.criado_em)}


class RadarItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresa.id"), nullable=False, index=True)
    numero_controle = db.Column(db.String(80), nullable=False)
    dados = db.Column(db.JSON)
    nota = db.Column(db.Integer)
    motivo = db.Column(db.Text)
    status = db.Column(db.String(20), default="novo")  # novo, descartado, acompanhando
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint("empresa_id", "numero_controle"),)

    def to_dict(self):
        return {"id": self.id, "numero_controle": self.numero_controle, "dados": self.dados or {},
                "nota": self.nota, "motivo": self.motivo, "status": self.status, "criado_em": _iso(self.criado_em)}


class Edital(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresa.id"), nullable=False, index=True)
    origem = db.Column(db.String(20), default="upload")  # pncp, upload
    numero_controle = db.Column(db.String(80))
    numero = db.Column(db.String(80))
    orgao = db.Column(db.String(300))
    objeto = db.Column(db.Text)
    modalidade = db.Column(db.String(80))
    tipo_objeto = db.Column(db.String(30))  # obra, servico_engenharia, servico_comum, servico_continuado, fornecimento, fornecimento_continuado, outro
    segmento = db.Column(db.String(30))  # saude, educacao, ti, alimentacao, transporte, limpeza, seguranca, obras, outro
    uf = db.Column(db.String(2))
    municipio = db.Column(db.String(120))
    valor_estimado = db.Column(db.Float)
    data_abertura = db.Column(db.DateTime)
    portal_disputa = db.Column(db.String(300))
    link = db.Column(db.String(500))
    arquivo = db.Column(db.String(300))
    nome_arquivo = db.Column(db.String(250))
    arquivo_url = db.Column(db.String(600))  # endereço original do documento no PNCP
    texto = db.Column(db.Text)
    status = db.Column(db.String(20), default="acompanhando")  # acompanhando, participando, ganho, perdido, descartado
    resultado_em = db.Column(db.Date)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self, completo=False):
        d = {"id": self.id, "empresa_id": self.empresa_id, "origem": self.origem, "numero_controle": self.numero_controle,
             "numero": self.numero, "orgao": self.orgao, "objeto": self.objeto, "modalidade": self.modalidade,
             "tipo_objeto": self.tipo_objeto, "segmento": self.segmento,
             "uf": self.uf, "municipio": self.municipio, "valor_estimado": self.valor_estimado,
             "data_abertura": _iso(self.data_abertura), "portal_disputa": self.portal_disputa, "link": self.link,
             "nome_arquivo": self.nome_arquivo, "tem_texto": bool(self.texto), "status": self.status,
             "tem_documento": bool(self.arquivo or self.numero_controle),
             "resultado_em": _iso(self.resultado_em), "criado_em": _iso(self.criado_em)}
        if completo:
            d["caracteres_texto"] = len(self.texto or "")
        return d


class Analise(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    edital_id = db.Column(db.Integer, db.ForeignKey("edital.id"), nullable=False, index=True)
    status = db.Column(db.String(20), default="concluida")  # processando, concluida, erro
    etapa = db.Column(db.String(40))       # andamento mostrado na tela enquanto processa
    erro = db.Column(db.Text)
    resultado = db.Column(db.JSON)
    modelos = db.Column(db.JSON)
    demonstracao = db.Column(db.Boolean, default=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    concluido_em = db.Column(db.DateTime)

    def to_dict(self):
        return {"id": self.id, "edital_id": self.edital_id, "status": self.status, "etapa": self.etapa,
                "erro": self.erro, "resultado": self.resultado or {},
                "modelos": self.modelos or {}, "demonstracao": self.demonstracao, "criado_em": _iso(self.criado_em),
                "concluido_em": _iso(self.concluido_em)}


class Peca(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresa.id"), nullable=False, index=True)
    edital_id = db.Column(db.Integer, db.ForeignKey("edital.id"))
    contrato_id = db.Column(db.Integer, db.ForeignKey("contrato.id"))
    tipo = db.Column(db.String(40), nullable=False)
    titulo = db.Column(db.String(300))
    conteudo = db.Column(db.Text)
    status = db.Column(db.String(30), default="rascunho")  # rascunho, revisao_solicitada, revisada
    demonstracao = db.Column(db.Boolean, default=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self, completo=True):
        d = {"id": self.id, "empresa_id": self.empresa_id, "edital_id": self.edital_id, "contrato_id": self.contrato_id,
             "tipo": self.tipo, "titulo": self.titulo, "status": self.status, "demonstracao": self.demonstracao,
             "criado_em": _iso(self.criado_em), "atualizado_em": _iso(self.atualizado_em)}
        if completo:
            d["conteudo"] = self.conteudo
        return d


class Revisao(db.Model):
    """Serviço de advogado: elaboração de uma peça do zero ou revisão de uma minuta gerada pela IA."""
    id = db.Column(db.Integer, primary_key=True)
    peca_id = db.Column(db.Integer, db.ForeignKey("peca.id"), nullable=False)
    conta_id = db.Column(db.Integer, db.ForeignKey("conta.id"), nullable=False, index=True)
    # aguardando_pagamento, pendente (pago, na fila), em_andamento, concluida, cancelada
    status = db.Column(db.String(24), default="pendente")
    servico = db.Column(db.String(20), default="revisao")  # elaboracao, revisao
    pago_em = db.Column(db.DateTime)
    valor = db.Column(db.Float)
    prazo_desejado = db.Column(db.Date)
    observacoes = db.Column(db.Text)
    parecer = db.Column(db.Text)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    peca = db.relationship("Peca")

    def to_dict(self):
        return {"id": self.id, "peca_id": self.peca_id, "status": self.status, "valor": self.valor,
                "servico": self.servico or "revisao", "pago_em": _iso(self.pago_em),
                "prazo_desejado": _iso(self.prazo_desejado), "observacoes": self.observacoes, "parecer": self.parecer,
                "criado_em": _iso(self.criado_em), "peca_titulo": self.peca.titulo if self.peca else None,
                "peca_tipo": self.peca.tipo if self.peca else None}


class Prazo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresa.id"), nullable=False, index=True)
    edital_id = db.Column(db.Integer, db.ForeignKey("edital.id"))
    contrato_id = db.Column(db.Integer, db.ForeignKey("contrato.id"))
    titulo = db.Column(db.String(300), nullable=False)
    data = db.Column(db.DateTime, nullable=False)
    tipo = db.Column(db.String(40), default="manual")
    fundamento = db.Column(db.String(300))
    concluido = db.Column(db.Boolean, default=False)
    automatico = db.Column(db.Boolean, default=False)

    def to_dict(self):
        return {"id": self.id, "empresa_id": self.empresa_id, "edital_id": self.edital_id, "contrato_id": self.contrato_id,
                "titulo": self.titulo, "data": _iso(self.data), "tipo": self.tipo, "fundamento": self.fundamento,
                "concluido": self.concluido, "automatico": self.automatico}


class Concorrente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    conta_id = db.Column(db.Integer, db.ForeignKey("conta.id"), nullable=False, index=True)
    cnpj = db.Column(db.String(14), nullable=False)
    razao_social = db.Column(db.String(300))
    dossie = db.Column(db.JSON)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow)
    # Dossiê completo: perfil consolidado pela IA a partir de fontes públicas, acervo e análises anteriores
    perfil = db.Column(db.JSON)
    perfil_em = db.Column(db.DateTime)
    perfil_status = db.Column(db.String(20))   # atualizando, pronto, desatualizado, erro
    perfil_etapa = db.Column(db.String(120))
    perfil_erro = db.Column(db.Text)
    __table_args__ = (db.UniqueConstraint("conta_id", "cnpj"),)

    def to_dict(self):
        return {"id": self.id, "cnpj": self.cnpj, "razao_social": self.razao_social, "dossie": self.dossie or {},
                "atualizado_em": _iso(self.atualizado_em), "perfil": self.perfil or {}, "perfil_em": _iso(self.perfil_em),
                "perfil_status": self.perfil_status, "perfil_etapa": self.perfil_etapa, "perfil_erro": self.perfil_erro}


class DocumentoConcorrente(db.Model):
    """Acervo do concorrente: atas, decisões, habilitações, balanços, atestados de outros certames."""
    id = db.Column(db.Integer, primary_key=True)
    concorrente_id = db.Column(db.Integer, db.ForeignKey("concorrente.id"), nullable=False, index=True)
    conta_id = db.Column(db.Integer, nullable=False, index=True)
    origem = db.Column(db.String(20), default="upload")  # upload, pncp
    tipo = db.Column(db.String(30), default="outro")     # ata, decisao, habilitacao, proposta, atestado, balanco, certidao, outro
    titulo = db.Column(db.String(300))
    orgao = db.Column(db.String(300))
    certame = db.Column(db.String(200))
    data_documento = db.Column(db.Date)
    arquivo = db.Column(db.String(300))
    nome_arquivo = db.Column(db.String(250))
    fonte_url = db.Column(db.String(600), index=True)
    texto = db.Column(db.Text)
    extracao = db.Column(db.JSON)
    status = db.Column(db.String(20), default="pendente")  # pendente, lido, sem_mencao, erro
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {"id": self.id, "concorrente_id": self.concorrente_id, "origem": self.origem, "tipo": self.tipo,
                "titulo": self.titulo, "orgao": self.orgao, "certame": self.certame,
                "data_documento": _iso(self.data_documento), "nome_arquivo": self.nome_arquivo,
                "fonte_url": self.fonte_url, "tem_arquivo": bool(self.arquivo), "extracao": self.extracao or {},
                "status": self.status, "criado_em": _iso(self.criado_em)}


class AnaliseConcorrente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    edital_id = db.Column(db.Integer, db.ForeignKey("edital.id"), nullable=False, index=True)
    concorrente_id = db.Column(db.Integer, db.ForeignKey("concorrente.id"), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)  # habilitacao, proposta
    nome_arquivo = db.Column(db.String(250))
    resultado = db.Column(db.JSON)
    modelos = db.Column(db.JSON)
    demonstracao = db.Column(db.Boolean, default=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    concorrente = db.relationship("Concorrente")

    def to_dict(self):
        return {"id": self.id, "edital_id": self.edital_id, "concorrente_id": self.concorrente_id, "tipo": self.tipo,
                "nome_arquivo": self.nome_arquivo, "resultado": self.resultado or {}, "modelos": self.modelos or {},
                "demonstracao": self.demonstracao, "criado_em": _iso(self.criado_em),
                "concorrente": {"cnpj": self.concorrente.cnpj, "razao_social": self.concorrente.razao_social}
                if self.concorrente else None}


class PesquisaPreco(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresa.id"), nullable=False, index=True)
    descricao = db.Column(db.String(300), nullable=False)
    codigo_catalogo = db.Column(db.String(30))
    tipo = db.Column(db.String(20), default="material")
    uf = db.Column(db.String(2))
    amostras = db.Column(db.JSON)
    estatisticas = db.Column(db.JSON)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {"id": self.id, "descricao": self.descricao, "codigo_catalogo": self.codigo_catalogo, "tipo": self.tipo,
                "uf": self.uf, "amostras": self.amostras or [], "estatisticas": self.estatisticas or {},
                "criado_em": _iso(self.criado_em)}


class Contrato(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresa.id"), nullable=False, index=True)
    edital_id = db.Column(db.Integer, db.ForeignKey("edital.id"))
    numero = db.Column(db.String(80))
    orgao = db.Column(db.String(300))
    objeto = db.Column(db.Text)
    valor = db.Column(db.Float)
    inicio = db.Column(db.Date)
    fim = db.Column(db.Date)
    data_base_reajuste = db.Column(db.Date)
    indice_reajuste = db.Column(db.String(60))
    garantia_validade = db.Column(db.Date)
    observacoes = db.Column(db.Text)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    # Leitura do PDF pela IA e gestão
    arquivo = db.Column(db.String(300))
    nome_arquivo = db.Column(db.String(250))
    texto = db.Column(db.Text)
    leitura_status = db.Column(db.String(20))   # lendo, concluida, erro
    leitura_erro = db.Column(db.Text)
    dados_ia = db.Column(db.JSON)               # tudo o que a IA extraiu (garantia, medição, faturamento...)
    obrigacoes = db.Column(db.JSON)             # rotinas de gestão [{descricao, periodicidade, dia, ...}]
    pagamentos = db.relationship("Pagamento", cascade="all, delete-orphan", order_by="Pagamento.vencimento")

    def to_dict(self, com_pagamentos=False):
        d = {"id": self.id, "empresa_id": self.empresa_id, "edital_id": self.edital_id, "numero": self.numero,
             "orgao": self.orgao, "objeto": self.objeto, "valor": self.valor, "inicio": _iso(self.inicio),
             "fim": _iso(self.fim), "data_base_reajuste": _iso(self.data_base_reajuste),
             "indice_reajuste": self.indice_reajuste, "garantia_validade": _iso(self.garantia_validade),
             "observacoes": self.observacoes, "nome_arquivo": self.nome_arquivo, "tem_arquivo": bool(self.arquivo),
             "leitura_status": self.leitura_status, "leitura_erro": self.leitura_erro,
             "dados_ia": self.dados_ia or {}, "obrigacoes": self.obrigacoes or []}
        if com_pagamentos:
            d["pagamentos"] = [p.to_dict() for p in self.pagamentos]
        return d


class Pagamento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    contrato_id = db.Column(db.Integer, db.ForeignKey("contrato.id"), nullable=False, index=True)
    referencia = db.Column(db.String(120))
    nota_fiscal = db.Column(db.String(60))
    valor = db.Column(db.Float)
    vencimento = db.Column(db.Date)
    pago_em = db.Column(db.Date)

    def situacao(self):
        if self.pago_em:
            return "pago"
        if self.vencimento and self.vencimento < date.today():
            return "atrasado"
        return "a_receber"

    def to_dict(self):
        dias = None
        if self.situacao() == "atrasado":
            dias = (date.today() - self.vencimento).days
        return {"id": self.id, "contrato_id": self.contrato_id, "referencia": self.referencia,
                "nota_fiscal": self.nota_fiscal, "valor": self.valor, "vencimento": _iso(self.vencimento),
                "pago_em": _iso(self.pago_em), "situacao": self.situacao(), "dias_atraso": dias}


class UsoIA(db.Model):
    """Registro de consumo: controla limites do plano e custo real das APIs."""
    id = db.Column(db.Integer, primary_key=True)
    conta_id = db.Column(db.Integer, db.ForeignKey("conta.id"), nullable=False, index=True)
    recurso = db.Column(db.String(30))  # analises, concorrentes, pecas, radar, precos
    cobravel = db.Column(db.Boolean, default=False)  # conta para o limite do plano
    modelo = db.Column(db.String(80))
    tokens_entrada = db.Column(db.Integer, default=0)
    tokens_saida = db.Column(db.Integer, default=0)
    custo_usd = db.Column(db.Float, default=0)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, index=True)


class Cobranca(db.Model):
    """Cada pagamento recebido (ou tentado). É a base do controle de receitas.
    Origem: mercadopago (webhook) ou manual (lançado pelo administrador)."""
    id = db.Column(db.Integer, primary_key=True)
    conta_id = db.Column(db.Integer, db.ForeignKey("conta.id"), index=True)
    origem = db.Column(db.String(20), default="mercadopago")  # mercadopago, manual
    tipo = db.Column(db.String(20), default="assinatura")     # assinatura, servico, outro
    mp_pagamento_id = db.Column(db.String(60), unique=True)
    mp_assinatura_id = db.Column(db.String(60), index=True)
    plano = db.Column(db.String(30))
    ciclo = db.Column(db.String(10))
    meio = db.Column(db.String(30))          # pix, cartao, boleto, outro
    valor = db.Column(db.Float, default=0)
    valor_liquido = db.Column(db.Float)      # após a tarifa do Mercado Pago, quando informado
    status = db.Column(db.String(20))        # aprovado, pendente, recusado, estornado, cancelado
    aplicado = db.Column(db.Boolean, default=False)  # já estendeu o acesso da conta (evita estender duas vezes)
    descricao = db.Column(db.String(300))
    pago_em = db.Column(db.DateTime, index=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {"id": self.id, "conta_id": self.conta_id, "origem": self.origem, "tipo": self.tipo,
                "mp_pagamento_id": self.mp_pagamento_id, "plano": self.plano, "ciclo": self.ciclo, "meio": self.meio,
                "valor": self.valor, "valor_liquido": self.valor_liquido, "status": self.status,
                "descricao": self.descricao, "pago_em": _iso(self.pago_em), "criado_em": _iso(self.criado_em)}


class Evento(db.Model):
    """Eventos do funil que não aparecem em outras tabelas (visita à página inicial, clique em
    "testar grátis", checkout iniciado). Cadastro, ativação e pagamento saem das tabelas próprias."""
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(30), nullable=False, index=True)  # visita, cta, checkout
    visitante_id = db.Column(db.String(40), index=True)
    conta_id = db.Column(db.Integer, index=True)
    origem = db.Column(db.String(80))
    campanha = db.Column(db.String(120))
    dados = db.Column(db.JSON)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, index=True)


class CodigoVerificacao(db.Model):
    """Código de 6 dígitos enviado por e-mail. Guardado só como hash; vale 15 minutos e 5 tentativas."""
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"), nullable=False, index=True)
    finalidade = db.Column(db.String(20), default="cadastro")
    codigo_hash = db.Column(db.String(64), nullable=False)
    tentativas = db.Column(db.Integer, default=0)
    expira_em = db.Column(db.DateTime, nullable=False)
    usado_em = db.Column(db.DateTime)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, index=True)


class TabelaReferencia(db.Model):
    """Tabela oficial de preços enviada pelo administrador (SINAPI, SICRO, CMED, SIGTAP, CCT...).
    Consultada por todos os clientes na formação de preço (RAG estruturado)."""
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200), nullable=False)
    fonte = db.Column(db.String(30), default="outra")   # sinapi, sicro, cmed, sigtap, cct, bps, outra
    uf = db.Column(db.String(2))
    data_base = db.Column(db.Date)
    observacao = db.Column(db.Text)
    n_itens = db.Column(db.Integer, default=0)
    ativa = db.Column(db.Boolean, default=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {"id": self.id, "nome": self.nome, "fonte": self.fonte, "uf": self.uf, "data_base": _iso(self.data_base),
                "observacao": self.observacao, "n_itens": self.n_itens, "ativa": self.ativa,
                "criado_em": _iso(self.criado_em)}


class ItemReferencia(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tabela_id = db.Column(db.Integer, db.ForeignKey("tabela_referencia.id"), nullable=False, index=True)
    codigo = db.Column(db.String(60))
    descricao = db.Column(db.Text, nullable=False)
    unidade = db.Column(db.String(40))
    preco = db.Column(db.Float)
    termos = db.Column(db.Text)  # descrição normalizada (minúsculas, sem acento) para a busca

    def to_dict(self, tabela=None):
        d = {"id": self.id, "tabela_id": self.tabela_id, "codigo": self.codigo, "descricao": self.descricao,
             "unidade": self.unidade, "preco": self.preco}
        if tabela:
            d.update({"tabela": tabela.nome, "fonte": tabela.fonte, "uf": tabela.uf, "data_base": _iso(tabela.data_base)})
        return d


class Proposta(db.Model):
    """Minuta de proposta comercial: itens com formação de preço + texto gerado pela IA."""
    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresa.id"), nullable=False, index=True)
    edital_id = db.Column(db.Integer, db.ForeignKey("edital.id"))
    titulo = db.Column(db.String(300))
    status = db.Column(db.String(20), default="rascunho")   # lendo_edital, rascunho, gerando, pronta, erro
    etapa = db.Column(db.String(80))
    erro = db.Column(db.Text)
    regime = db.Column(db.String(20), default="simples")     # simples, presumido, real
    tributos_pct = db.Column(db.Float, default=6.0)          # alíquota total sobre o preço de venda
    bdi_pct = db.Column(db.Float, default=20.0)              # BDI/margem padrão aplicado aos itens
    bdi_detalhe = db.Column(db.JSON)                         # componentes da fórmula do TCU, se usada
    validade_dias = db.Column(db.Integer, default=60)
    condicoes = db.Column(db.JSON)   # o que o edital exige da proposta (lido pela IA)
    itens = db.Column(db.JSON)       # [{descricao, unidade, quantidade, custo_unitario, bdi, preco_unitario, ...}]
    texto = db.Column(db.Text)       # minuta (markdown simples)
    alertas = db.Column(db.JSON)     # pontos de atenção apontados pela IA e pelas regras
    demonstracao = db.Column(db.Boolean, default=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self, completo=True):
        d = {"id": self.id, "empresa_id": self.empresa_id, "edital_id": self.edital_id, "titulo": self.titulo,
             "status": self.status, "etapa": self.etapa, "erro": self.erro, "regime": self.regime,
             "tributos_pct": self.tributos_pct, "bdi_pct": self.bdi_pct, "validade_dias": self.validade_dias,
             "demonstracao": self.demonstracao, "criado_em": _iso(self.criado_em),
             "atualizado_em": _iso(self.atualizado_em), "n_itens": len(self.itens or [])}
        if completo:
            d.update({"bdi_detalhe": self.bdi_detalhe or {}, "condicoes": self.condicoes or {},
                      "itens": self.itens or [], "texto": self.texto or "", "alertas": self.alertas or []})
        return d


class LogErro(db.Model):
    """Erros do sistema durante o uso (servidor, tarefas em segundo plano e navegador), para o admin analisar."""
    id = db.Column(db.Integer, primary_key=True)
    origem = db.Column(db.String(20), index=True)      # servidor, tarefa, navegador
    nivel = db.Column(db.String(10), default="erro")   # erro, aviso
    mensagem = db.Column(db.Text)
    detalhe = db.Column(db.Text)                       # traceback ou pilha do navegador
    rota = db.Column(db.String(300))
    metodo = db.Column(db.String(10))
    status = db.Column(db.Integer)
    usuario_email = db.Column(db.String(200))
    conta_id = db.Column(db.Integer, index=True)
    navegador = db.Column(db.String(300))
    assinatura = db.Column(db.String(64), index=True)  # agrupa erros iguais
    ocorrencias = db.Column(db.Integer, default=1)
    resolvido = db.Column(db.Boolean, default=False, index=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    ultimo_em = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def to_dict(self, completo=False):
        d = {"id": self.id, "origem": self.origem, "nivel": self.nivel, "mensagem": self.mensagem, "rota": self.rota,
             "metodo": self.metodo, "status": self.status, "usuario_email": self.usuario_email, "conta_id": self.conta_id,
             "ocorrencias": self.ocorrencias, "resolvido": self.resolvido, "criado_em": _iso(self.criado_em),
             "ultimo_em": _iso(self.ultimo_em)}
        if completo:
            d.update({"detalhe": self.detalhe, "navegador": self.navegador})
        return d
