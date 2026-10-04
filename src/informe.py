"""Informe de lo que cambia en una actualizacion frente al ultimo commit.

Funciones puras sobre DataFrames: la lectura de la version anterior (git) y
la escritura del informe las hace src/actualizar.py.
"""
import hashlib
import math
import numbers
from pathlib import Path

import pandas as pd

TOLERANCIA = 1e-9
UMBRAL_PRECIO = 0.40
UMBRAL_EURUSD = 0.08
UMBRAL_TIPO = 0.01
UMBRAL_INGRESOS = 0.40


def _ignorado(campo: str) -> bool:
    """Columnas de trazabilidad: no son cifras, no cuentan como reexpresion.

    source_update_letter cita siempre la carta mas reciente que cubre el
    trimestre y cambia cada vez que llega una carta nueva, sin que las cifras
    cambien; de ahi el prefijo "source" en vez de un nombre exacto.
    """
    return campo == "retrieved_at" or campo.startswith("source")


def _nulo(x) -> bool:
    return x is None or (isinstance(x, float) and math.isnan(x)) or pd.isna(x)


def _limpio(x):
    """Valor serializable en JSON: los numeros de numpy pasan a float."""
    if _nulo(x):
        return None
    if isinstance(x, numbers.Number) and not isinstance(x, bool):
        return float(x)
    return x


def _iguales(a, b) -> bool:
    if _nulo(a) and _nulo(b):
        return True
    if _nulo(a) or _nulo(b):
        return False
    try:
        fa, fb = float(a), float(b)
    except (TypeError, ValueError):
        return a == b
    if not (math.isfinite(fa) and math.isfinite(fb)):
        # inf/-inf: la formula de tolerancia relativa daria nan al restarlos.
        return fa == fb
    return abs(fa - fb) <= TOLERANCIA * max(abs(fa), abs(fb), 1e-300)


def comparar(nuevo: pd.DataFrame, anterior: pd.DataFrame | None,
             clave: str) -> tuple[list[str], list[dict], list[str]]:
    """Periodos nuevos, campos cambiados en los que ya estaban, y periodos eliminados.

    Un periodo eliminado suele ser sintoma de una descarga fallida, no una
    revision real: quien llama decide si detener la rutina.
    """
    if anterior is None:
        return sorted(nuevo[clave].astype(str)), [], []
    previos = anterior.set_index(clave)
    presentes = set(nuevo[clave])
    eliminados = sorted(str(p) for p in previos.index if p not in presentes)
    nuevos, reexpresiones = [], []
    for _, fila in nuevo.sort_values(clave).iterrows():
        periodo = fila[clave]
        if periodo not in previos.index:
            nuevos.append(str(periodo))
            continue
        vieja = previos.loc[periodo]
        for campo in nuevo.columns:
            # Una columna que no existia en la version anterior es nueva, no
            # una reexpresion: no hay "antes" con el que comparar.
            if campo == clave or _ignorado(campo) or campo not in previos.columns:
                continue
            antes = vieja[campo]
            if not _iguales(fila[campo], antes):
                reexpresiones.append({"periodo": str(periodo), "campo": campo,
                                      "antes": _limpio(antes), "despues": _limpio(fila[campo])})
    return nuevos, reexpresiones, eliminados


def comparar_columnas(nuevo: pd.DataFrame, anterior: pd.DataFrame | None,
                      clave: str) -> tuple[list[str], list[str]]:
    """Columnas que aparecen o desaparecen entre versiones, fuera de trazabilidad."""
    if anterior is None:
        return [], []
    antes = {c for c in anterior.columns if c != clave and not _ignorado(c)}
    despues = {c for c in nuevo.columns if c != clave and not _ignorado(c)}
    return sorted(despues - antes), sorted(antes - despues)


def resumen_mercado(nuevo: pd.DataFrame, anterior: pd.DataFrame | None) -> dict:
    m = nuevo.sort_values("month").reset_index(drop=True)
    meses_previos = set(anterior["month"]) if anterior is not None else set()
    ultimo, previo = m.iloc[-1], (m.iloc[-2] if len(m) > 1 else None)
    par = lambda c: {"antes": None if previo is None else _limpio(previo[c]),
                     "despues": _limpio(ultimo[c])}
    return {
        "meses_nuevos": [str(x) for x in m["month"] if x not in meses_previos],
        "ultimo_mes": str(ultimo["month"]),
        "mes_anterior": None if previo is None else str(previo["month"]),
        "precio": par("price_close"),
        "eurusd": par("eurusd"),
        "rf_10y": par("rf_10y"),
    }


def _variacion(antes, despues) -> float | None:
    if _nulo(antes) or _nulo(despues) or float(antes) == 0:
        return None
    return float(despues) / float(antes) - 1


