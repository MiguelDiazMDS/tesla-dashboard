"""Datos de la pagina del cuadro de mando.

Reune lo que muestra la pagina a partir de los CSV, la valoracion oficial y
los supuestos, y calcula los KPIs derivados. No accede a la red. Los huecos se
escriben como None (null en el JSON), nunca como cero.
"""
import math
from dataclasses import asdict

import pandas as pd

from src.multiplos import MULTIPLOS
from src.valorar import base_y_balance, sin_nan

CAMPOS_TRIMESTRALES = (
    "deliveries_total", "production_total", "deliveries_volumen",
    "deliveries_nicho", "production_volumen", "production_nicho",
    "days_inventory", "storage_deployed_gwh", "fsd_subscriptions",
    "revenue_total", "revenue_auto_segment", "gross_profit_auto_segment",
    "cogs_auto_segment", "revenue_energy_segment", "gross_profit_energy_segment",
    "revenue_auto_sales", "revenue_reg_credits", "revenue_auto_leasing",
    "revenue_services", "revenue_energy_sales", "revenue_energy_leasing",
    "revenue_us", "revenue_china", "revenue_other", "operating_income",
    "ocf", "capex", "shares_outstanding", "total_debt", "cash_and_investments",
    "short_term_investments", "deferred_revenue_current",
    "deferred_revenue_noncurrent",
)
ETIQUETAS = ("etiqueta_volumen", "etiqueta_nicho")


def _num(valor) -> float | None:
    try:
        f = float(valor)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _div(a, b) -> float | None:
    if a is None or b is None or b == 0:
        return None
    return a / b


def _resta(a, b) -> float | None:
    return None if a is None or b is None else a - b


def _valor_de_fila(r: pd.Series, campo: str) -> float | None:
    return _num(r[campo]) if campo in r.index else None


def kpis_trimestrales(financieros: pd.DataFrame,
                      operativos: pd.DataFrame) -> list[dict]:
    """Una fila por trimestre con los campos que usa la pagina y los derivados."""
    ope = operativos.drop(columns=[c for c in ("source", "retrieved_at")
                                   if c in operativos.columns])
    df = financieros.merge(ope, on="period", how="outer").sort_values("period")
    filas = []
    for _, r in df.iterrows():
        fila = {"period": r["period"]}
        for campo in CAMPOS_TRIMESTRALES:
            fila[campo] = _valor_de_fila(r, campo)
        for campo in ETIQUETAS:
            texto = r[campo] if campo in r.index else None
            fila[campo] = texto if isinstance(texto, str) else None
        creditos = fila["revenue_reg_credits"]
        # Aproximado: las entregas incluyen vehiculos en leasing, cuyos ingresos
        # no estan en revenue_auto_sales, asi que el ASP sale sesgado a la baja.
        fila["asp_implicito"] = _div(fila["revenue_auto_sales"], fila["deliveries_total"])
        # Aproximado: el coste del segmento de automocion incluye servicios.
        fila["coste_por_vehiculo"] = _div(fila["cogs_auto_segment"], fila["deliveries_total"])
        fila["ratio_produccion_entregas"] = _div(fila["production_total"],
                                                 fila["deliveries_total"])
        fila["margen_auto_sin_creditos"] = _div(
            _resta(fila["gross_profit_auto_segment"], creditos),
            _resta(fila["revenue_auto_segment"], creditos))
        fila["margen_energia"] = _div(fila["gross_profit_energy_segment"],
                                      fila["revenue_energy_segment"])
        fila["margen_operativo"] = _div(fila["operating_income"], fila["revenue_total"])
        fila["fcf"] = _resta(fila["ocf"], fila["capex"])
        filas.append(fila)
    return filas


