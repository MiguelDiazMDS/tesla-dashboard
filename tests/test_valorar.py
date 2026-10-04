import json

import pandas as pd
import pytest

from src.valorar import calcular, comprobar_frescura, resumen


@pytest.fixture
def resultado(financieros, mercado, supuestos):
    return calcular(financieros, mercado, supuestos, "abcd", "2026-09-22")


def test_el_wacc_sigue_su_formula(resultado, mercado):
    cc = resultado["coste_capital"]
    e = resultado["capitalizacion"]
    d = 9e9
    esperado = e / (e + d) * cc["coste_acciones"] + d / (e + d) * 0.06 * (1 - 0.21)
    assert cc["wacc"] == pytest.approx(esperado)


def test_el_tipo_sin_riesgo_es_el_del_ultimo_mes(resultado, mercado):
    assert resultado["coste_capital"]["tipo_sin_riesgo"] == pytest.approx(
        mercado["rf_10y"].iloc[-1])


def test_la_beta_usa_los_60_ultimos_meses_completos(resultado, mercado):
    """El mes en curso esta a medias: no entra en la beta."""
    from src.wacc import beta, rentabilidades
    completos = mercado[mercado["month"] < "2026-09"].tail(61)
    esperado = beta(rentabilidades(completos["price_close"].tolist()),
                    rentabilidades(completos["spy_close"].tolist()))
    assert resultado["coste_capital"]["beta"] == pytest.approx(esperado)
    assert resultado["coste_capital"]["beta"] != pytest.approx(1.5)


def test_los_escenarios_se_ordenan(resultado):
    e = resultado["escenarios"]
    assert (e["bear"]["valor_por_accion"] < e["base"]["valor_por_accion"]
            < e["bull"]["valor_por_accion"])


def test_la_opcionalidad_implicita_es_capitalizacion_menos_valor_base(resultado):
    assert resultado["opcionalidad_implicita"] == pytest.approx(
        resultado["capitalizacion"] - resultado["escenarios"]["base"]["valor_acciones"])


def test_el_precio_frente_al_valor(resultado):
    base = resultado["escenarios"]["base"]
    assert base["precio_frente_a_valor"] == pytest.approx(
        resultado["precio"] / base["valor_por_accion"] - 1)


def test_la_sensibilidad_al_reparto_mueve_el_valor_entre_unidades(resultado):
    s = resultado["sensibilidad"]["reparto_id_automocion"]
    assert s["100%"]["automocion"] < s["70%"]["automocion"]
    assert s["100%"]["energia"] > s["70%"]["energia"]


def test_queda_rastro_de_la_version_y_la_huella(resultado):
    assert resultado["version_supuestos"] == "2026-09-22"
    assert resultado["huella"] == "abcd"


def test_el_resultado_es_json_valido_sin_nan(resultado):
    json.dumps(resultado, allow_nan=False)


def test_el_resumen_nombra_lo_esencial(resultado):
    texto = resumen(resultado)
    for fragmento in ("bear", "base", "bull", "WACC", "Opcionalidad", "EV/Ventas"):
        assert fragmento in texto


def test_el_resultado_lleva_el_mes_del_precio(resultado, mercado):
    assert resultado["mes_precio"] == mercado["month"].iloc[-1]


def test_comprobar_frescura_exige_el_precio_del_mes_en_curso():
    mercado = pd.DataFrame({"month": ["2026-07", "2026-08"]})
    with pytest.raises(ValueError, match="2026-08"):
        comprobar_frescura(mercado, "2026-09-22")


def test_base_y_balance_es_lo_que_usa_la_valoracion(financieros, mercado, supuestos):
    from src.sotp import proyectar, suma_unidades, valor_por_accion
    from src.valorar import base_y_balance, calcular
    r = calcular(financieros, mercado, supuestos, "abcd", "2026-09-22")
    base, balance, ttm_hasta = base_y_balance(financieros, "2026-09-22")
    assert ttm_hasta == r["ttm_hasta"]
    unidades = proyectar(base, supuestos["escenarios"]["base"], supuestos["comun"],
                         r["coste_capital"]["wacc"])
    assert valor_por_accion(suma_unidades(unidades), **balance) == pytest.approx(
        r["escenarios"]["base"]["valor_por_accion"], rel=1e-12)


def test_comprobar_frescura_pasa_con_el_precio_al_dia():
    mercado = pd.DataFrame({"month": ["2026-08", "2026-09"]})
    comprobar_frescura(mercado, "2026-09-22")


def test_el_resultado_lleva_el_horizonte(resultado, supuestos):
    assert resultado["horizonte_anios"] == supuestos["comun"]["horizonte_anios"]


def test_motivo_cuando_el_precio_ya_supera_al_valor_bajista(financieros, mercado, supuestos):
    """Precio tan bajo que ni cayendo un 10% al anio se alcanza: infravalorada."""
    barato = mercado.copy()
    barato.loc[barato.index[-1], "price_close"] = 5.0
    r = calcular(financieros, barato, supuestos, "abcd", "2026-09-22")
    assert r["crecimiento_implicito"] is None
    assert r["crecimiento_implicito_motivo"] == (
        "el precio esta por debajo del valor incluso con los ingresos "
        "cayendo un 10% anual")


def test_motivo_cuando_no_se_alcanza_ni_con_crecimiento_del_80(financieros, mercado, supuestos):
    caro = mercado.copy()
    caro.loc[caro.index[-1], "price_close"] = 5000.0
    r = calcular(financieros, caro, supuestos, "abcd", "2026-09-22")
    assert r["crecimiento_implicito"] is None
    assert r["crecimiento_implicito_motivo"] == (
        "no se alcanza el precio con crecimientos de hasta el 80% anual")


def test_el_motivo_es_nulo_cuando_si_hay_crecimiento_implicito(resultado):
    assert resultado["crecimiento_implicito"] is not None
    assert resultado["crecimiento_implicito_motivo"] is None


def test_el_mensaje_de_ttm_ausente_menciona_los_datos_necesarios(mercado, supuestos):
    """Un unico trimestre no llega a los cuatro que exige el TTM."""
    incompletos = pd.DataFrame([{
        "period": "2026Q2", "filing_date": "2026-07-23",
        "revenue_total": 23e9, "revenue_auto_segment": 20e9,
        "gross_profit_auto_segment": 3.5e9, "revenue_energy_segment": 3e9,
        "gross_profit_energy_segment": 0.9e9, "opex_rd": 1.7e9, "opex_sga": 1.5e9,
        "cash_and_investments": 15e9, "short_term_investments": 25e9,
        "total_debt": 9e9, "shares_outstanding": 3.5e9,
    }])
    with pytest.raises(ValueError, match="con todos los datos necesarios"):
        calcular(incompletos, mercado, supuestos, "abcd", "2026-09-22")


def test_la_congelacion_lee_el_resultado_real_del_motor(resultado):
    """Contrato entre calcular y comprobar_congelacion: la congelacion debe
    reconocer la version y la huella tal como las escribe el propio motor, no
    un diccionario de prueba escrito a mano."""
    from src.supuestos import SupuestosInvalidos, comprobar_congelacion
    with pytest.raises(SupuestosInvalidos, match="version"):
        comprobar_congelacion(resultado["version_supuestos"], "otra huella", resultado)
    comprobar_congelacion(resultado["version_supuestos"], resultado["huella"], resultado)
    comprobar_congelacion("2026-10-23", "otra huella", resultado)
