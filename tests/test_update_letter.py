from pathlib import Path

import pytest

from src.cargar_update_letter import (
    cifras_significativas, elegir, es_redondeo, fusionar, periodo_de_carta,
)
from src.fetch_update_letter import (
    CuadroNoEncontrado, cabecera_trimestres, parsear_cuadro, texto_plano,
)

FIXTURES = Path(__file__).parent / "fixtures"


def leer(nombre):
    return (FIXTURES / nombre).read_text(encoding="utf-8", errors="replace")


# --- Carta moderna, exhibit HTML de EDGAR -----------------------------------

def test_el_cuadro_cubre_cinco_trimestres():
    cuadro = parsear_cuadro(leer("update_letter_2026Q2.htm"))
    assert list(cuadro) == ["2025Q2", "2025Q3", "2025Q4", "2026Q1", "2026Q2"]


def test_lee_dias_de_inventario_y_almacenamiento():
    """Cifras reales del Update Letter de Q2 2026."""
    cuadro = parsear_cuadro(leer("update_letter_2026Q2.htm"))
    assert cuadro["2026Q2"]["days_inventory"] == 15
    assert cuadro["2026Q2"]["storage_deployed_gwh"] == 13.5
    assert cuadro["2026Q1"]["storage_deployed_gwh"] == 8.8


def test_lee_las_suscripciones_fsd_en_unidades():
    """Tesla las publica en millones: 1,48 son 1.480.000 suscripciones."""
    cuadro = parsear_cuadro(leer("update_letter_2026Q2.htm"))
    assert cuadro["2026Q2"]["fsd_subscriptions"] == pytest.approx(1_480_000)
    assert cuadro["2025Q2"]["fsd_subscriptions"] == pytest.approx(950_000)


# --- Carta antigua, texto extraido del PDF ----------------------------------

def test_el_mismo_parser_lee_el_texto_del_pdf():
    """Las cartas de 2020Q4-2022Q1 son imagenes en EDGAR: se leen del PDF."""
    cuadro = parsear_cuadro(leer("update_letter_2022Q1_pdf.txt"))
    assert list(cuadro) == ["2021Q1", "2021Q2", "2021Q3", "2021Q4", "2022Q1"]
    assert cuadro["2021Q4"]["days_inventory"] == 4


def test_convierte_el_almacenamiento_de_mwh_a_gwh():
    """Hasta 2024 la unidad era MWh: sin convertir, el error seria de mil veces."""
    cuadro = parsear_cuadro(leer("update_letter_2022Q1_pdf.txt"))
    assert cuadro["2021Q2"]["storage_deployed_gwh"] == pytest.approx(1.274)


def test_una_carta_antigua_no_trae_suscripciones_fsd():
    """El dato no se publicaba en 2022: no hay que inventarlo."""
    cuadro = parsear_cuadro(leer("update_letter_2022Q1_pdf.txt"))
    assert all("fsd_subscriptions" not in v for v in cuadro.values())


def test_rechaza_una_unidad_de_almacenamiento_desconocida():
    html = ("Q1-2024 Q2-2024 Q3-2024 Q4-2024 Q1-2025 "
            "Storage deployed (TWh) 1 2 3 4 5 10%")
    with pytest.raises(CuadroNoEncontrado, match="unidad"):
        parsear_cuadro(html)


def test_un_documento_sin_cuadro_avisa():
    with pytest.raises(CuadroNoEncontrado):
        parsear_cuadro("<html><body>Highlights sin metricas</body></html>")


# --- Utilidades --------------------------------------------------------------

def test_cabecera_exige_cinco_trimestres_consecutivos():
    texto = "Q1-2024 Q3-2024 Q2-2025 Q3-2025 Q4-2025 Q1-2026 Q2-2026 metrica"
    assert cabecera_trimestres(texto, len(texto)) == [
        "2025Q2", "2025Q3", "2025Q4", "2026Q1", "2026Q2"]


def test_texto_plano_quita_etiquetas_y_entidades():
    assert texto_plano("<p>Days&#160;of&nbsp;supply</p>") == "Days of supply"


def test_periodo_de_carta_toma_el_8k_de_resultados():
    """La carta llega unas tres semanas tras el cierre; la nota de entregas, antes."""
    assert periodo_de_carta("2026-07-22") == "2026Q2"
    assert periodo_de_carta("2026-01-28") == "2025Q4"
    assert periodo_de_carta("2026-07-02") is None


# --- Fusion de cartas que se solapan ----------------------------------------

def test_cifras_significativas():
    assert cifras_significativas(3.653) == 4
    assert cifras_significativas(3.7) == 2
    assert cifras_significativas(800_000) == 1
    assert cifras_significativas(1_040_000) == 3


def test_un_redondeo_no_es_una_discrepancia():
    """La carta de 2024Q2 da 3,7 GWh donde la de 2024Q1 daba 3.653 MWh."""
    assert es_redondeo(3.653, 3.7)
    assert es_redondeo(850_000, 800_000)


def test_una_diferencia_real_si_es_discrepancia():
    assert not es_redondeo(3.653, 4.2)


def test_se_conserva_el_valor_mas_preciso():
    assert elegir(3.653, 3.7) == 3.653      # el antiguo es mas preciso
    assert elegir(800_000, 850_000) == 850_000   # el nuevo es mas preciso


def test_a_igual_precision_gana_la_carta_posterior():
    assert elegir(3.6, 3.7) == 3.7


def test_fusionar_conserva_la_precision_y_no_avisa_por_redondeo():
    mejor, avisos = {}, []
    fusionar(mejor, "2024Q1", "8-K a", {"2023Q2": {"storage_deployed_gwh": 3.653}}, avisos)
    fusionar(mejor, "2024Q2", "8-K b", {"2023Q2": {"storage_deployed_gwh": 3.7}}, avisos)
    assert mejor["2023Q2"][2]["storage_deployed_gwh"] == 3.653
    assert avisos == []


def test_fusionar_avisa_de_una_posible_reexpresion():
    mejor, avisos = {}, []
    fusionar(mejor, "2024Q1", "8-K a", {"2023Q2": {"days_inventory": 16}}, avisos)
    fusionar(mejor, "2024Q2", "8-K b", {"2023Q2": {"days_inventory": 25}}, avisos)
    assert mejor["2023Q2"][2]["days_inventory"] == 25
    assert len(avisos) == 1


def test_fusionar_completa_campos_que_una_carta_no_trae():
    mejor, avisos = {}, []
    fusionar(mejor, "2025Q4", "8-K a", {"2025Q2": {"days_inventory": 24}}, avisos)
    fusionar(mejor, "2026Q2", "8-K b", {"2025Q2": {"fsd_subscriptions": 950_000}}, avisos)
    assert mejor["2025Q2"][2] == {"days_inventory": 24, "fsd_subscriptions": 950_000}
