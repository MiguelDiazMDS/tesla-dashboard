import pytest

from src.wacc import beta, coste_capital_propio, rentabilidades, wacc


def test_rentabilidades_de_una_serie_de_precios():
    assert rentabilidades([100, 110, 99]) == pytest.approx([0.10, -0.10])


def test_la_beta_del_mercado_consigo_mismo_es_uno():
    mercado = [0.02, -0.01, 0.03, -0.02, 0.01, 0.015] * 3
    assert beta(mercado, mercado) == pytest.approx(1.0)


def test_la_beta_de_un_activo_que_amplifica_el_mercado():
    mercado = [0.02, -0.01, 0.03, -0.02, 0.01, 0.015] * 3
    assert beta([1.5 * r for r in mercado], mercado) == pytest.approx(1.5)


def test_la_beta_exige_suficientes_observaciones():
    with pytest.raises(ValueError, match="12"):
        beta([0.1] * 5, [0.1] * 5)


def test_la_beta_exige_series_de_igual_longitud():
    with pytest.raises(ValueError):
        beta([0.01] * 20, [0.01] * 19)


def test_capm():
    """4,96% + 2,0 x 5% = 14,96%."""
    assert coste_capital_propio(0.0496, 2.0, 0.05) == pytest.approx(0.1496)


def test_wacc_pondera_por_valor_de_mercado():
    """90 de acciones al 12% y 10 de deuda al 6% antes de un 21% de impuestos."""
    assert wacc(0.12, 0.06, 0.21, 90, 10) == pytest.approx(0.9 * 0.12 + 0.1 * 0.06 * 0.79)


def test_sin_deuda_el_wacc_es_el_coste_de_las_acciones():
    assert wacc(0.12, 0.06, 0.21, 100, 0) == pytest.approx(0.12)
