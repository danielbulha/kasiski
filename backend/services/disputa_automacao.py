"""Motor de decisão para simulação de lances; NUNCA envia lances a portais.

A integração transacional exige conector oficialmente autorizado e revisão separada.
"""
from decimal import Decimal, InvalidOperation, ROUND_DOWN, ROUND_UP
from datetime import datetime, timezone

class LanceBloqueado(ValueError):
    pass

def _num(value, label):
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise LanceBloqueado(f'{label} inválido.')
    if not d.is_finite():
        raise LanceBloqueado(f'{label} não é finito.')
    return d

def avaliar(disputa, *, fase_confirmada=False, dados_atualizados=False, autorizacao=False):
    """Retorna recomendação e bloqueios; sem efeito colateral e sem envio externo."""
    from services.disputa import sugerir
    bloqueios = []
    if disputa.status != 'em_disputa':
        bloqueios.append('A disputa não está em andamento.')
    if not fase_confirmada:
        bloqueios.append('A fase competitiva não foi confirmada.')
    if not dados_atualizados:
        bloqueios.append('Os eventos do portal não foram confirmados como atualizados.')
    if not autorizacao:
        bloqueios.append('Não há autorização expressa para esta simulação.')
    if disputa.preco_piso is None:
        bloqueios.append('Configure um limite financeiro antes de prosseguir.')
    s = sugerir(disputa)
    if s['situacao'] not in ('cobrir', 'no_piso') or s['proximo'] is None:
        bloqueios.append(s['mensagem'] or 'Não existe lance recomendado.')
    if s['espera_s'] > 0:
        bloqueios.append(f"Aguarde {s['espera_s']} segundos para respeitar o intervalo configurado.")
    candidato = s['proximo']
    if candidato is not None and disputa.preco_piso is not None:
        valor, piso = _num(candidato, 'Lance'), _num(disputa.preco_piso, 'Limite')
        if disputa.criterio == 'menor_preco' and valor < piso:
            bloqueios.append('Lance inferior ao limite financeiro.')
        if disputa.criterio == 'maior_desconto' and valor > piso:
            bloqueios.append('Desconto superior ao limite autorizado.')
    return {
        'modo': 'simulacao_sem_envio', 'apto': not bloqueios,
        'lance_sugerido': candidato if not bloqueios else None,
        'bloqueios': bloqueios, 'situacao': s['situacao'],
        'gerado_em': datetime.now(timezone.utc).isoformat(),
        'aviso': 'Nenhum lance foi transmitido a qualquer portal.'
    }
