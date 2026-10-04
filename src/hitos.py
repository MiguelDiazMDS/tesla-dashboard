"""Hitos: lo que aun debe producirse y la credibilidad de las fechas de Tesla.

Funciones puras sobre los datos de data/milestones.yaml y los CSV. Las fechas
vagas ("2026", "2026-Q3", "2026-09") se leen como el ultimo dia de su
periodo, la lectura mas favorable para Tesla.
"""
import calendar
import re
import statistics
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import yaml

RUTA = Path("data/milestones.yaml")
TIPOS_PROMESA = {"oficial", "musk"}
TIPOS_EVIDENCIA = {"oficial", "musk", "registro", "tercero"}
ETIQUETAS = {"R", "E"}
ESTADOS_HISTORIAL = {"cumplido", "vigente", "abandonado"}
TIPOS_PASO = {"mercado"}
IDS_HITOS_PRIORITARIOS = {"robotaxi-escala", "optimus", "fsd", "automovil", "energia", "semi"}
DIAS_POR_MES = 365.25 / 12


class HitosInvalidos(Exception):
    """El fichero de hitos esta incompleto o es incoherente."""


def fin_de_periodo(valor) -> date:
    """Ultimo dia del periodo que nombra el texto; una fecha completa, tal cual."""
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    texto = str(valor).strip()
    if m := re.fullmatch(r"(\d{4})", texto):
        return date(int(m[1]), 12, 31)
    if m := re.fullmatch(r"(\d{4})-Q([1-4])", texto):
        anio, mes = int(m[1]), int(m[2]) * 3
        return date(anio, mes, calendar.monthrange(anio, mes)[1])
    if m := re.fullmatch(r"(\d{4})-(\d{2})", texto):
        anio, mes = int(m[1]), int(m[2])
        if 1 <= mes <= 12:
            return date(anio, mes, calendar.monthrange(anio, mes)[1])
    if m := re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", texto):
        try:
            return date(int(m[1]), int(m[2]), int(m[3]))
        except ValueError:
            pass
    raise HitosInvalidos(f"fecha no reconocida: {valor!r} (usa AAAA, AAAA-Qn, AAAA-MM o AAAA-MM-DD)")


def _fecha_periodo(valor, donde: str) -> date:
    """fin_de_periodo, pero con la ruta del fallo si la fecha no se reconoce."""
    try:
        return fin_de_periodo(valor)
    except HitosInvalidos as e:
        raise HitosInvalidos(f"{donde}: {e}") from e


def fecha_exacta(valor, donde: str) -> date:
    """Fecha completa (date, datetime o AAAA-MM-DD); rechaza periodos vagos."""
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    texto = str(valor).strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", texto):
        raise HitosInvalidos(f"{donde}: debe ser una fecha completa AAAA-MM-DD, no un periodo")
    return _fecha_periodo(texto, donde)


def _numero(valor) -> bool:
    return isinstance(valor, (int, float)) and not isinstance(valor, bool)


def _entero(valor) -> bool:
    return isinstance(valor, int) and not isinstance(valor, bool)


def _exigir(bloque: dict, campos: tuple[str, ...], donde: str) -> None:
    for campo in campos:
        if bloque.get(campo) in (None, ""):
            raise HitosInvalidos(f"{donde}: falta '{campo}'")


def _lista(valor, donde: str) -> list:
    if not isinstance(valor, list):
        raise HitosInvalidos(f"{donde}: debe ser una lista")
    return valor


def _lista_de_dicts(valor, donde: str) -> list:
    lst = _lista(valor, donde)
    for i, elem in enumerate(lst):
        if not isinstance(elem, dict):
            raise HitosInvalidos(f"{donde}[{i}]: debe ser un objeto")
    return lst


def _lista_de_texto(valor, donde: str) -> list:
    lst = _lista(valor, donde)
    for i, elem in enumerate(lst):
        if not isinstance(elem, str):
            raise HitosInvalidos(f"{donde}[{i}]: debe ser texto")
    return lst


def _enlace(bloque: dict, donde: str) -> None:
    _exigir(bloque, ("enlace",), donde)
    enlace = str(bloque["enlace"])
    if not enlace.startswith("https://"):
        raise HitosInvalidos(f"{donde}: el enlace debe empezar por https://")
    dominio = enlace[len("https://"):].split("/")[0]
    if "." not in dominio:
        raise HitosInvalidos(f"{donde}: el enlace debe tener un dominio valido")


