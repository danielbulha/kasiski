"""Fluxos de negócio que combinam IA, dados públicos e banco. As rotas só chamam estas funções."""
import logging
from datetime import date, datetime, timedelta

from extensions import ErroAPI, db
from models import Analise, AnaliseConcorrente, Documento, Prazo, RadarItem
from services import kb, llm, pncp, prompts
from services.arquivos import cortar
from services.dados_publicos import receita, sancoes_cgu, sancoes_tcu
from services.prazos import fim_do_dia, subtrair_uteis

log = logging.getLogger(__name__)


def _empresa_dict(e):
    return {"razao_social": e.razao_social, "cnpj": e.cnpj, "porte": e.porte, "cnaes": e.cnaes,
            "atuacao": e.palavras_chave, "ufs": e.ufs}


_TERMOS_TIPO_OBJETO = {
    "obra": "obra regime execução empreitada contratação integrada semi-integrada matriz de riscos ART RRT CREA CAU projeto básico executivo medição fiscalização engenharia",
    "servico_engenharia": "serviço engenharia ART RRT CREA CAU responsabilidade técnica projeto",
    "servico_continuado": "serviço continuado dedicação mão de obra planilha custos convenção coletiva repactuação encargos",
    "fornecimento": "fornecimento bens amostra prova de conceito marca modelo garantia produto entrega assistência técnica",
    "fornecimento_continuado": "registro de preços ata adesão carona fornecimento entrega parcelada",
}
_TERMOS_SEGMENTO = {
    "saude": "saúde ANVISA vigilância sanitária licença sanitária responsável técnico farmacêutico CRF rastreabilidade cadeia de frio hospitalar PGRSS resíduos serviços de saúde",
    "educacao": "educação escolar PNAE merenda nutricionista CRN transporte escolar DETRAN condutor material didático BNCC",
    "ti": "tecnologia da informação TI software SaaS licenciamento LGPD dados pessoais segurança da informação ISO 27001 propriedade intelectual código-fonte métrica pontos de função",
    "seguranca": "segurança vigilância patrimonial Polícia Federal vigilante curso de formação posto armado arma central de monitoramento periculosidade",
    "transporte": "transporte frota locação de veículos ANTT DETRAN CRLV condutor CNH categoria rastreamento manutenção preventiva",
    "alimentacao": "alimentação refeições nutricionista CRN vigilância sanitária boas práticas de fabricação RDC 216 cozinha industrial cadeia de frio transporte térmico",
}
_TERMOS_CONTRATACAO_DIRETA = ("dispensa inexigibilidade contratação direta aviso valor fracionamento "
                              "inviabilidade de competição notória especialização fornecedor exclusivo")


def eh_contratacao_direta(modalidade):
    m = (modalidade or "").lower()
    return "dispensa" in m or "inexigib" in m


def _termos_setoriais(tipo_objeto, segmento):
    return f"{_TERMOS_TIPO_OBJETO.get(tipo_objeto, '')} {_TERMOS_SEGMENTO.get(segmento, '')}".strip()


def _data_iso(v):
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v)[:16])
    except ValueError:
        return None


def _verificar(texto, itens, familia_principal):
    """Envia os apontamentos para outra IA conferir. Devolve (mapa id->verificação, resposta)."""
    if not itens:
        return {}, None
    s, u, demo = prompts.verificacao(cortar(texto), itens)
    r = llm.chamar("verificacao", s, u, max_tokens=3000, demo=demo, evitar_familia=familia_principal)
    try:
        dados = llm.extrair_json(r.texto)
        mapa = {str(v.get("id")): {"confirmado": bool(v.get("confirmado")), "comentario": v.get("comentario", ""),
                                  "modelo": r.modelo} for v in dados.get("verificacoes", [])}
    except Exception as e:
        log.warning("Verificação ilegível: %s", e)
        mapa = {}
    return mapa, r


# ---------------------------------------------------------------- edital
def _etapa(analise, texto):
    if analise is not None:
        analise.etapa = texto
        db.session.commit()


