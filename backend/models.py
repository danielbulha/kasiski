"""Modelos do banco. Toda informação de cliente pertence a uma Conta (multi-tenant)."""
from datetime import datetime, date
from extensions import db


def _iso(v):
    if v is None:
        return None
    return v.isoformat()



class NaLixeira:
    """Exclusão com lixeira: o item some das telas, pode ser restaurado por 30 dias e depois é apagado de vez
    (services/lixeira.py). excluido_grupo liga os itens que foram para a lixeira junto com o principal."""
    excluido_em = db.Column(db.DateTime)
    excluido_por = db.Column(db.String(120))
    excluido_grupo = db.Column(db.String(40))


class Conta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200), nullable=False)
    plano = db.Column(db.String(30), default="free")  # free, essencial, profissional, business, consultor, enterprise, suspenso
    trial_fim = db.Column(db.DateTime)            # fim do teste do Profissional (a conta segue no Free por baixo)
    trial_usado = db.Column(db.Boolean, default=False)
    tabela_precos = db.Column(db.Integer, default=2026)   # versão da tabela de preços em que a conta foi criada/migrada
    preco_contratado = db.Column(db.Float)        # assinante da tabela antiga: valor mensal que continua pagando
    creditos = db.Column(db.Integer, default=0)   # Pacote de inteligência: créditos para uso acima do limite do plano
    creditos_validade = db.Column(db.DateTime)
    empresas_extras = db.Column(db.Integer, default=0)   # empresas adicionais (R$ 49/mês cada; Business e Consultor)
    empresas_extras_ate = db.Column(db.DateTime)
    empresas_extras_status = db.Column(db.String(20))
    empresas_extras_metodo = db.Column(db.String(20))
    empresas_extras_mp_id = db.Column(db.String(60), index=True)
    marca_relatorio = db.Column(db.String(200))  # plano Consultor: nome do escritório nos relatórios
    dados_fiscais = db.Column(db.JSON)            # tomador da NFS-e: documento, nome, e-mail e endereço (services/fiscal.py)
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
    # atribuição de marketing: {"primeiro": {utm_source, utm_medium, utm_campaign, utm_content, utm_term, gclid, ref,
    # landing, referrer, em}, "ultimo": {...}} — o primeiro toque e o último antes do cadastro
    aquisicao = db.Column(db.JSON)
    lead_id = db.Column(db.Integer, index=True)
    marketing_optout = db.Column(db.Boolean, default=False)  # não quer receber e-mails de dicas/automação

    # Pacotes extras de contratos (mensal)
    pacotes_contratos = db.Column(db.Integer, default=0)
    pacotes_ate = db.Column(db.DateTime)
    pacotes_status = db.Column(db.String(20))   # pendente, ativa, cancelada, inadimplente
    pacotes_metodo = db.Column(db.String(20))   # recorrente, avulso
    pacotes_mp_assinatura_id = db.Column(db.String(60), index=True)
    ultimo_aviso_contratos = db.Column(db.Date)

    def to_dict(self):
        return {"id": self.id, "nome": self.nome, "plano": self.plano, "trial_fim": _iso(self.trial_fim), "trial_usado": self.trial_usado,
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
    papel = db.Column(db.String(20))              # dono (gerencia equipe e assinatura) ou membro
    tour = db.Column(db.JSON)                     # tour guiado por plano: {"free": "concluido"|"pulado"|"anterior", ...}
    conta = db.relationship("Conta")

    @property
    def verificado(self):
        return self.email_verificado is not False

    def to_dict(self, admin=False):
        return {"id": self.id, "nome": self.nome, "email": self.email, "modo_guiado": self.modo_guiado, "admin": admin,
                "papel": self.papel or "dono", "tour": self.tour or {}}


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

    oportunidades_sync = db.Column(db.JSON)  # {status, iniciado_em, concluido_em, movidos}
    radar_buscas = db.Column(db.JSON)  # plano Free: {"dia": "AAAA-MM-DD", "n": buscas no dia, "extra": bool, "desde": ISO da última busca}
    historico_pncp = db.Column(db.JSON)  # vitórias da própria empresa no PNCP (services/historico_empresa.py), cache de 7 dias
    radar_diarios = db.Column(db.Boolean, default=False)  # radar também nos diários oficiais municipais (services/diarios.py)

    def to_dict(self):
        return {"id": self.id, "razao_social": self.razao_social, "cnpj": self.cnpj, "porte": self.porte,
                "cnaes": self.cnaes, "segmentos": self.segmentos, "palavras_chave": self.palavras_chave, "ufs": self.ufs,
                "valor_min": self.valor_min, "valor_max": self.valor_max, "termos_radar": self._termos_radar(),
                "radar_diarios": bool(self.radar_diarios)}

    def _termos_radar(self):
        from services import cnae
        return cnae.termos_radar(self.segmentos, self.palavras_chave)


class Documento(NaLixeira, db.Model):
    """Cofre de habilitação."""
    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresa.id"), nullable=False, index=True)
    categoria = db.Column(db.String(40))  # juridica, fiscal, trabalhista, economica, tecnica, declaracao, outro
    tipo = db.Column(db.String(120), nullable=False)
    descricao = db.Column(db.Text, default="")
    validade = db.Column(db.Date)
    arquivo = db.Column(db.String(300))
    nome_arquivo = db.Column(db.String(250))
    pendente = db.Column(db.Boolean, default=False)   # item do checklist que a empresa ainda não providenciou
    checklist_id = db.Column(db.String(40))           # item do catálogo (data/checklist_habilitacao.json)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    def situacao(self, referencia=None):
        if self.pendente and not self.arquivo and not self.validade:
            return "pendente"
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
                "nome_arquivo": self.nome_arquivo, "tem_arquivo": bool(self.arquivo), "criado_em": _iso(self.criado_em),
                "pendente": bool(self.pendente), "checklist_id": self.checklist_id}


