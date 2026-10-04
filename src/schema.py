"""Esquemas de los ficheros de datos. Sin red, sin E/S: solo declaracion."""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Campo:
    nombre: str
    tipo: str           # "str", "float" o "int"
    unidad: str         # "USD", "vehiculos", "GWh", "ratio", "fecha", "texto"
    minimo: float | None = None
    maximo: float | None = None
    obligatorio: bool = True


@dataclass(frozen=True)
class Esquema:
    nombre: str
    clave: list[str]
    campos: list[Campo] = field(default_factory=list)


TRAZABILIDAD = [
    Campo("source", "str", "texto"),
    Campo("retrieved_at", "str", "fecha"),
]

FINANCIALS = Esquema(
    nombre="financials_quarterly",
    clave=["period"],
    campos=[
        Campo("period", "str", "texto"),           # formato "2019Q1"
        Campo("filing_date", "str", "fecha"),
        # --- Consolidado (API companyfacts de la SEC) ---
        Campo("revenue_total", "float", "USD", minimo=0),
        Campo("cogs_total", "float", "USD", minimo=0),
        Campo("gross_profit_total", "float", "USD"),
        # --- Los dos segmentos reportables (estados renderizados del filing) ---
        # Tesla declara dos segmentos bajo ASC 280: automocion y energia.
        # No publica resultado operativo por segmento: I+D y SG&A no se asignan.
        Campo("revenue_auto_segment", "float", "USD", minimo=0, obligatorio=False),
        Campo("cogs_auto_segment", "float", "USD", minimo=0, obligatorio=False),
        Campo("gross_profit_auto_segment", "float", "USD", obligatorio=False),
        Campo("revenue_energy_segment", "float", "USD", minimo=0, obligatorio=False),
        Campo("cogs_energy_segment", "float", "USD", minimo=0, obligatorio=False),
        Campo("gross_profit_energy_segment", "float", "USD", obligatorio=False),
        # --- Lineas de producto DENTRO del segmento de automocion ---
        # "Services and other" no es un segmento: es una linea de este bloque.
        Campo("revenue_auto_sales", "float", "USD", minimo=0, obligatorio=False),
        Campo("revenue_auto_leasing", "float", "USD", minimo=0, obligatorio=False),
        Campo("revenue_reg_credits", "float", "USD", minimo=0, obligatorio=False),
        Campo("revenue_services", "float", "USD", minimo=0, obligatorio=False),
        # --- Lineas de producto dentro del segmento de energia ---
        Campo("revenue_energy_sales", "float", "USD", minimo=0, obligatorio=False),
        Campo("revenue_energy_leasing", "float", "USD", minimo=0,
              obligatorio=False),
        # --- Ingresos por region ---
        # Dato reportado en el filing, no una estimacion a partir de
        # matriculaciones de terceros.
        Campo("revenue_us", "float", "USD", minimo=0, obligatorio=False),
        Campo("revenue_china", "float", "USD", minimo=0, obligatorio=False),
        Campo("revenue_other", "float", "USD", minimo=0, obligatorio=False),
        Campo("opex_rd", "float", "USD", minimo=0),
        Campo("opex_sga", "float", "USD", minimo=0),
        Campo("operating_income", "float", "USD"),
        Campo("net_income_gaap", "float", "USD"),
        Campo("eps_diluted_gaap", "float", "USD", obligatorio=False),
        Campo("ocf", "float", "USD"),
        Campo("capex", "float", "USD", minimo=0),
        # Solo caja y equivalentes, pese al nombre: las inversiones a corto
        # plazo van en short_term_investments.
        Campo("cash_and_investments", "float", "USD", minimo=0),
        Campo("total_debt", "float", "USD", minimo=0),
        # Componentes de la deuda del balance, arrendamientos financieros
        # incluidos. total_debt es su suma.
        Campo("debt_current", "float", "USD", minimo=0, obligatorio=False),
        Campo("debt_noncurrent", "float", "USD", minimo=0, obligatorio=False),
        Campo("finance_lease_current", "float", "USD", minimo=0, obligatorio=False),
        Campo("finance_lease_noncurrent", "float", "USD", minimo=0,
              obligatorio=False),
        Campo("short_term_investments", "float", "USD", minimo=0),
        # Amortizaciones y deterioros del estado de flujos.
        Campo("da", "float", "USD", minimo=0),
        # Sin minimo: puede haber credito fiscal y perdidas.
        Campo("income_tax", "float", "USD"),
        Campo("pretax_income", "float", "USD"),
        Campo("shares_diluted", "float", "acciones", minimo=0, obligatorio=False),
        Campo("shares_outstanding", "float", "acciones", minimo=0,
              obligatorio=False),
        Campo("sbc", "float", "USD", minimo=0),
        Campo("deferred_revenue_current", "float", "USD", minimo=0),
        Campo("deferred_revenue_noncurrent", "float", "USD", minimo=0),
        *TRAZABILIDAD,
    ],
)

