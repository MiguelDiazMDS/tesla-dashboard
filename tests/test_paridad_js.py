"""El motor de la pagina tiene que dar lo mismo que el de Python."""
import copy
import json
import random

import pytest
import yaml

from src.reverse_dcf import crecimiento_implicito, valor_con_crecimiento
from src.sotp import AnioBase, proyectar, suma_unidades, valor_por_accion
from src.supuestos import validar_supuestos
from tests.nodo import RAIZ, ejecutar

N_CASOS = 500
TOLERANCIA = 1e-9
SEMILLA = 20260923
PUENTE = RAIZ / "tests" / "paridad" / "ejecutar_motor.js"

# Caso valido fijo, de un orden de magnitud parecido al de Tesla, para los limites.
CASO_FIJO = {
    "base": {"ingresos": {"automocion": 75e9, "energia": 11e9},
             "margen_bruto": {"automocion": 0.17, "energia": 0.28},
             "id_sobre_ingresos": 0.06, "sga_sobre_ingresos": 0.055},
    "escenario": {
        "automocion": {"crecimiento_inicial": 0.10, "crecimiento_final": 0.04,
                       "margen_bruto_final": 0.20, "ventas_sobre_capital": 2.0,
                       "ajuste_wacc": 0.0},
        "energia": {"crecimiento_inicial": 0.30, "crecimiento_final": 0.06,
                    "margen_bruto_final": 0.30, "ventas_sobre_capital": 1.5,
                    "ajuste_wacc": 0.01},
        "id_sobre_ingresos_final": 0.05, "sga_sobre_ingresos_final": 0.045},
    "comun": {"horizonte_anios": 10, "tipo_impositivo": 0.21,
              "crecimiento_terminal": 0.025, "roic_terminal": 0.15,
              "reparto_id_automocion": 0.8},
    "wacc": 0.10,
    "balance": {"caja": 16e9, "inversiones": 20e9, "deuda": 8e9, "acciones": 3.5e9},
    "precio": 250.0,
}


def _caso(rng: random.Random) -> dict:
    """Supuestos en los rangos que permite el simulador de la pagina. No se
    fuerza tasa > g ni ROIC > g: los casos que lanzan tambien se comparan."""
    def unidad():
        return {"crecimiento_inicial": rng.uniform(-0.2, 0.8),
                "crecimiento_final": rng.uniform(-0.05, 0.2),
                "margen_bruto_final": rng.uniform(0.05, 0.5),
                "ventas_sobre_capital": rng.uniform(0.5, 6.0),
                "ajuste_wacc": rng.uniform(-0.03, 0.05)}

    return {
        "base": {"ingresos": {"automocion": rng.uniform(20e9, 150e9),
                              "energia": rng.uniform(2e9, 40e9)},
                 "margen_bruto": {"automocion": rng.uniform(0.10, 0.30),
                                  "energia": rng.uniform(0.10, 0.35)},
                 "id_sobre_ingresos": rng.uniform(0.03, 0.10),
                 "sga_sobre_ingresos": rng.uniform(0.03, 0.09)},
        "escenario": {"automocion": unidad(), "energia": unidad(),
                      "id_sobre_ingresos_final": rng.uniform(0.01, 0.15),
                      "sga_sobre_ingresos_final": rng.uniform(0.01, 0.15)},
        "comun": {"horizonte_anios": rng.randint(5, 15),
                  "tipo_impositivo": rng.uniform(0.05, 0.35),
                  "crecimiento_terminal": rng.uniform(0.0, 0.05),
                  "roic_terminal": rng.uniform(0.03, 0.5),
                  "reparto_id_automocion": rng.choice([0.0, 1.0, rng.uniform(0.0, 1.0)])},
        "wacc": rng.uniform(0.05, 0.25),
        "balance": {"caja": rng.uniform(5e9, 40e9), "inversiones": rng.uniform(0, 40e9),
                    "deuda": rng.uniform(0, 20e9), "acciones": rng.uniform(2e9, 4e9)},
        "precio": rng.uniform(5, 600),
    }


def _python(caso: dict) -> dict:
    base = AnioBase(**caso["base"])
    try:
        unidades = proyectar(base, caso["escenario"], caso["comun"], caso["wacc"])
        return {
            "valor_por_accion": valor_por_accion(suma_unidades(unidades),
                                                 **caso["balance"]),
            "unidades": {u: p.valor for u, p in unidades.items()},
            "crecimiento_implicito": crecimiento_implicito(
                caso["precio"], base, caso["escenario"], caso["comun"], caso["wacc"],
                caso["balance"]),
        }
    except ValueError as e:
        return {"error": str(e)}


