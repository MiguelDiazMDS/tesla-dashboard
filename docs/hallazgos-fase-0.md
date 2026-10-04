# Hallazgos — Fase 0 (exploración)

## EDGAR companyfacts

**Fuente:** `https://data.sec.gov/api/xbrl/companyfacts/CIK0001318605.json` (Tesla, Inc., CIK 0001318605).
Script: `spikes/spike_edgar_companyfacts.py`. Ejecutado el 2026-09-22 con `SEC_USER_AGENT` configurado en `.env`.

### Taxonomías presentes

El JSON trae tres taxonomías: `dei`, `us-gaap`, `ffd`. El análisis se centró en `us-gaap`, que contiene **643 conceptos**.

### Conceptos candidatos: disponibilidad

De los 17 conceptos candidatos para `financials_quarterly`, **los 17 están presentes** (ninguno falta). Detalle (forms 10-Q y 10-K combinados, salvo indicación contraria):

| Concepto | Unidad | n | Desde | Hasta |
|---|---|---|---|---|
| `Revenues` | USD | 271 | 2009-12-31 | 2026-06-30 |
| `RevenueFromContractWithCustomerExcludingAssessedTax` | USD | 45 | 2018-03-31 | 2026-06-30 |
| `CostOfRevenue` | USD | 199 | 2009-12-31 | 2026-06-30 |
| `GrossProfit` | USD | 271 | 2009-12-31 | 2026-06-30 |
| `ResearchAndDevelopmentExpense` | USD | 199 | 2009-12-31 | 2026-06-30 |
| `SellingGeneralAndAdministrativeExpense` | USD | 199 | 2009-12-31 | 2026-06-30 |
| `OperatingIncomeLoss` | USD | 199 | 2009-12-31 | 2026-06-30 |
| `NetIncomeLoss` | USD | 274 | 2009-12-31 | 2026-06-30 |
| `EarningsPerShareDiluted` | USD/shares | 128 | 2012-03-31 | 2026-06-30 |
| `NetCashProvidedByUsedInOperatingActivities` | USD | 101 | 2009-12-31 | 2026-06-30 |
| `PaymentsToAcquirePropertyPlantAndEquipment` | USD | 137 | 2009-12-31 | 2026-06-30 |
| `CashAndCashEquivalentsAtCarryingValue` | USD | 238 | 2008-12-31 | 2026-06-30 |
| `WeightedAverageNumberOfDilutedSharesOutstanding` | shares | 125 | 2012-03-31 | 2026-06-30 |
| `ShareBasedCompensation` | USD | 137 | 2009-12-31 | 2026-06-30 |
| `ContractWithCustomerLiabilityCurrent` | USD | 66 | 2017-12-31 | 2026-06-30 |
| `ContractWithCustomerLiabilityNoncurrent` | USD | 66 | 2017-12-31 | 2026-06-30 |
| `DeferredRevenueCurrent` | USD | 56 | 2010-12-31 | 2018-03-31 |
| `DeferredRevenueNoncurrent` | USD | 56 | 2010-12-31 | 2018-03-31 |

**Nota sobre `DeferredRevenueCurrent`/`DeferredRevenueNoncurrent`:** dejan de aportar datos después de 2018-03-31. Coincide con el momento en que Tesla adoptó ASC 606 y pasó a reportar bajo los conceptos `ContractWithCustomerLiability*`, que arrancan justo en 2017-12-31. El extractor de fase 1 deberá tratar estos dos pares de conceptos como series empalmadas (una sustituye a la otra), no como series independientes que conviven todo el histórico.

**Ninguno falta** — no hay conceptos de la lista `BUSCAR` ausentes en `us-gaap`.

### Pregunta central: ¿hay dimensiones de segmento en companyfacts?

**NO.** El script recorrió todos los valores de los 643 conceptos `us-gaap` buscando claves adicionales a las estándar (`start`, `end`, `val`, `accn`, `fy`, `fp`, `form`, `filed`, `frame`). El resultado fue:

```
Conceptos con claves extra (posibles dimensiones): NINGUNO
```

Esto confirma la expectativa: **`companyfacts` entrega únicamente hechos consolidados a nivel de compañía, sin ningún desglose dimensional** (ni por segmento de negocio, ni por geografía, ni por ninguna otra dimensión XBRL). El endpoint `companyfacts` aplana los datos y descarta la información de miembros/ejes (`Member`/`Axis`) que sí existe en los propios ficheros XBRL de cada filing (`R.htm`/`Financial Report.xlsx` o el `xbrl frames`/`companyconcept` con contexto completo no aplica tampoco, porque son la misma fuente subyacente). Si en fase 1 se necesita el desglose Automoción/Energía/Servicios, **no se puede obtener de `companyfacts`**; haría falta parsear directamente el XBRL instance document de cada 10-Q/10-K (o las tablas del propio filing en HTML/XLSX) buscando los `Member` del eje de segmentos (típicamente `ProductOrServiceAxis` o un eje de segmento operativo propio de Tesla), lo cual queda fuera del alcance de esta tarea exploratoria.

> [!question] Laguna
> No se ha explorado en esta tarea si el desglose por segmento (Automoción/Energía/Servicios) está disponible en otro endpoint de EDGAR (p. ej. `frames` con contexto, o extrayendo el `R*.htm`/instance XBRL del filing) ni en las presentaciones trimestrales (shareholder deck) que Tesla publica aparte del 10-Q. Queda pendiente para una futura tarea de fase 0 si el diseño de fase 1 requiere el desglose por segmento.

### Qué concepto de ingresos usa Tesla, y cuándo

Se inspeccionaron los registros individuales (no solo el conteo agregado) de `Revenues` y `RevenueFromContractWithCustomerExcludingAssessedTax` en `cache/companyfacts.json`:

- **`Revenues`**: presente de forma continua desde el ejercicio fiscal **2009** (10-K, periodo 2009-12-31) hasta el trimestre más reciente disponible, **2026-Q2** (periodo 2026-04-01/2026-06-30, `accn` 0001628280-26-049270). Es el único concepto de ingresos disponible entre 2009 y 2017.
- **`RevenueFromContractWithCustomerExcludingAssessedTax`**: aparece por primera vez en **2018-Q1** (periodo 2018-01-01/2018-03-31, `accn` 0001564590-18-011086) y continúa hasta **2026-Q2** (mismo `accn` 0001628280-26-049270 que `Revenues` en ese periodo).
- **A partir de 2018-Q1, Tesla reporta ambos conceptos simultáneamente en el mismo filing (mismo `accn`) y con el mismo valor** (comprobado en el primer y el último registro de cada serie: p. ej. 2026-Q1 = 22.387.000.000 USD y 2026-Q2 = 28.236.000.000 USD en ambos conceptos). Es decir, Tesla "dual-tagea" sus ingresos con el concepto legacy (`Revenues`) y el concepto ASC 606 (`RevenueFromContractWithCustomerExcludingAssessedTax`) desde que adoptó el nuevo estándar contable, probablemente por retro-compatibilidad con herramientas que aún buscan el tag antiguo.

**Conclusión para el extractor de fase 1:**
- Periodos **2009 a 2017**: usar únicamente `Revenues` (es el único disponible).
- Periodos **2018 en adelante**: ambos conceptos están presentes con el mismo valor; el extractor puede usar cualquiera de los dos, pero por semántica contable (ASC 606) se recomienda **priorizar `RevenueFromContractWithCustomerExcludingAssessedTax` cuando exista, y hacer fallback a `Revenues` si falta** para ese periodo. Esto cubre todo el histórico 2009-2026 sin huecos.

## Estado de la caché

El JSON completo de companyfacts quedó guardado en `cache/companyfacts.json` (no versionado, excluido por `.gitignore`) para reutilizarlo en análisis posteriores sin volver a golpear la API de la SEC.

## Segmentos

**Fuente:** estados renderizados (`R*.htm`) del filing 10-Q más reciente de Tesla, CIK 0001318605.
Script: `spikes/spike_edgar_segments.py`. Filing usado: accession `0001628280-26-049270` (10-Q, periodo `2026-06-30`), localizado a través de `https://data.sec.gov/submissions/CIK0001318605.json`. Ejecutado el 2026-09-22 con `SEC_USER_AGENT` configurado en `.env`.

