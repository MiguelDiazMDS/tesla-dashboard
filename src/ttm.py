"""Magnitudes de los ultimos doce meses, tal como se conocian en una fecha.

Solo cuentan los trimestres cuyo 10-Q o 10-K ya se habia presentado en esa
fecha. Asi los multiplos historicos no usan datos que el mercado aun no tenia.
"""
import pandas as pd

FLUJOS_TTM = ("revenue_total", "operating_income", "net_income_gaap",
              "ocf", "capex", "da")
SALDOS = ("cash_and_investments", "short_term_investments",
          "total_debt", "shares_outstanding")


def _indice(periodo: str) -> int:
    return int(periodo[:4]) * 4 + int(periodo[5]) - 1


def ttm_en(df: pd.DataFrame, fecha: str, flujos=FLUJOS_TTM,
           saldos=SALDOS) -> dict | None:
    """Suma de los cuatro ultimos trimestres publicados y saldos del ultimo.

    `fecha` en formato ISO. Devuelve None si no hay cuatro trimestres
    consecutivos publicados o si falta algun dato.
    """
    visibles = df[df["filing_date"].notna() & (df["filing_date"] <= fecha)]
    visibles = visibles.sort_values("period")
    if len(visibles) < 4:
        return None
    ultimos = visibles.tail(4)
    indices = [_indice(p) for p in ultimos["period"]]
    if indices != list(range(indices[0], indices[0] + 4)):
        return None

    salida: dict = {"periodo": ultimos["period"].iloc[-1]}
    for campo in flujos:
        if ultimos[campo].isna().any():
            return None
        salida[campo] = float(ultimos[campo].sum())
    for campo in saldos:
        valor = ultimos[campo].iloc[-1]
        if pd.isna(valor):
            return None
        salida[campo] = float(valor)
    return salida
