"""Valoracion completa de Tesla a partir de los datos y los supuestos.

Lee data/*.csv y data/assumptions.yaml, calcula y escribe
dist/valoracion.json, que consumira el cuadro de mando. No accede a la red.

    python -m src.valorar          valoracion oficial: comprueba la congelacion
                                   de los supuestos y escribe el resultado
    python -m src.valorar --borrador   solo imprime, no escribe ni comprueba

Es una herramienta analitica que refleja los supuestos de quien la usa; no es
asesoramiento de inversion.
"""
import json
import math
import sys
from datetime import date
from pathlib import Path

import pandas as pd

from src.multiplos import MULTIPLOS, multiplos_mensuales, percentil_actual
from src.reverse_dcf import crecimiento_implicito, rejilla, valor_con_crecimiento
from src.schema import FINANCIALS, MARKET
from src.sotp import (
    CAMPOS_BASE_FLUJO, CAMPOS_BASE_SALDO, UNIDADES, AnioBase, anio_base,
    proyectar, suma_unidades, valor_por_accion,
)
from src.supuestos import ESCENARIOS, cargar_supuestos, comprobar_congelacion
from src.ttm import ttm_en
from src.validate import validar, validar_continuidad_mensual
from src.wacc import beta, coste_capital_propio, rentabilidades, wacc

RUTA_SUPUESTOS = "data/assumptions.yaml"
RUTA_RESULTADO = Path("dist/valoracion.json")
CRECIMIENTOS_REJILLA = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40]
MARGENES_REJILLA = [0.15, 0.19, 0.23, 0.27, 0.30]
NOMBRES_MULTIPLOS = {"ev_ventas": "EV/Ventas", "per": "PER",
                     "ev_ebitda": "EV/EBITDA", "p_fcf": "P/FCF"}


def sin_nan(valor):
    """El JSON no admite NaN: los huecos se escriben como null."""
    if isinstance(valor, float) and math.isnan(valor):
        return None
    if isinstance(valor, dict):
        return {k: sin_nan(v) for k, v in valor.items()}
    if isinstance(valor, list):
        return [sin_nan(v) for v in valor]
    return valor


def base_y_balance(financieros: pd.DataFrame, hoy: str) -> tuple[AnioBase, dict, str]:
    """Año base, balance y ultimo trimestre de los doce meses conocidos en `hoy`.

    Lo usan la valoracion y el simulador de la pagina, que tiene que partir
    exactamente del mismo punto.
    """
    ttm = ttm_en(financieros, hoy, flujos=CAMPOS_BASE_FLUJO, saldos=CAMPOS_BASE_SALDO)
    if ttm is None:
        raise ValueError(
            "no hay cuatro trimestres consecutivos publicados con todos los "
            "datos necesarios")
    balance = {"caja": ttm["cash_and_investments"],
               "inversiones": ttm["short_term_investments"],
               "deuda": ttm["total_debt"], "acciones": ttm["shares_outstanding"]}
    return anio_base(ttm), balance, ttm["periodo"]


