import math
import os
import time

import pytest
import requests

from src.http_client import (
    AGENTE_NAVEGADOR, ClienteHTTP, ESPERAS, ErrorDescarga, FaltaUserAgent,
    _retry_after, cabeceras_para,
)


def test_a_la_sec_se_va_identificado_con_nombre_y_correo(monkeypatch):
    monkeypatch.setenv("SEC_USER_AGENT", "Nombre Apellido correo@dominio.com")
    cabeceras = cabeceras_para("https://data.sec.gov/api/xbrl/companyfacts/X.json")
    assert cabeceras["User-Agent"] == "Nombre Apellido correo@dominio.com"


def test_al_resto_de_fuentes_con_cabecera_de_navegador(monkeypatch):
    """api.nasdaq.com deja la conexion colgada si no la recibe: no da 403."""
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    assert cabeceras_para("https://api.nasdaq.com/api/quote/TSLA/historical") == {
        "User-Agent": AGENTE_NAVEGADOR
    }


def test_fuera_de_la_sec_no_hace_falta_el_user_agent_identificado(monkeypatch):
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    cabeceras_para("https://data-api.ecb.europa.eu/service/data/EXR/X")


def test_exige_user_agent_para_dominios_de_la_sec(monkeypatch, tmp_path):
    """Con tmp_path el resultado no depende de que la cache este caliente."""
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    cliente = ClienteHTTP(directorio_cache=str(tmp_path))
    with pytest.raises(FaltaUserAgent):
        cliente.obtener("https://data.sec.gov/api/xbrl/companyfacts/CIK0001318605.json")


def test_la_clave_de_cache_es_estable_y_valida_como_nombre_de_fichero(tmp_path):
    """Con tmp_path el test no depende del contenido del directorio real."""
    cliente = ClienteHTTP(directorio_cache=str(tmp_path))
    clave = cliente.clave_cache("https://example.com/a/b?c=1&d=2")
    assert clave == cliente.clave_cache("https://example.com/a/b?c=1&d=2")
    assert not set(clave) & set('/\\:*?"<>|')


def test_devuelve_lo_cacheado_sin_tocar_la_red(tmp_path):
    cliente = ClienteHTTP(directorio_cache=str(tmp_path))
    url = "https://example.com/recurso"
    destino = tmp_path / cliente.clave_cache(url)
    destino.write_bytes(b"contenido cacheado")
    assert cliente.obtener(url) == b"contenido cacheado"


class _Respuesta:
    def __init__(self, contenido=b"", estado=200, cabeceras=None):
        self.content = contenido
        self.status_code = estado
        self.headers = cabeceras or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}", response=self)


def test_una_entrada_reciente_se_sirve_de_cache(tmp_path, monkeypatch):
    llamadas = []
    monkeypatch.setattr("src.http_client.requests.get",
                        lambda *a, **k: llamadas.append(1) or _Respuesta(b"nuevo"))
    cliente = ClienteHTTP(directorio_cache=str(tmp_path), pausa=0)
    url = "https://example.com/indice"
    (tmp_path / cliente.clave_cache(url)).write_bytes(b"cacheado")
    assert cliente.obtener(url, max_edad_horas=12) == b"cacheado"
    assert llamadas == []


def test_una_entrada_caducada_se_vuelve_a_descargar(tmp_path, monkeypatch):
    """Sin caducidad, una carga repetida dentro del mes no veria filings nuevos."""
    monkeypatch.setattr("src.http_client.requests.get",
                        lambda *a, **k: _Respuesta(b"nuevo"))
    cliente = ClienteHTTP(directorio_cache=str(tmp_path), pausa=0)
    url = "https://example.com/indice"
    destino = tmp_path / cliente.clave_cache(url)
    destino.write_bytes(b"viejo")
    hace_dos_dias = time.time() - 48 * 3600
    os.utime(destino, (hace_dos_dias, hace_dos_dias))
    assert cliente.obtener(url, max_edad_horas=12) == b"nuevo"
    assert destino.read_bytes() == b"nuevo"


def test_sin_caducidad_la_cache_no_expira(tmp_path, monkeypatch):
    """Los filings archivados no cambian nunca: su cache vale para siempre."""
    monkeypatch.setattr("src.http_client.requests.get",
                        lambda *a, **k: _Respuesta(b"nuevo"))
    cliente = ClienteHTTP(directorio_cache=str(tmp_path), pausa=0)
    url = "https://example.com/filing"
    destino = tmp_path / cliente.clave_cache(url)
    destino.write_bytes(b"archivado")
    antiguo = time.time() - 400 * 24 * 3600
    os.utime(destino, (antiguo, antiguo))
    assert cliente.obtener(url) == b"archivado"


def _cliente_con(respuestas, tmp_path, monkeypatch):
    """Cliente cuyo requests.get devuelve (o lanza) cada elemento en orden.

    `llamadas` acumula las cabeceras recibidas en cada llamada, para poder
    comprobar que cada reintento las repite (p. ej. el User-Agent de la SEC).
    """
    cola = list(respuestas)
    llamadas = []

    def falso_get(*a, headers=None, **k):
        llamadas.append(headers)
        r = cola.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    monkeypatch.setattr("src.http_client.requests.get", falso_get)
    esperas = []
    cliente = ClienteHTTP(directorio_cache=str(tmp_path), pausa=0, esperar=esperas.append)
    return cliente, llamadas, esperas


