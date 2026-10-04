"""Matematica financiera del descuento de flujos. Sin datos, sin supuestos."""


def trayectoria(inicial: float, final: float, anios: int) -> list[float]:
    """Valores del anio 1 al N, en linea recta de `inicial` a `final`."""
    if anios < 1:
        raise ValueError("el horizonte debe ser de al menos un anio")
    if anios == 1:
        return [final]
    paso = (final - inicial) / (anios - 1)
    return [inicial + paso * i for i in range(anios)]


def valor_presente(flujos: list[float], tasa: float) -> float:
    """Valor hoy de flujos que llegan al final de los anios 1, 2, ..., N."""
    return sum(f / (1 + tasa) ** t for t, f in enumerate(flujos, start=1))


def valor_terminal(nopat_siguiente: float, tasa: float, crecimiento: float,
                   roic: float) -> float:
    """Valor al final del anio N de los flujos a perpetuidad (Gordon).

    El flujo libre del anio N+1 es el NOPAT menos la reinversion que exige
    crecer a `crecimiento` con una rentabilidad `roic`: FCF = NOPAT (1 - g/ROIC).
    Con NOPAT negativo no hay reinversion que descontar: una unidad que pierde
    dinero no "desinvierte" para crecer, asi que la perdida se perpetua entera
    en vez de encogerse por un credito de reinversion que no existe.
    """
    if tasa <= crecimiento:
        raise ValueError(
            f"el coste de capital ({tasa:.2%}) debe superar al crecimiento "
            f"terminal ({crecimiento:.2%})")
    if roic <= crecimiento:
        raise ValueError(
            f"el ROIC terminal ({roic:.2%}) debe superar al crecimiento "
            f"terminal ({crecimiento:.2%})")
    # Con perdidas no hay reinversion que descontar: una unidad que pierde
    # dinero no "desinvierte" para crecer, y la perdida se perpetua entera.
    reinversion = crecimiento / roic if nopat_siguiente > 0 else 0.0
    return nopat_siguiente * (1 - reinversion) / (tasa - crecimiento)


def nopat(ebit: float, tipo_impositivo: float) -> float:
    """Resultado operativo tras impuestos; sin credito fiscal si hay perdida."""
    return ebit * (1 - tipo_impositivo) if ebit > 0 else ebit
