"""Datos sinteticos para los tests del motor de valoracion.

Cifras redondas pero de orden de magnitud realista. La rentabilidad de TSLA
lleva un ruido propio, de ciclo distinto al de 6 meses de SPY, para que la
beta no sea exactamente 1,5 y para que una ventana equivocada de la beta
(un mes de mas o de menos) de un resultado distinto al de la ventana
correcta. El ciclo del ruido es de 7 meses, no de 5: con un ciclo de 5, el
minimo comun multiplo con el ciclo de 6 de SPY es 30, que divide exactamente
a los 60 meses de `meses_beta`, y dos ventanas de 60 meses acaban
promediando el mismo conjunto de valores aunque empiecen en meses distintos
(la covarianza no depende del orden). Con un ciclo de 7 eso no ocurre. El
rf_10y varia cada mes por la misma razon: para que usar la fila equivocada
se note.
"""
import pandas as pd
import pytest

PERIODOS = ["2024Q3", "2024Q4", "2025Q1", "2025Q2",
            "2025Q3", "2025Q4", "2026Q1", "2026Q2"]
PUBLICACION = ["2024-10-24", "2025-01-29", "2025-04-23", "2025-07-24",
               "2025-10-23", "2026-01-29", "2026-04-23", "2026-07-23"]

TRIMESTRE = {
    "revenue_total": 23e9,
    "revenue_auto_segment": 20e9, "gross_profit_auto_segment": 3.5e9,
    "revenue_energy_segment": 3e9, "gross_profit_energy_segment": 0.9e9,
    "opex_rd": 1.7e9, "opex_sga": 1.5e9,
    "operating_income": 1.2e9, "net_income_gaap": 1.0e9,
    "ocf": 3.0e9, "capex": 2.0e9, "da": 1.4e9,
    "cash_and_investments": 15e9, "short_term_investments": 25e9,
    "total_debt": 9e9, "shares_outstanding": 3.5e9,
}

RENTABILIDADES_SPY = [0.02, -0.01, 0.03, -0.02, 0.01, 0.015]
RUIDO_TSLA = [0.01, -0.005, 0.002, 0.0, -0.007, 0.004, -0.003]


@pytest.fixture
def financieros():
    return pd.DataFrame([
        {"period": p, "filing_date": f, **TRIMESTRE}
        for p, f in zip(PERIODOS, PUBLICACION)
    ])


@pytest.fixture
def mercado():
    meses = pd.period_range("2021-01", "2026-09", freq="M").strftime("%Y-%m").tolist()
    spy, tsla = [400.0], [200.0]
    for i in range(1, len(meses)):
        r = RENTABILIDADES_SPY[i % len(RENTABILIDADES_SPY)]
        spy.append(spy[-1] * (1 + r))
        tsla.append(tsla[-1] * (1 + 1.5 * r + RUIDO_TSLA[i % len(RUIDO_TSLA)]))
    rf = [0.03 + 0.0002 * i for i in range(len(meses))]
    return pd.DataFrame({
        "month": meses, "price_close": tsla, "spy_close": spy,
        "rf_10y": rf, "eurusd": 1.15,
    })


def _unidad(g0, g1, margen, ventas_capital):
    return {"crecimiento_inicial": g0, "crecimiento_final": g1,
            "margen_bruto_final": margen, "ventas_sobre_capital": ventas_capital,
            "ajuste_wacc": 0.0}


@pytest.fixture
def supuestos():
    return {
        "version": "2026-09-22",
        "comun": {
            "horizonte_anios": 10, "prima_riesgo_mercado": 0.05,
            "meses_beta": 60, "coste_deuda_antes_impuestos": 0.06,
            "tipo_impositivo": 0.21, "crecimiento_terminal": 0.03,
            "roic_terminal": 0.15, "reparto_id_automocion": 0.85,
        },
        "escenarios": {
            "bear": {"automocion": _unidad(0.00, 0.02, 0.15, 1.8),
                     "energia": _unidad(0.15, 0.03, 0.22, 2.0),
                     "id_sobre_ingresos_final": 0.075,
                     "sga_sobre_ingresos_final": 0.065},
            "base": {"automocion": _unidad(0.08, 0.03, 0.19, 2.0),
                     "energia": _unidad(0.30, 0.05, 0.28, 2.5),
                     "id_sobre_ingresos_final": 0.06,
                     "sga_sobre_ingresos_final": 0.05},
            "bull": {"automocion": _unidad(0.15, 0.04, 0.23, 2.2),
                     "energia": _unidad(0.45, 0.06, 0.32, 3.0),
                     "id_sobre_ingresos_final": 0.05,
                     "sga_sobre_ingresos_final": 0.045},
        },
    }
