"""Segmentos, lineas de producto e ingresos por geografia desde los filings.

Estos datos NO estan en la API companyfacts: solo sirve las taxonomias dei,
us-gaap y ffd, y las lineas de negocio de Tesla viven en su taxonomia propia.
Hay que leerlos de los estados renderizados que la SEC genera para cada filing.

El numero del fichero R*.htm cambia de un filing a otro, asi que nunca se
accede por posicion: se resuelve por nombre desde el FilingSummary.xml, que
lista los ~67 informes de cada filing. Son tres peticiones por filing en vez
de recorrer los sesenta y seis a ciegas.

Este modulo no accede a la red: recibe el texto ya descargado.
"""
import io
import re

import pandas as pd

MESES = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}
TRIMESTRE_POR_MES_FINAL = {3: 1, 6: 2, 9: 3, 12: 4}

# Fragmentos por los que localizar cada informe en el FilingSummary.xml.
# Son deliberadamente cortos porque Tesla ha ido cambiando los titulos: en 2019
# el de segmentos se llamaba "Total Revenues and Gross Margin by Reportable
# Segment" y despues paso a "... Gross Profit ...", y el sufijo alterna entre
# "(Detail)" y "(Details)".
INFORME_SEGMENTOS = "Total Revenues and Gross"
INFORME_LINEAS = "Disaggregation of Revenue by Major Source"
INFORME_GEOGRAFIA = "Schedule of Revenues by Geographic Area"

# Un informe "(Parenthetical)" acompana a algunas tablas con notas al pie y no
# contiene las cifras: hay que saltarlo.
EXCLUIR_DEL_NOMBRE = ("parenthetical",)

# Los nombres de seccion cambian entre epocas: los filings antiguos llevan el
# sufijo "[Member]" y a veces un prefijo jerarquico separado por "|". Todas las
# claves de los mapas de abajo estan ya normalizadas con normalizar_seccion().
SECCIONES_SEGMENTO = {
    "automotive segment": "auto_segment",
    "automotive": "auto_segment",
    "energy generation and storage": "energy_segment",
    "energy generation and storage segment": "energy_segment",
}
METRICAS_SEGMENTO = {
    "Revenues": "revenue",
    "Total revenues": "revenue",       # como se llama la fila hasta 2025
    "Cost of revenues": "cogs",
    "Gross profit": "gross_profit",
    "Gross margin": "gross_profit",    # como se llamaba la fila hasta 2021
}

# Las tablas declaran su escala en el encabezado y esta ha cambiado: los
# filings de 2019 vienen en miles y los posteriores en millones. Leerla del
# encabezado evita un error de factor mil en el historico antiguo.
ESCALAS = (
    ("in thousands", 1_000),
    ("in millions", 1_000_000),
    ("in billions", 1_000_000_000),
)

# Lineas de producto. Las de automocion suman el segmento de automocion y las
# de energia el suyo; "Services and other" es una linea de automocion, no un
# segmento propio.
#
# Hasta 2021 Tesla partia las ventas de vehiculos en dos lineas segun llevaran
# o no garantia de valor residual: ambas se suman en la misma serie para que el
# historico sea homogeneo.
SECCIONES_LINEA = {
    "automotive sales": "revenue_auto_sales",
    "automotive sales without resale value guarantee": "revenue_auto_sales",
    "automotive sales with resale value guarantee": "revenue_auto_sales",
    "automotive regulatory credits": "revenue_reg_credits",
    "automotive leasing": "revenue_auto_leasing",
    "services and other": "revenue_services",
    "energy generation and storage sales": "revenue_energy_sales",
    "energy generation and storage leasing": "revenue_energy_leasing",
}

# Solo se nombran las dos regiones que Tesla ha desglosado siempre. Todo lo
# demas se agrega en "resto": en 2019 publicaba ademas Noruega y Paises Bajos
# por separado, y agregarlos mantiene la serie comparable en todo el periodo.
SECCIONES_GEOGRAFIA = {
    "united states": "revenue_us",
    "china": "revenue_china",
}
CAMPO_RESTO_DEL_MUNDO = "revenue_other"