class ChecklistPublico(db.Model):
    """Checklist de habilitação montado no site (/checklist-habilitacao/) — importado para o Cofre no cadastro."""
    id = db.Column(db.String(40), primary_key=True)
    lead_id = db.Column(db.Integer, index=True)
    email = db.Column(db.String(200), index=True)
    segmento = db.Column(db.String(40))
    itens = db.Column(db.JSON)                 # [{id, tem, validade}]
    acao = db.Column(db.String(20))            # baixar, importar
    conta_id = db.Column(db.Integer)
    importado_em = db.Column(db.DateTime)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, index=True)


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


class Edital(NaLixeira, db.Model):
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
    # empresas que venceram contratações parecidas no PNCP: {status, itens, termos, consultado_em, erro}
    possiveis_concorrentes = db.Column(db.JSON)
    # Kanban da oportunidade (ciclo comercial): ver services/oportunidades.py
    etapa = db.Column(db.String(30), index=True)
    etapa_em = db.Column(db.DateTime)
    responsavel = db.Column(db.String(120))
    responsavel_id = db.Column(db.Integer)
    decisao = db.Column(db.String(10))            # go, no_go
    decisao_motivo = db.Column(db.Text)
    motivo_saida = db.Column(db.Text)             # por que foi perdida / desistência
    unidade_codigo = db.Column(db.String(30))     # UASG / código da unidade compradora
    unidade_nome = db.Column(db.String(300))
    pncp_situacao = db.Column(db.String(80))
    pncp_sincronizado_em = db.Column(db.DateTime)
    data_sessao_fonte = db.Column(db.String(20))  # de onde veio a data da sessão: usuario > edital (lida pela IA) > pncp
    cronograma = db.Column(db.JSON)  # sessão, envio de propostas, impugnação... por fonte e divergências (services/cronograma.py)
    arquivado_em = db.Column(db.DateTime)        # licitação encerrada: dossiê no Arquivo (services/arquivo_licitacao.py)
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
        d.update({"etapa": self.etapa, "etapa_em": _iso(self.etapa_em), "responsavel": self.responsavel,
                  "responsavel_id": self.responsavel_id, "decisao": self.decisao, "decisao_motivo": self.decisao_motivo,
                  "motivo_saida": self.motivo_saida, "unidade_codigo": self.unidade_codigo, "unidade_nome": self.unidade_nome,
                  "pncp_situacao": self.pncp_situacao, "pncp_sincronizado_em": _iso(self.pncp_sincronizado_em),
                  "arquivado_em": _iso(self.arquivado_em)})
        from services import cronograma as _cr
        d["alerta_datas"] = _cr.alerta(self)
        if completo:
            d["cronograma"] = _cr.publico(self)
            d["caracteres_texto"] = len(self.texto or "")
            d["possiveis_concorrentes"] = self.possiveis_concorrentes
        return d


class DocumentoLicitacao(NaLixeira, db.Model):
    """Documentos da licitação enviados pelo usuário (atas, anexos, propostas, recursos, decisões...).
    Atas podem ser analisadas pela IA, que sugere peças (recurso, contrarrazões etc.)."""
    id = db.Column(db.Integer, primary_key=True)
    edital_id = db.Column(db.Integer, db.ForeignKey("edital.id"), nullable=False, index=True)
    empresa_id = db.Column(db.Integer, nullable=False, index=True)
    tipo = db.Column(db.String(30), default="outro")
    titulo = db.Column(db.String(300))
    arquivo = db.Column(db.String(300))
    nome_arquivo = db.Column(db.String(250))
    tamanho = db.Column(db.Integer, default=0)
    texto = db.Column(db.Text)
    analise = db.Column(db.JSON)        # resultado da análise da ata
    analise_status = db.Column(db.String(20))   # processando, concluida, erro
    analise_erro = db.Column(db.String(300))
    enviado_por = db.Column(db.String(120))
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {"id": self.id, "edital_id": self.edital_id, "tipo": self.tipo, "titulo": self.titulo,
                "nome_arquivo": self.nome_arquivo, "tamanho": self.tamanho or 0, "tem_arquivo": bool(self.arquivo),
                "tem_texto": bool(self.texto), "analise": self.analise, "analise_status": self.analise_status,
                "analise_erro": self.analise_erro, "enviado_por": self.enviado_por, "criado_em": _iso(self.criado_em)}


