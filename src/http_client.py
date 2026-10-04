"""Unico punto de acceso a la red del proyecto."""
import hashlib
import math
import os
import time
from pathlib import Path

import requests


class FaltaUserAgent(Exception):
    """La SEC exige identificarse; sin SEC_USER_AGENT responde 403."""


DOMINIOS_SEC = ("sec.gov",)

# Fuera de la SEC hace falta una cabecera de navegador: api.nasdaq.com no
# responde 403 sin ella, simplemente deja la conexion colgada hasta agotar el
# tiempo de espera, lo que despista al diagnosticar.
AGENTE_NAVEGADOR = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

# Fallos transitorios: se reintentan. Cualquier otro error falla a la primera,
# porque reintentarlo solo esconderia un fallo real (404, 403...).
REINTENTABLES = {429, 500, 502, 503, 504}
ESPERAS = (2, 4, 8)          # segundos antes del 2o, 3er y 4o intento
MAX_RETRY_AFTER = 60


class ErrorDescarga(requests.HTTPError):
    """Agotados los reintentos ante un fallo transitorio."""


def _retry_after(respuesta) -> float | None:
    valor = respuesta.headers.get("Retry-After") if respuesta.headers else None
    if valor is None:
        return None
    try:
        segundos = float(valor)
    except ValueError:
        return None   # Retry-After con fecha HTTP: se usa la espera normal
    if not math.isfinite(segundos):
        return None   # nan o inf: cabecera invalida, se ignora
    return min(max(0.0, segundos), MAX_RETRY_AFTER)


def cabeceras_para(url: str) -> dict[str, str]:
    """Cabeceras de la peticion segun el destino.

    A la SEC se va siempre identificado con nombre y correo, como exige su
    politica de acceso automatizado. Al resto de fuentes, con una cabecera de
    navegador corriente.
    """
    if any(dominio in url for dominio in DOMINIOS_SEC):
        agente = os.environ.get("SEC_USER_AGENT")
        if not agente:
            raise FaltaUserAgent(
                "Define SEC_USER_AGENT (nombre y correo) antes de llamar a la SEC"
            )
        return {"User-Agent": agente}
    return {"User-Agent": AGENTE_NAVEGADOR}


class ClienteHTTP:
    def __init__(self, directorio_cache: str = "cache", pausa: float = 0.2,
                 esperar=time.sleep):
        self.cache = Path(directorio_cache)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.pausa = pausa
        self.esperar = esperar

    @staticmethod
    def clave_cache(url: str) -> str:
        return hashlib.sha256(url.encode()).hexdigest()[:32]

    def obtener(self, url: str, forzar: bool = False,
                max_edad_horas: float | None = None) -> bytes:
        """Contenido de la URL, de la cache si es valida.

        `max_edad_horas` es para los indices que cambian (submissions,
        companyfacts, tipos de cambio, el CSV del Tesoro del anio en curso): si
        la copia es mas antigua, se vuelve a descargar. Los filings archivados
        no cambian nunca y se llaman sin caducidad.
        """
        destino = self.cache / self.clave_cache(url)
        if destino.exists() and not forzar and not self._caducado(destino, max_edad_horas):
            return destino.read_bytes()

        cabeceras = cabeceras_para(url)

        contenido = self._descargar(url, cabeceras)
        destino.write_bytes(contenido)
        return contenido

    def _descargar(self, url: str, cabeceras: dict[str, str]) -> bytes:
        intentos = len(ESPERAS) + 1
        ultimo: Exception | None = None
        for intento in range(intentos):
            time.sleep(self.pausa)
            espera = ESPERAS[intento] if intento < len(ESPERAS) else None
            try:
                resp = requests.get(url, headers=cabeceras, timeout=120)
            except (requests.ConnectionError, requests.Timeout,
                    requests.exceptions.ChunkedEncodingError) as error:
                ultimo = error
            else:
                if resp.status_code not in REINTENTABLES:
                    resp.raise_for_status()
                    return resp.content
                ultimo = requests.HTTPError(f"HTTP {resp.status_code}", response=resp)
                indicada = _retry_after(resp)
                espera = indicada if indicada is not None else espera
            # Tras el ultimo intento no se espera: se lanza el error.
            if espera is not None and intento < intentos - 1:
                self.esperar(espera)
        raise ErrorDescarga(
            f"{url}: {intentos} intentos sin respuesta valida (ultimo error: {ultimo})",
            response=getattr(ultimo, "response", None),
        ) from ultimo

    @staticmethod
    def _caducado(ruta: Path, max_edad_horas: float | None) -> bool:
        if max_edad_horas is None:
            return False
        return time.time() - ruta.stat().st_mtime > max_edad_horas * 3600
