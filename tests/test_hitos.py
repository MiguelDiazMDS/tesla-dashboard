import copy
import json
from datetime import date, datetime

import pandas as pd
import pytest

from src.hitos import (
    HitosInvalidos, cargar, construir_hitos, deslizamiento, estado_hito, fin_de_periodo, indice,
    metricas_hito, meses_entre, transversal_caja, validar,
)

ENLACE = "https://ir.tesla.com/ejemplo"
HOY = date(2026, 9, 23)


def _promesa(declarada="2019-04-22", prometida="2020", tipo="oficial"):
    return {"declarada": declarada, "fecha_prometida": prometida, "fuente_tipo": tipo,
            "fuente": "Carta a accionistas", "enlace": ENLACE}


def _evidencia(fecha="2023-11-30", tipo="oficial"):
    return {"fecha": fecha, "fuente_tipo": tipo, "fuente": "Update Letter", "enlace": ENLACE}


def _hito_minimo(id_, prioridad, titulo):
    return {"id": id_, "prioridad": prioridad, "titulo": titulo,
            "que_debe_ocurrir": "x", "que_demostraria": "y",
            "pasos": [], "requeridos": [], "promesas": [], "estancado": None}


def datos_minimos():
    return {
        "version": "2026-09-23",
        "hitos": [
            {
                "id": "optimus", "prioridad": 2, "titulo": "Optimus comercial",
                "que_debe_ocurrir": "x", "que_demostraria": "y",
                "pasos": [{"id": "produccion", "texto": "Inicio de produccion", "etiqueta": "R",
                           "cumplido": None}],
                "requeridos": ["produccion"],
                "promesas": [_promesa("2024-06-13", "2025")], "estancado": None,
            },
            _hito_minimo("robotaxi-escala", 1, "Robotaxi a escala"),
            _hito_minimo("fsd", 3, "FSD"),
            _hito_minimo("automovil", 4, "Recuperacion del beneficio del automovil"),
            _hito_minimo("energia", 5, "Energia a mayor escala"),
            _hito_minimo("semi", 6, "Tesla Semi en serie"),
        ],
        "historial": [{
            "id": "cybertruck", "titulo": "Cybertruck", "criterio": "Entregas a clientes",
            "promesas": [_promesa()], "estado": "cumplido", "cumplimiento": _evidencia(),
        }],
        "transversal": {
            "capex_guia": {"anio": 2026, "importe": 25.0e9, "texto": "mas de 25.000 millones",
                           "fuente_tipo": "oficial", "fuente": "Update Letter", "enlace": ENLACE},
            "seguridad": [{"id": "nhtsa-fsd", "texto": "Investigacion FSD", "abierta_desde": "2024-10-17",
                           "estado": "abierta", "fuente": "NHTSA", "enlace": ENLACE}],
        },
    }


def _romper(cambio):
    d = copy.deepcopy(datos_minimos())
    cambio(d)
    return d


# --------------------------------------------------------------------------
# fin_de_periodo
# --------------------------------------------------------------------------

@pytest.mark.parametrize("texto, esperado", [
    ("2026", date(2026, 12, 31)), ("2026-Q1", date(2026, 3, 31)), ("2026-Q3", date(2026, 9, 30)),
    ("2026-02", date(2026, 2, 28)), ("2026-09-15", date(2026, 9, 15)), (2026, date(2026, 12, 31)),
    (date(2026, 5, 4), date(2026, 5, 4)),
])
def test_fin_de_periodo(texto, esperado):
    assert fin_de_periodo(texto) == esperado


def test_fecha_irreconocible():
    with pytest.raises(HitosInvalidos, match="fecha"):
        fin_de_periodo("pronto")


def test_fin_de_periodo_acepta_datetime():
    assert fin_de_periodo(datetime(2026, 5, 4, 10, 30)) == date(2026, 5, 4)


# --------------------------------------------------------------------------
# validar: casos base
# --------------------------------------------------------------------------

def test_datos_minimos_validan():
    validar(datos_minimos())


def test_validar_none():
    with pytest.raises(HitosInvalidos, match="vacio"):
        validar(None)


@pytest.mark.parametrize("cambio, mensaje", [
    (lambda d: d["historial"][0]["promesas"][0].pop("enlace"), "enlace"),
    (lambda d: d["historial"][0]["promesas"][0].update(enlace="http://x"), "https"),
    (lambda d: d["historial"][0]["promesas"][0].update(fuente_tipo="rumor"), "fuente_tipo"),
    (lambda d: d["historial"][0]["promesas"][0].update(declarada="2021-05-01"), "declarada"),
    (lambda d: d["historial"][0].update(cumplimiento=None), "cumplimiento"),
    (lambda d: d["historial"][0].update(estado="retrasado"), "estado"),
    (lambda d: d["hitos"][0]["pasos"][0].update(cumplido={"fecha": "2026-01-01"}), "fuente"),
    (lambda d: d["hitos"][0].update(requeridos=["inexistente"]), "requeridos"),
    (lambda d: d["historial"][0].update(id="optimus"), "duplicado"),
    (lambda d: d["hitos"][0].update(estancado={"desde": "2026-01-01"}), "estancado"),
    (lambda d: d["hitos"][0]["pasos"][0].update(
        cumplido=_evidencia("2026-01-01", "tercero")), "etiqueta"),
    (lambda d: d["transversal"]["capex_guia"].pop("importe"), "importe"),
])
def test_validacion_rechaza(cambio, mensaje):
    with pytest.raises(HitosInvalidos, match=mensaje):
        validar(_romper(cambio))


def test_etiqueta_e_con_tercero_valida():
    def cambio(d):
        paso = d["hitos"][0]["pasos"][0]
        paso["etiqueta"] = "E"
        paso["cumplido"] = {**_evidencia("2026-01-01", "tercero"), "valor": 1200}
    validar(_romper(cambio))


# --------------------------------------------------------------------------
# validar: robustez de tipos y estructura (fix critico/importante 4)
# --------------------------------------------------------------------------

def test_hitos_debe_ser_lista():
    with pytest.raises(HitosInvalidos, match="hitos"):
        validar(_romper(lambda d: d.update(hitos="no-es-lista")))


def test_pasos_debe_ser_lista_de_objetos():
    with pytest.raises(HitosInvalidos, match=r"hitos\.optimus\.pasos"):
        validar(_romper(lambda d: d["hitos"][0].update(pasos=["no-es-objeto"])))


