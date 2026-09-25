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
    plano = db.Column(db.String(30), default="trial")  # trial, essencial, profissional, consultor, suspenso
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
             "resultado_em": _iso(self.resultado_em), "criado_em": _iso(self.criado_em)}
        if completo:
            d["caracteres_texto"] = len(self.texto or "")
        return d


class Analise(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    edital_id = db.Column(db.Integer, db.ForeignKey("edital.id"), nullable=False, index=True)
    status = db.Column(db.String(20), default="concluida")
    resultado = db.Column(db.JSON)
    modelos = db.Column(db.JSON)
    demonstracao = db.Column(db.Boolean, default=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {"id": self.id, "edital_id": self.edital_id, "status": self.status, "resultado": self.resultado or {},
                "modelos": self.modelos or {}, "demonstracao": self.demonstracao, "criado_em": _iso(self.criado_em)}


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
    id = db.Column(db.Integer, primary_key=True)
    peca_id = db.Column(db.Integer, db.ForeignKey("peca.id"), nullable=False)
    conta_id = db.Column(db.Integer, db.ForeignKey("conta.id"), nullable=False, index=True)
    status = db.Column(db.String(20), default="pendente")  # pendente, em_andamento, concluida, cancelada
    valor = db.Column(db.Float)
    prazo_desejado = db.Column(db.Date)
    observacoes = db.Column(db.Text)
    parecer = db.Column(db.Text)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    peca = db.relationship("Peca")

    def to_dict(self):
        return {"id": self.id, "peca_id": self.peca_id, "status": self.status, "valor": self.valor,
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
    __table_args__ = (db.UniqueConstraint("conta_id", "cnpj"),)

    def to_dict(self):
        return {"id": self.id, "cnpj": self.cnpj, "razao_social": self.razao_social, "dossie": self.dossie or {},
                "atualizado_em": _iso(self.atualizado_em)}


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
    pagamentos = db.relationship("Pagamento", cascade="all, delete-orphan", order_by="Pagamento.vencimento")

    def to_dict(self, com_pagamentos=False):
        d = {"id": self.id, "empresa_id": self.empresa_id, "edital_id": self.edital_id, "numero": self.numero,
             "orgao": self.orgao, "objeto": self.objeto, "valor": self.valor, "inicio": _iso(self.inicio),
             "fim": _iso(self.fim), "data_base_reajuste": _iso(self.data_base_reajuste),
             "indice_reajuste": self.indice_reajuste, "garantia_validade": _iso(self.garantia_validade),
             "observacoes": self.observacoes}
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
