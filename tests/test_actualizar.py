import json
import subprocess
from pathlib import Path

import pandas as pd
import pytest

from src import actualizar
from src.actualizar import ActualizacionRechazada, comprobar_completar, preparar


def _informe(**cambios):
    base = {"fecha": "2026-10-05", "huella_datos": "h1", "revision_trimestral": False,
            "version_supuestos_en_preparar": "v1"}
    return {**base, **cambios}


# ---------- comprobar_completar(): informe, fecha, huella ----------

def test_completar_sin_informe():
    with pytest.raises(ActualizacionRechazada, match="preparar"):
        comprobar_completar(None, "2026-10-05", "h1", "v1", False)


def test_completar_con_informe_de_otro_mes():
    with pytest.raises(ActualizacionRechazada, match="2026-10-05"):
        comprobar_completar(_informe(fecha="2026-09-30"), "2026-10-05", "h1", "v1", False)


def test_completar_con_datos_cambiados_desde_preparar():
    with pytest.raises(ActualizacionRechazada, match="datos"):
        comprobar_completar(_informe(), "2026-10-05", "h2", "v1", False)


def test_sin_trimestre_nuevo_basta_con_informe_y_datos():
    comprobar_completar(_informe(), "2026-10-05", "h1", "v1", False)


def test_informe_sin_version_en_preparar_pide_repetir_preparar():
    """Informe de antes del cambio: no trae version_supuestos_en_preparar."""
    informe = _informe(revision_trimestral=True)
    del informe["version_supuestos_en_preparar"]
    with pytest.raises(ActualizacionRechazada, match="preparar"):
        comprobar_completar(informe, "2026-10-05", "h1", "v1", False)


# ---------- comprobar_completar(): decision sobre los supuestos ----------

def test_trimestre_nuevo_sin_decision_sobre_los_supuestos():
    """La version no ha cambiado desde preparar y no se pide mantenerla: se rechaza."""
    with pytest.raises(ActualizacionRechazada, match="--mantener-supuestos"):
        comprobar_completar(_informe(revision_trimestral=True), "2026-10-05", "h1", "v1", False)


def test_trimestre_nuevo_con_mantener_supuestos_y_version_sin_cambiar():
    comprobar_completar(_informe(revision_trimestral=True), "2026-10-05", "h1", "v1", True)


def test_trimestre_nuevo_con_version_revisada_sin_mantener():
    comprobar_completar(_informe(revision_trimestral=True), "2026-10-05", "h1", "v2", False)


def test_trimestre_nuevo_con_mantener_y_version_cambiada_es_contradictorio():
    with pytest.raises(ActualizacionRechazada, match="mantener"):
        comprobar_completar(_informe(revision_trimestral=True), "2026-10-05", "h1", "v2", True)


def test_version_cambiada_antes_de_preparar_no_cuenta_como_decision():
    """Hueco detectado: un cambio de version anterior a este preparar no es una
    decision sobre el trimestre actual, aunque la version 'vigente' fuera otra."""
    informe = _informe(revision_trimestral=True, version_supuestos_en_preparar="v2")
    with pytest.raises(ActualizacionRechazada, match="--mantener-supuestos"):
        comprobar_completar(informe, "2026-10-05", "h1", "v2", False)


# ---------- comprobar_estado(): plumbing con ficheros reales ----------

def test_comprobar_estado_trimestre_nuevo_sin_valoracion_previa_exige_decision(
        tmp_path, monkeypatch):
    """Hueco detectado: sin dist/valoracion.json (primera vez), la pausa debe seguir activa."""
    informe_ruta = tmp_path / "informe.json"
    informe_ruta.write_text(json.dumps(_informe(revision_trimestral=True)), encoding="utf-8")
    monkeypatch.setattr(actualizar, "INFORME", informe_ruta)
    monkeypatch.setattr(actualizar, "VALORACION", tmp_path / "no-existe.json")
    monkeypatch.setattr(actualizar, "cargar_supuestos", lambda ruta: ({"version": "v1"}, "h"))
    monkeypatch.setattr(actualizar, "huella_datos", lambda rutas: "h1")
    with pytest.raises(ActualizacionRechazada, match="--mantener-supuestos"):
        actualizar.comprobar_estado(False, "2026-10-05")