def test_requeridos_elemento_debe_ser_texto():
    with pytest.raises(HitosInvalidos, match="requeridos"):
        validar(_romper(lambda d: d["hitos"][0].update(requeridos=[123])))


def test_seguridad_debe_ser_lista():
    with pytest.raises(HitosInvalidos, match="seguridad"):
        validar(_romper(lambda d: d["transversal"].update(seguridad="no-es-lista")))


def test_mensaje_incluye_ruta_en_fecha_de_evidencia():
    def cambio(d):
        d["hitos"][0]["pasos"][0]["cumplido"] = {
            "fecha": "2026-13-40", "fuente_tipo": "tercero", "fuente": "x", "enlace": ENLACE}
    with pytest.raises(HitosInvalidos, match=r"hitos\.optimus\.pasos\.produccion\.cumplido\.fecha"):
        validar(_romper(cambio))


def test_mensaje_incluye_ruta_en_seguridad():
    with pytest.raises(HitosInvalidos, match=r"transversal\.seguridad\.nhtsa-fsd"):
        validar(_romper(lambda d: d["transversal"]["seguridad"][0].pop("abierta_desde")))


# --------------------------------------------------------------------------
# validar: coherencia (fix importante 5)
# --------------------------------------------------------------------------

def test_id_de_paso_duplicado():
    def cambio(d):
        d["hitos"][0]["pasos"].append(
            {"id": "produccion", "texto": "otro", "etiqueta": "R", "cumplido": None})
    with pytest.raises(HitosInvalidos, match="duplicado"):
        validar(_romper(cambio))


def test_tipo_de_paso_invalido():
    with pytest.raises(HitosInvalidos, match="tipo"):
        validar(_romper(lambda d: d["hitos"][0]["pasos"][0].update(tipo="otro")))


def test_ids_de_hitos_prioritarios_exactos():
    with pytest.raises(HitosInvalidos, match="hitos"):
        validar(_romper(lambda d: d["hitos"][0].update(id="otro-id")))


def test_prioridad_debe_ser_entero():
    with pytest.raises(HitosInvalidos, match="prioridad"):
        validar(_romper(lambda d: d["hitos"][0].update(prioridad=2.5)))


def test_prioridad_repetida():
    def cambio(d):
        d["hitos"][1]["prioridad"] = d["hitos"][0]["prioridad"]
    with pytest.raises(HitosInvalidos, match="prioridad"):
        validar(_romper(cambio))


def test_hitos_no_puede_estar_vacia():
    with pytest.raises(HitosInvalidos, match="hitos"):
        validar(_romper(lambda d: d.update(hitos=[])))


def test_promesas_de_historial_no_puede_estar_vacia():
    with pytest.raises(HitosInvalidos, match="promesas"):
        validar(_romper(lambda d: d["historial"][0].update(promesas=[])))


def test_declarada_posterior_al_cumplimiento():
    def cambio(d):
        d["historial"][0]["promesas"][0]["declarada"] = "2024-01-01"
        d["historial"][0]["promesas"][0]["fecha_prometida"] = "2025"
        d["historial"][0]["cumplimiento"]["fecha"] = "2023-01-01"
    with pytest.raises(HitosInvalidos, match="cumplimiento"):
        validar(_romper(cambio))


def test_paso_requiere_valor_exige_valor_numerico():
    def cambio(d):
        paso = d["hitos"][0]["pasos"][0]
        paso["requiere_valor"] = True
        paso["cumplido"] = _evidencia()
    with pytest.raises(HitosInvalidos, match="valor"):
        validar(_romper(cambio))


# --------------------------------------------------------------------------
# validar: fechas exactas (fix importante 6)
# --------------------------------------------------------------------------

def test_declarada_no_puede_ser_periodo_vago():
    with pytest.raises(HitosInvalidos, match="declarada"):
        validar(_romper(lambda d: d["hitos"][0]["promesas"][0].update(declarada="2024")))


def test_estancado_desde_debe_ser_fecha_exacta():
    def cambio(d):
        d["hitos"][0]["estancado"] = {"desde": "2026-Q1", "motivo": "x", "fuente": "y", "enlace": ENLACE}
    with pytest.raises(HitosInvalidos, match="estancado"):
        validar(_romper(cambio))


def test_seguridad_abierta_desde_debe_ser_fecha_exacta():
    with pytest.raises(HitosInvalidos, match="abierta_desde"):
        validar(_romper(lambda d: d["transversal"]["seguridad"][0].update(abierta_desde="2024")))


# --------------------------------------------------------------------------
# validar: objetivo_tesla desaparece (fix importante 7)
# --------------------------------------------------------------------------

def test_objetivo_tesla_ya_no_se_usa():
    with pytest.raises(HitosInvalidos, match="objetivo_tesla"):
        validar(_romper(lambda d: d["hitos"][0].update(objetivo_tesla=None)))


# --------------------------------------------------------------------------
# validar: capex_guia (fix importante 3)
# --------------------------------------------------------------------------

def test_capex_guia_importe_no_puede_ser_bool():
    with pytest.raises(HitosInvalidos, match="importe"):
        validar(_romper(lambda d: d["transversal"]["capex_guia"].update(importe=True)))


def test_capex_guia_anio_debe_ser_entero():
    with pytest.raises(HitosInvalidos, match="anio"):
        validar(_romper(lambda d: d["transversal"]["capex_guia"].update(anio="2026")))


def test_capex_guia_fuente_tipo_invalido():
    with pytest.raises(HitosInvalidos, match="fuente_tipo"):
        validar(_romper(lambda d: d["transversal"]["capex_guia"].update(fuente_tipo="rumor")))


# --------------------------------------------------------------------------
# deslizamiento e indice
# --------------------------------------------------------------------------

def test_meses_entre():
    assert meses_entre(date(2020, 12, 31), date(2023, 11, 30)) == pytest.approx(
        (date(2023, 11, 30) - date(2020, 12, 31)).days / (365.25 / 12))


def test_deslizamiento_de_un_cumplido():
    h = {"promesas": [_promesa("2019-04-22", "2020"), _promesa("2021-01-27", "2022", "musk")],
         "estado": "cumplido", "cumplimiento": _evidencia("2023-11-30")}
    d = deslizamiento(h, HOY, solo_oficiales=False)
    assert d["tipo"] == "realizado"
    assert d["primera"] == "2020-12-31" and d["vigente"] == "2022-12-31"
    assert d["re_promesas"] == 1
    assert d["meses"] == pytest.approx(meses_entre(date(2020, 12, 31), date(2023, 11, 30)))


