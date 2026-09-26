"""Gestão de contratos: leitura do PDF pela IA, rotinas de gestão (medição, faturamento, comprovações)
e prazos preventivos na agenda (vigência, prorrogação, garantia, reajuste)."""
import calendar
from datetime import date, datetime, timedelta

from extensions import db
from models import Prazo
from services import llm
from services.fluxos import cortar
from services.prazos import fim_do_dia
from services.prompts import BASE

PERIODOS = {"mensal": 1, "bimestral": 2, "trimestral": 3, "semestral": 6, "anual": 12}
OCORRENCIAS_A_FRENTE = 3   # quantas próximas ocorrências de cada rotina ficam na agenda


# ---------------------------------------------------------------- leitura do contrato (IA)
def prompt_leitura(texto):
    sistema = BASE + (" Sua tarefa é EXTRAIR de um contrato administrativo (e de seus anexos, se houver) os dados "
                      "necessários à GESTÃO do contrato pela empresa contratada, sem opinar.")
    usuario = f"""Extraia do contrato abaixo, em JSON:
{{
 "numero": "", "orgao": "", "processo": "", "objeto": "", "valor_total": null, "valor_mensal": null,
 "data_assinatura": "AAAA-MM-DD ou null", "inicio_vigencia": "AAAA-MM-DD ou null", "fim_vigencia": "AAAA-MM-DD ou null",
 "prazo_vigencia": "", "servico_continuo": false, "prorrogavel": false, "regras_prorrogacao": "",
 "regime_execucao": "", "data_base_reajuste": "AAAA-MM-DD ou null (data do orçamento estimado ou da proposta, conforme o contrato)",
 "indice_reajuste": "", "repactuacao": false,
 "garantia": {{"exigida": false, "modalidade": "", "percentual": null, "valor": null, "validade": "AAAA-MM-DD ou null", "prazo_apresentacao": ""}},
 "pagamento": {{"prazo_dias": null, "condicoes": "", "documentos_para_pagamento": [""]}},
 "medicao": {{"periodicidade": "mensal|quinzenal|por etapa|outra|nao se aplica", "dia_ou_prazo": "", "prazo_ateste_dias": null, "como": ""}},
 "faturamento": {{"periodicidade": "", "prazo": "", "documentos": [""]}},
 "fiscal": "", "gestor": "",
 "obrigacoes_periodicas": [{{"descricao": "rotina que a CONTRATADA deve cumprir", "periodicidade": "mensal|bimestral|trimestral|semestral|anual|unica",
    "dia_do_mes": null, "prazo": "texto do contrato (ex.: até o 5º dia útil)", "fundamento": "cláusula", "pagina": ""}}],
 "penalidades": [""], "pontos_de_atencao": [""]
}}
Inclua em "obrigacoes_periodicas" o que o contrato exigir periodicamente da contratada: medição, emissão da nota fiscal,
comprovação de recolhimentos (FGTS, INSS, folha) nos contratos com mão de obra, relatórios, renovação de seguros,
ART, apresentação de garantia, reuniões de acompanhamento etc. Use null quando não constar. Indique a página ([pág. N]).

CONTRATO:
{texto}"""
    demo = {
        "numero": "Contrato 112/2026", "orgao": "Prefeitura Municipal de Exemplo", "processo": "PE 45/2026",
        "objeto": "Prestação de serviços contínuos de limpeza e conservação predial", "valor_total": 1790000.0,
        "valor_mensal": 149166.67, "data_assinatura": None, "inicio_vigencia": date.today().replace(day=1).isoformat(),
        "fim_vigencia": (date.today().replace(day=1) + timedelta(days=364)).isoformat(), "prazo_vigencia": "12 meses",
        "servico_continuo": True, "prorrogavel": True, "regras_prorrogacao": "Até 10 anos, com vantajosidade (arts. 106 e 107)",
        "regime_execucao": "Empreitada por preço unitário", "data_base_reajuste": date.today().replace(month=1, day=1).isoformat(),
        "indice_reajuste": "Repactuação pela CCT (mão de obra) e IPCA (insumos)", "repactuacao": True,
        "garantia": {"exigida": True, "modalidade": "Seguro-garantia", "percentual": 5, "valor": 89500.0,
                     "validade": (date.today().replace(day=1) + timedelta(days=455)).isoformat(),
                     "prazo_apresentacao": "10 dias úteis após a assinatura"},
        "pagamento": {"prazo_dias": 30, "condicoes": "Até 30 dias após o atesto da nota fiscal",
                      "documentos_para_pagamento": ["Nota fiscal", "Certidões de regularidade fiscal e trabalhista", "Folha e comprovantes de FGTS/INSS"]},
        "medicao": {"periodicidade": "mensal", "dia_ou_prazo": "Até o 5º dia útil do mês seguinte", "prazo_ateste_dias": 10,
                    "como": "Relatório de postos efetivamente cobertos, com glosas"},
        "faturamento": {"periodicidade": "mensal", "prazo": "Após o ateste da medição", "documentos": ["Nota fiscal de serviço"]},
        "fiscal": "Servidor designado por portaria", "gestor": "Secretaria de Administração",
        "obrigacoes_periodicas": [
            {"descricao": "Entregar a medição mensal dos serviços", "periodicidade": "mensal", "dia_do_mes": 5, "prazo": "Até o 5º dia útil", "fundamento": "Cláusula 8ª", "pagina": "6"},
            {"descricao": "Emitir a nota fiscal após o ateste", "periodicidade": "mensal", "dia_do_mes": 15, "prazo": "Após o ateste", "fundamento": "Cláusula 9ª", "pagina": "7"},
            {"descricao": "Comprovar pagamento de salários, FGTS e INSS dos empregados", "periodicidade": "mensal", "dia_do_mes": 10, "prazo": "Junto com a nota fiscal", "fundamento": "Cláusula 11ª; Lei 14.133, art. 121", "pagina": "9"},
            {"descricao": "Renovar a garantia contratual antes do vencimento", "periodicidade": "anual", "dia_do_mes": None, "prazo": "30 dias antes do vencimento", "fundamento": "Cláusula 14ª", "pagina": "11"},
        ],
        "penalidades": ["Multa de 0,5% ao dia de atraso", "Glosa por posto descoberto"],
        "pontos_de_atencao": ["Repactuação depende de pedido da contratada após o registro da nova CCT"],
    }
    return sistema, usuario, demo