def test_comprobar_estado_trimestre_nuevo_con_mantener_pasa(tmp_path, monkeypatch):
    informe_ruta = tmp_path / "informe.json"
    informe_ruta.write_text(json.dumps(_informe(revision_trimestral=True)), encoding="utf-8")
    monkeypatch.setattr(actualizar, "INFORME", informe_ruta)
    monkeypatch.setattr(actualizar, "VALORACION", tmp_path / "no-existe.json")
    monkeypatch.setattr(actualizar, "cargar_supuestos", lambda ruta: ({"version": "v1"}, "h"))
    monkeypatch.setattr(actualizar, "huella_datos", lambda rutas: "h1")
    actualizar.comprobar_estado(True, "2026-10-05")


def test_comprobar_estado_sin_informe_lanza(tmp_path, monkeypatch):
    monkeypatch.setattr(actualizar, "INFORME", tmp_path / "no-existe.json")
    monkeypatch.setattr(actualizar, "VALORACION", tmp_path / "no-existe-tampoco.json")
    monkeypatch.setattr(actualizar, "cargar_supuestos", lambda ruta: ({"version": "v1"}, "h"))
    monkeypatch.setattr(actualizar, "huella_datos", lambda rutas: "h1")
    with pytest.raises(ActualizacionRechazada, match="preparar"):
        actualizar.comprobar_estado(False, "2026-10-05")


# ---------- preparar() ----------

def test_preparar_para_si_falla_la_carga(tmp_path):
    llamadas = []

    def cargar():
        llamadas.append("cargar")
        raise ValueError("identidad contable rota")

    with pytest.raises(ActualizacionRechazada, match="git checkout data/"):
        preparar(cargar=cargar, leer_anterior=lambda r: None, hoy="2026-10-05",
                 salida=tmp_path / "informe.json")
    assert llamadas == ["cargar"] and not (tmp_path / "informe.json").exists()


def test_preparar_escribe_el_informe(tmp_path, monkeypatch):
    fin = pd.DataFrame({"period": ["2026Q2"], "revenue_total": [1.0]})
    mer = pd.DataFrame({"month": ["2026-10"], "price_close": [1.0], "eurusd": [1.1],
                        "rf_10y": [0.04]})
    rutas = {}
    for nombre, df in (("financials_quarterly", fin), ("operating_quarterly", fin),
                       ("market_monthly", mer)):
        rutas[nombre] = tmp_path / f"{nombre}.csv"
        df.to_csv(rutas[nombre], index=False)
    monkeypatch.setattr(actualizar, "RUTAS", rutas)
    monkeypatch.setattr(actualizar, "cargar_supuestos", lambda ruta: ({"version": "v9"}, "h"))
    informe = preparar(cargar=lambda: None, leer_anterior=lambda r: None,
                       hoy="2026-10-05", salida=tmp_path / "informe.json")
    escrito = json.loads((tmp_path / "informe.json").read_text(encoding="utf-8"))
    assert escrito == informe and informe["revision_trimestral"] is True
    assert len(informe["huella_datos"]) == 64
    assert informe["version_supuestos_en_preparar"] == "v9"