def test_pendiente_ya_retrasado_da_minimo_hasta_hoy():
    h = {"promesas": [_promesa("2020-01-29", "2021-Q4")], "estado": "vigente"}
    d = deslizamiento(h, HOY, solo_oficiales=False)
    assert d["tipo"] == "minimo"
    assert d["meses"] == pytest.approx(meses_entre(date(2021, 12, 31), HOY))
    assert d["vencida_vigente"] is True


def test_pendiente_no_vencido_no_entra():
    h = {"promesas": [_promesa("2026-01-28", "2027")], "estado": "vigente"}
    assert deslizamiento(h, HOY, solo_oficiales=False)["tipo"] == "a_tiempo"


def test_abandonado_y_sin_promesa_oficial():
    assert deslizamiento({"promesas": [_promesa()], "estado": "abandonado"}, HOY, False)["tipo"] == "abandonado"
    h = {"promesas": [_promesa(tipo="musk")], "estado": "cumplido", "cumplimiento": _evidencia()}
    assert deslizamiento(h, HOY, solo_oficiales=True) is None


def test_indice_realizado_y_minimo():
    cumplido = {"promesas": [_promesa("2019-04-22", "2020")], "estado": "cumplido",
                "cumplimiento": _evidencia("2021-12-31")}          # 12 meses
    pendiente = {"promesas": [_promesa("2020-01-29", "2025-09")], "estado": "vigente"}  # vencido el 2025-09-30
    abandonado = {"promesas": [_promesa()], "estado": "abandonado"}
    r = indice([cumplido, pendiente, abandonado], HOY)
    todas = r["todas"]
    real = meses_entre(date(2020, 12, 31), date(2021, 12, 31))
    minimo = meses_entre(date(2025, 9, 30), HOY)
    assert todas["realizado"]["media"] == pytest.approx(real)
    assert todas["minimo"]["media"] == pytest.approx((real + minimo) / 2)
    assert todas["minimo"]["mediana"] == pytest.approx((real + minimo) / 2)
    assert todas["cumplidos"] == 1 and todas["retrasados"] == 1 and todas["abandonados"] == 1


def test_desempate_por_fecha_prometida():
    h = {"promesas": [_promesa("2020-01-01", "2025"), _promesa("2020-01-01", "2022")],
         "estado": "vigente"}
    d = deslizamiento(h, HOY, solo_oficiales=False)
    assert d["vigente"] == "2025-12-31"


def test_solo_oficiales_cambia_la_primera_promesa():
    h = {"promesas": [_promesa("2018-01-01", "2019", "musk"), _promesa("2020-01-01", "2021")],
         "estado": "vigente"}
    todas = deslizamiento(h, HOY, solo_oficiales=False)
    oficiales = deslizamiento(h, HOY, solo_oficiales=True)
    assert todas["primera"] == "2019-12-31"
    assert oficiales["primera"] == "2021-12-31"


def test_hoy_igual_a_primera_es_a_tiempo():
    h = {"promesas": [_promesa("2020-01-01", str(HOY.year))], "estado": "vigente"}
    assert deslizamiento(h, HOY, False)["tipo"] == "a_tiempo"


def test_cumplimiento_anterior_a_la_primera_fecha_da_meses_negativos():
    h = {"promesas": [_promesa("2020-01-01", "2026")], "estado": "cumplido",
         "cumplimiento": _evidencia("2025-06-01")}
    d = deslizamiento(h, HOY, False)
    assert d["meses"] < 0


def test_vencida_vigente_false_en_abandonado():
    h = {"promesas": [_promesa("2018-01-01", "2019")], "estado": "abandonado"}
    assert deslizamiento(h, HOY, False)["vencida_vigente"] is False


# --------------------------------------------------------------------------
# metricas: trimestres consecutivos (fix critico 1)
# --------------------------------------------------------------------------

def test_metricas_del_automovil():
    # Sin creditos: 21/100 = 21 % >= 20 %; operativo 11/100 = 11 % >= 10 %; entregas 401 >= 400.
    fin = pd.DataFrame([{"period": p, "revenue_auto_segment": 100.0, "revenue_reg_credits": 0.0,
                         "gross_profit_auto_segment": 21.0, "operating_income": 11.0,
                         "revenue_total": 100.0} for p in ("2025Q3", "2025Q4", "2026Q1", "2026Q2")])
    ope = pd.DataFrame([{"period": p, "deliveries_total": d} for p, d in
                        zip(["2024Q3", "2024Q4", "2025Q1", "2025Q2", "2025Q3", "2025Q4", "2026Q1", "2026Q2"],
                            [100, 100, 100, 100, 100, 100, 100, 101])])
    m = {x["id"]: x for x in metricas_hito("automovil", fin, ope, [])}
    assert m["margen_auto_sin_creditos"]["cumple"] is True
    assert m["margen_operativo"]["cumple"] is True
    assert m["entregas_12m"]["cumple"] is True


def test_metrica_sin_dato_no_se_cumple():
    fin = pd.DataFrame([{"period": "2026Q2", "revenue_auto_segment": 100.0, "revenue_reg_credits": 0.0,
                         "gross_profit_auto_segment": 25.0, "operating_income": 15.0, "revenue_total": 100.0}])
    ope = pd.DataFrame({"period": ["2026Q2"], "deliveries_total": [100]})
    m = {x["id"]: x for x in metricas_hito("automovil", fin, ope, [])}
    assert m["margen_auto_sin_creditos"]["cumple"] is None
    assert m["entregas_12m"]["cumple"] is None


def test_metricas_de_fsd_y_mercados():
    ope = pd.DataFrame({"period": ["2025Q2", "2025Q3", "2025Q4", "2026Q1", "2026Q2"],
                        "fsd_subscriptions": [1.0e6, 1.2e6, 1.5e6, 2.0e6, 2.6e6]})
    pasos = [{"id": f"m{i}", "tipo": "mercado", "cumplido": {"fecha": f"2026-1{i}-01"}} for i in range(3)]
    pasos.append({"id": "nl", "tipo": "mercado", "cumplido": {"fecha": "2026-04-10"}})   # antes de la base
    m = {x["id"]: x for x in metricas_hito("fsd", pd.DataFrame(), ope, pasos)}
    assert m["suscripciones"]["cumple"] is True
    assert m["crecimiento_4t"]["cumple"] is True
    assert m["mercados_nuevos"]["valor"] == 3 and m["mercados_nuevos"]["cumple"] is False


