"""Newsletter semanal Kasiski Intelligence.

Fluxo: toda segunda-feira o agendador coleta no PNCP as contratações publicadas na semana anterior e monta um
RASCUNHO (dado da semana, setores, UFs e as 5 maiores oportunidades ainda abertas). O admin revisa no painel,
escreve o radar regulatório (opcionalmente com um rascunho da IA para a abertura) e envia ou agenda.

Envio: só para leads com inscrição confirmada e sem descadastro; 1 e-mail por inscrito por edição (restrição única),
em lotes de até 100 pelo Resend, retomável se o processo cair. Abertura (pixel), clique (redirecionamento só para
links da própria edição) e descadastro ficam registrados por envio.
"""
import html
import json
import logging
import re
import secrets
import time
import unicodedata
from collections import defaultdict
from datetime import date, datetime, timedelta

from flask import current_app
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from extensions import ErroAPI, db
from models import EdicaoNewsletter, Lead, NewsletterEnvio

log = logging.getLogger(__name__)

# modalidades da API de consulta do PNCP (codigoModalidadeContratacao)
COMPETITIVAS = [(6, "Pregão eletrônico"), (4, "Concorrência eletrônica"), (7, "Pregão presencial"), (5, "Concorrência presencial")]
CONTAGEM = [(8, "Dispensa"), (9, "Inexigibilidade"), (12, "Credenciamento"), (1, "Leilão eletrônico"), (3, "Concurso"), (2, "Diálogo competitivo")]

SETORES = [
    ("Obras e engenharia", ["obra", "paviment", "recapeamento", "construc", "reforma", "engenharia", "drenagem", "edificac", "saneamento",
                            "ponte", "asfalt", "terraplen"]),
    ("Saúde", ["medicament", "hospital", "saude", "medic", "odontolog", "exame", "laborator", "enfermagem", "farmac", "ortese", "protese"]),
    ("Tecnologia", ["software", "sistema de", "informatica", "computador", "notebook", "tecnologia da informacao", "licenca", "rede logica",
                    "nuvem", "datacenter", "impressora", "telefonia", "internet", "link de dados"]),
    ("Alimentação", ["aliment", "merenda", "refeic", "hortifruti", "carne", "lanche", "cafe", "agua mineral"]),
    ("Transporte e veículos", ["veicul", "transporte", "combustiv", "frota", "pneu", "onibus", "ambulancia", "caminhao", "motocicleta"]),
    ("Serviços e facilities", ["limpeza", "conservacao", "vigilancia", "portaria", "manutencao predial", "jardinagem", "copeiragem",
                               "recepcao", "apoio administrativo", "terceiriz", "mao de obra"]),
    ("Educação e material", ["material escolar", "uniforme", "livro", "didatic", "educac", "brinquedo", "mobiliario escolar"]),
    ("Material de consumo e expediente", ["material de expediente", "papel", "material de limpeza", "higiene", "copa e cozinha", "descartave"]),
]
OUTROS = "Outros"


