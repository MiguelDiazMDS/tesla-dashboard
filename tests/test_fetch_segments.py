from pathlib import Path

import pytest

from src.fetch_segments import (
    INFORME_GEOGRAFIA, INFORME_LINEAS, INFORME_SEGMENTOS, InformeNoEncontrado,
    SeccionContradictoria, extraer_geografia, extraer_lineas_producto,
    extraer_segmentos, parsear_tabla, periodo_de_columna, recortar_html,
    resolver_informe,
)

FIXTURES = Path(__file__).parent / "fixtures"
SUMMARY = (FIXTURES / "filing_summary_min.xml").read_text(encoding="utf-8")


def leer(nombre):
    return (FIXTURES / nombre).read_text(encoding="utf-8", errors="replace")


# --- Resolucion del informe dentro del filing -------------------------------

def test_resolver_informe_localiza_por_nombre_no_por_posicion():
    """El numero del fichero cambia entre filings: hay que buscar por nombre."""
    assert resolver_informe(SUMMARY, INFORME_SEGMENTOS) == "R63.htm"


def test_resolver_informe_ignora_mayusculas():
    assert resolver_informe(SUMMARY, INFORME_GEOGRAFIA.lower()) == "R64.htm"


def test_resolver_informe_encuentra_las_lineas_de_producto():
    assert resolver_informe(SUMMARY, INFORME_LINEAS) == "R35.htm"


def test_resolver_informe_avisa_si_no_existe():
    with pytest.raises(InformeNoEncontrado, match="Inexistente"):
        resolver_informe(SUMMARY, "Informe Inexistente")


# --- Utilidades de parseo ---------------------------------------------------

def test_recortar_html_quita_el_envoltorio_sgml():
    envuelto = "<DOCUMENT><TYPE>XML<TEXT><html><body>x</body></html></TEXT>"
    assert recortar_html(envuelto) == "<html><body>x</body></html>"


def test_periodo_de_columna_interpreta_la_cabecera():
    assert periodo_de_columna("3 Months Ended", "Jun. 30, 2026") == (3, "2026Q2")
    assert periodo_de_columna("12 Months Ended", "Dec. 31, 2024") == (12, "2024Q4")


def test_periodo_de_columna_descarta_un_cierre_no_trimestral():
    assert periodo_de_columna("3 Months Ended", "May 31, 2026") is None


# --- Segmentos --------------------------------------------------------------

def test_extraer_segmentos_da_las_dos_unidades_reportables():
    """Cifras reales de Q2 2026."""
    datos = parsear_tabla(leer("segmentos_2026Q2.htm"))
    seg = extraer_segmentos(datos, 3, "2026Q2")
    assert seg["revenue_auto_segment"] == 25_097_000_000
    assert seg["revenue_energy_segment"] == 3_139_000_000
    assert seg["gross_profit_auto_segment"] == 4_111_000_000
    assert seg["gross_profit_energy_segment"] == 640_000_000


def test_los_dos_segmentos_suman_el_consolidado():
    datos = parsear_tabla(leer("segmentos_2026Q2.htm"))
    seg = extraer_segmentos(datos, 3, "2026Q2")
    assert seg["revenue_auto_segment"] + seg["revenue_energy_segment"] == 28_236_000_000


def test_no_aparece_un_tercer_segmento():
    """Tesla declara dos segmentos bajo ASC 280: servicios no es uno de ellos."""
    datos = parsear_tabla(leer("segmentos_2026Q2.htm"))
    seg = extraer_segmentos(datos, 3, "2026Q2")
    assert not [c for c in seg if "services_segment" in c]


def test_la_tabla_trae_tambien_el_acumulado_del_semestre():
    """Un 10-Q publica el trimestre y el acumulado: hay que saber distinguirlos."""
    datos = parsear_tabla(leer("segmentos_2026Q2.htm"))
    assert (3, "2026Q2") in datos
    assert (6, "2026Q2") in datos
    assert extraer_segmentos(datos, 6, "2026Q2")["revenue_auto_segment"] == 45_076_000_000


# --- Lineas de producto -----------------------------------------------------

def test_extraer_lineas_da_las_seis_lineas():
    lineas = extraer_lineas_producto(parsear_tabla(leer("lineas_2026Q2.htm")), 3, "2026Q2")
    assert lineas["revenue_auto_sales"] == 20_006_000_000
    assert lineas["revenue_reg_credits"] == 146_000_000
    assert lineas["revenue_auto_leasing"] == 364_000_000
    assert lineas["revenue_services"] == 4_581_000_000
    assert lineas["revenue_energy_sales"] == 2_998_000_000
    assert lineas["revenue_energy_leasing"] == 141_000_000


def test_las_lineas_de_automocion_suman_su_segmento():
    """Servicios y creditos regulatorios van dentro de automocion."""
    lineas = extraer_lineas_producto(parsear_tabla(leer("lineas_2026Q2.htm")), 3, "2026Q2")
    suma = sum(lineas[c] for c in (
        "revenue_auto_sales", "revenue_reg_credits",
        "revenue_auto_leasing", "revenue_services",
    ))
    assert suma == 25_097_000_000