def test_metricas_de_energia():
    fin = pd.DataFrame([{"period": p, "revenue_energy_segment": 10.0, "gross_profit_energy_segment": 3.0}
                        for p in ("2025Q3", "2025Q4", "2026Q1", "2026Q2")])
    ope = pd.DataFrame({"period": ["2025Q3", "2025Q4", "2026Q1", "2026Q2"],
                        "storage_deployed_gwh": [20.0, 20.0, 20.0, 19.0]})
    m = {x["id"]: x for x in metricas_hito("energia", fin, ope, [])}
    assert m["margen_energia"]["cumple"] is True          # 30 % >= 28 %
    assert m["almacenamiento_12m"]["valor"] == pytest.approx(79.0)
    assert m["almacenamiento_12m"]["cumple"] is False


def test_crecimiento_4t_none_con_trimestre_ausente_en_medio():
    ope = pd.DataFrame({"period": ["2025Q1", "2025Q2", "2025Q3", "2025Q4", "2026Q2"],
                        "fsd_subscriptions": [1.0e6, 1.2e6, 1.4e6, 1.6e6, 2.6e6]})   # falta 2026Q1
    m = {x["id"]: x for x in metricas_hito("fsd", pd.DataFrame(), ope, [])}
    assert m["crecimiento_4t"]["cumple"] is None


def test_almacenamiento_none_con_trimestre_faltante_en_medio():
    # Cuatro filas presentes (mismo recuento que la ventana de 4), pero falta 2026Q1 en medio.
    ope = pd.DataFrame({"period": ["2025Q2", "2025Q3", "2025Q4", "2026Q2"],
                        "storage_deployed_gwh": [20.0, 20.0, 20.0, 20.0]})
    fin = pd.DataFrame([{"period": p, "revenue_energy_segment": 10.0, "gross_profit_energy_segment": 3.0}
                        for p in ("2025Q3", "2025Q4", "2026Q1", "2026Q2")])
    m = {x["id"]: x for x in metricas_hito("energia", fin, ope, [])}
    assert m["almacenamiento_12m"]["cumple"] is None


def test_margen_none_con_trimestre_faltante_en_medio():
    # Cuatro filas presentes, pero falta 2025Q4 en medio de la ventana de 4 trimestres.
    filas = [
        {"period": "2025Q2", "revenue_auto_segment": 100.0, "revenue_reg_credits": 0.0,
         "gross_profit_auto_segment": 21.0, "operating_income": 11.0, "revenue_total": 100.0},
        {"period": "2025Q3", "revenue_auto_segment": 100.0, "revenue_reg_credits": 0.0,
         "gross_profit_auto_segment": 21.0, "operating_income": 11.0, "revenue_total": 100.0},
        {"period": "2026Q1", "revenue_auto_segment": 100.0, "revenue_reg_credits": 0.0,
         "gross_profit_auto_segment": 21.0, "operating_income": 11.0, "revenue_total": 100.0},
        {"period": "2026Q2", "revenue_auto_segment": 100.0, "revenue_reg_credits": 0.0,
         "gross_profit_auto_segment": 21.0, "operating_income": 11.0, "revenue_total": 100.0},
    ]
    fin = pd.DataFrame(filas)
    ope = pd.DataFrame({"period": [], "deliveries_total": []})
    m = {x["id"]: x for x in metricas_hito("automovil", fin, ope, [])}
    assert m["margen_auto_sin_creditos"]["cumple"] is None


def test_margen_none_con_nan_dentro_de_la_ventana():
    filas = [
        {"period": "2025Q3", "revenue_auto_segment": 100.0, "revenue_reg_credits": 0.0,
         "gross_profit_auto_segment": 21.0, "operating_income": 11.0, "revenue_total": 100.0},
        {"period": "2025Q4", "revenue_auto_segment": 100.0, "revenue_reg_credits": float("nan"),
         "gross_profit_auto_segment": 21.0, "operating_income": 11.0, "revenue_total": 100.0},
        {"period": "2026Q1", "revenue_auto_segment": 100.0, "revenue_reg_credits": 0.0,
         "gross_profit_auto_segment": 21.0, "operating_income": 11.0, "revenue_total": 100.0},
        {"period": "2026Q2", "revenue_auto_segment": 100.0, "revenue_reg_credits": 0.0,
         "gross_profit_auto_segment": 21.0, "operating_income": 11.0, "revenue_total": 100.0},
    ]
    fin = pd.DataFrame(filas)
    ope = pd.DataFrame({"period": [], "deliveries_total": []})
    m = {x["id"]: x for x in metricas_hito("automovil", fin, ope, [])}
    assert m["margen_auto_sin_creditos"]["cumple"] is None


def test_metricas_con_filas_desordenadas_y_un_trimestre_bajo_el_umbral():
    filas = [{"period": p, "revenue_auto_segment": 100.0, "revenue_reg_credits": 0.0,
              "gross_profit_auto_segment": v, "operating_income": 11.0, "revenue_total": 100.0}
             for p, v in [("2026Q2", 21.0), ("2025Q3", 21.0), ("2026Q1", 15.0), ("2025Q4", 21.0)]]
    fin = pd.DataFrame(filas)
    ope = pd.DataFrame({"period": [], "deliveries_total": []})
    m = {x["id"]: x for x in metricas_hito("automovil", fin, ope, [])}
    assert m["margen_auto_sin_creditos"]["valor"] == pytest.approx(0.15)
    assert m["margen_auto_sin_creditos"]["cumple"] is False


def test_crecimiento_4t_cuenta_subidas_seguidas():
    ope = pd.DataFrame({"period": ["2025Q2", "2025Q3", "2025Q4", "2026Q1", "2026Q2"],
                        "fsd_subscriptions": [2.0e6, 1.8e6, 2.0e6, 2.2e6, 2.4e6]})
    m = {x["id"]: x for x in metricas_hito("fsd", pd.DataFrame(), ope, [])}
    assert m["crecimiento_4t"]["valor"] == 3 and m["crecimiento_4t"]["umbral"] == 4
    assert m["crecimiento_4t"]["cumple"] is False


# --------------------------------------------------------------------------
# estado_hito
# --------------------------------------------------------------------------

