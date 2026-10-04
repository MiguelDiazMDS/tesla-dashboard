"""Genera dist/dashboard.html, la pagina que se publica como artifact.

Se niega a construir si la valoracion oficial no corresponde a los supuestos
actuales o al ultimo precio de mercado: la pagina nunca muestra cifras
desfasadas como si fueran las vigentes.

    python -m src.construir_dashboard
"""
import json
import re
import sys
from datetime import date
from pathlib import Path

import pandas as pd

from src import historico, hitos
from src.datos_dashboard import construir_datos
from src.schema import FINANCIALS, HISTORICO, MARKET, OPERATING
from src.supuestos import cargar_supuestos
from src.validate import ErrorValidacion, validar

WEB = Path("web")
SALIDA_HTML = Path("dist/dashboard.html")
SALIDA_JSON = Path("dist/datos_dashboard.json")
# Version completa para publicar en un servidor propio (el artifact de
# claude.ai anade por su cuenta doctype, head y viewport; un servidor no).
SALIDA_WEB = Path("dist/web/index.html")
INICIO_CUERPO = '<div class="pagina">'
CHARSET = '<meta charset="utf-8">'
VALORACION = Path("dist/valoracion.json")
MARCA_DATOS = "__DATOS__"
MARCA_CSS = "/*__ESTILOS__*/"
PIEZAS = {
    "/*__ESTILOS__*/": "estilos.css",
    "/*__MOTOR__*/": "motor.js",
    "/*__SIMULADOR__*/": "simulador.js",
    "/*__APP__*/": "app.js",
}


class ConstruccionRechazada(Exception):
    """La valoracion no esta al dia: hay que volver a valorar antes."""


def comprobar_vigencia(valoracion: dict, huella_supuestos: str,
                       ultimo_mes_mercado: str, ultimo_precio: float) -> None:
    if valoracion.get("huella") != huella_supuestos:
        raise ConstruccionRechazada(
            "La valoracion se calculo con otros supuestos: ejecuta "
            "python -m src.valorar antes de construir la pagina")
    if valoracion.get("mes_precio") != ultimo_mes_mercado:
        raise ConstruccionRechazada(
            f"La valoracion usa el precio de {valoracion.get('mes_precio')} y el ultimo "
            f"mes de mercado es {ultimo_mes_mercado}: ejecuta python -m src.valorar")
    # El CSV de mercado puede refrescarse dentro del mismo mes: el mes coincide
    # pero el precio no. Mismo origen, asi que la igualdad es exacta.
    precio = valoracion.get("precio")
    if precio is None or float(precio) != float(ultimo_precio):
        raise ConstruccionRechazada(
            f"La valoracion usa un precio de {precio} y el ultimo cierre del CSV de "
            f"mercado es {ultimo_precio}: ejecuta python -m src.valorar")


def leer_valoracion(ruta: Path = VALORACION) -> dict:
    if not ruta.exists():
        raise ConstruccionRechazada(
            f"No existe {ruta.as_posix()}: ejecuta python -m src.valorar antes de "
            "construir la pagina")
    return json.loads(ruta.read_text(encoding="utf-8"))


def leer_historico(ruta: Path = historico.RUTA) -> list[dict]:
    try:
        df = historico.leer(ruta)
    except pd.errors.EmptyDataError as error:
        raise ConstruccionRechazada(
            f"[historico_valoraciones] {Path(ruta).as_posix()} esta vacio: borralo o "
            "repara el fichero") from error
    # Se valida aunque no tenga filas: una cabecera con columnas obligatorias
    # ausentes no debe colarse como "sin historico todavia".
    try:
        validar(df, HISTORICO)
    except ErrorValidacion as error:
        raise ConstruccionRechazada(f"El historico no valida: {error}") from error
    if df.empty:
        return []
    return [{k: (None if pd.isna(v) else v) for k, v in fila.items()}
            for fila in df.to_dict(orient="records")]


def leer_hitos(financieros, operativos, hoy: date, ruta: Path = hitos.RUTA) -> dict | None:
    """Hitos ya calculados para la pagina; None si todavia no hay fichero."""
    if not Path(ruta).exists():
        return None
    try:
        datos = hitos.cargar(ruta)
    except hitos.HitosInvalidos as error:
        raise ConstruccionRechazada(f"{Path(ruta).as_posix()} no valida: {error}") from error
    return hitos.construir_hitos(datos, financieros, operativos, hoy)


def comprobar_esquemas(financieros, operativos, mercado) -> None:
    try:
        validar(financieros, FINANCIALS)
        validar(operativos, OPERATING)
        validar(mercado, MARKET)
    except ErrorValidacion as error:
        raise ConstruccionRechazada(
            f"Los datos no validan: {error}. Ejecuta python -m src.cargar_todo") from error


