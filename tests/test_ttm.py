import pytest

from src.ttm import ttm_en


def test_sin_cuatro_trimestres_publicados_no_hay_ttm(financieros):
    assert ttm_en(financieros, "2025-04-30") is None


def test_el_dia_de_publicacion_del_cuarto_trimestre_ya_hay_ttm(financieros):
    t = ttm_en(financieros, "2025-07-24")
    assert t["periodo"] == "2025Q2"
    assert t["revenue_total"] == pytest.approx(4 * 23e9)


def test_el_dia_anterior_todavia_no(financieros):
    """Point-in-time: lo que no estaba publicado no se usa."""
    assert ttm_en(financieros, "2025-07-23") is None


def test_los_saldos_son_los_del_ultimo_trimestre(financieros):
    financieros.loc[financieros.period == "2026Q2", "total_debt"] = 12e9
    t = ttm_en(financieros, "2026-09-30")
    assert t["periodo"] == "2026Q2"
    assert t["total_debt"] == 12e9


def test_trimestres_no_consecutivos_no_dan_ttm(financieros):
    sin_uno = financieros[financieros.period != "2026Q1"]
    assert ttm_en(sin_uno, "2026-09-30") is None


def test_un_dato_ausente_no_da_ttm(financieros):
    """Mejor un hueco que un multiplo calculado con tres trimestres."""
    financieros.loc[financieros.period == "2026Q1", "da"] = None
    assert ttm_en(financieros, "2026-09-30") is None


def test_campos_a_medida(financieros):
    t = ttm_en(financieros, "2026-09-30", flujos=("opex_rd",), saldos=())
    assert t == {"periodo": "2026Q2", "opex_rd": pytest.approx(4 * 1.7e9)}
