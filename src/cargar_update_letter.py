"""Anade al fichero operativo las metricas del Update Letter.

Cada carta trimestral cubre cinco trimestres, asi que un mismo trimestre
aparece en varias cartas, y no siempre con la misma precision: la de 2024Q1 da
3.653 MWh donde la de 2024Q2 da 3,7 GWh. Se conserva el valor con mas cifras
significativas. Solo cuando la diferencia no se explica por redondeo se toma
el de la carta mas reciente, que puede traer una reexpresion, y se avisa.

La columna source_update_letter cita la carta mas reciente que cubre el
trimestre; el valor es el mas preciso de las que coinciden.

Las cartas cuyo exhibit trae las paginas como imagenes no son legibles desde
EDGAR; los trimestres que solo cubren ellas se leen del PDF de Tesla.
"""
import math
from datetime import date

import pandas as pd

from src.fetch_deliveries import localizar_exhibit
from src.fetch_update_letter import CuadroNoEncontrado, parsear_cuadro, texto_plano
from src.filings import BASE_ARCHIVO, indice_filings
from src.http_client import ClienteHTTP, ErrorDescarga

# El 8-K de resultados llega unas tres semanas despues del cierre, pasada la
# ventana de la nota de entregas.
MES_A_TRIMESTRE = {1: (4, 1), 4: (1, 0), 7: (2, 0), 10: (3, 0)}
DIA_MINIMO = 13
CAMPOS = ("days_inventory", "storage_deployed_gwh", "fsd_subscriptions")

# Cartas cuyo exhibit en EDGAR son imagenes y cuyo PDF sigue publicado. Cada
# una cubre cinco trimestres: la de 2022Q1 rellena 2021Q1-2022Q1 y la de 2020Q4
# rellena 2020Q4. Las de 2019 y 2020Q1 ya no estan en el servidor de Tesla.
PLANTILLA_PDF = (
    "https://digitalassets.tesla.com/tesla-contents/image/upload/IR/"
    "TSLA-Q{trimestre}-{anio}-Update.pdf"
)
CARTAS_PDF = ("2020Q4", "2022Q1")


def periodo_de_carta(fecha_filing: str) -> str | None:
    """Trimestre al que se refiere un 8-K de resultados presentado en esa fecha."""
    f = date.fromisoformat(fecha_filing)
    if f.day < DIA_MINIMO or f.month not in MES_A_TRIMESTRE:
        return None
    trimestre, atras = MES_A_TRIMESTRE[f.month]
    return f"{f.year - atras}Q{trimestre}"


def listar_cartas(cliente: ClienteHTTP) -> dict[str, list[str]]:
    """{periodo de la carta: accessions candidatos}."""
    indice = indice_filings(cliente)
    cartas: dict[str, list[str]] = {}
    for i, formulario in enumerate(indice["form"]):
        if formulario != "8-K":
            continue
        periodo = periodo_de_carta(indice["filingDate"][i])
        if periodo:
            cartas.setdefault(periodo, []).append(indice["accessionNumber"][i])
    return cartas


def leer_carta(cliente: ClienteHTTP, candidatos: list[str]) -> tuple[str, str] | None:
    """(accession, html) de la carta entre los candidatos, o None."""
    for accession in candidatos:
        base = f"{BASE_ARCHIVO}/{accession.replace('-', '')}"
        try:
            completo = cliente.obtener(f"{base}/{accession}.txt").decode(
                "utf-8", errors="replace")
        except ErrorDescarga:
            raise         # agotar los reintentos es "no se sabe", no "siguiente candidato"
        except Exception:
            continue
        fichero = localizar_exhibit(completo)
        if not fichero:
            continue
        html = cliente.obtener(f"{base}/{fichero}").decode("utf-8", errors="replace")
        # El 8-K de resultados lleva la carta; otros 8-K de la misma ventana no.
        if "Update" in texto_plano(html)[:600]:
            return accession, html
    return None


