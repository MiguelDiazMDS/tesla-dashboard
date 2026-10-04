"""Historico mensual de la valoracion oficial: una fila por mes.

    python -m src.historico     registra la valoracion oficial vigente
"""
import json
from pathlib import Path

import pandas as pd

from src.schema import HISTORICO
from src.validate import validar

RUTA = Path("data/historico_valoraciones.csv")
VALORACION = Path("dist/valoracion.json")
COLUMNAS = [c.nombre for c in HISTORICO.campos]
# Sin esto, una huella o una version solo con digitos se leeria como numero.
TEXTO = {c.nombre: str for c in HISTORICO.campos if c.tipo == "str"}


def leer(ruta: Path = RUTA) -> pd.DataFrame:
    if not Path(ruta).exists():
        return pd.DataFrame(columns=COLUMNAS)
    # round_trip evita que el redondeo por defecto de pandas (repr de C, con
    # menos cifras) introduzca deriva en los decimales al releer y reescribir.
    return pd.read_csv(ruta, dtype=TEXTO, float_precision="round_trip")


def fila_de_valoracion(v: dict) -> dict:
    esc = v["escenarios"]
    return {
        "mes": v["mes_precio"], "fecha": v["fecha"],
        "version_supuestos": v["version_supuestos"], "huella": v["huella"],
        "ttm_hasta": v["ttm_hasta"], "precio": v["precio"],
        "vpa_bear": esc["bear"]["valor_por_accion"],
        "vpa_base": esc["base"]["valor_por_accion"],
        "vpa_bull": esc["bull"]["valor_por_accion"],
        "crecimiento_implicito": v["crecimiento_implicito"],
        "opcionalidad_implicita": v["opcionalidad_implicita"],
        "wacc": v["coste_capital"]["wacc"],
    }


def registrar(valoracion: dict, ruta: Path = RUTA) -> pd.DataFrame:
    """Anade la fila del mes de la valoracion o sustituye la que ya hubiera."""
    fila = pd.DataFrame([fila_de_valoracion(valoracion)], columns=COLUMNAS)
    previo = leer(ruta)
    previo = previo[previo["mes"] != fila["mes"].iloc[0]]
    df = pd.concat([previo, fila], ignore_index=True) if len(previo) else fila
    df = df.sort_values("mes").reset_index(drop=True)[COLUMNAS]
    validar(df, HISTORICO)
    df.to_csv(ruta, index=False)
    return df


def main() -> None:
    valoracion = json.loads(VALORACION.read_text(encoding="utf-8"))
    df = registrar(valoracion)
    print(f"{RUTA.as_posix()}: {len(df)} meses, ultimo {df['mes'].iloc[-1]}")


if __name__ == "__main__":
    main()
