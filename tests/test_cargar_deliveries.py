import pytest

from src.cargar_deliveries import leer_nota
from src.http_client import ErrorDescarga


class _ClienteFallaSiempre:
    def obtener(self, url):
        raise ErrorDescarga("agotados los reintentos")


def test_error_descarga_al_leer_el_indice_se_propaga():
    """Agotar los reintentos es 'no se sabe', no 'candidato descartado'."""
    with pytest.raises(ErrorDescarga):
        leer_nota(_ClienteFallaSiempre(), "0000912345-26-000123")


class _ClienteFallaEnElExhibit:
    """Primera llamada (indice) ok; segunda (el exhibit) agota los reintentos."""

    def __init__(self):
        self.llamadas = 0

    def obtener(self, url):
        self.llamadas += 1
        if self.llamadas == 1:
            return b"<TYPE>EX-99.1<FILENAME>exhibit99-1.htm"
        raise ErrorDescarga("agotados los reintentos")


def test_error_descarga_al_leer_el_exhibit_se_propaga():
    with pytest.raises(ErrorDescarga):
        leer_nota(_ClienteFallaEnElExhibit(), "0000912345-26-000123")