### Conclusión: A — los estados renderizados (`R*.htm`) sirven

Se confirma que la tabla de segmentos **sí existe** en el filing y es alcanzable vía `R*.htm`, pero llegar hasta ella exigió corregir dos problemas que no estaban previstos en el script inicial (ver más abajo). Con la versión corregida de `spikes/spike_edgar_segments.py`, la tabla se localizó en **`R22.htm`** (nota "Segment Reporting and Information about Geographic Areas"). La misma información también aparece, en formato de tabla "Details" más estructurado y fácil de parsear con `pandas.read_html`, en **`R63.htm`** ("...Schedule of Total Revenues and Gross Profit by Reportable Segment (Details)").

> [!warning] El número de fichero varía entre filings
> `R22`/`R63` son los números para ESTE filing concreto. La numeración de los estados renderizados depende del orden en que el generador de XBRL de Tesla/su agente de filing coloca las notas y tablas en cada 10-Q/10-K, y cambia de un trimestre a otro. **No se puede asumir una posición fija** (p. ej. "siempre es R22"); hay que localizar el fichero correcto buscando por contenido (rótulo "Segment Reporting" + nombres de los segmentos) en cada ejecución, igual que hace el script.

### Dos problemas encontrados y corregidos respecto al script original de la tarea

1. **Envoltorio SGML que rompe `pandas.read_html`.** Los `R*.htm` que sirve EDGAR en este entorno no llegan como HTML "pelado": vienen envueltos en un preámbulo de tipo SGML (`<DOCUMENT><TYPE>XML<SEQUENCE>...<FILENAME>R22.htm<DESCRIPTION>IDEA: XBRL DOCUMENT<TEXT><html>...</html>`). Esto se comprobó en los 66 `R*.htm` del filing (`R1.htm`, `R9.htm`, `R22.htm`, `R24.htm`, `R63.htm`, todos con el mismo prefijo `<DOCUMENT><TYPE>XML...`). El parser `lxml` que usa `pandas.read_html` por defecto revienta con `OSError: Error reading file` al recibir ese preámbulo antes de la etiqueta `<html>`. **Solución aplicada:** recortar el fragmento real entre `<html` y `</html>` antes de pasarlo a `pd.read_html` (función `html_puro()` en el script corregido).
2. **El criterio de búsqueda original apuntaba a la tabla equivocada.** El script tal y como se definió en la tarea busca `"Energy generation and storage" in html and "Services and other" in html`. Ese criterio **encuentra primero `R24.htm`**, que es la nota "Summary of Significant Accounting Policies" con el desglose de ingresos **por fuente/producto** (Automotive sales, Automotive regulatory credits, Energy generation and storage sales, Services and other, Automotive leasing, Energy generation and storage leasing) — una tabla real y útil, pero **no es la tabla de segmentos reportables**. La tabla de segmentos real (`R22`/`R63`) **nunca contiene la cadena "Services and other"**, porque, como se explica abajo, Tesla solo declara dos segmentos reportables y los ingresos de "Services and other" quedan dentro del segmento Automotive. Con el criterio original, el bucle se detiene en `R24.htm` creyendo (incorrectamente) que esa es la tabla de segmentos, y además revienta ahí mismo por el problema (1). **Criterio corregido:** buscar el rótulo `"Segment Reporting"` junto con los nombres literales `"Automotive segment"` y `"Energy generation and storage segment"`.

> [!warning] Contradicción con la premisa de la tarea (Automoción / Energía / Servicios)
> La tarea da por hecho un desglose en tres segmentos: Automoción, Energía y Servicios. **Esto no coincide con lo que Tesla reporta bajo ASC 280.** El propio texto de la nota lo dice explícitamente: *"We have two operating and reportable segments: (i) automotive and (ii) energy generation and storage."* No existe un tercer segmento reportable de "Services". Los ingresos de "Services and other" (línea de producto, visible en `R24.htm`) están **incluidos dentro de los ingresos del segmento Automotive** — se comprobó por diferencia: ingresos del segmento Automotive en el Q2-2026 = 25.097 M USD; sumando las líneas de producto "Automotive sales" (20.006) + "Automotive regulatory credits" (146) + "Automotive leasing" (364) = 20.516 M USD, la diferencia (4.581 M USD) coincide exactamente con la línea "Services and other" (4.581 M USD) de `R24.htm`. Si la valoración SOTP necesita de verdad un margen de "Servicios" separado del de Automoción, **ese dato no existe como tal en el filing**: solo se dispone del ingreso de "Services and other" (sin coste ni margen propio, ver más abajo) mezclado dentro del margen bruto consolidado del segmento Automotive.

### Líneas exactas de la tabla de segmentos (texto literal de `R22.htm`)

> "We have two operating and reportable segments: (i) automotive and (ii) energy generation and storage. The following table presents revenues, cost of revenues and gross profit by reportable segment (in millions):"

| Segmento | Métrica | 3M jun-2026 | 3M jun-2025 | 6M jun-2026 | 6M jun-2025 |
|---|---|---:|---:|---:|---:|
| Automotive segment | Revenues | 25.097 | 19.707 | 45.076 | 36.312 |
| Automotive segment | Cost of revenues (1) | 20.986 | 16.675 | 37.197 | 30.912 |
| Automotive segment | Gross profit | 4.111 | 3.032 | 7.879 | 5.400 |
| Energy generation and storage segment | Revenues | 3.139 | 2.789 | 5.547 | 5.519 |
| Energy generation and storage segment | Cost of revenues (2) | 2.499 | 1.943 | 3.955 | 3.888 |
| Energy generation and storage segment | Gross profit | 640 | 846 | 1.592 | 1.631 |

(1)/(2) notas al pie: depreciación y amortización incluida en cada coste de ventas por segmento (no aportan una línea adicional de margen).

La misma nota trae, a continuación, dos tablas adicionales por segmento/geografía que también podrían ser útiles para el dashboard: ingresos por área geográfica (US / China / Other international) e inventario por segmento reportable (Automotive / Energy generation and storage).

### Periodos que cubre la tabla

Un 10-Q trae, como se esperaba, **trimestre (3 meses) y acumulado del año (6 meses)**, cada uno con su comparativo interanual: columnas "Three Months Ended June 30, 2026 / 2025" y "Six Months Ended June 30, 2026 / 2025". Para una serie histórica completa habría que repetir la extracción filing a filing (cada 10-Q trae su trimestre + acumulado; un 10-K trae el ejercicio completo), tal y como ya se anticipaba en el hallazgo de `companyfacts`.

### Limitación relevante para el margen por segmento

La nota de segmentos **solo desglosa Revenues, Cost of revenues y Gross profit** (más D&A informativo) por segmento. **No hay operating income (EBIT) por segmento**: los gastos de SG&A y I+D no se asignan a nivel de segmento en el 10-Q, solo a nivel consolidado. Por tanto, con esta fuente se puede construir **margen bruto por segmento (Automotive vs. Energy)**, pero no un margen operativo por segmento sin asumir una clave de reparto propia para SG&A/I+D — y, como se explicó arriba, tampoco hay un tercer segmento de "Servicios" que aislar.

### Valoración de fragilidad de esta vía

