import json
import re

import pytest
import yaml

import pandas as pd

import src.construir_dashboard as cd
from src.construir_dashboard import (
    ConstruccionRechazada, comprobar_esquemas, comprobar_vigencia, ensamblar,
    json_incrustable, leer_historico,
)
from tests.test_hitos import datos_minimos

VALORACION = {"huella": "abcd", "mes_precio": "2026-09", "precio": 378.9}
PLANTILLA = ("<style>/*__ESTILOS__*/</style><script id=\"datos\" type=\"application/json\">"
             "__DATOS__</script><script>/*__MOTOR__*/</script>"
             "<script>/*__SIMULADOR__*/</script><script>/*__APP__*/</script>")
PIEZAS = {"/*__ESTILOS__*/": "body{}", "/*__MOTOR__*/": "var a=1;",
          "/*__SIMULADOR__*/": "var b=2;", "/*__APP__*/": "var c=3;"}


def test_valoracion_al_dia_pasa():
    comprobar_vigencia(VALORACION, "abcd", "2026-09", 378.9)


def test_rechaza_una_valoracion_de_otros_supuestos():
    with pytest.raises(ConstruccionRechazada, match="supuestos"):
        comprobar_vigencia(VALORACION, "efgh", "2026-09", 378.9)


def test_rechaza_un_precio_que_no_es_del_ultimo_mes():
    with pytest.raises(ConstruccionRechazada, match="2026-10"):
        comprobar_vigencia(VALORACION, "abcd", "2026-10", 378.9)


def test_rechaza_un_precio_refrescado_dentro_del_mismo_mes():
    """El CSV de mercado se actualizo dentro del mes sin volver a valorar."""
    with pytest.raises(ConstruccionRechazada, match="src.valorar"):
        comprobar_vigencia(VALORACION, "abcd", "2026-09", 381.2)


def test_una_valoracion_sin_huella_se_rechaza_con_mensaje():
    with pytest.raises(ConstruccionRechazada, match="src.valorar"):
        comprobar_vigencia({"mes_precio": "2026-09", "precio": 378.9}, "abcd",
                           "2026-09", 378.9)


def test_rechaza_un_csv_que_no_valida(financieros, mercado):
    """La fixture de financieros no tiene todas las columnas obligatorias."""
    with pytest.raises(ConstruccionRechazada, match="financials_quarterly"):
        comprobar_esquemas(financieros, pd.DataFrame({"period": ["2026Q2"]}), mercado)


def test_el_json_no_puede_cerrar_la_etiqueta_script():
    texto = json_incrustable({"x": "</script><script>alert(1)</script>"})
    assert "</script" not in texto
    assert json.loads(texto) == {"x": "</script><script>alert(1)</script>"}


def test_el_json_no_deja_ningun_signo_menor():
    """Tambien cubre '<!--', que dentro de <script> cambia como se analiza."""
    original = {"x": "<!--<script>"}
    texto = json_incrustable(original)
    assert "<" not in texto
    assert json.loads(texto) == original


def test_el_json_rechaza_nan():
    with pytest.raises(ValueError):
        json_incrustable({"x": float("nan")})


def test_ensamblar_rellena_todas_las_marcas():
    html = ensamblar(PLANTILLA, PIEZAS, '{"a":1}')
    assert "__" not in html
    assert 'var c=3;' in html and '{"a":1}' in html


def test_ensamblar_exige_cada_marca_una_vez():
    with pytest.raises(ValueError, match="__APP__"):
        ensamblar(PLANTILLA.replace("/*__APP__*/", ""), PIEZAS, "{}")


def test_ensamblar_rechaza_una_pieza_que_cierra_script():
    piezas = dict(PIEZAS, **{"/*__APP__*/": "x = '</script>';"})
    with pytest.raises(ValueError, match="script"):
        ensamblar(PLANTILLA, piezas, "{}")


@pytest.mark.parametrize("marca", ["/*__MOTOR__*/", "/*__SIMULADOR__*/", "/*__APP__*/"])
def test_ensamblar_rechaza_un_comentario_html_en_una_pieza_js(marca):
    piezas = dict(PIEZAS, **{marca: "x = '<!--';"})
    with pytest.raises(ValueError, match="<!--"):
        ensamblar(PLANTILLA, piezas, "{}")


def test_ensamblar_rechaza_una_pieza_css_que_cierra_style():
    piezas = dict(PIEZAS, **{"/*__ESTILOS__*/": "a{} </STYLE> b{}"})
    with pytest.raises(ValueError, match="(?i)</style"):
        ensamblar(PLANTILLA, piezas, "{}")