def json_incrustable(datos: dict) -> str:
    """JSON que se puede meter en un <script> sin que lo cierre antes de tiempo.

    Todo '<' pasa a su escape \\u003c: cubre '</script' y tambien '<!--', que
    dentro de un <script> cambia como analiza el navegador el resto del bloque.
    """
    texto = json.dumps(datos, ensure_ascii=False, allow_nan=False)
    return texto.replace("<", "\\u003c")


def comprobar_pieza(marca: str, contenido: str, marcas: list[str]) -> None:
    """Rechaza lo que romperia la pagina o el propio ensamblado."""
    if re.search(r"</script", contenido, re.I):
        raise ValueError(f"la pieza de {marca} contiene '</script' y romperia la pagina")
    if marca == MARCA_CSS:
        if re.search(r"</style", contenido, re.I):
            raise ValueError(f"la pieza de {marca} contiene '</style' y romperia la pagina")
    elif "<!--" in contenido:
        raise ValueError(f"la pieza de {marca} contiene '<!--', que altera como se "
                         "analiza un <script>")
    for otra in marcas:
        if otra in contenido:
            raise ValueError(f"la pieza de {marca} contiene la marca {otra}")


def ensamblar(plantilla: str, piezas: dict[str, str], datos_json: str) -> str:
    marcas = [*piezas, MARCA_DATOS]
    for marca, contenido in piezas.items():
        comprobar_pieza(marca, contenido, marcas)
    html = plantilla
    for marca, contenido in piezas.items():
        if html.count(marca) != 1:
            raise ValueError(f"la plantilla debe contener {marca} exactamente una vez")
        html = html.replace(marca, contenido)
    if html.count(MARCA_DATOS) != 1:
        raise ValueError(f"la plantilla debe contener {MARCA_DATOS} exactamente una vez")
    return html.replace(MARCA_DATOS, datos_json)


def documento_completo(fragmento: str) -> str:
    """El fragmento del artifact convertido en un documento HTML completo.

    Lo anterior al contenedor de la pagina (titulo, fuentes y estilos) va al
    head; el resto, al body. Sin indexar: es un analisis personal.
    """
    corte = fragmento.find(INICIO_CUERPO)
    if corte < 0:
        raise ValueError(f"el fragmento no contiene el inicio de la pagina ({INICIO_CUERPO})")
    cabecera = fragmento[:corte].replace(CHARSET, "").strip()
    cuerpo = fragmento[corte:].strip()
    return ("<!doctype html>\n<html lang=\"es\">\n<head>\n"
            f"{CHARSET}\n"
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            '<meta name="robots" content="noindex, nofollow">\n'
            f"{cabecera}\n</head>\n<body>\n{cuerpo}\n</body>\n</html>\n")


def construir() -> str:
    financieros = pd.read_csv("data/financials_quarterly.csv")
    operativos = pd.read_csv("data/operating_quarterly.csv")
    mercado = pd.read_csv("data/market_monthly.csv")
    # Validar antes de ordenar: sin 'month', sort_values daria un KeyError opaco.
    comprobar_esquemas(financieros, operativos, mercado)
    mercado = mercado.sort_values("month")
    supuestos, huella = cargar_supuestos("data/assumptions.yaml")
    valoracion = leer_valoracion()
    comprobar_vigencia(valoracion, huella, mercado["month"].iloc[-1],
                       float(mercado["price_close"].iloc[-1]))

    datos = construir_datos(financieros, operativos, mercado, valoracion, supuestos,
                            date.today().isoformat(), historico=leer_historico(),
                            hitos=leer_hitos(financieros, operativos, date.today()))
    texto_json = json.dumps(datos, ensure_ascii=False, indent=1, allow_nan=False)
    piezas = {marca: (WEB / fichero).read_text(encoding="utf-8")
              for marca, fichero in PIEZAS.items()}
    html = ensamblar((WEB / "plantilla.html").read_text(encoding="utf-8"), piezas,
                     json_incrustable(datos))
    # Solo se escribe cuando todo ha salido bien: nunca queda una pareja a medias.
    web = documento_completo(html)
    SALIDA_WEB.parent.mkdir(parents=True, exist_ok=True)
    SALIDA_JSON.write_text(texto_json, encoding="utf-8")
    SALIDA_HTML.write_text(html, encoding="utf-8")
    SALIDA_WEB.write_text(web, encoding="utf-8")
    return (f"{SALIDA_HTML} ({len(html.encode('utf-8')) / 1024:,.0f} KB) y "
            f"{SALIDA_WEB} para servidor propio")


def main() -> None:
    try:
        print(construir())
    except ConstruccionRechazada as error:
        sys.exit(str(error))


if __name__ == "__main__":
    main()