def _promesa(p: dict, donde: str) -> None:
    _exigir(p, ("declarada", "fecha_prometida", "fuente_tipo", "fuente"), donde)
    _enlace(p, donde)
    if p["fuente_tipo"] not in TIPOS_PROMESA:
        raise HitosInvalidos(f"{donde}: fuente_tipo debe ser oficial o musk")
    declarada = fecha_exacta(p["declarada"], f"{donde}.declarada")
    prometida = _fecha_periodo(p["fecha_prometida"], f"{donde}.fecha_prometida")
    if declarada > prometida:
        raise HitosInvalidos(f"{donde}: declarada despues de la fecha prometida")


def _firma_promesa(p: dict, donde: str) -> tuple:
    """Lo que identifica una promesa: enlace, declarada, fecha prometida y cita."""
    return (str(p["enlace"]), fecha_exacta(p["declarada"], f"{donde}.declarada"),
            str(p["fecha_prometida"]), p.get("cita") or "")


def _evidencia(e: dict, donde: str) -> None:
    _exigir(e, ("fecha", "fuente_tipo", "fuente"), donde)
    _enlace(e, donde)
    if e["fuente_tipo"] not in TIPOS_EVIDENCIA:
        raise HitosInvalidos(f"{donde}: fuente_tipo debe ser uno de {sorted(TIPOS_EVIDENCIA)}")
    fecha_exacta(e["fecha"], f"{donde}.fecha")