@pytest.mark.parametrize("pasos, metricas, estancado, esperado", [
    ([{"id": "a", "cumplido": _evidencia()}], [], None, "logrado"),
    ([{"id": "a", "cumplido": _evidencia()}, {"id": "b", "cumplido": None}], [], None, "en curso"),
    ([{"id": "a", "cumplido": None}], [{"cumple": False}], None, "no iniciado"),
    ([], [{"cumple": True}, {"cumple": None}], None, "en curso"),
    ([], [{"cumple": True}, {"cumple": True}], None, "logrado"),
    ([], [], None, "no iniciado"),
])
def test_estado_hito(pasos, metricas, estancado, esperado):
    hito = {"pasos": pasos, "requeridos": [p["id"] for p in pasos], "estancado": estancado}
    assert estado_hito(hito, metricas)["estado"] == esperado


def test_estancado_se_muestra_aparte():
    # El estado calculado no lo sustituye "estancado" (spec 4.1): con requeridos vacios
    # y la unica metrica en umbral, el estado calculado es "logrado"; la marca
    # "estancado" se anade aparte, sin cambiarlo.
    hito = {"pasos": [], "requeridos": [], "estancado": {"desde": "2026-01-01", "motivo": "x"}}
    r = estado_hito(hito, [{"cumple": True}])
    assert r["estado"] == "logrado" and r["estancado"]["motivo"] == "x"


def test_estado_hito_con_estancado_real_y_no_logrado():
    hito = {"pasos": [{"id": "a", "cumplido": None}], "requeridos": ["a"],
            "estancado": {"desde": "2026-01-01", "motivo": "bloqueo regulatorio", "fuente": "x"}}
    r = estado_hito(hito, [])
    assert r["estado"] == "no iniciado" and r["estancado"]["motivo"] == "bloqueo regulatorio"


# --------------------------------------------------------------------------
# transversal_caja (fix importante 2)
# --------------------------------------------------------------------------

def test_transversal_caja():
    fin = pd.DataFrame([{"period": p, "capex": c, "ocf": o} for p, c, o in
                        [("2025Q3", 3e9, 4e9), ("2025Q4", 3e9, 4e9), ("2026Q1", 4e9, 5e9), ("2026Q2", 4.3e9, 5e9)]])
    guia = {"anio": 2026, "importe": 25e9, "texto": "mas de 25.000 millones"}
    r = transversal_caja(fin, guia)
    assert r["capex_anio"] == pytest.approx(8.3e9) and r["trimestres_anio"] == 2
    assert r["capex_restante"] == pytest.approx(16.7e9)
    assert r["fcf_12m"] == pytest.approx(18e9 - 14.3e9)
    assert r["completo"] is True


def test_transversal_caja_sin_trimestres_del_anio():
    fin = pd.DataFrame([{"period": p, "capex": c, "ocf": o} for p, c, o in
                        [("2025Q1", 3e9, 4e9), ("2025Q2", 3e9, 4e9),
                         ("2025Q3", 3e9, 4e9), ("2025Q4", 3e9, 4e9)]])
    guia = {"anio": 2026, "importe": 25e9, "texto": "mas de 25.000 millones"}
    r = transversal_caja(fin, guia)
    assert r["capex_anio"] == 0.0 and r["trimestres_anio"] == 0 and r["completo"] is True
    assert r["capex_restante"] == pytest.approx(25e9)


def test_transversal_caja_con_hueco_es_incompleto():
    fin = pd.DataFrame([{"period": p, "capex": c, "ocf": o} for p, c, o in
                        [("2025Q4", 3e9, 4e9), ("2026Q1", 4e9, 5e9),
                         ("2026Q3", 4e9, 5e9), ("2026Q4", 4e9, 5e9)]])       # falta 2026Q2
    guia = {"anio": 2026, "importe": 25e9, "texto": "mas de 25.000 millones"}
    r = transversal_caja(fin, guia)
    assert r["capex_anio"] is None and r["trimestres_anio"] is None
    assert r["capex_restante"] is None and r["completo"] is False


def test_transversal_caja_con_nan_es_incompleto():
    fin = pd.DataFrame([{"period": "2026Q1", "capex": float("nan"), "ocf": 5e9},
                        {"period": "2026Q2", "capex": 4e9, "ocf": 5e9}])
    guia = {"anio": 2026, "importe": 25e9, "texto": "x"}
    r = transversal_caja(fin, guia)
    assert r["completo"] is False and r["capex_anio"] is None


def test_fcf_none_si_faltan_trimestres():
    fin = pd.DataFrame([{"period": p, "capex": 3e9, "ocf": 4e9} for p in ("2026Q1", "2026Q2", "2026Q3")])
    guia = {"anio": 2027, "importe": 25e9, "texto": "x"}
    r = transversal_caja(fin, guia)
    assert r["fcf_12m"] is None
    assert r["capex_anio"] == 0.0 and r["trimestres_anio"] == 0 and r["completo"] is True


# --------------------------------------------------------------------------
# nota de un paso
# --------------------------------------------------------------------------

def test_nota_de_paso_valida_si_es_texto():
    validar(_romper(lambda d: d["hitos"][0]["pasos"][0].update(nota="Aclaracion breve")))


def test_nota_de_paso_debe_ser_texto():
    with pytest.raises(HitosInvalidos, match="nota"):
        validar(_romper(lambda d: d["hitos"][0]["pasos"][0].update(nota=["no", "texto"])))


# --------------------------------------------------------------------------
# construir_hitos
# --------------------------------------------------------------------------

FIN_AUTO_OK = pd.DataFrame([{"period": p, "revenue_auto_segment": 100.0, "revenue_reg_credits": 0.0,
                             "gross_profit_auto_segment": 21.0, "operating_income": 11.0,
                             "revenue_total": 100.0, "capex": 1e9, "ocf": 2e9}
                            for p in ("2025Q3", "2025Q4", "2026Q1", "2026Q2")])
OPE_AUTO_OK = pd.DataFrame([{"period": p, "deliveries_total": d} for p, d in
                            zip(["2024Q3", "2024Q4", "2025Q1", "2025Q2",
                                 "2025Q3", "2025Q4", "2026Q1", "2026Q2"],
                                [100, 100, 100, 100, 100, 100, 100, 101])])


def _por_id(salida):
    return {h["id"]: h for h in salida["hitos"]}


