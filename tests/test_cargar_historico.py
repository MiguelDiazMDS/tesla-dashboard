import pandas as pd
import pytest

from src.cargar_historico import componer_deuda_y_liquidez
from src.fetch_edgar import CONCEPTOS, extraer_serie


def marco(**cambios):
    base = {
        "period": ["2021Q3", "2021Q4", "2022Q1"],
        "debt_current": [1.0, 1.0, 1.0],
        "debt_noncurrent": [7.0, 7.0, 7.0],
        "finance_lease_current": [0.1, 0.1, 0.1],
        "finance_lease_noncurrent": [0.2, 0.2, 0.2],
        "short_term_investments": [None, 0.131, 0.5],
    }
    base.update(cambios)
    return pd.DataFrame(base)


def test_la_deuda_total_suma_los_cuatro_componentes():
    """En 2026Q2: 1.340 + 7.721 + 78 + 203 = 9.342, igual que el balance."""
    df = componer_deuda_y_liquidez(marco())
    assert df["total_debt"].tolist() == pytest.approx([8.3, 8.3, 8.3])


def test_sin_algun_componente_no_hay_deuda_total():
    """Mejor un hueco visible que una deuda infravalorada."""
    df = componer_deuda_y_liquidez(marco(debt_current=[1.0, None, 1.0]))
    assert pd.isna(df["total_debt"].iloc[1])


def test_antes_de_su_primera_aparicion_las_inversiones_valen_cero():
    """Tesla no tuvo inversiones a corto plazo hasta 2021Q4."""
    df = componer_deuda_y_liquidez(marco())
    assert df["short_term_investments"].iloc[0] == 0.0


def test_un_hueco_posterior_a_la_primera_aparicion_se_respeta():
    df = componer_deuda_y_liquidez(marco(short_term_investments=[None, 0.131, None]))
    assert pd.isna(df["short_term_investments"].iloc[2])


def test_las_inversiones_de_2022_salen_del_concepto_antiguo():
    """En 2022Q1-Q3 Tesla etiquetaba la linea como MarketableSecuritiesCurrent."""
    facts = {"facts": {"us-gaap": {
        "ShortTermInvestments": {"units": {"USD": [
            {"end": "2022-12-31", "val": 5_932e6, "form": "10-K", "filed": "2023-01-31"}]}},
        "MarketableSecuritiesCurrent": {"units": {"USD": [
            {"end": "2022-03-31", "val": 508e6, "form": "10-Q", "filed": "2022-04-25"}]}},
    }}}
    serie = extraer_serie(facts, CONCEPTOS["short_term_investments"])
    assert serie == {"2022Q1": 508e6, "2022Q4": 5_932e6}
