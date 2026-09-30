"""Prospecção ativa com a própria inteligência do Kasiski: quem vence licitações é quem precisa do Kasiski.

Ciclo: dados públicos do PNCP (contratos e atas de um segmento) → empresas vencedoras (CNPJ) → classificação por
segmento, volume, órgãos atendidos e recorrência → dados cadastrais públicos da Receita (porte, CNAE, contato da
empresa) → Lead Score Kasiski (aderência ao produto) → lista de abordagem por LinkedIn/telefone, relatório gratuito
personalizado e envio ao CRM de leads.

LGPD: só dados de PESSOA JURÍDICA e dados manifestamente públicos (PNCP, QSA da Receita), tratados com base no
legítimo interesse (art. 7º, IX e §4º) para prospecção B2B. Não enviamos e-mail em massa por este módulo. Quem pedir
para não ser contatado vira "nao_contatar" e nunca mais entra em lista (art. 18, §2º — oposição).
"""
import logging
import re
import secrets
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta

from extensions import db
from models import BuscaProspeccao, Conta, Empresa, Lead, Prospect

log = logging.getLogger(__name__)

POR_PAGINA = 50
MAX_DOCS_POR_TERMO = 150
MAX_ENRIQUECER = 120
PRAZO_S = 600

SEGMENTOS = {  # atalhos da tela (o admin pode digitar qualquer termo)
    "limpeza": ["limpeza predial", "conservação e limpeza"],
    "obras": ["pavimentação", "reforma de prédio", "construção de"],
    "medicamentos": ["medicamentos", "material médico hospitalar"],
    "ti": ["software", "equipamentos de informática", "serviços de TI"],
    "alimentação": ["gêneros alimentícios", "merenda escolar", "refeições"],
    "transporte": ["locação de veículos", "transporte escolar"],
    "vigilância": ["vigilância patrimonial", "portaria"],
    "facilities": ["manutenção predial", "apoio administrativo terceirizado"],
    "material": ["material de expediente", "material de limpeza"],
}

STATUS = ("novo", "contatado", "respondeu", "lead", "cliente", "descartado", "nao_contatar")


def _data(v):
    try:
        return datetime.fromisoformat(str(v).replace("Z", "")[:19]) if v else None
    except ValueError:
        return None