OPERATING = Esquema(
    nombre="operating_quarterly",
    clave=["period"],
    campos=[
        Campo("period", "str", "texto"),
        Campo("deliveries_total", "int", "vehiculos", minimo=0, maximo=2_000_000),
        Campo("production_total", "int", "vehiculos", minimo=0, maximo=2_000_000),
        # Series homogeneas en todo el periodo. Tesla cambio la nomenclatura en
        # 2020 al aparecer el Model Y: en 2019 publicaba "Model S/X" y "Model 3",
        # despues "Model 3/Y" y "Other Models". La linea de volumen es Model 3 y
        # luego Model 3/Y; la de nicho es Model S/X y luego Other Models.
        Campo("deliveries_volumen", "int", "vehiculos", minimo=0, maximo=2_000_000),
        Campo("deliveries_nicho", "int", "vehiculos", minimo=0, maximo=500_000),
        Campo("production_volumen", "int", "vehiculos", minimo=0, maximo=2_000_000),
        Campo("production_nicho", "int", "vehiculos", minimo=0, maximo=500_000),
        # Nombre literal que uso Tesla en ese trimestre, para no perder el dato
        # original ni la capacidad de auditar contra el documento.
        Campo("etiqueta_volumen", "str", "texto"),
        Campo("etiqueta_nicho", "str", "texto"),
        Campo("days_inventory", "float", "dias", minimo=0, maximo=200,
              obligatorio=False),
        # Siempre en GWh. Tesla reportaba en MWh hasta 2024 y en GWh despues:
        # la carga detecta la unidad en la etiqueta y normaliza.
        Campo("storage_deployed_gwh", "float", "GWh", minimo=0, maximo=200),
        # Suscripciones activas de FSD, en unidades. Tesla las publica en el
        # Update Letter solo desde finales de 2024: antes el dato no existe.
        Campo("fsd_subscriptions", "float", "suscripciones", minimo=0,
              maximo=50_000_000, obligatorio=False),
        *TRAZABILIDAD,
    ],
)

MARKET = Esquema(
    nombre="market_monthly",
    clave=["month"],
    campos=[
        Campo("month", "str", "texto"),            # formato "2019-01"
        Campo("price_close", "float", "USD", minimo=0),
        # ETF SPY como aproximacion del S&P 500, para la beta.
        Campo("spy_close", "float", "USD", minimo=0),
        # Rendimiento del bono del Tesoro a 10 anios, en tanto por uno.
        Campo("rf_10y", "float", "ratio", minimo=0, maximo=0.2),
        Campo("eurusd", "float", "ratio", minimo=0.5, maximo=2.0),
        *TRAZABILIDAD,
    ],
)

HISTORICO = Esquema(
    nombre="historico_valoraciones",
    clave=["mes"],
    campos=[
        Campo("mes", "str", "texto"),                 # "2026-09"
        Campo("fecha", "str", "fecha"),
        Campo("version_supuestos", "str", "texto"),
        Campo("huella", "str", "texto"),
        Campo("ttm_hasta", "str", "texto"),
        Campo("precio", "float", "USD", minimo=0),
        # El valor por accion puede ser negativo con supuestos extremos.
        Campo("vpa_bear", "float", "USD"),
        Campo("vpa_base", "float", "USD"),
        Campo("vpa_bull", "float", "USD"),
        # Nulo cuando ningun crecimiento entre -10 % y 80 % alcanza el precio.
        Campo("crecimiento_implicito", "float", "ratio", obligatorio=False),
        Campo("opcionalidad_implicita", "float", "USD"),
        Campo("wacc", "float", "ratio", minimo=0, maximo=1),
    ],
)
