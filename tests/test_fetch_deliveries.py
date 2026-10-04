from pathlib import Path

import pytest

from src.cargar_deliveries import periodo_reportado
from src.fetch_deliveries import (
    TablaDeliveriesNoEncontrada, localizar_exhibit, parsear_deliveries,
)

FIXTURES = Path(__file__).parent / "fixtures"


def leer(nombre):
    return (FIXTURES / nombre).read_text(encoding="utf-8", errors="replace")


# --- Identificacion de la nota ---------------------------------------------

def test_periodo_reportado_asocia_el_mes_con_su_trimestre():
    """La nota de enero reporta el cuarto trimestre del anio anterior."""
    assert periodo_reportado("2026-01-02") == "2025Q4"
    assert periodo_reportado("2026-04-02") == "2026Q1"
    assert periodo_reportado("2026-07-02") == "2026Q2"
    assert periodo_reportado("2026-10-02") == "2026Q3"


def test_periodo_reportado_descarta_el_8k_de_resultados():
    """Tres semanas mas tarde llega el 8-K de resultados, que no es la nota."""
    assert periodo_reportado("2026-07-23") is None


def test_periodo_reportado_descarta_un_mes_cualquiera():
    assert periodo_reportado("2026-05-05") is None


def test_localizar_exhibit_encuentra_el_99_1():
    submission = "<TYPE>8-K\n<FILENAME>tsla-8k.htm\n<TYPE>EX-99.1\n<FILENAME>ex991.htm\n"
    assert localizar_exhibit(submission) == "ex991.htm"


def test_localizar_exhibit_devuelve_none_si_no_lo_hay():
    assert localizar_exhibit("<TYPE>8-K\n<FILENAME>tsla-8k.htm\n") is None


# --- Nota moderna, con tabla ------------------------------------------------

def test_parsear_la_nota_en_tabla():
    """Cifras reales de Q2 2026."""
    datos = parsear_deliveries(leer("deliveries_tabla_2026Q2.htm"))
    assert datos["deliveries_total"] == 480_126
    assert datos["deliveries_volumen"] == 467_762
    assert datos["deliveries_nicho"] == 12_364
    assert datos["production_total"] == 451_758


def test_la_nota_en_tabla_guarda_la_etiqueta_literal():
    """Hay que poder auditar contra el documento original."""
    datos = parsear_deliveries(leer("deliveries_tabla_2026Q2.htm"))
    assert datos["etiqueta_volumen"] == "Model 3/Y"
    assert datos["etiqueta_nicho"] == "Other Models"


def test_no_confunde_la_columna_de_arrendamiento_con_las_entregas():
    """La nota trae una columna de porcentaje en arrendamiento operativo."""
    datos = parsear_deliveries(leer("deliveries_tabla_2026Q2.htm"))
    assert datos["deliveries_volumen"] + datos["deliveries_nicho"] == datos["deliveries_total"]


# --- Nota antigua, en prosa -------------------------------------------------

def test_parsear_la_nota_en_prosa():
    """La nota de Q1 2019 no lleva tabla: da las cifras en texto."""
    datos = parsear_deliveries(leer("deliveries_narrativo_2019Q1.htm"))
    assert datos["production_total"] == 77_100
    assert datos["production_volumen"] == 62_950
    assert datos["production_nicho"] == 14_150
    assert datos["deliveries_total"] == 63_000
    assert datos["deliveries_volumen"] == 50_900
    assert datos["deliveries_nicho"] == 12_100


def test_la_nota_en_prosa_usa_la_nomenclatura_de_su_epoca():
    """En 2019 el Model Y no existia: las lineas se llamaban de otro modo."""
    datos = parsear_deliveries(leer("deliveries_narrativo_2019Q1.htm"))
    assert datos["etiqueta_volumen"] == "Model 3"
    assert datos["etiqueta_nicho"] == "Model S and X"


def test_un_documento_sin_cifras_avisa():
    with pytest.raises(TablaDeliveriesNoEncontrada):
        parsear_deliveries("<html><body><p>Nada que ver aqui</p></body></html>")


def test_un_guion_en_la_tabla_significa_cero():
    """Tesla no fabrico Model S/X en 2021Q1 y lo publico con un guion."""
    from src.fetch_deliveries import _a_entero
    assert _a_entero("-") == 0
    assert _a_entero("\u2014") == 0
    assert _a_entero("180338") == 180_338
    assert _a_entero("n/d") is None
