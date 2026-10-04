"""Spike: estructura de la nota de prensa de Production, Deliveries & Deployments.

Version adaptada tras la exploracion inicial. Respecto a la plantilla original
de la tarea (una URL fija de ir.tesla.com), lo que realmente funciona es:

1. `ir.tesla.com` bloquea la navegacion automatizada con un desafio Akamai
   (ya documentado en tareas previas de fase 0), asi que la via directa
   queda descartada de entrada.
2. En EDGAR, la nota de deliveries **no tiene una URL predecible por
   trimestre**: no hay una plantilla estable de nombre de fichero. Hay que
   localizarla en dos pasos:
   a) listar los 8-K recientes de Tesla via
      `https://data.sec.gov/submissions/CIK0001318605.json` y quedarse con
      los que tienen el item `2.02` (Results of Operations) Y fecha de
      presentacion cercana al cierre del trimestre (los primeros dias del
      mes siguiente) — asi se distingue del 8-K de resultados/Update
      Letter, que tambien lleva item `2.02` pero se presenta ~3 semanas
      despues.
   b) dentro de ese filing, el exhibit 99.1 (la nota en si) **tampoco tiene
      un nombre de fichero predecible**: en 2019 se llama
      `tsla-ex991_14.htm`, en 2026 se llama `exhibit99111111.htm`. La forma
      generica y estable de localizarlo es descargar el `.txt` de la
      submission completa (que SI tiene una URL predecible,
      `<accession>.txt`) y buscar con una expresion regular el bloque
      `<TYPE>EX-99.1 ... <FILENAME>...`, que es un formato SGML que EDGAR
      mantiene igual desde hace decadas.
3. Los ficheros que sirve EDGAR vienen envueltos en el mismo preambulo SGML
   ya visto en las tareas de Segmentos y Update Letter
   (`<DOCUMENT><TYPE>...<TEXT><html>...`), asi que hay que recortar el
   fragmento `<html ... </html>` antes de pasarlo a `pandas.read_html`.
"""
import os
import re
import sys
from io import StringIO

import pandas as pd
import requests
from bs4 import BeautifulSoup

UA = os.environ.get("SEC_USER_AGENT")
if not UA:
    sys.exit("Define SEC_USER_AGENT antes de ejecutar (ver .env)")
H = {"User-Agent": UA}

CIK = "1318605"
os.makedirs("cache", exist_ok=True)


def html_puro(raw: str) -> str:
    """Recorta el envoltorio SGML <DOCUMENT>...<TEXT> que antecede al <html> real."""
    inicio = raw.find("<html")
    fin = raw.rfind("</html>")
    if inicio == -1 or fin == -1:
        # Algunos exhibits antiguos usan <HTML> en mayusculas.
        inicio = raw.find("<HTML")
        fin = raw.rfind("</HTML>")
    if inicio == -1 or fin == -1:
        return raw
    return raw[inicio : fin + 7]


def localizar_exhibit_991(accession: str) -> str | None:
    """Dado un accession number, devuelve la URL del exhibit EX-99.1 del filing.

    Se resuelve via el .txt de la submission completa (URL predecible:
    <accession>.txt), buscando el bloque SGML <TYPE>EX-99.1<FILENAME>...
    en vez de adivinar el nombre del fichero individual, que NO es estable
    entre eras (ver docstring del modulo).
    """
    acc_sin_guiones = accession.replace("-", "")
    base = f"https://www.sec.gov/Archives/edgar/data/{CIK}/{acc_sin_guiones}"
    txt = requests.get(f"{base}/{accession}.txt", headers=H, timeout=60).text
    m = re.search(r"<TYPE>EX-99\.1\s*\n<SEQUENCE>\d+\s*\n<FILENAME>([^\n]+)", txt)
    if not m:
        return None
    return f"{base}/{m.group(1).strip()}"


def es_nota_de_deliveries(texto_plano: str) -> bool:
    """Distingue la nota de deliveries (texto corto) del exhibit 99.1 del
    8-K de resultados (que en anios recientes es el propio Update Letter
    volcado como imagenes, sin tabla de Production/Deliveries en texto)."""
    return "Production" in texto_plano and (
        "Deliveries" in texto_plano or "Delivery" in texto_plano
    )