def leer_pdf(cliente: ClienteHTTP, periodo_carta: str) -> str | None:
    """Texto de las primeras paginas del PDF de una carta, o None."""
    import io

    import pdfplumber

    url = PLANTILLA_PDF.format(trimestre=periodo_carta[5], anio=periodo_carta[:4])
    try:
        contenido = cliente.obtener(url)
    except ErrorDescarga:
        raise
    except Exception as exc:
        print(f"  PDF {periodo_carta} no disponible: {exc}")
        return None
    with pdfplumber.open(io.BytesIO(contenido)) as pdf:
        return "\n".join((p.extract_text() or "") for p in pdf.pages[:8])


def cifras_significativas(x: float) -> int:
    """Cuantas cifras significativas tiene un valor: 3.653 -> 4, 800000 -> 1."""
    if x == 0:
        return 1
    digitos = f"{abs(x):.12g}".replace(".", "").lstrip("0").rstrip("0")
    return max(len(digitos), 1)


def ultima_cifra(x: float) -> float:
    """Valor posicional de la ultima cifra significativa: 3.7 -> 0.1."""
    if x == 0:
        return 0.0
    orden = math.floor(math.log10(abs(x)))
    return 10.0 ** (orden - cifras_significativas(x) + 1)


def es_redondeo(a: float, b: float) -> bool:
    """True si la diferencia se explica por redondear el mas preciso.

    Las cartas publican el mismo trimestre con distinta precision: la de 2024Q2
    da 3,7 GWh donde la de 2024Q1 daba 3.653 MWh. Es el mismo dato.
    """
    menos_preciso = a if cifras_significativas(a) <= cifras_significativas(b) else b
    return abs(a - b) <= 0.5 * ultima_cifra(menos_preciso) * (1 + 1e-9)


def elegir(anterior: float, nuevo: float) -> float:
    """Entre dos valores del mismo trimestre, el de mas cifras significativas.

    A igual precision prevalece el nuevo, que viene de una carta posterior y
    puede incorporar una reexpresion.
    """
    if cifras_significativas(anterior) > cifras_significativas(nuevo):
        return anterior
    return nuevo


def fusionar(mejor, periodo_carta, origen, cuadro, discrepancias) -> None:
    """Incorpora una carta al acumulado, campo a campo.

    Se conserva el valor mas preciso, y solo se anota como discrepancia lo que
    no se explica por redondeo: eso si podria ser una reexpresion.
    """
    for periodo, valores in cuadro.items():
        previo = mejor.get(periodo)
        if not previo:
            mejor[periodo] = (periodo_carta, origen, dict(valores))
            continue
        combinados = dict(previo[2])
        for campo, valor in valores.items():
            anterior = combinados.get(campo)
            if anterior is None:
                combinados[campo] = valor
                continue
            if not es_redondeo(anterior, valor):
                discrepancias.append(
                    f"{periodo} {campo}: {anterior:g} ({previo[0]}) "
                    f"frente a {valor:g} ({periodo_carta})")
                combinados[campo] = valor     # posible reexpresion: la reciente
            else:
                combinados[campo] = elegir(anterior, valor)
        mejor[periodo] = (max(previo[0], periodo_carta), origen, combinados)


def _nulo(x) -> bool:
    return x is None or (isinstance(x, float) and math.isnan(x))


def combinar_almacenamiento(de_carta, de_nota) -> tuple[float | None, str | None]:
    """Almacenamiento del trimestre y, si las dos fuentes discrepan, un aviso.

    La nota de entregas lo publica tres semanas antes que el Update Letter:
    hasta que llega la carta vale el dato de la nota. Con carta manda la
    carta, que da mas precision; si la diferencia no se explica por redondeo
    se avisa, porque una de las dos fuentes esta mal leida.
    """
    if _nulo(de_carta):
        return (None if _nulo(de_nota) else float(de_nota)), None
    if _nulo(de_nota) or es_redondeo(float(de_carta), float(de_nota)):
        return float(de_carta), None
    return float(de_carta), (f"la carta da {float(de_carta):g} GWh y la nota de entregas "
                             f"{float(de_nota):g} GWh: se usa la carta")


