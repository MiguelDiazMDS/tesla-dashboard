from src.cargar_estados import (
    desacumular, discrepancias, extraer_da, listar_informes, meses_acumulados,
)
import src.cargar_estados as cargar_estados


def test_meses_acumulados_segun_el_filing():
    """El estado de flujos de un 10-Q va acumulado desde enero."""
    assert meses_acumulados("10-Q", "2026Q1") == 3
    assert meses_acumulados("10-Q", "2026Q2") == 6
    assert meses_acumulados("10-Q", "2026Q3") == 9
    assert meses_acumulados("10-K", "2025Q4") == 12


def test_extraer_da_busca_en_cualquier_seccion():
    """La fila cuelga de 'Cash Flows from Operating Activities', no del consolidado."""
    datos = {(6, "2026Q2"): {"Cash Flows from Operating Activities": {
        "Net income": 1e9,
        "Depreciation, amortization and impairment": 3_209e6,
    }}}
    assert extraer_da(datos, 6, "2026Q2") == 3_209e6


def test_extraer_da_reconoce_la_etiqueta_antigua():
    datos = {(3, "2019Q1"): {"": {"Depreciation and amortization": 450e6}}}
    assert extraer_da(datos, 3, "2019Q1") == 450e6


def test_extraer_da_devuelve_none_si_no_esta():
    assert extraer_da({(3, "2019Q1"): {"": {"Net income": 1.0}}}, 3, "2019Q1") is None


def test_desacumular_convierte_acumulados_en_trimestres():
    acumulados = {
        "2026Q1": (3, 1_500.0), "2026Q2": (6, 3_209.0),
        "2025Q3": (9, 4_000.0), "2025Q4": (12, 5_400.0),
    }
    trimestres = desacumular(acumulados)
    assert trimestres["2026Q1"] == 1_500.0
    assert trimestres["2026Q2"] == 1_709.0
    assert trimestres["2025Q4"] == 1_400.0


def test_desacumular_omite_un_trimestre_sin_su_anterior():
    """Sin el acumulado previo no se puede restar: mejor omitir que inventar."""
    assert desacumular({"2025Q3": (9, 4_000.0)}) == {}


def test_listar_informes_da_la_fecha_de_presentacion():
    """listar_informes recibe el indice ya unido (paginas antiguas incluidas),
    un diccionario plano de arrays, no el JSON de submissions envuelto."""
    indice = {
        "form": ["10-Q", "8-K", "10-K", "10-Q"],
        "reportDate": ["2026-06-30", "2026-07-02", "2025-12-31", "2018-09-30"],
        "filingDate": ["2026-07-23", "2026-07-02", "2026-01-29", "2018-10-26"],
        "accessionNumber": ["a", "b", "c", "d"],
    }
    assert listar_informes(indice) == [
        ("c", "10-K", "2025Q4", "2026-01-29"),
        ("a", "10-Q", "2026Q2", "2026-07-23"),
    ]


# --- Discrepancias de amortizaciones -----------------------------------------

def test_coincidencia_dentro_de_tolerancia_no_da_discrepancia():
    acumulados = {"2026Q1": (3, 1_000e6)}
    comparativos = {"2026Q1": (3, 1_003e6)}       # 0.3%, por debajo del 0.5%
    assert discrepancias(acumulados, comparativos) == []


def test_diferencia_del_uno_por_ciento_da_discrepancia():
    acumulados = {"2026Q1": (3, 1_000e6)}
    comparativos = {"2026Q1": (3, 1_010e6)}       # 1%
    assert discrepancias(acumulados, comparativos) == ["2026Q1"]


def test_un_periodo_en_reexpresiones_conocidas_se_excluye(monkeypatch):
    monkeypatch.setattr(cargar_estados, "REEXPRESIONES_CONOCIDAS", {"2026Q1"})
    acumulados = {"2026Q1": (3, 1_000e6)}
    comparativos = {"2026Q1": (3, 1_010e6)}
    assert discrepancias(acumulados, comparativos) == []


def test_un_comparativo_de_otra_duracion_no_se_compara():
    """El comparativo de otro numero de meses no es el mismo periodo acumulado."""
    acumulados = {"2026Q2": (6, 1_000e6)}
    comparativos = {"2026Q2": (3, 2_000e6)}       # meses distintos: no compara
    assert discrepancias(acumulados, comparativos) == []
