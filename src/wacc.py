"""Coste de capital: beta por regresion, CAPM y media ponderada con la deuda."""


def rentabilidades(precios: list[float]) -> list[float]:
    """Rentabilidades simples entre precios consecutivos."""
    return [b / a - 1 for a, b in zip(precios, precios[1:])]


def beta(rent_activo: list[float], rent_mercado: list[float]) -> float:
    """Pendiente de la regresion del activo sobre el mercado: cov / var."""
    if len(rent_activo) != len(rent_mercado):
        raise ValueError("las dos series de rentabilidades deben tener la misma longitud")
    if len(rent_activo) < 12:
        raise ValueError("hacen falta al menos 12 pares de rentabilidades")
    n = len(rent_activo)
    media_a = sum(rent_activo) / n
    media_m = sum(rent_mercado) / n
    cov = sum((a - media_a) * (m - media_m)
              for a, m in zip(rent_activo, rent_mercado)) / (n - 1)
    var = sum((m - media_m) ** 2 for m in rent_mercado) / (n - 1)
    if var == 0:
        raise ValueError("el mercado no varia: la beta no esta definida")
    return cov / var


def coste_capital_propio(tipo_sin_riesgo: float, beta_: float,
                         prima_riesgo: float) -> float:
    """CAPM: tipo sin riesgo mas beta por prima de riesgo de mercado."""
    return tipo_sin_riesgo + beta_ * prima_riesgo


def wacc(coste_acciones: float, coste_deuda_antes_impuestos: float,
         tipo_impositivo: float, valor_acciones: float, valor_deuda: float) -> float:
    """Media del coste de acciones y deuda, ponderada por valor de mercado."""
    total = valor_acciones + valor_deuda
    if total <= 0:
        raise ValueError("el valor de la empresa debe ser positivo")
    return (valor_acciones / total * coste_acciones
            + valor_deuda / total * coste_deuda_antes_impuestos * (1 - tipo_impositivo))