def calcular(financieros: pd.DataFrame, mercado: pd.DataFrame, supuestos: dict,
             huella: str, hoy: str) -> dict:
    comun = supuestos["comun"]
    base, balance, ttm_hasta = base_y_balance(financieros, hoy)
    precio = float(mercado["price_close"].iloc[-1])
    capitalizacion = precio * balance["acciones"]

    completos = mercado[mercado["month"] < hoy[:7]]
    if len(completos) < comun["meses_beta"] + 1:
        raise ValueError(
            f"hacen falta {comun['meses_beta'] + 1} meses completos para la "
            f"beta y solo hay {len(completos)} antes de {hoy[:7]}")
    ventana = completos.tail(comun["meses_beta"] + 1)
    beta_ = beta(rentabilidades(ventana["price_close"].tolist()),
                 rentabilidades(ventana["spy_close"].tolist()))
    rf = float(mercado["rf_10y"].iloc[-1])
    ke = coste_capital_propio(rf, beta_, comun["prima_riesgo_mercado"])
    w = wacc(ke, comun["coste_deuda_antes_impuestos"], comun["tipo_impositivo"],
             capitalizacion, balance["deuda"])

    def por_accion(esc, tasa, reparto=None):
        return valor_por_accion(suma_unidades(
            proyectar(base, esc, comun, tasa, reparto_id=reparto)), **balance)

    escenarios = {}
    for nombre in ESCENARIOS:
        unidades = proyectar(base, supuestos["escenarios"][nombre], comun, w)
        vpa = valor_por_accion(suma_unidades(unidades), **balance)
        escenarios[nombre] = {
            "valor_por_accion": vpa,
            "valor_acciones": vpa * balance["acciones"],
            "valor_unidades": {u: unidades[u].valor for u in UNIDADES},
            "precio_frente_a_valor": precio / vpa - 1 if vpa > 0 else None,
        }

    esc_base = supuestos["escenarios"]["base"]
    sensibilidad_wacc = {}
    for delta in (-0.02, 0.0, 0.02):
        try:
            sensibilidad_wacc[f"{delta:+.0%}"] = por_accion(esc_base, w + delta)
        except ValueError:
            sensibilidad_wacc[f"{delta:+.0%}"] = None   # tasa por debajo de g
    sensibilidad_reparto = {
        f"{r:.0%}": {u: p.valor for u, p in
                     proyectar(base, esc_base, comun, w, reparto_id=r).items()}
        for r in (0.70, 0.85, 1.00)
    }

    g_implicito = crecimiento_implicito(precio, base, esc_base, comun, w, balance)
    motivo = None
    if g_implicito is None:
        valor_bajista = valor_con_crecimiento(-0.10, base, esc_base, comun, w, balance)
        motivo = ("el precio esta por debajo del valor incluso con los ingresos "
                  "cayendo un 10% anual" if precio < valor_bajista else
                  "no se alcanza el precio con crecimientos de hasta el 80% anual")

    serie = multiplos_mensuales(financieros, mercado)
    multiplos = {}
    for m in MULTIPLOS:
        columna = pd.to_numeric(serie[m], errors="coerce")
        ultimo = columna.iloc[-1] if not columna.empty else float("nan")
        multiplos[m] = {
            "actual": None if pd.isna(ultimo) else float(ultimo),
            "mediana": float(columna.median()) if columna.notna().any() else None,
            "percentil": percentil_actual(columna),
        }

    resultado = {
        "fecha": hoy,
        "version_supuestos": supuestos["version"],
        "huella": huella,
        "ttm_hasta": ttm_hasta,
        "precio": precio,
        "mes_precio": mercado["month"].iloc[-1],
        "precio_obtenido": (mercado["retrieved_at"].iloc[-1]
                            if "retrieved_at" in mercado.columns else None),
        "capitalizacion": capitalizacion,
        "coste_capital": {"tipo_sin_riesgo": rf, "beta": beta_,
                          "prima_riesgo": comun["prima_riesgo_mercado"],
                          "coste_acciones": ke, "wacc": w},
        "escenarios": escenarios,
        "opcionalidad_implicita": capitalizacion - escenarios["base"]["valor_acciones"],
        "horizonte_anios": comun["horizonte_anios"],
        "crecimiento_implicito": g_implicito,
        "crecimiento_implicito_motivo": motivo,
        "rejilla": {"crecimientos": CRECIMIENTOS_REJILLA,
                    "margenes_automocion": MARGENES_REJILLA,
                    "valor_por_accion": rejilla(base, esc_base, comun, w, balance,
                                                CRECIMIENTOS_REJILLA, MARGENES_REJILLA)},
        "sensibilidad": {"wacc": sensibilidad_wacc,
                         "reparto_id_automocion": sensibilidad_reparto},
        "multiplos": multiplos,
        "serie_multiplos": serie.to_dict(orient="records"),
    }
    return sin_nan(resultado)