def analisar_edital(edital, empresa, analise=None):
    """Roda as três etapas. Com `analise` (registro em processamento), preenche esse registro e
    atualiza a etapa a cada passo, para a tela mostrar o andamento."""
    if not edital.texto:
        raise ErroAPI("Este edital ainda não tem texto. Envie o PDF do edital para analisar.")
    texto = cortar(edital.texto)

    # 1) Extração estruturada com a IA mais barata
    _etapa(analise, "Lendo o edital e extraindo os dados")
    s, u, demo = prompts.extracao_edital(texto)
    r_ext = llm.chamar("barata", s, u, max_tokens=4000, demo=demo)
    extracao = llm.extrair_json(r_ext.texto)

    # Completa o cadastro do edital com o que foi extraído
    for campo in ("orgao", "numero", "objeto", "modalidade", "portal_disputa", "tipo_objeto", "segmento"):
        if not getattr(edital, campo) and extracao.get(campo):
            setattr(edital, campo, str(extracao[campo])[:300])
    if not edital.valor_estimado and isinstance(extracao.get("valor_estimado"), (int, float)):
        edital.valor_estimado = float(extracao["valor_estimado"])
    if not edital.data_abertura and _data_iso(extracao.get("data_abertura")):
        edital.data_abertura = _data_iso(extracao["data_abertura"])

    # 2) Análise jurídica com a Claude
    _etapa(analise, "Conferindo habilitação e cláusulas")
    ref = edital.data_abertura.date() if edital.data_abertura else date.today()
    cofre = [{"tipo": d.tipo, "categoria": d.categoria, "validade": d.validade.isoformat() if d.validade else None,
              "situacao_na_sessao": d.situacao(ref)} for d in Documento.query.filter_by(empresa_id=empresa.id)]
    contexto = kb.buscar(f"habilitação impugnação esclarecimento restritiva {edital.objeto or ''} "
                         f"{empresa.porte} microempresa atestado índices "
                         f"{_termos_setoriais(extracao.get('tipo_objeto'), extracao.get('segmento'))} "
                         f"{_TERMOS_CONTRATACAO_DIRETA if eh_contratacao_direta(extracao.get('modalidade')) else ''}",
                         k=6)
    s, u, demo = prompts.analise_edital(texto, extracao, _empresa_dict(empresa), cofre, contexto)
    r_an = llm.chamar("analise", s, u, max_tokens=8000, demo=demo)
    resultado = llm.extrair_json(r_an.texto)

    # 3) Verificação cruzada das cláusulas restritivas e riscos
    itens = []
    for i, c in enumerate(resultado.get("clausulas_restritivas", [])):
        c["id"] = f"c{i}"
        itens.append({"id": c["id"], "tipo": "clausula_restritiva", **{k: c.get(k) for k in
                      ("clausula", "pagina", "por_que_restringe", "fundamento")}})
    for i, rk in enumerate(resultado.get("riscos", [])):
        rk["id"] = f"r{i}"
        itens.append({"id": rk["id"], "tipo": "risco", "tema": rk.get("tema"), "descricao": rk.get("descricao"),
                      "pagina": rk.get("pagina")})
    _etapa(analise, "Verificação cruzada com a segunda IA")
    mapa, r_ver = _verificar(texto, itens, r_an.familia)
    for lista in (resultado.get("clausulas_restritivas", []), resultado.get("riscos", [])):
        for it in lista:
            it["verificacao"] = mapa.get(it["id"], {"confirmado": None, "comentario": "Sem retorno do revisor."})

    resultado["extracao"] = extracao

    if analise is None:
        analise = Analise(edital_id=edital.id)
        db.session.add(analise)
    analise.resultado = resultado
    analise.modelos = {"extracao": r_ext.modelo, "analise": r_an.modelo, "verificacao": r_ver.modelo if r_ver else None}
    analise.demonstracao = r_an.demonstracao
    analise.status, analise.etapa, analise.erro = "concluida", None, None
    analise.concluido_em = datetime.utcnow()
    gerar_prazos_edital(edital)
    return analise, [r_ext, r_an, r_ver]


