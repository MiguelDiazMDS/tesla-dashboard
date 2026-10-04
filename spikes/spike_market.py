"""Spike: cotizacion historica de TSLA y tipo de cambio EUR/USD.

Intento 1: Stooq (segun el enunciado de la tarea) como fuente de cotizacion,
sin autenticacion ni clave.

Resultado observado (2026-09-22): el endpoint de descarga de Stooq
(`stooq.com/q/d/l/...`) ya no devuelve CSV directamente. Con el User-Agent
por defecto de `requests` responde 404. Anadiendo un User-Agent de
navegador responde 200 pero con una pagina HTML que ejecuta un reto
"proof-of-work" en JavaScript (calcula un hash SHA-256 con dificultad y lo
envia a `/__verify` antes de servir el contenido real). Esto es un mecanismo
anti-bot: NO se intenta resolver por scripting (fuera de alcance y de las
normas de este entorno). Se documenta el fallo y se prueban alternativas
gratuitas sin clave, tal como permite la tarea.

Intento 2 (alternativa que SI funciona): el endpoint publico que usa la
propia web de nasdaq.com para pintar el grafico historico
(`api.nasdaq.com/api/quote/<TICKER>/historical`). No requiere clave, basta
un User-Agent de navegador.

BCE: el endpoint de datos de EXR (tipos de cambio de referencia) funciona
segun lo previsto en el enunciado, sin cambios.
"""
import io

import pandas as pd
import requests

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}

# --- Intento 1: Stooq -------------------------------------------------
print("=== Intento 1: Stooq ===")
variantes_stooq = [
    ("sin User-Agent, sin rango", "https://stooq.com/q/d/l/?s=tsla.us&i=d", {}),
    ("con User-Agent, con rango d1/d2",
     "https://stooq.com/q/d/l/?s=tsla.us&i=d&d1=20190101&d2=20260922",
     BROWSER_HEADERS),
]
for nombre, url, headers in variantes_stooq:
    r = requests.get(url, headers=headers, timeout=60)
    es_html_reto = "requires JavaScript to verify your browser" in r.text
    print(f"- {nombre}: status={r.status_code}, "
          f"content-type={r.headers.get('Content-Type')}, "
          f"reto_js_detectado={es_html_reto}")
print("Veredicto Stooq: bloqueado por un reto anti-bot (proof-of-work en "
      "JavaScript) en el endpoint de descarga. No se puede usar con "
      "requests simple sin implementar un bypass, lo cual queda fuera de "
      "alcance.\n")

# --- Intento 2: Nasdaq (alternativa gratuita sin clave) ---------------
print("=== Intento 2: api.nasdaq.com (alternativa) ===")
url_nasdaq = (
    "https://api.nasdaq.com/api/quote/TSLA/historical"
    "?assetclass=stocks&fromdate=2019-01-01&limit=9999&todate=2026-09-22"
)
r = requests.get(url_nasdaq, headers=BROWSER_HEADERS, timeout=60)
print("status:", r.status_code, r.headers.get("Content-Type"))
datos = r.json()["data"]
filas = datos["tradesTable"]["rows"]
print("totalRecords:", datos["totalRecords"], "| filas devueltas:", len(filas))

precios = pd.DataFrame(filas)
precios["Date"] = pd.to_datetime(precios["date"], format="%m/%d/%Y")
precios["Close"] = precios["close"].str.replace("$", "", regex=False).astype(float)
precios = precios.sort_values("Date").reset_index(drop=True)

print("TSLA:", precios["Date"].min().date(), "->", precios["Date"].max().date(),
      f"({len(precios)} sesiones)")
print(precios[["Date", "Close"]].tail(3).to_string())

mensual = precios.set_index("Date")["Close"].resample("ME").last()
print("\nCierres mensuales desde 2019:")
print(mensual["2019":].head(3).to_string())
print(mensual.tail(3).to_string())

# --- Paso 3: verificacion critica del ajuste por split -----------------
print("\n=== Verificacion de ajuste por split ===")
print("Cierre 2019-01-02:", precios.loc[precios["Date"] == "2019-01-02", "Close"].values)
print("(si ronda 20 USD -> ajustada; si ronda 300 USD -> NO ajustada)\n")

print("Sesiones alrededor del split 5:1 (31-ago-2020):")
ventana1 = precios[(precios["Date"] >= "2020-08-25") & (precios["Date"] <= "2020-09-03")]
print(ventana1[["Date", "Close"]].to_string())

print("\nSesiones alrededor del split 3:1 (25-ago-2022):")
ventana2 = precios[(precios["Date"] >= "2022-08-19") & (precios["Date"] <= "2022-08-30")]
print(ventana2[["Date", "Close"]].to_string())

# --- BCE: EUR/USD -------------------------------------------------------
print("\n=== BCE: EUR/USD ===")
fx = requests.get(
    "https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A"
    "?format=csvdata&startPeriod=2019-01-01",
    timeout=60,
).text
tipos = pd.read_csv(io.StringIO(fx))
print("EUR/USD del BCE:", tipos.shape)
print(tipos[["TIME_PERIOD", "OBS_VALUE"]].head(3).to_string())
print(tipos[["TIME_PERIOD", "OBS_VALUE"]].tail(3).to_string())