def test_construir_hitos_claves_y_orden():
    r = construir_hitos(datos_minimos(), FIN_AUTO_OK, OPE_AUTO_OK, HOY)
    assert {"version", "hitos", "historial", "indice", "transversal"} <= set(r)
    assert [h["prioridad"] for h in r["hitos"]] == [1, 2, 3, 4, 5, 6]
    assert r["transversal"]["caja"]["anio"] == 2026
    assert r["transversal"]["seguridad"][0]["id"] == "nhtsa-fsd"
    json.dumps(r, allow_nan=False)


def test_construir_hitos_normaliza_fechas_a_texto_iso():
    # yaml.safe_load devuelve date para las fechas sin comillas.
    def cambio(d):
        d["hitos"][0]["promesas"][0]["declarada"] = date(2024, 6, 13)
        d["historial"][0]["cumplimiento"]["fecha"] = date(2023, 11, 30)
        d["transversal"]["seguridad"][0]["abierta_desde"] = datetime(2024, 10, 17, 9, 0)
    r = construir_hitos(validar(_romper(cambio)), FIN_AUTO_OK, OPE_AUTO_OK, HOY)
    texto = json.dumps(r, allow_nan=False)      # sin default=str
    assert _por_id(r)["optimus"]["promesas"][0]["declarada"] == "2024-06-13"
    assert r["historial"][0]["cumplimiento"]["fecha"] == "2023-11-30"
    assert r["transversal"]["seguridad"][0]["abierta_desde"] == "2024-10-17"
    assert "2024-06-13" in texto


def test_prioritario_no_logrado_entra_en_el_indice_como_vigente():
    r = construir_hitos(datos_minimos(), FIN_AUTO_OK, OPE_AUTO_OK, HOY)
    optimus = _por_id(r)["optimus"]
    assert optimus["estado"] == "no iniciado"
    assert len(optimus["grupos_promesas"]) == 1
    grupo = optimus["grupos_promesas"][0]
    assert grupo["paso"] is None and grupo["texto"] == "el hito completo"
    assert grupo["deslizamiento"]["tipo"] == "minimo"          # prometido para 2025
    assert grupo["en_indice"] is True
    assert optimus["en_indice"] is True
    todas = r["indice"]["todas"]
    assert todas["cumplidos"] == 1 and todas["retrasados"] == 1   # cybertruck + optimus


def test_prioritario_logrado_entra_como_cumplido_con_la_evidencia_mas_tardia():
    def cambio(d):
        optimus = d["hitos"][0]
        optimus["pasos"] = [
            {"id": "a", "texto": "a", "etiqueta": "R", "cumplido": _evidencia("2025-11-30")},
            {"id": "b", "texto": "b", "etiqueta": "R", "cumplido": _evidencia("2026-02-28")},
            {"id": "c", "texto": "c", "etiqueta": "R", "cumplido": _evidencia("2026-08-31")},
        ]
        optimus["requeridos"] = ["a", "b"]           # c no cuenta para la fecha
    r = construir_hitos(validar(_romper(cambio)), FIN_AUTO_OK, OPE_AUTO_OK, HOY)
    optimus = _por_id(r)["optimus"]
    assert optimus["estado"] == "logrado"
    assert optimus["cumplimiento"] == {"fecha": "2026-02-28"}
    grupo = optimus["grupos_promesas"][0]
    assert grupo["cumplimiento"] == {"fecha": "2026-02-28"}
    assert grupo["deslizamiento"]["tipo"] == "realizado"
    assert grupo["deslizamiento"]["meses"] == pytest.approx(meses_entre(date(2025, 12, 31),
                                                                            date(2026, 2, 28)))
    todas = r["indice"]["todas"]
    assert todas["cumplidos"] == 2 and todas["retrasados"] == 0


def test_logrado_solo_con_metricas_no_entra_en_el_indice():
    def cambio(d):
        auto = next(h for h in d["hitos"] if h["id"] == "automovil")
        auto["promesas"] = [_promesa("2024-01-01", "2024")]
    r = construir_hitos(validar(_romper(cambio)), FIN_AUTO_OK, OPE_AUTO_OK, HOY)
    auto = _por_id(r)["automovil"]
    assert auto["estado"] == "logrado"
    assert auto["grupos_promesas"][0]["en_indice"] is False
    assert auto["grupos_promesas"][0]["barra"] is None
    assert auto["en_indice"] is False and auto["cumplimiento"] is None
    todas = r["indice"]["todas"]
    assert todas["cumplidos"] == 1 and todas["retrasados"] == 1   # cybertruck + optimus


def test_fechas_prometidas_en_orden_de_declaracion():
    def cambio(d):
        d["hitos"][0]["promesas"] = [_promesa("2025-01-01", "2026-Q2"), _promesa("2024-06-13", "2025")]
    r = construir_hitos(validar(_romper(cambio)), FIN_AUTO_OK, OPE_AUTO_OK, HOY)
    optimus = _por_id(r)["optimus"]
    assert optimus["grupos_promesas"][0]["fechas_prometidas"] == ["2025-12-31", "2026-06-30"]
    assert r["historial"][0]["fechas_prometidas"] == ["2020-12-31"]
    assert r["hoy"] == "2026-09-23"


def test_construir_hitos_sin_capex_guia():
    r = construir_hitos(_romper(lambda d: d["transversal"].pop("capex_guia")),
                        FIN_AUTO_OK, OPE_AUTO_OK, HOY)
    assert r["transversal"]["caja"] is None


def test_cargar_yaml_mal_formado_da_hitos_invalidos(tmp_path):
    ruta = tmp_path / "milestones.yaml"
    ruta.write_text("version: [sin cerrar\n", encoding="utf-8")
    with pytest.raises(HitosInvalidos, match="YAML"):
        cargar(ruta)


def test_validar_raiz_debe_ser_objeto():
    with pytest.raises(HitosInvalidos, match="raiz"):
        validar(["no", "es", "un", "objeto"])


def test_construir_hitos_expone_promesa_vigente_base_de_mercados_y_fuente_de_la_guia():
    def cambio(d):
        d["hitos"][0]["promesas"] = [_promesa("2025-01-01", "2026-Q2"), _promesa("2024-06-13", "2025")]
    r = construir_hitos(validar(_romper(cambio)), FIN_AUTO_OK, OPE_AUTO_OK, HOY)
    assert _por_id(r)["optimus"]["grupos_promesas"][0]["promesa_vigente"]["fecha_prometida"] == "2026-Q2"
    assert _por_id(r)["fsd"]["grupos_promesas"] == []
    assert r["historial"][0]["promesa_vigente"]["fecha_prometida"] == "2020"
    assert r["fecha_base_mercados"] == "2026-09-23"
    assert r["transversal"]["caja"]["enlace"] == ENLACE
    assert r["transversal"]["caja"]["fuente"] == "Update Letter"


