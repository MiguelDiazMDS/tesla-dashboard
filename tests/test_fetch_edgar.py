import json
from pathlib import Path

import pytest

from src.fetch_edgar import completar_q4, extraer_serie, extraer_serie_anual, periodo_de_fechas

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "companyfacts_min.json").read_text()
)


def test_periodo_de_fechas_identifica_el_trimestre_natural():
    assert periodo_de_fechas("2019-01-01", "2019-03-31") == "2019Q1"
    assert periodo_de_fechas("2019-04-01", "2019-06-30") == "2019Q2"
    assert periodo_de_fechas("2019-10-01", "2019-12-31") == "2019Q4"


def test_periodo_de_fechas_rechaza_un_periodo_anual():
    """Un hecho de 10-K abarca el anio: no es un trimestre."""
    assert periodo_de_fechas("2019-01-01", "2019-12-31") is None


def test_extraer_serie_devuelve_periodo_y_valor():
    serie = extraer_serie(FIXTURE, ["Revenues"])
    assert serie == {"2019Q1": 4541000000, "2019Q2": 6350000000}


def test_extraer_serie_usa_el_primer_concepto_disponible():
    serie = extraer_serie(FIXTURE, ["ConceptoInexistente", "Revenues"])
    assert serie["2019Q1"] == 4541000000


def test_extraer_serie_falla_si_ningun_concepto_existe():
    with pytest.raises(KeyError, match="ninguno de los conceptos"):
        extraer_serie(FIXTURE, ["NoExiste1", "NoExiste2"])


def test_extraer_serie_anual_recoge_el_ejercicio_completo():
    assert extraer_serie_anual(FIXTURE, ["Revenues"]) == {2019: 24578000000}


def test_extraer_serie_anual_ignora_los_trimestres():
    assert list(extraer_serie_anual(FIXTURE, ["Revenues"])) == [2019]


def test_extraer_serie_anual_devuelve_vacio_si_no_hay_concepto():
    """La ausencia de dato anual solo impide reconstruir Q4: no es fatal."""
    assert extraer_serie_anual(FIXTURE, ["NoExiste"]) == {}


def test_completar_q4_calcula_por_diferencia():
    trimestres = {"2019Q1": 100.0, "2019Q2": 200.0, "2019Q3": 300.0}
    anuales = {2019: 1000.0}
    assert completar_q4(trimestres, anuales)["2019Q4"] == 400.0


def test_completar_q4_no_toca_los_trimestres_existentes():
    trimestres = {"2019Q1": 100.0, "2019Q2": 200.0, "2019Q3": 300.0}
    resultado = completar_q4(trimestres, {2019: 1000.0})
    assert resultado["2019Q1"] == 100.0


def test_completar_q4_ignora_un_anio_incompleto():
    trimestres = {"2019Q1": 100.0, "2019Q2": 200.0}
    resultado = completar_q4(trimestres, {2019: 1000.0})
    assert "2019Q4" not in resultado


def test_completar_q4_respeta_un_q4_ya_presente():
    trimestres = {f"2019Q{i}": 100.0 for i in range(1, 5)}
    resultado = completar_q4(trimestres, {2019: 999.0})
    assert resultado["2019Q4"] == 100.0


from src.fetch_edgar import CLASE_MAGNITUD, factor_split, normalizar_acciones


def test_factor_split_antes_de_los_dos_splits():
    """Un dato publicado antes de agosto de 2020 no tiene ningun split aplicado."""
    assert factor_split("2019-04-29") == 15
    assert factor_split("2020-07-28") == 15


def test_factor_split_entre_los_dos_splits():
    """Publicado entre ambos: solo lleva aplicado el 5:1."""
    assert factor_split("2020-10-26") == 3
    assert factor_split("2022-04-25") == 3


def test_factor_split_despues_de_los_dos():
    assert factor_split("2022-10-24") == 1
    assert factor_split("2026-07-23") == 1


def test_normalizar_acciones_deja_la_serie_en_la_base_actual():
    """2019Q3 publicado en 2020 lleva el 5:1 pero no el 3:1: falta un x3."""
    hechos = {"2019Q3": ("2020-10-26", 922_000_000)}
    assert normalizar_acciones(hechos) == {"2019Q3": 2_766_000_000}


def test_normalizar_acciones_con_dato_prehistorico():
    hechos = {"2019Q1": ("2020-04-30", 173_000_000)}
    assert normalizar_acciones(hechos) == {"2019Q1": 2_595_000_000}


def test_las_magnitudes_no_aditivas_estan_clasificadas():
    """Reconstruir el Q4 de un promedio ponderado por diferencia seria un error."""
    assert CLASE_MAGNITUD["shares_diluted"] == "no_aditiva"
    assert CLASE_MAGNITUD["eps_diluted_gaap"] == "no_aditiva"
    assert CLASE_MAGNITUD["revenue_total"] == "flujo"
    assert CLASE_MAGNITUD["cash_and_investments"] == "balance"


from src.fetch_edgar import extraer_serie_con_filed

REEXPRESADO = {"facts": {"us-gaap": {"Cualquiera": {"units": {"USD": [
    {"start": "2019-07-01", "end": "2019-09-30", "val": 184_000_000,
     "form": "10-Q", "accn": "viejo", "filed": "2019-10-29"},
    {"start": "2019-07-01", "end": "2019-09-30", "val": 922_000_000,
     "form": "10-Q", "accn": "nuevo", "filed": "2020-10-26"},
]}}}}}