# ---------------------------------------------------------------- 1) coleta no PNCP
def coletar(termos, ufs, meses, etapa=lambda t: None, limite_tempo=None):
    """Contratos e atas recentes dos termos → {cnpj: agregados}. Tolerante a falhas do PNCP."""
    from services import pncp
    desde = datetime.utcnow() - timedelta(days=30 * meses)
    limite_tempo = limite_tempo or (datetime.utcnow() + timedelta(seconds=PRAZO_S))
    docs = {}
    for termo in termos:
        for tipo in ("contrato", "ata"):
            pagina = 0
            while pagina * POR_PAGINA < MAX_DOCS_POR_TERMO and datetime.utcnow() < limite_tempo:
                pagina += 1
                try:
                    lote = pncp.buscar_documentos(termo, tipo, POR_PAGINA, pagina=pagina, ufs=ufs or None)
                except Exception as e:
                    log.info("Prospecção: busca %s/%s p%s falhou: %s", termo, tipo, pagina, e)
                    break
                novos = 0
                for d in lote:
                    dt = _data(d.get("data"))
                    if d.get("numero_controle") and (not dt or dt >= desde) and d["numero_controle"] not in docs:
                        d["termo"] = termo
                        docs[d["numero_controle"]] = d
                        novos += 1
                antigos = [d for d in lote if _data(d.get("data")) and _data(d.get("data")) < desde]
                if len(lote) < POR_PAGINA or len(antigos) == len(lote):
                    break
                time.sleep(0.2)
    etapa(f"Identificando os vencedores de {len(docs)} contratação(ões)")

    def vencedores(doc):
        if doc["tipo"] == "contrato":
            f = pncp.fornecedor_do_contrato(doc["numero_controle"])
            return doc, [f] if f else []
        res = pncp.resultados_da_compra(doc.get("numero_controle_compra") or doc["numero_controle"], max_itens=6)
        venc = {}
        for r in res:
            v = venc.setdefault(r["cnpj"], {"cnpj": r["cnpj"], "nome": r["nome"], "valor": 0.0})
            v["valor"] += r.get("valor_total") or 0
        return doc, list(venc.values())

    empresas = {}
    restante = max(30, (limite_tempo - datetime.utcnow()).total_seconds())
    with ThreadPoolExecutor(max_workers=6) as ex:
        futuros = [ex.submit(vencedores, d) for d in docs.values()]
        try:
            for fut in as_completed(futuros, timeout=restante):
                try:
                    doc, lista = fut.result()
                except Exception:
                    continue
                for f in lista:
                    e = empresas.setdefault(f["cnpj"], {"cnpj": f["cnpj"], "nome": "", "contratos": 0, "atas": 0, "valor": 0.0,
                                                         "orgaos": defaultdict(int), "ufs": set(), "meses": set(), "datas": [],
                                                         "termos": set(), "exemplos": []})
                    e["nome"] = e["nome"] or (f.get("nome") or "").strip()
                    e["contratos" if doc["tipo"] == "contrato" else "atas"] += 1
                    e["valor"] += float(f.get("valor") or doc.get("valor") or 0)
                    orgao = f.get("orgao") or doc.get("orgao")
                    if orgao:
                        e["orgaos"][orgao] += 1
                    uf = (f.get("uf") or doc.get("uf") or "").upper()
                    if uf:
                        e["ufs"].add(uf)
                    dt = _data(f.get("data") or doc.get("data"))
                    if dt:
                        e["datas"].append(dt.date())
                        e["meses"].add(dt.strftime("%Y-%m"))
                    e["termos"].add(doc["termo"])
                    partes = pncp.partes_controle(doc.get("numero_controle_compra") or doc["numero_controle"])
                    if len(e["exemplos"]) < 8:
                        e["exemplos"].append({"tipo": doc["tipo"], "objeto": (f.get("objeto") or doc.get("objeto") or "")[:240],
                                              "orgao": orgao, "uf": uf, "data": dt.date().isoformat() if dt else None,
                                              "valor": f.get("valor") or doc.get("valor"),
                                              "link": f"https://pncp.gov.br/app/editais/{partes[0]}/{partes[1]}/{partes[2]}" if partes else None})
        except Exception:
            log.info("Prospecção: tempo limite atingido com %s empresa(s)", len(empresas))
    return docs, empresas


# ---------------------------------------------------------------- 2) Lead Score Kasiski
def _pequena(porte):
    p = (porte or "").upper()
    return "MICRO" in p or "PEQUENO" in p or p in ("ME", "EPP", "01", "03")


