"""Genera data/financials_quarterly.csv desde Q1 2019 con datos de EDGAR."""
import json
from datetime import date

import pandas as pd

from src.fetch_edgar import (
    CLASE_MAGNITUD, CONCEPTOS, URL_COMPANYFACTS, completar_q4,
    extraer_serie_anual, extraer_serie_con_filed, extraer_serie_ytd,
    normalizar_acciones,
)
from src.http_client import ClienteHTTP

DESDE = "2019Q1"

# Campos expresados en numero de acciones: hay que normalizarlos a la base de
# split actual antes de usarlos, o la serie mezcla bases y salta de forma
# artificial (177 a 922 millones entre Q2 y Q3 de 2019).
CAMPOS_EN_ACCIONES = {"shares_diluted", "shares_outstanding"}


COMPONENTES_DEUDA = (
    "debt_current", "debt_noncurrent",
    "finance_lease_current", "finance_lease_noncurrent",
)


def componer_deuda_y_liquidez(df: pd.DataFrame) -> pd.DataFrame:
    """Deuda total del balance y serie completa de inversiones a corto plazo.

    La deuda de Tesla en XBRL viene repartida en cuatro conceptos cuya suma
    cuadra con las dos lineas del balance (en 2026Q2, 1.340 + 7.721 + 78 + 203
    = 1.418 + 7.924 = 9.342 millones). Si falta alguno, no hay total.

    Tesla no tuvo inversiones a corto plazo hasta 2021Q3 (30 M, via
    MarketableSecuritiesCurrent): antes la linea no aparece en el balance, asi
    que vale cero y no es un dato ausente. Un hueco posterior a su primera
    aparicion si lo seria, y se deja visible.
    """
    df = df.copy()
    df["total_debt"] = df[list(COMPONENTES_DEUDA)].sum(axis=1, min_count=4)
    primero = df["short_term_investments"].first_valid_index()
    if primero is not None:
        df.loc[df.index < primero, "short_term_investments"] = 0.0
    return df


def main() -> None:
    cliente = ClienteHTTP()
    facts = json.loads(cliente.obtener(URL_COMPANYFACTS, max_edad_horas=12))

    series: dict[str, dict[str, float]] = {}
    for campo, conceptos in CONCEPTOS.items():
        try:
            con_filed = extraer_serie_con_filed(facts, conceptos)
        except KeyError as exc:
            print(f"AVISO: {campo} no disponible -> {exc}")
            series[campo] = {}
            continue

        if campo in CAMPOS_EN_ACCIONES:
            serie = normalizar_acciones(con_filed)
        else:
            serie = {p: valor for p, (_, valor) in con_filed.items()}

        clase = CLASE_MAGNITUD.get(campo, "flujo")
        if clase == "flujo_ytd":
            # El estado de flujos se publica acumulado desde enero: hay que
            # desacumularlo. Ya salen trimestres discretos, sin pasar por Q4.
            serie = extraer_serie_ytd(facts, conceptos)
        elif clase == "flujo":
            # El 10-K informa del anio completo: Q4 se obtiene por diferencia
            anuales = extraer_serie_anual(facts, conceptos)
            antes = len(serie)
            serie = completar_q4(serie, anuales)
            if len(serie) > antes:
                print(f"{campo}: reconstruidos {len(serie) - antes} cuartos trimestres")
        elif clase == "no_aditiva":
            # Un promedio ponderado del ejercicio no es la suma de sus
            # trimestres: su Q4 no se puede reconstruir y queda vacio.
            if not [p for p in serie if p.endswith("Q4")]:
                print(f"{campo}: sin cuartos trimestres (magnitud no aditiva)")

        series[campo] = serie

    periodos = sorted({p for s in series.values() for p in s if p >= DESDE})
    hoy = date.today().isoformat()
    filas = []
    for periodo in periodos:
        fila = {"period": periodo}
        fila.update({campo: series[campo].get(periodo) for campo in series})
        fila["source"] = "SEC EDGAR companyfacts"
        fila["retrieved_at"] = hoy
        filas.append(fila)

    df = pd.DataFrame(filas)
    print(df[["period", "revenue_total", "operating_income"]].to_string())
    print(f"\n{len(df)} trimestres, de {periodos[0]} a {periodos[-1]}")
    print("\nCobertura por campo:")
    for columna in df.columns:
        print(f"  {columna}: {df[columna].notna().sum()}/{len(df)}")

    df = componer_deuda_y_liquidez(df)
    df.to_csv("data/financials_quarterly.csv", index=False)
    # La validacion completa (con "da", "filing_date" y los segmentos, que
    # anaden pasos posteriores) la hace src/cargar_todo.py al final.


if __name__ == "__main__":
    main()
