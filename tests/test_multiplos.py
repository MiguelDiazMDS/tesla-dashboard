import pandas as pd
import pytest

from src.multiplos import fin_de_mes, multiplos_mensuales, percentil_actual


def test_fin_de_mes_respeta_los_bisiestos():
    assert fin_de_mes("2024-02") == "2024-02-29"
    assert fin_de_mes("2025-02") == "2025-02-28"


def test_solo_hay_multiplos_desde_que_hay_cuatro_trimestres_publicados(financieros, mercado):
    serie = multiplos_mensuales(financieros, mercado)
    assert serie["month"].iloc[0] == "2025-07"


def test_ev_ventas_con_liquidez_completa(financieros, mercado):
    """El EV descuenta caja e inversiones a corto: omitirlas lo infla."""
    serie = multiplos_mensuales(financieros, mercado)
    precio = mercado["price_close"].iloc[-1]
    cap = precio * 3.5e9
    ev = cap + 9e9 - 15e9 - 25e9
    assert serie["ev_ventas"].iloc[-1] == pytest.approx(ev / (4 * 23e9))
    assert serie["ev_ebitda"].iloc[-1] == pytest.approx(ev / (4 * (1.2e9 + 1.4e9)))
    assert serie["p_fcf"].iloc[-1] == pytest.approx(cap / (4 * (3.0e9 - 2.0e9)))


def test_sin_beneficio_el_per_no_esta_definido(financieros, mercado):
    financieros["net_income_gaap"] = -1e9
    serie = multiplos_mensuales(financieros, mercado)
    assert serie["per"].isna().all()


def test_percentil_del_ultimo_valor():
    assert percentil_actual(pd.Series([1.0, 2.0, 3.0, 4.0])) == 1.0
    assert percentil_actual(pd.Series([4.0, 3.0, 2.0, 1.0])) == 0.25


def test_percentil_ignora_huecos_y_devuelve_none_si_el_ultimo_falta():
    assert percentil_actual(pd.Series([1.0, None, 3.0])) == 1.0
    assert percentil_actual(pd.Series([1.0, 2.0, None])) is None