class Movimento(db.Model):
    """Histórico do cartão no Kanban de oportunidades (quem moveu, de onde para onde e por quê)."""
    id = db.Column(db.Integer, primary_key=True)
    edital_id = db.Column(db.Integer, db.ForeignKey("edital.id"), nullable=False, index=True)
    de = db.Column(db.String(30))
    para = db.Column(db.String(30))
    origem = db.Column(db.String(20), default="usuario")  # usuario, automatico
    autor = db.Column(db.String(200))
    motivo = db.Column(db.Text)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {"id": self.id, "de": self.de, "para": self.para, "origem": self.origem, "autor": self.autor,
                "motivo": self.motivo, "criado_em": _iso(self.criado_em)}


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


class Peca(NaLixeira, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresa.id"), nullable=False, index=True)
    edital_id = db.Column(db.Integer, db.ForeignKey("edital.id"))
    contrato_id = db.Column(db.Integer, db.ForeignKey("contrato.id"))
    tipo = db.Column(db.String(40), nullable=False)
    titulo = db.Column(db.String(300))
    conteudo = db.Column(db.Text)
    status = db.Column(db.String(30), default="rascunho")  # rascunho, revisao_solicitada, revisada
    demonstracao = db.Column(db.Boolean, default=False)
    doublecheck = db.Column(db.JSON)  # verificação independente da minuta: {status, estado, resumo, achados, pontos}
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self, completo=True):
        dc = dict(self.doublecheck or {})
        dc.pop("pontos", None)
        d = {"id": self.id, "empresa_id": self.empresa_id, "edital_id": self.edital_id, "contrato_id": self.contrato_id,
             "tipo": self.tipo, "titulo": self.titulo, "status": self.status, "demonstracao": self.demonstracao,
             "doublecheck": dc or None, "criado_em": _iso(self.criado_em), "atualizado_em": _iso(self.atualizado_em)}
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


class Prazo(NaLixeira, db.Model):
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


class DocumentoConcorrente(NaLixeira, db.Model):
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


class AnaliseConcorrente(NaLixeira, db.Model):
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


class PesquisaPreco(NaLixeira, db.Model):
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


class Contrato(NaLixeira, db.Model):
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
    # nota fiscal de serviço (controle manual pelo admin; vazio = pendente quando o pagamento está aprovado)
    nf_status = db.Column(db.String(20))     # emitida, nao_emitir
    nf_numero = db.Column(db.String(40))
    nf_emitida_em = db.Column(db.DateTime)
    nf_tomador = db.Column(db.JSON)          # cópia dos dados fiscais no momento da emissão
    nf_obs = db.Column(db.String(300))

    def to_dict(self):
        return {"id": self.id, "conta_id": self.conta_id, "origem": self.origem, "tipo": self.tipo,
                "nf_status": self.nf_status, "nf_numero": self.nf_numero,
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
    lead_id = db.Column(db.Integer, index=True)
    canal = db.Column(db.String(30))
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, index=True)