def validar(datos) -> dict:
    """Devuelve los mismos datos si son validos; si no, lanza con la ruta del fallo."""
    if datos is None:
        raise HitosInvalidos("el fichero esta vacio")
    if not isinstance(datos, dict):
        raise HitosInvalidos("raiz: debe ser un objeto")
    _exigir(datos, ("version", "hitos", "historial", "transversal"), "raiz")

    hitos = _lista_de_dicts(datos["hitos"], "hitos")
    if not hitos:
        raise HitosInvalidos("hitos: no puede estar vacia")
    historial = _lista_de_dicts(datos["historial"], "historial")

    ids = set()

    def registrar_id(i, donde):
        if i in ids:
            raise HitosInvalidos(f"{donde}: id duplicado '{i}'")
        ids.add(i)

    ids_capa1 = set()
    prioridades = set()
    firmas = {}

    def registrar_promesa(p, donde):
        firma = _firma_promesa(p, donde)
        if firma in firmas:
            raise HitosInvalidos(f"{donde}: promesa repetida (ya esta en {firmas[firma]})")
        firmas[firma] = donde

    for h in hitos:
        donde = f"hitos.{h.get('id')}"
        _exigir(h, ("id", "prioridad", "titulo", "que_debe_ocurrir", "que_demostraria"), donde)
        if "objetivo_tesla" in h:
            raise HitosInvalidos(f"{donde}: objetivo_tesla ya no se usa; la promesa vigente se deriva")
        registrar_id(h["id"], donde)
        ids_capa1.add(h["id"])
        if not _entero(h["prioridad"]):
            raise HitosInvalidos(f"{donde}: prioridad debe ser un entero")
        if h["prioridad"] in prioridades:
            raise HitosInvalidos(f"{donde}: prioridad repetida {h['prioridad']}")
        prioridades.add(h["prioridad"])

        pasos_raw = h.get("pasos")
        pasos_lista = _lista_de_dicts(pasos_raw, f"{donde}.pasos") if pasos_raw is not None else []
        pasos = {}
        ids_paso = set()
        for paso in pasos_lista:
            dp = f"{donde}.pasos.{paso.get('id')}"
            _exigir(paso, ("id", "texto", "etiqueta"), dp)
            if paso["id"] in ids_paso:
                raise HitosInvalidos(f"{dp}: id de paso duplicado '{paso['id']}'")
            ids_paso.add(paso["id"])
            if paso["etiqueta"] not in ETIQUETAS:
                raise HitosInvalidos(f"{dp}: etiqueta debe ser R o E")
            if paso.get("tipo") is not None and paso["tipo"] not in TIPOS_PASO:
                raise HitosInvalidos(f"{dp}: tipo debe ser uno de {sorted(TIPOS_PASO)}")
            if paso.get("nota") is not None and not isinstance(paso["nota"], str):
                raise HitosInvalidos(f"{dp}: nota debe ser texto")
            if paso.get("cumplido"):
                _evidencia(paso["cumplido"], f"{dp}.cumplido")
                es_tercero = paso["cumplido"]["fuente_tipo"] == "tercero"
                if es_tercero != (paso["etiqueta"] == "E"):
                    raise HitosInvalidos(
                        f"{dp}: la etiqueta debe ser E si la evidencia es de terceros, y R si no")
                if paso.get("requiere_valor") and not _numero(paso["cumplido"].get("valor")):
                    raise HitosInvalidos(f"{dp}.cumplido: valor debe ser numerico")
            pasos[paso["id"]] = paso

        requeridos_raw = h.get("requeridos")
        requeridos = (_lista_de_texto(requeridos_raw, f"{donde}.requeridos")
                      if requeridos_raw is not None else [])
        for requerido in requeridos:
            if requerido not in pasos:
                raise HitosInvalidos(f"{donde}: requeridos nombra un paso inexistente '{requerido}'")

        promesas_raw = h.get("promesas")
        promesas = (_lista_de_dicts(promesas_raw, f"{donde}.promesas")
                    if promesas_raw is not None else [])
        for i, p in enumerate(promesas):
            dp = f"{donde}.promesas[{i}]"
            _promesa(p, dp)
            registrar_promesa(p, dp)
            if p.get("paso") is not None and p["paso"] not in pasos:
                raise HitosInvalidos(f"{dp}: paso inexistente '{p['paso']}'")
            hecho = pasos[p["paso"]].get("cumplido") if p.get("paso") is not None else None
            if hecho and (fecha_exacta(p["declarada"], f"{dp}.declarada")
                          > fecha_exacta(hecho["fecha"], f"{dp}.paso")):
                raise HitosInvalidos(f"{dp}: declarada posterior al cumplimiento del paso '{p['paso']}'")

        if h.get("estancado"):
            _exigir(h["estancado"], ("desde", "motivo", "fuente"), f"{donde}.estancado")
            _enlace(h["estancado"], f"{donde}.estancado")
            fecha_exacta(h["estancado"]["desde"], f"{donde}.estancado.desde")

    if ids_capa1 != IDS_HITOS_PRIORITARIOS:
        raise HitosInvalidos(f"hitos: los ids deben ser exactamente {sorted(IDS_HITOS_PRIORITARIOS)}")

    for h in historial:
        donde = f"historial.{h.get('id')}"
        _exigir(h, ("id", "titulo", "criterio", "promesas", "estado"), donde)
        registrar_id(h["id"], donde)
        if h["estado"] not in ESTADOS_HISTORIAL:
            raise HitosInvalidos(f"{donde}: estado debe ser uno de {sorted(ESTADOS_HISTORIAL)}")
        promesas = _lista_de_dicts(h["promesas"], f"{donde}.promesas")
        if not promesas:
            raise HitosInvalidos(f"{donde}.promesas: no puede estar vacia")
        for i, p in enumerate(promesas):
            dp = f"{donde}.promesas[{i}]"
            _promesa(p, dp)
            registrar_promesa(p, dp)
            if "paso" in p:
                raise HitosInvalidos(f"{dp}: paso solo se admite en las promesas de los hitos prioritarios")
        if h["estado"] == "cumplido":
            if not h.get("cumplimiento"):
                raise HitosInvalidos(f"{donde}: un hito cumplido necesita cumplimiento")
            _evidencia(h["cumplimiento"], f"{donde}.cumplimiento")
            cumplida = fecha_exacta(h["cumplimiento"]["fecha"], f"{donde}.cumplimiento.fecha")
            for i, p in enumerate(promesas):
                declarada = fecha_exacta(p["declarada"], f"{donde}.promesas[{i}].declarada")
                if declarada > cumplida:
                    raise HitosInvalidos(f"{donde}.promesas[{i}]: declarada posterior al cumplimiento")

    guia = datos["transversal"].get("capex_guia")
    if guia:
        _exigir(guia, ("anio", "importe", "texto", "fuente_tipo", "fuente"), "transversal.capex_guia")
        _enlace(guia, "transversal.capex_guia")
        if not _numero(guia["importe"]):
            raise HitosInvalidos("transversal.capex_guia: importe debe ser numerico")
        if not _entero(guia["anio"]):
            raise HitosInvalidos("transversal.capex_guia: anio debe ser un entero")
        if guia["fuente_tipo"] not in TIPOS_EVIDENCIA:
            raise HitosInvalidos(
                f"transversal.capex_guia: fuente_tipo debe ser uno de {sorted(TIPOS_EVIDENCIA)}")

    seguridad_raw = datos["transversal"].get("seguridad")
    seguridad = (_lista_de_dicts(seguridad_raw, "transversal.seguridad")
                 if seguridad_raw is not None else [])
    for s in seguridad:
        dp = f"transversal.seguridad.{s.get('id')}"
        _exigir(s, ("id", "texto", "abierta_desde", "estado", "fuente"), dp)
        registrar_id(s["id"], dp)
        _enlace(s, dp)
        fecha_exacta(s["abierta_desde"], f"{dp}.abierta_desde")

    return datos


