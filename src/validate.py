"""Valida un DataFrame contra un esquema. Sin red, sin E/S."""
import pandas as pd

from src.schema import Esquema


class ErrorValidacion(Exception):
    """El marco de datos no cumple el esquema declarado."""


def validar(df: pd.DataFrame, esquema: Esquema) -> None:
    """Lanza ErrorValidacion con un mensaje accionable si algo no cuadra."""
    for campo in esquema.campos:
        if campo.nombre not in df.columns:
            if campo.obligatorio:
                raise ErrorValidacion(
                    f"[{esquema.nombre}] falta la columna '{campo.nombre}'"
                )
            continue

        serie = df[campo.nombre]

        if campo.obligatorio and serie.isna().any():
            filas = df.index[serie.isna()].tolist()
            raise ErrorValidacion(
                f"[{esquema.nombre}] '{campo.nombre}' tiene nulos en {filas}"
            )

        if campo.tipo in ("float", "int"):
            numerica = pd.to_numeric(serie, errors="coerce")
            no_convertibles = serie.notna() & numerica.isna()
            if no_convertibles.any():
                filas = df.index[no_convertibles].tolist()
                raise ErrorValidacion(
                    f"[{esquema.nombre}] '{campo.nombre}' no es numerico en {filas}"
                )
            if campo.minimo is not None and (numerica < campo.minimo).any():
                raise ErrorValidacion(
                    f"[{esquema.nombre}] '{campo.nombre}' fuera de rango: "
                    f"minimo {campo.minimo}, encontrado {numerica.min()}"
                )
            if campo.maximo is not None and (numerica > campo.maximo).any():
                raise ErrorValidacion(
                    f"[{esquema.nombre}] '{campo.nombre}' fuera de rango: "
                    f"maximo {campo.maximo}, encontrado {numerica.max()}"
                )

    faltan_clave = [c for c in esquema.clave if c not in df.columns]
    if faltan_clave:
        raise ErrorValidacion(
            f"[{esquema.nombre}] falta la columna clave {faltan_clave}"
        )
    duplicadas = df[df.duplicated(subset=esquema.clave, keep=False)]
    if not duplicadas.empty:
        valores = duplicadas[esquema.clave].to_dict("records")
        raise ErrorValidacion(
            f"[{esquema.nombre}] claves duplicadas: {valores}"
        )


def periodos_esperados(desde: str, hasta: str) -> list[str]:
    """Genera la serie trimestral completa entre dos periodos, ambos incluidos.

    Formato de periodo: "2019Q1".
    """
    anio_i, trim_i = int(desde[:4]), int(desde[5])
    anio_f, trim_f = int(hasta[:4]), int(hasta[5])

    if not (1 <= trim_i <= 4):
        raise ValueError(f"trimestre invalido en '{desde}': debe estar entre 1 y 4")
    if not (1 <= trim_f <= 4):
        raise ValueError(f"trimestre invalido en '{hasta}': debe estar entre 1 y 4")
    if (anio_i, trim_i) > (anio_f, trim_f):
        raise ValueError(
            f"rango invertido: '{desde}' es posterior a '{hasta}'"
        )

    serie = []
    anio, trim = anio_i, trim_i
    while (anio, trim) <= (anio_f, trim_f):
        serie.append(f"{anio}Q{trim}")
        trim += 1
        if trim == 5:
            trim = 1
            anio += 1
    return serie


def validar_continuidad(periodos, desde: str, hasta: str) -> None:
    """Lanza ErrorValidacion si falta algun trimestre de la serie."""
    faltan = sorted(set(periodos_esperados(desde, hasta)) - set(periodos))
    if faltan:
        raise ErrorValidacion(f"faltan trimestres en la serie: {faltan}")


def validar_continuidad_mensual(meses) -> None:
    """Lanza ErrorValidacion si falta algun mes entre el primero y el ultimo."""
    periodos = pd.PeriodIndex(sorted(meses), freq="M")
    esperados = pd.period_range(periodos.min(), periodos.max(), freq="M")
    faltan = [str(p) for p in esperados.difference(periodos)]
    if faltan:
        raise ErrorValidacion(f"faltan meses en la serie: {faltan}")
