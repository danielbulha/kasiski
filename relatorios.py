"""Indicadores de gestão: carteira de contratos e relatório executivo (alta administração)."""
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

from models import Analise, Contrato, Edital, Empresa, Movimento, Pagamento, Peca, Prazo, Proposta
from services import oportunidades as op

VITORIA = {"homologada", "contratacao", "contrato_ativo"}
DISPUTA = {"em_disputa", "classificada", "recurso"}
ATIVAS = set(op.ORDEM) - {"contrato_ativo"}


def _aniversario(base, hoje):
    """Próxima data de aniversário (reajuste anual) a partir da data-base."""
    if not base:
        return None
    for ano in (hoje.year, hoje.year + 1):
        try:
            d = base.replace(year=ano)
        except ValueError:
            d = base.replace(year=ano, day=28)
        if d >= hoje:
            return d
    return None


def _mensal(c):
    ia = c.dados_ia or {}
    try:
        v = float(ia.get("valor_mensal") or 0)
    except (TypeError, ValueError):
        v = 0
    if v:
        return v
    if c.valor and c.inicio and c.fim and c.fim > c.inicio:
        meses = max(1, round((c.fim - c.inicio).days / 30.4))
        return c.valor / meses
    return 0


def carteira(empresa_ids):
    hoje = date.today()
    contratos = Contrato.query.filter(Contrato.empresa_id.in_(empresa_ids or [0])).all()
    ativos = [c for c in contratos if (not c.fim or c.fim >= hoje) and (not c.inicio or c.inicio <= hoje + timedelta(days=30))]
    encerrados = [c for c in contratos if c.fim and c.fim < hoje]
    def vence(dias):
        return [c for c in ativos if c.fim and hoje <= c.fim <= hoje + timedelta(days=dias)]
    reajustes = []
    for c in ativos:
        d = _aniversario(c.data_base_reajuste, hoje)
        if d and d <= hoje + timedelta(days=60):
            reajustes.append({"id": c.id, "numero": c.numero, "orgao": c.orgao, "data": d.isoformat(), "indice": c.indice_reajuste})
    garantias = [{"id": c.id, "numero": c.numero, "orgao": c.orgao, "data": c.garantia_validade.isoformat()}
                 for c in ativos if c.garantia_validade and c.garantia_validade <= hoje + timedelta(days=60)]
    ids = [c.id for c in contratos]
    pags = Pagamento.query.filter(Pagamento.contrato_id.in_(ids or [0])).all()
    atrasados = [p for p in pags if p.situacao() == "atrasado"]
    recebido_12m = sum(p.valor or 0 for p in pags if p.pago_em and p.pago_em >= hoje - timedelta(days=365))
    por_orgao = defaultdict(float)
    for c in ativos:
        por_orgao[c.orgao or "Órgão não informado"] += c.valor or 0
    return {
        "total": len(contratos), "ativos": len(ativos), "encerrados": len(encerrados),
        "valor_carteira": round(sum(c.valor or 0 for c in ativos), 2),
        "receita_mensal": round(sum(_mensal(c) for c in ativos), 2),
        "vencendo": {"30": len(vence(30)), "60": len(vence(60)), "90": len(vence(90)), "120": len(vence(120))},
        "vencendo_lista": [{"id": c.id, "numero": c.numero, "orgao": c.orgao, "fim": c.fim.isoformat(), "valor": c.valor,
                            "dias": (c.fim - hoje).days} for c in sorted(vence(120), key=lambda x: x.fim)],
        "reajustes": sorted(reajustes, key=lambda x: x["data"]), "garantias": sorted(garantias, key=lambda x: x["data"]),
        "pagamentos": {"recebido_12m": round(recebido_12m, 2),
                       "a_receber": round(sum(p.valor or 0 for p in pags if p.situacao() == "a_receber"), 2),
                       "atrasado": round(sum(p.valor or 0 for p in atrasados), 2), "qtd_atrasados": len(atrasados),
                       "maior_atraso_dias": max([(hoje - p.vencimento).days for p in atrasados], default=0)},
        "por_orgao": [{"orgao": o, "valor": round(v, 2)} for o, v in sorted(por_orgao.items(), key=lambda x: -x[1])[:6]],
        "leitura_pendente": sum(1 for c in contratos if c.leitura_status in ("lendo", "erro")),
    }


