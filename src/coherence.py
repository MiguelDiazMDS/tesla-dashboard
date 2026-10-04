"""Comprobaciones cruzadas entre campos y entre ficheros de datos.

Son las identidades contables que deben cumplirse siempre. Detectan errores de
mapeo de conceptos, de escala y de transcripcion manual, que es justo la clase
de fallo que no produce ninguna excepcion y llegaria hasta el cuadro de mando
con aspecto de cifra normal.

Una fila con algun dato ausente se omite: un trimestre todavia sin cargar no es
una incoherencia. Lo que nunca se hace es relajar la tolerancia para que algo
cuadre.
"""
import pandas as pd

SEGMENTOS = ["revenue_auto_segment", "revenue_energy_segment"]
MARGEN_SEGMENTOS = ["gross_profit_auto_segment", "gross_profit_energy_segment"]
LINEAS_AUTOMOCION = [
    "revenue_auto_sales", "revenue_reg_credits",
    "revenue_auto_leasing", "revenue_services",
]
LINEAS_ENERGIA = ["revenue_energy_sales", "revenue_energy_leasing"]
REGIONES = ["revenue_us", "revenue_china", "revenue_other"]


class IncoherenciaDatos(Exception):
    """Los datos se contradicen entre si."""


def _comprobar_suma(
    df: pd.DataFrame, partes: list[str], total: str, etiqueta: str,
    tolerancia: float = 0.005,
) -> int:
    """Las columnas de `partes` deben sumar la columna `total`.

    Devuelve cuantas filas se han podido comprobar.
    """
    faltan = [c for c in [*partes, total] if c not in df.columns]
    if faltan:
        raise IncoherenciaDatos(f"{etiqueta}: faltan columnas {faltan}")

    comprobadas = 0
    for _, fila in df.iterrows():
        valores = [fila[c] for c in partes]
        suma_total = fila[total]
        if any(pd.isna(v) for v in valores) or pd.isna(suma_total) or not suma_total:
            continue
        suma = sum(valores)
        if abs(suma - suma_total) / abs(suma_total) > tolerancia:
            raise IncoherenciaDatos(
                f"{fila['period']}: {etiqueta} suman {suma:,.0f} "
                f"pero {total} es {suma_total:,.0f}"
            )
        comprobadas += 1
    return comprobadas


def comprobar_segmentos(df: pd.DataFrame) -> int:
    """Automocion mas energia deben sumar el ingreso consolidado.

    Tesla declara solo estos dos segmentos bajo ASC 280.
    """
    return _comprobar_suma(df, SEGMENTOS, "revenue_total", "los dos segmentos")


def comprobar_margen_segmentos(df: pd.DataFrame) -> int:
    """El margen bruto de los dos segmentos debe sumar el consolidado."""
    return _comprobar_suma(
        df, MARGEN_SEGMENTOS, "gross_profit_total", "el margen de los segmentos")


def comprobar_lineas_automocion(df: pd.DataFrame) -> int:
    """Las cuatro lineas de producto deben sumar el segmento de automocion.

    Incluye "Services and other", que es una linea de este segmento y no un
    segmento propio.
    """
    return _comprobar_suma(
        df, LINEAS_AUTOMOCION, "revenue_auto_segment",
        "las lineas de producto de automocion")


def comprobar_lineas_energia(df: pd.DataFrame) -> int:
    """Venta y arrendamiento deben sumar el segmento de energia."""
    return _comprobar_suma(
        df, LINEAS_ENERGIA, "revenue_energy_segment", "las lineas de energia")


def comprobar_geografia(df: pd.DataFrame) -> int:
    """Las tres regiones deben sumar el ingreso consolidado."""
    return _comprobar_suma(df, REGIONES, "revenue_total", "las regiones")


def comprobar_margen_por_segmento(df: pd.DataFrame) -> int:
    """Ingresos menos coste debe dar el margen bruto, en cada segmento."""
    comprobadas = 0
    for unidad in ("auto", "energy"):
        comprobadas += _comprobar_suma(
            df, [f"cogs_{unidad}_segment", f"gross_profit_{unidad}_segment"],
            f"revenue_{unidad}_segment", f"coste y margen de {unidad}")
    return comprobadas


def comprobar_deliveries(df: pd.DataFrame, tolerancia: int = 100) -> int:
    """Las lineas de volumen y de nicho deben sumar el total de entregas."""
    comprobadas = 0
    for _, fila in df.iterrows():
        partes = [fila.get("deliveries_volumen"), fila.get("deliveries_nicho")]
        total = fila.get("deliveries_total")
        if any(pd.isna(p) for p in partes) or pd.isna(total):
            continue
        if abs(sum(partes) - total) > tolerancia:
            raise IncoherenciaDatos(
                f"{fila['period']}: los grupos suman {sum(partes):,.0f} "
                f"pero el total reportado es {total:,.0f}"
            )
        comprobadas += 1
    return comprobadas


COMPROBACIONES_FINANCIERAS = (
    ("los dos segmentos suman el consolidado", comprobar_segmentos),
    ("el margen de los segmentos suma el consolidado", comprobar_margen_segmentos),
    ("las lineas de automocion suman su segmento", comprobar_lineas_automocion),
    ("las lineas de energia suman su segmento", comprobar_lineas_energia),
    ("las regiones suman el consolidado", comprobar_geografia),
    ("ingresos menos coste da el margen, por segmento", comprobar_margen_por_segmento),
)


def revisar_financieros(df: pd.DataFrame) -> dict[str, int]:
    """Ejecuta todas las comprobaciones y devuelve cuantas filas valido cada una."""
    return {nombre: comprobar(df) for nombre, comprobar in COMPROBACIONES_FINANCIERAS}