def _data(v):
    if not v:
        return None
    try:
        return datetime.strptime(str(v)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _num(v):
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def ler_contrato(contrato):
    s, u, demo = prompt_leitura(cortar(contrato.texto))
    r = llm.chamar("barata", s, u, max_tokens=6000, demo=demo)
    d = llm.extrair_json(r.texto)
    # só preenche o que o usuário ainda não informou
    campos = {"numero": d.get("numero"), "orgao": d.get("orgao"), "objeto": d.get("objeto"),
              "indice_reajuste": d.get("indice_reajuste")}
    for k, v in campos.items():
        if v and not getattr(contrato, k):
            setattr(contrato, k, str(v)[:300] if k != "objeto" else str(v))
    if not contrato.valor and _num(d.get("valor_total")):
        contrato.valor = _num(d["valor_total"])
    for k, chave in (("inicio", "inicio_vigencia"), ("fim", "fim_vigencia"), ("data_base_reajuste", "data_base_reajuste")):
        if not getattr(contrato, k) and _data(d.get(chave)):
            setattr(contrato, k, _data(d[chave]))
    gar = d.get("garantia") or {}
    if not contrato.garantia_validade and _data(gar.get("validade")):
        contrato.garantia_validade = _data(gar["validade"])
    obrig = []
    for o in (d.get("obrigacoes_periodicas") or [])[:30]:
        if not str(o.get("descricao") or "").strip():
            continue
        per = str(o.get("periodicidade") or "").lower()
        dia = o.get("dia_do_mes")
        obrig.append({"descricao": str(o["descricao"])[:300], "periodicidade": per if per in PERIODOS or per == "unica" else "mensal",
                      "dia_do_mes": int(dia) if isinstance(dia, (int, float)) and 1 <= int(dia) <= 31 else None,
                      "prazo": str(o.get("prazo") or "")[:200], "fundamento": str(o.get("fundamento") or "")[:200],
                      "pagina": str(o.get("pagina") or ""), "ativa": True})
    contrato.dados_ia = d
    if obrig or not contrato.obrigacoes:
        contrato.obrigacoes = obrig
    return [r]


# ---------------------------------------------------------------- prazos na agenda
def _somar_meses(d, n):
    m = d.month - 1 + n
    a, m = d.year + m // 12, m % 12 + 1
    return date(a, m, min(d.day, calendar.monthrange(a, m)[1]))


def _mais_um_ano(d):
    return _somar_meses(d, 12)


def _ocorrencias(o, inicio, fim, hoje, cadastro=None):
    """Próximas datas de uma rotina periódica, dentro da vigência."""
    if o.get("periodicidade") == "unica" or not o.get("ativa", True):
        return []
    passo = PERIODOS.get(o.get("periodicidade"), 1)
    dia = o.get("dia_do_mes") or 10
    base = inicio or hoje
    atual = date(base.year, base.month, min(dia, calendar.monthrange(base.year, base.month)[1]))
    if atual < base:
        atual = _somar_meses(atual, 1)
    saida, guarda, futuras = [], 0, 0
    # mantém visível a ocorrência do último mês ainda não concluída, mas nada anterior ao cadastro do contrato
    desde = max(hoje - timedelta(days=31), cadastro or hoje)
    while futuras < OCORRENCIAS_A_FRENTE and guarda < 400:
        guarda += 1
        if fim and atual > fim:
            break
        if atual >= desde:
            saida.append(atual)
            futuras += atual >= hoje
        atual = _somar_meses(date(atual.year, atual.month, 1), passo)
        atual = atual.replace(day=min(dia, calendar.monthrange(atual.year, atual.month)[1]))
    return saida


def gerar_prazos(c):
    """Recria os prazos automáticos do contrato (os manuais e os já concluídos são preservados)."""
    Prazo.query.filter_by(contrato_id=c.id, automatico=True, concluido=False).delete(synchronize_session=False)
    concluidos = {(p.titulo, p.data.date()) for p in Prazo.query.filter_by(contrato_id=c.id, automatico=True, concluido=True)}
    base = {"empresa_id": c.empresa_id, "contrato_id": c.id, "automatico": True}
    num = (c.numero or str(c.id)).strip()
    nome = num if num.lower().startswith(("contrato", "ata", "termo")) else f"Contrato {num}"
    hoje = date.today()
    cadastro = c.criado_em.date() if c.criado_em else hoje
    dados = c.dados_ia or {}
    novos = []

    def add(titulo, dia, tipo, fundamento):
        if dia and (titulo, dia) not in concluidos:
            novos.append(Prazo(titulo=titulo, data=fim_do_dia(dia), tipo=tipo, fundamento=fundamento, **base))

    if c.fim:
        prorrogavel = dados.get("prorrogavel") or dados.get("servico_continuo")
        if prorrogavel:
            add(f"{nome}: decidir a prorrogação (faltam 120 dias)", c.fim - timedelta(days=120), "prorrogacao",
                "Manifestar interesse e reunir documentos com antecedência (Lei 14.133, arts. 106 e 107)")
            add(f"{nome}: confirmar termo aditivo de prorrogação (faltam 60 dias)", c.fim - timedelta(days=60), "prorrogacao",
                "Sem aditivo assinado até o fim da vigência, o contrato se extingue")
        else:
            add(f"{nome}: vigência termina em 60 dias", c.fim - timedelta(days=60), "vigencia",
                "Planejar a desmobilização e o faturamento final")
        add(f"{nome}: fim da vigência", c.fim, "vigencia", "Lei 14.133, arts. 105 a 107")
    if c.garantia_validade:
        add(f"{nome}: renovar a garantia (faltam 30 dias)", c.garantia_validade - timedelta(days=30), "garantia",
            "A garantia deve cobrir toda a vigência e as prorrogações (Lei 14.133, art. 96 e seguintes)")
        add(f"{nome}: vencimento da garantia", c.garantia_validade, "garantia", "Lei 14.133, art. 96")
    if c.data_base_reajuste:
        alvo = _mais_um_ano(c.data_base_reajuste)
        while alvo < hoje:
            alvo = _mais_um_ano(alvo)
        tipo_r = "repactuação" if dados.get("repactuacao") else "reajuste"
        add(f"{nome}: preparar o pedido de {tipo_r} (faltam 30 dias)", alvo - timedelta(days=30), "reajuste",
            "Reunir índices/CCT e a memória de cálculo")
        add(f"{nome}: aniversário para {tipo_r}", alvo, "reajuste",
            "Anualidade contada da data do orçamento estimado (Lei 14.133, art. 25, §7º; art. 92, V; art. 135)")
    for o in c.obrigacoes or []:
        if c.garantia_validade and "garantia" in o["descricao"].lower() and o.get("periodicidade") == "anual":
            continue  # já coberto pelos prazos de garantia acima
        for dia in _ocorrencias(o, c.inicio, c.fim, hoje, cadastro):
            tipo = "medicao" if "medi" in o["descricao"].lower() else "faturamento" if ("nota" in o["descricao"].lower() or "fatur" in o["descricao"].lower()) else "obrigacao"
            add(f"{nome}: {o['descricao']}", dia, tipo, " · ".join(x for x in (o.get("prazo"), o.get("fundamento")) if x))
    db.session.add_all(novos)
    return len(novos)


# ---------------------------------------------------------------- aviso diário por e-mail
def resumo_avisos(conta_id, dias=7):
    """Prazos de gestão de contratos em aberto: vencidos e dos próximos `dias` dias."""
    from models import Contrato, Empresa
    ids = [e.id for e in Empresa.query.filter_by(conta_id=conta_id)]
    if not ids:
        return []
    limite = datetime.combine(date.today() + timedelta(days=dias), datetime.max.time())
    q = Prazo.query.filter(Prazo.empresa_id.in_(ids), Prazo.contrato_id.isnot(None), Prazo.concluido.is_(False),
                           Prazo.data <= limite, Prazo.data >= datetime.utcnow() - timedelta(days=15))
    return q.order_by(Prazo.data).all()