- **Recuperación del fichero correcto:** requiere descargar y examinar los `R*.htm` uno a uno (hasta 66 en este filing) buscando por contenido, no por posición — es lento (varias decenas de peticiones secuenciales, con `time.sleep(0.2)` entre ellas para respetar la tasa de la SEC) pero fiable si el criterio de búsqueda es el correcto. **El criterio de búsqueda es el punto frágil real**: si el rótulo de la nota cambiara de redacción (p. ej. Tesla renombrara "Segment Reporting" o los nombres de los `Member` del eje `StatementBusinessSegmentsAxis`), el script dejaría de encontrar la tabla silenciosamente (caería al mensaje "no localizado") en vez de fallar de forma ruidosa. Conviene, para fase 1, anclar la búsqueda también a los nombres de los ejes/miembros XBRL vistos en el pie de página de `R63.htm` (`us-gaap_StatementBusinessSegmentsAxis=tsla_AutomotiveSegmentMember` y `...tsla_EnergyGenerationAndStorageSegmentMember`), que son más estables que el texto libre de la nota.
- **Envoltorio SGML:** es un detalle de bajo nivel pero rompe cualquier `pd.read_html` ingenuo sobre estos ficheros en este entorno; ya está resuelto con `html_puro()`, pero cualquier reimplementación futura (p. ej. en `src/`) debe incorporar ese recorte o cambiar de parser.
- **Estabilidad de la estructura de la tabla:** dentro de `R22.htm` el HTML de la tabla es una sopa de `<td>` con muchos `colspan`/`NaN` (ver salida cruda de `pd.read_html` sobre esa tabla); es más robusto parsear `R63.htm` (la vista "Details" generada por el visor de XBRL), que produce una tabla limpia de 16×5 con una fila por métrica y segmento — ver primera tabla del volcado de `R63.htm` en el log de ejecución.
- **En conjunto**, se considera una vía **automatizable pero de complejidad media-alta**: no es tan directa como `companyfacts` (hay que iterar y localizar por contenido, tratar el envoltorio SGML, y decidir entre la vista narrativa `R22` o la vista "Details" `R63`), y frágil ante cambios de redacción de la SEC/Tesla en las notas. Para fase 1 se recomienda extraer preferentemente de la tabla "Details" (`R63`-equivalente en cada filing) por su estructura tabular más limpia, con fallback a parsear el texto narrativo de la nota `R22`-equivalente si la vista "Details" no aparece en algún filing.

### Estado de la caché

Los 66 `R*.htm` del filing analizado quedaron guardados en `cache/rhtm/` (no versionado, excluido por `.gitignore`) para reutilizarlos sin volver a golpear la API de la SEC.

## Update Letter

**Fuente:** Update Letter trimestral en PDF (carta a accionistas), dos trimestres alejados en el tiempo para forzar la detección de cambios de maquetación.
Script: `spikes/spike_update_letter.py`. Ejecutado el 2026-09-22 con `SEC_USER_AGENT` configurado en `.env`.

### URL exactas y localización

Localizar la URL de Q1 2024 no fue trivial: `ir.tesla.com` bloquea el acceso automatizado con un desafío de Akamai (`Access Denied`, `/_sec/cpr/challenge`), así que no se pudo navegar la página de "Quarterly Disclosure" directamente. Se recurrió a búsqueda web y a comprobar candidatos con `curl -I`.

| Periodo | URL | Estado |
|---|---|---|
| Q1 2024 | `https://digitalassets.tesla.com/tesla-contents/image/upload/IR/TSLA-Q1-2024-Update.pdf` | HTTP 200, 7.458.951 bytes |
| Q2 2026 | `https://assets-ir.tesla.com/tesla-contents/IR/TSLA-Q2-2026-Update.pdf` | HTTP 200, 10.552.832 bytes |

> [!warning] El patrón de URL de la tarea NO es estable entre trimestres
> La tarea asumía (correctamente para el trimestre antiguo) que los PDF viven en `digitalassets.tesla.com` con la ruta `tesla-contents/image/upload/IR/TSLA-Q{n}-{YYYY}-Update.pdf` (alojado en Cloudinary). Esto **funciona para Q1 2024** pero **falla con 404 para Q2 2026** — la misma plantilla de URL con `TSLA-Q2-2026-Update.pdf` en `digitalassets.tesla.com` devuelve `X-Cld-Error: Resource not found`. El trimestre reciente está alojado en un **host distinto**, `assets-ir.tesla.com` (servido por MinIO, no Cloudinary), con una ruta ligeramente distinta (`tesla-contents/IR/...`, sin el segmento `image/upload`). Es decir: **en algún momento entre 2024 y 2026 Tesla migró el alojamiento de estos PDF**, y no hay una única plantilla de URL que sirva para todo el histórico. Para localizar el PDF de un trimestre arbitrario hay que probar ambos patrones (o, mejor, resolver la URL real desde el 8-K de resultados de ese trimestre en EDGAR — el exhibit 99.1 — en vez de adivinar la URL en el dominio de Tesla).
> No se encontró, dentro del alcance de esta tarea, una tercera fuente 100 % estable (p. ej. un índice JSON versionado); construir la URL de un trimestre cualquiera sigue siendo una heurística, no una certeza.

### Estructura del documento: cambia de un trimestre a otro

El índice (página 2 de ambos PDF) ya delata el cambio de maquetación:

- **Q1 2024** (31 páginas): Highlights(3), Financial Summary(4), Operational Summary(6), Vehicle Capacity(7), Core Technology(8), Other Highlights(9), Outlook(10), Photos & Charts(11), Key Metrics(22), Financial Statements(24), Additional Information(30).
- **Q2 2026** (33 páginas): Highlights(3), Financial Summary(4), Operational Summary(5), Manufacturing & Hardware(6), Supporting Infrastructure(7), AI & Software(8), Services(9), Outlook(10), Photos & Charts(11), Key Metrics(23), Financial Statements(26), Additional Information(32).

Las secciones "Vehicle Capacity", "Core Technology" y "Other Highlights" de 2024 desaparecen; en 2026 se sustituyen por "Manufacturing & Hardware", "Supporting Infrastructure", "AI & Software" y "Services" — un rediseño de contenido, no solo de paginación. **La numeración de página de cada sección NO es estable entre trimestres** (Key Metrics pasa de la página 22 a la 23, Financial Statements de la 24 a la 26), igual que ocurría con los `R*.htm` de EDGAR. La única forma fiable de localizar una sección es buscarla por contenido, no por número de página fijo — así lo hace la versión corregida del script (busca los rótulos `"F I N A N C I A L S U M M A R Y"` y `"O P E R A T I O N A L S U M M A R Y"` recorriendo todas las páginas).

> [!question] Laguna
> Los rótulos de sección se extraen con un espacio intercalado entre cada letra (p. ej. `"F I N A N C I A L S U M M A R Y"`) por el tracking tipográfico del diseño del PDF. No se ha comprobado si este espaciado es constante en todos los trimestres del histórico (solo en los dos analizados, donde sí coincide) ni si depende de la versión del software con el que Tesla genera el PDF.

### ¿Aparecen las mismas etiquetas en ambos trimestres?

Las etiquetas literales que proponía la tarea (`"Total production"`, `"Total deliveries"`, `"Days of supply"`, `"Energy storage deployments"`, `"Solar deployments"`, `"Total gross margin"`, `"Operating margin"`, `"Free cash flow"`) **no coinciden todas con el texto real**. Tras inspeccionar `extract_text()` a mano, el resultado por etiqueta es:

| Métrica buscada | Q1 2024 (nombre exacto) | Q2 2026 (nombre exacto) | ¿Estable? |
|---|---|---|---|
| Producción total | `Total production` | `Total production` | Sí |
| Deliveries totales | `Total deliveries` | `Total deliveries` | Sí |
| Deliveries por grupo de modelos | `Model 3/Y deliveries` / `Other models deliveries` | `Model 3/Y deliveries` / `Other models deliveries` | Sí |
| Días de inventario | `Global vehicle inventory (days of supply)(1)` | `Global vehicle inventory (days of supply)(4)` | Sí (solo cambia el número de nota al pie) |
| Almacenamiento desplegado | `Storage deployed (MWh)` | `Storage deployed (GWh)` | **NO — cambia la unidad, no solo el rótulo** (ver aviso abajo) |
| Margen bruto | `Total GAAP gross margin` | `Total GAAP gross margin` | Sí, pero **no es** `"Total gross margin"` como asumía la tarea |
| Margen operativo | `Operating margin` | `Operating margin` | Sí |
| Free cash flow | `Free cash flow` | `Free cash flow` | Sí |
| Deployments solares (MW) | no aparece como cifra | no aparece como cifra | No existe como métrica numérica en ninguno de los dos trimestres |
| "Energy storage deployments" (cadena literal) | aparece en el texto narrativo de la página "Other Highlights" (`Other Highlights`, no en la tabla) | no aparece (esa sección ya no existe en 2026; ver "Structure") | No |