def test_ensamblar_nombra_la_pieza_que_contiene_una_marca():
    piezas = dict(PIEZAS, **{"/*__APP__*/": "// ver /*__MOTOR__*/"})
    with pytest.raises(ValueError, match=r"pieza de /\*__APP__\*/"):
        ensamblar(PLANTILLA, piezas, "{}")


def test_ensamblar_nombra_la_pieza_que_contiene_la_marca_de_datos():
    piezas = dict(PIEZAS, **{"/*__SIMULADOR__*/": "var d = '__DATOS__';"})
    with pytest.raises(ValueError, match=r"pieza de /\*__SIMULADOR__\*/"):
        ensamblar(PLANTILLA, piezas, "{}")


# ---------- construir(): entradas y escritura ----------

# Como la plantilla real, con el contenedor que abre el cuerpo de la pagina.
PLANTILLA_PAGINA = PLANTILLA.replace("</style>", "</style><div class=\"pagina\"></div>", 1)


def _proyecto(tmp_path, plantilla=PLANTILLA_PAGINA, valoracion=True, mercado=None):
    """Carpeta minima con la forma del proyecto para ejecutar construir()."""
    (tmp_path / "data").mkdir()
    (tmp_path / "web").mkdir()
    (tmp_path / "dist").mkdir()
    pd.DataFrame({"period": ["2026Q2"]}).to_csv(
        tmp_path / "data/financials_quarterly.csv", index=False)
    pd.DataFrame({"period": ["2026Q2"]}).to_csv(
        tmp_path / "data/operating_quarterly.csv", index=False)
    (mercado if mercado is not None else
     pd.DataFrame({"month": ["2026-09", "2026-08"], "price_close": [378.9, 350.0]})
     ).to_csv(tmp_path / "data/market_monthly.csv", index=False)
    (tmp_path / "web/plantilla.html").write_text(plantilla, encoding="utf-8")
    for marca, fichero in cd.PIEZAS.items():
        (tmp_path / "web" / fichero).write_text(PIEZAS[marca], encoding="utf-8")
    if valoracion:
        (tmp_path / "dist/valoracion.json").write_text(json.dumps(VALORACION),
                                                       encoding="utf-8")
    return tmp_path


@pytest.fixture
def sin_validacion(monkeypatch):
    monkeypatch.setattr(cd, "comprobar_esquemas", lambda *a: None)
    monkeypatch.setattr(cd, "cargar_supuestos", lambda ruta: ({}, "abcd"))
    monkeypatch.setattr(cd, "construir_datos", lambda *a, **kw: {"a": 1})


def test_construir_escribe_la_pagina_y_los_datos(tmp_path, monkeypatch, sin_validacion):
    monkeypatch.chdir(_proyecto(tmp_path))
    cd.construir()
    assert "var c=3;" in (tmp_path / "dist/dashboard.html").read_text(encoding="utf-8")
    assert json.loads((tmp_path / "dist/datos_dashboard.json").read_text(
        encoding="utf-8")) == {"a": 1}
    web = (tmp_path / "dist/web/index.html").read_text(encoding="utf-8")
    assert web.startswith("<!doctype html>") and "var c=3;" in web


def test_construir_no_escribe_nada_si_el_ensamblado_falla(tmp_path, monkeypatch,
                                                          sin_validacion):
    monkeypatch.chdir(_proyecto(tmp_path, plantilla=PLANTILLA.replace("/*__APP__*/", "")))
    with pytest.raises(ValueError):
        cd.construir()
    assert not (tmp_path / "dist/datos_dashboard.json").exists()
    assert not (tmp_path / "dist/dashboard.html").exists()
    assert not (tmp_path / "dist/web/index.html").exists()


def test_construir_sin_valoracion_pide_valorar(tmp_path, monkeypatch, sin_validacion):
    monkeypatch.chdir(_proyecto(tmp_path, valoracion=False))
    with pytest.raises(ConstruccionRechazada, match="python -m src.valorar"):
        cd.construir()


def test_construir_valida_el_mercado_antes_de_ordenarlo(tmp_path, monkeypatch):
    """Un CSV de mercado sin 'month' da un rechazo explicado, no un KeyError."""
    monkeypatch.chdir(_proyecto(tmp_path, mercado=pd.DataFrame({"x": [1]})))
    with pytest.raises(ConstruccionRechazada):
        cd.construir()