def cargar(ruta: Path = RUTA) -> dict:
    try:
        datos = yaml.safe_load(Path(ruta).read_text(encoding="utf-8"))
    except yaml.YAMLError as error:
        raise HitosInvalidos(f"YAML mal formado: {error}") from error
    return validar(datos)


FECHA_BASE_MERCADOS = date(2026, 9, 23)
UMBRALES = {
    "fsd_suscripciones": 2.5e6, "fsd_mercados_nuevos": 5,
    "auto_margen_sin_creditos": 0.20, "auto_margen_operativo": 0.10,
    "energia_gwh_12m": 80.0, "energia_margen": 0.28,
}


def meses_entre(a: date, b: date) -> float:
    return (b - a).days / DIAS_POR_MES


def _ordenadas(promesas, solo_oficiales):
    """Promesas aplicables, ordenadas por fecha declarada; en caso de empate,
    por fecha prometida (orden estable y reproducible a mano)."""
    ps = [p for p in promesas if not solo_oficiales or p["fuente_tipo"] == "oficial"]
    return sorted(ps, key=lambda p: (fin_de_periodo(p["declarada"]), fin_de_periodo(p["fecha_prometida"])))


def deslizamiento(h: dict, hoy: date, solo_oficiales: bool) -> dict | None:
    """Retraso frente a la primera fecha prometida. None si no hay promesas aplicables.

    tipo: realizado (cumplido), minimo (pendiente cuya primera fecha ya paso:
    el retraso final sera al menos este), a_tiempo (pendiente no vencido),
    abandonado. Si el cumplimiento es anterior a la primera fecha prometida,
    meses puede salir negativo (Tesla se adelanto); se deja tal cual, documentado.
    """
    ps = _ordenadas(h.get("promesas") or [], solo_oficiales)
    if not ps:
        return None
    primera = fin_de_periodo(ps[0]["fecha_prometida"])
    vigente = fin_de_periodo(ps[-1]["fecha_prometida"])
    base = {"primera": primera.isoformat(), "vigente": vigente.isoformat(),
            "re_promesas": len(ps) - 1, "vencida_vigente": hoy > vigente,
            "meses_vigente_vs_primera": meses_entre(primera, vigente)}
    estado = h.get("estado", "vigente")
    if estado == "abandonado":
        return {**base, "tipo": "abandonado", "meses": None, "vencida_vigente": False}
    if estado == "cumplido":
        hecho = fin_de_periodo(h["cumplimiento"]["fecha"])
        return {**base, "tipo": "realizado", "meses": meses_entre(primera, hecho),
                "vencida_vigente": False}
    if hoy > primera:
        return {**base, "tipo": "minimo", "meses": meses_entre(primera, hoy)}
    return {**base, "tipo": "a_tiempo", "meses": None}


def _resumen(valores: list[float]) -> dict:
    if not valores:
        return {"n": 0, "media": None, "mediana": None}
    return {"n": len(valores), "media": statistics.fmean(valores),
            "mediana": statistics.median(valores)}


def indice(entradas: list[dict], hoy: date) -> dict:
    """Deslizamiento realizado y minimo acumulado, con todas las fuentes y solo oficiales."""
    salida = {}
    for clave, solo in (("todas", False), ("oficiales", True)):
        ds = [d for d in (deslizamiento(h, hoy, solo) for h in entradas) if d]
        realizados = [d["meses"] for d in ds if d["tipo"] == "realizado"]
        minimos = [d["meses"] for d in ds if d["tipo"] == "minimo"]
        salida[clave] = {
            "realizado": _resumen(realizados),
            "minimo": _resumen(realizados + minimos),
            "cumplidos": len(realizados), "retrasados": len(minimos),
            "a_tiempo": sum(d["tipo"] == "a_tiempo" for d in ds),
            "abandonados": sum(d["tipo"] == "abandonado" for d in ds),
        }
    return salida


