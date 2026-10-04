import pandas as pd
import pytest

from src.schema import Campo, Esquema
from src.validate import (
    ErrorValidacion, periodos_esperados, validar, validar_continuidad,
    validar_continuidad_mensual,
)

ESQ = Esquema(
    nombre="prueba",
    clave=["period"],
    campos=[
        Campo("period", "str", "texto"),
        Campo("valor", "float", "USD", minimo=0, maximo=100),
        Campo("opcional", "float", "USD", obligatorio=False),
        Campo("source", "str", "texto"),
        Campo("retrieved_at", "str", "fecha"),
    ],
)


def marco(**cambios):
    base = {
        "period": ["2019Q1", "2019Q2"],
        "valor": [10.0, 20.0],
        "opcional": [None, None],
        "source": ["edgar", "edgar"],
        "retrieved_at": ["2026-09-22", "2026-09-22"],
    }
    base.update(cambios)
    return pd.DataFrame(base)


def test_un_marco_correcto_pasa():
    validar(marco(), ESQ)


def test_detecta_columna_obligatoria_ausente():
    df = marco().drop(columns=["valor"])
    with pytest.raises(ErrorValidacion, match="falta la columna 'valor'"):
        validar(df, ESQ)


def test_una_columna_opcional_puede_faltar():
    validar(marco().drop(columns=["opcional"]), ESQ)


def test_detecta_valor_por_encima_del_maximo():
    with pytest.raises(ErrorValidacion, match="fuera de rango"):
        validar(marco(valor=[10.0, 500.0]), ESQ)


def test_detecta_valor_por_debajo_del_minimo():
    with pytest.raises(ErrorValidacion, match="fuera de rango"):
        validar(marco(valor=[-1.0, 20.0]), ESQ)


def test_detecta_clave_duplicada():
    with pytest.raises(ErrorValidacion, match="duplicad"):
        validar(marco(period=["2019Q1", "2019Q1"]), ESQ)


def test_detecta_nulo_en_campo_obligatorio():
    with pytest.raises(ErrorValidacion, match="nulos"):
        validar(marco(valor=[10.0, None]), ESQ)


def test_periodos_esperados_genera_la_serie_trimestral():
    assert periodos_esperados("2019Q1", "2019Q4") == [
        "2019Q1", "2019Q2", "2019Q3", "2019Q4"
    ]


def test_periodos_esperados_cruza_el_cambio_de_anio():
    assert periodos_esperados("2019Q3", "2020Q2") == [
        "2019Q3", "2019Q4", "2020Q1", "2020Q2"
    ]


def test_continuidad_acepta_una_serie_sin_huecos():
    validar_continuidad(["2019Q1", "2019Q2", "2019Q3"], "2019Q1", "2019Q3")


def test_continuidad_detecta_un_trimestre_ausente():
    with pytest.raises(ErrorValidacion, match="2019Q2"):
        validar_continuidad(["2019Q1", "2019Q3"], "2019Q1", "2019Q3")


def test_periodos_esperados_acepta_un_unico_trimestre():
    assert periodos_esperados("2019Q1", "2019Q1") == ["2019Q1"]


def test_periodos_esperados_rechaza_un_rango_invertido():
    """Devolver una lista vacia convertiria validar_continuidad en un no-op."""
    with pytest.raises(ValueError, match="invertido"):
        periodos_esperados("2020Q1", "2019Q1")


def test_periodos_esperados_rechaza_un_trimestre_imposible():
    with pytest.raises(ValueError, match="trimestre"):
        periodos_esperados("2019Q5", "2020Q1")


def test_continuidad_mensual_acepta_una_serie_sin_huecos():
    validar_continuidad_mensual(["2024-01", "2024-02", "2024-03"])


def test_continuidad_mensual_detecta_un_mes_ausente():
    with pytest.raises(ErrorValidacion, match="2024-02"):
        validar_continuidad_mensual(["2024-01", "2024-03"])
