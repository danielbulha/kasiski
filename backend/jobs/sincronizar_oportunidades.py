"""Tarefa diária: movimenta os cartões do Kanban de oportunidades conforme os eventos públicos do PNCP
(sessão iniciada, revogação/anulação, resultado homologado, contrato publicado).

Roda no mesmo agendamento do radar (jobs/radar_diario.py) ou sozinha:  python jobs/sincronizar_oportunidades.py
"""
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app  # noqa: E402
from models import Conta, Empresa  # noqa: E402
import planos  # noqa: E402
from services import oportunidades  # noqa: E402

log = logging.getLogger("sincronizar_oportunidades")


def executar():
    with app.app_context():
        total = 0
        for conta in Conta.query.filter(Conta.plano != "suspenso"):
            if planos.teste_expirado(conta):
                continue
            for emp in Empresa.query.filter_by(conta_id=conta.id):
                try:
                    n = oportunidades.sincronizar_empresa(emp)
                    total += n
                    if n:
                        log.info("%s: %d oportunidade(s) mudaram de etapa", emp.razao_social, n)
                except Exception as e:
                    log.warning("Falha ao sincronizar oportunidades de %s: %s", emp.razao_social, e)
        log.info("Sincronização concluída: %d cartão(ões) movimentado(s)", total)


if __name__ == "__main__":
    executar()