class Lead(db.Model):
    """Pessoa que ainda não criou conta (ou que já criou: fica ligada à conta para ver o funil inteiro)."""
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200))
    email = db.Column(db.String(200), unique=True, index=True)
    telefone = db.Column(db.String(40))
    whatsapp = db.Column(db.String(40))
    empresa = db.Column(db.String(250))
    cnpj = db.Column(db.String(14))
    cargo = db.Column(db.String(120))
    segmento = db.Column(db.String(80))
    cidade = db.Column(db.String(120))
    uf = db.Column(db.String(2))
    origem = db.Column(db.String(80))
    canal = db.Column(db.String(30), index=True)       # busca_paga, busca_organica, social_pago, social, email, indicacao, parceiro, direto, outro
    campanha = db.Column(db.String(120))
    utm_source = db.Column(db.String(80))
    utm_medium = db.Column(db.String(80))
    utm_campaign = db.Column(db.String(120))
    utm_content = db.Column(db.String(120))
    utm_term = db.Column(db.String(120))
    gclid = db.Column(db.String(200))
    ref_parceiro = db.Column(db.String(60))
    lead_magnet = db.Column(db.String(60))             # analisar_edital, consultar_concorrente, newsletter, checklist, contato
    landing_page = db.Column(db.String(300))
    primeira_visita = db.Column(db.DateTime)
    ultima_visita = db.Column(db.DateTime)
    visitante_id = db.Column(db.String(40), index=True)
    score = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default="novo", index=True)  # novo, engajado, mql, sql, trial, ativado, assinante, perdido
    responsavel = db.Column(db.String(120))
    notas = db.Column(db.Text)
    usuario_id = db.Column(db.Integer)
    conta_id = db.Column(db.Integer, index=True)
    newsletter = db.Column(db.Boolean, default=False)
    newsletter_confirmada = db.Column(db.Boolean, default=False)
    token = db.Column(db.String(40), index=True)        # confirmação/descadastro sem login
    consentimento_em = db.Column(db.DateTime)
    marketing_optout = db.Column(db.Boolean, default=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow)
    convertido_em = db.Column(db.DateTime)

    def to_dict(self):
        campos = ("id", "nome", "email", "telefone", "whatsapp", "empresa", "cnpj", "cargo", "segmento", "cidade", "uf",
                  "origem", "canal", "campanha", "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term",
                  "ref_parceiro", "lead_magnet", "landing_page", "score", "status", "responsavel", "notas", "usuario_id",
                  "conta_id", "newsletter", "newsletter_confirmada", "marketing_optout")
        d = {k: getattr(self, k) for k in campos}
        for k in ("primeira_visita", "ultima_visita", "criado_em", "convertido_em", "atualizado_em"):
            d[k] = _iso(getattr(self, k))
        return d


class AnalisePublica(db.Model):
    """Análise gratuita de edital feita pelo site (sem conta). O arquivo expira em 7 dias."""
    id = db.Column(db.String(40), primary_key=True)     # token aleatório (vai na URL do resultado)
    lead_id = db.Column(db.Integer, index=True)
    email = db.Column(db.String(200), index=True)
    ip_hash = db.Column(db.String(64), index=True)
    arquivo = db.Column(db.String(300))
    nome_arquivo = db.Column(db.String(250))
    texto = db.Column(db.Text)
    status = db.Column(db.String(20), default="processando")  # processando, concluida, erro
    etapa = db.Column(db.String(80))
    resultado = db.Column(db.JSON)
    erro = db.Column(db.Text)
    custo_usd = db.Column(db.Float, default=0)
    conta_id = db.Column(db.Integer)                    # conta que importou depois do cadastro
    edital_id = db.Column(db.Integer)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    concluido_em = db.Column(db.DateTime)


class DiagnosticoB2G(db.Model):
    """Diagnóstico de maturidade para vendas ao governo feito no site (/diagnostico)."""
    __tablename__ = "diagnostico_b2g"
    id = db.Column(db.String(40), primary_key=True)
    visitante_id = db.Column(db.String(40), index=True)
    lead_id = db.Column(db.Integer, index=True)
    ip_hash = db.Column(db.String(64))
    respostas = db.Column(db.JSON)
    eixos = db.Column(db.JSON)          # {eixo: nota 0-100 ou None (não se aplica)}
    nota = db.Column(db.Integer)
    nivel = db.Column(db.String(30))
    segmento = db.Column(db.String(80))
    porte = db.Column(db.String(30))
    versao = db.Column(db.Integer, default=1)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, index=True)


class UsoPublico(db.Model):
    """Registro de uso das ferramentas gratuitas, para limitar abuso por IP e por e-mail."""
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(30), index=True)        # analisar_edital, concorrente, newsletter, lead
    ip_hash = db.Column(db.String(64), index=True)
    email = db.Column(db.String(200), index=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, index=True)


class Automacao(db.Model):
    """Regra de e-mail automático: gatilho + atraso + condição + modelo."""
    id = db.Column(db.Integer, primary_key=True)
    chave = db.Column(db.String(40), unique=True, nullable=False)
    nome = db.Column(db.String(120))
    gatilho = db.Column(db.String(40))                 # cadastro, empresa, radar, analise, trial_fim
    atraso_min = db.Column(db.Integer, default=0)      # para trial_fim: minutos ANTES do fim do teste
    condicao = db.Column(db.String(60))
    assunto = db.Column(db.String(200))
    ativo = db.Column(db.Boolean, default=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)