def _clave_periodo(periodo) -> int:
    """'AAAAQn' -> entero que crece de uno en uno entre trimestres consecutivos."""
    texto = str(periodo)
    return int(texto[:4]) * 4 + int(texto[-1])


def _serie(df, campo):
    """Pares (period, valor) ordenados por period; [] si falta el campo o los datos."""
    if df is None or campo not in getattr(df, "columns", []):
        return []
    d = df.sort_values("period")
    return list(zip(d["period"], d[campo]))


def _ultimos(pares, n):
    """Los ultimos n valores si son de trimestres consecutivos y ninguno es nulo; si no, None."""
    ult = pares[-n:]
    if len(ult) < n:
        return None
    claves = [_clave_periodo(p) for p, _ in ult]
    if claves != list(range(claves[0], claves[0] + n)):
        return None
    valores = [v for _, v in ult]
    if any(v is None or pd.isna(v) for v in valores):
        return None
    return [float(v) for v in valores]


def _serie_margen_auto(df):
    """(period, margen bruto de automocion sin creditos) por fila."""
    campos = {"revenue_auto_segment", "revenue_reg_credits", "gross_profit_auto_segment"}
    if df is None or not len(df) or not campos.issubset(df.columns):
        return []
    d = df.sort_values("period")
    salida = []
    for _, r in d.iterrows():
        den = r["revenue_auto_segment"] - r["revenue_reg_credits"]
        num = r["gross_profit_auto_segment"] - r["revenue_reg_credits"]
        valor = None if pd.isna(den) or pd.isna(num) or den == 0 else num / den
        salida.append((r["period"], valor))
    return salida


def _serie_margen_operativo(df):
    """(period, margen operativo consolidado) por fila."""
    campos = {"operating_income", "revenue_total"}
    if df is None or not len(df) or not campos.issubset(df.columns):
        return []
    d = df.sort_values("period")
    salida = []
    for _, r in d.iterrows():
        ingresos = r["revenue_total"]
        valor = (None if pd.isna(ingresos) or ingresos == 0 or pd.isna(r["operating_income"])
                 else r["operating_income"] / ingresos)
        salida.append((r["period"], valor))
    return salida


def _serie_margen_energia(df):
    """(period, margen bruto de energia) por fila."""
    campos = {"revenue_energy_segment", "gross_profit_energy_segment"}
    if df is None or not len(df) or not campos.issubset(df.columns):
        return []
    d = df.sort_values("period")
    salida = []
    for _, r in d.iterrows():
        ingresos = r["revenue_energy_segment"]
        valor = (None if pd.isna(ingresos) or ingresos == 0 or pd.isna(r["gross_profit_energy_segment"])
                 else r["gross_profit_energy_segment"] / ingresos)
        salida.append((r["period"], valor))
    return salida


def _serie_diferencia(df, campo_a, campo_b):
    """(period, campo_a - campo_b) por fila; None si falta algun dato de la fila."""
    campos = {campo_a, campo_b}
    if df is None or not len(df) or not campos.issubset(df.columns):
        return []
    d = df.sort_values("period")
    salida = []
    for _, r in d.iterrows():
        valor = None if pd.isna(r[campo_a]) or pd.isna(r[campo_b]) else r[campo_a] - r[campo_b]
        salida.append((r["period"], valor))
    return salida


def _subidas_seguidas(valores) -> int:
    """Cuantas subidas consecutivas terminan en el ultimo valor de la lista."""
    n = 0
    for i in range(len(valores) - 1, 0, -1):
        if valores[i] > valores[i - 1]:
            n += 1
        else:
            break
    return n


def _metrica(id_, nombre, valor, umbral, unidad, cumple):
    return {"id": id_, "nombre": nombre, "valor": valor, "umbral": umbral,
            "unidad": unidad, "cumple": cumple}