def main() -> None:
    cliente = ClienteHTTP()
    cartas = listar_cartas(cliente)

    # Reunir todas las cartas legibles, de EDGAR y de PDF, antes de fusionar.
    leidas: list[tuple[str, str, dict]] = []
    ilegibles = []
    for periodo_carta in sorted(cartas):
        leida = leer_carta(cliente, cartas[periodo_carta])
        if leida is None:
            continue
        accession, html = leida
        try:
            leidas.append((periodo_carta, f"8-K {accession}", parsear_cuadro(html)))
        except CuadroNoEncontrado:
            ilegibles.append(periodo_carta)
    for periodo_carta in CARTAS_PDF:
        texto = leer_pdf(cliente, periodo_carta)
        if texto:
            try:
                leidas.append((periodo_carta, "PDF de Tesla", parsear_cuadro(texto)))
            except CuadroNoEncontrado as exc:
                print(f"  PDF {periodo_carta}: {exc}")

    # periodo -> (periodo de la carta, origen, {campo: valor})
    mejor: dict[str, tuple[str, str, dict[str, float]]] = {}
    discrepancias: list[str] = []
    for periodo_carta, origen, cuadro in sorted(leidas, key=lambda x: x[0]):
        fusionar(mejor, periodo_carta, origen, cuadro, discrepancias)

    print(f"Cartas leidas: {len(leidas)} "
          f"({sum(1 for x in leidas if x[1].startswith('PDF'))} en PDF)")
    print(f"Cartas con las paginas como imagen en EDGAR: {', '.join(ilegibles) or 'ninguna'}")
    if discrepancias:
        print(f"\nDiscrepancias entre cartas en trimestres solapados ({len(discrepancias)}):")
        for d in discrepancias[:15]:
            print(f"  {d}")
    else:
        print("Las cartas coinciden en todos los trimestres que se solapan")

    df = pd.read_csv("data/operating_quarterly.csv")
    # cargar_deliveries deja en esta columna lo que cita la nota de entregas.
    de_nota = (dict(zip(df["period"], df["storage_deployed_gwh"]))
               if "storage_deployed_gwh" in df.columns else {})
    for campo in CAMPOS:
        df[campo] = df["period"].map(
            lambda p: mejor[p][2].get(campo) if p in mejor else None)
    avisos_almacenamiento, combinados, solo_nota = [], [], []
    for periodo, de_carta in zip(df["period"], df["storage_deployed_gwh"]):
        valor, aviso = combinar_almacenamiento(de_carta, de_nota.get(periodo))
        combinados.append(valor)
        if aviso:
            avisos_almacenamiento.append(f"{periodo}: {aviso}")
        if _nulo(de_carta) and valor is not None:
            solo_nota.append(periodo)
    df["storage_deployed_gwh"] = combinados
    df["source_update_letter"] = df["period"].map(
        lambda p: f"Update Letter {mejor[p][0]} ({mejor[p][1]})" if p in mejor else None)
    df.to_csv("data/operating_quarterly.csv", index=False)

    if solo_nota:
        print("\nAlmacenamiento tomado de la nota de entregas (aun sin carta): "
              + ", ".join(solo_nota))
    if avisos_almacenamiento:
        print("\nAlmacenamiento, carta frente a nota de entregas:")
        for aviso in avisos_almacenamiento:
            print(f"  {aviso}")

    print(f"\nCobertura ({len(df)} trimestres):")
    for campo in CAMPOS:
        faltan = df.loc[df[campo].isna(), "period"].tolist()
        print(f"  {campo}: {df[campo].notna().sum()}/{len(df)}"
              + (f"  faltan {faltan}" if faltan and len(faltan) < 12 else ""))


if __name__ == "__main__":
    main()
