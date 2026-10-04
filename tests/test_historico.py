import pandas as pd
import pytest

from src.historico import fila_de_valoracion, leer, registrar
from src.schema import HISTORICO
from src.validate import validar

VALORACION = {
    "fecha": "2026-09-23", "mes_precio": "2026-09", "version_supuestos": "2026-09-23",
    "huella": "abcd", "ttm_hasta": "2026Q2", "precio": 378.9,
    "escenarios": {"bear": {"valor_por_accion": 13.5}, "base": {"valor_por_accion": 24.9},
                   "bull": {"valor_por_accion": 45.3}},
    "crecimiento_implicito": 0.702, "opcionalidad_implicita": 1.398e12,
    "coste_capital": {"wacc": 0.1393},
}


def test_fila_de_valoracion():
    f = fila_de_valoracion(VALORACION)
    assert f["mes"] == "2026-09" and f["vpa_base"] == 24.9 and f["wacc"] == 0.1393
    assert f["crecimiento_implicito"] == 0.702


def test_registrar_anade_y_valida(tmp_path):
    ruta = tmp_path / "h.csv"
    registrar(VALORACION, ruta)
    df = leer(ruta)
    validar(df, HISTORICO)
    assert list(df["mes"]) == ["2026-09"]


def test_el_mismo_mes_se_sustituye(tmp_path):
    ruta = tmp_path / "h.csv"
    registrar(VALORACION, ruta)
    registrar({**VALORACION, "precio": 400.0}, ruta)
    df = pd.read_csv(ruta)
    assert len(df) == 1 and df["precio"].iloc[0] == 400.0


def test_meses_ordenados(tmp_path):
    ruta = tmp_path / "h.csv"
    registrar({**VALORACION, "mes_precio": "2026-10"}, ruta)
    registrar(VALORACION, ruta)
    assert list(pd.read_csv(ruta)["mes"]) == ["2026-09", "2026-10"]


def test_los_textos_se_leen_como_texto(tmp_path):
    """Una huella hexadecimal solo con digitos no debe convertirse en numero."""
    ruta = tmp_path / "h.csv"
    registrar({**VALORACION, "huella": "0123"}, ruta)
    registrar({**VALORACION, "mes_precio": "2026-10", "huella": "0456"}, ruta)
    assert list(leer(ruta)["huella"]) == ["0123", "0456"]


def test_leer_sin_fichero_da_vacio(tmp_path):
    assert leer(tmp_path / "no.csv").empty


def test_crecimiento_implicito_nulo(tmp_path):
    ruta = tmp_path / "h.csv"
    registrar({**VALORACION, "crecimiento_implicito": None}, ruta)
    df = pd.read_csv(ruta)
    validar(df, HISTORICO)
    assert pd.isna(df["crecimiento_implicito"].iloc[0])


def test_sin_deriva_de_decimales_al_registrar_otro_mes(tmp_path):
    """Un valor de 17 cifras significativas no debe cambiar al releer el CSV."""
    ruta = tmp_path / "h.csv"
    precisos = {**VALORACION, "escenarios": {
        "bear": {"valor_por_accion": 13.5}, "base": {"valor_por_accion": 24.867586436823437},
        "bull": {"valor_por_accion": 45.3}}, "coste_capital": {"wacc": 0.13934785863749669}}
    registrar(precisos, ruta)
    linea_original = ruta.read_text(encoding="utf-8").splitlines()[1]
    registrar({**VALORACION, "mes_precio": "2026-10"}, ruta)
    linea_tras_segundo_registro = ruta.read_text(encoding="utf-8").splitlines()[1]
    assert linea_original == linea_tras_segundo_registro
