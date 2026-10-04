import pytest

from src.cargar_segmentos import leer_filing
from src.http_client import ErrorDescarga


class _ClienteFallaEnElSummary:
    def obtener(self, url):
        raise ErrorDescarga("agotados los reintentos")


def test_error_descarga_al_leer_el_filing_summary_se_propaga():
    with pytest.raises(ErrorDescarga):
        leer_filing(_ClienteFallaEnElSummary(), "0000912345-26-000123", "10-Q", "2026Q1")


class _ClienteFallaEnElInforme:
    """Primera llamada (FilingSummary) ok; el informe agota los reintentos."""

    def __init__(self):
        self.llamadas = 0

    def obtener(self, url):
        self.llamadas += 1
        if self.llamadas == 1:
            return b"<FilingSummary/>"
        raise ErrorDescarga("agotados los reintentos")


def test_error_descarga_al_leer_un_informe_se_propaga(monkeypatch):
    import src.cargar_segmentos as cargar_segmentos
    monkeypatch.setattr(cargar_segmentos, "resolver_informe",
                        lambda summary, nombre: "R1.htm")
    with pytest.raises(ErrorDescarga):
        leer_filing(_ClienteFallaEnElInforme(), "0000912345-26-000123", "10-Q", "2026Q1")