def metricas_hito(hito_id: str, financieros, operativos, pasos: list[dict]) -> list[dict]:
    """Metricas automaticas del hito sobre los CSV. cumple es None si falta algun dato
    (incluido un trimestre ausente dentro de la ventana, aunque los demas esten completos)."""
    u = UMBRALES
    if hito_id == "fsd":
        ult1 = _ultimos(_serie(operativos, "fsd_subscriptions"), 1)
        ult5 = _ultimos(_serie(operativos, "fsd_subscriptions"), 5)
        subidas = None if ult5 is None else _subidas_seguidas(ult5)
        mercados = sum(1 for p in pasos if p.get("tipo") == "mercado" and p.get("cumplido")
                       and fin_de_periodo(p["cumplido"]["fecha"]) > FECHA_BASE_MERCADOS)
        return [
            _metrica("suscripciones", "Suscripciones activas", ult1 and ult1[0],
                     u["fsd_suscripciones"], "suscripciones",
                     None if ult1 is None else ult1[0] >= u["fsd_suscripciones"]),
            _metrica("crecimiento_4t", "Subidas trimestrales seguidas", subidas, 4, "trimestres",
                     None if subidas is None else subidas >= 4),
            _metrica("mercados_nuevos", "Mercados nuevos autorizados", mercados,
                     u["fsd_mercados_nuevos"], "mercados", mercados >= u["fsd_mercados_nuevos"]),
        ]
    if hito_id == "automovil":
        m1 = _ultimos(_serie_margen_auto(financieros), 4)
        m2 = _ultimos(_serie_margen_operativo(financieros), 4)
        entregas = _ultimos(_serie(operativos, "deliveries_total"), 8)
        return [
            _metrica("margen_auto_sin_creditos", "Margen bruto de automoción sin créditos, 4 trimestres",
                     m1 and min(m1), u["auto_margen_sin_creditos"], "ratio",
                     None if m1 is None else min(m1) >= u["auto_margen_sin_creditos"]),
            _metrica("margen_operativo", "Margen operativo, 4 trimestres", m2 and min(m2),
                     u["auto_margen_operativo"], "ratio",
                     None if m2 is None else min(m2) >= u["auto_margen_operativo"]),
            _metrica("entregas_12m", "Entregas de doce meses frente a los doce anteriores",
                     None if entregas is None else sum(entregas[4:]) / sum(entregas[:4]) - 1, 0.0, "ratio",
                     None if entregas is None else sum(entregas[4:]) >= sum(entregas[:4])),
        ]
    if hito_id == "energia":
        gwh = _ultimos(_serie(operativos, "storage_deployed_gwh"), 4)
        m = _ultimos(_serie_margen_energia(financieros), 4)
        return [
            _metrica("almacenamiento_12m", "Almacenamiento desplegado en doce meses",
                     None if gwh is None else sum(gwh), u["energia_gwh_12m"], "GWh",
                     None if gwh is None else sum(gwh) >= u["energia_gwh_12m"]),
            _metrica("margen_energia", "Margen bruto de energía, 4 trimestres", m and min(m),
                     u["energia_margen"], "ratio", None if m is None else min(m) >= u["energia_margen"]),
        ]
    return []


def estado_hito(hito: dict, metricas: list[dict]) -> dict:
    pasos = {p["id"]: p for p in hito.get("pasos") or []}
    requeridos = hito.get("requeridos") or []
    hechos = [pasos[r].get("cumplido") for r in requeridos]
    alguno = any(p.get("cumplido") for p in pasos.values()) or any(m["cumple"] is True for m in metricas)
    completo = bool(requeridos or metricas) and all(hechos) and all(m["cumple"] is True for m in metricas)
    estado = "logrado" if completo else "en curso" if alguno else "no iniciado"
    return {"estado": estado, "estancado": hito.get("estancado")}


def _quarter_num(periodo) -> int:
    return int(str(periodo)[-1])


