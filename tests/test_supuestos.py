import copy
import datetime

import pytest
import yaml

from src.supuestos import (
    SupuestosInvalidos, cargar_supuestos, comprobar_congelacion, huella,
    validar_supuestos,
)


def test_unos_supuestos_completos_validan(supuestos):
    assert validar_supuestos(supuestos) is supuestos


def test_falta_un_campo_de_unidad(supuestos):
    roto = copy.deepcopy(supuestos)
    del roto["escenarios"]["base"]["energia"]["ventas_sobre_capital"]
    with pytest.raises(SupuestosInvalidos, match="base.energia.*ventas_sobre_capital"):
        validar_supuestos(roto)


def test_un_valor_fuera_de_rango(supuestos):
    roto = copy.deepcopy(supuestos)
    roto["escenarios"]["bull"]["automocion"]["margen_bruto_final"] = 1.5
    with pytest.raises(SupuestosInvalidos, match="fuera de"):
        validar_supuestos(roto)


def test_falta_un_escenario(supuestos):
    roto = copy.deepcopy(supuestos)
    del roto["escenarios"]["bear"]
    with pytest.raises(SupuestosInvalidos, match="bear"):
        validar_supuestos(roto)


def test_roic_terminal_debe_superar_al_crecimiento_terminal(supuestos):
    roto = copy.deepcopy(supuestos)
    roto["comun"]["roic_terminal"] = 0.02
    roto["comun"]["crecimiento_terminal"] = 0.03
    with pytest.raises(SupuestosInvalidos, match="roic_terminal"):
        validar_supuestos(roto)


def test_horizonte_anios_debe_ser_un_entero(supuestos):
    roto = copy.deepcopy(supuestos)
    roto["comun"]["horizonte_anios"] = 10.5
    with pytest.raises(SupuestosInvalidos, match="entero"):
        validar_supuestos(roto)


def test_la_version_debe_ser_texto(supuestos):
    """YAML convierte 2026-09-22 sin comillas en fecha: hay que entrecomillarla."""
    roto = copy.deepcopy(supuestos)
    roto["version"] = datetime.date(2026, 9, 22)
    with pytest.raises(SupuestosInvalidos, match="comillas"):
        validar_supuestos(roto)


def test_cargar_supuestos_desde_yaml(tmp_path, supuestos):
    ruta = tmp_path / "assumptions.yaml"
    ruta.write_text(yaml.safe_dump(supuestos), encoding="utf-8")
    cargados, h = cargar_supuestos(ruta)
    assert cargados["comun"]["horizonte_anios"] == 10
    assert h == huella(ruta.read_text(encoding="utf-8"))


def test_la_huella_cambia_con_el_contenido():
    assert huella("a: 1") != huella("a: 2")
    assert huella("a: 1") == huella("a: 1")


def test_cambiar_supuestos_sin_cambiar_la_version_se_detiene():
    """La disciplina que evita retocar el modelo para validar el precio del dia."""
    anterior = {"version_supuestos": "2026-09-22", "huella": "aaaa"}
    with pytest.raises(SupuestosInvalidos, match="version"):
        comprobar_congelacion("2026-09-22", "bbbb", anterior)


def test_cambiar_supuestos_con_version_nueva_se_permite():
    comprobar_congelacion("2026-10-23", "bbbb", {"version_supuestos": "2026-09-22", "huella": "aaaa"})


def test_sin_valoracion_previa_no_hay_nada_que_comprobar():
    comprobar_congelacion("2026-09-22", "aaaa", None)