# --- Paso 1: listar 8-K recientes y quedarse con los candidatos a nota de deliveries ---
subs = requests.get(
    f"https://data.sec.gov/submissions/CIK000{CIK}.json", headers=H, timeout=60
).json()
recientes = subs["filings"]["recent"]
n = len(recientes["form"])
candidatos = [
    {
        "accession": recientes["accessionNumber"][i],
        "reportDate": recientes["reportDate"][i],
        "filingDate": recientes["filingDate"][i],
        "items": recientes["items"][i],
    }
    for i in range(n)
    if recientes["form"][i] == "8-K" and "2.02" in recientes["items"][i]
]
print(f"8-K con item 2.02 encontrados: {len(candidatos)}")

# Heuristica de fecha: la nota de deliveries se presenta ~2 dias despues del
# cierre de trimestre (dia del mes <= 10); el 8-K de resultados/Update
# Letter, que TAMBIEN lleva item 2.02, se presenta ~3 semanas despues
# (dia del mes >= 15). Nos quedamos con el candidato mas reciente de la
# primera clase.
candidatos_deliveries = [
    c for c in candidatos if int(c["filingDate"][8:10]) <= 10
]
print(f"Candidatos por heuristica de fecha (dia <=10 del mes): {len(candidatos_deliveries)}")
for c in candidatos_deliveries[:5]:
    print("  ", c)

if not candidatos_deliveries:
    sys.exit("No se ha localizado ningun 8-K candidato a nota de deliveries")

elegido = candidatos_deliveries[0]
print(f"\nFiling elegido (mas reciente): {elegido}")

URL = localizar_exhibit_991(elegido["accession"])
print(f"URL del exhibit 99.1 resuelta: {URL}")
if URL is None:
    sys.exit("No se ha encontrado el exhibit EX-99.1 en la submission .txt")

# --- Paso 2: descargar la nota y volcar su estructura ---
html_crudo = requests.get(URL, headers=H, timeout=60).text
html = html_puro(html_crudo)
sopa = BeautifulSoup(html, "lxml")

for titular in sopa.find_all(["h1", "h2", "h3"]):
    print("TITULAR:", titular.get_text(strip=True))

texto_plano = sopa.get_text("|", strip=True)
print("\nTEXTO PLANO (primeros 2000 caracteres):")
print(texto_plano[:2000])

if not es_nota_de_deliveries(texto_plano):
    print(
        "\n[AVISO] El texto no contiene 'Production' + 'Deliveries'; puede "
        "que la heuristica de fecha haya elegido el filing equivocado."
    )

tablas = pd.read_html(StringIO(html))
print(f"\n{len(tablas)} tablas encontradas")
for i, t in enumerate(tablas):
    print(f"\n--- tabla {i} ---")
    print(t.to_string())

# --- Paso 3: comprobacion de histórico (2019/2020) ---
# Filing de referencia ya localizado a mano durante la exploracion:
# 0001564590-19-024414 (8-K del 2019-07-02, nota de Q2 2019).
ACCESSION_HISTORICO = "0001564590-19-024414"
print(f"\n\n===== COMPROBACION HISTORICO: {ACCESSION_HISTORICO} (Q2 2019) =====")
url_historico = localizar_exhibit_991(ACCESSION_HISTORICO)
print("URL exhibit historico:", url_historico)
html_crudo_hist = requests.get(url_historico, headers=H, timeout=60).text
html_hist = html_puro(html_crudo_hist)
sopa_hist = BeautifulSoup(html_hist, "lxml")
texto_hist = sopa_hist.get_text("|", strip=True)
print("TEXTO PLANO (primeros 1200 caracteres):")
print(texto_hist[:1200])
tablas_hist = pd.read_html(StringIO(html_hist))
print(f"\n{len(tablas_hist)} tablas encontradas (historico)")
for i, t in enumerate(tablas_hist):
    print(f"\n--- tabla historico {i} ---")
    print(t.to_string())