def test_main_sale_con_el_mensaje_sin_traceback(monkeypatch):
    def rechazar():
        raise ConstruccionRechazada("ejecuta python -m src.valorar")
    monkeypatch.setattr(cd, "construir", rechazar)
    with pytest.raises(SystemExit) as salida:
        cd.main()
    assert salida.value.code == "ejecuta python -m src.valorar"


# ---------- leer_historico() ----------

FILA_HISTORICO = {
    "mes": "2026-09", "fecha": "2026-09-23", "version_supuestos": "2026-09-23",
    "huella": "02f115965fa8c9d8", "ttm_hasta": "2026Q2", "precio": 378.9,
    "vpa_bear": 13.55, "vpa_base": 24.87, "vpa_bull": 45.26,
    "crecimiento_implicito": None, "opcionalidad_implicita": 1.4e12, "wacc": 0.139,
}


def test_leer_historico_sin_fichero_da_lista_vacia(tmp_path):
    assert leer_historico(tmp_path / "no-existe.csv") == []


def test_leer_historico_fichero_valido(tmp_path):
    ruta = tmp_path / "historico_valoraciones.csv"
    pd.DataFrame([FILA_HISTORICO]).to_csv(ruta, index=False)
    filas = leer_historico(ruta)
    assert len(filas) == 1
    assert filas[0]["mes"] == "2026-09"
    assert filas[0]["crecimiento_implicito"] is None


def test_leer_historico_rechaza_un_csv_que_no_valida(tmp_path):
    ruta = tmp_path / "historico_valoraciones.csv"
    pd.DataFrame({"mes": ["2026-09"]}).to_csv(ruta, index=False)
    with pytest.raises(ConstruccionRechazada, match="historico_valoraciones"):
        leer_historico(ruta)


def test_leer_historico_solo_cabecera_valida_da_lista_vacia(tmp_path):
    from src.historico import COLUMNAS
    ruta = tmp_path / "historico_valoraciones.csv"
    ruta.write_text(",".join(COLUMNAS) + "\n", encoding="utf-8")
    assert leer_historico(ruta) == []


def test_leer_historico_solo_cabecera_incompleta_se_rechaza(tmp_path):
    """Cabecera sin filas pero con columnas obligatorias ausentes: no debe colarse como []."""
    ruta = tmp_path / "historico_valoraciones.csv"
    ruta.write_text("mes\n", encoding="utf-8")
    with pytest.raises(ConstruccionRechazada, match="historico_valoraciones"):
        leer_historico(ruta)


def test_leer_historico_fichero_vacio_se_rechaza(tmp_path):
    ruta = tmp_path / "historico_valoraciones.csv"
    ruta.write_bytes(b"")
    with pytest.raises(ConstruccionRechazada):
        leer_historico(ruta)


# ---------- hitos ----------

@pytest.fixture
def captura_datos(monkeypatch):
    """Como sin_validacion, pero guarda los argumentos de construir_datos."""
    llamadas = {}
    monkeypatch.setattr(cd, "comprobar_esquemas", lambda *a: None)
    monkeypatch.setattr(cd, "cargar_supuestos", lambda ruta: ({}, "abcd"))

    def construir_datos(*a, **kw):
        llamadas.update(kw)
        return {"a": 1}
    monkeypatch.setattr(cd, "construir_datos", construir_datos)
    return llamadas


def test_construir_sin_milestones_da_hitos_none(tmp_path, monkeypatch, captura_datos):
    monkeypatch.chdir(_proyecto(tmp_path))
    cd.construir()
    assert captura_datos["hitos"] is None


def test_construir_con_milestones_invalido_se_rechaza(tmp_path, monkeypatch, captura_datos):
    monkeypatch.chdir(_proyecto(tmp_path))
    (tmp_path / "data/milestones.yaml").write_text("version: x\n", encoding="utf-8")
    with pytest.raises(ConstruccionRechazada, match="milestones.yaml"):
        cd.construir()
    assert not (tmp_path / "dist/dashboard.html").exists()


def test_construir_con_milestones_valido_pasa_los_hitos(tmp_path, monkeypatch, captura_datos):
    monkeypatch.chdir(_proyecto(tmp_path))
    (tmp_path / "data/milestones.yaml").write_text(
        yaml.safe_dump(datos_minimos(), allow_unicode=True), encoding="utf-8")
    cd.construir()
    hitos = captura_datos["hitos"]
    assert [h["id"] for h in hitos["hitos"]][:2] == ["robotaxi-escala", "optimus"]
    json.dumps(hitos, allow_nan=False)


# ---------- construir() de punta a punta, con la pagina real ----------

