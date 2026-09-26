"""Ferramentas gratuitas do site (sem conta): triagem de edital, consulta de concorrente, newsletter, leads.

Proteções: limite por IP e por e-mail, teto global diário de análises com IA (custo), honeypot, Cloudflare
Turnstile opcional (TURNSTILE_SECRET), tamanho máximo do PDF e expiração dos arquivos em 7 dias.
"""
import hashlib
import logging
import os
import secrets
from datetime import datetime, timedelta

import requests
from flask import current_app, request

from extensions import ErroAPI, db
from models import AnalisePublica, Lead, UsoPublico

log = logging.getLogger(__name__)
_cache_concorrente = {}  # cnpj -> (quando, dados) — consulta pública repetida no mesmo dia não bate nas APIs de novo


def ip_hash():
    bruto = (request.headers.get("X-Forwarded-For") or request.remote_addr or "").split(",")[0].strip()
    return hashlib.sha256(f"{bruto}|{current_app.config['SECRET_KEY']}".encode()).hexdigest()[:40]


def exigir_humano(d):
    """Honeypot (campo 'site' tem de vir vazio) e Turnstile, quando configurado."""
    if (d.get("site") or "").strip():
        raise ErroAPI("Não foi possível enviar agora.", 400, "bloqueado")
    segredo = current_app.config.get("TURNSTILE_SECRET")
    if not segredo:
        return
    token = d.get("cf-turnstile-response") or d.get("turnstile") or ""
    try:
        r = requests.post("https://challenges.cloudflare.com/turnstile/v0/siteverify", timeout=10,
                          data={"secret": segredo, "response": token, "remoteip": request.remote_addr})
        if not r.json().get("success"):
            raise ErroAPI("Confirme que você não é um robô e tente de novo.", 400, "captcha")
    except requests.RequestException:
        log.warning("Turnstile indisponível; seguindo sem a verificação")


def limitar(tipo, ip, email=None, por_ip=None, horas_ip=24, por_email=None, dias_email=30):
    agora = datetime.utcnow()
    if por_ip is not None:
        n = UsoPublico.query.filter(UsoPublico.tipo == tipo, UsoPublico.ip_hash == ip,
                                    UsoPublico.criado_em >= agora - timedelta(hours=horas_ip)).count()
        if n >= por_ip:
            raise ErroAPI("Você atingiu o limite gratuito por hoje. Crie sua conta grátis para continuar sem esse limite.", 429, "limite_publico")
    if email and por_email is not None:
        n = UsoPublico.query.filter(UsoPublico.tipo == tipo, UsoPublico.email == email,
                                    UsoPublico.criado_em >= agora - timedelta(days=dias_email)).count()
        if n >= por_email:
            raise ErroAPI("Este e-mail já usou a análise gratuita. Crie sua conta grátis: o teste inclui análises completas.", 429, "limite_publico")
    db.session.add(UsoPublico(tipo=tipo, ip_hash=ip, email=email))


def email_valido(email):
    import re
    return bool(re.match(r"[^@\s]+@[^@\s]+\.[^@\s]{2,}$", email or ""))


# ---------------------------------------------------------------- triagem de edital
def teto_global_atingido():
    hoje = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    return AnalisePublica.query.filter(AnalisePublica.criado_em >= hoje).count() >= current_app.config["PUBLICO_ANALISES_DIA"]


def nota_participacao(extracao, triagem):
    """0-100: quanto maior, mais simples participar. Parte de 100 e desconta pontos de atenção e prazo curto."""
    pesos = {"alta": 12, "media": 6, "baixa": 2}
    nota = 100 - sum(pesos.get(p.get("gravidade"), 3) for p in triagem.get("pontos_atencao") or [])
    nota -= 3 * len(triagem.get("documentos_criticos") or [])
    dias = dias_ate_sessao(extracao)
    if dias is not None and dias < 5:
        nota -= 10
    if len(extracao.get("exigencias_tecnicas_objeto") or []) > 8:
        nota -= 5
    return max(20, min(100, nota))


def dias_ate_sessao(extracao):
    try:
        d = datetime.fromisoformat(str(extracao.get("data_abertura"))[:16])
        return (d.date() - datetime.utcnow().date()).days
    except (TypeError, ValueError):
        return None