> [!warning] Contradicción con la premisa de la tarea: "GWh de almacenamiento desplegados" cambia de unidad entre trimestres, no solo de nombre
> En Q1 2024 la fila de la tabla "Operational Summary" es `Storage deployed (MWh)` con valor `4.053` (es decir, 4.053 MWh = 4,053 GWh). En Q2 2026 la misma fila pasa a llamarse `Storage deployed (GWh)` con valor `13.5` (13,5 GWh). **Si un extractor asumiera ciegamente que la fila siempre está en MWh (como pide literalmente la tarea, "GWh de almacenamiento desplegados", asumiendo que hay que convertir desde MWh), o asumiera que el rótulo con el que hace `match` es fijo, produciría un error de 1000× al cambiar de trimestre sin darse cuenta.** Cualquier extractor debe leer la unidad del propio rótulo de la fila (`(MWh)` vs `(GWh)`) en cada ejecución, nunca asumirla fija.

> [!warning] "MW solares" no existe como cifra en ninguno de los dos trimestres
> Se buscó de dos formas: (a) la cadena literal `"Solar deployments"` en todo el texto de ambos PDF — ausente en los dos; (b) cualquier línea que contenga a la vez `"olar"` y `"MW"` en todo el documento — ninguna coincidencia en ninguno de los dos trimestres. Lo único que existe sobre solar es una mención narrativa sin cifra ("...partially offset by a decrease in solar deployments" en Q1 2024; "...progressed in the quarter for solar and semiconductor manufacturing" en Q2 2026) y, en el balance, la partida contable `Solar energy systems, net` (valor en libros, no deployments del trimestre). **La métrica "MW solares desplegados" que pedía valorar esta tarea no está disponible en el Update Letter de ninguno de los dos trimestres analizados como cifra explícita**; si existe en algún trimestre del histórico, no es en estos dos, y no se puede dar por hecho que exista en general.

### ¿`extract_tables()` da estructura utilizable, o hace falta regex sobre texto plano?

**`extract_tables()` funciona bien y de forma consistente en ambos trimestres** para las dos tablas relevantes (Financial Summary y Operational Summary): en los dos casos devuelve **una única tabla por página**, con la misma forma (7 columnas: etiqueta + 5 trimestres + `YoY`), una fila por métrica, sin necesidad de `regex` sobre texto plano. No hace falta recurrir a texto plano con expresiones regulares para estas dos tablas — es el caso favorable. Ejemplo de fila idéntica en estructura entre ambos trimestres:
```
['Total production', '440.808', '479.700', '430.488', '494.989', '433.371', '-2%']   # 2024Q1
['Total production', '410.244', '447.450', '434.358', '408.386', '451.758', '10%']   # 2026Q2
```
La salida cruda completa de `extract_tables()` para ambas páginas y ambos trimestres queda recogida en la salida literal del script (sección siguiente del informe de la tarea).

Donde `extract_tables()` **no sirve** es en las páginas de gráficos ("Photos & Charts", "Key Metrics"): son gráficas de barras vectoriales sin tabla subyacente, y el propio `extract_text()` devuelve las etiquetas del eje X en **orden invertido y con los caracteres del trimestre invertidos** (p. ej. `"1202-Q2"` en vez de `"Q2-2021"`), señal inequívoca de que el texto proviene de un objeto gráfico mal ordenado, no de texto real de tabla. Esas páginas quedan descartadas como fuente fiable.

### ¿La página del cuadro de métricas es siempre la misma?

**No.** Ya documentado arriba: la tabla "Operational Summary" está en la página 6 (índice 5) en Q1 2024 y en la página 5 (índice 4) en Q2 2026 — un desplazamiento de una página completa por el rediseño de secciones. La tabla "Financial Summary" sí coincidió por casualidad en la página 4 (índice 3) en ambos trimestres, pero no se puede generalizar ese único punto de coincidencia: hay que localizar cada tabla buscando el rótulo de sección en el texto de cada página, recorriendo el documento, exactamente igual que se tuvo que hacer con los `R*.htm` de EDGAR en el hallazgo de Segmentos.

### Veredicto: automatizable con esfuerzo — no apto para captura ingenua

- Las dos tablas núcleo (Financial Summary, Operational Summary) **sí se pueden automatizar de forma razonablemente robusta**: `extract_tables()` da estructura limpia y consistente, y localizar la página por contenido (no por número fijo) resuelve el problema de la paginación variable.
- Pero el extractor **no puede asumir nombres de fila fijos entre trimestres**: como mínimo hay que tolerar variantes de rótulo con distinta unidad (`Storage deployed (MWh)` vs `(GWh)`) y leer la unidad del propio texto de la celda en cada ejecución, nunca hardcodearla.
- **Deliveries totales, deliveries por grupo de modelos (Model 3/Y vs. otros), producción total y días de inventario son extraíbles de forma fiable** en ambos trimestres con el mismo enfoque (buscar página por contenido + `extract_tables()`).
- **GWh de almacenamiento desplegados es extraíble, pero exige normalizar la unidad por trimestre** (leer si el rótulo dice MWh o GWh y convertir).
- **MW solares desplegados NO es extraíble**: no existe como cifra en el texto de ninguno de los dos trimestres analizados. Si el dashboard necesita esta métrica, **hay que recurrir a captura manual** (o a otra fuente, p. ej. el propio comunicado de prensa de producción/entregas, que no se ha explorado en esta tarea) — no es un problema de robustez del parser, es que el dato no está en esta fuente en el formato esperado.
- **La localización de la propia URL del PDF no es automatizable de forma trivial** sin resolverla desde el 8-K de EDGAR: el host cambió de `digitalassets.tesla.com` a `assets-ir.tesla.com` entre 2024 y 2026, y `ir.tesla.com` bloquea la navegación automatizada con un desafío anti-bot.

**Conclusión:** el Update Letter es una fuente **automatizable con esfuerzo medio** para las métricas de producción/deliveries/inventario/almacenamiento (con el cuidado de normalizar unidades y localizar tablas por contenido), pero **no** para MW solares, que en la práctica solo se puede resolver con **captura manual con checklist** — son pocos campos y cambian una vez por trimestre, tal y como anticipaba la propia tarea como conclusión aceptable. Se recomienda además, para fase 1, resolver la URL del PDF de cada trimestre desde el exhibit 99.1 del 8-K en EDGAR (fuente estable, ya usada en el hallazgo de Segmentos) en vez de adivinar la plantilla de URL en el dominio de Tesla, que ha demostrado no ser estable.

### Estado de la caché

Los dos PDF (`update_2024Q1.pdf`, `update_2026Q2.pdf`) quedaron guardados en `cache/` (no versionado, excluido por `.gitignore`) para reutilizarlos sin volver a descargarlos.

## Deliveries

**Fuente:** exhibit 99.1 del 8-K de Tesla, CIK 0001318605, en EDGAR.
Script: `spikes/spike_deliveries.py`. Filing usado como caso principal: accession `0001628280-26-046717` (8-K del 2026-07-02, nota de Q2 2026). Filing usado como comprobación histórica: accession `0001564590-19-024414` (8-K del 2019-07-02, nota de Q2 2019). Ejecutado el 2026-09-22 con `SEC_USER_AGENT` configurado en `.env`.

### Vía que funcionó: EDGAR (preferida), pero con dos resoluciones dinámicas, no una URL fija

Ni `ir.tesla.com` (bloqueado por el desafío Akamai, ya documentado en tareas previas) ni una plantilla de URL fija sirven aquí. Hicieron falta **dos pasos de resolución dinámica**, ninguno de los cuales asume una URL o nombre de fichero predecible:

