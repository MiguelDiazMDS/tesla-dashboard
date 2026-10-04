import pytest

from src.cargar_update_letter import leer_carta, leer_pdf
from src.http_client import ErrorDescarga


class _ClienteFallaSiempre:
    def obtener(self, url):
        raise ErrorDescarga("agotados los reintentos")


def test_error_descarga_al_leer_el_txt_de_la_carta_se_propaga():
    """Agotar los reintentos es 'no se sabe', no 'siguiente candidato'."""
    with pytest.raises(ErrorDescarga):
        leer_carta(_ClienteFallaSiempre(), ["0000912345-26-000123"])


def test_error_descarga_al_leer_el_pdf_se_propaga():
    with pytest.raises(ErrorDescarga):
        leer_pdf(_ClienteFallaSiempre(), "2022Q1")