def rodar_triagem(ap_id):
    """Em segundo plano: extração (IA barata) + triagem de riscos (IA barata)."""
    from services import llm, prompts
    ap = AnalisePublica.query.get(ap_id)
    try:
        texto = (ap.texto or "")[: current_app.config["PUBLICO_MAX_CHARS"]]
        ap.etapa = "Lendo o edital"
        db.session.commit()
        s, u, demo = prompts.extracao_edital(texto)
        r1 = llm.chamar("barata", s, u, max_tokens=3500, demo=demo)
        extracao = llm.extrair_json(r1.texto)
        ap.etapa = "Procurando pontos de atenção"
        db.session.commit()
        resumo_ext = {k: extracao.get(k) for k in ("orgao", "objeto", "modalidade", "criterio_julgamento", "valor_estimado",
                                                   "data_abertura", "exclusivo_me_epp", "garantia_contrato")}
        s, u, demo = prompts.triagem_publica(texto[:60000], resumo_ext)
        r2 = llm.chamar("barata", s, u, max_tokens=1800, demo=demo)
        triagem = llm.extrair_json(r2.texto)
        ap.resultado = {"extracao": extracao, "triagem": triagem, "nota": nota_participacao(extracao, triagem),
                        "demonstracao": bool(getattr(r2, "demonstracao", False))}
        ap.custo_usd = float((r1.custo_usd or 0) + (r2.custo_usd or 0))
        ap.status, ap.etapa, ap.concluido_em = "concluida", None, datetime.utcnow()
        from services import marketing
        lead = Lead.query.get(ap.lead_id) if ap.lead_id else None
        marketing.registrar("edital_free_analysis", lead=lead, dados={"analise": ap.id, "nota": ap.resultado["nota"]})
        db.session.commit()
        enviar_resultado_por_email(ap)
    except Exception:
        db.session.rollback()
        log.exception("Falha na triagem pública %s", ap_id)
        ap = AnalisePublica.query.get(ap_id)
        ap.status, ap.etapa = "erro", None
        ap.erro = "Não conseguimos analisar este edital agora. Tente de novo em alguns minutos."
        db.session.commit()


def visao_publica(ap):
    """O que a página mostra sem conta: resumo, nota, contagens e o primeiro ponto de atenção completo.
    Os demais pontos vão sem explicação (bloqueados) — o conteúdo completo nunca sai do servidor."""
    base = {"id": ap.id, "status": ap.status, "etapa": ap.etapa, "erro": ap.erro, "nome_arquivo": ap.nome_arquivo}
    if ap.status != "concluida":
        return base
    r = ap.resultado or {}
    ex, tr = r.get("extracao") or {}, r.get("triagem") or {}
    pontos = tr.get("pontos_atencao") or []
    pontos.sort(key=lambda p: {"alta": 0, "media": 1, "baixa": 2}.get(p.get("gravidade"), 3))
    exig = ex.get("exigencias_habilitacao") or []
    categorias = {}
    for e in exig:
        categorias[e.get("categoria") or "outros"] = categorias.get(e.get("categoria") or "outros", 0) + 1
    dias = dias_ate_sessao(ex)
    base.update({
        "nota": r.get("nota"), "demonstracao": r.get("demonstracao"),
        "edital": {k: ex.get(k) for k in ("orgao", "numero", "objeto", "modalidade", "criterio_julgamento", "valor_estimado",
                                         "data_abertura", "portal_disputa", "exclusivo_me_epp")},
        "resumo": tr.get("resumo"),
        "documentos": {"total": len(exig), "por_categoria": categorias},
        "documentos_criticos": len(tr.get("documentos_criticos") or []),
        "pontos": {"total": len(pontos), "altos": sum(1 for p in pontos if p.get("gravidade") == "alta"),
                   "primeiro": pontos[0] if pontos else None,
                   "bloqueados": [{"gravidade": p.get("gravidade")} for p in pontos[1:]]},
        "prazo": {"dias": dias, "suficiente": None if dias is None else dias >= 8},
    })
    return base


def enviar_resultado_por_email(ap):
    from services import email as em
    if not ap.email or not em.configurado():
        return
    v = visao_publica(ap)
    link = f"{current_app.config['FRONTEND_URL']}/analisar-edital/?r={ap.id}"
    cad = f"{current_app.config['FRONTEND_URL']}/#/cadastro?utm_source=kasiski&utm_medium=email&utm_campaign=analise_gratuita"
    corpo = em.layout_marketing(
        f"Sua análise gratuita está pronta: nota {v.get('nota')}/100",
        f"<p>Analisamos <b>{em.esc(ap.nome_arquivo or 'o edital')}</b>. Encontramos <b>{v['pontos']['total']} ponto(s) de atenção</b> "
        f"({v['pontos']['altos']} de gravidade alta) e <b>{v['documentos']['total']} documento(s) de habilitação</b> exigidos.</p>",
        "Ver o resultado", link,
        f"<p>Para ver todos os pontos com fundamento e conferir a habilitação contra os documentos da sua empresa, "
        f"<a href='{cad}'>crie sua conta grátis</a> com este mesmo e-mail: a análise é importada automaticamente.</p>")
    try:
        em.enviar(ap.email, f"Análise do edital pronta — nota {v.get('nota')}/100", f"Veja o resultado: {link}", corpo)
    except Exception:
        log.warning("Não foi possível enviar o e-mail da análise pública %s", ap.id)


