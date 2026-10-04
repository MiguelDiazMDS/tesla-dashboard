"""Spike: inventario de conceptos disponibles en companyfacts para TSLA."""
import json
import os
import sys
from collections import defaultdict

import requests

CIK = "0001318605"
URL = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{CIK}.json"
UA = os.environ.get("SEC_USER_AGENT")
if not UA:
    sys.exit("Define SEC_USER_AGENT antes de ejecutar (ver .env.example)")

resp = requests.get(URL, headers={"User-Agent": UA}, timeout=120)
resp.raise_for_status()
facts = resp.json()

with open("cache/companyfacts.json", "w", encoding="utf-8") as fh:
    json.dump(facts, fh)

print("Taxonomias:", list(facts["facts"].keys()))

conceptos = facts["facts"].get("us-gaap", {})
print("Conceptos us-gaap:", len(conceptos))

# Conceptos candidatos para el esquema de financials_quarterly
BUSCAR = [
    "Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
    "CostOfRevenue", "GrossProfit", "ResearchAndDevelopmentExpense",
    "SellingGeneralAndAdministrativeExpense", "OperatingIncomeLoss",
    "NetIncomeLoss", "EarningsPerShareDiluted",
    "NetCashProvidedByUsedInOperatingActivities",
    "PaymentsToAcquirePropertyPlantAndEquipment",
    "CashAndCashEquivalentsAtCarryingValue",
    "WeightedAverageNumberOfDilutedSharesOutstanding",
    "ShareBasedCompensation",
    "ContractWithCustomerLiabilityCurrent",
    "ContractWithCustomerLiabilityNoncurrent",
    "DeferredRevenueCurrent", "DeferredRevenueNoncurrent",
]
for nombre in BUSCAR:
    if nombre in conceptos:
        unidades = conceptos[nombre]["units"]
        for unidad, valores in unidades.items():
            trimestrales = [v for v in valores if v.get("form") in ("10-Q", "10-K")]
            fechas = sorted({v["end"] for v in trimestrales})
            print(f"OK   {nombre} [{unidad}] n={len(trimestrales)} "
                  f"desde={fechas[0] if fechas else '-'} hasta={fechas[-1] if fechas else '-'}")
    else:
        print(f"FALTA {nombre}")

# Pregunta central: hay dimensiones de segmento en algun hecho?
con_dimensiones = defaultdict(int)
for nombre, cuerpo in conceptos.items():
    for valores in cuerpo["units"].values():
        for v in valores:
            if any(k not in {"start", "end", "val", "accn", "fy", "fp",
                             "form", "filed", "frame"} for k in v):
                con_dimensiones[nombre] += 1
print("\nConceptos con claves extra (posibles dimensiones):",
      dict(list(con_dimensiones.items())[:20]) or "NINGUNO")
