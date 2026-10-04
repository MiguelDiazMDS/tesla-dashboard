"""Spike: localizar la tabla de segmentos dentro de un filing 10-Q.

Version corregida tras la ejecucion inicial. El contenido original del
spike (tal y como se definio en la tarea) fallaba por dos motivos que se
documentan tambien en docs/hallazgos-fase-0.md:

1. Los R*.htm que sirve EDGAR en este entorno llegan envueltos en un
   preambulo SGML (`<DOCUMENT><TYPE>XML...<TEXT><html>...</html>`), no
   como HTML "pelado". `pandas.read_html` con el parser lxml por defecto
   revienta al intentar parsear ese preambulo como XML/HTML. Hay que
   recortar el fragmento entre `<html` y `</html>` antes de pasarselo a
   pandas.
2. El criterio de busqueda original (`"Energy generation and storage" in
   html and "Services and other" in html`) NO localiza la tabla de
   segmentos real: encuentra primero R24.htm, que es la nota de
   "Summary of Significant Accounting Policies" con el desglose de
   ingresos POR FUENTE/PRODUCTO (Automotive sales, Energy generation and
   storage sales, Services and other, ...), no el desglose por SEGMENTO
   REPORTABLE. La tabla de segmentos real (Automotive segment / Energy
   generation and storage segment) nunca menciona "Services and other"
   porque Tesla solo tiene DOS segmentos reportables bajo ASC 280; los
   ingresos de "Services and other" quedan dentro del segmento
   Automotive. Por eso el criterio se cambia a buscar el rotulo
   "Segment Reporting" junto con los nombres de ambos segmentos.
"""
import os
import re
import sys
from io import StringIO

import pandas as pd
import requests

UA = os.environ.get("SEC_USER_AGENT")
if not UA:
    sys.exit("Define SEC_USER_AGENT antes de ejecutar")
H = {"User-Agent": UA}


def html_puro(raw: str) -> str:
    """Recorta el envoltorio SGML <DOCUMENT>...<TEXT> que antecede al <html> real."""
    inicio = raw.find("<html")
    fin = raw.rfind("</html>")
    if inicio == -1 or fin == -1:
        return raw
    return raw[inicio : fin + len("</html>")]


subs = requests.get(
    "https://data.sec.gov/submissions/CIK0001318605.json", headers=H, timeout=60
).json()
recientes = subs["filings"]["recent"]
filings = [
    (recientes["accessionNumber"][i], recientes["form"][i], recientes["reportDate"][i])
    for i in range(len(recientes["form"]))
    if recientes["form"][i] in ("10-Q", "10-K")
]
print("Ultimos filings:", filings[:6])

accession, form, fecha = filings[0]
acc = accession.replace("-", "")
base = f"https://www.sec.gov/Archives/edgar/data/1318605/{acc}"

idx = requests.get(f"{base}/index.json", headers=H, timeout=60).json()
nombres = [f["name"] for f in idx["directory"]["item"]]
print("Ficheros en el filing:", [n for n in nombres if n.endswith((".xlsx", ".htm"))][:25])

# Los estados renderizados R*.htm contienen las tablas del filing, segmentos incluidos
erres = sorted(
    (n for n in nombres if n.startswith("R") and n.endswith(".htm")),
    key=lambda n: int(re.sub(r"\D", "", n)),
)
print(f"Encontrados {len(erres)} estados renderizados")

encontrado = False
for nombre in erres:
    html_crudo = requests.get(f"{base}/{nombre}", headers=H, timeout=60).text
    # Criterio corregido: el rotulo de la nota + los dos nombres de segmento.
    # (El criterio original "Energy generation and storage" + "Services and
    # other" solo encuentra la nota de ingresos por producto, no la de
    # segmentos — ver docstring del modulo.)
    if (
        "Segment Reporting" in html_crudo
        and "Automotive segment" in html_crudo
        and "Energy generation and storage segment" in html_crudo
    ):
        print(f"\n>>> SEGMENTOS EN {nombre}")
        html = html_puro(html_crudo)
        tablas = pd.read_html(StringIO(html))
        for t in tablas:
            print(t.head(20).to_string())
        encontrado = True
        break

if not encontrado:
    print("\nNo se ha localizado la tabla de segmentos en los estados renderizados")
