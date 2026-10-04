"""Supuestos de valoracion: carga, validacion y disciplina de congelacion.

Los supuestos se revisan una vez por trimestre. Cambiarlos exige cambiar su
`version`, de modo que siempre quede rastro fechado de que se toco y cuando.
"""
import hashlib
from pathlib import Path

import yaml

ESCENARIOS = ("bear", "base", "bull")
UNIDADES = ("automocion", "energia")

# Campo -> (minimo, maximo). Rangos amplios: su funcion es cazar errores de
# transcripcion (un 19 en vez de 0.19), no opinar sobre los supuestos.
CAMPOS_COMUNES = {
    "horizonte_anios": (3, 30),
    "prima_riesgo_mercado": (0.0, 0.15),
    "meses_beta": (24, 120),
    "coste_deuda_antes_impuestos": (0.0, 0.25),
    "tipo_impositivo": (0.0, 0.5),
    "crecimiento_terminal": (-0.02, 0.06),
    "roic_terminal": (0.01, 1.0),
    "reparto_id_automocion": (0.0, 1.0),
}
CAMPOS_ESCENARIO = {
    "id_sobre_ingresos_final": (0.0, 0.5),
    "sga_sobre_ingresos_final": (0.0, 0.5),
}
CAMPOS_UNIDAD = {
    "crecimiento_inicial": (-0.5, 1.0),
    "crecimiento_final": (-0.2, 0.3),
    "margen_bruto_final": (0.0, 0.8),
    "ventas_sobre_capital": (0.1, 20.0),
    "ajuste_wacc": (-0.05, 0.10),
}


class SupuestosInvalidos(Exception):
    """El fichero de supuestos esta incompleto, fuera de rango o sin versionar."""


def _comprobar(bloque: dict, campos: dict, donde: str) -> None:
    for campo, (minimo, maximo) in campos.items():
        if campo not in bloque:
            raise SupuestosInvalidos(f"{donde}: falta '{campo}'")
        valor = bloque[campo]
        if isinstance(valor, bool) or not isinstance(valor, (int, float)):
            raise SupuestosInvalidos(f"{donde}.{campo} no es un numero: {valor!r}")
        if not minimo <= valor <= maximo:
            raise SupuestosInvalidos(
                f"{donde}.{campo} = {valor} fuera de [{minimo}, {maximo}]")


def validar_supuestos(supuestos: dict) -> dict:
    """Devuelve los mismos supuestos si son validos; si no, lanza."""
    for clave in ("version", "comun", "escenarios"):
        if clave not in supuestos:
            raise SupuestosInvalidos(f"falta la seccion '{clave}'")
    if not isinstance(supuestos["version"], str):
        raise SupuestosInvalidos(
            "la version debe ir entre comillas en el YAML, por ejemplo "
            "version: \"2026-09-22\"; sin ellas YAML la convierte en fecha")
    _comprobar(supuestos["comun"], CAMPOS_COMUNES, "comun")
    comun = supuestos["comun"]
    if comun["roic_terminal"] <= comun["crecimiento_terminal"]:
        raise SupuestosInvalidos(
            "comun.roic_terminal debe superar a comun.crecimiento_terminal")
    for campo in ("horizonte_anios", "meses_beta"):
        if not isinstance(comun[campo], int) or isinstance(comun[campo], bool):
            raise SupuestosInvalidos(f"comun.{campo} debe ser un numero entero")
    for escenario in ESCENARIOS:
        if escenario not in supuestos["escenarios"]:
            raise SupuestosInvalidos(f"falta el escenario '{escenario}'")
        bloque = supuestos["escenarios"][escenario]
        _comprobar(bloque, CAMPOS_ESCENARIO, escenario)
        for unidad in UNIDADES:
            if unidad not in bloque:
                raise SupuestosInvalidos(f"{escenario}: falta la unidad '{unidad}'")
            _comprobar(bloque[unidad], CAMPOS_UNIDAD, f"{escenario}.{unidad}")
    return supuestos


def huella(texto: str) -> str:
    """Resumen del contenido del fichero: cambia si cambia cualquier caracter
    del fichero, comentarios incluidos."""
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()[:16]


def cargar_supuestos(ruta) -> tuple[dict, str]:
    texto = Path(ruta).read_text(encoding="utf-8")
    return validar_supuestos(yaml.safe_load(texto)), huella(texto)


def comprobar_congelacion(version: str, huella_actual: str,
                          anterior: dict | None) -> None:
    """Un cambio en los supuestos tiene que ir con una version nueva.

    Si los supuestos cambian y la version no, se detiene: es la disciplina que
    evita retocar el modelo para que valide el precio del dia.
    """
    if not anterior:
        return
    # "version_supuestos" es la clave con que valorar.calcular guarda la
    # version en el resultado: ese es el contrato entre ambos modulos.
    if (anterior.get("version_supuestos") == version
            and anterior.get("huella") != huella_actual):
        raise SupuestosInvalidos(
            f"Los supuestos han cambiado pero la version sigue siendo {version}. "
            "Cambia 'version' a la fecha de la revision para que quede rastro.")
