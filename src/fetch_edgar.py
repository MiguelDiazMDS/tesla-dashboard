"""Extrae financieros consolidados trimestrales de la API XBRL de la SEC."""
from datetime import date

CIK = "0001318605"
URL_COMPANYFACTS = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{CIK}.json"

# Conceptos alternativos por campo. El orden importa: se usa el primero
# disponible. Verificado contra companyfacts en la fase 0.
CONCEPTOS = {
    "revenue_total": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
    ],
    "cogs_total": ["CostOfRevenue", "CostOfGoodsAndServicesSold"],
    "gross_profit_total": ["GrossProfit"],
    "opex_rd": ["ResearchAndDevelopmentExpense"],
    "opex_sga": ["SellingGeneralAndAdministrativeExpense"],
    "operating_income": ["OperatingIncomeLoss"],
    "net_income_gaap": ["NetIncomeLoss"],
    "eps_diluted_gaap": ["EarningsPerShareDiluted"],
    "ocf": ["NetCashProvidedByUsedInOperatingActivities"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment"],
    "cash_and_investments": ["CashAndCashEquivalentsAtCarryingValue"],
    "shares_diluted": ["WeightedAverageNumberOfDilutedSharesOutstanding"],
    "shares_outstanding": ["CommonStockSharesOutstanding"],
    "sbc": ["ShareBasedCompensation"],
    "deferred_revenue_current": [
        "ContractWithCustomerLiabilityCurrent", "DeferredRevenueCurrent",
    ],
    "deferred_revenue_noncurrent": [
        "ContractWithCustomerLiabilityNoncurrent", "DeferredRevenueNoncurrent",
    ],
    "income_tax": ["IncomeTaxExpenseBenefit"],
    "pretax_income": [
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
    ],
    # En 2022Q1-Q3 el balance llamaba a esta linea "Short-term marketable
    # securities" y la etiquetaba con MarketableSecuritiesCurrent.
    "short_term_investments": ["ShortTermInvestments", "MarketableSecuritiesCurrent"],
    # LongTermDebt es la deuda no corriente sin arrendamientos: sumada a los
    # otros tres cuadra con las dos lineas del balance (verificado en 2026Q2).
    "debt_current": ["DebtCurrent"],
    "debt_noncurrent": ["LongTermDebt"],
    "finance_lease_current": ["FinanceLeaseLiabilityCurrent"],
    "finance_lease_noncurrent": ["FinanceLeaseLiabilityNoncurrent"],
}

TRIMESTRE_POR_MES_FINAL = {3: 1, 6: 2, 9: 3, 12: 4}

# Tesla dividio sus acciones 5:1 el 31 de agosto de 2020 y 3:1 el 25 de agosto
# de 2022. Un dato publicado antes de una de esas fechas esta expresado en la
# base de entonces, y los filings dejan de reexpresar los trimestres antiguos,
# asi que hay que normalizarlo a la base actual para que la serie sea comparable.
SPLIT_5_POR_1 = date(2020, 8, 31)
SPLIT_3_POR_1 = date(2022, 8, 25)

# Como se comporta cada magnitud ante la reconstruccion del cuarto trimestre.
CLASE_MAGNITUD = {
    "revenue_total": "flujo",
    "cogs_total": "flujo",
    "gross_profit_total": "flujo",
    "opex_rd": "flujo",
    "opex_sga": "flujo",
    "operating_income": "flujo",
    "net_income_gaap": "flujo",
    "ocf": "flujo_ytd",
    "capex": "flujo_ytd",
    "sbc": "flujo_ytd",
    "cash_and_investments": "balance",
    "shares_outstanding": "balance",
    "total_debt": "balance",
    "deferred_revenue_current": "balance",
    "deferred_revenue_noncurrent": "balance",
    # El promedio ponderado del ejercicio no es la suma de los trimestres, y el
    # BPA tampoco: su Q4 no se puede obtener por diferencia.
    "shares_diluted": "no_aditiva",
    "eps_diluted_gaap": "no_aditiva",
    "income_tax": "flujo",
    "pretax_income": "flujo",
    "short_term_investments": "balance",
    "debt_current": "balance",
    "debt_noncurrent": "balance",
    "finance_lease_current": "balance",
    "finance_lease_noncurrent": "balance",
}