def gerar_prazos_edital(edital):
    """Cria/atualiza os prazos automáticos a partir da data de abertura.

    Em pregão/concorrência (regra geral), usa o art. 164: esclarecimento e impugnação até 3 dias úteis
    antes da sessão. Em dispensa/inexigibilidade (contratação direta), não existe sessão de disputa nem
    prazo de impugnação/recurso nesses moldes — o que existe, quando cabível, é o prazo mínimo de 3 dias
    úteis de divulgação prévia do aviso de contratação direta (art. 75, §3º), contado PARA FRENTE a partir
    da publicação (interpretamos a data de abertura cadastrada como a data de publicação do aviso, já que
    não há sessão pública para esse tipo de processo)."""
    if not edital.data_abertura:
        return
    Prazo.query.filter_by(edital_id=edital.id, automatico=True).filter(
        Prazo.tipo.in_(["esclarecimento", "impugnacao", "sessao", "aviso_contratacao_direta"])).delete(
        synchronize_session=False)
    base = {"empresa_id": edital.empresa_id, "edital_id": edital.id, "automatico": True}

    if eh_contratacao_direta(edital.modalidade):
        from services.prazos import somar_uteis
        fim_manifestacao = somar_uteis(edital.data_abertura.date(), 3)
        db.session.add(Prazo(titulo="Fim do prazo de manifestação sobre o aviso de contratação direta",
                             data=fim_do_dia(fim_manifestacao), tipo="aviso_contratacao_direta",
                             fundamento="Lei 14.133, art. 75, §3º — divulgação prévia mínima de 3 dias úteis "
                                        "antes da celebração do contrato", **base))
        return

    limite = subtrair_uteis(edital.data_abertura.date(), 3)
    db.session.add_all([
        Prazo(titulo="Último dia para pedido de esclarecimento", data=fim_do_dia(limite), tipo="esclarecimento",
              fundamento="Lei 14.133, art. 164 — até 3 dias úteis antes da abertura", **base),
        Prazo(titulo="Último dia para impugnar o edital", data=fim_do_dia(limite), tipo="impugnacao",
              fundamento="Lei 14.133, art. 164 — até 3 dias úteis antes da abertura", **base),
        Prazo(titulo="Sessão pública de disputa", data=edital.data_abertura, tipo="sessao",
              fundamento=edital.portal_disputa or "Conferir portal no edital", **base),
    ])


def gerar_prazos_recurso(edital, data_intimacao):
    from services.prazos import somar_uteis
    Prazo.query.filter_by(edital_id=edital.id, automatico=True, tipo="recurso").delete(synchronize_session=False)
    db.session.add(Prazo(empresa_id=edital.empresa_id, edital_id=edital.id, automatico=True, tipo="recurso",
                         titulo="Prazo final das razões de recurso", data=fim_do_dia(somar_uteis(data_intimacao, 3)),
                         fundamento="Lei 14.133, art. 165, I e §1º — 3 dias úteis da intimação ou da ata "
                                    "(a intenção de recorrer deve ser manifestada imediatamente na sessão)"))


# ---------------------------------------------------------------- concorrentes
def montar_dossie(cnpj):
    dados = receita(cnpj)
    return {
        "receita": dados,
        "sancoes_tcu": sancoes_tcu(cnpj),
        "sancoes_cgu": sancoes_cgu(cnpj),
        "historico_pncp": pncp.historico_fornecedor(cnpj),
        "consultado_em": datetime.utcnow().isoformat(),
    }, dados.get("razao_social")