1. **Elegir el 8-K correcto.** La nota de deliveries se presenta como 8-K con item `2.02` (Results of Operations), pero **el 8-K de resultados/Update Letter también lleva item `2.02`** — ambos son indistinguibles por el campo `items` de `https://data.sec.gov/submissions/CIK0001318605.json`. Se distinguen por **fecha de presentación relativa al cierre de trimestre**: la nota de deliveries se presenta con `filingDate` en los primeros días del mes siguiente al cierre (día ≤10: `2026-07-02`, `2026-04-02`, `2026-01-02`, `2025-10-02`...), mientras que el 8-K de resultados se presenta ~3 semanas después (día ≥15: `2026-07-22`, `2026-04-22`...). El script usa esta heurística de fecha, no el campo `items`.
2. **Localizar el exhibit 99.1 dentro del filing elegido.** El nombre de fichero del exhibit **no es estable entre eras**: en el filing de 2019 es `tsla-ex991_14.htm`, en el de 2026 es `exhibit99111111.htm` (sufijo generado por Workiva, sin patrón reconocible). `index.json` del filing tampoco distingue qué fichero es el EX-99.1 (su campo `type` es solo el icono de MIME, no el tipo de documento SEC). La forma robusta que se encontró: descargar el `.txt` de la submission completa — esa sí tiene URL predecible, `<accession-con-guiones>.txt` — y buscar con regex el bloque SGML `<TYPE>EX-99.1\n<SEQUENCE>\d+\n<FILENAME>...`, formato que EDGAR mantiene igual desde hace décadas. Esta técnica funcionó **de forma idéntica en el filing de 2019 y en el de 2026**, 7 años de diferencia.

> [!warning] No dar por buena la plantilla de URL fija que proponía la tarea
> La tarea original planteaba localizar "la URL real de la nota de deliveries" como si fuera una única URL fija. En la práctica **no existe tal URL estable ni siquiera dentro de EDGAR**: cambia el nombre del exhibit entre eras y hay que distinguir el 8-K correcto entre dos candidatos con el mismo item. El script resuelve ambos pasos programáticamente en cada ejecución; no hardcodea ninguna URL de exhibit.

Aviso adicional sobre la codificación: el texto de la nota usa apóstrofos/comillas tipográficas Unicode (p. ej. `Tesla’s`) que en la consola de Windows se muestran como `�` al volcar por `print()`; es un problema de encoding de terminal, no del contenido descargado (se comprobó que el HTML crudo trae el carácter Unicode correcto, `’`).

### Nombres exactos y literales de las filas de la tabla

**Q2 2026** (columnas: `Production`, `Deliveries`, `Subject to operating lease accounting`):

| Fila (nombre literal) | Production | Deliveries | Subject to operating lease accounting |
|---|---:|---:|---:|
| `Model 3/Y` | 442.936 | 467.762 | 2% |
| `Other Models` | 8.822 | 12.364 | 2% |
| `Total` | 451.758 | 480.126 | 2% |

**Q2 2019** (columnas: `Production`, `Deliveries`, sin columna de leasing):

| Fila (nombre literal) | Production | Deliveries |
|---|---:|---:|
| `Model S/X` | 14.517 | 17.650 |
| `Model 3` | 72.531 | 77.550 |
| `Total` | 87.048 | 95.200 |

> [!warning] Contradicción con la premisa de nombres de fila estables
> Los nombres literales de fila **no son los mismos en todo el histórico**: en 2019 son `Model S/X` y `Model 3` (Model Y aún no existía); en 2026 son `Model 3/Y` y `Other Models` (Model Y se agrupa con Model 3, y `Other Models` pasa a incluir S/X/Cybertruck y el resto). El extractor de fase 1 **no puede hardcodear** `Model 3/Y`/`Other Models` como si valiera para todo el histórico 2019-2026; tiene que tratar el cambio de agrupación de modelos como un cambio de esquema fechado (probablemente coincidiendo con el lanzamiento de Model Y en 2020), o bien capturar la fila `Total` como ancla estable y las filas de detalle por modelo como best-effort. `Total` sí es literal y estable en ambos trimestres comprobados.

### Energy storage deployments (GWh/MWh): no está en esta tabla

Los "13.5 GWh of energy storage products" desplegados en Q2 2026 **solo aparecen en la frase narrativa inicial** del comunicado (`"...delivered over 480,000 vehicles and deployed 13.5 GWh of energy storage products."`), **no como fila de la tabla** ni en ninguna otra tabla del documento — la única tabla del exhibit 99.1 es la de producción/deliveries de vehículos. Si el dashboard necesita esta cifra desde la nota de deliveries (en vez de esperar al Update Letter, que sí la trae en tabla — ver hallazgo de "Update Letter"), habrá que extraerla por regex de la frase narrativa, cuya redacción no está garantizada que sea estable entre trimestres (no se ha comprobado en más de un trimestre).

### ¿Es predecible la URL por trimestre, o hay que recorrer el listado de 8-K?

**Hay que recorrer el listado de 8-K** (vía `submissions/CIK...json`) y resolver el exhibit dinámicamente vía el `.txt` de la submission, como se explica arriba. No existe una plantilla de URL fija ni siquiera dentro del propio dominio `sec.gov` — a diferencia de, por ejemplo, `companyfacts.json`, cuya URL sí es fija y no depende de recorrer ningún índice.

### ¿Histórico 2019-2020 accesible por esta vía, y mismo formato?

**Sí, accesible.** Se comprobó explícitamente el 8-K del 2019-07-02 (accession `0001564590-19-024414`, nota de Q2 2019). La misma técnica de resolución (submissions JSON → heurística de fecha → `.txt` de la submission → regex `<TYPE>EX-99.1`) funcionó sin cambios.

**El formato NO es exactamente el mismo:**
- La tabla en 2019 **no tiene** la columna `Subject to operating lease accounting` (aparece en algún momento posterior del histórico; no se ha determinado en qué trimestre exacto empieza).
- Los nombres de fila por modelo difieren (`Model S/X`/`Model 3` en 2019 vs. `Model 3/Y`/`Other Models` en 2026), como ya se explicó arriba.
- La estructura general (tabla de 3 columnas mínimo: modelo, Production, Deliveries, con fila `Total`) sí se mantiene igual.

### ¿Distingue la tabla deliveries en leasing del desglose de producción?

**Parcialmente, y solo en el formato reciente.** La tabla de 2026 tiene la columna `Subject to operating lease accounting` con un porcentaje (`2%` en las tres filas de Q2 2026) — es el **porcentaje de las deliveries de esa fila que están sujetas a contabilidad de leasing operativo**, no un recuento absoluto de vehículos en leasing ni una columna de producción en leasing. La tabla de 2019 no tiene ninguna columna de leasing. En ningún caso hay un desglose de *producción* en leasing (leasing es un concepto que solo aplica al lado de deliveries/reconocimiento contable, no a la fabricación).

### Veredicto: automatizable

- **Localizar el filing y el exhibit correcto es automatizable de forma robusta** una vez resuelto con la heurística de fecha + regex sobre el `.txt` de la submission (probado en dos eras 7 años distintas sin fallar).
- **La tabla de Production/Deliveries por modelo y el Total son extraíbles de forma fiable con `pandas.read_html`** tras recortar el envoltorio SGML (mismo patrón ya usado en Segmentos y Update Letter).
- **El extractor no puede asumir nombres de fila de modelo fijos** entre 2019 y 2026 (ver contradicción arriba); sí puede asumir que la fila `Total` existe siempre con ese nombre literal.
- **GWh de almacenamiento desplegado no está en tabla en esta fuente** (solo en Q2 2026 se comprobó, como frase narrativa) — si se necesita desde la nota de deliveries y no desde el Update Letter, exige extracción por regex sobre texto libre, de fiabilidad menor que una tabla.
- El único punto manual recomendable es una **revisión puntual tras cada cambio de esquema de Tesla** (p. ej. si añaden o quitan una columna, o cambian de nuevo la agrupación de modelos), pero no la extracción en sí, que es completamente automatizable con el enfoque de este script.

### Estado de la caché

Esta tarea no descargó ficheros pesados a `cache/` (los exhibits HTML son pequeños, ~13 KB, y no se persistieron en disco; se procesaron en memoria en cada ejecución del script).

## Mercado

**Script:** `spikes/spike_market.py`. Ejecutado el 2026-09-22.

### Stooq: NO usable con `requests` simple

El endpoint de descarga que pedía el enunciado (`https://stooq.com/q/d/l/?s=tsla.us&i=d`) ya no sirve el CSV directamente:

