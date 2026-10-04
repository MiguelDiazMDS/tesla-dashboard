import pytest

from src.reverse_dcf import crecimiento_implicito, rejilla, valor_con_crecimiento
from src.sotp import AnioBase

BASE = AnioBase(
    ingresos={"automocion": 80e9, "energia": 12e9},
    margen_bruto={"automocion": 0.175, "energia": 0.30},
    id_sobre_ingresos=0.074, sga_sobre_ingresos=0.065,
)
BALANCE = {"caja": 15e9, "inversiones": 25e9, "deuda": 9e9, "acciones": 3.5e9}


def test_recupera_el_crecimiento_que_genero_el_precio(supuestos):
    esc, comun = supuestos["escenarios"]["base"], supuestos["comun"]
    precio = valor_con_crecimiento(0.12, BASE, esc, comun, 0.12, BALANCE)
    g = crecimiento_implicito(precio, BASE, esc, comun, 0.12, BALANCE)
    assert g == pytest.approx(0.12, abs=1e-3)


def test_un_precio_inalcanzable_devuelve_none(supuestos):
    esc, comun = supuestos["escenarios"]["base"], supuestos["comun"]
    assert crecimiento_implicito(1e9, BASE, esc, comun, 0.12, BALANCE) is None


def test_la_rejilla_tiene_una_fila_por_crecimiento(supuestos):
    esc, comun = supuestos["escenarios"]["base"], supuestos["comun"]
    r = rejilla(BASE, esc, comun, 0.12, BALANCE, [0.05, 0.10, 0.20], [0.15, 0.20])
    assert len(r) == 3 and all(len(fila) == 2 for fila in r)


def test_en_la_rejilla_mas_margen_da_mas_valor(supuestos):
    esc, comun = supuestos["escenarios"]["base"], supuestos["comun"]
    r = rejilla(BASE, esc, comun, 0.12, BALANCE, [0.10], [0.15, 0.20, 0.25])
    assert r[0][0] < r[0][1] < r[0][2]
