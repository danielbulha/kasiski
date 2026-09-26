"""Tarefa agendada (Render Cron Job): atualiza o radar de todas as empresas com plano ativo.

Comando no Render:  python jobs/radar_diario.py
Agendamento sugerido: 0 9 * * 1-5  (UTC = 6h em Brasília, dias úteis)
"""
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app  # noqa: E402
from extensions import db  # noqa: E402
from models import Conta, Empresa  # noqa: E402
import planos  # noqa: E402
from services import fluxos  # noqa: E402

log = logging.getLogger("radar_diario")


def executar():
    with app.app_context():
        total = 0
        for conta in Conta.query.filter(Conta.plano != "suspenso"):
            if planos.teste_expirado(conta):
                continue
            for emp in Empresa.query.filter_by(conta_id=conta.id):
                if not (emp.palavras_chave or "").strip():
                    continue
                try:
                    novos, respostas = fluxos.atualizar_radar(emp)
                    planos.registrar_uso(conta, "radar", respostas, cobravel=False)
                    db.session.commit()
                    total += novos
                    log.info("%s: %d novos editais", emp.razao_social, novos)
                except Exception as e:
                    db.session.rollback()
                    log.warning("Falha no radar de %s: %s", emp.razao_social, e)
        fluxos.limpar_radar_antigo()
        db.session.commit()
        log.info("Radar concluído: %d novos editais no total", total)


if __name__ == "__main__":
    executar()
    # avisos de gestão de contratos rodam no mesmo agendamento (todo dia)
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "avisos_contratos", os.path.join(os.path.dirname(os.path.abspath(__file__)), "avisos_contratos.py"))
    avisos = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(avisos)
    avisos.executar()
