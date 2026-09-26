"""Aviso diário de gestão de contratos: renova as rotinas periódicas na agenda e envia, por e-mail,
os prazos vencidos e dos próximos 7 dias (vigência, prorrogação, garantia, reajuste, medição, faturamento).

Roda junto com o radar (jobs/radar_diario.py) ou sozinho:  python jobs/avisos_contratos.py
"""
import html
import logging
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app  # noqa: E402
from extensions import db  # noqa: E402
from models import Conta, Contrato, Empresa, Usuario  # noqa: E402
import planos  # noqa: E402
from services import contratos as gestao  # noqa: E402
from services import email  # noqa: E402

log = logging.getLogger("avisos_contratos")


def _corpo(conta, prazos):
    hoje = date.today()
    linhas_txt, linhas_html = [], []
    for p in prazos:
        d = p.data.date()
        quando = "VENCIDO" if d < hoje else "hoje" if d == hoje else f"em {(d - hoje).days} dia(s)"
        linhas_txt.append(f"- {d.strftime('%d/%m')} ({quando}): {p.titulo}")
        cor = "#B02A1F" if d <= hoje else "#8A5A00" if (d - hoje).days <= 3 else "#071D2D"
        linhas_html.append(f"<tr><td style='padding:6px 10px;color:{cor};white-space:nowrap'><b>{d.strftime('%d/%m')}</b> · {quando}</td>"
                           f"<td style='padding:6px 10px'>{html.escape(p.titulo)}<br><small style='color:#4F6373'>{html.escape(p.fundamento or '')}</small></td></tr>")
    url = app.config["FRONTEND_URL"] + "/#/contratos"
    texto = f"Prazos de gestão dos seus contratos:\n\n" + "\n".join(linhas_txt) + f"\n\nAbra o Kasiski: {url}"
    corpo = (f"<div style='font-family:Inter,Arial,sans-serif;max-width:620px;color:#071D2D'><p style='font-size:18px;font-weight:800'>Kasiski · gestão de contratos</p>"
             f"<p>Estes são os prazos de gestão que pedem atenção em {html.escape(conta.nome)}:</p>"
             f"<table style='border-collapse:collapse;font-size:14px'>{''.join(linhas_html)}</table>"
             f"<p style='margin-top:18px'><a href='{url}' style='background:#071D2D;color:#fff;padding:10px 16px;border-radius:6px;text-decoration:none'>Abrir a gestão de contratos</a></p>"
             f"<p style='color:#4F6373;font-size:12px'>Marque cada item como concluído na agenda para ele sair deste aviso.</p></div>")
    return texto, corpo


def executar():
    with app.app_context():
        hoje, enviados = date.today(), 0
        for conta in Conta.query.filter(Conta.plano != "suspenso"):
            ids = [e.id for e in Empresa.query.filter_by(conta_id=conta.id)]
            if not ids:
                continue
            try:
                for c in Contrato.query.filter(Contrato.empresa_id.in_(ids)):
                    gestao.gerar_prazos(c)   # mantém as próximas ocorrências das rotinas na agenda
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                log.warning("Falha ao renovar prazos de %s: %s", conta.nome, e)
                continue
            if conta.ultimo_aviso_contratos == hoje or planos.teste_expirado(conta):
                continue
            prazos = gestao.resumo_avisos(conta.id)
            if not prazos or not email.configurado():
                continue
            texto, corpo = _corpo(conta, prazos)
            try:
                for u in Usuario.query.filter_by(conta_id=conta.id):
                    email.enviar(u.email, f"Kasiski: {len(prazos)} prazo(s) de gestão de contratos", texto, corpo)
                conta.ultimo_aviso_contratos = hoje
                db.session.commit()
                enviados += 1
            except Exception as e:
                db.session.rollback()
                log.warning("Aviso de contratos não enviado para %s: %s", conta.nome, e)
        log.info("Avisos de contratos enviados para %d conta(s)", enviados)


if __name__ == "__main__":
    executar()