- Sin cabecera `User-Agent` (la que pone `requests` por defecto): responde **404**.
- Con `User-Agent` de navegador, y probando tanto `s=tsla.us` como con rango explícito `&d1=20190101&d2=20260922`: responde **200** pero el cuerpo es una página HTML que ejecuta un **reto anti-bot "proof-of-work" en JavaScript** (calcula un hash SHA-256 con dificultad y lo envía por POST a `/__verify` antes de servir el contenido real; ver `cache/stooq_raw.txt` con la respuesta cruda capturada durante el spike, no versionado).

No se ha intentado resolver este reto por scripting: es un mecanismo de detección de bots y queda fuera de lo que debe hacer este spike. **Veredicto: Stooq no es una fuente viable tal cual para este proyecto**, salvo que en el futuro cambie su política de acceso o se use un navegador real (Selenium/Playwright), lo cual excede el alcance de un fetch simple con `requests`.

### Alternativa que sí funciona: `api.nasdaq.com`

Se probó el endpoint público que usa la propia web de nasdaq.com para pintar el gráfico histórico de una acción, sin clave ni autenticación:

```
https://api.nasdaq.com/api/quote/TSLA/historical?assetclass=stocks&fromdate=2019-01-01&limit=9999&todate=2026-09-22
```

Requiere solo una cabecera `User-Agent` de navegador (con el `User-Agent` por defecto de `requests` también responde 200, pero se usó una cabecera de navegador por prudencia). Responde JSON con `totalRecords` y un array de filas `{date, close, volume, open, high, low}`.

- **Cobertura real:** 2019-01-02 → 2026-09-21, **1940 sesiones**. Cubre sobradamente el requisito "desde 2019".
- Los precios vienen como texto con símbolo `$` (p. ej. `"$20.6747"`), hay que parsear a float quitando el símbolo.

### Veredicto sobre el ajuste por split: LA SERIE DE NASDAQ ESTÁ AJUSTADA

Cifras concretas obtenidas en la ejecución del spike:

- **Cierre del 2019-01-02: 20.6747 USD** — ronda los 20 USD, no los 300 USD. Esto por sí solo ya indica serie ajustada por los dos splits (factor acumulado 15).
- **Continuidad alrededor del split 5:1 (31-ago-2020):** cierres de 134.89 (25-ago) → 143.54 → 149.25 → 147.56 → **166.11 (31-ago)** → 158.35 (1-sep) → 149.12 → 135.67. No hay salto brusco de magnitud ×5 ni ×1/5 en la sesión del split; la serie se mueve de forma continua.
- **Continuidad alrededor del split 3:1 (25-ago-2022):** cierres de 296.67 (19-ago) → 289.91 → 296.45 → 297.10 → **296.07 (25-ago)** → 288.09 → 284.82 → 277.70. Tampoco hay salto de magnitud ×3 ni ×1/3.

**Conclusión: la serie de `api.nasdaq.com` ya viene ajustada por ambos splits y se puede usar tal cual, sin aplicar factores de corrección manuales.**

### BCE: cobertura completa y frecuencia diaria

La URL del enunciado funciona exactamente como estaba escrita, sin cambios:

```
https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A?format=csvdata&startPeriod=2019-01-01
```

- Devuelve CSV con 1978 filas (columnas `TIME_PERIOD`, `OBS_VALUE` entre otras).
- **Cobertura:** 2019-01-02 → 2026-09-22 (hasta la fecha de ejecución del spike), **frecuencia diaria** (serie `D.USD.EUR.SP00.A`), solo días hábiles TARGET (sin fines de semana ni festivos del BCE).
- Últimos valores observados: 2026-09-18 → 1.1460, 2026-09-21 → 1.1490, 2026-09-22 → 1.1463 USD por EUR.

### Fragilidades detectadas

- **Stooq** cambió de comportamiento respecto al enunciado de la tarea: pasó de servir CSV plano a exigir un reto JS anti-bot. Es una fuente frágil por diseño (puede cambiar de política en cualquier momento) y **no se recomienda para este proyecto**.
- **`api.nasdaq.com` es un endpoint no documentado oficialmente** (es el que usa el frontend de nasdaq.com internamente, no una API pública con contrato estable). Puede cambiar de formato o empezar a exigir cabeceras adicionales sin aviso, igual que le pasó a Stooq. Es la mejor alternativa gratuita y sin clave encontrada en este spike, pero conviene aislarla detrás de una capa de adaptador para poder sustituirla si deja de funcionar.
- El parámetro `limit=9999` de Nasdaq no está documentado como "sin límite"; en esta ejecución devolvió el histórico completo pedido (1940 filas, coincide con `totalRecords`), pero convendría paginar o verificar `totalRecords == len(rows)` en el extractor definitivo por si en el futuro aplican un límite duro inferior.
- El **BCE** no mostró fragilidad: URL estable, formato CSV consistente, sin límites de descarga aparentes.

## Conclusiones

### Respuestas a las cinco preguntas de la fase 0

**1. ¿Trae `companyfacts` el desglose por segmento con dimensiones utilizables?**
No. El script recorrió los 643 conceptos `us-gaap` buscando claves adicionales a las estándar (`start`, `end`, `val`, `accn`, `fy`, `fp`, `form`, `filed`, `frame`) y no encontró ninguna: `companyfacts` entrega únicamente hechos consolidados a nivel de compañía, sin ningún desglose dimensional (ni segmento, ni geografía, ni ningún otro eje XBRL). Ver sección "EDGAR companyfacts" → "Pregunta central".

**2. Si no, ¿de dónde se obtienen los segmentos?**
De los estados renderizados (`R*.htm`) del propio filing 10-Q/10-K, concretamente de la nota "Segment Reporting and Information about Geographic Areas". Localizarlos exige recorrer los `R*.htm` del filing buscando por contenido (no por número fijo, que varía entre filings) y recortar el envoltorio SGML antes de pasarlos a `pandas.read_html`. La vista "Details" (equivalente a `R63.htm` en el filing analizado) da una tabla más limpia que la vista narrativa (`R22.htm`). Ver sección "Segmentos".

**3. ¿Se parsea el Update Letter de forma estable entre trimestres?**
Con esfuerzo, sí, para las tablas núcleo. `extract_tables()` da estructura consistente (7 columnas, una fila por métrica) en los dos trimestres comprobados (Q1 2024 y Q2 2026) para las tablas "Financial Summary" y "Operational Summary", siempre que la página se localice buscando el rótulo de sección por contenido (la paginación no es estable) y que la unidad de cada fila se lea del propio rótulo en cada ejecución (caso "Storage deployed (MWh)" vs. "(GWh)"). No es estable, en cambio, la URL del PDF (cambió de host entre 2024 y 2026) ni la existencia de "MW solares" como cifra (no aparece en ningún trimestre analizado). Ver sección "Update Letter".

**4. ¿Es constante el formato de la nota de deliveries desde 2019?**
No es idéntico, pero sí extraíble de forma fiable con el mismo enfoque en ambas eras comprobadas (Q2 2019 y Q2 2026, 7 años de diferencia). Cambia la columna `Subject to operating lease accounting` (no existe en 2019) y cambian los nombres literales de las filas por modelo (`Model S/X`/`Model 3` en 2019 frente a `Model 3/Y`/`Other Models` en 2026). La fila `Total` sí es literal y estable en ambos trimestres. La resolución del filing y el exhibit correctos (heurística de fecha de presentación + regex `<TYPE>EX-99.1` sobre el `.txt` de la submission) también funcionó sin cambios en las dos eras. Ver sección "Deliveries".

**5. ¿Sirve Stooq como fuente de cotización?**
No. El endpoint `https://stooq.com/q/d/l/?s=tsla.us&i=d` ya no sirve CSV plano: sin `User-Agent` devuelve 404, y con `User-Agent` de navegador devuelve una página HTML con un reto anti-bot "proof-of-work" en JavaScript. Resolverlo excede el alcance de un fetch simple con `requests` (exigiría Selenium/Playwright). La alternativa que sí funcionó, sin clave ni autenticación, es `api.nasdaq.com`, cuya serie ya viene ajustada por los dos splits de Tesla (comprobado por continuidad de precio alrededor de las fechas de split, sin saltos de magnitud ×5 ni ×3). El tipo de cambio EUR/USD del BCE (`data-api.ecb.europa.eu`) funcionó exactamente como estaba escrito en el enunciado, sin fragilidad detectada. Ver sección "Mercado".