def pontuar(p):
    """Aderência ao Kasiski (0–100) e os motivos, em linguagem de vendas."""
    motivos, pts = [], 0
    if p.situacao and "ATIVA" not in (p.situacao or "").upper():
        return 0, "D", [f"situação cadastral: {p.situacao}"], None
    vit = (p.contratos or 0) + (p.atas or 0)
    if vit >= 50:
        pts += 20; motivos.append(f"{vit} vitórias no período: operação grande, provavelmente com equipe própria")
    elif vit >= 16:
        pts += 30; motivos.append(f"{vit} vitórias no período: disputa licitações toda semana")
    elif vit >= 5:
        pts += 26; motivos.append(f"{vit} vitórias no período: vende ao governo com frequência")
    elif vit >= 2:
        pts += 16; motivos.append(f"{vit} vitórias no período")
    else:
        pts += 6; motivos.append("1 vitória no período")
    n_org = len(p.orgaos or {})
    pts += 20 if n_org >= 10 else 15 if n_org >= 4 else 10 if n_org >= 2 else 3
    if n_org >= 2:
        motivos.append(f"atende {n_org} órgãos diferentes")
    if p.meses_ativos and p.meses_ativos >= 4:
        pts += 5; motivos.append(f"vence em {p.meses_ativos} meses diferentes: recorrência")
    if p.ultima_vitoria:
        dias = (date.today() - p.ultima_vitoria).days
        pts += 15 if dias <= 90 else 10 if dias <= 180 else 5 if dias <= 365 else 0
        if dias <= 90:
            motivos.append(f"última vitória há {dias} dia(s)")
    if p.porte:
        if _pequena(p.porte):
            pts += 20; motivos.append("ME/EPP: costuma não ter equipe dedicada a licitações")
        elif (p.capital_social or 0) and p.capital_social < 10_000_000:
            pts += 12
        else:
            pts += 5
    else:
        pts += 10
    if len(p.ufs_atuacao or []) > 1:
        pts += 5; motivos.append(f"atua em {len(p.ufs_atuacao)} UFs: precisa de radar amplo")
    medio = (p.valor_total or 0) / vit if vit else 0
    pts += 5 if 50_000 <= medio <= 5_000_000 else 2
    if re.search(r"^(7020|8211|8219|8299|6911)", p.cnae or ""):
        motivos.append("CNAE de consultoria/apoio administrativo: pode atender vários clientes (plano Consultor)")
    score = max(0, min(100, pts))
    faixa = "A" if score >= 70 else "B" if score >= 50 else "C" if score >= 30 else "D"
    plano = ("consultor" if re.search(r"^(7020|8211|8219|8299|6911)", p.cnae or "") else
             "business" if vit >= 16 else "profissional" if vit >= 5 else "essencial")
    return score, faixa, motivos, plano


# ---------------------------------------------------------------- 3) gravação + enriquecimento
def _clientes_cnpjs():
    return {re.sub(r"\D", "", e.cnpj or "") for e in Empresa.query.with_entities(Empresa.cnpj)}


def gravar(busca, empresas):
    clientes = _clientes_cnpjs()
    salvos = []
    for cnpj, e in empresas.items():
        p = Prospect.query.filter_by(cnpj=cnpj).first()
        if not p:
            p = Prospect(cnpj=cnpj, token=secrets.token_urlsafe(18), status="novo", segmentos=[], buscas=[])
            db.session.add(p)
        elif p.status == "nao_contatar":
            continue
        p.razao_social = p.razao_social or e["nome"] or None
        # uma nova busca soma o que já se sabia da empresa (outros segmentos), sem duplicar contratos
        exemplos = {x.get("link") or x.get("objeto"): x for x in (p.exemplos or []) + e["exemplos"]}
        p.exemplos = list(exemplos.values())[:12]
        orgaos = dict(p.orgaos or {})
        for o, n in e["orgaos"].items():
            orgaos[o] = max(orgaos.get(o, 0), n)
        p.orgaos = dict(sorted(orgaos.items(), key=lambda x: -x[1])[:30])
        p.contratos = max(p.contratos or 0, e["contratos"])
        p.atas = max(p.atas or 0, e["atas"])
        p.valor_total = max(p.valor_total or 0, round(e["valor"], 2))
        p.ufs_atuacao = sorted(set(p.ufs_atuacao or []) | e["ufs"])
        p.meses_ativos = max(p.meses_ativos or 0, len(e["meses"]))
        if e["datas"]:
            p.primeira_vitoria = min([d for d in (p.primeira_vitoria,) if d] + e["datas"])
            p.ultima_vitoria = max([d for d in (p.ultima_vitoria,) if d] + e["datas"])
        p.segmentos = sorted(set(p.segmentos or []) | e["termos"])
        p.buscas = sorted(set(p.buscas or []) | {busca.id})
        if cnpj in clientes and p.status not in ("cliente",):
            p.status = "cliente"
        p.atualizado_em = datetime.utcnow()
        salvos.append(p)
    db.session.commit()
    return salvos


