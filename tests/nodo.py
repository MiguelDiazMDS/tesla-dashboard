"""Localiza Node para las pruebas de JavaScript.

La paridad entre el motor de Python y el de la pagina es obligatoria: si Node
no esta instalado, la prueba falla en vez de saltarse en silencio.
"""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
LIMITE_SEGUNDOS = 120


def node() -> str:
    ejecutable = shutil.which("node")
    if ejecutable is None:
        pytest.fail("Node no esta instalado y la prueba de paridad es obligatoria")
    return ejecutable


def ejecutar(*argumentos: str, entorno: dict | None = None) -> str:
    """entorno: variables que se anaden a las del proceso actual."""
    try:
        r = subprocess.run([node(), *argumentos], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", cwd=RAIZ,
                           timeout=LIMITE_SEGUNDOS,
                           env={**os.environ, **entorno} if entorno else None)
    except subprocess.TimeoutExpired:
        pytest.fail(f"Node no termino en {LIMITE_SEGUNDOS} s: {' '.join(argumentos)}")
    if r.returncode != 0:
        pytest.fail(f"Node termino con error:\n{r.stdout}\n{r.stderr}")
    return r.stdout