### Decisiones tomadas

**1. SOTP con dos unidades GAAP (Automoción y Energía).**
Tesla solo reporta dos segmentos bajo ASC 280 — "we have two operating and reportable segments: (i) automotive and (ii) energy generation and storage" (nota de `R22.htm`) — y no asigna I+D ni SG&A a nivel de segmento (esos gastos solo existen a nivel consolidado; ver "Limitación relevante para el margen por segmento"). No existe un tercer segmento de "Servicios": los ingresos de "Services and other" están incluidos dentro del segmento Automotive, como se comprobó por diferencia exacta (25.097 − (20.006 + 146 + 364) = 4.581 M USD, que coincide con la línea "Services and other" de `R24.htm`). Por ello se valorarán las dos unidades GAAP reportadas (Automoción y Energía) con su margen bruto propio, repartiendo el opex consolidado con un criterio explícito: I+D mayoritariamente a Automoción (por concentrar el gasto en IA y FSD) y SG&A proporcional a ingresos. FSD y Robotaxi, al no tener margen ni segmento propios en el filing, quedan fuera del DCF y se tratan como opcionalidad.

**2. Deliveries: guardar el literal y derivar una serie homogénea.**
Los nombres de fila por modelo cambian entre eras (`Model S/X` y `Model 3` en 2019; `Model 3/Y` y `Other Models` a partir de la introducción de Model Y) y no se pueden hardcodear como si fueran constantes en todo el histórico (ver "Contradicción con la premisa de nombres de fila estables"). La decisión es conservar el nombre literal tal como Tesla lo publicó en cada época y, además, derivar dos series comparables en todo el periodo: un grupo de alto volumen (Model 3 → Model 3/Y) y un grupo de nicho (Model S/X → Other Models). La fila `Total` es estable en ambas eras comprobadas y sirve de ancla/control.

**3. Cotización desde `api.nasdaq.com`, aislada detrás de un adaptador.**
Stooq no es viable (reto anti-bot JS, ver pregunta 5). `api.nasdaq.com` es un endpoint no documentado oficialmente (el que usa internamente el frontend de nasdaq.com, no una API pública con contrato estable) y puede cambiar de formato sin aviso, igual que le ocurrió a Stooq — de ahí la decisión de aislarlo detrás de un adaptador, para poder sustituirlo sin tocar el resto del pipeline. El histórico completo (2019-01-02 → 2026-09-21, 1940 sesiones) ya está descargado y verificado como ajustado por ambos splits (5:1 de agosto 2020 y 3:1 de agosto 2022, sin saltos de magnitud en ninguno de los dos). A partir de ahora el mantenimiento mensual solo necesita el cierre de un mes cada vez; si el endpoint falla, el script debe avisar y permitir teclear el dato a mano en vez de fallar silenciosamente.

**4. MW solares: KPI eliminado del cuadro de mando.**
Se buscó de dos formas en los dos Update Letter analizados (Q1 2024 y Q2 2026): la cadena literal "Solar deployments" (ausente en ambos) y cualquier línea que combinara "olar" y "MW" (sin coincidencias en ninguno de los dos). Solo existe mención narrativa sin cifra ("...a decrease in solar deployments" en Q1 2024; "...progressed... for solar and semiconductor manufacturing" en Q2 2026) y la partida de balance "Solar energy systems, net" (valor en libros, no deployments del trimestre). Al no existir como cifra explícita en ninguno de los dos trimestres comprobados, y siendo el negocio solar de Tesla residual y decreciente frente al almacenamiento, se elimina este KPI del cuadro de mando en vez de mantenerlo como captura manual.

### Hallazgos operativos para la fase 1

- **Cada Update Letter contiene cinco trimestres en el mismo cuadro** (columnas de 5 trimestres + `YoY` en las tablas "Financial Summary" y "Operational Summary"; ver ejemplo de fila `Total production` con 5 valores trimestrales en la sección "Update Letter"). Con unos seis PDF bien elegidos (espaciados ~5 trimestres entre sí) se cubren los treinta trimestres desde Q1 2019, en lugar de descargar treinta PDF individuales.
- **Verificación cruzada disponible entre dos fuentes independientes:** la nota 8-K de deliveries (exhibit 99.1) y el PDF del Update Letter dan las mismas cifras para el mismo trimestre — Q2 2026: 451.758 producidos y 480.126 entregados en ambas fuentes (fila `Total` de la tabla de deliveries en la sección "Deliveries", y fila `Total production`/`Total deliveries` en la sección "Update Letter"). Sirve como control de integridad automático: si en fase 1 ambas fuentes se extraen para el mismo trimestre y no coinciden, es señal de un error de parseo en alguna de las dos.

## Cobertura efectiva de EDGAR

Resultado de la primera carga real del histórico (`src/cargar_historico.py`, tarea 1.7) contra `data.sec.gov/api/xbrl/companyfacts`. La serie resultante tiene **30 trimestres, de 2019Q1 a 2026Q2**, sin huecos en el eje temporal: los 30 períodos esperados están presentes como filas.

### Cobertura completa (30/30)

`cogs_total`, `gross_profit_total`, `opex_rd`, `opex_sga`, `operating_income`, `net_income_gaap`, `cash_and_investments`, `shares_outstanding`, `deferred_revenue_current`, `deferred_revenue_noncurrent`.

En los campos de flujo esta cobertura solo se alcanza gracias a la reconstrucción del cuarto trimestre por diferencia (anual del 10-K menos los tres primeros trimestres): EDGAR **nunca** publica un hecho de Q4 discreto, porque el 10-K informa del ejercicio completo. La carga reconstruyó 15 cuartos trimestres en `cogs_total`, `opex_rd`, `opex_sga` y `operating_income`, y 5 en `gross_profit_total` y `net_income_gaap` (menos porque esos conceptos ya tenían más años cubiertos por otra vía).

### Cobertura parcial

- **`revenue_total`: 15/30.** Causa identificada: `CONCEPTOS["revenue_total"]` lista dos conceptos alternativos, `RevenueFromContractWithCustomerExcludingAssessedTax` y `Revenues`, pero `extraer_serie_con_filed()` se queda con **el primero que exista** en `companyfacts`, sin comparar coberturas. El primero existe, pero solo tiene hechos trimestrales desde 2022Q3 (más tres de 2018); el segundo, `Revenues`, cubre 59 trimestres, incluido todo 2019-2022. Resultado: faltan 2019Q1-2022Q2. No es un error de mapeo — el concepto elegido da cifras correctas donde existe — sino una limitación del criterio de selección entre conceptos alternativos: elige por existencia, no por cobertura. **Pendiente de decidir en tarea posterior**; no se ha tocado aquí por estar fuera del alcance de esta tarea.
- **`eps_diluted_gaap` y `shares_diluted`: 23/30.** Es lo correcto y esperado: faltan exactamente los 7 cuartos trimestres del rango (2019Q4-2025Q4). Ver el apartado sobre magnitudes no aditivas más abajo.
- **`ocf`, `capex`, `sbc`: 8/30.** Causa identificada: **los hechos del estado de flujos de efectivo se publican acumulados desde el inicio del ejercicio (YTD), no por trimestre discreto.** Se comprobó midiendo la duración de cada hecho en `companyfacts`: para estos tres conceptos solo existen duraciones de ~90 días con cierre a 31 de marzo; el resto son de 180, 272 y 364 días. Es decir, el único trimestre discreto publicado es el Q1 de cada año, y por eso la cobertura es exactamente 8 (Q1 de 2019 a 2026). La reconstrucción de Q4 tampoco puede ayudar, porque `completar_q4()` exige tener Q1, Q2 y Q3. Obtener Q2 y Q3 discretos exigiría restar YTD consecutivos (Q2 = 6 meses menos 3 meses, Q3 = 9 meses menos 6 meses), lógica que hoy no existe en `fetch_edgar.py`. **Es el hueco más relevante de la carga**, porque `ocf` y `capex` son los insumos del free cash flow.