# --------------------------------------------------------------------------
# promesas ligadas a un paso (decision del usuario)
# --------------------------------------------------------------------------

def _con_paso(promesa, paso):
    return {**promesa, "paso": paso}


def test_promesa_con_paso_inexistente():
    def cambio(d):
        d["hitos"][0]["promesas"][0]["paso"] = "no-existe"
    with pytest.raises(HitosInvalidos, match="paso"):
        validar(_romper(cambio))


def test_paso_en_el_historial_se_rechaza():
    def cambio(d):
        d["historial"][0]["promesas"][0]["paso"] = "produccion"
    with pytest.raises(HitosInvalidos, match="paso"):
        validar(_romper(cambio))


def test_promesa_con_paso_existente_valida():
    validar(_romper(lambda d: d["hitos"][0]["promesas"][0].update(paso="produccion")))


def test_promesa_repetida_en_dos_entradas_se_rechaza():
    def cambio(d):
        semi = next(h for h in d["hitos"] if h["id"] == "semi")
        semi["promesas"] = [copy.deepcopy(d["historial"][0]["promesas"][0])]
    with pytest.raises(HitosInvalidos, match="repetida"):
        validar(_romper(cambio))


def test_promesa_con_otra_cita_no_es_repetida():
    def cambio(d):
        otra = copy.deepcopy(d["historial"][0]["promesas"][0])
        otra["cita"] = "otra frase"
        next(h for h in d["hitos"] if h["id"] == "semi")["promesas"] = [otra]
    validar(_romper(cambio))


def _energia_con_paso_cumplido(d):
    energia = next(h for h in d["hitos"] if h["id"] == "energia")
    energia["pasos"] = [{"id": "texas", "texto": "Texas", "etiqueta": "R",
                         "cumplido": _evidencia("2026-08-06")}]
    energia["requeridos"] = ["texas"]
    energia["promesas"] = [_con_paso(_promesa("2025-10-22", "2026"), "texas")]


def test_promesa_de_paso_cumplido_cuenta_aunque_las_metricas_no_lleguen():
    # FIN_AUTO_OK no trae columnas de energia: las metricas quedan sin dato y el
    # hito no esta logrado, pero la promesa apuntaba al paso, que si se cumplio.
    r = construir_hitos(validar(_romper(_energia_con_paso_cumplido)), FIN_AUTO_OK, OPE_AUTO_OK, HOY)
    energia = _por_id(r)["energia"]
    assert energia["estado"] == "en curso"
    grupo = energia["grupos_promesas"][0]
    assert grupo["paso"] == "texas" and grupo["texto"] == "Texas"
    assert grupo["en_indice"] is True
    assert grupo["cumplimiento"] == {"fecha": "2026-08-06"}
    assert grupo["deslizamiento"]["tipo"] == "realizado"
    assert grupo["deslizamiento"]["meses"] < 0                    # antes del fin de 2026
    assert grupo["barra"] == {"desde": "2026-12-31", "hasta": "2026-08-06",
                              "tipo": "adelantado", "invertida": True}
    assert r["indice"]["todas"]["cumplidos"] == 2                 # cybertruck + texas


def test_grupos_con_y_sin_paso_en_el_mismo_hito():
    def cambio(d):
        optimus = d["hitos"][0]
        optimus["pasos"] = [
            {"id": "a", "texto": "Paso A", "etiqueta": "R", "cumplido": _evidencia("2025-06-30")},
            {"id": "b", "texto": "Paso B", "etiqueta": "R", "cumplido": None},
        ]
        optimus["requeridos"] = ["a", "b"]
        optimus["promesas"] = [
            _promesa("2024-01-10", "2027"),                                  # hito completo
            _con_paso(_promesa("2024-01-01", "2025"), "b"),
            _con_paso(_promesa("2023-01-01", "2024"), "a"),
            _con_paso(_promesa("2024-02-01", "2025-Q2"), "a"),
        ]
    r = construir_hitos(validar(_romper(cambio)), FIN_AUTO_OK, OPE_AUTO_OK, HOY)
    grupos = _por_id(r)["optimus"]["grupos_promesas"]
    assert [g["paso"] for g in grupos] == ["a", "b", None]            # orden de los pasos; completo al final
    a, b, completo = grupos
    assert a["deslizamiento"]["tipo"] == "realizado" and a["deslizamiento"]["re_promesas"] == 1
    assert a["cumplimiento"] == {"fecha": "2025-06-30"}
    assert a["barra"]["tipo"] == "cumplido" and a["barra"]["hasta"] == "2025-06-30"
    assert b["deslizamiento"]["tipo"] == "minimo" and b["cumplimiento"] is None
    assert b["barra"] == {"desde": "2025-12-31", "hasta": "2026-09-23", "tipo": "retrasado",
                          "invertida": False}
    assert completo["texto"] == "el hito completo"
    assert completo["deslizamiento"]["tipo"] == "a_tiempo"
    assert completo["barra"]["tipo"] == "en_plazo" and completo["barra"]["invertida"] is True
    todas = r["indice"]["todas"]
    # historial (cybertruck, realizado) + a (realizado) + b (minimo) + completo (a tiempo)
    assert (todas["cumplidos"], todas["retrasados"], todas["a_tiempo"]) == (2, 1, 1)


def test_indice_oficial_con_prioritarios_y_un_hito_sin_promesas_oficiales():
    def cambio(d):
        d["hitos"][0]["promesas"] = [_promesa("2024-06-13", "2025", "musk")]   # solo Musk
        semi = next(h for h in d["hitos"] if h["id"] == "semi")
        semi["promesas"] = [_promesa("2023-01-01", "2024", "musk"),
                            _promesa("2024-01-01", "2025", "oficial")]
    r = construir_hitos(validar(_romper(cambio)), FIN_AUTO_OK, OPE_AUTO_OK, HOY)
    optimus = _por_id(r)["optimus"]["grupos_promesas"][0]
    assert optimus["deslizamiento_oficial"] is None
    semi = _por_id(r)["semi"]["grupos_promesas"][0]
    assert semi["deslizamiento_oficial"]["primera"] == "2025-12-31"
    todas, oficiales = r["indice"]["todas"], r["indice"]["oficiales"]
    assert (todas["cumplidos"], todas["retrasados"]) == (1, 2)          # cybertruck; optimus, semi
    assert (oficiales["cumplidos"], oficiales["retrasados"]) == (1, 1)  # cybertruck; semi
    assert oficiales["minimo"]["n"] == 2
    assert oficiales["minimo"]["media"] == pytest.approx(
        (meses_entre(date(2020, 12, 31), date(2023, 11, 30)) + meses_entre(date(2025, 12, 31), HOY)) / 2)