def test_preparar_rechaza_si_desaparece_un_periodo(tmp_path, monkeypatch):
    """Un periodo que ya estaba y ya no esta suele delatar una descarga fallida."""
    fin_actual = pd.DataFrame({"period": ["2026Q1"], "revenue_total": [1.0]})
    fin_anterior = pd.DataFrame({"period": ["2026Q1", "2026Q2"], "revenue_total": [1.0, 2.0]})
    mer = pd.DataFrame({"month": ["2026-10"], "price_close": [1.0], "eurusd": [1.1],
                        "rf_10y": [0.04]})
    rutas = {}
    for nombre, df in (("financials_quarterly", fin_actual), ("operating_quarterly", fin_actual),
                       ("market_monthly", mer)):
        rutas[nombre] = tmp_path / f"{nombre}.csv"
        df.to_csv(rutas[nombre], index=False)
    monkeypatch.setattr(actualizar, "RUTAS", rutas)
    monkeypatch.setattr(actualizar, "cargar_supuestos", lambda ruta: ({"version": "v1"}, "h"))

    def leer_anterior(ruta):
        return fin_anterior if ruta == rutas["financials_quarterly"] else None

    salida = tmp_path / "informe.json"
    with pytest.raises(ActualizacionRechazada, match="2026Q2.*git checkout data/"):
        preparar(cargar=lambda: None, leer_anterior=leer_anterior, hoy="2026-10-05",
                 salida=salida)
    # El informe se escribe igualmente, para poder diagnosticar el fallo.
    assert salida.exists()
    escrito = json.loads(salida.read_text(encoding="utf-8"))
    assert escrito["periodos_eliminados"]["financials_quarterly"] == ["2026Q2"]


# ---------- completar(): orden de los pasos y mensajes de fallo parcial ----------

def test_completar_llama_a_los_pasos_en_orden(tmp_path, monkeypatch):
    orden = []
    monkeypatch.setattr(actualizar, "comprobar_estado", lambda mantener, hoy: None)
    actualizar.completar(False, hoy="2026-10-05",
                         valorar_oficial=lambda: orden.append("valorar"),
                         registrar_historico=lambda: orden.append("historico"),
                         construir_pagina=lambda: orden.append("construir"))
    assert orden == ["valorar", "historico", "construir"]


def test_completar_si_comprobar_estado_lanza_no_ejecuta_ningun_paso(monkeypatch):
    orden = []

    def comprobar_falla(mantener, hoy):
        raise ActualizacionRechazada("no hay informe de actualizacion")

    monkeypatch.setattr(actualizar, "comprobar_estado", comprobar_falla)
    with pytest.raises(ActualizacionRechazada):
        actualizar.completar(False, hoy="2026-10-05",
                             valorar_oficial=lambda: orden.append("valorar"),
                             registrar_historico=lambda: orden.append("historico"),
                             construir_pagina=lambda: orden.append("construir"))
    assert orden == []


def test_completar_falla_al_registrar_historico_avisa_de_lo_escrito(monkeypatch):
    monkeypatch.setattr(actualizar, "comprobar_estado", lambda mantener, hoy: None)

    def falla():
        raise ValueError("csv corrupto")

    with pytest.raises(ActualizacionRechazada) as exc:
        actualizar.completar(False, hoy="2026-10-05", valorar_oficial=lambda: None,
                             registrar_historico=falla,
                             construir_pagina=lambda: pytest.fail("no deberia llamarse"))
    mensaje = str(exc.value)
    assert "dist/valoracion.json" in mensaje
    assert "registrar el historico" in mensaje
    assert "csv corrupto" in mensaje
    assert "python -m src.actualizar completar" in mensaje


def test_completar_falla_al_construir_la_pagina_avisa_de_lo_escrito(monkeypatch):
    monkeypatch.setattr(actualizar, "comprobar_estado", lambda mantener, hoy: None)

    def falla():
        raise ValueError("plantilla rota")

    with pytest.raises(ActualizacionRechazada) as exc:
        actualizar.completar(False, hoy="2026-10-05", valorar_oficial=lambda: None,
                             registrar_historico=lambda: None, construir_pagina=falla)
    mensaje = str(exc.value)
    assert "dist/valoracion.json" in mensaje
    assert "construir la pagina" in mensaje
    assert "plantilla rota" in mensaje
    assert "python -m src.actualizar completar" in mensaje