def _js(casos: list[dict], tmp_path) -> list[dict]:
    ruta = tmp_path / "casos.json"
    ruta.write_text(json.dumps(casos), encoding="utf-8")
    js = json.loads(ejecutar(str(PUENTE), str(ruta)))
    assert len(js) == len(casos)
    return js


def _relativa(a: float, b: float) -> float:
    return abs(a - b) / max(abs(a), abs(b), 1e-300)


def _discrepa(a: float, b: float) -> bool:
    # Escrito asi para que un NaN cuente como discrepancia.
    return not (_relativa(a, b) <= TOLERANCIA)


def _comparar(casos: list[dict], js: list[dict]) -> tuple[list, list[dict]]:
    """Discrepancias entre Python y JavaScript, y los resultados de Python."""
    fallos, resultados = [], []
    for i, (caso, j) in enumerate(zip(casos, js)):
        p = _python(caso)
        resultados.append(p)
        if ("error" in p) != ("error" in j):
            fallos.append((i, "error", p.get("error"), j.get("error")))
            continue
        if "error" in p:
            continue
        pares = [("valor_por_accion", p["valor_por_accion"], j["valor_por_accion"])]
        pares += [(f"unidad {u}", p["unidades"][u], j["unidades"][u])
                  for u in ("automocion", "energia")]
        for nombre, a, b in pares:
            if _discrepa(a, b):
                fallos.append((i, nombre, a, b))
        gp, gj = p["crecimiento_implicito"], j["crecimiento_implicito"]
        if (gp is None) != (gj is None) or (gp is not None and _discrepa(gp, gj)):
            fallos.append((i, "crecimiento_implicito", gp, gj))
    return fallos, resultados


def test_motor_js_reproduce_el_motor_python(tmp_path):
    rng = random.Random(SEMILLA)
    casos = [_caso(rng) for _ in range(N_CASOS)]
    fallos, resultados = _comparar(casos, _js(casos, tmp_path))
    assert not fallos, f"{len(fallos)} discrepancias, las primeras: {fallos[:5]}"
    validos = [p for p in resultados if "error" not in p]
    con_error = N_CASOS - len(validos)
    con_cruce = sum(p["crecimiento_implicito"] is not None for p in validos)
    # La prueba solo vale si ejercita los casos que lanzan, sin que dominen,
    # y los dos caminos del reverse DCF.
    assert 0 < con_error < N_CASOS / 2
    assert 0 < con_cruce < len(validos)


def test_motor_js_en_los_casos_limite(tmp_path):
    horizonte_uno = copy.deepcopy(CASO_FIJO)
    horizonte_uno["comun"]["horizonte_anios"] = 1
    reparto_cero = copy.deepcopy(CASO_FIJO)
    reparto_cero["comun"]["reparto_id_automocion"] = 0.0
    reparto_uno = copy.deepcopy(CASO_FIJO)
    reparto_uno["comun"]["reparto_id_automocion"] = 1.0
    # Precio igual al valor con el crecimiento minimo: el primer punto de la
    # rejilla da una diferencia exactamente nula.
    diferencia_cero = copy.deepcopy(CASO_FIJO)
    diferencia_cero["precio"] = valor_con_crecimiento(
        -0.10, AnioBase(**CASO_FIJO["base"]), CASO_FIJO["escenario"],
        CASO_FIJO["comun"], CASO_FIJO["wacc"], CASO_FIJO["balance"])
    casos = [horizonte_uno, reparto_cero, reparto_uno, diferencia_cero]
    js = _js(casos, tmp_path)
    fallos, resultados = _comparar(casos, js)
    assert not fallos, f"{len(fallos)} discrepancias: {fallos}"
    assert all("error" not in p for p in resultados)
    assert resultados[3]["crecimiento_implicito"] == -0.10
    assert js[3]["crecimiento_implicito"] == -0.10