def enriquecer(prospects, etapa=lambda t: None, limite_tempo=None):
    """Dados cadastrais públicos (BrasilAPI/Receita): porte, CNAE, situação, contato da empresa e QSA."""
    from services.dados_publicos import receita
    limite_tempo = limite_tempo or (datetime.utcnow() + timedelta(seconds=PRAZO_S))
    for i, p in enumerate(prospects):
        if datetime.utcnow() > limite_tempo:
            break
        if p.enriquecido_em and p.enriquecido_em > datetime.utcnow() - timedelta(days=60):
            continue
        if i % 10 == 0:
            etapa(f"Consultando a Receita: {i} de {len(prospects)} empresa(s)")
        r = receita(p.cnpj)
        if r.get("status") == "ok":
            cn = (r.get("cnaes") or [{}])[0]
            p.razao_social = r.get("razao_social") or p.razao_social
            p.nome_fantasia = r.get("nome_fantasia")
            p.uf, p.municipio = r.get("uf"), r.get("municipio")
            p.porte, p.situacao, p.abertura = r.get("porte"), r.get("situacao"), r.get("abertura")
            p.capital_social = r.get("capital_social")
            p.simples = r.get("opcao_simples")
            p.cnae, p.cnae_descricao = (cn.get("codigo") or "")[:20], (cn.get("descricao") or "")[:250]
            p.telefone, p.email_empresa = r.get("telefone"), r.get("email")
            p.socios = (r.get("socios") or [])[:8]
            p.enriquecido_em = datetime.utcnow()
        time.sleep(0.4)  # a BrasilAPI limita consultas seguidas
        db.session.commit()


def buscar_contatos(p, rapido=False):
    """E-mails e site da empresa em bases públicas além do PNCP (services/contatos.py)."""
    from services import contatos
    r = contatos.buscar(p, rapido=rapido)
    p.contatos, p.site, p.email_sugerido = r["contatos"], r["site"], r["email_principal"]
    if r["telefones"] and not p.telefone:
        p.telefone = r["telefones"][0]
    p.contatos_em = datetime.utcnow()
    db.session.commit()
    return r


def repontuar(prospects):
    for p in prospects:
        p.score, p.faixa, p.motivos, p.plano_sugerido = pontuar(p)
    db.session.commit()


def executar(busca_id):
    """Tarefa em segundo plano de uma busca."""
    b = BuscaProspeccao.query.get(busca_id)
    limite = datetime.utcnow() + timedelta(seconds=PRAZO_S)

    def etapa(t):
        b.etapa = t[:160]
        db.session.commit()
    try:
        b.status = "buscando"
        etapa("Lendo contratos e atas do segmento no PNCP")
        docs, empresas = coletar(b.termos or [], b.ufs or [], b.meses or 12, etapa, limite)
        b.documentos = len(docs)
        salvos = gravar(b, empresas)
        repontuar(salvos)
        # enriquece primeiro os mais promissores pela atividade (a Receita é o passo lento)
        salvos.sort(key=lambda p: -(p.score or 0))
        alvo = [p for p in salvos if p.status != "cliente"][:min(b.limite or 100, MAX_ENRIQUECER)]
        b.status = "enriquecendo"
        enriquecer(alvo, etapa, limite + timedelta(seconds=300))
        repontuar(salvos)
        # contatos (e-mails e site) dos melhores A/B, dentro do tempo que sobrar
        fim_contatos = datetime.utcnow() + timedelta(seconds=240)
        melhores = [p for p in sorted(salvos, key=lambda p: -(p.score or 0)) if p.faixa in ("A", "B")
                    and p.status not in ("cliente", "nao_contatar") and not p.contatos_em][:20]
        for i, p in enumerate(melhores):
            if datetime.utcnow() > fim_contatos:
                break
            etapa(f"Buscando e-mails de contato: {i + 1} de {len(melhores)}")
            try:
                buscar_contatos(p)
            except Exception:
                log.exception("Falha ao buscar contatos de %s", p.cnpj)
                db.session.rollback()
        b.empresas = len(salvos)
        b.status, b.etapa, b.concluido_em = "concluida", None, datetime.utcnow()
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        log.exception("Falha na busca de prospecção %s", busca_id)
        b = BuscaProspeccao.query.get(busca_id)
        b.status, b.erro, b.etapa = "erro", "Não foi possível concluir a busca agora (PNCP ou Receita indisponível). Tente de novo.", None
        db.session.commit()


