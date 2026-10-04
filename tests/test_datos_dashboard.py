import json

import numpy as np
import pandas as pd
import pytest

from src.datos_dashboard import _num, kpis_trimestrales

FIN = pd.DataFrame([{
    "period": "2026Q2", "revenue_total": 28e9, "revenue_auto_segment": 25e9,
    "gross_profit_auto_segment": 4e9, "cogs_auto_segment": 21e9,
    "revenue_energy_segment": 3e9, "gross_profit_energy_segment": 0.6e9,
    "revenue_auto_sales": 20e9, "revenue_reg_credits": 0.4e9,
    "operating_income": 1.2e9, "ocf": 3e9, "capex": 2e9,
}])
OPE = pd.DataFrame([{
    "period": "2026Q2", "deliveries_total": 400_000, "production_total": 420_000,
    "etiqueta_volumen": "Model 3/Y", "etiqueta_nicho": "Other Models",
}])


def test_kpis_derivados_calculados_a_mano():
    fila = kpis_trimestrales(FIN, OPE)[0]
    assert fila["asp_implicito"] == pytest.approx(50_000)
    assert fila["coste_por_vehiculo"] == pytest.approx(52_500)
    assert fila["ratio_produccion_entregas"] == pytest.approx(1.05)
    assert fila["margen_auto_sin_creditos"] == pytest.approx(3.6 / 24.6)
    assert fila["margen_energia"] == pytest.approx(0.2)
    assert fila["margen_operativo"] == pytest.approx(1.2 / 28)
    assert fila["fcf"] == pytest.approx(1e9)


def test_un_operando_ausente_da_null_no_cero():
    fin = FIN.assign(revenue_reg_credits=None)
    fila = kpis_trimestrales(fin, OPE)[0]
    assert fila["margen_auto_sin_creditos"] is None
    assert fila["asp_implicito"] == pytest.approx(50_000)


def test_un_operando_nan_como_llega_del_csv_da_null():
    fin = FIN.assign(revenue_auto_sales=float("nan"))
    fila = kpis_trimestrales(fin, OPE)[0]
    assert fila["asp_implicito"] is None


def test_denominador_cero_da_null():
    ope = OPE.assign(deliveries_total=0)
    fila = kpis_trimestrales(FIN, ope)[0]
    assert fila["asp_implicito"] is None


def test_num_casos():
    assert _num(float("nan")) is None
    assert _num(float("inf")) is None
    assert _num("abc") is None
    assert _num(None) is None
    assert _num(pd.NA) is None
    assert _num(np.int64(3)) == 3.0


def test_conserva_campos_originales_y_etiquetas():
    fila = kpis_trimestrales(FIN, OPE)[0]
    assert fila["period"] == "2026Q2"
    assert fila["deliveries_total"] == 400_000
    assert fila["etiqueta_volumen"] == "Model 3/Y"


def test_campos_que_faltan_en_los_ficheros_son_null():
    fila = kpis_trimestrales(FIN, OPE)[0]
    assert fila["fsd_subscriptions"] is None
    json.dumps(kpis_trimestrales(FIN, OPE), allow_nan=False)


from src.datos_dashboard import CATALOGO


def test_los_campos_testigo_del_catalogo_estan_en_las_filas_trimestrales():
    fila = kpis_trimestrales(FIN, OPE)[0]
    for _, _, _, origen, campo in CATALOGO:
        if origen in ("financieros", "operativos", "kpi"):
            assert campo in fila, f"{campo} (origen {origen}) no esta en la fila"


from src.datos_dashboard import retorno_eur

MERCADO_EUR = pd.DataFrame({
    "month": ["2025-09", "2025-12", "2026-09"],
    "price_close": [200.0, 250.0, 300.0],
    "eurusd": [1.10, 1.15, 1.20],
})


def test_retorno_de_los_ultimos_12_meses_calculado_a_mano():
    r = retorno_eur(MERCADO_EUR)["ultimos_12_meses"]
    assert r["desde"] == "2025-09" and r["hasta"] == "2026-09"
    assert r["usd"] == pytest.approx(0.5)
    assert r["eur"] == pytest.approx(0.375)   # 250 / 181,818 - 1
    assert r["efecto_divisa"] == pytest.approx(1.10 / 1.20 - 1)
    assert 1 + r["eur"] == pytest.approx((1 + r["usd"]) * (1 + r["efecto_divisa"]))


def test_retorno_en_lo_que_va_de_anio_parte_de_diciembre():
    r = retorno_eur(MERCADO_EUR)["en_el_anio"]
    assert r["desde"] == "2025-12"
    assert r["usd"] == pytest.approx(0.2)
    assert r["eur"] == pytest.approx(0.15)
    assert r["efecto_divisa"] == pytest.approx(1.15 / 1.20 - 1)


