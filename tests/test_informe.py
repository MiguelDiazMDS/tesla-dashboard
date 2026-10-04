import json
import math

import numpy as np
import pandas as pd
import pytest

from src.informe import (
    avisos, comparar, comparar_columnas, construir_informe, huella_datos, resumen_mercado,
)

ANTES = pd.DataFrame([
    {"period": "2026Q1", "revenue_total": 20e9, "capex": 2e9, "sbc": None,
     "source": "a", "retrieved_at": "2026-08-01"},
])
DESPUES = pd.DataFrame([
    {"period": "2026Q1", "revenue_total": 20e9, "capex": 2.1e9, "sbc": None,
     "source": "b", "retrieved_at": "2026-09-23"},
    {"period": "2026Q2", "revenue_total": 30e9, "capex": 2e9, "sbc": 1e8,
     "source": "b", "retrieved_at": "2026-09-23"},
])


def test_trimestres_nuevos_y_reexpresiones():
    nuevos, reexp, eliminados = comparar(DESPUES, ANTES, "period")
    assert nuevos == ["2026Q2"] and eliminados == []
    # capex cambio; revenue igual; sbc nulo en ambos; source/retrieved_at se ignoran
    assert reexp == [{"periodo": "2026Q1", "campo": "capex", "antes": 2e9, "despues": 2.1e9}]


def test_sin_version_anterior_todo_es_nuevo():
    nuevos, reexp, eliminados = comparar(DESPUES, None, "period")
    assert nuevos == ["2026Q1", "2026Q2"] and reexp == [] and eliminados == []


def test_diferencias_minimas_no_son_reexpresion():
    casi = DESPUES.copy()
    casi.loc[0, "capex"] = 2.1e9 * (1 + 1e-12)
    _, reexp, _ = comparar(casi, DESPUES, "period")
    assert reexp == []


def test_diferencia_relativa_de_1e_8_si_es_reexpresion():
    casi = DESPUES.copy()
    casi.loc[0, "capex"] = 2.1e9 * (1 + 1e-8)
    _, reexp, _ = comparar(casi, DESPUES, "period")
    assert len(reexp) == 1 and reexp[0]["campo"] == "capex"


def test_un_nulo_que_aparece_es_reexpresion():
    antes = DESPUES.copy()
    antes.loc[1, "sbc"] = None
    _, reexp, _ = comparar(DESPUES, antes, "period")
    assert reexp == [{"periodo": "2026Q2", "campo": "sbc", "antes": None, "despues": 1e8}]


def test_un_periodo_que_desaparece_se_reporta_como_eliminado():
    """Probablemente una descarga fallo: falta comprobarlo antes de valorar."""
    nuevos, reexp, eliminados = comparar(ANTES, DESPUES, "period")
    assert nuevos == [] and eliminados == ["2026Q2"]


def test_columna_source_update_letter_no_genera_reexpresion():
    """source_update_letter cita siempre la carta mas reciente: cambia cada trimestre."""
    antes = pd.DataFrame([{"period": "2026Q1", "storage_deployed_gwh": 3.7,
                           "source_update_letter": "Update Letter 2026Q1 (8-K X)"}])
    despues = pd.DataFrame([{"period": "2026Q1", "storage_deployed_gwh": 3.7,
                             "source_update_letter": "Update Letter 2026Q2 (8-K Y)"}])
    _, reexp, _ = comparar(despues, antes, "period")
    assert reexp == []


def test_una_columna_nueva_no_genera_reexpresion():
    antes = pd.DataFrame([{"period": "2026Q1", "revenue_total": 20e9}])
    despues = pd.DataFrame([{"period": "2026Q1", "revenue_total": 20e9,
                             "fsd_subscriptions": 500.0}])
    _, reexp, _ = comparar(despues, antes, "period")
    assert reexp == []


def test_infinitos_iguales_no_son_reexpresion():
    antes = pd.DataFrame([{"period": "2026Q1", "revenue_total": math.inf}])
    despues = pd.DataFrame([{"period": "2026Q1", "revenue_total": math.inf}])
    _, reexp, _ = comparar(despues, antes, "period")
    assert reexp == []


def test_infinito_frente_a_finito_es_reexpresion():
    antes = pd.DataFrame([{"period": "2026Q1", "revenue_total": math.inf}])
    despues = pd.DataFrame([{"period": "2026Q1", "revenue_total": 20e9}])
    _, reexp, _ = comparar(despues, antes, "period")
    assert len(reexp) == 1