# Subtotales que aparecen como seccion pero no son una linea de negocio.
SECCIONES_IGNORADAS = {"sales and services", "total revenues from sales and services"}

# Margen para que una seccion repetida se considere "el mismo importe" pese al
# redondeo de las tablas.
TOLERANCIA_SECCION_REPETIDA = 0.005


class SeccionContradictoria(Exception):
    """La misma seccion aparece dos veces en el filing con importes distintos."""


def normalizar_seccion(texto: str) -> str:
    """Deja el nombre de una seccion comparable entre epocas.

    Quita el sufijo "[Member]" de los filings antiguos, se queda con el nivel
    mas especifico cuando viene una jerarquia separada por "|", y normaliza
    mayusculas y espacios.
    """
    limpio = texto.replace("[Member]", " ")
    if "|" in limpio:
        limpio = limpio.split("|")[-1]
    return " ".join(limpio.lower().split())


class InformeNoEncontrado(Exception):
    """El FilingSummary no lista ningun informe con ese nombre."""


def resolver_informe(summary_xml: str, nombre: str) -> str:
    """Nombre del fichero R*.htm del informe, buscado por su ShortName.

    La comparacion ignora mayusculas y acepta coincidencia parcial, porque el
    nombre completo lleva prefijos que varian entre filings.
    """
    buscado = nombre.lower()
    for bloque in re.findall(r"<Report[^>]*>.*?</Report>", summary_xml, re.S):
        corto = re.search(r"<ShortName>(.*?)</ShortName>", bloque, re.S)
        fichero = re.search(r"<HtmlFileName>(.*?)</HtmlFileName>", bloque, re.S)
        if not corto or not fichero:
            continue
        titulo = corto.group(1).lower()
        if buscado in titulo and not any(x in titulo for x in EXCLUIR_DEL_NOMBRE):
            return fichero.group(1).strip()
    raise InformeNoEncontrado(f"El FilingSummary no lista '{nombre}'")


def recortar_html(texto: str) -> str:
    """Extrae el documento HTML del envoltorio SGML que sirve EDGAR.

    Los R*.htm vienen dentro de <DOCUMENT><TYPE>XML...<TEXT><html>...</html>,
    y ese envoltorio rompe el parser de pandas.
    """
    inicio = texto.find("<html")
    fin = texto.rfind("</html>")
    return texto[inicio:fin + 7] if inicio != -1 and fin != -1 else texto


def periodo_de_columna(duracion: str, fecha: str) -> tuple[int, str] | None:
    """Convierte la cabecera de una columna en (meses, periodo).

    "3 Months Ended" y "Jun. 30, 2026" dan (3, "2026Q2"). Devuelve None si la
    columna no corresponde a un cierre trimestral.
    """
    meses = re.search(r"(\d+)\s+Months?\s+Ended", duracion or "")
    partes = re.search(r"([A-Z][a-z]{2})\.?\s+\d{1,2},\s*(\d{4})", fecha or "")
    if not meses or not partes:
        return None
    mes = MESES.get(partes.group(1))
    trimestre = TRIMESTRE_POR_MES_FINAL.get(mes)
    if trimestre is None:
        return None
    return int(meses.group(1)), f"{partes.group(2)}Q{trimestre}"


def escala_de_tabla(tabla) -> int:
    """Factor por el que multiplicar las cifras, leido del encabezado.

    Las tablas declaran "$ in Thousands" o "$ in Millions" en la cabecera de su
    primera columna, y Tesla cambio de miles a millones a partir de 2020. Si no
    se declara ninguna escala, las cifras ya estan en dolares.
    """
    columna = tabla.columns[0]
    encabezado = " ".join(str(x) for x in columna) if isinstance(columna, tuple) else str(columna)
    encabezado = encabezado.lower()
    for texto, factor in ESCALAS:
        if texto in encabezado:
            return factor
    return 1