def transversal_caja(financieros, guia: dict) -> dict:
    """Capex frente a la guia anual y FCF de doce meses (spec 4.5), con las
    cifras derivadas que muestra la pagina.

    capex_anio/trimestres_anio/capex_restante solo se calculan si los trimestres
    presentes del anio son Q1..Qn seguidos y sin NaN; si no, quedan en None,
    completo=False y motivo_incompleto lo explica. Un anio sin ningun trimestre es
    capex_anio=0.0, trimestres_anio=0, completo=True. capex_por_trimestre_restante
    es None si el anio esta cerrado y 0 si la guia ya se alcanzo. fcf_12m es None
    si los 4 ultimos trimestres no son consecutivos o tienen algun NaN.
    """
    anio = guia["anio"]
    resultado = {"anio": anio, "guia": guia["importe"], "texto_guia": guia["texto"],
                 "capex_anio": None, "trimestres_anio": None, "capex_restante": None,
                 "cuota_guia": None, "trimestres_restantes": None,
                 "capex_por_trimestre_restante": None, "completo": False,
                 "motivo_incompleto": None, "fcf_12m": None}
    columnas = set(getattr(financieros, "columns", [])) if financieros is not None else set()
    if not {"period", "capex"}.issubset(columnas):
        resultado["motivo_incompleto"] = "falta la columna capex"
        return resultado

    f = financieros.sort_values("period")
    del_anio = f[f["period"].astype(str).str.startswith(str(anio))].sort_values("period")
    trimestres = [_quarter_num(p) for p in del_anio["period"]]
    capex_vals = list(del_anio["capex"])
    if trimestres != list(range(1, len(trimestres) + 1)):
        resultado["motivo_incompleto"] = "falta algún trimestre del año"
    elif any(pd.isna(v) for v in capex_vals):
        resultado["motivo_incompleto"] = "hay trimestres sin dato"
    else:
        capex_anio = float(sum(capex_vals))
        restante = guia["importe"] - capex_anio
        quedan = 4 - len(trimestres)
        resultado.update(
            capex_anio=capex_anio, trimestres_anio=len(trimestres), capex_restante=restante,
            cuota_guia=capex_anio / guia["importe"] if guia["importe"] else None,
            trimestres_restantes=quedan,
            capex_por_trimestre_restante=max(restante, 0.0) / quedan if quedan > 0 else None,
            completo=True)

    if "ocf" in columnas:
        ult = _ultimos(_serie_diferencia(f, "ocf", "capex"), 4)
        resultado["fcf_12m"] = float(sum(ult)) if ult is not None else None
    return resultado


def _a_texto_iso(valor):
    """Copia de la estructura con las fechas como texto AAAA-MM-DD (el YAML
    devuelve date para las fechas sin comillas y el JSON no las admite)."""
    if isinstance(valor, datetime):
        return valor.date().isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    if isinstance(valor, dict):
        return {k: _a_texto_iso(v) for k, v in valor.items()}
    if isinstance(valor, list):
        return [_a_texto_iso(v) for v in valor]
    return valor


def _fechas_prometidas(promesas) -> list[str]:
    """Fin de periodo de cada promesa, en orden de declaracion (para la linea temporal)."""
    return [fin_de_periodo(p["fecha_prometida"]).isoformat() for p in _ordenadas(promesas or [], False)]


def _promesa_vigente(promesas) -> dict | None:
    """La declarada mas recientemente (a igual fecha, la de fecha prometida mas tardia)."""
    ps = _ordenadas(promesas or [], False)
    return ps[-1] if ps else None


def _fecha_logrado(hito: dict) -> date | None:
    """Fecha en que se completo un hito logrado: la evidencia mas tardia de sus
    pasos requeridos. None si no tiene requeridos (solo metricas)."""
    pasos = {p["id"]: p for p in hito.get("pasos") or []}
    fechas = [fin_de_periodo(pasos[r]["cumplido"]["fecha"]) for r in hito.get("requeridos") or []]
    return max(fechas) if fechas else None


def _barra(d: dict | None, cumplimiento: dict | None, hoy: date) -> dict | None:
    """Tramo de la linea temporal: de la primera fecha prometida al cumplimiento
    (cumplido o adelantado), a hoy (retrasado o en plazo) o a la fecha vigente
    (abandonado). invertida si termina antes de empezar."""
    if d is None:
        return None
    desde = fin_de_periodo(d["primera"])
    if d["tipo"] == "realizado":
        hasta = fin_de_periodo(cumplimiento["fecha"])
        tipo = "adelantado" if hasta < desde else "cumplido"
    elif d["tipo"] == "abandonado":
        hasta, tipo = fin_de_periodo(d["vigente"]), "abandonado"
    else:
        hasta, tipo = hoy, "retrasado" if d["tipo"] == "minimo" else "en_plazo"
    return {"desde": desde, "hasta": hasta, "tipo": tipo, "invertida": hasta < desde}