# ---------------------------------------------------------------- 4) abordagem
_PLANOS = {"essencial": "Essencial", "profissional": "Profissional", "business": "Business", "avancado": "Business", "consultor": "Consultor"}


def _brl(v):
    return ("R$ " + f"{float(v or 0):,.0f}").replace(",", ".")


def roteiro(p, link_relatorio):
    """Mensagens prontas para LinkedIn e telefone, com os números da própria empresa."""
    nome = p.nome_fantasia or (p.razao_social or "").title()
    vit = (p.contratos or 0) + (p.atas or 0)
    orgaos = list((p.orgaos or {}).keys())
    seg = (p.segmentos or ["licitações"])[0]
    gancho = f"vi no PNCP que a {nome} venceu {vit} {'contratação' if vit == 1 else 'contratações'} de {seg} nos últimos meses"
    if len(orgaos) >= 2:
        gancho += f", com {len(orgaos)} órgãos diferentes"
    linkedin = (f"Olá! Sou o Daniel, do Kasiski. {gancho[0].upper() + gancho[1:]}. Montei um relatório gratuito com o "
                f"histórico de vocês, os concorrentes do segmento e os editais abertos agora que combinam com a empresa: "
                f"{link_relatorio}\nSe fizer sentido, te mostro em 15 minutos como o Kasiski encontra e analisa esses editais por vocês.")
    conexao = f"Olá! Acompanho o mercado de {seg} em licitações e {gancho}. Gostaria de trocar uma ideia sobre isso."[:295]
    telefone = [
        f"Apresentação: \"Falo com o responsável pelas licitações da {nome}? Sou o Daniel, do Kasiski.\"",
        f"Gancho: \"{gancho[0].upper() + gancho[1:]}{f' (entre eles {orgaos[0]})' if orgaos else ''}.\"",
        "Pergunta: \"Hoje, como vocês encontram os editais e conferem a habilitação antes de participar?\"",
        "Valor: \"O Kasiski procura os editais do seu segmento todo dia no PNCP e a IA lê o edital em minutos: "
        "requisitos, riscos, documentos que faltam e preço de referência.\"",
        f"Próximo passo: \"Posso te mandar por WhatsApp ou e-mail um relatório com os editais abertos agora para vocês? "
        f"A conta é grátis e dá para experimentar o Profissional por 7 dias.\" (link: {link_relatorio})",
        "Se não quiser contato: agradeça e marque \"Não contatar\" — a empresa sai de todas as listas.",
    ]
    return {"linkedin_conexao": conexao, "linkedin_mensagem": linkedin, "telefone": telefone,
            "plano_sugerido": _PLANOS.get(p.plano_sugerido, p.plano_sugerido)}


