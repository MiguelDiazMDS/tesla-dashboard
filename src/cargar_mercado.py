"""Genera data/market_monthly.csv: TSLA, SPY, tipo sin riesgo y EUR/USD."""
from datetime import date

import pandas as pd

from src.fetch_market import (
    cierres_mensuales, descargar_eurusd, descargar_precios, descargar_rf_10y,
)
from src.http_client import ClienteHTTP
from src.schema import MARKET
from src.validate import validar

DESDE = "2019-01"
RUTA = "data/market_monthly.csv"


def main() -> None:
    hoy = date.today()
    cliente = ClienteHTTP()
    tsla = cierres_mensuales(descargar_precios(cliente, "2019-01-01", hoy.isoformat()))
    spy = cierres_mensuales(descargar_precios(
        cliente, "2019-01-01", hoy.isoformat(), simbolo="SPY", clase="etf"))
    rf = descargar_rf_10y(cliente, 2019, hoy.year)
    fx = descargar_eurusd(cliente)

    meses = sorted(m for m in tsla if m >= DESDE)
    df = pd.DataFrame([{
        "month": m,
        "price_close": tsla[m],
        "spy_close": spy.get(m),
        "rf_10y": rf.get(m),
        "eurusd": fx.get(m),
        "source": "api.nasdaq.com (TSLA, SPY) + Tesoro de EE.UU. + BCE",
        "retrieved_at": hoy.isoformat(),
    } for m in meses])
    validar(df, MARKET)
    df.to_csv(RUTA, index=False)
    print(f"{len(df)} meses, de {meses[0]} a {meses[-1]}")
    print(df.tail(3).to_string(index=False))


if __name__ == "__main__":
    main()
