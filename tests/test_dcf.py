import pytest

from src.dcf import nopat, trayectoria, valor_presente, valor_terminal


def test_trayectoria_interpola_de_inicial_a_final():
    assert trayectoria(0.10, 0.01, 4) == pytest.approx([0.10, 0.07, 0.04, 0.01])


def test_trayectoria_de_un_anio_es_el_valor_final():
    assert trayectoria(0.10, 0.03, 1) == [0.03]


def test_trayectoria_rechaza_un_horizonte_nulo():
    with pytest.raises(ValueError):
        trayectoria(0.1, 0.1, 0)


def test_valor_presente_de_una_anualidad_conocida():
    """100 al final de cada uno de tres anios al 10%: 248,685."""
    assert valor_presente([100, 100, 100], 0.10) == pytest.approx(248.6852, rel=1e-6)


def test_valor_terminal_de_gordon_con_reinversion():
    """NOPAT 100, g 3%, ROIC 15%: se reinvierte el 20%. 80 / (10% - 3%)."""
    assert valor_terminal(100, 0.10, 0.03, 0.15) == pytest.approx(1142.857, rel=1e-6)


def test_valor_terminal_exige_tasa_mayor_que_crecimiento():
    with pytest.raises(ValueError, match="superar"):
        valor_terminal(100, 0.03, 0.03, 0.15)


def test_valor_terminal_exige_roic_positivo():
    with pytest.raises(ValueError, match="ROIC"):
        valor_terminal(100, 0.10, 0.03, 0.0)


def test_con_nopat_negativo_la_perdida_se_perpetua_entera():
    """Una unidad en perdidas no reinvierte para crecer: no hay credito."""
    assert valor_terminal(-100, 0.10, 0.03, 0.15) == pytest.approx(-100 / 0.07)


def test_valor_terminal_exige_roic_mayor_que_crecimiento():
    with pytest.raises(ValueError, match="ROIC"):
        valor_terminal(100, 0.10, 0.05, 0.02)


def test_nopat_aplica_impuestos_solo_sobre_beneficio():
    assert nopat(100, 0.21) == pytest.approx(79)
    assert nopat(-100, 0.21) == -100
