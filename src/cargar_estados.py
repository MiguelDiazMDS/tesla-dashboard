"""Amortizaciones del estado de flujos y fecha de publicacion de cada trimestre.

La API companyfacts no trae la linea "Depreciation, amortization and
impairment" del estado de flujos: el concepto Depreciation que si trae cubre
solo una parte (4.120 millones en 2024). Se lee del estado renderizado, que va
acumulado desde enero y que ademas publica la columna del anio anterior. Esa
columna comparativa permite contrastar cada trimestre con el filing siguiente.

La fecha de publicacion es la del 10-Q o 10-K del trimestre. Los multiplos
mensuales la usan para no emplear datos que aun no se conocian.
"""
import re

import pandas as pd

from src.cargar_segmentos import periodo_de_fecha_informe
from src.fetch_segments import InformeNoEncontrado, parsear_tabla, resolver_informe
from src.filings import BASE_ARCHIVO, indice_filings
from src.http_client import ClienteHTTP

RUTA = "data/financials_quarterly.csv"
DESDE = "2019Q1"
INFORME_FLUJOS = "Consolidated Statements of Cash Flows"
# "Depreciation, amortization and impairment" y la antigua "Depreciation and
# amortization".
PATRON_DA = re.compile(r"^depreciation,? (and )?amortization", re.I)
MESES_10Q = {1: 3, 2: 6, 3: 9}
TOLERANCIA_COMPARATIVO = 0.005

# Reexpresiones de amortizaciones comprobadas a mano y aceptadas, por periodo.
# Hoy no hay ninguna: los 26 trimestres contrastados coinciden.
REEXPRESIONES_CONOCIDAS: set[str] = set()


class DiscrepanciaAmortizaciones(Exception):
    """Un trimestre no coincide con el comparativo del filing siguiente."""


def meses_acumulados(formulario: str, periodo: str) -> int:
    """Meses que acumula el estado de flujos de ese filing."""
    return 12 if formulario == "10-K" else MESES_10Q[int(periodo[5])]


def extraer_da(datos, meses: int, periodo: str) -> float | None:
    """Importe de amortizaciones de una columna, busque donde busque la fila.

    La fila cuelga de la seccion "Cash Flows from Operating Activities", que el
    parser trata como seccion porque es una fila sin cifras.
    """
    for metricas in datos.get((meses, periodo), {}).values():
        for etiqueta, valor in metricas.items():
            if PATRON_DA.match(etiqueta.strip()):
                return valor
    return None


def desacumular(acumulados: dict[str, tuple[int, float]]) -> dict[str, float]:
    """{periodo: (meses, acumulado)} -> {periodo: importe del trimestre}."""
    salida: dict[str, float] = {}
    for periodo, (_, valor) in acumulados.items():
        trimestre = int(periodo[5])
        if trimestre == 1:
            salida[periodo] = valor
            continue
        previo = acumulados.get(f"{periodo[:4]}Q{trimestre - 1}")
        if previo is not None:
            salida[periodo] = valor - previo[1]
    return salida


def discrepancias(acumulados, comparativos,
                   tolerancia: float = TOLERANCIA_COMPARATIVO) -> list[str]:
    """Periodos cuyo acumulado difiere del comparativo mas alla de la tolerancia."""
    return sorted(
        p for p, (m, v) in comparativos.items()
        if p in acumulados and acumulados[p][0] == m
        and abs(acumulados[p][1] - v) > tolerancia * abs(v)
        and p not in REEXPRESIONES_CONOCIDAS
    )


def listar_informes(indice: dict) -> list[tuple[str, str, str, str]]:
    """(accession, formulario, periodo, fecha de presentacion) de 10-Q y 10-K.

    `indice` es el diccionario de arrays ya unido por `indice_filings`, con las
    paginas antiguas de submissions incluidas.
    """
    salida = []
    for i, formulario in enumerate(indice["form"]):
        if formulario not in ("10-Q", "10-K"):
            continue
        periodo = periodo_de_fecha_informe(indice["reportDate"][i])
        if periodo and periodo >= DESDE:
            salida.append((indice["accessionNumber"][i], formulario, periodo,
                           indice["filingDate"][i]))
    return sorted(salida, key=lambda x: x[2])


def main() -> None:
    cliente = ClienteHTTP()
    indice = indice_filings(cliente)

    acumulados: dict[str, tuple[int, float]] = {}
    comparativos: dict[str, tuple[int, float]] = {}
    fechas: dict[str, str] = {}
    for accession, formulario, periodo, fecha in listar_informes(indice):
        fechas[periodo] = fecha
        base = f"{BASE_ARCHIVO}/{accession.replace('-', '')}"
        summary = cliente.obtener(f"{base}/FilingSummary.xml").decode(
            "utf-8", errors="replace")
        try:
            fichero = resolver_informe(summary, INFORME_FLUJOS)
        except InformeNoEncontrado:
            print(f"{periodo}: el filing no lista el estado de flujos")
            continue
        datos = parsear_tabla(cliente.obtener(f"{base}/{fichero}").decode(
            "utf-8", errors="replace"))
        meses = meses_acumulados(formulario, periodo)
        valor = extraer_da(datos, meses, periodo)
        if valor is None:
            print(f"{periodo}: sin linea de amortizaciones en {fichero}")
            continue
        acumulados[periodo] = (meses, valor)
        # La columna del anio anterior sirve para contrastar el filing previo.
        for (m, p) in datos:
            if p != periodo and m == meses:
                comparado = extraer_da(datos, m, p)
                if comparado is not None:
                    comparativos[p] = (m, comparado)

    periodos_discrepantes = discrepancias(acumulados, comparativos)
    print(f"Contrastados con el filing siguiente: "
          f"{sum(1 for p in comparativos if p in acumulados)} trimestres")
    mensajes = [
        f"{p}: {acumulados[p][1]/1e6:,.0f} M en su filing, "
        f"{comparativos[p][1]/1e6:,.0f} M como comparativo del siguiente"
        for p in periodos_discrepantes
    ]
    for m in mensajes:
        print(f"  DISCREPANCIA {m}")
    if periodos_discrepantes:
        raise DiscrepanciaAmortizaciones(
            "amortizaciones que no coinciden con el comparativo del filing "
            f"siguiente: {'; '.join(mensajes)}"
        )

    trimestres = desacumular(acumulados)
    df = pd.read_csv(RUTA)
    df["da"] = df["period"].map(trimestres)
    df["filing_date"] = df["period"].map(fechas)
    df.to_csv(RUTA, index=False)

    print(f"Amortizaciones: {df['da'].notna().sum()}/{len(df)} trimestres")
    print(f"Fecha de publicacion: {df['filing_date'].notna().sum()}/{len(df)}")
    df["anio"] = df["period"].str[:4]
    for anio, total in df.groupby("anio")["da"].sum(min_count=4).items():
        if pd.notna(total):
            print(f"  {anio}: {total/1e6:>8,.0f} M")


if __name__ == "__main__":
    main()
