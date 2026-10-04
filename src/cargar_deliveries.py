"""Genera data/operating_quarterly.csv con deliveries y produccion.

Tesla publica la nota de produccion y entregas como exhibit de un 8-K en los
primeros dias del mes siguiente al cierre del trimestre. Se identifica por esa
ventana de fechas, porque el 8-K de resultados llega tres semanas despues.
"""
from datetime import date

import pandas as pd

from src.fetch_deliveries import (
    TablaDeliveriesNoEncontrada, localizar_exhibit, parsear_deliveries,
)
from src.filings import BASE_ARCHIVO, indice_filings
from src.http_client import ClienteHTTP, ErrorDescarga
from src.schema import OPERATING
from src.validate import ErrorValidacion, validar, validar_continuidad

DESDE = "2019Q1"

# Mes de publicacion -> trimestre que reporta y cuantos anios atras queda.
MES_A_TRIMESTRE = {1: (4, 1), 4: (1, 0), 7: (2, 0), 10: (3, 0)}
DIA_LIMITE = 12          # despues de esa fecha el 8-K ya es el de resultados


def periodo_reportado(fecha_filing: str) -> str | None:
    """Trimestre al que se refiere una nota publicada en esa fecha."""
    f = date.fromisoformat(fecha_filing)
    if f.day > DIA_LIMITE or f.month not in MES_A_TRIMESTRE:
        return None
    trimestre, atras = MES_A_TRIMESTRE[f.month]
    return f"{f.year - atras}Q{trimestre}"


def listar_notas(cliente: ClienteHTTP) -> list[tuple[str, list[str]]]:
    """(periodo, candidatos) de las notas de deliveries.

    Devuelve TODOS los 8-K presentados en la ventana de cada trimestre, no solo
    el primero: Tesla presenta otros 8-K en esas mismas fechas (cambios
    estatutarios, hechos societarios) y solo uno lleva la nota de produccion y
    entregas. Quien llame prueba los candidatos hasta dar con el bueno.
    """
    indice = indice_filings(cliente)
    notas: dict[str, list[str]] = {}
    for i, formulario in enumerate(indice["form"]):
        if formulario != "8-K":
            continue
        periodo = periodo_reportado(indice["filingDate"][i])
        if periodo and periodo >= DESDE:
            notas.setdefault(periodo, []).append(indice["accessionNumber"][i])
    return sorted(notas.items())


def leer_nota(cliente: ClienteHTTP, accession: str) -> dict:
    """Produccion y entregas de una nota, o un diccionario vacio si falla."""
    base = f"{BASE_ARCHIVO}/{accession.replace('-', '')}"
    try:
        completo = cliente.obtener(f"{base}/{accession}.txt").decode(
            "utf-8", errors="replace")
    except ErrorDescarga:
        raise             # agotar los reintentos es "no se sabe", no "descartado"
    except Exception as exc:
        return {}          # candidato descartado
    fichero = localizar_exhibit(completo)
    if not fichero:
        return {}          # otro 8-K de la misma ventana, no la nota
    try:
        html = cliente.obtener(f"{base}/{fichero}").decode("utf-8", errors="replace")
        return parsear_deliveries(html)
    except TablaDeliveriesNoEncontrada as exc:
        print(f"    {exc}")
    except ErrorDescarga:
        raise
    except Exception as exc:
        print(f"    fallo al parsear {fichero}: {type(exc).__name__}: {exc}")
    return {}


def main() -> None:
    cliente = ClienteHTTP()
    notas = listar_notas(cliente)
    print(f"{len(notas)} notas de deliveries desde {DESDE}\n")

    hoy = date.today().isoformat()
    filas = []
    for periodo, candidatos in notas:
        datos, accession = {}, None
        for candidato in candidatos:
            datos = leer_nota(cliente, candidato)
            if datos:
                accession = candidato
                break
        if not datos:
            print(f"{periodo}: sin datos en {len(candidatos)} candidato(s)")
            continue
        filas.append({
            "period": periodo,
            "source": f"SEC 8-K {accession} (exhibit 99.1)",
            "retrieved_at": hoy,
            **datos,
        })
        print(f"{periodo}: {datos.get('deliveries_total', 0):>9,} entregas, "
              f"{datos.get('production_total', 0):>9,} producidos "
              f"({datos.get('etiqueta_volumen', '?')} / "
              f"{datos.get('etiqueta_nicho', '?')})")

    df = pd.DataFrame(filas).sort_values("period").reset_index(drop=True)
    df.to_csv("data/operating_quarterly.csv", index=False)

    print(f"\n{len(df)} trimestres escritos")
    print("Cobertura por campo:")
    for columna in df.columns:
        print(f"  {columna}: {df[columna].notna().sum()}/{len(df)}")

    try:
        validar_continuidad(df["period"].tolist(), DESDE, df["period"].max())
        print("\nSerie trimestral sin huecos")
    except ErrorValidacion as exc:
        print(f"\n{exc}")
    try:
        validar(df, OPERATING)
        print("Validacion de esquema: OK")
    except ErrorValidacion as exc:
        print(f"Validacion de esquema pendiente: {exc}")
        print("Los campos del Update Letter se cargan aparte.")


if __name__ == "__main__":
    main()