def test_comparar_columnas_detecta_altas_y_bajas():
    antes = pd.DataFrame([{"period": "2026Q1", "revenue_total": 20e9, "cogs_total": 15e9}])
    despues = pd.DataFrame([{"period": "2026Q1", "revenue_total": 20e9,
                             "fsd_subscriptions": 500.0}])
    nuevas, eliminadas = comparar_columnas(despues, antes, "period")
    assert nuevas == ["fsd_subscriptions"] and eliminadas == ["cogs_total"]


def test_comparar_columnas_ignora_las_de_trazabilidad():
    antes = pd.DataFrame([{"period": "2026Q1", "revenue_total": 20e9,
                           "source_update_letter": "x", "retrieved_at": "2026-08-01"}])
    despues = pd.DataFrame([{"period": "2026Q1", "revenue_total": 20e9,
                             "source_update_letter": "y", "retrieved_at": "2026-09-23"}])
    assert comparar_columnas(despues, antes, "period") == ([], [])


def test_comparar_columnas_sin_version_anterior():
    assert comparar_columnas(DESPUES, None, "period") == ([], [])


MERCADO = pd.DataFrame({"month": ["2026-08", "2026-09"], "price_close": [300.0, 450.0],
                        "eurusd": [1.10, 1.20], "rf_10y": [0.040, 0.052]})


def test_resumen_de_mercado():
    r = resumen_mercado(MERCADO, MERCADO.iloc[:1])
    assert r["meses_nuevos"] == ["2026-09"]
    assert r["ultimo_mes"] == "2026-09" and r["mes_anterior"] == "2026-08"
    assert r["precio"] == {"antes": 300.0, "despues": 450.0}


def test_avisos_por_encima_del_umbral():
    trimestral = pd.DataFrame({"period": ["2026Q1", "2026Q2"], "revenue_total": [20e9, 30e9]})
    textos = avisos(MERCADO, trimestral, ["2026Q2"])
    assert len(textos) == 4          # precio +50 %, EUR/USD +9,1 %, tipo +1,2 pp, ingresos +50 %
    assert any("precio" in t for t in textos)


def test_sin_avisos_por_debajo_del_umbral():
    mercado = MERCADO.assign(price_close=[300.0, 400.0], eurusd=[1.10, 1.18],
                             rf_10y=[0.040, 0.049])
    trimestral = pd.DataFrame({"period": ["2026Q1", "2026Q2"], "revenue_total": [20e9, 27e9]})
    assert avisos(mercado, trimestral, ["2026Q2"]) == []


def test_exactamente_un_punto_de_tipo_no_avisa():
    """0.050 - 0.040 sale 0,010000000000000002 en coma flotante: sin redondear avisaria."""
    mercado = MERCADO.assign(price_close=[300.0, 300.0], eurusd=[1.10, 1.10],
                             rf_10y=[0.040, 0.050])
    trimestral = pd.DataFrame({"period": ["2026Q1", "2026Q2"], "revenue_total": [20e9, 20e9]})
    assert avisos(mercado, trimestral, []) == []


def test_huella_cambia_con_el_contenido(tmp_path):
    a, b = tmp_path / "a.csv", tmp_path / "b.csv"
    a.write_text("x\n1\n"), b.write_text("y\n2\n")
    h1 = huella_datos([a, b])
    b.write_text("y\n3\n")
    assert huella_datos([a, b]) != h1 and len(h1) == 64


def test_huella_es_igual_con_crlf_o_con_lf(tmp_path):
    """Un cambio de terminador de linea (editar en Windows) no debe parecer un cambio de datos."""
    a, b = tmp_path / "a.csv", tmp_path / "b.csv"
    a.write_bytes(b"x,y\r\n1,2\r\n"), b.write_bytes(b"month\r\n2026-09\r\n")
    h_crlf = huella_datos([a, b])
    a.write_bytes(b"x,y\n1,2\n"), b.write_bytes(b"month\n2026-09\n")
    h_lf = huella_datos([a, b])
    assert h_crlf == h_lf


def test_huella_cambia_si_se_mueven_bytes_de_un_fichero_al_siguiente(tmp_path):
    """Sin el nombre y la longitud, "AB" + "CD" y "A" + "BCD" hashean igual."""
    a, b = tmp_path / "a.csv", tmp_path / "b.csv"
    a.write_text("AB"), b.write_text("CD")
    h1 = huella_datos([a, b])
    a.write_text("A"), b.write_text("BCD")
    h2 = huella_datos([a, b])
    assert h1 != h2


