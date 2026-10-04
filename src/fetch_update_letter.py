"""Metricas operativas del Update Letter trimestral de Tesla.

El Update Letter se presenta como exhibit 99.1 del 8-K de resultados, unas tres
semanas despues del cierre del trimestre. Desde mediados de 2023 el exhibit
lleva el texto; en buena parte de los anos anteriores las paginas son imagenes
y hay que recurrir al PDF, que se trata en otro modulo.

El cuadro "Operational Summary" no es una tabla HTML sino texto posicionado,
asi que se lee del texto plano: una cabecera con cinco trimestres ("Q2-2025 ...
Q2-2026") y, para cada metrica, su etiqueta seguida de cinco valores y la
variacion interanual. Cada carta cubre por tanto cinco trimestres.

Este modulo no accede a la red: recibe el texto ya descargado.
"""
import re

# Etiqueta de cada metrica, como expresion regular. Las notas al pie ("(4)") y
# la unidad ("(GWh)", "(mil)") que siguen a la etiqueta se saltan despues.
METRICAS = {
    "days_inventory": r"Global vehicle inventory \(days of supply\)",
    "storage_deployed": r"Storage deployed",
    "fsd_subscriptions": r"Active FSD Subscriptions",
}

# Tesla reportaba el almacenamiento en MWh hasta 2024 y en GWh despues. Un
# extractor que asumiera la unidad fija introduciria un error de factor mil.
FACTOR_A_GWH = {"gwh": 1.0, "mwh": 0.001}
# Las suscripciones FSD se publican en millones ("(mil)").
FACTOR_SUSCRIPCIONES = {"mil": 1_000_000}

PATRON_TRIMESTRE = re.compile(r"Q([1-4])-(\d{4})")
PATRON_NUMERO = re.compile(r"-?\d[\d,]*\.?\d*")


class CuadroNoEncontrado(Exception):
    """El documento no contiene el cuadro de metricas operativas."""


def texto_plano(html: str) -> str:
    """Quita etiquetas y entidades y deja un solo espacio entre palabras."""
    texto = re.sub(r"<[^>]+>", " ", html)
    for entidad, sustituto in (
        ("&#160;", " "), ("&nbsp;", " "), ("&amp;", "&"),
        ("&#8211;", "-"), ("&#8212;", "-"), ("&#8217;", "'"),
    ):
        texto = texto.replace(entidad, sustituto)
    return " ".join(texto.split())


def cabecera_trimestres(texto: str, antes_de: int) -> list[str]:
    """Los cinco trimestres de la cabecera que precede a una posicion.

    Se toma el ultimo bloque de cinco trimestres consecutivos anterior a la
    primera metrica: es la cabecera de las columnas del cuadro.
    """
    encontrados = [
        (m.start(), f"{m.group(2)}Q{m.group(1)}")
        for m in PATRON_TRIMESTRE.finditer(texto, 0, antes_de)
    ]
    for i in range(len(encontrados) - 5, -1, -1):
        bloque = [p for _, p in encontrados[i:i + 5]]
        if len(bloque) == 5 and _consecutivos(bloque):
            return bloque
    return []


def _consecutivos(periodos: list[str]) -> bool:
    indices = [int(p[:4]) * 4 + int(p[5]) for p in periodos]
    return all(b - a == 1 for a, b in zip(indices, indices[1:]))


def _valores_de(texto: str, etiqueta: str) -> tuple[list[float], str | None] | None:
    """Los cinco valores que siguen a una etiqueta, y su unidad si la declara."""
    encontrado = re.search(etiqueta, texto)
    if not encontrado:
        return None
    resto = texto[encontrado.end():]
    unidad = None
    # Saltar notas al pie "(4)" y unidades "(GWh)" pegadas a la etiqueta.
    while True:
        parentesis = re.match(r"\s*\(([^)]*)\)", resto)
        if not parentesis:
            break
        contenido = parentesis.group(1).strip()
        if not contenido.isdigit():
            unidad = contenido.lower()
        resto = resto[parentesis.end():]
    numeros = PATRON_NUMERO.findall(resto[:160])[:5]
    if len(numeros) < 5:
        return None
    return [float(n.replace(",", "")) for n in numeros], unidad


def parsear_cuadro(html: str) -> dict[str, dict[str, float]]:
    """{periodo: {campo: valor}} para los cinco trimestres del cuadro.

    Normaliza el almacenamiento a GWh y las suscripciones a unidades, leyendo la
    unidad de la propia etiqueta de cada carta.
    """
    texto = texto_plano(html)
    posiciones = [
        m.start() for patron in METRICAS.values()
        if (m := re.search(patron, texto))
    ]
    if not posiciones:
        raise CuadroNoEncontrado("ninguna metrica operativa en el texto")

    periodos = cabecera_trimestres(texto, min(posiciones))
    if not periodos:
        raise CuadroNoEncontrado("no se localiza la cabecera de cinco trimestres")

    salida: dict[str, dict[str, float]] = {p: {} for p in periodos}
    for campo, patron in METRICAS.items():
        leido = _valores_de(texto, patron)
        if leido is None:
            continue
        valores, unidad = leido
        if campo == "storage_deployed":
            factor = FACTOR_A_GWH.get(unidad or "")
            if factor is None:
                raise CuadroNoEncontrado(
                    f"unidad de almacenamiento desconocida: {unidad!r}")
            campo, valores = "storage_deployed_gwh", [v * factor for v in valores]
        elif campo == "fsd_subscriptions":
            factor = FACTOR_SUSCRIPCIONES.get(unidad or "", 1)
            valores = [v * factor for v in valores]
        for periodo, valor in zip(periodos, valores):
            salida[periodo][campo] = valor
    return salida