class AutomacaoEnvio(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    automacao_id = db.Column(db.Integer, db.ForeignKey("automacao.id"), nullable=False, index=True)
    conta_id = db.Column(db.Integer, nullable=False, index=True)
    email = db.Column(db.String(200))
    status = db.Column(db.String(20), default="enviado")  # enviado, falhou, ignorado
    detalhe = db.Column(db.Text)
    enviado_em = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    __table_args__ = (db.UniqueConstraint("automacao_id", "conta_id"),)


class InvestimentoCanal(db.Model):
    """Quanto foi investido por canal em um mês (para calcular o CAC)."""
    id = db.Column(db.Integer, primary_key=True)
    mes = db.Column(db.String(7), index=True)          # AAAA-MM
    canal = db.Column(db.String(80))                   # utm_source (google, linkedin, meta...) ou canal
    campanha = db.Column(db.String(120))
    valor = db.Column(db.Float, default=0)
    notas = db.Column(db.String(300))
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {"id": self.id, "mes": self.mes, "canal": self.canal, "campanha": self.campanha, "valor": self.valor, "notas": self.notas}


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
    desonerado = db.Column(db.Boolean)                  # SINAPI/SICRO: preços com desoneração da folha
    colunas = db.Column(db.JSON)                        # [{nome, tipo: preco|info}] colunas extras guardadas na importação
    desativada_em = db.Column(db.DateTime)              # a limpeza apaga os itens 30 dias depois
    itens_removidos_em = db.Column(db.DateTime)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {"id": self.id, "nome": self.nome, "fonte": self.fonte, "uf": self.uf, "data_base": _iso(self.data_base),
                "observacao": self.observacao, "n_itens": self.n_itens, "ativa": self.ativa, "desonerado": self.desonerado,
                "colunas": self.colunas or [], "desativada_em": _iso(self.desativada_em),
                "itens_removidos_em": _iso(self.itens_removidos_em), "criado_em": _iso(self.criado_em)}


class ItemReferencia(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tabela_id = db.Column(db.Integer, db.ForeignKey("tabela_referencia.id"), nullable=False, index=True)
    codigo = db.Column(db.String(60))
    descricao = db.Column(db.Text, nullable=False)
    unidade = db.Column(db.String(40))
    preco = db.Column(db.Float)
    termos = db.Column(db.Text)  # descrição normalizada (minúsculas, sem acento) para a busca
    precos = db.Column(db.JSON)  # todas as colunas de preço da linha {rótulo: valor} (ex.: CMED PF 18%, PMVG 18%)
    extras = db.Column(db.JSON)  # demais colunas informativas {rótulo: texto} (ex.: laboratório, registro, CAP, tarja)

    def to_dict(self, tabela=None):
        d = {"id": self.id, "tabela_id": self.tabela_id, "codigo": self.codigo, "descricao": self.descricao,
             "unidade": self.unidade, "preco": self.preco, "precos": self.precos or {}, "extras": self.extras or {}}
        if tabela:
            d.update({"tabela": tabela.nome, "fonte": tabela.fonte, "uf": tabela.uf, "data_base": _iso(tabela.data_base),
                      "desonerado": tabela.desonerado})
        return d


class Proposta(NaLixeira, db.Model):
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
    parametros = db.Column(db.JSON)  # referência de preço: {uf, icms_pct, criterio_cmed, desonerado, fontes, modo}
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
            d.update({"bdi_detalhe": self.bdi_detalhe or {}, "condicoes": self.condicoes or {}, "parametros": self.parametros or {},
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


class ChatConversa(db.Model):
    """Conversa do assistente virtual (visitante ou usuário logado). Vira chamado quando pede atendimento humano."""
    id = db.Column(db.String(40), primary_key=True)
    conta_id = db.Column(db.Integer, index=True)
    usuario_email = db.Column(db.String(200))
    visitante_id = db.Column(db.String(40), index=True)
    pagina = db.Column(db.String(300))
    status = db.Column(db.String(20), default="bot", index=True)  # bot, encaminhada, em_atendimento, resolvida
    nome = db.Column(db.String(200))
    email = db.Column(db.String(200))
    telefone = db.Column(db.String(40))
    assunto = db.Column(db.Text)
    n_mensagens = db.Column(db.Integer, default=0)
    notas = db.Column(db.Text)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    encaminhada_em = db.Column(db.DateTime)

    def to_dict(self):
        return {"id": self.id, "conta_id": self.conta_id, "usuario_email": self.usuario_email, "pagina": self.pagina,
                "status": self.status, "nome": self.nome, "email": self.email, "telefone": self.telefone,
                "assunto": self.assunto, "n_mensagens": self.n_mensagens, "notas": self.notas,
                "criado_em": _iso(self.criado_em), "atualizado_em": _iso(self.atualizado_em),
                "encaminhada_em": _iso(self.encaminhada_em)}


class ChatMensagem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    conversa_id = db.Column(db.String(40), db.ForeignKey("chat_conversa.id"), nullable=False, index=True)
    papel = db.Column(db.String(12))  # usuario, assistente, sistema, atendente
    texto = db.Column(db.Text)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {"id": self.id, "papel": self.papel, "texto": self.texto, "criado_em": _iso(self.criado_em)}


class EdicaoNewsletter(db.Model):
    """Edição semanal da newsletter Kasiski Intelligence (dados do PNCP + radar regulatório escrito pelo admin)."""
    __tablename__ = "newsletter_edicao"
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.Integer, unique=True, nullable=False)
    semana_inicio = db.Column(db.Date, unique=True, nullable=False)
    semana_fim = db.Column(db.Date, nullable=False)
    titulo = db.Column(db.String(200))
    assunto = db.Column(db.String(200))
    pre_cabecalho = db.Column(db.String(200))
    abertura = db.Column(db.Text)
    dados = db.Column(db.JSON)            # métricas, modalidades, UFs, setores, oportunidades, amostra
    radar = db.Column(db.JSON)            # [{titulo, resumo, link, fonte}]
    ocultas = db.Column(db.JSON)          # números de controle das oportunidades removidas pelo admin
    links = db.Column(db.JSON)            # URLs rastreadas do e-mail (índice usado no redirecionamento)
    status = db.Column(db.String(20), default="rascunho", index=True)  # rascunho, agendada, enviando, enviada
    agendada_para = db.Column(db.DateTime)
    processando_em = db.Column(db.DateTime)   # batimento do envio (retoma se o processo cair)
    enviada_em = db.Column(db.DateTime)
    destinatarios = db.Column(db.Integer, default=0)
    enviados = db.Column(db.Integer, default=0)
    falhas = db.Column(db.Integer, default=0)
    coletado_em = db.Column(db.DateTime)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow)


class NewsletterEnvio(db.Model):
    """Um e-mail de uma edição para um inscrito (idempotente) + abertura, clique e descadastro."""
    __tablename__ = "newsletter_envio"
    id = db.Column(db.Integer, primary_key=True)
    edicao_id = db.Column(db.Integer, db.ForeignKey("newsletter_edicao.id"), nullable=False, index=True)
    lead_id = db.Column(db.Integer, nullable=False, index=True)
    email = db.Column(db.String(200))
    token = db.Column(db.String(40), unique=True, nullable=False)
    status = db.Column(db.String(20), default="pendente")  # pendente, enviado, falhou
    erro = db.Column(db.Text)
    enviado_em = db.Column(db.DateTime)
    aberto_em = db.Column(db.DateTime)
    aberturas = db.Column(db.Integer, default=0)
    clicado_em = db.Column(db.DateTime)
    cliques = db.Column(db.JSON)          # {índice do link: quantidade}
    descadastrou_em = db.Column(db.DateTime)
    __table_args__ = (db.UniqueConstraint("edicao_id", "lead_id"),)


class BuscaProspeccao(db.Model):
    """Varredura do PNCP por segmento para achar empresas que vendem ao governo (possíveis clientes do Kasiski)."""
    __tablename__ = "busca_prospeccao"
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(160))
    termos = db.Column(db.JSON)            # ["limpeza predial", "conservação"]
    ufs = db.Column(db.JSON)               # ["SP", "MG"] ou []
    meses = db.Column(db.Integer, default=12)
    limite = db.Column(db.Integer, default=100)
    status = db.Column(db.String(20), default="na_fila")  # na_fila, buscando, enriquecendo, concluida, erro
    etapa = db.Column(db.String(160))
    documentos = db.Column(db.Integer, default=0)
    empresas = db.Column(db.Integer, default=0)
    erro = db.Column(db.Text)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    concluido_em = db.Column(db.DateTime)

    def to_dict(self):
        return {"id": self.id, "nome": self.nome, "termos": self.termos or [], "ufs": self.ufs or [], "meses": self.meses,
                "limite": self.limite, "status": self.status, "etapa": self.etapa, "documentos": self.documentos,
                "empresas": self.empresas, "erro": self.erro, "criado_em": _iso(self.criado_em),
                "concluido_em": _iso(self.concluido_em)}


class Prospect(db.Model):
    """Empresa que vence licitações (dados públicos do PNCP e da Receita) avaliada como possível cliente."""
    __tablename__ = "prospect"
    id = db.Column(db.Integer, primary_key=True)
    cnpj = db.Column(db.String(14), unique=True, nullable=False, index=True)
    razao_social = db.Column(db.String(250))
    nome_fantasia = db.Column(db.String(250))
    uf = db.Column(db.String(2), index=True)
    municipio = db.Column(db.String(120))
    porte = db.Column(db.String(60))
    cnae = db.Column(db.String(20))
    cnae_descricao = db.Column(db.String(250))
    situacao = db.Column(db.String(40))
    abertura = db.Column(db.String(20))
    capital_social = db.Column(db.Float)
    simples = db.Column(db.Boolean)
    telefone = db.Column(db.String(60))         # contato cadastrado na Receita (pode ser do contador)
    email_empresa = db.Column(db.String(200))   # idem
    socios = db.Column(db.JSON)                 # [{nome, qualificacao}] do QSA público
    segmentos = db.Column(db.JSON)              # termos de busca em que apareceu
    buscas = db.Column(db.JSON)                 # ids das buscas
    contratos = db.Column(db.Integer, default=0)
    atas = db.Column(db.Integer, default=0)
    valor_total = db.Column(db.Float, default=0)
    orgaos = db.Column(db.JSON)                 # {órgão: vitórias}
    ufs_atuacao = db.Column(db.JSON)
    meses_ativos = db.Column(db.Integer, default=0)
    primeira_vitoria = db.Column(db.Date)
    ultima_vitoria = db.Column(db.Date)
    exemplos = db.Column(db.JSON)               # contratos/atas com link do PNCP
    score = db.Column(db.Integer, default=0, index=True)
    faixa = db.Column(db.String(1), index=True)  # A, B, C, D
    motivos = db.Column(db.JSON)
    plano_sugerido = db.Column(db.String(20))
    status = db.Column(db.String(20), default="novo", index=True)  # novo, contatado, respondeu, lead, cliente, descartado, nao_contatar
    responsavel = db.Column(db.String(120))
    notas = db.Column(db.Text)
    lead_id = db.Column(db.Integer, index=True)
    conta_id = db.Column(db.Integer, index=True)
    token = db.Column(db.String(40), unique=True, index=True)   # link do relatório gratuito
    relatorio_visitas = db.Column(db.Integer, default=0)
    relatorio_visto_em = db.Column(db.DateTime)
    editais_cache = db.Column(db.JSON)          # editais abertos que combinam (cache do relatório)
    editais_cache_em = db.Column(db.DateTime)
    contatado_em = db.Column(db.DateTime)
    enriquecido_em = db.Column(db.DateTime)
    contatos = db.Column(db.JSON)               # [{tipo, valor, fonte, verificado, obs}] — services/contatos.py
    site = db.Column(db.String(300))
    email_sugerido = db.Column(db.String(200))  # melhor e-mail para a abordagem
    contatos_em = db.Column(db.DateTime)
    emails_enviados = db.Column(db.JSON)        # [{para, assunto, em, por, id}] — abordagens enviadas pelo sistema
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self, completo=False):
        d = {k: getattr(self, k) for k in ("id", "cnpj", "razao_social", "nome_fantasia", "uf", "municipio", "porte", "cnae",
                                           "cnae_descricao", "situacao", "telefone", "email_empresa", "contratos", "atas",
                                           "valor_total", "meses_ativos", "score", "faixa", "plano_sugerido", "status",
                                           "responsavel", "lead_id", "conta_id", "token", "relatorio_visitas")}
        d.update({"segmentos": self.segmentos or [], "n_orgaos": len(self.orgaos or {}), "ufs_atuacao": self.ufs_atuacao or [],
                  "ultima_vitoria": _iso(self.ultima_vitoria), "primeira_vitoria": _iso(self.primeira_vitoria),
                  "relatorio_visto_em": _iso(self.relatorio_visto_em), "contatado_em": _iso(self.contatado_em),
                  "motivos": self.motivos or [], "criado_em": _iso(self.criado_em), "email_sugerido": self.email_sugerido})
        if completo:
            d.update({"orgaos": self.orgaos or {}, "exemplos": self.exemplos or [], "socios": self.socios or [],
                      "notas": self.notas, "abertura": self.abertura, "capital_social": self.capital_social,
                      "simples": self.simples, "buscas": self.buscas or [], "contatos": self.contatos or [],
                      "site": self.site, "contatos_em": _iso(self.contatos_em), "emails_enviados": self.emails_enviados or []})
        return d