def relatorio_publico(p):
    """Dados do relatório gratuito (só dados públicos da própria empresa e do mercado)."""
    from services import pncp
    vit = (p.contratos or 0) + (p.atas or 0)
    # concorrentes: outras empresas que venceram no mesmo segmento (dados públicos de PJ)
    conc = []
    segs = set(p.segmentos or [])
    if segs:
        for o in Prospect.query.filter(Prospect.id != p.id, Prospect.status != "nao_contatar").order_by(Prospect.score.desc()).limit(300):
            if segs & set(o.segmentos or []):
                conc.append({"nome": o.nome_fantasia or o.razao_social, "uf": o.uf, "vitorias": (o.contratos or 0) + (o.atas or 0),
                             "orgaos": len(o.orgaos or {})})
        conc = sorted(conc, key=lambda x: -x["vitorias"])[:6]
    if not p.editais_cache_em or p.editais_cache_em < datetime.utcnow() - timedelta(hours=12):
        try:
            ufs = ",".join(sorted(set([p.uf] if p.uf else []) | set((p.ufs_atuacao or [])[:3]))) or None
            abertos = pncp.buscar_editais_abertos(", ".join((p.segmentos or [])[:3]), ufs=ufs, paginas=1)
            abertos.sort(key=lambda e: -(float(e.get("valor_estimado") or 0)))
            p.editais_cache = [{k: e.get(k) for k in ("objeto", "orgao", "uf", "municipio", "valor_estimado", "data_encerramento", "link")}
                               for e in abertos[:8]]
            p.editais_cache_em = datetime.utcnow()
            db.session.commit()
        except Exception as e:
            log.info("Relatório de prospecção: editais abertos indisponíveis: %s", e)
    return {"empresa": p.nome_fantasia or p.razao_social, "razao_social": p.razao_social, "uf": p.uf, "municipio": p.municipio,
            "segmentos": p.segmentos or [], "vitorias": vit, "contratos": p.contratos, "atas": p.atas,
            "valor_total": p.valor_total, "orgaos": [{"nome": k, "vitorias": v} for k, v in list((p.orgaos or {}).items())[:8]],
            "n_orgaos": len(p.orgaos or {}), "ufs": p.ufs_atuacao or [], "meses_ativos": p.meses_ativos,
            "ultima_vitoria": p.ultima_vitoria.isoformat() if p.ultima_vitoria else None,
            "exemplos": (p.exemplos or [])[:6], "concorrentes": conc, "editais_abertos": p.editais_cache or []}


def registrar_visita(p):
    from services import marketing
    primeira = not p.relatorio_visto_em
    p.relatorio_visitas = (p.relatorio_visitas or 0) + 1
    p.relatorio_visto_em = datetime.utcnow()
    if primeira:
        marketing.registrar("prospect_report_view", lead=Lead.query.get(p.lead_id) if p.lead_id else None,
                            dados={"prospect_id": p.id, "cnpj": p.cnpj})
    db.session.commit()


def enviar_ao_crm(p, responsavel=None):
    """Cria (ou liga) o lead no CRM de marketing, com canal 'outbound'."""
    if p.status == "nao_contatar":
        return None
    lead = Lead.query.get(p.lead_id) if p.lead_id else None
    if not lead and p.email_empresa:
        lead = Lead.query.filter_by(email=p.email_empresa).first()
    if not lead:
        lead = Lead(token=secrets.token_urlsafe(20), status="novo", score=0)
        db.session.add(lead)
    lead.empresa = lead.empresa or p.nome_fantasia or p.razao_social
    lead.cnpj = lead.cnpj or p.cnpj
    lead.telefone = lead.telefone or p.telefone
    lead.email = lead.email or p.email_empresa
    lead.uf, lead.cidade = lead.uf or p.uf, lead.cidade or p.municipio
    lead.segmento = lead.segmento or ", ".join((p.segmentos or [])[:2])[:80]
    lead.origem = lead.origem or "prospeccao_pncp"
    lead.canal = lead.canal or "outbound"
    lead.lead_magnet = lead.lead_magnet or "prospeccao"
    lead.responsavel = lead.responsavel or responsavel
    lead.notas = ((lead.notas or "") + f"\nProspecção PNCP: score {p.score} ({p.faixa}), {(p.contratos or 0) + (p.atas or 0)} vitórias, "
                  f"{len(p.orgaos or {})} órgãos. Plano sugerido: {_PLANOS.get(p.plano_sugerido, '')}.").strip()
    lead.atualizado_em = datetime.utcnow()
    db.session.flush()
    p.lead_id = lead.id
    if p.status in ("novo", "contatado", "respondeu"):
        p.status = "lead"
    db.session.commit()
    return lead


def vincular_cadastro(empresa):
    """Chamado quando um cliente cadastra a empresa: se ela veio da prospecção, fecha o ciclo."""
    cnpj = re.sub(r"\D", "", empresa.cnpj or "")
    p = Prospect.query.filter_by(cnpj=cnpj).first() if len(cnpj) == 14 else None
    if not p:
        return None
    p.status, p.conta_id = "cliente", empresa.conta_id
    if p.lead_id:
        lead = Lead.query.get(p.lead_id)
        if lead and not lead.conta_id:
            lead.conta_id = empresa.conta_id
    return p