def _grupo(promesas, paso, texto, estado, cumplimiento, en_indice, hoy) -> tuple[dict, dict | None]:
    """Un grupo de promesas con su calculo y, si cuenta, su entrada para el indice."""
    entrada = {"promesas": promesas, "estado": estado, "cumplimiento": cumplimiento}
    d = deslizamiento(entrada, hoy, False) if en_indice else None
    grupo = {
        "paso": paso, "texto": texto, "en_indice": en_indice, "cumplimiento": cumplimiento,
        "deslizamiento": d if en_indice else deslizamiento({"promesas": promesas}, hoy, False),
        "deslizamiento_oficial": deslizamiento(entrada, hoy, True) if en_indice else None,
        "fechas_prometidas": _fechas_prometidas(promesas),
        "promesa_vigente": _promesa_vigente(promesas),
        "barra": _barra(d, cumplimiento, hoy),
    }
    return grupo, (entrada if en_indice else None)


def _grupos_promesas(h: dict, estado: str, hoy: date) -> list[tuple[dict, dict | None]]:
    """Las promesas del hito agrupadas por el paso al que apuntan (decision del
    usuario). Un grupo con paso se cumple con la evidencia de ese paso. Las
    promesas sin paso son del hito completo: cumplido si el hito esta logrado y
    tiene requeridos (fecha de la evidencia mas tardia); fuera del indice si esta
    logrado solo por metricas; vigente si no esta logrado."""
    promesas = h.get("promesas") or []
    salida = []
    for paso in h.get("pasos") or []:
        ps = [p for p in promesas if p.get("paso") == paso["id"]]
        if not ps:
            continue
        hecho = paso.get("cumplido")
        cumplimiento = {"fecha": fin_de_periodo(hecho["fecha"])} if hecho else None
        salida.append(_grupo(ps, paso["id"], paso["texto"], "cumplido" if hecho else "vigente",
                             cumplimiento, True, hoy))
    sueltas = [p for p in promesas if p.get("paso") is None]
    if sueltas:
        fecha = _fecha_logrado(h) if estado == "logrado" else None
        cumplimiento = {"fecha": fecha} if fecha else None
        en_indice = not (estado == "logrado" and fecha is None)
        salida.append(_grupo(sueltas, None, "el hito completo", "cumplido" if cumplimiento else "vigente",
                             cumplimiento, en_indice, hoy))
    return salida


def construir_hitos(datos: dict, financieros, operativos, hoy: date) -> dict:
    """Todo lo que la pagina necesita de los hitos, ya calculado.

    Cada grupo de promesas de un hito prioritario (ver _grupos_promesas) cuenta
    una vez en el indice, igual que cada entrada del historial.
    """
    hitos = []
    entradas = list(datos["historial"])
    for h in sorted(datos["hitos"], key=lambda x: x["prioridad"]):
        ms = metricas_hito(h["id"], financieros, operativos, h.get("pasos") or [])
        est = estado_hito(h, ms)
        fecha = _fecha_logrado(h) if est["estado"] == "logrado" else None
        grupos = _grupos_promesas(h, est["estado"], hoy)
        entradas.extend(e for _, e in grupos if e is not None)
        hitos.append({**h, **est, "metricas": ms,
                      "cumplimiento": {"fecha": fecha} if fecha else None,
                      "en_indice": any(g["en_indice"] for g, _ in grupos),
                      "grupos_promesas": [g for g, _ in grupos]})
    historial = []
    for h in datos["historial"]:
        d = deslizamiento(h, hoy, False)
        historial.append({**h, "deslizamiento": d,
                          "deslizamiento_oficial": deslizamiento(h, hoy, True),
                          "fechas_prometidas": _fechas_prometidas(h["promesas"]),
                          "promesa_vigente": _promesa_vigente(h["promesas"]),
                          "barra": _barra(d, h.get("cumplimiento"), hoy)})
    cumplidos = sum(h["estado"] == "cumplido" for h in datos["historial"])
    total = len(datos["historial"])
    tr = datos["transversal"]
    guia = tr.get("capex_guia")
    caja = ({**transversal_caja(financieros, guia), "fuente": guia["fuente"], "enlace": guia["enlace"]}
            if guia else None)
    return _a_texto_iso({
        "version": datos["version"], "hoy": hoy, "fecha_base_mercados": FECHA_BASE_MERCADOS,
        "hitos": hitos, "historial": historial,
        "indice": {**indice(entradas, hoy),
                   "pct_cumplidos_historial": {"cumplidos": cumplidos, "total": total,
                                               "valor": cumplidos / total if total else None}},
        "transversal": {"caja": caja, "seguridad": tr.get("seguridad") or []},
    })