def test_extraer_serie_se_queda_con_el_filing_mas_reciente():
    """Con 37 periodos reexpresados en los datos reales, esto no puede depender
    del orden en que la SEC devuelva los hechos."""
    assert extraer_serie(REEXPRESADO, ["Cualquiera"]) == {"2019Q3": 922_000_000}


def test_el_desempate_no_depende_del_orden_de_entrada():
    invertido = {"facts": {"us-gaap": {"Cualquiera": {"units": {"USD": list(
        reversed(REEXPRESADO["facts"]["us-gaap"]["Cualquiera"]["units"]["USD"])
    )}}}}}
    assert extraer_serie(invertido, ["Cualquiera"]) == {"2019Q3": 922_000_000}


def test_extraer_serie_con_filed_conserva_la_fecha_de_publicacion():
    """Necesario para poder aplicar el factor de split correcto."""
    assert extraer_serie_con_filed(REEXPRESADO, ["Cualquiera"]) == {
        "2019Q3": ("2020-10-26", 922_000_000)
    }


from src.fetch_edgar import extraer_serie_ytd, tramo_ytd

DOS_CONCEPTOS = {"facts": {"us-gaap": {
    "Preferente": {"units": {"USD": [
        {"start": "2022-07-01", "end": "2022-09-30", "val": 300,
         "form": "10-Q", "filed": "2022-10-24"},
    ]}},
    "Amplio": {"units": {"USD": [
        {"start": "2019-01-01", "end": "2019-03-31", "val": 100,
         "form": "10-Q", "filed": "2019-04-29"},
        {"start": "2022-07-01", "end": "2022-09-30", "val": 300,
         "form": "10-Q", "filed": "2022-10-24"},
    ]}},
}}}


def test_los_conceptos_se_fusionan_por_periodo():
    """El concepto preferente cubre menos periodos: los demas rellenan el resto."""
    serie = extraer_serie(DOS_CONCEPTOS, ["Preferente", "Amplio"])
    assert serie == {"2019Q1": 100, "2022Q3": 300}


def test_gana_el_concepto_mas_preferente_en_los_periodos_compartidos():
    conflicto = {"facts": {"us-gaap": {
        "Preferente": {"units": {"USD": [
            {"start": "2019-01-01", "end": "2019-03-31", "val": 111,
             "form": "10-Q", "filed": "2019-04-29"}]}},
        "Amplio": {"units": {"USD": [
            {"start": "2019-01-01", "end": "2019-03-31", "val": 999,
             "form": "10-Q", "filed": "2019-04-29"}]}},
    }}}
    assert extraer_serie(conflicto, ["Preferente", "Amplio"]) == {"2019Q1": 111}


def test_tramo_ytd_reconoce_los_cuatro_acumulados():
    assert tramo_ytd("2024-01-01", "2024-03-31") == (2024, 1)
    assert tramo_ytd("2024-01-01", "2024-06-30") == (2024, 2)
    assert tramo_ytd("2024-01-01", "2024-09-30") == (2024, 3)
    assert tramo_ytd("2024-01-01", "2024-12-31") == (2024, 4)


def test_tramo_ytd_descarta_lo_que_no_arranca_en_enero():
    """Un periodo suelto de tres meses no es un acumulado del ejercicio."""
    assert tramo_ytd("2024-04-01", "2024-06-30") is None


def test_extraer_serie_ytd_desacumula_el_ejercicio():
    """Cifras reales del flujo de explotacion de Tesla en 2024."""
    flujos = {"facts": {"us-gaap": {"Flujo": {"units": {"USD": [
        {"start": "2024-01-01", "end": "2024-03-31", "val": 242_000_000,
         "form": "10-Q", "filed": "2024-04-24"},
        {"start": "2024-01-01", "end": "2024-06-30", "val": 3_854_000_000,
         "form": "10-Q", "filed": "2024-07-24"},
        {"start": "2024-01-01", "end": "2024-09-30", "val": 10_109_000_000,
         "form": "10-Q", "filed": "2024-10-24"},
        {"start": "2024-01-01", "end": "2024-12-31", "val": 14_923_000_000,
         "form": "10-K", "filed": "2025-01-29"},
    ]}}}}}
    serie = extraer_serie_ytd(flujos, ["Flujo"])
    assert serie == {
        "2024Q1": 242_000_000, "2024Q2": 3_612_000_000,
        "2024Q3": 6_255_000_000, "2024Q4": 4_814_000_000,
    }
    assert sum(serie.values()) == 14_923_000_000


def test_extraer_serie_ytd_omite_un_trimestre_sin_su_anterior():
    """Sin el acumulado previo no se puede restar: mejor omitir que inventar."""
    solo_nueve = {"facts": {"us-gaap": {"Flujo": {"units": {"USD": [
        {"start": "2024-01-01", "end": "2024-09-30", "val": 10_109_000_000,
         "form": "10-Q", "filed": "2024-10-24"},
    ]}}}}}
    assert extraer_serie_ytd(solo_nueve, ["Flujo"]) == {}