def test_completar_imprime_lo_que_devuelve_construir_pagina(monkeypatch, capsys):
    monkeypatch.setattr(actualizar, "comprobar_estado", lambda mantener, hoy: None)
    actualizar.completar(False, hoy="2026-10-05", valorar_oficial=lambda: None,
                         registrar_historico=lambda: None,
                         construir_pagina=lambda: "dist/dashboard.html (148 KB)")
    assert "dist/dashboard.html (148 KB)" in capsys.readouterr().out


# ---------- leer_de_head(): repositorio git real, siempre dentro de tmp_path ----------

def _git(cwd: Path, *args: str) -> None:
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                       encoding="utf-8")
    assert r.returncode == 0, r.stderr


def _repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test")
    return tmp_path


def test_leer_de_head_fichero_presente(tmp_path, monkeypatch):
    _repo(tmp_path)
    (tmp_path / "datos.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    _git(tmp_path, "add", "datos.csv")
    _git(tmp_path, "commit", "-q", "-m", "c1")
    monkeypatch.chdir(tmp_path)
    df = actualizar.leer_de_head(Path("datos.csv"))
    assert df is not None and list(df.columns) == ["a", "b"] and df["a"].iloc[0] == 1


def test_leer_de_head_fichero_ausente_en_head(tmp_path, monkeypatch):
    _repo(tmp_path)
    (tmp_path / "otro.csv").write_text("a\n1\n", encoding="utf-8")
    _git(tmp_path, "add", "otro.csv")
    _git(tmp_path, "commit", "-q", "-m", "c1")
    monkeypatch.chdir(tmp_path)
    assert actualizar.leer_de_head(Path("no-existe.csv")) is None


def test_leer_de_head_fichero_sin_comitear(tmp_path, monkeypatch):
    _repo(tmp_path)
    (tmp_path / "sin_commit.csv").write_text("a\n1\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert actualizar.leer_de_head(Path("sin_commit.csv")) is None


def test_leer_de_head_repositorio_sin_commits(tmp_path, monkeypatch):
    _repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert actualizar.leer_de_head(Path("cualquiera.csv")) is None


def test_leer_de_head_fuera_de_un_repositorio_lanza(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)   # tmp_path no es un repositorio git
    with pytest.raises(ActualizacionRechazada, match="git"):
        actualizar.leer_de_head(Path("cualquiera.csv"))


def test_leer_de_head_sin_git_instalado_lanza(monkeypatch):
    def falla(*a, **k):
        raise FileNotFoundError("git no encontrado")

    monkeypatch.setattr(actualizar.subprocess, "run", falla)
    with pytest.raises(ActualizacionRechazada, match="git"):
        actualizar.leer_de_head(Path("cualquiera.csv"))


# ---------- main(): argumentos ----------

def test_main_sin_argumentos_sale_con_el_uso():
    with pytest.raises(SystemExit, match="uso:"):
        actualizar.main([])


def test_main_con_verbo_desconocido_sale_con_el_uso():
    with pytest.raises(SystemExit, match="uso:"):
        actualizar.main(["destruir"])


def test_main_preparar_con_argumentos_extra_sale_con_el_uso(monkeypatch):
    monkeypatch.setattr(actualizar, "preparar", lambda: pytest.fail("no deberia llamarse"))
    with pytest.raises(SystemExit, match="uso:"):
        actualizar.main(["preparar", "algo"])


def test_main_completar_con_argumento_desconocido_sale_con_el_uso(monkeypatch):
    monkeypatch.setattr(actualizar, "completar", lambda *a, **k: pytest.fail("no deberia llamarse"))
    with pytest.raises(SystemExit, match="uso:"):
        actualizar.main(["completar", "--algo-raro"])


def test_main_completar_con_mantener_supuestos_pasa_el_flag(monkeypatch):
    recibido = {}
    monkeypatch.setattr(actualizar, "completar", lambda mantener: recibido.setdefault("m", mantener))
    actualizar.main(["completar", "--mantener-supuestos"])
    assert recibido["m"] is True