def _proyecto_completo(tmp_path, financieros, mercado, supuestos):
    """Proyecto con las piezas web reales, supuestos y valoracion coherentes y el
    milestones.yaml del repositorio con las fechas completas sin comillas (YAML
    las lee como date)."""
    from src.supuestos import cargar_supuestos
    from src.valorar import calcular
    from tests.nodo import RAIZ
    from tests.test_datos_dashboard import OPE_SINT
    for carpeta in ("data", "web", "dist"):
        (tmp_path / carpeta).mkdir()
    for fichero in ("plantilla.html", *cd.PIEZAS.values()):
        (tmp_path / "web" / fichero).write_text(
            (RAIZ / "web" / fichero).read_text(encoding="utf-8"), encoding="utf-8")
    financieros.to_csv(tmp_path / "data/financials_quarterly.csv", index=False)
    OPE_SINT.to_csv(tmp_path / "data/operating_quarterly.csv", index=False)
    mercado.to_csv(tmp_path / "data/market_monthly.csv", index=False)
    (tmp_path / "data/assumptions.yaml").write_text(
        yaml.safe_dump(supuestos, allow_unicode=True), encoding="utf-8")
    _, huella = cargar_supuestos(tmp_path / "data/assumptions.yaml")
    valoracion = calcular(financieros, mercado, supuestos, huella, "2026-09-22")
    (tmp_path / "dist/valoracion.json").write_text(
        json.dumps(valoracion, allow_nan=False), encoding="utf-8")
    texto = (RAIZ / "data/milestones.yaml").read_text(encoding="utf-8")
    sin_comillas = re.sub(r'"(\d{4}-\d{2}-\d{2})"', r"\1", texto)
    assert sin_comillas != texto
    (tmp_path / "data/milestones.yaml").write_text(sin_comillas, encoding="utf-8")
    return tmp_path


def test_construir_con_fechas_yaml_sin_comillas_de_punta_a_punta(
        tmp_path, monkeypatch, financieros, mercado, supuestos):
    monkeypatch.chdir(_proyecto_completo(tmp_path, financieros, mercado, supuestos))
    # Los CSV sinteticos no llevan las columnas de trazabilidad del esquema.
    monkeypatch.setattr(cd, "comprobar_esquemas", lambda *a: None)
    cd.construir()
    datos = json.loads((tmp_path / "dist/datos_dashboard.json").read_text(encoding="utf-8"))
    hitos = datos["hitos"]
    assert len(hitos["hitos"]) == 6 and len(hitos["historial"]) >= 1
    assert isinstance(hitos["version"], str)
    optimus = next(h for h in hitos["hitos"] if h["id"] == "optimus")
    assert optimus["grupos_promesas"][0]["promesa_vigente"]["declarada"] == "2026-07-22"
    assert "__DATOS__" not in (tmp_path / "dist/dashboard.html").read_text(encoding="utf-8")


def test_humo_de_la_pagina_en_node(tmp_path, monkeypatch, financieros, mercado, supuestos):
    """app.js se ejecuta sin errores con hitos, sin hitos y sin Chart (tests/js/humo_app.test.js)."""
    from tests.nodo import RAIZ, ejecutar
    monkeypatch.chdir(_proyecto_completo(tmp_path, financieros, mercado, supuestos))
    monkeypatch.setattr(cd, "comprobar_esquemas", lambda *a: None)
    cd.construir()
    ejecutar("--test", str(RAIZ / "tests" / "js" / "humo_app.test.js"),
             entorno={"HUMO_DATOS": str(tmp_path / "dist/datos_dashboard.json")})


FRAGMENTO = ('<title>Valoración TSLA</title>\n<meta charset="utf-8">\n<style>body{}</style>\n\n'
             '<div class="pagina">contenido</div>\n<script>var a=1;</script>')


def test_documento_completo_para_servidor_propio():
    doc = cd.documento_completo(FRAGMENTO)
    assert doc.startswith("<!doctype html>")
    cabecera, cuerpo = doc.split("<body>")
    assert '<html lang="es">' in cabecera
    assert '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">' in cabecera
    assert '<meta name="robots" content="noindex, nofollow">' in cabecera
    assert "<title>Valoración TSLA</title>" in cabecera and "<style>body{}</style>" in cabecera
    assert doc.count('<meta charset="utf-8">') == 1
    assert cuerpo.lstrip().startswith('<div class="pagina">')
    assert "<script>var a=1;</script>" in cuerpo and doc.rstrip().endswith("</html>")


def test_documento_completo_exige_el_inicio_de_la_pagina():
    with pytest.raises(ValueError, match="pagina"):
        cd.documento_completo("<title>x</title><p>sin contenedor</p>")