def test_sin_el_mes_inicial_el_periodo_es_null():
    assert retorno_eur(MERCADO_EUR)["desde_2019"] is None


from src.datos_dashboard import construir_datos, datos_simulador, serie_mensual
from src.valorar import calcular

OPE_SINT = pd.DataFrame([{"period": p, "deliveries_total": 400_000,
                          "production_total": 410_000, "source": "8-K",
                          "retrieved_at": "2026-09-23"}
                         for p in ("2025Q3", "2025Q4", "2026Q1", "2026Q2")])


@pytest.fixture
def valoracion(financieros, mercado, supuestos):
    return calcular(financieros, mercado, supuestos, "abcd", "2026-09-22")


def test_datos_del_simulador_parten_de_la_valoracion(financieros, supuestos, valoracion):
    s = datos_simulador(financieros, supuestos, valoracion)
    assert set(s) == {"base", "balance", "wacc", "precio", "supuestos", "anio_cero"}
    assert s["wacc"] == valoracion["coste_capital"]["wacc"]
    assert s["precio"] == valoracion["precio"]
    assert set(s["base"]) == {"ingresos", "margen_bruto", "id_sobre_ingresos",
                              "sga_sobre_ingresos"}


def test_serie_mensual_une_precio_y_multiplos(mercado, valoracion):
    serie = serie_mensual(mercado, valoracion)
    assert len(serie) == len(mercado)
    ultimo = serie[-1]
    assert ultimo["ev_ventas"] == valoracion["multiplos"]["ev_ventas"]["actual"]
    assert serie[0]["ev_ventas"] is None     # antes de haber cuatro trimestres


def test_construir_datos_cumple_el_contrato(financieros, mercado, supuestos, valoracion):
    datos = construir_datos(financieros, OPE_SINT, mercado, valoracion, supuestos,
                            "2026-09-23", historico=[{"mes": "2026-09", "precio": 1.0}])
    assert set(datos) == {"generado", "valoracion", "trimestral", "mensual",
                          "retorno_eur", "simulador", "trazabilidad", "historico", "hitos"}
    assert datos["hitos"] is None
    assert datos["historico"] == [{"mes": "2026-09", "precio": 1.0}]
    json.dumps(datos, allow_nan=False)
    for kpi in datos["trazabilidad"]:
        assert kpi["etiqueta"] in ("R", "D", "E")
        assert kpi["fuente"]


def test_construir_datos_sin_historico_da_lista_vacia(financieros, mercado, supuestos,
                                                       valoracion):
    datos = construir_datos(financieros, OPE_SINT, mercado, valoracion, supuestos,
                            "2026-09-23")
    assert datos["historico"] == []


def test_construir_datos_incluye_los_hitos(financieros, mercado, supuestos, valoracion):
    hitos = {"version": "2026-09-23", "hitos": []}
    datos = construir_datos(financieros, OPE_SINT, mercado, valoracion, supuestos,
                            "2026-09-23", hitos=hitos)
    assert datos["hitos"] == hitos


def test_datos_simulador_exige_que_el_ttm_hasta_coincida(financieros, supuestos, valoracion):
    alterada = {**valoracion, "ttm_hasta": "2020Q1"}
    with pytest.raises(ValueError):
        datos_simulador(financieros, supuestos, alterada)


from src.datos_dashboard import trazabilidad


def test_trazabilidad_ultimo_periodo_con_ope_sint(financieros, mercado, valoracion):
    trimestral = kpis_trimestrales(financieros, OPE_SINT)
    mensual = serie_mensual(mercado, valoracion)
    filas = trazabilidad(financieros, OPE_SINT, mercado, valoracion, trimestral, mensual)
    por_kpi = {f["kpi"]: f for f in filas}
    assert por_kpi["Entregas y producción"]["ultimo_periodo"] == "2026Q2"
    assert por_kpi["Días de inventario"]["ultimo_periodo"] is None


from src.datos_dashboard import anio_cero


def test_anio_cero_calculado_a_mano(financieros):
    # Fixture: ocf 3e9 y capex 2e9 por trimestre; automocion 20e9 y energia 3e9.
    a = anio_cero(financieros, "2026Q2")
    assert a["hasta"] == "2026Q2"
    assert a["ocf"] == pytest.approx(12e9) and a["capex"] == pytest.approx(8e9)
    assert a["fcf_reportado"] == pytest.approx(4e9)
    assert a["ingresos_previos"] == {"automocion": pytest.approx(80e9),
                                     "energia": pytest.approx(12e9)}


def test_anio_cero_sin_trimestres_previos(financieros):
    assert anio_cero(financieros, "2025Q2")["ingresos_previos"] is None