def comprobar_frescura(mercado: pd.DataFrame, hoy: str) -> None:
    """La valoracion oficial exige el precio del mes en curso."""
    ultimo = mercado["month"].iloc[-1]
    if ultimo != hoy[:7]:
        raise ValueError(
            f"el ultimo precio es de {ultimo} y hoy es {hoy}: "
            "ejecuta python -m src.cargar_mercado antes de valorar")


def _cifra(x):
    return "n/d" if x is None else f"{x:.1f}"


def resumen(r: dict) -> str:
    cc = r["coste_capital"]
    lineas = [
        f"Valoracion de TSLA a {r['fecha']} (supuestos {r['version_supuestos']}, "
        f"ultimos doce meses hasta {r['ttm_hasta']})",
        f"Precio {r['precio']:.2f} USD (mes {r['mes_precio']}) | "
        f"capitalizacion {r['capitalizacion']/1e9:,.0f} mil M USD",
        f"Coste de capital: tipo sin riesgo {cc['tipo_sin_riesgo']:.2%}, beta {cc['beta']:.2f}, "
        f"prima {cc['prima_riesgo']:.2%} -> acciones {cc['coste_acciones']:.2%}, WACC {cc['wacc']:.2%}",
        "",
        f"{'escenario':10} {'valor/accion':>13} {'precio frente a valor':>23}",
    ]
    for nombre, e in r["escenarios"].items():
        pfv = e["precio_frente_a_valor"]
        lineas.append(f"{nombre:10} {e['valor_por_accion']:>13.2f} "
                      f"{('n/d' if pfv is None else f'{pfv:+.0%}'):>23}")
    op = r["opcionalidad_implicita"]
    lineas += [
        "",
        f"Opcionalidad implicita: {op/1e9:,.0f} mil M USD "
        f"({op / r['capitalizacion']:.0%} de la capitalizacion)",
    ]
    g = r["crecimiento_implicito"]
    lineas.append(
        f"Crecimiento anual de ingresos implicito a {r['horizonte_anios']} anios: "
        + (f"{g:.1%}" if g is not None else r["crecimiento_implicito_motivo"]))
    lineas += ["", f"{'multiplo':10} {'actual':>8} {'mediana':>8} {'percentil':>10}"]
    for m, v in r["multiplos"].items():
        pct = "n/d" if v["percentil"] is None else f"{v['percentil']:.0%}"
        lineas.append(f"{NOMBRES_MULTIPLOS[m]:10} {_cifra(v['actual']):>8} "
                      f"{_cifra(v['mediana']):>8} {pct:>10}")
    lineas += ["", "Herramienta analitica basada en supuestos propios: no es asesoramiento de inversion."]
    return "\n".join(lineas)


def main(borrador: bool = False) -> None:
    financieros = pd.read_csv("data/financials_quarterly.csv")
    mercado = pd.read_csv("data/market_monthly.csv")
    validar(financieros, FINANCIALS)
    validar(mercado, MARKET)
    mercado = mercado.sort_values("month").reset_index(drop=True)
    validar_continuidad_mensual(mercado["month"].tolist())
    supuestos, huella = cargar_supuestos(RUTA_SUPUESTOS)
    hoy = date.today().isoformat()
    if not borrador:
        comprobar_frescura(mercado, hoy)
        anterior = (json.loads(RUTA_RESULTADO.read_text(encoding="utf-8"))
                    if RUTA_RESULTADO.exists() else None)
        comprobar_congelacion(supuestos["version"], huella, anterior)
    r = calcular(financieros, mercado, supuestos, huella, hoy)
    print(resumen(r))
    if not borrador:
        RUTA_RESULTADO.parent.mkdir(exist_ok=True)
        RUTA_RESULTADO.write_text(
            json.dumps(r, indent=2, ensure_ascii=False, allow_nan=False),
            encoding="utf-8")
        print(f"\nResultado escrito en {RUTA_RESULTADO}")


if __name__ == "__main__":
    main(borrador="--borrador" in sys.argv)
