"""Cotizacion mensual de TSLA y SPY, tipo sin riesgo del Tesoro y EUR/USD.

La cotizacion viene de un endpoint interno de Nasdaq, sin contrato publico:
se aisla aqui y se valida la forma de la respuesta para que un cambio de
formato se detecte en el momento en vez de corromper los datos.
"""
import io
import json
from datetime import date

import pandas as pd

URL_BCE = (
    "https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A"
    "?format=csvdata&startPeriod=2019-01-01"
)


class RespuestaInesperada(Exception):
    """La fuente ha cambiado de formato: mejor fallar que escribir basura."""


def url_nasdaq(desde: str, hasta: str, simbolo: str = "TSLA",
               clase: str = "stocks") -> str:
    """Historico diario de un valor. Fechas en formato ISO.

    El indice SPX no esta disponible en esta fuente; para la beta se usa el ETF
    SPY, con clase "etf".
    """
    return (
        f"https://api.nasdaq.com/api/quote/{simbolo}/historical"
        f"?assetclass={clase}&fromdate={desde}&todate={hasta}&limit=9999"
    )


def parsear_nasdaq(crudo: bytes) -> pd.DataFrame:
    """DataFrame con columnas Date y Close a partir del JSON de Nasdaq.

    La serie que sirve Nasdaq ya esta ajustada por los splits de 2020 y 2022,
    comprobado en la fase 0.
    """
    datos = json.loads(crudo)
    try:
        filas = datos["data"]["tradesTable"]["rows"]
    except (KeyError, TypeError) as exc:
        raise RespuestaInesperada(
            f"El JSON de Nasdaq no tiene data.tradesTable.rows: {exc}"
        ) from exc
    if not filas:
        raise RespuestaInesperada("Nasdaq ha devuelto cero sesiones")

    df = pd.DataFrame(filas)
    df["Date"] = pd.to_datetime(df["date"], format="%m/%d/%Y")
    df["Close"] = (
        df["close"].str.replace(r"[\$,]", "", regex=True).astype(float)
    )
    return df[["Date", "Close"]].sort_values("Date").reset_index(drop=True)


def cierres_mensuales(df: pd.DataFrame) -> dict[str, float]:
    """Ultimo cierre de cada mes, con el mes en formato "2019-01"."""
    serie = df.set_index("Date")["Close"].resample("ME").last()
    return {fecha.strftime("%Y-%m"): float(valor)
            for fecha, valor in serie.items() if pd.notna(valor)}


def descargar_precios(cliente, desde: str, hasta: str, simbolo: str = "TSLA",
                      clase: str = "stocks") -> pd.DataFrame:
    return parsear_nasdaq(cliente.obtener(url_nasdaq(desde, hasta, simbolo, clase)))


def descargar_eurusd(cliente) -> dict[str, float]:
    crudo = cliente.obtener(URL_BCE, max_edad_horas=12).decode("utf-8")
    df = pd.read_csv(io.StringIO(crudo))
    df["fecha"] = pd.to_datetime(df["TIME_PERIOD"])
    serie = df.set_index("fecha")["OBS_VALUE"].resample("ME").last()
    return {fecha.strftime("%Y-%m"): float(valor)
            for fecha, valor in serie.items() if pd.notna(valor)}


def url_tesoro(anio: int) -> str:
    """CSV diario de la curva de tipos del Tesoro de EE.UU. para un anio."""
    return (
        "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
        f"daily-treasury-rates.csv/{anio}/all?type=daily_treasury_yield_curve"
        f"&field_tdr_date_value={anio}&page&_format=csv"
    )


def parsear_tesoro(crudo: bytes) -> dict[str, float]:
    """Ultimo rendimiento del bono a 10 anios de cada mes, en tanto por uno."""
    df = pd.read_csv(io.StringIO(crudo.decode("utf-8")))
    if "Date" not in df.columns or "10 Yr" not in df.columns:
        raise RespuestaInesperada(
            "el CSV del Tesoro no trae las columnas Date y 10 Yr")
    df["fecha"] = pd.to_datetime(df["Date"], format="%m/%d/%Y")
    serie = df.set_index("fecha").sort_index()["10 Yr"].resample("ME").last()
    return {f.strftime("%Y-%m"): float(v) / 100
            for f, v in serie.items() if pd.notna(v)}


def descargar_rf_10y(cliente, desde_anio: int, hasta_anio: int) -> dict[str, float]:
    """Tipo sin riesgo mensual. FRED no responde de forma fiable: fuente primaria."""
    salida: dict[str, float] = {}
    for anio in range(desde_anio, hasta_anio + 1):
        # El fichero del anio en curso cambia cada dia; los anteriores, nunca.
        caducidad = 12 if anio == date.today().year else None
        salida.update(parsear_tesoro(cliente.obtener(url_tesoro(anio),
                                                     max_edad_horas=caducidad)))
    return salida
