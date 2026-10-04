"""Anade segmentos, lineas de producto y geografia a financials_quarterly.csv.

Recorre los 10-Q y 10-K desde 2019 resolviendo en cada uno los tres informes
que interesan a traves de su FilingSummary.xml, en vez de recorrer a ciegas los
sesenta y seis estados renderizados. Son tres peticiones por filing.

Los 10-Q publican el trimestre; los 10-K publican el ejercicio completo, asi
que el cuarto trimestre se obtiene por diferencia igual que el resto de
magnitudes de flujo.
"""
from datetime import date

import pandas as pd

from src.fetch_edgar import completar_q4
from src.fetch_segments import (
    INFORME_GEOGRAFIA, INFORME_LINEAS, INFORME_SEGMENTOS, InformeNoEncontrado,
    extraer_geografia, extraer_lineas_producto, extraer_segmentos,
    parsear_tabla, resolver_informe,
)
from src.filings import BASE_ARCHIVO, indice_filings
from src.http_client import ClienteHTTP, ErrorDescarga

DESDE = "2019Q1"

INFORMES = (
    (INFORME_SEGMENTOS, extraer_segmentos),
    (INFORME_LINEAS, extraer_lineas_producto),
    (INFORME_GEOGRAFIA, extraer_geografia),
)


def periodo_de_fecha_informe(fecha: str) -> str | None:
    """"2026-06-30" -> "2026Q2". None si no es un cierre trimestral."""
    f = date.fromisoformat(fecha)
    trimestre = {3: 1, 6: 2, 9: 3, 12: 4}.get(f.month)
    return f"{f.year}Q{trimestre}" if trimestre else None


def listar_filings(cliente: ClienteHTTP) -> list[tuple[str, str, str]]:
    """(accession, formulario, periodo) de los 10-Q y 10-K desde 2019."""
    indice = indice_filings(cliente)
    salida = []
    for i, formulario in enumerate(indice["form"]):
        if formulario not in ("10-Q", "10-K"):
            continue
        periodo = periodo_de_fecha_informe(indice["reportDate"][i])
        if periodo and periodo >= DESDE:
            salida.append((indice["accessionNumber"][i], formulario, periodo))
    return sorted(salida, key=lambda x: x[2])


def leer_filing(cliente: ClienteHTTP, accession: str, formulario: str,
                periodo: str) -> dict[str, float]:
    """Los tres informes de un filing, para su periodo propio.

    Un 10-Q trae el trimestre (3 meses); un 10-K, el ejercicio (12 meses).
    """
    base = f"{BASE_ARCHIVO}/{accession.replace('-', '')}"
    meses = 12 if formulario == "10-K" else 3
    try:
        summary = cliente.obtener(f"{base}/FilingSummary.xml").decode(
            "utf-8", errors="replace")
    except ErrorDescarga:
        raise
    except Exception as exc:
        print(f"  {periodo}: no se pudo leer el FilingSummary -> {exc}")
        return {}

    fila: dict[str, float] = {}
    for nombre, extraer in INFORMES:
        try:
            fichero = resolver_informe(summary, nombre)
        except InformeNoEncontrado:
            continue
        try:
            html = cliente.obtener(f"{base}/{fichero}").decode(
                "utf-8", errors="replace")
            fila.update(extraer(parsear_tabla(html), meses, periodo))
        except ErrorDescarga:
            raise
        except Exception as exc:
            print(f"  {periodo}: fallo al parsear {fichero} -> "
                  f"{type(exc).__name__}: {exc}")
    return fila


LINEAS_AUTO_SIN_LEASING = (
    "revenue_auto_sales", "revenue_reg_credits", "revenue_services",
)


def completar_leasing(fila: dict[str, float]) -> dict[str, float]:
    """Deduce el leasing de automocion cuando el filing no lo desglosa.

    Hasta 2022 Tesla presentaba los ingresos por arrendamiento agregados, sin
    repartirlos entre automocion y energia. Como si publica el total del
    segmento y las otras tres lineas, la diferencia da el leasing de forma
    exacta; no es una estimacion.
    """
    if "revenue_auto_leasing" in fila:
        return fila
    segmento = fila.get("revenue_auto_segment")
    if segmento is None:
        return fila
    if not all(c in fila for c in LINEAS_AUTO_SIN_LEASING):
        return fila
    resto = segmento - sum(fila[c] for c in LINEAS_AUTO_SIN_LEASING)
    if resto >= 0:
        fila["revenue_auto_leasing"] = resto
    return fila


def main() -> None:
    cliente = ClienteHTTP()
    filings = listar_filings(cliente)
    print(f"{len(filings)} filings desde {DESDE}\n")

    trimestrales: dict[str, dict[str, float]] = {}
    anuales: dict[str, dict[int, float]] = {}

    for accession, formulario, periodo in filings:
        fila = completar_leasing(leer_filing(cliente, accession, formulario, periodo))
        if not fila:
            print(f"{periodo} ({formulario}): sin datos")
            continue
        if formulario == "10-K":
            # El informe anual da el ejercicio: Q4 se calcula por diferencia.
            for campo, valor in fila.items():
                anuales.setdefault(campo, {})[int(periodo[:4])] = valor
            print(f"{periodo} ({formulario}): {len(fila)} campos, ejercicio completo")
        else:
            trimestrales[periodo] = fila
            print(f"{periodo} ({formulario}): {len(fila)} campos")

    # Reorganizar a {campo: {periodo: valor}} y reconstruir los Q4
    series: dict[str, dict[str, float]] = {}
    for periodo, fila in trimestrales.items():
        for campo, valor in fila.items():
            series.setdefault(campo, {})[periodo] = valor
    for campo, por_anio in anuales.items():
        antes = len(series.get(campo, {}))
        series[campo] = completar_q4(series.get(campo, {}), por_anio)
        reconstruidos = len(series[campo]) - antes
        if reconstruidos:
            print(f"{campo}: {reconstruidos} cuartos trimestres reconstruidos")

    df = pd.read_csv("data/financials_quarterly.csv")
    for campo, serie in series.items():
        df[campo] = df["period"].map(serie)

    # Tesla dejo de publicar el coste por segmento y solo da el margen bruto.
    # La resta lo recupera de forma exacta, no es una estimacion.
    for unidad in ("auto", "energy"):
        ingresos = df[f"revenue_{unidad}_segment"]
        margen = df[f"gross_profit_{unidad}_segment"]
        derivado = ingresos - margen
        df[f"cogs_{unidad}_segment"] = df[f"cogs_{unidad}_segment"].fillna(derivado)

    df.to_csv("data/financials_quarterly.csv", index=False)

    print(f"\nCobertura de los campos nuevos ({len(df)} trimestres):")
    for campo in sorted(series):
        print(f"  {campo}: {df[campo].notna().sum()}/{len(df)}")


if __name__ == "__main__":
    main()