class Convite(db.Model):
    """Convite para entrar na equipe da conta (limite de usuários do plano)."""
    id = db.Column(db.Integer, primary_key=True)
    conta_id = db.Column(db.Integer, db.ForeignKey("conta.id"), nullable=False, index=True)
    email = db.Column(db.String(200), nullable=False, index=True)
    token = db.Column(db.String(60), unique=True, nullable=False)
    convidado_por = db.Column(db.Integer)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    expira_em = db.Column(db.DateTime)
    aceito_em = db.Column(db.DateTime)

    def to_dict(self):
        return {"id": self.id, "email": self.email, "criado_em": _iso(self.criado_em), "expira_em": _iso(self.expira_em),
                "aceito_em": _iso(self.aceito_em)}


# ---------------------------------------------------------------- rede de segurança: texto maior que a coluna
# Textos vindos da IA ou de formulários às vezes passam do tamanho da coluna (ex.: String(60)). No Postgres isso
# derruba a gravação inteira (StringDataRightTruncation); aqui o texto é cortado com reticências antes de gravar.
from sqlalchemy import String, event  # noqa: E402


def _cortar_textos(mapper, connection, alvo):
    for col in mapper.columns:
        n = getattr(col.type, "length", None)
        if not n or not isinstance(col.type, String):
            continue
        v = getattr(alvo, col.key, None)
        if isinstance(v, str) and len(v) > n:
            setattr(alvo, col.key, v[: n - 1].rstrip() + "…")