def periodo_de_fechas(inicio: str, fin: str) -> str | None:
    """Devuelve "2019Q1" si el intervalo es un trimestre natural, None si no.

    Un hecho de 10-K abarca el anio completo y debe descartarse aqui: el cuarto
    trimestre se calcula despues por diferencia.
    """
    d_inicio = date.fromisoformat(inicio)
    d_fin = date.fromisoformat(fin)
    dias = (d_fin - d_inicio).days
    if not 80 <= dias <= 100:
        return None
    trimestre = TRIMESTRE_POR_MES_FINAL.get(d_fin.month)
    if trimestre is None:
        return None
    return f"{d_fin.year}Q{trimestre}"


def extraer_serie_con_filed(
    facts: dict, conceptos: list[str]
) -> dict[str, tuple[str, float]]:
    """Serie {periodo: (filed, valor)} fusionando los conceptos de la lista.

    El orden expresa preferencia: para cada periodo gana el concepto mas
    preferente que tenga dato, y los siguientes solo rellenan los huecos. Asi un
    concepto moderno con poca historia no deja fuera los periodos antiguos.

    Dentro de un mismo concepto, cuando un periodo aparece en varios filings se
    conserva el mas reciente: es el que incorpora reexpresiones y splits.
    """
    us_gaap = facts["facts"]["us-gaap"]
    presentes = [c for c in conceptos if c in us_gaap]
    if not presentes:
        raise KeyError(
            f"ninguno de los conceptos existe en companyfacts: {conceptos}"
        )

    serie: dict[str, tuple[str, float]] = {}
    for concepto in presentes:
        propia: dict[str, tuple[str, float]] = {}
        for hechos in us_gaap[concepto]["units"].values():
            for hecho in hechos:
                if hecho.get("form") not in ("10-Q", "10-K"):
                    continue
                if "start" in hecho:
                    periodo = periodo_de_fechas(hecho["start"], hecho["end"])
                else:
                    fin = date.fromisoformat(hecho["end"])
                    trimestre = TRIMESTRE_POR_MES_FINAL.get(fin.month)
                    periodo = f"{fin.year}Q{trimestre}" if trimestre else None
                if not periodo:
                    continue
                filed = hecho.get("filed", "")
                if periodo not in propia or filed > propia[periodo][0]:
                    propia[periodo] = (filed, hecho["val"])
        for periodo, valor in propia.items():
            serie.setdefault(periodo, valor)
    return serie


def extraer_serie(facts: dict, conceptos: list[str]) -> dict[str, float]:
    """Serie {periodo: valor}, con el valor del filing mas reciente."""
    return {
        periodo: valor
        for periodo, (_, valor) in extraer_serie_con_filed(facts, conceptos).items()
    }


def extraer_serie_anual(facts: dict, conceptos: list[str]) -> dict[int, float]:
    """Serie {anio: valor} de los hechos que abarcan un ejercicio completo.

    Devuelve un diccionario vacio si ningun concepto de la lista existe, porque
    la ausencia de dato anual solo impide reconstruir Q4, no es un error fatal.
    """
    us_gaap = facts["facts"]["us-gaap"]
    for concepto in conceptos:
        if concepto not in us_gaap:
            continue
        serie: dict[int, float] = {}
        for hechos in us_gaap[concepto]["units"].values():
            for hecho in hechos:
                if hecho.get("form") != "10-K" or "start" not in hecho:
                    continue
                inicio = date.fromisoformat(hecho["start"])
                fin = date.fromisoformat(hecho["end"])
                if 350 <= (fin - inicio).days <= 380:
                    serie[fin.year] = hecho["val"]
        return serie
    return {}


