"""Indice completo de filings de Tesla en EDGAR.

El JSON de submissions solo trae en `filings.recent` los ~1.000 filings mas
recientes; el resto esta en paginas aparte listadas en `filings.files`. Leer
solo `recent` funciona hoy (el mas antiguo de esos ~1.000 filings es el 10-Q de
2018Q1, presentado el 2018-05-07), pero como Tesla presenta 100-150 filings al
anio, el 10-Q de 2019Q1 se iria quedando fuera de `recent` hacia 2027. Cada
pagina antigua es un JSON con los mismos arrays a nivel superior, sin el
envoltorio `filings`.
"""
import json

CIK = "1318605"
URL_SUBMISSIONS = f"https://data.sec.gov/submissions/CIK{int(CIK):010d}.json"
URL_PAGINA = "https://data.sec.gov/submissions/{nombre}"
BASE_ARCHIVO = f"https://www.sec.gov/Archives/edgar/data/{CIK}"
COLUMNAS = ("form", "reportDate", "filingDate", "accessionNumber")


def unir_indice(principal: dict, paginas: list[dict]) -> dict[str, list]:
    """Une `filings.recent` con las paginas antiguas en un solo indice."""
    indice = {c: list(principal["filings"]["recent"][c]) for c in COLUMNAS}
    for pagina in paginas:
        for c in COLUMNAS:
            indice[c].extend(pagina[c])
    return indice


def indice_filings(cliente) -> dict[str, list]:
    """Indice completo, con las paginas antiguas incluidas."""
    principal = json.loads(cliente.obtener(URL_SUBMISSIONS, max_edad_horas=12))
    paginas = [
        json.loads(cliente.obtener(URL_PAGINA.format(nombre=p["name"]),
                                   max_edad_horas=12))
        for p in principal["filings"].get("files", [])
    ]
    return unir_indice(principal, paginas)
