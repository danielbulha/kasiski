"""Automações de e-mail do onboarding e do fim do teste grátis (motor próprio, sem ferramenta externa).

Cada regra = gatilho (cadastro, empresa, radar, analise, trial_fim) + atraso + condição + modelo.
O envio é idempotente (1 por regra por conta: restrição única em AutomacaoEnvio), respeita o descadastro
e só dispara dentro de uma janela de 3 dias após o momento previsto (não inunda contas antigas no deploy).
Roda a cada AUTOMACOES_INTERVALO_S segundos numa thread do servidor web e também no job diário.
"""
import logging
import threading
import time
from datetime import datetime, timedelta

from flask import current_app
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import (Analise, AnaliseConcorrente, Automacao, AutomacaoEnvio, Conta, Edital, Empresa, Evento, Lead, Peca, Prazo, RadarItem,
                    UsoIA, Usuario)

log = logging.getLogger(__name__)
JANELA = timedelta(days=3)

PADRAO = [
    # chave, nome, gatilho, atraso_min, condicao, assunto
    ("boas_vindas", "Boas-vindas", "cadastro", 10, None, "Bem-vindo ao Kasiski"),
    ("empresa_24h", "Lembrete: cadastrar a empresa", "cadastro", 1440, "sem_empresa", "Falta um passo para o Kasiski trabalhar por você"),
    ("radar_config", "Empresa cadastrada → configurar radar", "empresa", 30, "sem_radar", "Agora vamos procurar oportunidades para você"),
    ("radar_ok", "Radar configurado", "radar", 60, None, "Seu Radar está funcionando"),
    ("sem_analise_24h", "24h sem análise de edital", "cadastro", 1440, "sem_analise", "Experimente o recurso mais poderoso do Kasiski"),
    ("primeira_analise", "Primeira análise concluída", "analise", 5, None, "Seu primeiro edital foi analisado"),
    ("trial_48h", "Teste termina em 48h", "trial_fim", 2880, "em_teste", "Seu teste termina em dois dias"),
    ("trial_24h", "Teste termina em 24h", "trial_fim", 1440, "em_teste", "O que você já conseguiu no Kasiski"),
    ("trial_6h", "Teste termina em 6h", "trial_fim", 360, "em_teste", "Continue com seus dados e análises"),
]


def garantir_padrao():
    existentes = {a.chave for a in Automacao.query.all()}
    for chave, nome, gatilho, atraso, cond, assunto in PADRAO:
        if chave not in existentes:
            db.session.add(Automacao(chave=chave, nome=nome, gatilho=gatilho, atraso_min=atraso, condicao=cond, assunto=assunto, ativo=True))
    db.session.commit()


def _primeiro_evento(conta_id, tipo):
    e = Evento.query.filter_by(conta_id=conta_id, tipo=tipo).order_by(Evento.criado_em).first()
    return e.criado_em if e else None


def momento(a, conta):
    """Quando a regra deveria disparar para a conta (ou None se o gatilho não aconteceu)."""
    if a.gatilho == "cadastro":
        base = conta.criado_em
    elif a.gatilho == "empresa":
        base = _primeiro_evento(conta.id, "company_created")
    elif a.gatilho == "radar":
        base = _primeiro_evento(conta.id, "radar_configured")
    elif a.gatilho == "analise":
        base = _primeiro_evento(conta.id, "edital_analyzed")
    elif a.gatilho == "trial_fim":
        return conta.trial_fim - timedelta(minutes=a.atraso_min or 0) if conta.trial_fim else None
    else:
        return None
    return base + timedelta(minutes=a.atraso_min or 0) if base else None


def metricas(conta):
    ids = [e.id for e in Empresa.query.filter_by(conta_id=conta.id)]
    eds = Edital.query.filter(Edital.empresa_id.in_(ids)).all() if ids else []
    return {
        "empresas": len(ids),
        "radar_config": any((e.palavras_chave or "").strip() for e in Empresa.query.filter_by(conta_id=conta.id)),
        "radar_itens": RadarItem.query.filter(RadarItem.empresa_id.in_(ids)).count() if ids else 0,
        "editais": len(eds),
        "analises": Analise.query.filter(Analise.edital_id.in_([e.id for e in eds]), Analise.status == "concluida").count() if eds else 0,
        "concorrentes": AnaliseConcorrente.query.filter(AnaliseConcorrente.edital_id.in_([e.id for e in eds])).count() if eds else 0,
        "pecas": Peca.query.filter(Peca.empresa_id.in_(ids)).count() if ids else 0,
        "prazos": Prazo.query.filter(Prazo.empresa_id.in_(ids)).count() if ids else 0,
    }


