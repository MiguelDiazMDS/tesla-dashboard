from src.filings import unir_indice


def test_unir_indice_junta_recent_y_una_pagina_antigua():
    """El orden es recent + pagina, tal como se pasan las paginas."""
    principal = {"filings": {"recent": {
        "form": ["10-Q", "10-K"],
        "reportDate": ["2026-06-30", "2025-12-31"],
        "filingDate": ["2026-07-23", "2026-01-29"],
        "accessionNumber": ["a", "b"],
    }}}
    pagina = {
        "form": ["10-Q"],
        "reportDate": ["2018-09-30"],
        "filingDate": ["2018-10-26"],
        "accessionNumber": ["c"],
    }
    indice = unir_indice(principal, [pagina])
    assert indice == {
        "form": ["10-Q", "10-K", "10-Q"],
        "reportDate": ["2026-06-30", "2025-12-31", "2018-09-30"],
        "filingDate": ["2026-07-23", "2026-01-29", "2018-10-26"],
        "accessionNumber": ["a", "b", "c"],
    }


def test_unir_indice_sin_paginas_es_igual_a_recent():
    principal = {"filings": {"recent": {
        "form": ["10-Q"],
        "reportDate": ["2026-06-30"],
        "filingDate": ["2026-07-23"],
        "accessionNumber": ["a"],
    }}}
    assert unir_indice(principal, []) == principal["filings"]["recent"]
