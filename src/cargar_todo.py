"""Regenera todos los ficheros de datos en el orden correcto y los verifica.

El orden importa: cargar_historico reescribe financials_quarterly.csv desde
cero y cargar_segmentos y cargar_estados le anaden columnas; cargar_deliveries
reescribe operating_quarterly.csv y cargar_update_letter le anade columnas.
"""
import pandas as pd

from src import (
    cargar_deliveries, cargar_estados, cargar_historico, cargar_mercado,
    cargar_segmentos, cargar_update_letter,
)
from src.coherence import comprobar_deliveries, revisar_financieros
from src.schema import FINANCIALS, MARKET, OPERATING
from src.validate import validar, validar_continuidad, validar_continuidad_mensual

PASOS = (
    ("financieros consolidados", cargar_historico.main),
    ("segmentos, lineas de producto y geografia", cargar_segmentos.main),
    ("amortizaciones y fechas de publicacion", cargar_estados.main),
    ("entregas y produccion", cargar_deliveries.main),
    ("Update Letter", cargar_update_letter.main),
    ("mercado", cargar_mercado.main),
)


def verificar() -> None:
    """Esquemas, continuidad e identidades contables. Lanza si algo falla."""
    financieros = pd.read_csv("data/financials_quarterly.csv")
    operativos = pd.read_csv("data/operating_quarterly.csv")
    mercado = pd.read_csv("data/market_monthly.csv")
    validar(financieros, FINANCIALS)
    validar(operativos, OPERATING)
    validar(mercado, MARKET)
    for df in (financieros, operativos):
        validar_continuidad(df["period"].tolist(), "2019Q1", df["period"].max())
    validar_continuidad_mensual(mercado["month"].tolist())
    for nombre, filas in revisar_financieros(financieros).items():
        print(f"  OK  {nombre} ({filas} filas)")
    print(f"  OK  las lineas de modelos suman las entregas "
          f"({comprobar_deliveries(operativos)} filas)")
    print("  OK  los tres ficheros validan contra su esquema, sin huecos")


def main() -> None:
    for nombre, paso in PASOS:
        print(f"\n=== {nombre} ===")
        paso()
    print("\n=== verificacion ===")
    verificar()


if __name__ == "__main__":
    main()
