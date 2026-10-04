import copy

import pytest

from src.dcf import nopat, valor_presente, valor_terminal
from src.sotp import (
    AnioBase, anio_base, proyectar, suma_unidades, valor_por_accion,
)

BASE = AnioBase(
    ingresos={"automocion": 80e9, "energia": 12e9},
    margen_bruto={"automocion": 0.175, "energia": 0.30},
    id_sobre_ingresos=0.074, sga_sobre_ingresos=0.065,
)


def test_anio_base_a_partir_del_ttm():
    ttm = {"revenue_auto_segment": 80e9, "gross_profit_auto_segment": 14e9,
           "revenue_energy_segment": 12e9, "gross_profit_energy_segment": 3.6e9,
           "revenue_total": 92e9, "opex_rd": 6.8e9, "opex_sga": 6.0e9}
    base = anio_base(ttm)
    assert base.margen_bruto["automocion"] == pytest.approx(0.175)
    assert base.margen_bruto["energia"] == pytest.approx(0.30)
    assert base.id_sobre_ingresos == pytest.approx(6.8 / 92)


def test_los_ingresos_crecen_segun_la_trayectoria(supuestos):
    esc = supuestos["escenarios"]["base"]
    unidades = proyectar(BASE, esc, supuestos["comun"], 0.12)
    assert unidades["automocion"].ingresos[0] == pytest.approx(80e9 * 1.08)
    assert len(unidades["energia"].ingresos) == 10


def test_la_suma_de_partes_coincide_con_el_dcf_consolidado(supuestos):
    """Requisito del spec: con el mismo coste de capital y beneficio en ambas
    unidades, valorar por separado y sumar da lo mismo que valorar el conjunto."""
    comun = supuestos["comun"]
    w, g, t = 0.12, comun["crecimiento_terminal"], comun["tipo_impositivo"]
    u = proyectar(BASE, supuestos["escenarios"]["base"], comun, w)
    a, e = u["automocion"], u["energia"]
    assert all(x > 0 for x in a.ebit + e.ebit)
    flujos = [x + y for x, y in zip(a.fcff, e.fcff)]
    nopat_siguiente = (nopat(a.ebit[-1], t) + nopat(e.ebit[-1], t)) * (1 + g)
    consolidado = (valor_presente(flujos, w)
                   + valor_terminal(nopat_siguiente, w, g, comun["roic_terminal"]) / (1 + w) ** 10)
    assert suma_unidades(u) == pytest.approx(consolidado, rel=1e-9)


def test_el_reparto_de_id_no_cambia_el_total_si_ambas_unidades_ganan(supuestos):
    """Solo mueve valor de una unidad a otra. Afectaria al total si las
    unidades tuvieran distinto coste de capital o alguna tuviera perdidas."""
    esc, comun = supuestos["escenarios"]["base"], supuestos["comun"]
    con_70 = proyectar(BASE, esc, comun, 0.12, reparto_id=0.70)
    con_100 = proyectar(BASE, esc, comun, 0.12, reparto_id=1.00)
    assert suma_unidades(con_70) == pytest.approx(suma_unidades(con_100), rel=1e-9)
    assert con_100["automocion"].valor < con_70["automocion"].valor


def test_un_ajuste_de_wacc_reduce_el_valor_de_la_unidad(supuestos):
    esc = copy.deepcopy(supuestos["escenarios"]["base"])
    sin = proyectar(BASE, esc, supuestos["comun"], 0.12)["energia"].valor
    esc["energia"]["ajuste_wacc"] = 0.02
    con = proyectar(BASE, esc, supuestos["comun"], 0.12)["energia"].valor
    assert con < sin


def test_mejores_supuestos_dan_mas_valor(supuestos):
    comun, esc = supuestos["comun"], supuestos["escenarios"]
    valores = [suma_unidades(proyectar(BASE, esc[n], comun, 0.12))
               for n in ("bear", "base", "bull")]
    assert valores[0] < valores[1] < valores[2]


def test_valor_por_accion_suma_liquidez_y_resta_deuda():
    assert valor_por_accion(100.0, caja=15.0, inversiones=25.0, deuda=10.0,
                            acciones=2.0) == pytest.approx(65.0)


def test_proyeccion_calculada_a_mano():
    """Dos anios, cifras redondas. Calculado aparte, sin usar este codigo."""
    base = AnioBase(ingresos={"automocion": 100.0, "energia": 50.0},
                    margen_bruto={"automocion": 0.20, "energia": 0.30},
                    id_sobre_ingresos=0.10, sga_sobre_ingresos=0.05)
    comun = {"horizonte_anios": 2, "tipo_impositivo": 0.25,
             "crecimiento_terminal": 0.02, "roic_terminal": 0.10,
             "reparto_id_automocion": 0.8}
    unidad = lambda g, m, vc: {"crecimiento_inicial": g, "crecimiento_final": g,
                               "margen_bruto_final": m, "ventas_sobre_capital": vc,
                               "ajuste_wacc": 0.0}
    escenario = {"automocion": unidad(0.10, 0.20, 2.0),
                 "energia": unidad(0.20, 0.30, 1.0),
                 "id_sobre_ingresos_final": 0.10, "sga_sobre_ingresos_final": 0.05}
    u = proyectar(base, escenario, comun, 0.10)
    a, e = u["automocion"], u["energia"]
    assert a.ingresos == pytest.approx([110.0, 121.0])
    assert e.ingresos == pytest.approx([60.0, 72.0])
    # Automocion anio 1: margen 22 - I+D 0,10*170*0,8 = 13,6 - SG&A 5,5
    assert a.ebit == pytest.approx([2.9, 2.71])
    # NOPAT 2,175 - reinversion (110-100)/2 = 5
    assert a.fcff == pytest.approx([-2.825, -3.4675])
    assert e.ebit == pytest.approx([11.6, 14.14])
    assert e.fcff == pytest.approx([-1.3, -1.395])
    assert a.valor == pytest.approx(11.699587, rel=1e-6)
    assert e.valor == pytest.approx(87.06281, rel=1e-6)
