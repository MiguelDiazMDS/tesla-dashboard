"""Suma de partes de las dos unidades que Tesla reporta: automocion y energia.

Tesla no asigna I+D ni SG&A por segmento, asi que el resultado operativo de
cada unidad depende de un reparto que es un juicio propio: la I+D va en la
proporcion `reparto_id_automocion` a automocion y el resto a energia, y el
SG&A en proporcion a los ingresos de cada una.

Robotaxi, FSD y Optimus quedan fuera: su valor es la opcionalidad implicita,
que se calcula por diferencia con la capitalizacion.
"""
from dataclasses import dataclass

from src.dcf import nopat, trayectoria, valor_presente, valor_terminal
from src.supuestos import UNIDADES
from src.ttm import SALDOS

CAMPOS_BASE_FLUJO = (
    "revenue_total", "revenue_auto_segment", "gross_profit_auto_segment",
    "revenue_energy_segment", "gross_profit_energy_segment",
    "opex_rd", "opex_sga",
)
CAMPOS_BASE_SALDO = SALDOS


@dataclass(frozen=True)
class AnioBase:
    """Punto de partida de la proyeccion: los doce ultimos meses conocidos."""
    ingresos: dict[str, float]
    margen_bruto: dict[str, float]
    id_sobre_ingresos: float
    sga_sobre_ingresos: float


@dataclass(frozen=True)
class Proyeccion:
    ingresos: list[float]
    ebit: list[float]
    fcff: list[float]
    valor: float


def anio_base(ttm: dict[str, float]) -> AnioBase:
    ingresos = {"automocion": ttm["revenue_auto_segment"],
                "energia": ttm["revenue_energy_segment"]}
    margen = {
        "automocion": ttm["gross_profit_auto_segment"] / ingresos["automocion"],
        "energia": ttm["gross_profit_energy_segment"] / ingresos["energia"],
    }
    total = ttm["revenue_total"]
    return AnioBase(ingresos, margen, ttm["opex_rd"] / total, ttm["opex_sga"] / total)


def proyectar(base: AnioBase, escenario: dict, comun: dict, wacc_base: float,
              reparto_id: float | None = None) -> dict[str, Proyeccion]:
    """Proyecta las dos unidades y descuenta sus flujos libres.

    Crecimiento, margen bruto y gastos sobre ingresos van en linea recta desde
    el anio base hasta el valor final del escenario. La reinversion es el
    aumento de ingresos dividido entre la ratio ventas/capital de la unidad.
    """
    n = comun["horizonte_anios"]
    tipo = comun["tipo_impositivo"]
    g_terminal = comun["crecimiento_terminal"]
    reparto = comun["reparto_id_automocion"] if reparto_id is None else reparto_id
    cuota_id = {"automocion": reparto, "energia": 1 - reparto}

    ingresos: dict[str, list[float]] = {}
    for unidad in UNIDADES:
        supuesto = escenario[unidad]
        serie, nivel = [], base.ingresos[unidad]
        for g in trayectoria(supuesto["crecimiento_inicial"],
                             supuesto["crecimiento_final"], n):
            nivel *= 1 + g
            serie.append(nivel)
        ingresos[unidad] = serie
    total = [sum(ingresos[u][t] for u in UNIDADES) for t in range(n)]
    ratio_id = trayectoria(base.id_sobre_ingresos, escenario["id_sobre_ingresos_final"], n)
    ratio_sga = trayectoria(base.sga_sobre_ingresos, escenario["sga_sobre_ingresos_final"], n)

    resultado: dict[str, Proyeccion] = {}
    for unidad in UNIDADES:
        supuesto = escenario[unidad]
        margenes = trayectoria(base.margen_bruto[unidad], supuesto["margen_bruto_final"], n)
        ebit, fcff, anterior = [], [], base.ingresos[unidad]
        for t in range(n):
            ventas = ingresos[unidad][t]
            gasto_id = ratio_id[t] * total[t] * cuota_id[unidad]
            gasto_sga = ratio_sga[t] * ventas
            resultado_operativo = ventas * margenes[t] - gasto_id - gasto_sga
            reinversion = (ventas - anterior) / supuesto["ventas_sobre_capital"]
            ebit.append(resultado_operativo)
            fcff.append(nopat(resultado_operativo, tipo) - reinversion)
            anterior = ventas
        tasa = wacc_base + supuesto["ajuste_wacc"]
        terminal = valor_terminal(nopat(ebit[-1], tipo) * (1 + g_terminal),
                                  tasa, g_terminal, comun["roic_terminal"])
        valor = valor_presente(fcff, tasa) + terminal / (1 + tasa) ** n
        resultado[unidad] = Proyeccion(ingresos[unidad], ebit, fcff, valor)
    return resultado


def suma_unidades(unidades: dict[str, Proyeccion]) -> float:
    return sum(p.valor for p in unidades.values())


def valor_por_accion(valor_unidades: float, caja: float, inversiones: float,
                     deuda: float, acciones: float) -> float:
    """Valor de las unidades mas liquidez menos deuda, por accion."""
    return (valor_unidades + caja + inversiones - deuda) / acciones