def condicao_ok(a, conta, m):
    c = a.condicao
    if c == "sem_empresa":
        return m["empresas"] == 0
    if c == "sem_radar":
        return not m["radar_config"]
    if c == "sem_analise":
        return m["analises"] == 0
    if c == "em_teste":
        return conta.plano == "trial" and conta.trial_fim and conta.trial_fim > datetime.utcnow()
    return True


def _link(caminho, chave):
    base = current_app.config["FRONTEND_URL"]
    sep = "&" if "?" in caminho else "?"
    return f"{base}/{caminho}{sep}utm_source=kasiski&utm_medium=email&utm_campaign=onboarding&utm_content={chave}"


def montar(a, conta, usuario, m):
    """(assunto, titulo, corpo_html, botao, link)."""
    from services import email as em
    nome = em.esc((usuario.nome or "").split(" ")[0])
    ch = a.chave
    if ch == "boas_vindas":
        if m["empresas"]:
            return (a.assunto, f"Bem-vindo ao Kasiski, {nome}!", "<p>Sua empresa já está cadastrada. O próximo passo é analisar um edital: "
                    "o Kasiski confere a habilitação, aponta cláusulas restritivas e recomenda se vale disputar.</p>", "Analisar um edital", _link("#/editais", ch))
        return (a.assunto, f"Bem-vindo ao Kasiski, {nome}!", "<p>Em 2 minutos você cadastra sua empresa pelo CNPJ: o Kasiski traz os CNAEs, sugere as "
                "palavras-chave e já começa a procurar editais aderentes no PNCP.</p>", "Cadastrar minha empresa", _link("#/empresas", ch))
    if ch == "empresa_24h":
        return (a.assunto, "Falta só cadastrar sua empresa", "<p>Com o CNPJ, o Kasiski monta o perfil da empresa e o Radar passa a buscar "
                "licitações todos os dias. Leva 2 minutos.</p>", "Cadastrar minha empresa", _link("#/empresas", ch))
    if ch == "radar_config":
        return (a.assunto, "Agora vamos procurar oportunidades para você", "<p>Confira as palavras-chave, as UFs e a faixa de valor da empresa: "
                "é com elas que o Radar busca e dá nota aos editais do PNCP.</p>", "Configurar o Radar", _link("#/empresas", ch))
    if ch == "radar_ok":
        n = m["radar_itens"]
        txt = f"<p>O Radar já encontrou <b>{n} edital(is)</b> aderentes ao perfil da sua empresa.</p>" if n else \
              "<p>O Radar vai buscar editais todos os dias e dar uma nota de aderência a cada um. Você também pode atualizar na hora.</p>"
        return (a.assunto, "Seu Radar está funcionando", txt, "Ver oportunidades", _link("#/radar", ch))
    if ch == "sem_analise_24h":
        return (a.assunto, "Experimente o recurso mais poderoso do Kasiski", "<p>Envie o PDF de um edital (ou importe do PNCP). Em poucos minutos você recebe "
                "o checklist de habilitação conferido com seus documentos, as cláusulas restritivas e a recomendação de participar ou não.</p>",
                "Analisar edital", _link("#/editais", ch))
    if ch == "primeira_analise":
        ids = [e.id for e in Empresa.query.filter_by(conta_id=conta.id)]
        a1 = Analise.query.join(Edital, Edital.id == Analise.edital_id).filter(Edital.empresa_id.in_(ids), Analise.status == "concluida") \
            .order_by(Analise.id).first() if ids else None
        r = (a1.resultado or {}) if a1 else {}
        riscos = len(r.get("riscos") or []) + len(r.get("clausulas_restritivas") or [])
        docs = len(r.get("checklist") or [])
        prazos = Prazo.query.filter_by(edital_id=a1.edital_id).count() if a1 else 0
        corpo = ("<table style='width:100%;border-collapse:collapse;margin:8px 0'>" +
                 "".join(f"<tr><td style='padding:8px 0;border-bottom:1px solid #E1E6EA'><b style='font-size:20px'>{v}</b> {t}</td></tr>"
                         for v, t in ((riscos, "riscos e pontos de atenção encontrados"), (docs, "documentos de habilitação verificados"),
                                      (prazos, "prazos identificados na agenda"))) + "</table>")
        return (a.assunto, "Seu primeiro edital foi analisado", corpo, "Ver a análise", _link(f"#/editais/{a1.edital_id}" if a1 else "#/editais", ch))
    itens = [(m["analises"], "edital(is) analisado(s)"), (m["radar_itens"], "oportunidade(s) encontradas pelo Radar"),
             (m["prazos"], "prazo(s) na agenda")]
    if m["concorrentes"]:
        itens.append((m["concorrentes"], "análise(s) de concorrente"))
    itens = [(v, t) for v, t in itens if v] or [(m["editais"], "edital(is) acompanhado(s)")]
    resumo = "<ul style='padding-left:18px'>" + "".join(f"<li><b>{v}</b> {t}</li>" for v, t in itens) + "</ul>"
    if ch == "trial_48h":
        return (a.assunto, "Seu teste termina em dois dias", f"<p>Até aqui, no Kasiski:</p>{resumo}<p>Escolha um plano para manter o Radar, os editais, "
                "os prazos e as análises. Nada se perde.</p>", "Ver planos", _link("#/conta", ch))
    if ch == "trial_24h":
        titulo = (f"Você analisou {m['analises']} edital(is) e encontrou {m['radar_itens']} oportunidade(s)" if m["analises"] and m["radar_itens"]
                  else f"Você analisou {m['analises']} edital(is) no Kasiski" if m["analises"] else "Seu teste termina amanhã")
        return (a.assunto, titulo, f"{resumo}"
                "<p>Seu teste termina amanhã. Assinando agora, tudo continua exatamente de onde parou.</p>", "Continuar no Kasiski", _link("#/conta", ch))
    if ch == "trial_6h":
        return (a.assunto, "Continue com seus dados e análises", f"<p>Seu teste termina hoje. Seus editais, documentos do cofre e prazos ficam guardados.</p>{resumo}",
                "Escolher um plano", _link("#/conta", ch))
    return (a.assunto, a.assunto, "", None, None)