def retorno_eur(mercado: pd.DataFrame) -> dict:
    """Retorno en USD y en EUR y efecto divisa, para tres periodos.

    `eurusd` son dolares por euro, asi que el precio en euros es precio / eurusd.
    El efecto divisa es multiplicativo: efecto_divisa = fx0 / fx1 - 1, de forma
    que (1 + eur) = (1 + usd) * (1 + efecto_divisa).
    El mes final es siempre el ultimo; si falta el mes inicial, el periodo es None.
    """
    serie = mercado.sort_values("month").set_index("month")
    ultimo = serie.index[-1]
    anio = int(ultimo[:4])
    inicios = {
        "desde_2019": "2019-01",
        "ultimos_12_meses": f"{anio - 1}{ultimo[4:]}",
        "en_el_anio": f"{anio - 1}-12",
    }
    p1, fx1 = serie.loc[ultimo, "price_close"], serie.loc[ultimo, "eurusd"]
    salida: dict = {}
    for clave, inicio in inicios.items():
        if inicio not in serie.index:
            salida[clave] = None
            continue
        p0, fx0 = serie.loc[inicio, "price_close"], serie.loc[inicio, "eurusd"]
        usd = p1 / p0 - 1
        eur = (p1 / fx1) / (p0 / fx0) - 1
        efecto_divisa = fx0 / fx1 - 1
        salida[clave] = {"desde": inicio, "hasta": ultimo, "usd": float(usd),
                         "eur": float(eur), "efecto_divisa": float(efecto_divisa)}
    return salida


# (nombre visible, etiqueta R/D/E, fuente, fichero de origen, campo testigo)
# El campo testigo sirve para fechar el ultimo periodo con dato.
CATALOGO = (
    ("Entregas y producción", "R", "Nota de producción y entregas (8-K, exhibit 99.1)",
     "operativos", "deliveries_total"),
    ("Días de inventario", "R", "Update Letter trimestral", "operativos", "days_inventory"),
    ("Almacenamiento desplegado (GWh)", "R",
     "Update Letter trimestral; hasta que se publica, nota de producción y entregas (8-K)",
     "operativos", "storage_deployed_gwh"),
    ("Suscripciones activas de FSD", "R", "Update Letter trimestral",
     "operativos", "fsd_subscriptions"),
    ("Ingresos, márgenes y resultado", "R", "API XBRL de la SEC (companyfacts)",
     "financieros", "revenue_total"),
    ("Segmentos, líneas de producto y regiones", "R",
     "Estados renderizados de los 10-Q y 10-K", "financieros", "revenue_auto_segment"),
    ("Flujo de caja y capex", "R", "API XBRL de la SEC, desacumulado",
     "financieros", "ocf"),
    ("Deuda, caja e inversiones a corto plazo", "R", "API XBRL de la SEC",
     "financieros", "total_debt"),
    ("Acciones en circulación", "R", "API XBRL de la SEC, normalizadas por split",
     "financieros", "shares_outstanding"),
    ("Deferred revenue", "R", "API XBRL de la SEC", "financieros",
     "deferred_revenue_current"),
    ("ASP implícito y coste por vehículo", "D",
     "Ingresos por venta de vehículos y coste de automoción entre entregas. "
     "Aproximado: las entregas incluyen leasing y el coste incluye servicios",
     "kpi", "asp_implicito"),
    ("Márgenes derivados y FCF", "D", "Calculados a partir de los estados",
     "kpi", "fcf"),
    ("Cotización de TSLA y SPY", "R", "api.nasdaq.com", "mercado", "price_close"),
    ("Tipo sin riesgo a 10 años", "R", "Tesoro de EE.UU.", "mercado", "rf_10y"),
    ("EUR/USD", "R", "Banco Central Europeo", "mercado", "eurusd"),
    ("Valoración, múltiplos y opcionalidad", "D", "Motor de valoración",
     "valoracion", None),
)


def serie_mensual(mercado: pd.DataFrame, valoracion: dict) -> list[dict]:
    multiplos = {m["month"]: m for m in valoracion["serie_multiplos"]}
    filas = []
    for _, r in mercado.sort_values("month").iterrows():
        m = multiplos.get(r["month"], {})
        filas.append({
            "month": r["month"],
            "price_close": _num(r.get("price_close")),
            "eurusd": _num(r.get("eurusd")),
            **{k: m.get(k) for k in MULTIPLOS},
        })
    return filas


def _suma_trimestres(filas: pd.DataFrame, campo: str) -> float | None:
    """Suma de cuatro trimestres; None si falta alguno."""
    valores = [_num(v) for v in filas[campo]] if campo in filas.columns else []
    if len(valores) != 4 or any(v is None for v in valores):
        return None
    return sum(valores)


