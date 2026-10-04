"""El almacenamiento desplegado se publica primero en la nota de entregas.

El Update Letter llega unas tres semanas despues: hasta entonces el dato sale
de la nota, y cuando llega la carta manda la carta.
"""
from pathlib import Path

import pytest

from src.cargar_update_letter import combinar_almacenamiento
from src.fetch_deliveries import parsear_almacenamiento, parsear_deliveries

FIXTURES = Path(__file__).parent / "fixtures"


def leer(nombre: str) -> str:
    return (FIXTURES / nombre).read_text(encoding="utf-8", errors="replace")


def test_la_nota_trae_el_almacenamiento_en_gwh():
    assert parsear_almacenamiento(leer("deliveries_tabla_2026Q2.htm")) == pytest.approx(13.5)


def test_parsear_deliveries_incluye_el_almacenamiento():
    datos = parsear_deliveries(leer("deliveries_tabla_2026Q2.htm"))
    assert datos["storage_deployed_gwh"] == pytest.approx(13.5)
    assert datos["deliveries_total"] == 480_126


def test_almacenamiento_en_mwh_se_pasa_a_gwh():
    html = "<p>we deployed 9,400 MWh of energy storage products.</p>"
    assert parsear_almacenamiento(html) == pytest.approx(9.4)


def test_etiquetas_html_en_medio_de_la_frase():
    html = "<p>and deployed&#160;<b>13.7</b> GWh of energy storage products</p>"
    assert parsear_almacenamiento(html) == pytest.approx(13.7)


def test_una_nota_sin_almacenamiento_da_none():
    assert parsear_almacenamiento(leer("deliveries_narrativo_2019Q1.htm")) is None
    assert "storage_deployed_gwh" not in parsear_deliveries(leer("deliveries_narrativo_2019Q1.htm"))


def test_sin_carta_vale_el_dato_de_la_nota():
    assert combinar_almacenamiento(None, 13.7) == (13.7, None)


def test_con_carta_manda_la_carta():
    assert combinar_almacenamiento(13.5, 13.5) == (13.5, None)
    # La carta puede dar mas precision que la nota: es el mismo dato.
    assert combinar_almacenamiento(13.52, 13.5) == (13.52, None)


def test_una_discrepancia_real_se_avisa_y_manda_la_carta():
    valor, aviso = combinar_almacenamiento(12.0, 13.5)
    assert valor == 12.0
    assert "12" in aviso and "13.5" in aviso


def test_sin_ninguno_de_los_dos_no_hay_dato():
    assert combinar_almacenamiento(None, None) == (None, None)
    assert combinar_almacenamiento(float("nan"), float("nan")) == (None, None)