def analisar_concorrente(edital, concorrente, tipo, texto, nome_arquivo, valor_proposta=None, engenharia=False):
    ultima = Analise.query.filter_by(edital_id=edital.id, status="concluida").order_by(Analise.id.desc()).first()
    extracao = (ultima.resultado or {}).get("extracao", {}) if ultima else {}
    exigencias = extracao.get("exigencias_habilitacao", []) if tipo == "habilitacao" else {
        "especificacoes": extracao.get("exigencias_tecnicas_objeto", []),
        "criterio": extracao.get("criterio_julgamento"), "valor_estimado": edital.valor_estimado}
    dossie = concorrente.dossie or {}
    dossie_resumo = {"receita": {k: (dossie.get("receita") or {}).get(k) for k in
                                 ("razao_social", "situacao", "abertura", "capital_social", "cnaes", "porte")},
                     "sancoes_tcu": (dossie.get("sancoes_tcu") or {}).get("certidoes"),
                     "sancoes_cgu": (dossie.get("sancoes_cgu") or {}).get("registros")}
    edital_info = {"orgao": edital.orgao, "numero": edital.numero, "objeto": edital.objeto,
                   "data_sessao": edital.data_abertura, "valor_estimado": edital.valor_estimado,
                   "engenharia": engenharia or extracao.get("obra_ou_servico_engenharia")}
    termo = "habilitação atestado certidão índices" if tipo == "habilitacao" else "exequibilidade proposta planilha"
    contexto = kb.buscar(f"{termo} recurso {edital.objeto or ''} "
                         f"{_termos_setoriais(edital.tipo_objeto, edital.segmento)}", k=5)
    texto = cortar(texto)
    from services.concorrencia import contexto_para_analise
    s, u, demo = prompts.analise_concorrente(tipo, texto, exigencias, dossie_resumo, edital_info, contexto,
                                             valor_proposta, historico=contexto_para_analise(concorrente))
    r_an = llm.chamar("analise", s, u, max_tokens=6000, demo=demo)
    resultado = llm.extrair_json(r_an.texto)

    # Regra determinística da lei: obras e serviços de engenharia abaixo de 75% do orçado (art. 59, §4º)
    if tipo == "proposta" and valor_proposta and edital.valor_estimado:
        pct = round(valor_proposta / edital.valor_estimado * 100, 2)
        resultado["percentual_do_estimado"] = pct
        if edital_info["engenharia"] and pct < 75:
            resultado.setdefault("apontamentos", []).insert(0, {
                "tema": "Inexequibilidade presumida",
                "descricao": f"Proposta equivale a {pct}% do valor orçado, abaixo de 75%.",
                "documento": "Proposta", "pagina": "", "fundamento": "Lei 14.133, art. 59, §4º; Súmula TCU 262 "
                "(presunção relativa: a licitante pode demonstrar exequibilidade)", "forca": "forte",
                "regra_automatica": True})

    # Dossiê público: sanções e situação cadastral viram apontamentos objetivos
    rec = dossie.get("receita") or {}
    if rec.get("situacao") and str(rec["situacao"]).upper() != "ATIVA":
        resultado.setdefault("apontamentos", []).insert(0, {
            "tema": "Situação cadastral", "descricao": f"CNPJ com situação '{rec['situacao']}' na Receita Federal.",
            "documento": "Consulta pública Receita Federal", "pagina": "", "fundamento": "Lei 14.133, art. 68, I",
            "forca": "forte", "regra_automatica": True})
    for s_ in (dossie.get("sancoes_cgu") or {}).get("registros", []):
        resultado.setdefault("apontamentos", []).insert(0, {
            "tema": f"Sanção registrada no {s_.get('cadastro')}",
            "descricao": f"{s_.get('tipo')} aplicada por {s_.get('orgao')} ({s_.get('inicio')} a {s_.get('fim')}). "
                         "Verificar se a sanção alcança este órgão e se está vigente.",
            "documento": "Portal da Transparência", "pagina": "", "fundamento": "Lei 14.133, arts. 14, III e 156",
            "forca": "forte", "regra_automatica": True})

    # Verificação cruzada: só o que for confirmado entra no parecer
    aps = resultado.get("apontamentos", [])
    for i, a in enumerate(aps):
        a["id"] = f"a{i}"
    para_verificar = [{"id": a["id"], **{k: a.get(k) for k in ("tema", "descricao", "documento", "pagina",
                                                                "fundamento")}}
                      for a in aps if not a.get("regra_automatica")]
    mapa, r_ver = _verificar(texto, para_verificar, r_an.familia)
    confirmados, descartados = [], []
    for a in aps:
        if a.get("regra_automatica"):
            a["verificacao"] = {"confirmado": True, "comentario": "Regra objetiva / dado público.", "modelo": "regra"}
        else:
            a["verificacao"] = mapa.get(a["id"], {"confirmado": False, "comentario": "Sem confirmação do revisor."})
        (confirmados if a["verificacao"]["confirmado"] else descartados).append(a)
    ordem = {"forte": 0, "medio": 1, "fraco": 2}
    resultado["apontamentos"] = sorted(confirmados, key=lambda a: ordem.get(a.get("forca"), 3))
    resultado["descartados"] = descartados
    # Sugestões de peça (recurso, contrarrazões...) combinando apontamentos confirmados e histórico do concorrente
    for i, sg in enumerate(resultado.get("sugestoes") or []):
        sg["id"] = f"s{i}"
        sg["descricao"] = sg.get("argumento")
    for i, cz in enumerate(resultado.get("cruzamentos_historico") or []):
        cz["id"] = f"h{i}"
        cz["descricao"] = f"{cz.get('o_que_o_historico_mostra', '')} Conferir: {cz.get('o_que_conferir_no_documento_atual', '')}".strip()
    resultado["usou_historico"] = bool(concorrente.perfil)
    if concorrente.perfil:
        concorrente.perfil_status = "desatualizado"  # a nova análise ainda não entrou no dossiê consolidado

    ac = AnaliseConcorrente(edital_id=edital.id, concorrente_id=concorrente.id, tipo=tipo, nome_arquivo=nome_arquivo,
                            resultado=resultado, demonstracao=r_an.demonstracao,
                            modelos={"analise": r_an.modelo, "verificacao": r_ver.modelo if r_ver else None})
    db.session.add(ac)
    return ac, [r_an, r_ver]


