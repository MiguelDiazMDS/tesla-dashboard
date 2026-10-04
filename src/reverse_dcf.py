"""Que crecimiento esta descontando el precio de la accion.

En vez de discutir si el valor propio es correcto, se despeja el crecimiento
anual de ingresos, constante durante el horizonte y comun a las dos unidades,
que hace que el valor por accion iguale al precio, manteniendo el resto de
supuestos del escenario base. Es el mejor control del sesgo de confirmacion:
se juzga si lo que descuenta el mercado es plausible.

El valor no es necesariamente monotono en el crecimiento (con margenes bajos,
crecer destruye valor por la reinversion), asi que se recorre una rejilla hasta
el primer cruce y luego se afina por biseccion.
"""
from src.sotp import UNIDADES, proyectar, suma_unidades, valor_por_accion


def _con_crecimiento(escenario: dict, g: float) -> dict:
    return {**escenario, **{
        u: {**escenario[u], "crecimiento_inicial": g, "crecimiento_final": g}
        for u in UNIDADES
    }}


def valor_con_crecimiento(g: float, base, escenario: dict, comun: dict,
                          wacc_: float, balance: dict) -> float:
    unidades = proyectar(base, _con_crecimiento(escenario, g), comun, wacc_)
    return valor_por_accion(suma_unidades(unidades), **balance)


def crecimiento_implicito(precio: float, base, escenario: dict, comun: dict,
                          wacc_: float, balance: dict, minimo: float = -0.10,
                          maximo: float = 0.80, paso: float = 0.01,
                          tolerancia: float = 1e-4) -> float | None:
    """Crecimiento anual que iguala valor y precio, o None si no hay cruce."""
    def diferencia(g):
        return valor_con_crecimiento(g, base, escenario, comun, wacc_, balance) - precio

    g_previo, d_previo = minimo, diferencia(minimo)
    if d_previo == 0:
        return g_previo
    pasos = round((maximo - minimo) / paso)
    for i in range(1, pasos + 1):
        g = minimo + i * paso
        d = diferencia(g)
        if (d_previo < 0) != (d < 0) or d == 0:
            bajo, alto, d_bajo = g_previo, g, d_previo
            while alto - bajo > tolerancia:
                medio = (bajo + alto) / 2
                d_medio = diferencia(medio)
                if (d_bajo < 0) == (d_medio < 0):
                    bajo, d_bajo = medio, d_medio
                else:
                    alto = medio
            return (bajo + alto) / 2
        g_previo, d_previo = g, d
    return None


def rejilla(base, escenario: dict, comun: dict, wacc_: float, balance: dict,
            crecimientos: list[float], margenes_automocion: list[float]) -> list[list[float]]:
    """Valor por accion para cada crecimiento (filas) y margen bruto final de
    automocion (columnas)."""
    filas = []
    for g in crecimientos:
        fila = []
        for margen in margenes_automocion:
            esc = _con_crecimiento(escenario, g)
            esc = {**esc, "automocion": {**esc["automocion"], "margen_bruto_final": margen}}
            fila.append(valor_por_accion(
                suma_unidades(proyectar(base, esc, comun, wacc_)), **balance))
        filas.append(fila)
    return filas