def _descadastro(conta):
    from services import marketing
    lead = Lead.query.get(conta.lead_id) if conta.lead_id else marketing._garantir_lead_da_conta(conta)
    if not lead:
        return None
    base = current_app.config["BACKEND_URL"] or ""
    return f"{base}/api/public/sair?t={lead.token}" if base else None


def enviar_um(a, conta, usuario, m, teste_para=None):
    from services import email as em
    assunto, titulo, corpo, botao, link = montar(a, conta, usuario, m)
    html_ = em.layout_marketing(titulo, corpo, botao, link, descadastro=_descadastro(conta))
    return em.enviar(teste_para or usuario.email, assunto, f"{titulo}\n\n{link or ''}", html_)


def rodar(agora=None):
    """Um ciclo: devolve [(chave, conta_id)] enviados."""
    from services import email as em
    if not em.configurado():
        return []
    agora = agora or datetime.utcnow()
    garantir_padrao()
    regras = Automacao.query.filter_by(ativo=True).all()
    if not regras:
        return []
    feitos = []
    enviados = {(e.automacao_id, e.conta_id) for e in AutomacaoEnvio.query.filter(AutomacaoEnvio.enviado_em >= agora - timedelta(days=45))}
    for conta in Conta.query.filter(Conta.criado_em >= agora - timedelta(days=30)):
        if conta.marketing_optout:
            continue
        usuario = Usuario.query.filter_by(conta_id=conta.id).order_by(Usuario.id).first()
        if not usuario or usuario.email_verificado is False:
            continue
        m = None
        for a in regras:
            if (a.id, conta.id) in enviados:
                continue
            quando = momento(a, conta)
            if not quando or quando > agora or agora - quando > JANELA:
                continue
            if a.gatilho == "trial_fim" and conta.trial_fim and agora >= conta.trial_fim:
                continue
            m = m or metricas(conta)
            if not condicao_ok(a, conta, m):
                continue
            reg = AutomacaoEnvio(automacao_id=a.id, conta_id=conta.id, email=usuario.email, status="enviando")
            db.session.add(reg)
            try:
                db.session.commit()  # reserva o envio (a outra instância do servidor não duplica)
            except IntegrityError:
                db.session.rollback()
                continue
            try:
                enviar_um(a, conta, usuario, m)
                reg.status = "enviado"
                feitos.append((a.chave, conta.id))
            except Exception as e:
                reg.status, reg.detalhe = "falhou", str(getattr(e, "detalhe", e))[:500]
            db.session.commit()
    return feitos


_iniciado = False


def iniciar_agendador(app):
    """Thread que roda as automações a cada N segundos no servidor web (uma por processo; o envio é idempotente)."""
    global _iniciado
    if _iniciado or not app.config.get("AUTOMACOES_ATIVAS"):
        return
    _iniciado = True

    def laco():
        time.sleep(30)
        while True:
            with app.app_context():
                try:
                    n = rodar()
                    if n:
                        log.info("Automações: %d e-mail(s) enviado(s)", len(n))
                except Exception:
                    log.exception("Falha no ciclo de automações")
                finally:
                    db.session.remove()
            time.sleep(max(60, app.config.get("AUTOMACOES_INTERVALO_S", 600)))
    threading.Thread(target=laco, daemon=True, name="automacoes").start()