event.listen(db.Model, "before_insert", _cortar_textos, propagate=True)
event.listen(db.Model, "before_update", _cortar_textos, propagate=True)



# ---------------------------------------------------------------- lixeira: itens excluídos somem de todas as consultas
from sqlalchemy.orm import Session as _Sessao, with_loader_criteria  # noqa: E402

MODELOS_LIXEIRA = (Edital, Contrato, Peca, Proposta, Documento, DocumentoLicitacao, DocumentoConcorrente,
                   AnaliseConcorrente, PesquisaPreco, Prazo)


@event.listens_for(_Sessao, "do_orm_execute")
def _sem_itens_da_lixeira(ctx):
    if (ctx.is_select and not ctx.is_column_load and not ctx.is_relationship_load
            and not ctx.execution_options.get("incluir_excluidos", False)):
        ctx.statement = ctx.statement.options(*[
            with_loader_criteria(m, lambda cls: cls.excluido_em.is_(None), include_aliases=True, track_closure_variables=False)
            for m in MODELOS_LIXEIRA])


class Disputa(NaLixeira, db.Model):
    """Sala de disputa: um item/lote de um pregão, com a estratégia de lances e o registro do que aconteceu.
    O Kasiski calcula o próximo lance e os intervalos; o lance é dado pelo usuário no portal."""
    id = db.Column(db.Integer, primary_key=True)
    empresa_id = db.Column(db.Integer, db.ForeignKey("empresa.id"), nullable=False, index=True)
    edital_id = db.Column(db.Integer, db.ForeignKey("edital.id"), index=True)
    item = db.Column(db.String(40))                # número do item ou do lote
    descricao = db.Column(db.String(400))
    portal = db.Column(db.String(30), default="comprasgov")   # comprasgov, bec, licitacoes_e, bll, portal_compras_publicas, outro
    modo = db.Column(db.String(20), default="aberto")          # aberto, aberto_fechado, fechado_aberto
    criterio = db.Column(db.String(20), default="menor_preco")  # menor_preco, maior_desconto
    valor_referencia = db.Column(db.Float)          # estimado do edital (ou 100% para desconto)
    lance_inicial = db.Column(db.Float)             # proposta inicial
    preco_piso = db.Column(db.Float)                # limite: abaixo disso não vale a pena (menor preço) / desconto máximo
    estrategia = db.Column(db.String(20), default="moderada")  # conservadora, moderada, agressiva, personalizada
    decremento_tipo = db.Column(db.String(10), default="percentual")  # percentual, valor
    decremento = db.Column(db.Float, default=1.0)
    diferenca_minima = db.Column(db.Float)          # intervalo mínimo de diferença entre lances fixado no edital (em R$ ou p.p.)
    intervalo_proprio_s = db.Column(db.Integer, default=20)
    intervalo_outros_s = db.Column(db.Integer, default=3)
    status = db.Column(db.String(20), default="preparando")    # preparando, em_disputa, encerrada
    resultado = db.Column(db.String(20))            # vencedor, classificado, perdeu, desistiu
    posicao = db.Column(db.Integer)
    melhor_lance = db.Column(db.Float)              # melhor lance do mercado visto no portal
    meu_ultimo = db.Column(db.Float)
    meu_ultimo_em = db.Column(db.DateTime)
    melhor_em = db.Column(db.DateTime)
    lances = db.Column(db.JSON)                     # [{em, valor, tipo: meu|mercado, obs}]
    analise = db.Column(db.JSON)                    # análise de lances com IA + DoubleCheck (services/analise_lances.py)
    notas = db.Column(db.Text)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


MODELOS_LIXEIRA = MODELOS_LIXEIRA + (Disputa,)  # o filtro da lixeira lê esta tupla a cada consulta


class PropostaLance(db.Model):
    """Aprovação humana de lance, sem integração transacional externa."""
    __tablename__ = "proposta_lance"
    id = db.Column(db.Integer, primary_key=True)
    disputa_id = db.Column(db.Integer, db.ForeignKey("disputa.id"), nullable=False, index=True)
    usuario_id = db.Column(db.Integer, nullable=False)
    valor = db.Column(db.Numeric(16, 2), nullable=False)
    criterio = db.Column(db.String(20), nullable=False)
    estado = db.Column(db.String(24), nullable=False, default="pendente")
    snapshot = db.Column(db.JSON, nullable=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expira_em = db.Column(db.DateTime, nullable=False)
    decidido_em = db.Column(db.DateTime)
    confirmado_em = db.Column(db.DateTime)
    observacao = db.Column(db.String(500))