def test_un_503_pasajero_se_reintenta(tmp_path, monkeypatch):
    cliente, llamadas, esperas = _cliente_con(
        [_Respuesta(estado=503), _Respuesta(b"ok")], tmp_path, monkeypatch)
    assert cliente.obtener("https://example.com/a") == b"ok"
    assert len(llamadas) == 2 and esperas == [2]


def test_cortes_y_tiempos_agotados_se_reintentan(tmp_path, monkeypatch):
    cliente, llamadas, esperas = _cliente_con(
        [requests.ConnectionError("corte"), requests.Timeout("lento"),
         _Respuesta(estado=429), _Respuesta(b"ok")], tmp_path, monkeypatch)
    assert cliente.obtener("https://example.com/b") == b"ok"
    assert esperas == [2, 4, 8]


def test_agotados_los_intentos_falla_con_la_url(tmp_path, monkeypatch):
    cliente, llamadas, esperas = _cliente_con(
        [_Respuesta(estado=503)] * 4, tmp_path, monkeypatch)
    with pytest.raises(ErrorDescarga, match="example.com/c.*4 intentos"):
        cliente.obtener("https://example.com/c")
    assert len(llamadas) == 4 and esperas == list(ESPERAS)


def test_un_404_no_se_reintenta(tmp_path, monkeypatch):
    cliente, llamadas, esperas = _cliente_con([_Respuesta(estado=404)], tmp_path, monkeypatch)
    with pytest.raises(requests.HTTPError):
        cliente.obtener("https://example.com/d")
    assert len(llamadas) == 1 and esperas == []


def test_retry_after_manda_con_un_maximo(tmp_path, monkeypatch):
    cliente, _, esperas = _cliente_con(
        [_Respuesta(estado=429, cabeceras={"Retry-After": "7"}),
         _Respuesta(estado=503, cabeceras={"Retry-After": "600"}),
         _Respuesta(b"ok")], tmp_path, monkeypatch)
    assert cliente.obtener("https://example.com/e") == b"ok"
    assert esperas == [7, 60]


def test_un_fallo_no_toca_la_cache(tmp_path, monkeypatch):
    cliente, _, _ = _cliente_con([_Respuesta(estado=404)], tmp_path, monkeypatch)
    with pytest.raises(requests.HTTPError):
        cliente.obtener("https://example.com/f")
    assert not (tmp_path / cliente.clave_cache("https://example.com/f")).exists()


def test_un_403_no_se_reintenta(tmp_path, monkeypatch):
    cliente, llamadas, esperas = _cliente_con([_Respuesta(estado=403)], tmp_path, monkeypatch)
    with pytest.raises(requests.HTTPError):
        cliente.obtener("https://example.com/g")
    assert len(llamadas) == 1 and esperas == []


def test_cache_vacia_al_agotar_los_intentos_con_503(tmp_path, monkeypatch):
    cliente, _, _ = _cliente_con([_Respuesta(estado=503)] * 4, tmp_path, monkeypatch)
    with pytest.raises(ErrorDescarga):
        cliente.obtener("https://example.com/h")
    assert not (tmp_path / cliente.clave_cache("https://example.com/h")).exists()


def test_chunked_encoding_error_se_reintenta(tmp_path, monkeypatch):
    cliente, llamadas, esperas = _cliente_con(
        [requests.exceptions.ChunkedEncodingError("corte"), _Respuesta(b"ok")],
        tmp_path, monkeypatch)
    assert cliente.obtener("https://example.com/i") == b"ok"
    assert esperas == [2]


def test_cada_reintento_a_la_sec_envia_el_user_agent(tmp_path, monkeypatch):
    monkeypatch.setenv("SEC_USER_AGENT", "Nombre Apellido correo@dominio.com")
    cliente, llamadas, esperas = _cliente_con(
        [_Respuesta(estado=503), _Respuesta(estado=503), _Respuesta(b"ok")],
        tmp_path, monkeypatch)
    assert cliente.obtener("https://data.sec.gov/api/xbrl/companyfacts/X.json") == b"ok"
    assert len(llamadas) == 3
    assert all(h["User-Agent"] == "Nombre Apellido correo@dominio.com" for h in llamadas)


def test_error_descarga_lleva_la_ultima_respuesta(tmp_path, monkeypatch):
    cliente, _, _ = _cliente_con([_Respuesta(estado=503)] * 4, tmp_path, monkeypatch)
    with pytest.raises(ErrorDescarga) as exc:
        cliente.obtener("https://example.com/j")
    assert exc.value.response is not None and exc.value.response.status_code == 503


def test_error_descarga_sin_respuesta_si_el_ultimo_fue_un_corte(tmp_path, monkeypatch):
    cliente, _, _ = _cliente_con([requests.ConnectionError("corte")] * 4, tmp_path, monkeypatch)
    with pytest.raises(ErrorDescarga) as exc:
        cliente.obtener("https://example.com/k")
    assert exc.value.response is None


def test_retry_after_negativo_se_recorta_a_cero():
    assert _retry_after(_Respuesta(cabeceras={"Retry-After": "-5"})) == 0.0


def test_retry_after_no_finito_se_descarta():
    assert _retry_after(_Respuesta(cabeceras={"Retry-After": "nan"})) is None
    assert _retry_after(_Respuesta(cabeceras={"Retry-After": "inf"})) is None
