"""Contagem de prazos em dias úteis (Lei 14.133, art. 183: exclui o dia do começo e inclui o do vencimento;
em dias úteis, contam-se apenas os dias de expediente). Feriados nacionais fixos e móveis incluídos.
Feriados estaduais/municipais: cadastre em FERIADOS_EXTRAS (AAAA-MM-DD, separados por vírgula)."""
import os
from datetime import date, datetime, timedelta
from functools import lru_cache


def _pascoa(ano):
    a = ano % 19; b = ano // 100; c = ano % 100; d = b // 4; e = b % 4
    f = (b + 8) // 25; g = (b - f + 1) // 3; h = (19 * a + b - d - g + 15) % 30
    i = c // 4; k = c % 4; l = (32 + 2 * e + 2 * i - h - k) % 7; m = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * m + 114) // 31; dia = ((h + l - 7 * m + 114) % 31) + 1
    return date(ano, mes, dia)


@lru_cache(maxsize=32)
def feriados(ano):
    fixos = [(1, 1), (4, 21), (5, 1), (9, 7), (10, 12), (11, 2), (11, 15), (11, 20), (12, 25)]
    fs = {date(ano, m, d) for m, d in fixos}
    p = _pascoa(ano)
    fs |= {p - timedelta(days=48), p - timedelta(days=47), p - timedelta(days=2), p + timedelta(days=60)}
    for x in os.getenv("FERIADOS_EXTRAS", "").split(","):
        try:
            dt = datetime.strptime(x.strip(), "%Y-%m-%d").date()
            if dt.year == ano:
                fs.add(dt)
        except ValueError:
            pass
    return fs


def dia_util(d):
    return d.weekday() < 5 and d not in feriados(d.year)


def somar_uteis(inicio, n):
    """n dias úteis depois de `inicio` (exclui o dia do começo)."""
    d = inicio
    contados = 0
    while contados < n:
        d += timedelta(days=1)
        if dia_util(d):
            contados += 1
    return d


def subtrair_uteis(referencia, n):
    """Último dia para agir quando a lei diz 'até n dias úteis antes' da data de referência."""
    d = referencia
    contados = 0
    while contados < n:
        d -= timedelta(days=1)
        if dia_util(d):
            contados += 1
    return d


def fim_do_dia(d):
    return datetime(d.year, d.month, d.day, 23, 59)