# ------------------------------------------------------------------ formatação
def _norm(t):
    t = unicodedata.normalize("NFKD", (t or "").lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def setor_de(objeto):
    o = _norm(objeto)
    for nome, chaves in SETORES:
        if any(k in o for k in chaves):
            return nome
    return OUTROS


def num(v):
    return f"{int(round(v or 0)):,}".replace(",", ".")


def moeda_curta(v):
    v = float(v or 0)
    for lim, suf in ((1e9, "bi"), (1e6, "mi"), (1e3, "mil")):
        if v >= lim:
            x = v / lim
            s = f"{x:,.1f}" if x < 100 else f"{x:,.0f}"
            return f"R$ {s.replace(',', 'X').replace('.', ',').replace('X', '.')} {suf}"
    return f"R$ {v:,.0f}".replace(",", ".")


def moeda(v):
    s = f"{float(v or 0):,.2f}"
    return "R$ " + s.replace(",", "X").replace(".", ",").replace("X", ".")


def dm(d):
    return d.strftime("%d/%m") if d else ""


def esc(v):
    return html.escape(str(v if v is not None else ""))


def semana_anterior(hoje=None):
    """Segunda a domingo da semana passada."""
    hoje = hoje or date.today()
    ini = hoje - timedelta(days=hoje.weekday() + 7)
    return ini, ini + timedelta(days=6)


# ------------------------------------------------------------------ coleta no PNCP
def _pagina(modalidade, ini, fim, pagina, tamanho=50):
    from services import pncp
    params = {"dataInicial": ini.strftime("%Y%m%d"), "dataFinal": fim.strftime("%Y%m%d"),
              "codigoModalidadeContratacao": modalidade, "pagina": pagina, "tamanhoPagina": tamanho}
    return pncp._get(f"{pncp.BASE_CONSULTA}/contratacoes/publicacao", params, timeout=25) or {}


def coletar(ini, fim, max_paginas=None):
    """Métricas da semana. Contagens são exatas (totalRegistros); valores somam os registros lidos e, se a leitura
    foi parcial (limite de páginas), são extrapolados e marcados como estimativa."""
    from services import pncp
    max_paginas = max_paginas or current_app.config.get("NEWSLETTER_MAX_PAGINAS", 60)
    teto = current_app.config.get("NEWSLETTER_VALOR_MAX", 20e9)
    agora = datetime.utcnow()
    modalidades, registros, falhas = [], [], []
    for cod, nome in COMPETITIVAS:
        total, lidos, soma = 0, 0, 0.0
        try:
            p = 1
            while p <= max_paginas:
                d = _pagina(cod, ini, fim, p)
                total = int(d.get("totalRegistros") or total or 0)
                itens = d.get("data") or []
                for it in itens:
                    v = it.get("valorTotalEstimado")
                    v = float(v) if isinstance(v, (int, float)) and 0 < v < teto else 0.0
                    soma += v
                    n = pncp._normalizar(it)
                    n["valor"] = v
                    n["setor"] = setor_de(n["objeto"])
                    registros.append(n)
                lidos += len(itens)
                if not itens or p >= int(d.get("totalPaginas") or 1):
                    break
                p += 1
                time.sleep(0.15)
        except Exception as e:
            log.warning("Newsletter: falha ao ler modalidade %s: %s", cod, e)
            falhas.append(nome)
        parcial = bool(total and lidos < total)
        modalidades.append({"codigo": cod, "nome": nome, "total": total, "lidos": lidos, "valor_lido": soma,
                            "valor": soma * (total / lidos) if parcial and lidos else soma, "parcial": parcial, "competitiva": True})
    for cod, nome in CONTAGEM:
        try:
            d = _pagina(cod, ini, fim, 1, tamanho=10)
            modalidades.append({"codigo": cod, "nome": nome, "total": int(d.get("totalRegistros") or 0), "competitiva": False})
        except Exception as e:
            log.warning("Newsletter: falha ao contar modalidade %s: %s", cod, e)
            falhas.append(nome)
    comp = [m for m in modalidades if m.get("competitiva")]
    lidos = sum(m["lidos"] for m in comp)
    total_comp = sum(m["total"] for m in comp)
    fator = (total_comp / lidos) if lidos and total_comp > lidos else 1.0

    por_setor, por_uf = defaultdict(lambda: [0, 0.0]), defaultdict(lambda: [0, 0.0])
    for r in registros:
        por_setor[r["setor"]][0] += 1
        por_setor[r["setor"]][1] += r["valor"]
        if r["uf"]:
            por_uf[r["uf"]][0] += 1
            por_uf[r["uf"]][1] += r["valor"]
    setores = sorted(({"nome": k, "editais": round(c * fator), "valor": v * fator} for k, (c, v) in por_setor.items()),
                     key=lambda x: -x["valor"])
    ufs = sorted(({"uf": k, "editais": round(c * fator), "valor": v * fator} for k, (c, v) in por_uf.items()),
                 key=lambda x: -x["valor"])[:5]

    # oportunidades: maiores valores com proposta aberta por pelo menos mais 2 dias, 1 por órgão
    limite = agora + timedelta(days=2)
    candidatas, vistos = [], set()
    for r in sorted(registros, key=lambda x: -x["valor"]):
        enc = pncp._data(r.get("data_encerramento"))
        if not r["valor"] or not enc or enc < limite:
            continue
        chave = r["orgao_cnpj"] or r["orgao"]
        if chave in vistos:
            continue
        vistos.add(chave)
        candidatas.append({k: r.get(k) for k in ("numero_controle", "orgao", "objeto", "modalidade", "uf", "municipio", "valor", "setor",
                                                 "data_encerramento", "link")})
        if len(candidatas) >= 15:  # sobra para o admin trocar as que não quiser
            break

    total_geral = sum(m["total"] for m in modalidades)
    return {
        "metricas": {"publicadas": total_geral, "competitivas": total_comp,
                     "valor_competitivas": sum(m["valor"] for m in comp), "estimado": fator > 1.0,
                     "amostra": lidos},
        "modalidades": modalidades, "setores": setores, "ufs": ufs, "oportunidades": candidatas,
        "falhas": falhas,
    }


# ------------------------------------------------------------------ edições
def _anterior(ed):
    """Edição da semana imediatamente anterior (a comparação só faz sentido semana contra semana)."""
    return EdicaoNewsletter.query.filter_by(semana_inicio=ed.semana_inicio - timedelta(days=7)).first()


def variacao(ed):
    """Variação % das métricas contra a edição anterior (None se não houver base)."""
    ant = _anterior(ed)
    if not ant or not (ant.dados or {}).get("metricas") or not (ed.dados or {}).get("metricas"):
        return {}
    a, b = ant.dados["metricas"], ed.dados["metricas"]
    out = {}
    for k in ("publicadas", "competitivas", "valor_competitivas"):
        if a.get(k):
            out[k] = round((b.get(k, 0) - a[k]) / a[k] * 100, 1)
    return out


def abertura_padrao(ed):
    d = ed.dados or {}
    m = d.get("metricas") or {}
    if not m.get("publicadas"):
        return ("Não conseguimos ler os dados do PNCP desta semana. Atualize os dados antes de enviar.")
    txt = (f"Entre {dm(ed.semana_inicio)} e {dm(ed.semana_fim)}, o PNCP recebeu {num(m['publicadas'])} contratações públicas. "
           f"Dessas, {num(m['competitivas'])} são licitações com disputa (pregões e concorrências), que somam "
           f"{'cerca de ' if m.get('estimado') else ''}{moeda_curta(m['valor_competitivas'])} em valor estimado.")
    s = [x for x in d.get("setores") or [] if x["nome"] != OUTROS]
    if s:
        txt += f" {s[0]['nome']} liderou em valor, com {moeda_curta(s[0]['valor'])}."
    v = variacao(ed).get("valor_competitivas")
    if v is not None and abs(v) >= 1:
        txt += f" O valor ficou {abs(v):.0f}% {'acima' if v > 0 else 'abaixo'} da semana anterior."
    return txt


def assunto_padrao(ed):
    m = (ed.dados or {}).get("metricas") or {}
    if not m.get("valor_competitivas"):
        return f"Kasiski Intelligence #{ed.numero}"
    return f"{moeda_curta(m['valor_competitivas'])} em licitações abertas na semana e as 5 maiores oportunidades"


def oportunidades(ed, n=5):
    ocultas = set(ed.ocultas or [])
    return [o for o in ((ed.dados or {}).get("oportunidades") or []) if o.get("numero_controle") not in ocultas][:n]


def gerar_rascunho(ini=None, coletar_dados=True):
    """Cria o rascunho da semana (idempotente: uma edição por semana)."""
    if ini is None:
        ini, fim = semana_anterior()
    else:
        ini = ini - timedelta(days=ini.weekday())
        fim = ini + timedelta(days=6)
    ed = EdicaoNewsletter.query.filter_by(semana_inicio=ini).first()
    if ed:
        return ed, False
    numero = (db.session.query(func.max(EdicaoNewsletter.numero)).scalar() or 0) + 1
    ed = EdicaoNewsletter(numero=numero, semana_inicio=ini, semana_fim=fim, status="rascunho", radar=[], ocultas=[])
    db.session.add(ed)
    try:
        db.session.commit()
    except IntegrityError:  # outro processo criou ao mesmo tempo
        db.session.rollback()
        return EdicaoNewsletter.query.filter_by(semana_inicio=ini).first(), False
    if coletar_dados:
        atualizar_dados(ed)
    return ed, True


def atualizar_dados(ed):
    if ed.status not in ("rascunho", "agendada"):
        raise ErroAPI("Esta edição já foi enviada.")
    ed.dados = coletar(ed.semana_inicio, ed.semana_fim)
    ed.coletado_em = datetime.utcnow()
    padrao_antigo = not ed.abertura or ed.abertura.startswith("Não conseguimos ler") or ed.abertura.startswith("Entre ")
    ed.titulo = ed.titulo or f"O mercado público de {dm(ed.semana_inicio)} a {dm(ed.semana_fim)}"
    if padrao_antigo:
        ed.abertura = abertura_padrao(ed)
    if not ed.assunto or ed.assunto.startswith("Kasiski Intelligence #") or " em licitações abertas na semana" in ed.assunto:
        ed.assunto = assunto_padrao(ed)
    ed.pre_cabecalho = ed.pre_cabecalho or "Dado da semana, setores em alta, as maiores oportunidades e o radar regulatório."
    ed.atualizado_em = datetime.utcnow()
    db.session.commit()
    return ed


def sugerir_abertura(ed):
    """Rascunho da abertura pela IA a partir dos números (o admin revisa)."""
    from services import llm
    d = ed.dados or {}
    resumo = {"semana": f"{dm(ed.semana_inicio)} a {dm(ed.semana_fim)}", "metricas": d.get("metricas"),
              "variacao_pct": variacao(ed), "setores": (d.get("setores") or [])[:6], "ufs": d.get("ufs"),
              "maiores": [{k: o.get(k) for k in ("objeto", "orgao", "uf", "valor", "setor")} for o in oportunidades(ed)]}
    sistema = ("Você escreve a abertura da newsletter semanal Kasiski Intelligence sobre o mercado de compras públicas no Brasil. "
               "Público: empresas que vendem ao governo e consultorias de licitação. Tom: analista de mercado, objetivo, sem "
               "exageros nem adjetivos vazios. Use apenas os números fornecidos; quando 'estimado' for verdadeiro diga 'cerca de'. "
               "Não invente leis, decisões ou fatos. Escreva em português do Brasil, 2 parágrafos curtos, no máximo 110 palavras. "
               'Devolva {"abertura": "...", "assunto": "..."} com um assunto de e-mail de até 70 caracteres.')
    demo = {"abertura": abertura_padrao(ed), "assunto": assunto_padrao(ed)}
    r = llm.chamar("barata", sistema, json.dumps(resumo, ensure_ascii=False, default=str), max_tokens=700, demo=demo)
    try:
        out = llm.extrair_json(r.texto)
    except ValueError:
        out = demo
    return {"abertura": (out.get("abertura") or "").strip(), "assunto": (out.get("assunto") or "").strip()[:200],
            "custo_usd": getattr(r, "custo_usd", 0)}


def to_dict(ed, completo=False):
    d = {"id": ed.id, "numero": ed.numero, "semana_inicio": ed.semana_inicio.isoformat(), "semana_fim": ed.semana_fim.isoformat(),
         "titulo": ed.titulo, "assunto": ed.assunto, "status": ed.status,
         "agendada_para": _iso(ed.agendada_para), "enviada_em": _iso(ed.enviada_em), "destinatarios": ed.destinatarios or 0,
         "enviados": ed.enviados or 0, "falhas": ed.falhas or 0, "coletado_em": _iso(ed.coletado_em),
         "metricas": (ed.dados or {}).get("metricas")}
    if completo:
        d.update({"pre_cabecalho": ed.pre_cabecalho, "abertura": ed.abertura, "radar": ed.radar or [], "ocultas": ed.ocultas or [],
                  "dados": ed.dados or {}, "variacao": variacao(ed)})
    return d


def _iso(v):
    return v.isoformat() + "Z" if v else None


# ------------------------------------------------------------------ HTML do e-mail
AZUL, TINTA, FRACO, FUNDO, LINHA = "#2E6CA4", "#071D2D", "#4F6373", "#F4F3EF", "#E3E1DA"


def _utm(url, ed, conteudo):
    if not url or not url.startswith(("http://", "https://")):
        return url
    site = (current_app.config.get("SITE_URL") or "") + "|" + (current_app.config.get("FRONTEND_URL") or "")
    dominio = re.sub(r"^https?://", "", url).split("/")[0]
    if dominio and dominio in site:
        sep = "&" if "?" in url else "?"
        return f"{url}{sep}utm_source=newsletter&utm_medium=email&utm_campaign=kasiski-intelligence-{ed.numero}&utm_content={conteudo}"
    return url


def _paragrafos(texto):
    partes = [p.strip() for p in re.split(r"\n\s*\n", texto or "") if p.strip()]
    return "".join(f'<p style="margin:0 0 14px">{esc(p).replace(chr(10), "<br>")}</p>' for p in partes)


def _secao(titulo):
    return (f'<tr><td style="padding:30px 0 10px"><p style="margin:0;font-size:11px;letter-spacing:.16em;font-weight:700;'
            f'color:{FRACO};text-transform:uppercase">{esc(titulo)}</p></td></tr>')


def _barras(itens, rotulo, maximo):
    linhas = []
    for it in itens:
        pct = max(2, round((it["valor"] / maximo) * 100)) if maximo else 0
        linhas.append(
            f'<tr><td style="padding:5px 10px 5px 0;font-size:14px;width:38%;vertical-align:middle">{esc(it[rotulo])}</td>'
            f'<td style="padding:5px 0;vertical-align:middle"><table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>'
            f'<td width="{pct}%" style="background:{AZUL};height:10px;border-radius:0 3px 3px 0;font-size:0;line-height:0">&nbsp;</td>'
            f'<td style="padding-left:8px;font-size:13px;color:{TINTA};white-space:nowrap;font-weight:600">{moeda_curta(it["valor"])}'
            f'<span style="color:{FRACO};font-weight:400"> · {num(it["editais"])}</span></td></tr></table></td></tr>')
    return f'<tr><td><table role="presentation" width="100%" cellpadding="0" cellspacing="0">{"".join(linhas)}</table></td></tr>'


def montar_html(ed, envio=None, lead=None, web=False):
    """HTML da edição. Com `envio`, os links passam pelo rastreio de clique e há pixel de abertura."""
    cfg = current_app.config
    api = cfg.get("BACKEND_URL") or ""
    site, app_url = cfg.get("SITE_URL") or "", cfg.get("FRONTEND_URL") or ""
    d = ed.dados or {}
    m = d.get("metricas") or {}
    var = variacao(ed)
    links = []

    def L(url, conteudo):
        u = _utm(url, ed, conteudo)
        if not envio or not u:
            return esc(u)
        if u not in links:
            links.append(u)
        return esc(f"{api}/api/public/n/{envio.token}/l/{links.index(u)}")

    def delta(k):
        v = var.get(k)
        if v is None or abs(v) < 0.5:
            return ""
        cor = "#1F7A4D" if v > 0 else "#A33A2B"
        return f'<br><span style="font-size:12px;color:{cor};font-weight:600">{"▲" if v > 0 else "▼"} {abs(v):.0f}% vs. semana anterior</span>'

    corpo = []
    corpo.append(f'<tr><td style="padding:0 0 18px;border-bottom:2px solid {TINTA}"><p style="margin:0;font-size:18px;font-weight:800;letter-spacing:.04em">KASISKI '
                 f'<span style="font-weight:500;font-size:11px;color:#91A5B3;letter-spacing:.2em">INTELLIGENCE</span></p>'
                 f'<p style="margin:4px 0 0;font-size:12px;color:{FRACO}">Edição #{ed.numero} · semana de {dm(ed.semana_inicio)} a {ed.semana_fim.strftime("%d/%m/%Y")}</p></td></tr>')
    corpo.append(f'<tr><td style="padding:22px 0 4px"><h1 style="margin:0 0 14px;font-size:24px;line-height:1.25">{esc(ed.titulo)}</h1>'
                 f'{_paragrafos(ed.abertura)}</td></tr>')

    if m.get("publicadas"):
        corpo.append(_secao("Dado da semana"))
        cel = lambda valor, legenda, k: (f'<td width="33%" style="padding:14px 12px;background:{FUNDO};vertical-align:top">'
                                         f'<p style="margin:0;font-size:22px;font-weight:800;color:{TINTA}">{valor}</p>'
                                         f'<p style="margin:4px 0 0;font-size:12px;color:{FRACO};line-height:1.35">{legenda}{delta(k)}</p></td>')
        corpo.append(f'<tr><td><table role="presentation" width="100%" cellpadding="0" cellspacing="4"><tr>'
                     f'{cel(num(m["publicadas"]), "contratações publicadas no PNCP", "publicadas")}'
                     f'{cel(num(m["competitivas"]), "licitações com disputa (pregões e concorrências)", "competitivas")}'
                     f'{cel(("≈ " if m.get("estimado") else "") + moeda_curta(m["valor_competitivas"]), "em valor estimado nas licitações com disputa", "valor_competitivas")}'
                     f'</tr></table></td></tr>')
        setores = [s for s in d.get("setores") or [] if s["valor"] > 0][:6]
        if setores:
            corpo.append(_secao("Setores em destaque (valor estimado · editais)"))
            corpo.append(_barras(setores, "nome", setores[0]["valor"]))
        ufs = [u for u in d.get("ufs") or [] if u["valor"] > 0]
        if ufs:
            corpo.append(_secao("Onde o governo mais comprou"))
            corpo.append(_barras(ufs, "uf", ufs[0]["valor"]))
        if m.get("estimado"):
            corpo.append(f'<tr><td style="padding:8px 0 0;font-size:11px;color:{FRACO}">Valores estimados a partir de {num(m["amostra"])} '
                         f'licitações lidas no PNCP e projetados para o total da semana.</td></tr>')

    ops = oportunidades(ed)
    if ops:
        corpo.append(_secao("As 5 maiores oportunidades abertas"))
        for o in ops:
            enc = (o.get("data_encerramento") or "")[:10]
            try:
                enc = datetime.fromisoformat(enc).strftime("%d/%m/%Y")
            except ValueError:
                pass
            objeto = (o.get("objeto") or "")
            objeto = objeto[:230] + ("…" if len(objeto) > 230 else "")
            local = " / ".join(x for x in (o.get("municipio"), o.get("uf")) if x)
            corpo.append(
                f'<tr><td style="padding:14px 0;border-bottom:1px solid {LINHA}">'
                f'<p style="margin:0 0 4px;font-size:11px;color:{AZUL};font-weight:700;letter-spacing:.06em;text-transform:uppercase">{esc(o.get("setor"))}</p>'
                f'<p style="margin:0 0 6px;font-size:15px;font-weight:700;line-height:1.35">{esc(objeto)}</p>'
                f'<p style="margin:0 0 8px;font-size:13px;color:{FRACO}">{esc(o.get("orgao"))}{" · " + esc(local) if local else ""} · {esc(o.get("modalidade"))}</p>'
                f'<p style="margin:0;font-size:14px"><b>{moeda(o.get("valor"))}</b> <span style="color:{FRACO}">· propostas até {esc(enc)}</span></p>'
                f'<p style="margin:8px 0 0;font-size:13px"><a href="{L(o.get("link"), "oportunidade")}" style="color:{AZUL};font-weight:600">Ver edital no PNCP</a>'
                f' &nbsp;·&nbsp; <a href="{L(site + "/analisar-edital/", "analisar")}" style="color:{AZUL};font-weight:600">Analisar o edital grátis</a></p></td></tr>')

    radar = [r for r in (ed.radar or []) if (r.get("titulo") or "").strip()]
    if radar:
        corpo.append(_secao("Radar regulatório"))
        for r in radar:
            fonte = f' <span style="color:{FRACO};font-size:12px">({esc(r.get("fonte"))})</span>' if r.get("fonte") else ""
            link = f' <a href="{L(r["link"], "radar")}" style="color:{AZUL};font-size:13px;font-weight:600">Ler</a>' if r.get("link") else ""
            corpo.append(f'<tr><td style="padding:8px 0 10px;border-left:3px solid {AZUL};padding-left:12px">'
                         f'<p style="margin:0 0 4px;font-size:15px;font-weight:700">{esc(r.get("titulo"))}{fonte}</p>'
                         f'<p style="margin:0;font-size:14px;color:{TINTA}">{esc(r.get("resumo"))}{link}</p></td></tr>')

    corpo.append(f'<tr><td style="padding:30px 0 0"><table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>'
                 f'<td style="background:{TINTA};color:#fff;padding:22px;border-radius:6px">'
                 f'<p style="margin:0 0 6px;font-size:17px;font-weight:800;color:#fff">Receba as oportunidades do seu setor todo dia</p>'
                 f'<p style="margin:0 0 16px;font-size:14px;color:#C9D5DE">O Radar do Kasiski procura no PNCP os editais que combinam com a sua empresa, '
                 f'e a IA analisa o edital em minutos: requisitos, riscos e documentos.</p>'
                 f'<a href="{L(app_url + "/#/cadastro", "cta_teste")}" style="background:#fff;color:{TINTA};text-decoration:none;padding:11px 20px;'
                 f'border-radius:6px;font-weight:700;display:inline-block;font-size:14px">Testar grátis por 7 dias</a></td></tr></table></td></tr>')

    rodape = cfg.get("NEWSLETTER_RODAPE") or "Kasiski · D.B.C. Consultoria e Serviços Ltda."
    fontes = "Fonte dos dados: Portal Nacional de Contratações Públicas (PNCP), consulta pública."
    if web:
        extra = f'<a href="{esc(site)}/newsletter/" style="color:{FRACO}">Assine a Kasiski Intelligence</a>'
    else:
        sair = f"{api}/api/public/sair?t={lead.token}" + (f"&e={envio.token}" if envio else "") if lead and lead.token else f"{site}/newsletter/"
        navegador = f"{site}/newsletter/arquivo/?n={ed.numero}"
        extra = (f'Você recebe este e-mail porque se inscreveu na Kasiski Intelligence. '
                 f'<a href="{esc(sair)}" style="color:{FRACO}">Descadastrar</a> · <a href="{L(navegador, "navegador")}" style="color:{FRACO}">Ver no navegador</a>')
    corpo.append(f'<tr><td style="padding:26px 0 0;font-size:11px;color:#91A5B3;line-height:1.6">{fontes}<br>{extra}<br>{esc(rodape)}</td></tr>')

    pixel = f'<img src="{esc(api)}/api/public/n/{envio.token}/a.gif" width="1" height="1" alt="" style="display:block;border:0">' if envio else ""
    pre = (f'<div style="display:none;max-height:0;overflow:hidden;opacity:0">{esc(ed.pre_cabecalho or "")}'
           f'{"&nbsp;&zwnj;" * 40}</div>') if not web else ""
    html_final = (f'{pre}<div style="background:#ffffff;padding:24px 12px"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
                  f'style="max-width:600px;margin:0 auto;font-family:Inter,Segoe UI,Arial,sans-serif;color:{TINTA};line-height:1.55">'
                  f'{"".join(corpo)}</table>{pixel}</div>')
    return html_final, links


def montar_texto(ed):
    m = (ed.dados or {}).get("metricas") or {}
    linhas = [f"KASISKI INTELLIGENCE #{ed.numero} — {ed.titulo}", "", ed.abertura or "", ""]
    if m.get("publicadas"):
        linhas += [f"{num(m['publicadas'])} contratações publicadas · {num(m['competitivas'])} licitações com disputa · "
                   f"{moeda_curta(m['valor_competitivas'])} em valor estimado", ""]
    for o in oportunidades(ed):
        linhas += [f"- {o.get('objeto', '')[:160]} — {o.get('orgao')} ({o.get('uf')}) — {moeda(o.get('valor'))}", f"  {o.get('link')}"]
    for r in ed.radar or []:
        if r.get("titulo"):
            linhas += ["", f"* {r['titulo']}: {r.get('resumo', '')} {r.get('link', '')}"]
    return "\n".join(linhas)


# ------------------------------------------------------------------ inscritos e envio
def destinatarios_q():
    return Lead.query.filter(Lead.newsletter.is_(True), Lead.newsletter_confirmada.is_(True),
                             Lead.marketing_optout.isnot(True), Lead.email.isnot(None))


def _cabecalhos(lead, envio):
    api = current_app.config.get("BACKEND_URL") or ""
    return {"List-Unsubscribe": f"<{api}/api/public/sair?t={lead.token}&e={envio.token}>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"}


def enviar_teste(ed, para):
    from services import email as em
    lead = Lead.query.filter_by(email=para).first()
    corpo, _ = montar_html(ed, lead=lead)
    em.enviar(para, f"[TESTE] {ed.assunto}", montar_texto(ed), corpo)


def _reivindicar(ed_id):
    """Só um processo envia cada edição: troca de status atômica (ou retoma um envio parado há 10 min)."""
    agora = datetime.utcnow()
    parado = agora - timedelta(minutes=10)
    q = EdicaoNewsletter.query.filter(EdicaoNewsletter.id == ed_id, db.or_(
        EdicaoNewsletter.status == "agendada",
        db.and_(EdicaoNewsletter.status == "enviando", db.or_(EdicaoNewsletter.processando_em.is_(None),
                                                               EdicaoNewsletter.processando_em < parado))))
    n = q.update({"status": "enviando", "processando_em": agora}, synchronize_session=False)
    db.session.commit()
    return n == 1


def disparar(ed):
    """Marca para envio imediato; o agendador (ou a thread abaixo) faz o envio."""
    from services import email as em
    if not em.configurado():
        raise ErroAPI("Configure o RESEND_API_KEY no Render para enviar a newsletter.")
    if ed.status not in ("rascunho", "agendada"):
        raise ErroAPI("Esta edição já foi enviada ou está sendo enviada.")
    if not oportunidades(ed) and not (ed.dados or {}).get("metricas", {}).get("publicadas"):
        raise ErroAPI("A edição está sem dados do PNCP. Atualize os dados antes de enviar.")
    ed.status, ed.agendada_para = "agendada", datetime.utcnow()
    db.session.commit()
    app = current_app._get_current_object()
    import threading

    def rodar():
        with app.app_context():
            try:
                processar(ed.id)
            except Exception:
                log.exception("Falha no envio da newsletter %s", ed.id)
            finally:
                db.session.remove()
    threading.Thread(target=rodar, daemon=True, name=f"newsletter-{ed.id}").start()


def processar(ed_id, lote=None):
    """Envia a edição para quem ainda não recebeu. Pode ser chamada de novo sem duplicar."""
    from services import email as em
    from services import marketing
    if not _reivindicar(ed_id):
        return 0
    ed = EdicaoNewsletter.query.get(ed_id)
    lote = lote or current_app.config.get("NEWSLETTER_LOTE", 100)
    ed.destinatarios = max(ed.destinatarios or 0, destinatarios_q().count())
    db.session.commit()
    enviados_agora = 0
    while True:
        ja = db.session.query(NewsletterEnvio.lead_id).filter(NewsletterEnvio.edicao_id == ed.id,
                                                              NewsletterEnvio.status.in_(("enviado", "falhou")))
        leads = destinatarios_q().filter(Lead.id.notin_(ja)).order_by(Lead.id).limit(lote).all()
        if not leads:
            break
        pacote, envios = [], []
        for lead in leads:
            envio = NewsletterEnvio.query.filter_by(edicao_id=ed.id, lead_id=lead.id).first()
            if not envio:
                envio = NewsletterEnvio(edicao_id=ed.id, lead_id=lead.id, email=lead.email, token=secrets.token_urlsafe(18), status="pendente")
                db.session.add(envio)
                db.session.flush()
            lead.token = lead.token or secrets.token_urlsafe(20)
            corpo, links = montar_html(ed, envio=envio, lead=lead)
            if links and (ed.links or []) != links:
                ed.links = links  # os links são iguais para todos os inscritos (só o token muda)
            pacote.append({"para": lead.email, "assunto": ed.assunto, "texto": montar_texto(ed), "html": corpo,
                           "cabecalhos": _cabecalhos(lead, envio)})
            envios.append(envio)
        db.session.commit()
        try:
            em.enviar_lote(pacote)
            agora = datetime.utcnow()
            for e in envios:
                e.status, e.enviado_em, e.erro = "enviado", agora, None
            enviados_agora += len(envios)
        except Exception:
            # o lote inteiro é recusado se um endereço for inválido: tenta um a um para isolar o problema
            agora = datetime.utcnow()
            for e, msg in zip(envios, pacote):
                try:
                    em.enviar(msg["para"], msg["assunto"], msg["texto"], msg["html"], cabecalhos=msg["cabecalhos"])
                    e.status, e.enviado_em, e.erro = "enviado", agora, None
                    enviados_agora += 1
                except Exception as ex1:
                    e.status, e.erro = "falhou", str(getattr(ex1, "detalhe", "") or ex1)[:500]
                time.sleep(0.5)  # limite do Resend: ~2 req/s
        ed.processando_em = datetime.utcnow()
        ed.enviados = NewsletterEnvio.query.filter_by(edicao_id=ed.id, status="enviado").count()
        ed.falhas = NewsletterEnvio.query.filter_by(edicao_id=ed.id, status="falhou").count()
        db.session.commit()
        time.sleep(current_app.config.get("NEWSLETTER_PAUSA_S", 0.6))
    ed.status, ed.enviada_em, ed.processando_em = "enviada", ed.enviada_em or datetime.utcnow(), None
    ed.destinatarios = NewsletterEnvio.query.filter_by(edicao_id=ed.id).count()
    db.session.commit()
    marketing.registrar("newsletter_sent", dados={"edicao": ed.numero, "enviados": ed.enviados})
    db.session.commit()
    log.info("Newsletter #%s: %d enviada(s) agora, %d falha(s)", ed.numero, enviados_agora, ed.falhas)
    return enviados_agora


def reenviar_falhas(ed):
    NewsletterEnvio.query.filter_by(edicao_id=ed.id, status="falhou").delete()
    ed.status = "agendada"
    db.session.commit()
    disparar_agendada(ed)


def disparar_agendada(ed):
    app = current_app._get_current_object()
    import threading

    def rodar():
        with app.app_context():
            try:
                processar(ed.id)
            finally:
                db.session.remove()
    threading.Thread(target=rodar, daemon=True).start()


def estatisticas(ed):
    base = NewsletterEnvio.query.filter_by(edicao_id=ed.id, status="enviado")
    enviados = base.count()
    abertos = base.filter(NewsletterEnvio.aberto_em.isnot(None)).count()
    clicaram = base.filter(NewsletterEnvio.clicado_em.isnot(None)).count()
    sairam = NewsletterEnvio.query.filter(NewsletterEnvio.edicao_id == ed.id, NewsletterEnvio.descadastrou_em.isnot(None)).count()
    por_link = defaultdict(int)
    for (c,) in db.session.query(NewsletterEnvio.cliques).filter(NewsletterEnvio.edicao_id == ed.id, NewsletterEnvio.cliques.isnot(None)):
        for i, q in (c or {}).items():
            por_link[int(i)] += 1  # pessoas únicas por link
    links = ed.links or []
    top = sorted(({"url": links[i] if i < len(links) else "?", "pessoas": q} for i, q in por_link.items()), key=lambda x: -x["pessoas"])[:10]
    pct = lambda a: round(a / enviados * 100, 1) if enviados else None
    return {"enviados": enviados, "abertos": abertos, "clicaram": clicaram, "descadastros": sairam,
            "taxa_abertura": pct(abertos), "taxa_clique": pct(clicaram), "taxa_descadastro": pct(sairam), "links": top,
            "falhas": NewsletterEnvio.query.filter_by(edicao_id=ed.id, status="falhou").count()}


# ------------------------------------------------------------------ rastreio (rotas públicas chamam estas funções)
def registrar_abertura(token):
    from services import marketing
    e = NewsletterEnvio.query.filter_by(token=token[:40]).first()
    if not e:
        return
    primeira = e.aberto_em is None
    e.aberto_em = e.aberto_em or datetime.utcnow()
    e.aberturas = (e.aberturas or 0) + 1
    if primeira:
        lead = Lead.query.get(e.lead_id)
        if lead:
            marketing.registrar("newsletter_open", lead=lead, dados={"edicao_id": e.edicao_id})
    db.session.commit()


def registrar_clique(token, indice):
    """Devolve a URL de destino (só links da própria edição, para não virar redirecionador aberto)."""
    from services import marketing
    e = NewsletterEnvio.query.filter_by(token=token[:40]).first()
    if not e:
        return None
    ed = EdicaoNewsletter.query.get(e.edicao_id)
    links = (ed.links or []) if ed else []
    if not (0 <= indice < len(links)):
        return None
    primeira = e.clicado_em is None
    agora = datetime.utcnow()
    e.clicado_em = e.clicado_em or agora
    e.aberto_em = e.aberto_em or agora  # quem clica abriu (pixel bloqueado)
    c = dict(e.cliques or {})
    c[str(indice)] = c.get(str(indice), 0) + 1
    e.cliques = c
    if primeira:
        lead = Lead.query.get(e.lead_id)
        if lead:
            marketing.registrar("newsletter_click", lead=lead, dados={"edicao": ed.numero, "url": links[indice][:300]})
    db.session.commit()
    return links[indice]


def registrar_descadastro(token):
    e = NewsletterEnvio.query.filter_by(token=(token or "")[:40]).first() if token else None
    if e and not e.descadastrou_em:
        e.descadastrou_em = datetime.utcnow()


# ------------------------------------------------------------------ agendador
def ciclo():
    """Chamado pelo agendador do servidor (a cada ~10 min) e pelo job diário.
    1) segunda-feira a partir das 9h UTC: cria o rascunho da semana passada e avisa os admins;
    2) envia as edições agendadas cujo horário chegou; 3) retoma envios parados."""
    cfg = current_app.config
    agora = datetime.utcnow()
    feito = []
    if cfg.get("NEWSLETTER_RASCUNHO_AUTO", True) and agora.weekday() == 0 and agora.hour >= 9:
        ini, _ = semana_anterior(agora.date())
        if not EdicaoNewsletter.query.filter_by(semana_inicio=ini).first():
            ed, criou = gerar_rascunho(ini)
            if criou:
                feito.append(f"rascunho #{ed.numero}")
                _avisar_admins(ed)
    prontas = EdicaoNewsletter.query.filter(db.or_(
        db.and_(EdicaoNewsletter.status == "agendada", EdicaoNewsletter.agendada_para <= agora),
        db.and_(EdicaoNewsletter.status == "enviando", EdicaoNewsletter.processando_em < agora - timedelta(minutes=10)))).all()
    for ed in prontas:
        n = processar(ed.id)
        feito.append(f"#{ed.numero}: {n}")
    return feito


def _avisar_admins(ed):
    from services import email as em
    if not em.configurado():
        return
    emails = set(current_app.config.get("ADMIN_EMAILS") or [])
    link = f"{current_app.config.get('FRONTEND_URL')}/#/admin"
    m = (ed.dados or {}).get("metricas") or {}
    corpo = em.layout_marketing(f"Rascunho da Kasiski Intelligence #{ed.numero} pronto",
                                f"<p>Os dados do PNCP da semana de {dm(ed.semana_inicio)} a {dm(ed.semana_fim)} já foram coletados "
                                f"({num(m.get('publicadas'))} contratações, {moeda_curta(m.get('valor_competitivas'))} em licitações com disputa).</p>"
                                "<p>Revise as oportunidades, escreva o radar regulatório e envie pelo painel: Admin → Marketing → Newsletter.</p>",
                                "Revisar a edição", link)
    for para in emails:
        try:
            em.enviar(para, f"Newsletter #{ed.numero}: rascunho pronto para revisão", f"Revise em {link}", corpo)
        except Exception:
            log.warning("Falha ao avisar admin sobre a newsletter")