def test_pct_cumplidos_del_historial():
    def cambio(d):
        d["historial"].append({"id": "roadster", "titulo": "Roadster", "criterio": "Entregas",
                               "promesas": [_promesa("2017-11-16", "2020", "musk")],
                               "estado": "vigente"})
    r = construir_hitos(validar(_romper(cambio)), FIN_AUTO_OK, OPE_AUTO_OK, HOY)
    assert r["indice"]["pct_cumplidos_historial"] == {"cumplidos": 1, "total": 2, "valor": 0.5}


def test_pct_cumplidos_del_historial_vacio():
    r = construir_hitos(_romper(lambda d: d.update(historial=[])), FIN_AUTO_OK, OPE_AUTO_OK, HOY)
    assert r["indice"]["pct_cumplidos_historial"] == {"cumplidos": 0, "total": 0, "valor": None}


def test_barra_del_historial():
    def cambio(d):
        d["historial"].append({"id": "roadster", "titulo": "Roadster", "criterio": "Entregas",
                               "promesas": [_promesa("2017-11-16", "2020", "musk"),
                                            _promesa("2019-01-01", "2021", "musk")],
                               "estado": "abandonado"})
    r = construir_hitos(validar(_romper(cambio)), FIN_AUTO_OK, OPE_AUTO_OK, HOY)
    cyber, roadster = r["historial"]
    assert cyber["barra"] == {"desde": "2020-12-31", "hasta": "2023-11-30", "tipo": "cumplido",
                              "invertida": False}
    assert roadster["barra"] == {"desde": "2020-12-31", "hasta": "2021-12-31", "tipo": "abandonado",
                                 "invertida": False}


def test_meses_vigente_vs_primera():
    h = {"promesas": [_promesa("2019-01-01", "2020"), _promesa("2020-06-01", "2021-Q2")]}
    d = deslizamiento(h, HOY, False)
    assert d["meses_vigente_vs_primera"] == pytest.approx(meses_entre(date(2020, 12, 31), date(2021, 6, 30)))
    h1 = {"promesas": [_promesa("2019-01-01", "2020")], "estado": "abandonado"}
    assert deslizamiento(h1, HOY, False)["meses_vigente_vs_primera"] == 0


# --------------------------------------------------------------------------
# transversal_caja: cifras derivadas para la pagina
# --------------------------------------------------------------------------

GUIA = {"anio": 2026, "importe": 25e9, "texto": "x"}


def test_transversal_caja_cuota_y_trimestres_restantes():
    fin = pd.DataFrame([{"period": p, "capex": c, "ocf": o} for p, c, o in
                        [("2025Q3", 3e9, 4e9), ("2025Q4", 3e9, 4e9), ("2026Q1", 4e9, 5e9), ("2026Q2", 4.3e9, 5e9)]])
    r = transversal_caja(fin, GUIA)
    assert r["cuota_guia"] == pytest.approx(8.3 / 25)
    assert r["trimestres_restantes"] == 2
    assert r["capex_por_trimestre_restante"] == pytest.approx(16.7e9 / 2)
    assert r["motivo_incompleto"] is None


def test_transversal_caja_anio_cerrado_sin_trimestres_restantes():
    fin = pd.DataFrame([{"period": f"2026Q{q}", "capex": 7e9, "ocf": 8e9} for q in (1, 2, 3, 4)])
    r = transversal_caja(fin, GUIA)
    assert r["trimestres_restantes"] == 0 and r["capex_por_trimestre_restante"] is None
    assert r["capex_restante"] == pytest.approx(-3e9) and r["cuota_guia"] == pytest.approx(28 / 25)


def test_transversal_caja_guia_superada_no_da_capex_negativo_por_trimestre():
    fin = pd.DataFrame([{"period": "2026Q1", "capex": 26e9, "ocf": 8e9}])
    r = transversal_caja(fin, GUIA)
    assert r["capex_por_trimestre_restante"] == 0.0


@pytest.mark.parametrize("filas, motivo", [
    ([("2026Q1", 4e9), ("2026Q3", 4e9)], "falta algún trimestre del año"),
    ([("2026Q1", float("nan")), ("2026Q2", 4e9)], "hay trimestres sin dato"),
])
def test_transversal_caja_motivo_incompleto(filas, motivo):
    fin = pd.DataFrame([{"period": p, "capex": c, "ocf": 5e9} for p, c in filas])
    r = transversal_caja(fin, GUIA)
    assert r["completo"] is False and r["motivo_incompleto"] == motivo
    assert r["cuota_guia"] is None and r["trimestres_restantes"] is None
    assert r["capex_por_trimestre_restante"] is None


def test_transversal_caja_sin_columna_capex():
    fin = pd.DataFrame([{"period": "2026Q1", "ocf": 5e9}])
    r = transversal_caja(fin, GUIA)
    assert r["completo"] is False and r["motivo_incompleto"] == "falta la columna capex"
    assert r["fcf_12m"] is None


def test_promesa_declarada_despues_del_cumplimiento_de_su_paso_se_rechaza():
    def cambio(d):
        optimus = d["hitos"][0]
        optimus["pasos"][0]["cumplido"] = _evidencia("2024-06-01")
        optimus["promesas"] = [_con_paso(_promesa("2024-06-13", "2025"), "produccion")]
    with pytest.raises(HitosInvalidos, match="posterior al cumplimiento"):
        validar(_romper(cambio))


def test_promesa_declarada_el_dia_del_cumplimiento_de_su_paso_valida():
    def cambio(d):
        optimus = d["hitos"][0]
        optimus["pasos"][0]["cumplido"] = _evidencia("2024-06-13")
        optimus["promesas"] = [_con_paso(_promesa("2024-06-13", "2025"), "produccion")]
    validar(_romper(cambio))
