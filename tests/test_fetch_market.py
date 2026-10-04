import json

import pytest

from src.fetch_market import (
    RespuestaInesperada, cierres_mensuales, parsear_nasdaq,
)

NASDAQ = json.dumps({"data": {"tradesTable": {"rows": [
    {"date": "01/30/2019", "close": "$20.00"},
    {"date": "01/31/2019", "close": "$21.00"},
    {"date": "02/27/2019", "close": "$22.50"},
    {"date": "02/28/2019", "close": "$1,023.00"},
]}}})


def test_parsear_nasdaq_limpia_fechas_y_precios():
    df = parsear_nasdaq(NASDAQ.encode())
    assert len(df) == 4
    assert df["Close"].iloc[0] == 20.0
    assert str(df["Date"].iloc[0].date()) == "2019-01-30"


def test_parsear_nasdaq_maneja_el_separador_de_miles():
    df = parsear_nasdaq(NASDAQ.encode())
    assert df["Close"].iloc[-1] == 1023.0


def test_parsear_nasdaq_falla_con_una_respuesta_inesperada():
    """Si el endpoint cambia de forma, hay que enterarse, no seguir en silencio."""
    with pytest.raises(RespuestaInesperada):
        parsear_nasdaq(b'{"data": null}')


def test_parsear_nasdaq_falla_si_no_hay_sesiones():
    with pytest.raises(RespuestaInesperada):
        parsear_nasdaq(json.dumps({"data": {"tradesTable": {"rows": []}}}).encode())


def test_cierres_mensuales_toma_el_ultimo_cierre_del_mes():
    serie = cierres_mensuales(parsear_nasdaq(NASDAQ.encode()))
    assert serie["2019-01"] == 21.0
    assert serie["2019-02"] == 1023.0


def test_cierres_mensuales_usa_formato_de_mes_ordenable():
    serie = cierres_mensuales(parsear_nasdaq(NASDAQ.encode()))
    assert sorted(serie) == ["2019-01", "2019-02"]


from src.fetch_market import parsear_tesoro, url_nasdaq, url_tesoro

CSV_TESORO = b"""Date,1 Mo,10 Yr,30 Yr
09/22/2026,4.10,4.96,5.10
09/19/2026,4.08,4.91,5.05
08/29/2026,4.00,4.80,4.95
08/28/2026,4.01,4.82,4.97
"""


def test_parsear_tesoro_toma_el_ultimo_dato_de_cada_mes_en_tanto_por_uno():
    serie = parsear_tesoro(CSV_TESORO)
    assert serie["2026-09"] == pytest.approx(0.0496)
    assert serie["2026-08"] == pytest.approx(0.0480)


def test_parsear_tesoro_falla_si_cambia_el_formato():
    with pytest.raises(RespuestaInesperada):
        parsear_tesoro(b"Fecha,Otra\n01/01/2026,1\n")


def test_url_tesoro_por_anio():
    assert "/2024/all" in url_tesoro(2024)
    assert "field_tdr_date_value=2024" in url_tesoro(2024)


def test_url_nasdaq_admite_otros_simbolos():
    """El indice SPX no esta disponible en la fuente; el ETF SPY si."""
    url = url_nasdaq("2019-01-01", "2026-09-22", simbolo="SPY", clase="etf")
    assert "/quote/SPY/" in url and "assetclass=etf" in url
    assert "/quote/TSLA/" in url_nasdaq("2019-01-01", "2026-09-22")
