"""Multiplos mensuales con los datos conocidos en cada fecha.

Cada mes usa el cierre de la accion y los doce ultimos meses de estados
financieros ya publicados a fin de mes. El valor de empresa descuenta la caja
y las inversiones a corto plazo: estas llegan a doblar la caja en 2026.
"""
import calendar

import pandas as pd

from src.ttm import ttm_en

MULTIPLOS = ("ev_ventas", "per", "ev_ebitda", "p_fcf")


def fin_de_mes(mes: str) -> str:
    """"2024-02" -> "2024-02-29"."""
    anio, numero = int(mes[:4]), int(mes[5:7])
    return f"{mes}-{calendar.monthrange(anio, numero)[1]:02d}"


def _cociente(numerador: float, denominador: float) -> float | None:
    """Un multiplo sobre una magnitud negativa o nula no tiene sentido."""
    return numerador / denominador if denominador > 0 else None


def multiplos_mensuales(financieros: pd.DataFrame, mercado: pd.DataFrame) -> pd.DataFrame:
    filas = []
    for _, mes in mercado.iterrows():
        t = ttm_en(financieros, fin_de_mes(mes["month"]))
        if t is None:
            continue
        cap = mes["price_close"] * t["shares_outstanding"]
        ev = cap + t["total_debt"] - t["cash_and_investments"] - t["short_term_investments"]
        filas.append({
            "month": mes["month"],
            "ttm_hasta": t["periodo"],
            "capitalizacion": cap,
            "ev": ev,
            "ev_ventas": _cociente(ev, t["revenue_total"]),
            "per": _cociente(cap, t["net_income_gaap"]),
            "ev_ebitda": _cociente(ev, t["operating_income"] + t["da"]),
            "p_fcf": _cociente(cap, t["ocf"] - t["capex"]),
        })
    return pd.DataFrame(filas, columns=["month", "ttm_hasta", "capitalizacion", "ev", *MULTIPLOS])


def percentil_actual(serie: pd.Series) -> float | None:
    """Fraccion de meses con un multiplo igual o menor que el del ultimo mes."""
    serie = pd.to_numeric(serie, errors="coerce")
    if serie.empty or pd.isna(serie.iloc[-1]):
        return None
    validos = serie.dropna()
    return float((validos <= serie.iloc[-1]).mean())
