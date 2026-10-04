"""Rutina mensual en dos tiempos. La dirige la skill /tesla-update.

    python -m src.actualizar preparar
        carga y verifica los datos, compara con el ultimo commit y escribe
        dist/informe_actualizacion.json. No valora.
    python -m src.actualizar completar [--mantener-supuestos]
        valora (oficial), registra el historico y construye la pagina. Si el
        informe trae un trimestre nuevo, exige una decision sobre los
        supuestos: version nueva en data/assumptions.yaml o --mantener-supuestos.

La pausa de revision de supuestos vive en completar() (via comprobar_estado):
python -m src.valorar ejecutado a mano no la comprueba, asi que la skill
nunca debe llamarlo directamente para la valoracion oficial.
"""
import io
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import pandas as pd

from src import cargar_todo, construir_dashboard, historico, valorar
from src.construir_dashboard import ConstruccionRechazada
from src.informe import construir_informe, huella_datos
from src.supuestos import SupuestosInvalidos, cargar_supuestos
from src.validate import ErrorValidacion

RUTAS = {
    "financials_quarterly": Path("data/financials_quarterly.csv"),
    "operating_quarterly": Path("data/operating_quarterly.csv"),
    "market_monthly": Path("data/market_monthly.csv"),
}
INFORME = Path("dist/informe_actualizacion.json")
VALORACION = Path("dist/valoracion.json")

# Fragmentos de stderr de "git show HEAD:..." que significan "no hay version
# anterior" (fichero nuevo o repositorio sin commits), no un fallo real.
_SIN_VERSION_PREVIA = ("does not exist", "exists on disk, but not in",
                       "invalid object name 'HEAD'", "unknown revision")


class ActualizacionRechazada(Exception):
    """La rutina no puede seguir: el mensaje dice que hacer."""


def leer_de_head(ruta: Path) -> pd.DataFrame | None:
    """Version del fichero en el ultimo commit, o None si no la hay.

    "No hay version anterior" solo cubre un fichero nuevo o un repositorio
    sin commits (se distingue por el texto de stderr de git). Si git no esta
    instalado o la carpeta no es un repositorio, es un problema real: se
    detiene con un mensaje claro en vez de tratarlo como "sin version".
    """
    try:
        r = subprocess.run(["git", "show", f"HEAD:./{ruta.as_posix()}"],
                           capture_output=True, text=True, encoding="utf-8")
    except FileNotFoundError as error:
        raise ActualizacionRechazada(
            "git no esta instalado o no esta en el PATH: no se puede comparar "
            "con el ultimo commit") from error
    if r.returncode != 0:
        if any(texto in r.stderr for texto in _SIN_VERSION_PREVIA):
            return None
        raise ActualizacionRechazada(
            f"No se pudo leer {ruta.as_posix()} del ultimo commit: {r.stderr.strip()}")
    return pd.read_csv(io.StringIO(r.stdout))


def preparar(cargar=cargar_todo.main, leer_anterior=leer_de_head,
             hoy: str | None = None, salida: Path = INFORME) -> dict:
    hoy = hoy or date.today().isoformat()
    try:
        cargar()
    except Exception as error:
        raise ActualizacionRechazada(
            f"La carga o la verificacion ha fallado: {error}. Los CSV quedan como "
            "estan para diagnosticar; restauralos con git checkout data/") from error
    actual = {n: pd.read_csv(r) for n, r in RUTAS.items()}
    anterior = {n: leer_anterior(r) for n, r in RUTAS.items()}
    informe = construir_informe(actual, anterior, hoy, huella_datos(list(RUTAS.values())))
    # La decision sobre los supuestos se toma despues de ver este informe: se
    # guarda la version de ese momento para distinguirla de una decision real.
    supuestos, _ = cargar_supuestos(valorar.RUTA_SUPUESTOS)
    informe["version_supuestos_en_preparar"] = supuestos["version"]
    salida.parent.mkdir(exist_ok=True)
    salida.write_text(json.dumps(informe, ensure_ascii=False, indent=2, allow_nan=False),
                      encoding="utf-8")
    eliminados = {n: p for n, p in informe["periodos_eliminados"].items() if p}
    if eliminados:
        # El informe ya quedo escrito para poder diagnosticar el fallo.
        detalle = "; ".join(f"{n}: {', '.join(p)}" for n, p in eliminados.items())
        raise ActualizacionRechazada(
            f"Han desaparecido periodos que ya estaban ({detalle}). Probablemente fallo "
            "una descarga: restaura los datos con git checkout data/ y reintenta.")
    return informe