def completar_q4(
    trimestres: dict[str, float], anuales: dict[int, float]
) -> dict[str, float]:
    """Calcula Q4 como anual menos la suma de los tres primeros trimestres.

    Solo aplicable a magnitudes de flujo. Un anio sin sus tres trimestres, o con
    un Q4 ya informado, se deja intacto.
    """
    resultado = dict(trimestres)
    for anio, total_anual in anuales.items():
        if f"{anio}Q4" in resultado:
            continue
        previos = [f"{anio}Q{i}" for i in (1, 2, 3)]
        if not all(p in resultado for p in previos):
            continue
        resultado[f"{anio}Q4"] = total_anual - sum(resultado[p] for p in previos)
    return resultado


def factor_split(filed: str) -> int:
    """Por cuanto multiplicar un recuento de acciones publicado en esa fecha."""
    f = date.fromisoformat(filed)
    if f < SPLIT_5_POR_1:
        return 15
    if f < SPLIT_3_POR_1:
        return 3
    return 1


def normalizar_acciones(
    hechos: dict[str, tuple[str, float]]
) -> dict[str, float]:
    """Lleva un recuento de acciones {periodo: (filed, valor)} a la base actual."""
    return {
        periodo: valor * factor_split(filed)
        for periodo, (filed, valor) in hechos.items()
    }


# Duracion en dias de cada acumulado del ejercicio, con holgura para los
# cierres que no caen en fin de mes natural.
DURACION_ACUMULADO = {1: (80, 100), 2: (170, 190), 3: (260, 285), 4: (350, 380)}


def tramo_ytd(inicio: str, fin: str) -> tuple[int, int] | None:
    """Devuelve (anio, trimestres acumulados) si el hecho es un acumulado.

    El estado de flujos de efectivo se publica acumulado desde enero, no por
    trimestres sueltos. Un periodo que no arranque en enero no es un acumulado.
    """
    i = date.fromisoformat(inicio)
    f = date.fromisoformat(fin)
    if i.month != 1 or f.month not in TRIMESTRE_POR_MES_FINAL:
        return None
    dias = (f - i).days
    for n, (minimo, maximo) in DURACION_ACUMULADO.items():
        if minimo <= dias <= maximo:
            return (f.year, n)
    return None


def extraer_serie_ytd(facts: dict, conceptos: list[str]) -> dict[str, float]:
    """Trimestres discretos a partir de los acumulados del estado de flujos.

    Q1 es el acumulado de tres meses; cada trimestre siguiente es la diferencia
    con el acumulado anterior. Un trimestre cuyo acumulado previo falte se omite:
    es preferible un hueco visible a un valor inventado.
    """
    us_gaap = facts["facts"]["us-gaap"]
    presentes = [c for c in conceptos if c in us_gaap]
    if not presentes:
        raise KeyError(
            f"ninguno de los conceptos existe en companyfacts: {conceptos}"
        )

    acumulados: dict[tuple[int, int], tuple[str, float]] = {}
    for concepto in presentes:
        propios: dict[tuple[int, int], tuple[str, float]] = {}
        for hechos in us_gaap[concepto]["units"].values():
            for hecho in hechos:
                if hecho.get("form") not in ("10-Q", "10-K") or "start" not in hecho:
                    continue
                clave = tramo_ytd(hecho["start"], hecho["end"])
                if clave is None:
                    continue
                filed = hecho.get("filed", "")
                if clave not in propios or filed > propios[clave][0]:
                    propios[clave] = (filed, hecho["val"])
        for clave, valor in propios.items():
            acumulados.setdefault(clave, valor)

    serie: dict[str, float] = {}
    for (anio, n), (_, valor) in acumulados.items():
        if n == 1:
            serie[f"{anio}Q1"] = valor
            continue
        previo = acumulados.get((anio, n - 1))
        if previo is not None:
            serie[f"{anio}Q{n}"] = valor - previo[1]
    return serie
