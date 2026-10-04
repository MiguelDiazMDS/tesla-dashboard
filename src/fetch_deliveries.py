"""Deliveries y produccion desde la nota de prensa trimestral de Tesla.

Tesla publica produccion y entregas unos dos dias despues de cerrar el
trimestre, tres semanas antes que los estados financieros. La nota va como
exhibit de un 8-K, asi que se lee de EDGAR y no de ir.tesla.com, que bloquea
el acceso automatizado.

El desglose por modelo no es homogeneo en el tiempo: hasta 2019 Tesla publicaba
"Model S/X" y "Model 3", y desde 2020 "Model 3/Y" y "Other Models", porque el
Model Y no existia antes. Se guarda la etiqueta literal de cada epoca y ademas
dos series comparables en todo el periodo: la linea de alto volumen y la de
nicho.

Este modulo no accede a la red: recibe el texto ya descargado.
"""
import io
import re

import pandas as pd

# Como se llamaba cada linea en cada epoca, normalizado a minusculas.
ETIQUETAS_VOLUMEN = ("model 3/y", "model 3")
ETIQUETAS_NICHO = ("other models", "model s/x")
ETIQUETAS_TOTAL = ("total",)

COLUMNAS_PRODUCCION = ("production",)
COLUMNAS_ENTREGAS = ("deliveries",)
# Columna informativa que aparece desde 2019 y no debe confundirse con las
# entregas totales.
COLUMNAS_IGNORADAS = ("subject to operating lease", "operating lease accounting")


class TablaDeliveriesNoEncontrada(Exception):
    """El exhibit no contiene una tabla de produccion y entregas reconocible."""


def _normalizar(texto) -> str:
    return " ".join(str(texto).lower().split())


# En una tabla financiera un guion solitario significa cero. Tesla lo usa, por
# ejemplo, para la produccion de Model S/X de 2021Q1, trimestre en que no
# fabrico ninguno mientras redisenaba esas lineas.
GUIONES_CERO = {"-", "–", "—"}


def _a_entero(bruto) -> int | None:
    texto = str(bruto).replace(",", "").replace("~", "").strip()
    if texto in GUIONES_CERO:
        return 0
    try:
        return int(float(texto))
    except ValueError:
        return None


def recortar_html(texto: str) -> str:
    """Extrae el HTML del envoltorio SGML con que EDGAR sirve los exhibits."""
    inicio = texto.find("<html")
    fin = texto.rfind("</html>")
    return texto[inicio:fin + 7] if inicio != -1 and fin != -1 else texto


def localizar_exhibit(submission_txt: str) -> str | None:
    """Nombre del fichero del exhibit 99.1 dentro de la submission completa."""
    patron = re.compile(
        r"<TYPE>EX-99\.1.*?<FILENAME>([^\s<]+)", re.S | re.I)
    encontrado = patron.search(submission_txt)
    return encontrado.group(1).strip() if encontrado else None


# Desde 2024 la nota da tambien el almacenamiento desplegado en el trimestre,
# tres semanas antes que el Update Letter: "deployed 13.7 GWh of energy
# storage products". Las notas antiguas lo daban en MWh o no lo daban.
PATRON_ALMACENAMIENTO = re.compile(
    r"deployed\s+([\d.,]+)\s*(GWh|MWh)\s+of\s+energy\s+storage", re.I)


def parsear_almacenamiento(html: str) -> float | None:
    """GWh de almacenamiento desplegado que cita la nota, o None si no lo cita."""
    texto = re.sub(r"<[^>]+>", " ", html)
    texto = texto.replace("&nbsp;", " ").replace("&#160;", " ")
    texto = " ".join(texto.split())
    encontrado = PATRON_ALMACENAMIENTO.search(texto)
    if not encontrado:
        return None
    try:
        valor = float(encontrado.group(1).replace(",", ""))
    except ValueError:
        return None
    return valor / 1000 if encontrado.group(2).lower() == "mwh" else valor


def parsear_deliveries(html: str) -> dict[str, int | str | float]:
    """Produccion, entregas y, si la nota lo trae, almacenamiento desplegado."""
    salida: dict[str, int | str | float] = dict(_parsear_vehiculos(html))
    almacenamiento = parsear_almacenamiento(html)
    if almacenamiento is not None:
        salida["storage_deployed_gwh"] = almacenamiento
    return salida