### Ausentes por completo del CSV

No se cargan porque no están en `CONCEPTOS` y vienen de otra fuente (estados renderizados del filing, tarea posterior): `filing_date`, `total_debt`, los seis campos de segmento (`revenue_auto_segment`, `cogs_auto_segment`, `gross_profit_auto_segment`, `revenue_energy_segment`, `cogs_energy_segment`, `gross_profit_energy_segment`) y los cuatro de línea de producto (`revenue_auto_sales`, `revenue_auto_leasing`, `revenue_reg_credits`, `revenue_services`).

La validación contra el esquema `FINANCIALS` falla, como estaba previsto, y lo hace por `revenue_total` (nulos en 15 filas), que es el primer campo obligatorio con hueco que encuentra.

### Acciones: diluidas frente a en circulación

Confirmado sobre los datos reales: **`shares_diluted` no tiene ningún cuarto trimestre (0/7) y `shares_outstanding` los tiene todos (7/7)**. Es por diseño, no un fallo de la carga. Las acciones diluidas son un **promedio ponderado del período**, y el promedio de un ejercicio no es la suma de sus trimestres: su Q4 no se puede obtener por diferencia, y por eso `CLASE_MAGNITUD` las marca como `no_aditiva` y la carga las deja vacías en lugar de inventar un valor. Las acciones en circulación son un **saldo a fecha de cierre** (`balance`), vienen ya con el trimestre de cierre y cubren los 30 trimestres. Para calcular la capitalización bursátil debe usarse `shares_outstanding`.

La serie de `shares_outstanding`, normalizada por los dos splits (x15 antes del 31-08-2020, x3 entre esa fecha y el 25-08-2022, x1 después), **es monótona creciente en los 30 trimestres, sin un solo retroceso**. Arranca en 2.605.230.000 (2019Q1) y termina en 3.949.000.000 (2026Q2). El salto de 2025Q3 a 2025Q4 (3.324 a 3.751 millones, +12,8%) no es un artefacto de la normalización: está confirmado contra el filing, que reporta 3.751.000.000 acciones en circulación a 31-12-2025 (`cache/rhtm/R3.htm`, balance parenthetical del 10-Q de Q2 2026).

### Verificación manual contra los filings originales

Tres contrastes contra la fuente primaria, para descartar un error de mapeo de conceptos XBRL que se propagaría en silencio a la valoración.

**1. Ingresos totales de 2019Q1 — NO VERIFICABLE EN EL CSV (campo vacío).**

- Fuente: 10-Q del trimestre cerrado a 31-03-2019 (accession `0001564590-19-013462`, presentado el 29-04-2019), *Consolidated Statements of Operations (Unaudited)*, línea `Total revenues`. Cifra del filing: **4.541.464 miles de USD = 4.541,5 M USD**.
- Cifra del CSV: **vacía**, por la limitación de selección entre conceptos alternativos descrita arriba.
- El concepto de reserva `Revenues`, que la carga no llega a usar, sí tiene el dato: **4.541.000.000 USD**, que coincide con el filing dentro del redondeo a millones. Es decir, el dato existe en EDGAR y es correcto; lo que falla es qué concepto elige la carga.
- El resto de la fila 2019Q1 sí está y **coincide línea a línea con ese mismo 10-Q**: coste total de ingresos 3.975.721 da CSV 3.975 M; margen bruto 565.743 da CSV 566 M; I+D 340.174 da CSV 340 M; SG&A 703.929 da CSV 704 M; resultado operativo (565.743 menos 1.087.574 de opex total) = -521.831 da CSV -522 M. El mapeo de conceptos es, por tanto, correcto.

**2. Resultado operativo de un cuarto trimestre — VERIFICADO, COINCIDE EXACTAMENTE.**

Es la comprobación crítica, porque valida la reconstrucción de Q4 por diferencia. Se contrastaron dos trimestres, ambos reconstruidos (se confirmó que EDGAR no publica ningún hecho directo para ellos):

| Trimestre | Reconstrucción de la carga | Cifra del Update Letter | Fuente |
|---|---|---|---|
| 2023Q4 | 8.891 - 6.827 = **2.064 M USD** | **2.064** | `cache/update_2024Q1.pdf`, p. 4, tabla *Financial Summary (Unaudited)*, fila `Income from operations`, columna `Q4-2023` |
| 2025Q4 | 4.355 - 2.946 = **1.409 M USD** | **1.409** | `cache/update_2026Q2.pdf`, p. 4, tabla *Financial Summary (Unaudited)*, fila `Income from operations`, columna `Q4-2025` |

Coincidencia exacta en ambos. Además, las otras cuatro columnas de cada tabla coinciden también al dólar con el CSV (Q1-2023 2.664, Q2-2023 2.399, Q3-2023 1.764, Q1-2024 1.171; Q2-2025 923, Q3-2025 1.624, Q1-2026 941, Q2-2026 398), y lo mismo la fila `Total revenues`, incluidos los dos Q4 reconstruidos de ingresos (Q4-2023 25.167 y Q4-2025 24.901). **El método de reconstrucción de Q4 por diferencia queda validado contra fuente independiente.**

**3. Acciones en circulación de 2026Q2 — VERIFICADO, COINCIDE.**

- Cifra del CSV: **3.949.000.000**.
- Fuente: 10-Q del trimestre cerrado a 30-06-2026, *Consolidated Balance Sheets (Parenthetical)*, línea `Common stock, shares outstanding (in shares)` a 30-06-2026 (`cache/rhtm/R3.htm`). Cifra del filing: **3.949.000.000**. Coincidencia exacta.
- Control adicional con la portada del mismo 10-Q (`cache/rhtm/R1.htm`), campo `Entity Common Stock, Shares Outstanding`: **3.949.547.394** a 16-07-2026. Es coherente: la portada da el recuento exacto a una fecha posterior al cierre, mientras que el balance lo presenta redondeado a millones a la fecha de cierre.

### Nota sobre el redondeo del histórico antiguo

`extraer_serie_con_filed()` conserva, para cada período, el valor del filing **más reciente** que lo contiene. Como Tesla pasó a presentar sus estados en millones (en lugar de miles) a partir del 10-K del ejercicio 2020, presentado el 08-02-2021, los trimestres antiguos llegan al CSV redondeados a millones enteros: el resultado operativo de 2019Q1 es -521.831 miles en el 10-Q original y -522.000.000 en el CSV. Es una pérdida de precisión de hasta 500.000 USD por dato en los trimestres anteriores a 2021, irrelevante frente a magnitudes de miles de millones, pero conviene tenerla presente al cuadrar contra un filing original: **no es un error de extracción, es el redondeo de la propia reexpresión de Tesla.**

### Efecto secundario: un test se vuelve dependiente del estado de la caché

Al ejecutar la carga real, `tests/test_http_client.py::test_exige_user_agent_para_dominios_de_la_sec` empieza a fallar (44/45). No es una regresión del código de producción, sino una dependencia de estado del propio test:

- El test construye `ClienteHTTP(directorio_cache="cache")`, es decir, apunta al directorio de caché **real** del proyecto, y espera que `obtener()` lance `FaltaUserAgent` al pedir la URL de `companyfacts`.
- Pero `ClienteHTTP.obtener()` comprueba la caché de disco **antes** de validar `SEC_USER_AGENT`. Una vez que la carga ha descargado `companyfacts` (fichero `cache/597cbaed968739244245bfeeaea6d98b`, 3,6 MB), esa llamada devuelve los bytes cacheados y nunca llega a la comprobación que el test verifica.
- Comprobado: retirando ese único fichero de `cache/`, la suite vuelve a pasar 45/45; restaurándolo, vuelve a fallar.

Como `cache/` está en `.gitignore`, el fallo solo aparece en una máquina donde ya se haya ejecutado la carga, no en un clon limpio. La corrección natural sería que el test use `tmp_path` como ya hace `test_devuelve_lo_cacheado_sin_tocar_la_red`, en lugar del directorio real. **No se ha aplicado aquí por estar `tests/` fuera del alcance de esta tarea.**