def avisos(mercado: pd.DataFrame, financieros: pd.DataFrame,
           trimestres_nuevos: list[str]) -> list[str]:
    """Variaciones anomalas que el usuario debe mirar. No detienen la rutina."""
    textos = []
    m = mercado.sort_values("month").reset_index(drop=True)
    if len(m) > 1:
        a, d = m.iloc[-2], m.iloc[-1]
        v = _variacion(a["price_close"], d["price_close"])
        if v is not None and abs(v) > UMBRAL_PRECIO:
            textos.append(f"El precio de {d['month']} varia un {v:+.1%} frente a {a['month']}")
        v = _variacion(a["eurusd"], d["eurusd"])
        if v is not None and abs(v) > UMBRAL_EURUSD:
            textos.append(f"El EUR/USD de {d['month']} varia un {v:+.1%} frente a {a['month']}")
        if not _nulo(a["rf_10y"]) and not _nulo(d["rf_10y"]):
            dif = float(d["rf_10y"]) - float(a["rf_10y"])
            # Redondeado: 0.050 - 0.040 da 0,010000000000000002 en coma
            # flotante, y sin redondear avisaria por exactamente 1 punto.
            if round(abs(dif), 10) > UMBRAL_TIPO:
                textos.append(f"El tipo sin riesgo de {d['month']} varia {dif * 100:+.2f} "
                              f"puntos frente a {a['month']}")
    f = financieros.sort_values("period").reset_index(drop=True)
    for periodo in trimestres_nuevos:
        idx = f.index[f["period"] == periodo]
        if len(idx) == 0 or idx[0] == 0:
            continue
        v = _variacion(f.loc[idx[0] - 1, "revenue_total"], f.loc[idx[0], "revenue_total"])
        if v is not None and abs(v) > UMBRAL_INGRESOS:
            textos.append(f"Los ingresos de {periodo} varian un {v:+.1%} frente al "
                          "trimestre anterior")
    return textos


def huella_datos(rutas: list[Path]) -> str:
    """Hash de los ficheros de datos: nombre, longitud y contenido de cada uno.

    Incluir el nombre y la longitud antes del contenido evita la ambiguedad
    de una simple concatenacion, donde mover bytes de un fichero al
    siguiente ("AB"+"CD" frente a "A"+"BCD") daria la misma huella.
    Normalizar CRLF a LF evita que un cambio de terminador de linea (por
    ejemplo, al editar un CSV en Windows) parezca un cambio real de los datos.
    """
    h = hashlib.sha256()
    for ruta in rutas:
        ruta = Path(ruta)
        contenido = ruta.read_bytes().replace(b"\r\n", b"\n")
        h.update(f"{ruta.name}:{len(contenido)}:".encode("utf-8"))
        h.update(contenido)
    return h.hexdigest()


FICHEROS = (("financials_quarterly", "period"), ("operating_quarterly", "period"),
           ("market_monthly", "month"))


def construir_informe(actual: dict[str, pd.DataFrame],
                      anterior: dict[str, pd.DataFrame | None],
                      hoy: str, huella: str) -> dict:
    trimestres: dict[str, list[str]] = {}
    reexpresiones, eliminados = {}, {}
    columnas_nuevas, columnas_eliminadas = {}, {}
    for nombre, clave in FICHEROS:
        nuevos, cambios, elim = comparar(actual[nombre], anterior.get(nombre), clave)
        if nombre != "market_monthly":
            trimestres[nombre] = nuevos
        reexpresiones[nombre], eliminados[nombre] = cambios, elim
        cn, ce = comparar_columnas(actual[nombre], anterior.get(nombre), clave)
        columnas_nuevas[nombre], columnas_eliminadas[nombre] = cn, ce

    # El ultimo mes de la version anterior era parcial por construccion (es
    # el cierre mas reciente, que se sigue actualizando dentro del mes): su
    # cambio no es una reexpresion, es "el mes revisado" del resumen.
    mercado_anterior = anterior.get("market_monthly")
    mes_en_curso = None
    if mercado_anterior is not None and len(mercado_anterior):
        mes_en_curso = str(mercado_anterior.sort_values("month")["month"].iloc[-1])
    cambios_mes_en_curso = [c for c in reexpresiones["market_monthly"]
                            if c["periodo"] == mes_en_curso]
    reexpresiones["market_monthly"] = [c for c in reexpresiones["market_monthly"]
                                       if c["periodo"] != mes_en_curso]

    mercado = resumen_mercado(actual["market_monthly"], mercado_anterior)
    mercado["mes_revisado"] = (
        {"mes": mes_en_curso,
         "campos": [{"campo": c["campo"], "antes": c["antes"], "despues": c["despues"]}
                    for c in cambios_mes_en_curso]}
        if cambios_mes_en_curso else None
    )

    return {
        "fecha": hoy,
        "huella_datos": huella,
        "trimestres_nuevos": trimestres,
        # Solo un trimestre financiero nuevo cambia la base del modelo; las
        # entregas se publican unas tres semanas antes que el 10-Q.
        "revision_trimestral": bool(trimestres["financials_quarterly"]),
        "reexpresiones": reexpresiones,
        "periodos_eliminados": eliminados,
        "columnas_nuevas": columnas_nuevas,
        "columnas_eliminadas": columnas_eliminadas,
        "mercado": mercado,
        "avisos": avisos(actual["market_monthly"], actual["financials_quarterly"],
                         trimestres["financials_quarterly"]),
    }