# ---------------------------------------------------------------- peças
def gerar_peca(tipo, empresa, referencia, pontos, instrucoes):
    termos = {"esclarecimento": "esclarecimento impugnação edital prazo", "impugnacao": "impugnação restritiva competitividade",
              "intencao_recurso": "intenção recorrer recurso", "recurso": "recurso habilitação inabilitação proposta",
              "contrarrazoes": "contrarrazões recurso", "reequilibrio": "reequilíbrio econômico financeiro reajuste",
              "cobranca_pagamento": "pagamento atraso ordem cronológica", "defesa_previa": "sanções defesa multa impedimento"}
    setoriais = _termos_setoriais(referencia.get("tipo_objeto"), referencia.get("segmento"))
    contexto = kb.buscar(f"{termos.get(tipo, tipo)} {setoriais} " + " ".join(str(p) for p in pontos or [])[:500], k=5)
    s, u, demo = prompts.peca(tipo, _empresa_dict(empresa), referencia, pontos, instrucoes, contexto)
    r = llm.chamar("redacao", s, u, max_tokens=6000, json_saida=False, demo=demo)
    return r.texto.strip(), r


# ---------------------------------------------------------------- radar
def atualizar_radar(empresa, usar_ia=True):
    if not (empresa.palavras_chave or "").strip():
        raise ErroAPI("Cadastre as palavras-chave de atuação da empresa para usar o radar.")
    encontrados = pncp.buscar_editais_abertos(empresa.palavras_chave, empresa.ufs or None)
    existentes = {r.numero_controle for r in RadarItem.query.filter_by(empresa_id=empresa.id)}
    novos = [e for e in encontrados if e["numero_controle"] not in existentes]
    if empresa.valor_max:
        novos = [e for e in novos if not e.get("valor_estimado") or e["valor_estimado"] <= empresa.valor_max]
    if empresa.valor_min:
        novos = [e for e in novos if not e.get("valor_estimado") or e["valor_estimado"] >= empresa.valor_min]
    respostas = []
    notas = {}
    if usar_ia and novos:
        for i in range(0, len(novos), 25):
            lote = [{"numero_controle": e["numero_controle"], "objeto": e["objeto"][:400], "uf": e["uf"],
                     "valor": e.get("valor_estimado")} for e in novos[i:i + 25]]
            s, u, demo = prompts.pontuar_radar(_empresa_dict(empresa), lote)
            try:
                r = llm.chamar("barata", s, u, max_tokens=3000, demo=demo)
                respostas.append(r)
                for n in llm.extrair_json(r.texto).get("notas", []):
                    notas[n.get("numero_controle")] = n
            except Exception as e:
                log.warning("Pontuação do radar falhou: %s", e)
    for e in novos:
        n = notas.get(e["numero_controle"], {})
        db.session.add(RadarItem(empresa_id=empresa.id, numero_controle=e["numero_controle"], dados=e,
                                 nota=n.get("nota"), motivo=n.get("motivo") or f"Contém '{e.get('termo', '')}'"))
    return len(novos), respostas


def limpar_radar_antigo(dias=45):
    corte = datetime.utcnow() - timedelta(days=dias)
    RadarItem.query.filter(RadarItem.criado_em < corte, RadarItem.status != "acompanhando").delete(
        synchronize_session=False)