def comprobar_completar(informe: dict | None, hoy: str, huella_actual: str,
                        version_supuestos: str, mantener: bool) -> None:
    if informe is None:
        raise ActualizacionRechazada(
            "No hay informe de actualizacion: ejecuta python -m src.actualizar preparar")
    if informe["fecha"][:7] != hoy[:7]:
        raise ActualizacionRechazada(
            f"El informe es del {informe['fecha']} y hoy es {hoy}: ejecuta "
            "python -m src.actualizar preparar")
    if informe["huella_datos"] != huella_actual:
        raise ActualizacionRechazada(
            "Los datos han cambiado desde preparar: vuelve a ejecutar "
            "python -m src.actualizar preparar")
    if "version_supuestos_en_preparar" not in informe:
        raise ActualizacionRechazada(
            "El informe es de antes de que se guardara la version de los supuestos: "
            "vuelve a ejecutar python -m src.actualizar preparar")
    if not informe["revision_trimestral"]:
        return
    cambiada = version_supuestos != informe["version_supuestos_en_preparar"]
    if mantener and cambiada:
        raise ActualizacionRechazada(
            "Has cambiado la version de los supuestos en data/assumptions.yaml y a la vez "
            "pides mantenerlos con --mantener-supuestos: decide una cosa u otra")
    if not mantener and not cambiada:
        raise ActualizacionRechazada(
            "Hay un trimestre nuevo: decide sobre los supuestos antes de valorar. "
            "O cambias 'version' en data/assumptions.yaml tras revisarlos, o "
            "confirmas que se mantienen con --mantener-supuestos")


def comprobar_estado(mantener: bool, hoy: str) -> None:
    informe = json.loads(INFORME.read_text(encoding="utf-8")) if INFORME.exists() else None
    supuestos, _ = cargar_supuestos(valorar.RUTA_SUPUESTOS)
    comprobar_completar(informe, hoy, huella_datos(list(RUTAS.values())),
                        supuestos["version"], mantener)


def _registrar_vigente() -> None:
    historico.registrar(json.loads(VALORACION.read_text(encoding="utf-8")))


def completar(mantener: bool, hoy: str | None = None, valorar_oficial=valorar.main,
              registrar_historico=_registrar_vigente,
              construir_pagina=construir_dashboard.construir) -> None:
    hoy = hoy or date.today().isoformat()
    comprobar_estado(mantener, hoy)
    valorar_oficial()
    # A partir de aqui la valoracion oficial ya esta escrita: un fallo en los
    # pasos siguientes debe decirlo, para no dar la impresion de que no paso
    # nada y de que hay que empezar de cero.
    try:
        registrar_historico()
    except Exception as error:
        raise ActualizacionRechazada(
            f"Valoracion oficial escrita en {VALORACION.as_posix()}; fallo al registrar "
            f"el historico: {error}. Corrige y repite python -m src.actualizar completar"
        ) from error
    try:
        resultado = construir_pagina()
    except Exception as error:
        raise ActualizacionRechazada(
            f"Valoracion oficial escrita en {VALORACION.as_posix()}; fallo al construir "
            f"la pagina: {error}. Corrige y repite python -m src.actualizar completar"
        ) from error
    if resultado:
        print(resultado)


def main(argv: list[str]) -> None:
    uso = "uso: python -m src.actualizar preparar | completar [--mantener-supuestos]"
    if not argv or argv[0] not in ("preparar", "completar"):
        sys.exit(uso)
    if argv[0] == "preparar" and len(argv) > 1:
        sys.exit(uso)
    if argv[0] == "completar" and any(a != "--mantener-supuestos" for a in argv[1:]):
        sys.exit(uso)
    try:
        if argv[0] == "preparar":
            informe = preparar()
            print(f"{INFORME.as_posix()} escrito. Trimestre nuevo: "
                  f"{'si' if informe['revision_trimestral'] else 'no'}. "
                  f"Avisos: {len(informe['avisos'])}.")
        else:
            completar("--mantener-supuestos" in argv[1:])
    except (ActualizacionRechazada, SupuestosInvalidos, ValueError, ErrorValidacion,
            ConstruccionRechazada) as error:
        # valorar lanza ValueError si falta el precio del mes, SupuestosInvalidos
        # si los supuestos cambian sin version nueva, ErrorValidacion si los CSV
        # no cuadran con su esquema y ConstruccionRechazada si construir_dashboard
        # se niega a publicar una pagina desactualizada.
        sys.exit(str(error))


if __name__ == "__main__":
    main(sys.argv[1:])