def parsear_tabla(html: str) -> dict[tuple[int, str], dict[str, dict[str, float]]]:
    """Lee una tabla jerarquica de los estados renderizados.

    Devuelve {(meses, periodo): {seccion: {metrica: valor en dolares}}}. Una
    fila sin ningun valor abre una seccion y las siguientes le pertenecen; las
    filas previas a cualquier seccion son el consolidado, bajo la clave "".

    Las tablas vienen en millones, asi que se multiplica para dejarlo en
    dolares, como el resto del esquema.
    """
    tablas = pd.read_html(io.StringIO(recortar_html(html)))
    if not tablas:
        return {}
    tabla = tablas[0]
    escala = escala_de_tabla(tabla)

    columnas: dict[int, tuple[int, str]] = {}
    for posicion, columna in enumerate(tabla.columns):
        if posicion == 0:
            continue
        duracion = str(columna[0]) if isinstance(columna, tuple) else ""
        fecha = str(columna[1]) if isinstance(columna, tuple) and len(columna) > 1 else ""
        clave = periodo_de_columna(duracion, fecha)
        if clave:
            columnas[posicion] = clave

    datos: dict[tuple[int, str], dict[str, dict[str, float]]] = {
        clave: {} for clave in columnas.values()
    }
    seccion = ""
    for _, fila in tabla.iterrows():
        etiqueta = str(fila.iloc[0]).strip()
        if "[Line Items]" in etiqueta or etiqueta.lower() == "nan":
            continue
        valores = {
            posicion: fila.iloc[posicion] for posicion in columnas
        }
        if all(pd.isna(v) for v in valores.values()):
            seccion = etiqueta          # fila de cabecera: abre una seccion
            continue
        for posicion, bruto in valores.items():
            if pd.isna(bruto):
                continue
            numero = _a_numero(bruto)
            if numero is None:
                continue
            clave = columnas[posicion]
            datos[clave].setdefault(seccion, {})[etiqueta] = numero * escala
    return datos


def _a_numero(bruto) -> float | None:
    """Convierte "$ 28,236" o "(1,234)" en float. None si no es una cifra."""
    texto = str(bruto).strip().replace("$", "").replace(",", "").strip()
    negativo = texto.startswith("(") and texto.endswith(")")
    if negativo:
        texto = texto[1:-1]
    try:
        valor = float(texto)
    except ValueError:
        return None
    return -valor if negativo else valor


def corregir_intercambio(salida: dict[str, float], periodo: str) -> dict[str, float]:
    """Deshace el cruce de ingresos entre segmentos de algunos filings.

    El estado renderizado del 10-Q de 2023Q1 asigna a automocion los ingresos de
    energia y viceversa, mientras que los margenes brutos si van en su sitio;
    es un defecto del renderizado de la SEC, no de los datos publicados por
    Tesla, y las lineas de producto del mismo filing confirman cual es el bueno.

    Se detecta con una regla de dominio comprobable: en todo el periodo cubierto
    el segmento de automocion supera con mucho al de energia, que nunca ha
    llegado al 15% de los ingresos. Si aparece al reves, estan cruzados.
    """
    auto = salida.get("revenue_auto_segment")
    energia = salida.get("revenue_energy_segment")
    if auto is None or energia is None or auto >= energia:
        return salida
    print(f"  {periodo}: ingresos de segmento cruzados en el filing "
          f"(automocion {auto:,.0f} < energia {energia:,.0f}); se corrige")
    salida["revenue_auto_segment"], salida["revenue_energy_segment"] = energia, auto
    for sufijo in ("cogs", "gross_profit"):
        a = salida.get(f"{sufijo}_auto_segment")
        e = salida.get(f"{sufijo}_energy_segment")
        # El margen bruto si viene bien asignado: solo se cruza si tambien
        # contradice la misma regla de dominio.
        if a is not None and e is not None and a < e:
            salida[f"{sufijo}_auto_segment"], salida[f"{sufijo}_energy_segment"] = e, a
    return salida