def anio_cero(financieros: pd.DataFrame, ttm_hasta: str) -> dict:
    """FCF reportado de los doce meses base e ingresos de los doce anteriores.

    El FCF reportado es flujo operativo menos capex. Los ingresos previos
    permiten a la pagina calcular la reinversion del modelo en el año base.
    """
    f = financieros.sort_values("period").reset_index(drop=True)
    i = int(f.index[f["period"] == ttm_hasta][0])
    ventana = f.iloc[i - 3:i + 1] if i >= 3 else f.iloc[0:0]
    previa = f.iloc[i - 7:i - 3] if i >= 7 else f.iloc[0:0]
    ocf, capex = _suma_trimestres(ventana, "ocf"), _suma_trimestres(ventana, "capex")
    auto = _suma_trimestres(previa, "revenue_auto_segment")
    energia = _suma_trimestres(previa, "revenue_energy_segment")
    return {
        "hasta": ttm_hasta, "ocf": ocf, "capex": capex, "fcf_reportado": _resta(ocf, capex),
        "ingresos_previos": (None if auto is None or energia is None
                             else {"automocion": auto, "energia": energia}),
    }


def datos_simulador(financieros: pd.DataFrame, supuestos: dict,
                    valoracion: dict) -> dict:
    """Lo que necesita motor.js para reproducir la valoracion oficial.

    Parte de la fecha de la valoracion para usar exactamente el mismo año base.
    """
    base, balance, ttm_hasta = base_y_balance(financieros, valoracion["fecha"])
    if ttm_hasta != valoracion["ttm_hasta"]:
        raise ValueError(
            f"el ttm_hasta recalculado ({ttm_hasta}) no coincide con el de la "
            f"valoracion oficial ({valoracion['ttm_hasta']}): revisa los datos "
            "financieros o la fecha de la valoracion")
    return {
        "base": asdict(base),
        "balance": balance,
        "wacc": valoracion["coste_capital"]["wacc"],
        "precio": valoracion["precio"],
        "supuestos": supuestos,
        "anio_cero": anio_cero(financieros, ttm_hasta),
    }


def _ultimo_periodo(filas: list[dict], clave: str, campo: str) -> str | None:
    con_dato = [f[clave] for f in filas if f.get(campo) is not None]
    return con_dato[-1] if con_dato else None


def _obtenido(df: pd.DataFrame) -> str | None:
    if "retrieved_at" not in df.columns or df["retrieved_at"].dropna().empty:
        return None
    return str(df["retrieved_at"].dropna().max())


def _mas_reciente(a: str | None, b: str | None) -> str | None:
    valores = [v for v in (a, b) if v is not None]
    return max(valores) if valores else None


def trazabilidad(financieros, operativos, mercado, valoracion,
                 trimestral: list[dict], mensual: list[dict]) -> list[dict]:
    obt_financieros = _obtenido(financieros)
    obt_operativos = _obtenido(operativos)
    obtenido = {"financieros": obt_financieros,
                "operativos": obt_operativos,
                "kpi": _mas_reciente(obt_financieros, obt_operativos),
                "mercado": _obtenido(mercado),
                "valoracion": valoracion["fecha"]}
    filas = []
    for nombre, etiqueta, fuente, origen, campo in CATALOGO:
        if origen == "valoracion":
            ultimo = valoracion["ttm_hasta"]
            fuente = f"{fuente}, supuestos {valoracion['version_supuestos']}"
        elif origen == "mercado" and campo == "rf_10y":
            ultimo = (mercado.loc[mercado["rf_10y"].notna(), "month"].max()
                      if "rf_10y" in mercado.columns else None)
            ultimo = None if pd.isna(ultimo) else ultimo
        elif origen == "mercado":
            ultimo = _ultimo_periodo(mensual, "month", campo)
        else:
            ultimo = _ultimo_periodo(trimestral, "period", campo)
        filas.append({"kpi": nombre, "etiqueta": etiqueta, "fuente": fuente,
                      "ultimo_periodo": ultimo, "obtenido": obtenido[origen]})
    return filas


def construir_datos(financieros, operativos, mercado, valoracion: dict,
                    supuestos: dict, hoy: str, historico: list[dict] | None = None,
                    hitos: dict | None = None) -> dict:
    trimestral = kpis_trimestrales(financieros, operativos)
    mensual = serie_mensual(mercado, valoracion)
    return sin_nan({
        "generado": hoy,
        "valoracion": valoracion,
        "trimestral": trimestral,
        "mensual": mensual,
        "retorno_eur": retorno_eur(mercado),
        "simulador": datos_simulador(financieros, supuestos, valoracion),
        "trazabilidad": trazabilidad(financieros, operativos, mercado, valoracion,
                                     trimestral, mensual),
        "historico": historico or [],
        "hitos": hitos,
    })