def test_las_lineas_de_energia_suman_su_segmento():
    lineas = extraer_lineas_producto(parsear_tabla(leer("lineas_2026Q2.htm")), 3, "2026Q2")
    assert lineas["revenue_energy_sales"] + lineas["revenue_energy_leasing"] == 3_139_000_000


# --- Geografia --------------------------------------------------------------

def test_extraer_geografia_da_las_tres_regiones():
    """Dato reportado en el filing, no una estimacion de terceros."""
    geo = extraer_geografia(parsear_tabla(leer("geografia_2026Q2.htm")), 3, "2026Q2")
    assert geo["revenue_us"] == 13_208_000_000
    assert geo["revenue_china"] == 4_675_000_000
    assert geo["revenue_other"] == 10_353_000_000


def test_las_regiones_suman_el_consolidado():
    geo = extraer_geografia(parsear_tabla(leer("geografia_2026Q2.htm")), 3, "2026Q2")
    assert sum(geo.values()) == 28_236_000_000


# --- Defensa frente al cruce de segmentos -----------------------------------

def test_corrige_los_ingresos_cruzados_de_algunos_filings():
    """El renderizado del 10-Q de 2023Q1 cruza los ingresos entre segmentos.

    En todo el periodo cubierto automocion supera con mucho a energia, que
    nunca ha llegado al 15% de los ingresos: si aparece al reves, estan mal.
    """
    from src.fetch_segments import corregir_intercambio
    cruzado = {
        "revenue_auto_segment": 1_529_000_000,
        "revenue_energy_segment": 21_800_000_000,
        "gross_profit_auto_segment": 4_343_000_000,
        "gross_profit_energy_segment": 168_000_000,
    }
    corregido = corregir_intercambio(dict(cruzado), "2023Q1")
    assert corregido["revenue_auto_segment"] == 21_800_000_000
    assert corregido["revenue_energy_segment"] == 1_529_000_000


def test_no_toca_el_margen_bruto_si_ya_esta_bien_asignado():
    from src.fetch_segments import corregir_intercambio
    corregido = corregir_intercambio({
        "revenue_auto_segment": 1_529_000_000,
        "revenue_energy_segment": 21_800_000_000,
        "gross_profit_auto_segment": 4_343_000_000,
        "gross_profit_energy_segment": 168_000_000,
    }, "2023Q1")
    assert corregido["gross_profit_auto_segment"] == 4_343_000_000


def test_deja_en_paz_un_trimestre_correcto():
    from src.fetch_segments import corregir_intercambio
    bueno = {
        "revenue_auto_segment": 25_097_000_000,
        "revenue_energy_segment": 3_139_000_000,
    }
    assert corregir_intercambio(dict(bueno), "2026Q2") == bueno


# --- Secciones repetidas en la jerarquia ------------------------------------

def test_una_seccion_repetida_no_se_suma_dos_veces():
    """El 10-K de 2019 lista los creditos regulatorios dos veces: suelta y
    colgando de Automotive. Sumarlas daba 1.188 millones en vez de 594."""
    datos = {(12, "2019Q4"): {
        "Automotive Regulatory Credits [Member]":
            {"Total revenues from sales and services": 594e6},
        "Automotive [Member] | Automotive Regulatory Credits [Member]":
            {"Total revenues from sales and services": 594e6},
    }}
    assert extraer_lineas_producto(datos, 12, "2019Q4")["revenue_reg_credits"] == 594e6


def test_secciones_distintas_de_la_misma_serie_si_se_suman():
    """Las ventas con y sin garantia de valor residual son dos lineas reales."""
    datos = {(12, "2019Q4"): {
        "Automotive [Member] | Automotive Sales without Resale Value Guarantee [Member]":
            {"Total revenues from sales and services": 19_212e6},
        "Automotive [Member] | Automotive Sales with Resale Value Guarantee [Member]":
            {"Total revenues from sales and services": 146e6},
    }}
    assert extraer_lineas_producto(datos, 12, "2019Q4")["revenue_auto_sales"] == 19_358e6


def test_una_region_repetida_no_se_suma_dos_veces():
    datos = {(3, "2019Q1"): {
        "China [Member]": {"Revenues": 100e6},
        "Other [Member] | China [Member]": {"Revenues": 100e6},
    }}
    assert extraer_geografia(datos, 3, "2019Q1")["revenue_china"] == 100e6


def test_una_linea_repetida_con_importe_distinto_lanza():
    """Si la segunda aparicion no vale lo mismo, elegir la primera al azar
    seria silencioso: mejor parar y que se investigue."""
    datos = {(12, "2019Q4"): {
        "Automotive Regulatory Credits [Member]":
            {"Total revenues from sales and services": 594e6},
        "Automotive [Member] | Automotive Regulatory Credits [Member]":
            {"Total revenues from sales and services": 700e6},
    }}
    with pytest.raises(SeccionContradictoria):
        extraer_lineas_producto(datos, 12, "2019Q4")


def test_una_region_repetida_con_importe_distinto_lanza():
    datos = {(3, "2019Q1"): {
        "China [Member]": {"Revenues": 100e6},
        "Other [Member] | China [Member]": {"Revenues": 150e6},
    }}
    with pytest.raises(SeccionContradictoria):
        extraer_geografia(datos, 3, "2019Q1")