def executivo(empresa_ids, meses=12):
    hoje = datetime.utcnow()
    ano, mes = hoje.year, hoje.month - (meses - 1)
    while mes <= 0:
        mes += 12
        ano -= 1
    inicio = datetime(ano, mes, 1)
    eds = Edital.query.filter(Edital.empresa_id.in_(empresa_ids or [0])).all()
    etapa = {e.id: (e.etapa or op.etapa_de(e)) for e in eds}
    ativas = [e for e in eds if etapa[e.id] in ATIVAS]
    vitorias = [e for e in eds if etapa[e.id] in VITORIA]
    perdidas = [e for e in eds if etapa[e.id] == "perdida"]
    desist = [e for e in eds if etapa[e.id] == "desistencia"]
    decididas = len(vitorias) + len(perdidas)
    funil = [{"codigo": k, "nome": n, "qtd": sum(1 for e in eds if etapa[e.id] == k),
              "valor": round(sum(e.valor_estimado or 0 for e in eds if etapa[e.id] == k), 2)} for k, n, _ in op.ETAPAS + op.SAIDAS]
    # série mensal
    chaves = []
    d = inicio
    while d <= hoje:
        chaves.append(d.strftime("%Y-%m"))
        d = (d + timedelta(days=32)).replace(day=1)
    serie = {k: {"mes": k, "novas": 0, "vitorias": 0, "perdas": 0, "valor_ganho": 0.0} for k in chaves}
    for e in eds:
        k = e.criado_em.strftime("%Y-%m") if e.criado_em else None
        if k in serie:
            serie[k]["novas"] += 1
    ids = [e.id for e in eds]
    valor = {e.id: e.valor_estimado or 0 for e in eds}
    vistos = set()
    for m in Movimento.query.filter(Movimento.edital_id.in_(ids or [0]), Movimento.criado_em >= inicio).order_by(Movimento.criado_em):
        k = m.criado_em.strftime("%Y-%m")
        if k not in serie:
            continue
        if m.para in VITORIA and (m.edital_id, "v") not in vistos and etapa.get(m.edital_id) in VITORIA:
            vistos.add((m.edital_id, "v"))
            serie[k]["vitorias"] += 1
            serie[k]["valor_ganho"] += valor.get(m.edital_id, 0)
        elif m.para == "perdida" and (m.edital_id, "p") not in vistos:
            vistos.add((m.edital_id, "p"))
            serie[k]["perdas"] += 1
    motivos = Counter()
    for e in perdidas + desist:
        if e.motivo_saida:
            motivos[e.motivo_saida.strip()[:120]] += 1
    orgaos = Counter(e.orgao for e in eds if e.orgao and etapa[e.id] not in ("identificada", "desistencia"))
    prazos = Prazo.query.filter(Prazo.empresa_id.in_(empresa_ids or [0]), Prazo.concluido.is_(False),
                                Prazo.data >= hoje - timedelta(days=1), Prazo.data <= hoje + timedelta(days=15)).order_by(Prazo.data).limit(25).all()
    empresas = {e.id: e.razao_social for e in Empresa.query.filter(Empresa.id.in_(empresa_ids or [0]))}
    por_empresa = []
    for eid, nome in empresas.items():
        mine = [e for e in eds if e.empresa_id == eid]
        v = sum(1 for e in mine if etapa[e.id] in VITORIA)
        p = sum(1 for e in mine if etapa[e.id] == "perdida")
        cart = carteira([eid])
        por_empresa.append({"id": eid, "nome": nome, "ativas": sum(1 for e in mine if etapa[e.id] in ATIVAS),
                            "valor_pipeline": round(sum(e.valor_estimado or 0 for e in mine if etapa[e.id] in ATIVAS), 2),
                            "vitorias": v, "perdas": p, "taxa": round(100 * v / (v + p)) if v + p else None,
                            "contratos_ativos": cart["ativos"], "carteira": cart["valor_carteira"], "atrasado": cart["pagamentos"]["atrasado"]})
    no_periodo = lambda q, campo: q.filter(campo >= inicio).count()  # noqa: E731
    return {
        "gerado_em": hoje.isoformat(), "periodo": {"inicio": inicio.date().isoformat(), "meses": meses},
        "kpis": {"ativas": len(ativas), "valor_pipeline": round(sum(e.valor_estimado or 0 for e in ativas), 2),
                 "em_disputa": sum(1 for e in eds if etapa[e.id] in DISPUTA),
                 "vitorias": len(vitorias), "perdas": len(perdidas), "desistencias": len(desist),
                 "taxa_sucesso": round(100 * len(vitorias) / decididas) if decididas else None,
                 "valor_ganho": round(sum(e.valor_estimado or 0 for e in vitorias), 2),
                 "go": sum(1 for e in eds if e.decisao == "go"), "no_go": sum(1 for e in eds if e.decisao == "no_go")},
        "funil": funil, "serie": list(serie.values()),
        "motivos_perda": [{"motivo": m, "qtd": q} for m, q in motivos.most_common(6)],
        "orgaos": [{"orgao": o, "qtd": q} for o, q in orgaos.most_common(6)],
        "prazos": [{**p.to_dict(), "empresa": empresas.get(p.empresa_id)} for p in prazos],
        "produtividade": {"analises": no_periodo(Analise.query.filter(Analise.edital_id.in_(ids or [0]), Analise.status == "concluida"), Analise.criado_em),
                          "pecas": no_periodo(Peca.query.filter(Peca.empresa_id.in_(empresa_ids or [0])), Peca.criado_em),
                          "propostas": no_periodo(Proposta.query.filter(Proposta.empresa_id.in_(empresa_ids or [0])), Proposta.criado_em)},
        "contratos": carteira(empresa_ids), "por_empresa": por_empresa,
    }