def extraer_segmentos(datos, meses: int, periodo: str) -> dict[str, float]:
    """Los seis campos de los dos segmentos reportables, para un periodo."""
    bloque = datos.get((meses, periodo), {})
    salida: dict[str, float] = {}
    for seccion, metricas in bloque.items():
        prefijo = SECCIONES_SEGMENTO.get(normalizar_seccion(seccion))
        if not prefijo:
            continue
        for metrica, sufijo in METRICAS_SEGMENTO.items():
            if metrica in metricas:
                salida[f"{sufijo}_{prefijo}"] = metricas[metrica]
    return corregir_intercambio(salida, periodo)


def _importe(metricas: dict[str, float]) -> float | None:
    """El importe de ingresos de una seccion, se llame como se llame la fila."""
    for nombre in ("Total revenues", "Revenues", "Total revenue",
                   "Total revenues from sales and services"):
        if nombre in metricas:
            return metricas[nombre]
    return None


def _repetida_o_registrada(vistas: dict[str, float], clave: str, valor: float,
                            periodo: str) -> bool:
    """True si la seccion ya se habia visto con el mismo importe (se ignora).

    Si reaparece con un importe distinto (mas de un 0,5% relativo), no se
    puede saber cual de las dos es la buena: se lanza en vez de elegir una al
    azar en silencio.
    """
    anterior = vistas.get(clave)
    if anterior is None:
        vistas[clave] = valor
        return False
    referencia = max(abs(anterior), abs(valor), 1.0)
    if abs(anterior - valor) > TOLERANCIA_SECCION_REPETIDA * referencia:
        raise SeccionContradictoria(
            f"{periodo}: la seccion '{clave}' aparece dos veces con importes "
            f"distintos: {anterior:,.0f} y {valor:,.0f}"
        )
    return True


def extraer_lineas_producto(datos, meses: int, periodo: str) -> dict[str, float]:
    """Las lineas de producto, sumando las que comparten serie."""
    bloque = datos.get((meses, periodo), {})
    salida: dict[str, float] = {}
    vistas: dict[str, float] = {}
    for seccion, metricas in bloque.items():
        clave = normalizar_seccion(seccion)
        campo = SECCIONES_LINEA.get(clave)
        if not campo or clave in SECCIONES_IGNORADAS:
            continue
        valor = _importe(metricas)
        if valor is None:
            continue
        # Secciones distintas pueden alimentar la misma serie (ventas con y
        # sin garantia de valor residual) y se suman. La misma seccion
        # repetida en otro nivel de la jerarquia no: en el 10-K de 2019 los
        # creditos regulatorios aparecen dos veces con el mismo importe.
        if _repetida_o_registrada(vistas, clave, valor, periodo):
            continue
        salida[campo] = salida.get(campo, 0.0) + valor
    return salida


def extraer_geografia(datos, meses: int, periodo: str) -> dict[str, float]:
    """Ingresos por region, agregando en "resto" todo lo que no sea EEUU o China."""
    bloque = datos.get((meses, periodo), {})
    salida: dict[str, float] = {}
    vistas: dict[str, float] = {}
    for seccion, metricas in bloque.items():
        clave = normalizar_seccion(seccion)
        if not clave or clave in SECCIONES_IGNORADAS:
            continue          # el consolidado no es una region
        valor = _importe(metricas)
        if valor is None:
            continue
        if _repetida_o_registrada(vistas, clave, valor, periodo):
            continue
        campo = SECCIONES_GEOGRAFIA.get(clave, CAMPO_RESTO_DEL_MUNDO)
        salida[campo] = salida.get(campo, 0.0) + valor
    return salida