def test_motor_js_rechaza_supuestos_incompletos(tmp_path):
    sin_margen = copy.deepcopy(CASO_FIJO)
    del sin_margen["escenario"]["automocion"]["margen_bruto_final"]
    horizonte_fraccionario = copy.deepcopy(CASO_FIJO)
    horizonte_fraccionario["comun"]["horizonte_anios"] = 7.5
    js = _js([sin_margen, horizonte_fraccionario], tmp_path)
    assert js[0] == {"error": "supuestos incompletos o no numericos"}
    assert "horizonte" in js[1].get("error", "")


def test_pruebas_de_javascript():
    ejecutar("--test", str(RAIZ / "tests" / "js" / "simulador.test.js"))


def _exportar_yaml(tmp_path, entrada: dict) -> str:
    ruta = tmp_path / "entrada.json"
    ruta.write_text(json.dumps(entrada), encoding="utf-8")
    return ejecutar(str(RAIZ / "tests" / "paridad" / "exportar_yaml.js"), str(ruta))


def _casi_igual(a, b) -> bool:
    """Compara numeros o dicts anidados con tolerancia, para las estructuras
    (escenario completo) que devuelve yaml.safe_load."""
    if isinstance(a, dict):
        return isinstance(b, dict) and a.keys() == b.keys() and all(
            _casi_igual(a[k], b[k]) for k in a)
    return a == pytest.approx(b)


def test_el_yaml_exportado_carga_y_valida(tmp_path, supuestos):
    """Lo que exporta la pagina tiene que poder sustituir a assumptions.yaml."""
    entrada = {"supuestos": supuestos, "nombre": "base",
               "escenario": supuestos["escenarios"]["base"], "comun": supuestos["comun"],
               "wacc": 0.14, "waccOficial": 0.14, "fecha": "2026-10-01"}
    texto = _exportar_yaml(tmp_path, entrada)
    cargado = validar_supuestos(yaml.safe_load(texto))
    assert cargado["version"] == "2026-10-01"
    for clave, valor in supuestos["comun"].items():
        assert cargado["comun"][clave] == pytest.approx(valor)
    for escenario, bloque in supuestos["escenarios"].items():
        for clave, valor in bloque.items():
            if isinstance(valor, dict):
                for k, v in valor.items():
                    assert cargado["escenarios"][escenario][clave][k] == pytest.approx(v)
            else:
                assert cargado["escenarios"][escenario][clave] == pytest.approx(valor)


def test_el_yaml_exportado_mezcla_solo_el_escenario_explorado(tmp_path, supuestos):
    """El escenario explorado sustituye unicamente al suyo; un cambio en comun
    llega al YAML y un campo de comun sin tocar se conserva. El valor de
    prueba (0.2345) no coincide con el margen oficial de ningun escenario,
    para que la comparacion no pueda dar un falso positivo por coincidencia."""
    explorado = copy.deepcopy(supuestos["escenarios"]["base"])
    explorado["automocion"]["margen_bruto_final"] = 0.2345
    entrada = {"supuestos": supuestos, "nombre": "base", "escenario": explorado,
               "comun": {"tipo_impositivo": 0.25}, "wacc": 0.14, "waccOficial": 0.14,
               "fecha": "2026-10-01"}
    texto = _exportar_yaml(tmp_path, entrada)
    cargado = validar_supuestos(yaml.safe_load(texto))

    # El escenario explorado lleva el valor unico en su sitio.
    assert cargado["escenarios"]["base"]["automocion"]["margen_bruto_final"] == \
        pytest.approx(0.2345)
    # Los otros dos escenarios son identicos, campo a campo, a los oficiales.
    for escenario in ("bear", "bull"):
        assert _casi_igual(cargado["escenarios"][escenario], supuestos["escenarios"][escenario])
    # El campo de comun explorado llega al YAML...
    assert cargado["comun"]["tipo_impositivo"] == pytest.approx(0.25)
    # ... y uno sin tocar se conserva igual que en la version oficial.
    assert cargado["comun"]["prima_riesgo_mercado"] == \
        pytest.approx(supuestos["comun"]["prima_riesgo_mercado"])


def test_el_yaml_exportado_avisa_del_wacc_explorado(tmp_path, supuestos):
    entrada = {"supuestos": supuestos, "nombre": "base",
               "escenario": supuestos["escenarios"]["base"], "comun": supuestos["comun"],
               "wacc": 0.16, "waccOficial": 0.14, "fecha": "2026-10-01"}
    texto = _exportar_yaml(tmp_path, entrada)
    assert "ATENCION: WACC explorado 16.00 % frente al oficial 14.00 %" in texto