def _parsear_vehiculos(html: str) -> dict[str, int | str]:
    """Produccion y entregas por linea de modelos a partir del exhibit.

    Devuelve las series homogeneas (volumen y nicho), los totales y la etiqueta
    literal que uso Tesla en ese trimestre, para poder auditar contra el
    documento original.
    """
    try:
        # flavor lxml explicito: los exhibits antiguos no son HTML bien
        # formado y pandas recurriria a html5lib, que no es dependencia.
        tablas = pd.read_html(io.StringIO(recortar_html(html)), flavor="lxml")
    except ValueError:
        # Las notas mas antiguas no llevan tabla: dan las cifras en prosa.
        return parsear_deliveries_narrativo(html)

    for tabla in tablas:
        columnas = _clasificar_columnas(tabla)
        if not columnas:
            continue

        salida: dict[str, int | str] = {}
        for _, fila in tabla.iterrows():
            literal = str(fila.iloc[0]).strip()
            etiqueta = _normalizar(literal)
            if etiqueta in ETIQUETAS_VOLUMEN:
                clave = "volumen"
            elif etiqueta in ETIQUETAS_NICHO:
                clave = "nicho"
            elif etiqueta in ETIQUETAS_TOTAL:
                clave = "total"
            else:
                continue
            for tipo, posicion in columnas.items():
                valor = _a_entero(fila.iloc[posicion])
                if valor is not None:
                    salida[f"{tipo}_{clave}"] = valor
            if clave != "total":
                salida[f"etiqueta_{clave}"] = literal

        if "deliveries_total" in salida and "deliveries_volumen" in salida:
            return salida

    return parsear_deliveries_narrativo(html)


# Las notas mas antiguas no traen tabla: dan las cifras en prosa, con "Model 3"
# y "Model S and X" como lineas y la palabra "approximately" delante.
PATRON_PRODUCCION = re.compile(
    r"produced\s+(?:approximately\s+)?([\d,]+)\s+total vehicles,\s*consisting of\s+"
    r"(?:approximately\s+)?([\d,]+)\s+Model 3\s+and\s+(?:approximately\s+)?([\d,]+)\s+"
    r"Model S and X", re.I | re.S)
PATRON_ENTREGAS = re.compile(
    r"[Dd]eliveries were\s+(?:approximately\s+)?([\d,]+)\s+vehicles", re.I | re.S)
PATRON_ENTREGAS_DESGLOSE = re.compile(
    r"(?:approximately\s+)?([\d,]+)\s+Model 3\s+and\s+(?:approximately\s+)?([\d,]+)\s+"
    r"Model S and X", re.I | re.S)


def parsear_deliveries_narrativo(html: str) -> dict[str, int | str]:
    """Lee las cifras de las notas antiguas, que las dan en prosa.

    Las cifras van precedidas de "approximately", asi que son aproximadas por
    el propio emisor; asi las publico Tesla y asi se guardan.
    """
    texto = re.sub(r"<[^>]+>", " ", html)
    texto = texto.replace("&nbsp;", " ").replace("&#160;", " ")
    texto = " ".join(texto.split())

    produccion = PATRON_PRODUCCION.search(texto)
    entregas = PATRON_ENTREGAS.search(texto)
    if not produccion or not entregas:
        raise TablaDeliveriesNoEncontrada(
            "ni tabla reconocible ni cifras en prosa")

    salida: dict[str, int | str] = {
        "production_total": _a_entero(produccion.group(1)),
        "production_volumen": _a_entero(produccion.group(2)),
        "production_nicho": _a_entero(produccion.group(3)),
        "deliveries_total": _a_entero(entregas.group(1)),
        "etiqueta_volumen": "Model 3",
        "etiqueta_nicho": "Model S and X",
    }
    # El desglose de entregas viene en la frase siguiente a la del total.
    desglose = PATRON_ENTREGAS_DESGLOSE.search(texto, entregas.end())
    if desglose:
        salida["deliveries_volumen"] = _a_entero(desglose.group(1))
        salida["deliveries_nicho"] = _a_entero(desglose.group(2))
    return salida


def _clasificar_columnas(tabla) -> dict[str, int]:
    """Posicion de las columnas de produccion y de entregas.

    La tabla del exhibit no trae cabecera: los titulos son una fila mas, y las
    celdas aparecen repetidas por los colspan del documento original. Se busca
    esa fila y se toma la primera posicion de cada bloque.
    """
    for _, fila in tabla.iterrows():
        textos = [_normalizar(v) for v in fila]
        if not any(x in t for t in textos for x in COLUMNAS_PRODUCCION):
            continue
        columnas: dict[str, int] = {}
        for posicion, texto in enumerate(textos):
            if any(x in texto for x in COLUMNAS_IGNORADAS):
                continue
            if any(x in texto for x in COLUMNAS_PRODUCCION):
                columnas.setdefault("production", posicion)
            elif any(x in texto for x in COLUMNAS_ENTREGAS):
                columnas.setdefault("deliveries", posicion)
        if "deliveries" in columnas:
            return columnas
    return {}