def importar_analises(conta, usuario, empresa):
    """Depois do cadastro da 1ª empresa: traz as análises gratuitas feitas com o mesmo e-mail como editais da conta
    e já roda a análise completa da mais recente, como cortesia (não desconta do plano)."""
    try:
        from models import Analise, Edital
        from services import oportunidades
        limite = datetime.utcnow() - timedelta(days=7)
        aps = AnalisePublica.query.filter(AnalisePublica.email == (usuario.email or "").lower(), AnalisePublica.conta_id.is_(None),
                                          AnalisePublica.status == "concluida", AnalisePublica.criado_em >= limite) \
            .order_by(AnalisePublica.criado_em.desc()).limit(3).all()
        primeiro = None
        for ap in aps:
            ex = (ap.resultado or {}).get("extracao") or {}
            ed = Edital(empresa_id=empresa.id, origem="upload", arquivo=ap.arquivo, nome_arquivo=ap.nome_arquivo, texto=ap.texto,
                        orgao=(ex.get("orgao") or "")[:300] or None, objeto=ex.get("objeto"), numero=(ex.get("numero") or "")[:80] or None,
                        modalidade=(ex.get("modalidade") or "")[:80] or None,
                        valor_estimado=ex.get("valor_estimado") if isinstance(ex.get("valor_estimado"), (int, float)) else None)
            try:
                ed.data_abertura = datetime.fromisoformat(str(ex.get("data_abertura"))[:16])
            except (TypeError, ValueError):
                pass
            db.session.add(ed)
            db.session.flush()
            oportunidades.registrar_criacao(ed, "Importada da análise gratuita feita no site.")
            ap.conta_id, ap.edital_id = conta.id, ed.id
            primeiro = primeiro or ed
        if primeiro:
            from services import fluxos
            fluxos.gerar_prazos_edital(primeiro)
            a = Analise(edital_id=primeiro.id, status="processando", etapa="Na fila")
            db.session.add(a)
            oportunidades.avancar(primeiro, "em_analise", "Análise completa de cortesia (edital da análise gratuita).")
            db.session.flush()
            from services import tarefas
            from routes.editais import _rodar_analise
            app = current_app._get_current_object()
            import threading
            aid, eid, emp_id, cid = a.id, primeiro.id, empresa.id, conta.id
            # dispara depois do commit da rota (a thread abre a própria sessão)
            threading.Timer(1.0, _rodar_analise, args=(app, aid, eid, emp_id, cid, True)).start()
        return len(aps)
    except Exception:
        log.exception("Falha ao importar análises gratuitas")
        return 0


def limpar_expiradas():
    """Apaga arquivos e textos das análises públicas com mais de 7 dias que não viraram conta."""
    from services import arquivos
    limite = datetime.utcnow() - timedelta(days=7)
    n = 0
    for ap in AnalisePublica.query.filter(AnalisePublica.criado_em < limite, AnalisePublica.conta_id.is_(None),
                                          AnalisePublica.arquivo.isnot(None)):
        try:
            caminho = arquivos.caminho_absoluto(ap.arquivo)
            if os.path.exists(caminho):
                os.remove(caminho)
        except Exception:
            pass
        ap.arquivo, ap.texto = None, None
        n += 1
    UsoPublico.query.filter(UsoPublico.criado_em < datetime.utcnow() - timedelta(days=45)).delete()
    return n


# ---------------------------------------------------------------- consulta de concorrente
def consultar_concorrente(cnpj):
    agora = datetime.utcnow()
    em_cache = _cache_concorrente.get(cnpj)
    if em_cache and agora - em_cache[0] < timedelta(hours=12):
        return em_cache[1]
    from services import fluxos
    dossie, razao = fluxos.montar_dossie(cnpj)
    rec = dossie.get("receita") or {}
    hist = dossie.get("historico_pncp") or []
    tcu, cgu = dossie.get("sancoes_tcu") or {}, dossie.get("sancoes_cgu") or {}
    contratos = [h for h in hist if h.get("tipo") == "contrato"]
    atas = [h for h in hist if h.get("tipo") == "ata"]
    orgaos = {h.get("orgao") for h in hist if h.get("orgao")}
    sancoes = None
    if tcu.get("status") == "ok" or cgu.get("status") in ("ok", "parcial"):
        sancoes = len([c for c in tcu.get("certidoes") or [] if "nada consta" not in str(c.get("situacao", "")).lower()]) + \
                  len(cgu.get("registros") or [])
    visao = {
        "cnpj": cnpj, "encontrado": rec.get("status") == "ok",
        "razao_social": razao or rec.get("razao_social"), "nome_fantasia": rec.get("nome_fantasia"),
        "situacao": rec.get("situacao"), "abertura": rec.get("abertura"), "porte": rec.get("porte"),
        "municipio": rec.get("municipio"), "uf": rec.get("uf"),
        "cnae_principal": next((c.get("descricao") for c in rec.get("cnaes") or [] if c.get("principal")), None),
        "contratos": len(contratos), "atas": len(atas), "orgaos": len(orgaos),
        "valor_contratos": round(sum(float(h.get("valor") or 0) for h in contratos), 2) or None,
        "ufs": sorted({h.get("uf") for h in hist if h.get("uf")}),
        "sancoes": sancoes, "fontes_sancoes": [n for n, s in (("TCU/CNJ/CEIS/CNEP", tcu), ("CGU", cgu)) if s.get("status") in ("ok", "parcial")],
        "consultado_em": agora.isoformat(),
    }
    _cache_concorrente[cnpj] = (agora, visao)
    if len(_cache_concorrente) > 500:
        _cache_concorrente.pop(next(iter(_cache_concorrente)))
    return visao


def novo_token():
    return secrets.token_urlsafe(24)
