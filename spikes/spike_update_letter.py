"""Spike: estabilidad del parseo del Update Letter entre trimestres distintos.

Version corregida tras una primera inspeccion manual de los dos PDF (ver
docs/hallazgos-fase-0.md, seccion "Update Letter"). Respecto a la plantilla
original de la tarea:

1. Las URL de la tarea (`digitalassets.tesla.com`) resultaron correctas SOLO
   para el trimestre antiguo (Q1 2024). El trimestre reciente (Q2 2026) ya
   no vive ahi: devuelve 404. Esta alojado en un host distinto,
   `assets-ir.tesla.com`, con una ruta distinta. Es decir, el propio host
   del PDF no es estable en el tiempo - ver detalle en el hallazgo.
2. La lista ETIQUETAS original (con nombres adivinados como "Total gross
   margin" o "Energy storage deployments") no coincide con el texto real
   de ninguno de los dos trimestres. Se sustituye por las etiquetas
   literales encontradas tras inspeccionar `extract_text()` de las primeras
   paginas de cada PDF a mano.
3. Los rotulos de seccion (p. ej. "FINANCIAL SUMMARY") se extraen con un
   espacio entre cada letra ("F I N A N C I A L S U M M A R Y") por el
   tracking tipografico del diseno del PDF. Localizar la pagina correcta
   por contenido exige buscar el rotulo ya "espaciado", no el texto normal.
"""
import os
import sys

import pdfplumber
import requests

UA = os.environ.get("SEC_USER_AGENT", "spike")
PDFS = {
    # Trimestre antiguo. Alojado en digitalassets.tesla.com (Cloudinary).
    "2024Q1": "https://digitalassets.tesla.com/tesla-contents/image/upload/IR/TSLA-Q1-2024-Update.pdf",
    # Trimestre reciente. Alojado en assets-ir.tesla.com (MinIO) — host
    # DISTINTO al de arriba. La misma plantilla de URL con digitalassets.
    # tesla.com para este trimestre devuelve 404 (comprobado con curl).
    "2026Q2": "https://assets-ir.tesla.com/tesla-contents/IR/TSLA-Q2-2026-Update.pdf",
}

# Rotulos de seccion tal y como aparecen en extract_text() (letra a letra,
# separadas por un espacio, por el tracking tipografico del diseno).
ROTULO_FINANCIERO = "F I N A N C I A L S U M M A R Y"
ROTULO_OPERATIVO = "O P E R A T I O N A L S U M M A R Y"

# Etiquetas reales encontradas tras inspeccionar el texto de ambos PDF a
# mano (no las etiquetas adivinadas de la plantilla original). Algunas
# cambian de nombre/unidad entre trimestres; se listan ambas variantes.
ETIQUETAS = [
    "Total production",
    "Total deliveries",
    "Model 3/Y deliveries",
    "Other models deliveries",
    "Global vehicle inventory (days of supply)",
    "Storage deployed (MWh)",  # nombre usado en 2024Q1
    "Storage deployed (GWh)",  # nombre usado en 2026Q2 (unidad distinta)
    "Total GAAP gross margin",  # NO "Total gross margin" como se asumia
    "Operating margin",
    "Free cash flow",
]
# Etiquetas que la tarea pedia buscar explicitamente y que NO se
# encontraron literalmente en ninguno de los dos trimestres (se buscan
# aparte para dejar constancia del resultado negativo).
ETIQUETAS_NO_ENCONTRADAS = ["Solar deployments", "Energy storage deployments"]

for periodo, url in PDFS.items():
    destino = f"cache/update_{periodo}.pdf"
    if not os.path.exists(destino):
        resp = requests.get(url, headers={"User-Agent": UA}, timeout=120)
        resp.raise_for_status()
        with open(destino, "wb") as fh:
            fh.write(resp.content)

    print(f"\n===== {periodo} =====")
    with pdfplumber.open(destino) as pdf:
        print("Paginas:", len(pdf.pages))

        # 1) Localizar por CONTENIDO (no por numero fijo de pagina) las
        #    paginas de Financial Summary y Operational Summary.
        pagina_financiera = None
        pagina_operativa = None
        for num, pagina in enumerate(pdf.pages):
            texto = pagina.extract_text() or ""
            if pagina_financiera is None and ROTULO_FINANCIERO in texto:
                pagina_financiera = num
            if pagina_operativa is None and ROTULO_OPERATIVO in texto:
                pagina_operativa = num
            if pagina_financiera is not None and pagina_operativa is not None:
                break

        print(
            f"Pagina Financial Summary: {pagina_financiera} | "
            f"Pagina Operational Summary: {pagina_operativa}"
        )

        # 2) Sobre esas dos paginas (mas la primera, por si acaso), buscar
        #    las ETIQUETAS conocidas en texto plano y volcar la tabla si
        #    extract_tables() detecta alguna.
        paginas_a_mirar = sorted(
            {p for p in (0, pagina_financiera, pagina_operativa) if p is not None}
        )
        for num in paginas_a_mirar:
            pagina = pdf.pages[num]
            texto = pagina.extract_text() or ""
            encontradas = [e for e in ETIQUETAS if e in texto]
            if encontradas:
                print(f"  p{num}: etiquetas encontradas en texto: {encontradas}")
            for tabla in pagina.extract_tables():
                if any(
                    any(e in (c or "") for e in ETIQUETAS)
                    for fila in tabla
                    for c in fila
                ):
                    print(f"  --- tabla en p{num} ({len(tabla)} filas) ---")
                    for fila in tabla[:20]:
                        print("   ", fila)

        # 3) Comprobacion explicita de las etiquetas que la tarea pedia y
        #    que se sospecha NO existen como metrica numerica en el texto.
        texto_completo = "\n".join((p.extract_text() or "") for p in pdf.pages)
        for etiqueta in ETIQUETAS_NO_ENCONTRADAS:
            presente = etiqueta in texto_completo
            print(f"  Etiqueta '{etiqueta}' presente literalmente: {presente}")
        # Busqueda mas laxa de un dato de solar en MW en todo el documento.
        lineas_solar_mw = [
            linea
            for linea in texto_completo.split("\n")
            if ("olar" in linea) and ("MW" in linea)
        ]
        print(f"  Lineas con 'olar' + 'MW' en todo el documento: {lineas_solar_mw}")