LLAVES_INFORME = {"fecha", "huella_datos", "trimestres_nuevos", "revision_trimestral",
                  "reexpresiones", "periodos_eliminados", "columnas_nuevas",
                  "columnas_eliminadas", "mercado", "avisos"}


def test_construir_informe_marca_la_revision_trimestral():
    actual = {"financials_quarterly": DESPUES, "operating_quarterly": DESPUES.iloc[:1],
              "market_monthly": MERCADO}
    anterior = {"financials_quarterly": ANTES, "operating_quarterly": ANTES,
                "market_monthly": MERCADO.iloc[:1]}
    inf = construir_informe(actual, anterior, "2026-09-23", "h" * 64)
    assert inf["revision_trimestral"] is True
    assert inf["trimestres_nuevos"] == {"financials_quarterly": ["2026Q2"],
                                        "operating_quarterly": []}
    assert inf["fecha"] == "2026-09-23" and inf["huella_datos"] == "h" * 64
    assert set(inf) == LLAVES_INFORME
    assert inf["periodos_eliminados"] == {"financials_quarterly": [], "operating_quarterly": [],
                                          "market_monthly": []}
    assert inf["columnas_nuevas"] == {"financials_quarterly": [], "operating_quarterly": [],
                                      "market_monthly": []}
    assert inf["columnas_eliminadas"] == {"financials_quarterly": [], "operating_quarterly": [],
                                          "market_monthly": []}
    assert inf["mercado"]["mes_revisado"] is None


def test_solo_entregas_nuevas_no_activan_la_revision():
    actual = {"financials_quarterly": ANTES, "operating_quarterly": DESPUES,
              "market_monthly": MERCADO}
    anterior = {"financials_quarterly": ANTES, "operating_quarterly": ANTES,
                "market_monthly": MERCADO}
    assert construir_informe(actual, anterior, "2026-09-23", "h")["revision_trimestral"] is False


def test_un_periodo_eliminado_aparece_en_el_informe():
    actual = {"financials_quarterly": ANTES, "operating_quarterly": ANTES,
              "market_monthly": MERCADO}
    anterior = {"financials_quarterly": DESPUES, "operating_quarterly": ANTES,
                "market_monthly": MERCADO}
    inf = construir_informe(actual, anterior, "2026-09-23", "h")
    assert inf["periodos_eliminados"]["financials_quarterly"] == ["2026Q2"]
    assert inf["periodos_eliminados"]["operating_quarterly"] == []


def test_mes_en_curso_revisado_no_es_reexpresion():
    """El ultimo mes de la version anterior era parcial: su cambio no es reexpresion."""
    anterior_mercado = pd.DataFrame({"month": ["2026-08"], "price_close": [300.0],
                                     "eurusd": [1.10], "rf_10y": [0.040]})
    actual_mercado = pd.DataFrame({"month": ["2026-08", "2026-09"],
                                   "price_close": [305.0, 450.0],
                                   "eurusd": [1.10, 1.20], "rf_10y": [0.040, 0.052]})
    actual = {"financials_quarterly": ANTES, "operating_quarterly": ANTES,
              "market_monthly": actual_mercado}
    anterior = {"financials_quarterly": ANTES, "operating_quarterly": ANTES,
                "market_monthly": anterior_mercado}
    inf = construir_informe(actual, anterior, "2026-09-23", "h")
    assert inf["reexpresiones"]["market_monthly"] == []
    assert inf["mercado"]["mes_revisado"] == {
        "mes": "2026-08",
        "campos": [{"campo": "price_close", "antes": 300.0, "despues": 305.0}],
    }


def test_mes_en_curso_sin_cambios_da_mes_revisado_nulo():
    actual = {"financials_quarterly": ANTES, "operating_quarterly": ANTES,
              "market_monthly": MERCADO}
    anterior = {"financials_quarterly": ANTES, "operating_quarterly": ANTES,
                "market_monthly": MERCADO.iloc[:1]}
    inf = construir_informe(actual, anterior, "2026-09-23", "h")
    assert inf["mercado"]["mes_revisado"] is None


def test_informe_es_serializable_con_enteros_numpy_y_nulos():
    fin = pd.DataFrame([{"period": "2026Q1", "revenue_total": np.int64(20_000_000_000),
                         "capex": None}])
    actual = {"financials_quarterly": fin, "operating_quarterly": fin, "market_monthly": MERCADO}
    anterior = {"financials_quarterly": None, "operating_quarterly": None,
                "market_monthly": None}
    inf = construir_informe(actual, anterior, "2026-09-23", "h")
    json.dumps(inf, allow_nan=False)
