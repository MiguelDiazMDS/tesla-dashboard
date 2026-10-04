import pandas as pd
import pytest

from src.coherence import (
    IncoherenciaDatos, comprobar_deliveries, comprobar_geografia,
    comprobar_lineas_automocion, comprobar_lineas_energia,
    comprobar_margen_por_segmento, comprobar_segmentos, revisar_financieros,
)

# Cifras reales de Q2 2026, en dolares. Los tests documentan ademas de comprobar.
Q2_2026 = {
    "period": "2026Q2",
    "revenue_total": 28_236e6,
    "gross_profit_total": 4_751e6,
    "revenue_auto_segment": 25_097e6,
    "cogs_auto_segment": 20_986e6,
    "gross_profit_auto_segment": 4_111e6,
    "revenue_energy_segment": 3_139e6,
    "cogs_energy_segment": 2_499e6,
    "gross_profit_energy_segment": 640e6,
    "revenue_auto_sales": 20_006e6,
    "revenue_reg_credits": 146e6,
    "revenue_auto_leasing": 364e6,
    "revenue_services": 4_581e6,
    "revenue_energy_sales": 2_998e6,
    "revenue_energy_leasing": 141e6,
    "revenue_us": 13_208e6,
    "revenue_china": 4_675e6,
    "revenue_other": 10_353e6,
}


def marco(**cambios):
    return pd.DataFrame([Q2_2026 | cambios])


def test_los_dos_segmentos_suman_el_consolidado():
    assert comprobar_segmentos(marco()) == 1


def test_segmentos_descuadrados_lanzan_error():
    with pytest.raises(IncoherenciaDatos, match="2026Q2"):
        comprobar_segmentos(marco(revenue_energy_segment=9_999e6))


def test_una_fila_incompleta_se_omite_sin_error():
    """Un trimestre todavia sin cargar no es una incoherencia."""
    assert comprobar_segmentos(marco(revenue_auto_segment=None)) == 0


def test_las_lineas_de_automocion_suman_su_segmento():
    assert comprobar_lineas_automocion(marco()) == 1


def test_lineas_de_automocion_descuadradas_lanzan_error():
    with pytest.raises(IncoherenciaDatos, match="2026Q2"):
        comprobar_lineas_automocion(marco(revenue_services=9_999e6))


def test_las_lineas_de_energia_suman_su_segmento():
    assert comprobar_lineas_energia(marco()) == 1


def test_las_regiones_suman_el_consolidado():
    assert comprobar_geografia(marco()) == 1


def test_regiones_descuadradas_lanzan_error():
    with pytest.raises(IncoherenciaDatos, match="2026Q2"):
        comprobar_geografia(marco(revenue_china=9_999e6))


def test_ingresos_menos_coste_da_el_margen_en_cada_segmento():
    assert comprobar_margen_por_segmento(marco()) == 2


def test_un_margen_inconsistente_lanza_error():
    with pytest.raises(IncoherenciaDatos, match="2026Q2"):
        comprobar_margen_por_segmento(marco(cogs_auto_segment=1e6))


def test_falta_de_columna_se_avisa_en_vez_de_pasar_por_alto():
    """Si el fichero no tiene la columna hay que enterarse, no dar por bueno."""
    with pytest.raises(IncoherenciaDatos, match="faltan columnas"):
        comprobar_segmentos(marco().drop(columns=["revenue_auto_segment"]))


def test_revisar_financieros_ejecuta_las_seis_comprobaciones():
    resultado = revisar_financieros(marco())
    assert len(resultado) == 6
    assert all(v > 0 for v in resultado.values())


# --- Deliveries -------------------------------------------------------------

def test_deliveries_por_grupo_suman_el_total():
    df = pd.DataFrame([{
        "period": "2026Q2", "deliveries_total": 480_126,
        "deliveries_volumen": 467_762, "deliveries_nicho": 12_364,
    }])
    assert comprobar_deliveries(df) == 1


def test_deliveries_descuadrados_lanzan_error():
    df = pd.DataFrame([{
        "period": "2026Q2", "deliveries_total": 480_126,
        "deliveries_volumen": 467_762, "deliveries_nicho": 999,
    }])
    with pytest.raises(IncoherenciaDatos, match="2026Q2"):
        comprobar_deliveries(df)
