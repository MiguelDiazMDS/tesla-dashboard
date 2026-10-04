# Tesla — datos, motor de valoración y cuadro de mando

Seguimiento y valoración de Tesla (TSLA) para una tesis de inversión propia.
Este repositorio contiene la **capa de datos** (histórico trimestral desde
Q1 2019, cargado desde fuentes públicas y verificado), el **motor de
valoración** y el **cuadro de mando**, una página HTML publicada como artifact
privado de claude.ai.

- Metodología de valoración: `docs/metodologia-valoracion.md`
- Hallazgos sobre las fuentes: `docs/hallazgos-fase-0.md`
- Catálogo de fuentes por campo: `docs/fuentes.md`

**Advertencia.** Esto es una herramienta analítica que refleja los supuestos de
quien la usa. No constituye asesoramiento en materia de inversión.

---

## Arquitectura

Tres capas desacopladas.

```
CAPA DE DATOS          →   MOTOR DE VALORACIÓN   →   PRESENTACIÓN
data/*.csv                 src/valorar.py            src/construir_dashboard.py
                           dist/valoracion.json      dist/dashboard.html
```

Los módulos de `src/` que parsean **no acceden a la red**: reciben el texto ya
descargado. Todo el acceso a red está en `http_client.py`. Por eso los tests
funcionan sin conexión y sin depender del contenido de `cache/`.

---

## Puesta en marcha

```bash
python -m pip install --user -r requirements.txt
cp .env.example .env     # y rellenar SEC_USER_AGENT
```

**`SEC_USER_AGENT` es obligatorio.** La SEC exige que toda petición
automatizada se identifique con nombre y correo de contacto, y responde HTTP
403 sin ello. El fichero `.env` no se versiona.

```bash
export SEC_USER_AGENT="Nombre Apellido correo@dominio.com"
```

Otras fuentes necesitan una cabecera de navegador corriente, que el cliente
añade sola: `api.nasdaq.com` no devuelve 403 sin ella, simplemente deja la
conexión colgada hasta agotar el tiempo de espera.

---

## Ficheros de datos

Todas las cifras monetarias están **en dólares**, no en miles ni millones.
Cada fila lleva `source` y `retrieved_at`: ningún dato del cuadro de mando
puede aparecer sin poder rastrearse hasta su documento de origen.

### `data/financials_quarterly.csv` — 30 trimestres, clave `period` ("2019Q1")

| Bloque | Campos | Origen |
|---|---|---|
| Consolidado | `revenue_total`, `cogs_total`, `gross_profit_total`, `opex_rd`, `opex_sga`, `operating_income`, `net_income_gaap`, `eps_diluted_gaap` | API XBRL de la SEC |
| Caja y balance | `ocf`, `capex`, `cash_and_investments` (solo caja), `short_term_investments`, `total_debt` (suma de cuatro componentes, arrendamientos incluidos), `deferred_revenue_current`, `deferred_revenue_noncurrent` | API XBRL |
| Impuestos | `income_tax`, `pretax_income` | API XBRL |
| Amortizaciones | `da` | Estado de flujos renderizado, desacumulado y contrastado con el filing siguiente |
| Publicación | `filing_date` | Índice de filings de la SEC. Lo usan los múltiplos para no mirar al futuro |
| Acciones | `shares_diluted` (media ponderada), `shares_outstanding` (saldo a cierre), `sbc` | API XBRL, normalizadas por split |
| Segmentos | `revenue_*_segment`, `cogs_*_segment`, `gross_profit_*_segment` para `auto` y `energy` | Estados renderizados del filing |
| Líneas de producto | `revenue_auto_sales`, `revenue_reg_credits`, `revenue_auto_leasing`, `revenue_services`, `revenue_energy_sales`, `revenue_energy_leasing` | Estados renderizados |
| Geografía | `revenue_us`, `revenue_china`, `revenue_other` | Estados renderizados |

### `data/operating_quarterly.csv` — 30 trimestres, clave `period`

`deliveries_total`, `production_total`, y las series homogéneas
`deliveries_volumen` / `deliveries_nicho` y sus equivalentes de producción,
más `etiqueta_volumen` y `etiqueta_nicho` con el nombre literal que usó Tesla
en ese trimestre. Origen: exhibit 99.1 de la nota de entregas (8-K).

Del Update Letter trimestral (exhibit 99.1 del 8-K de resultados, o el PDF de
Tesla cuando el exhibit trae las páginas como imagen):

| Campo | Cobertura | Nota |
|---|---|---|
| `storage_deployed_gwh` | 30/30 | Normalizado a GWh: hasta 2024 Tesla lo daba en MWh |
| `days_inventory` | 28/30 | Faltan 2019Q1 y 2019Q2: sus cartas ya no están publicadas |
| `fsd_subscriptions` | 7/30 | Suscripciones activas de FSD. Tesla solo las publica desde 2024Q4 |

`source_update_letter` cita la carta de la que procede cada fila.

### `data/market_monthly.csv` — 93 meses, clave `month` ("2019-01")

`price_close` (serie ya ajustada por los splits de 2020 y 2022), `spy_close`
(ETF SPY, para la beta), `rf_10y` (bono del Tesoro a 10 años, en tanto por
uno) y `eurusd`.

---

## Regenerar los datos

```bash
export SEC_USER_AGENT="..."
python -m src.cargar_todo
```

Ejecuta los seis cargadores en el orden correcto y termina validando los tres
ficheros: esquemas, continuidad y las siete identidades contables. El orden
importa porque `cargar_historico` y `cargar_deliveries` reescriben su fichero
desde cero y los demás cargadores les añaden columnas. Si una comprobación
falla, la carga se detiene: no se relaja nada para que pase.

Los índices que cambian (filings de la SEC, tipos de cambio, el CSV del Tesoro
del año en curso) caducan en la caché a las 12 horas; los filings archivados,
que no cambian, se cachean para siempre.

El cliente HTTP cachea en `cache/`, así que repetir una carga es rápido y no
vuelve a molestar a los servidores de la SEC. Para forzar la descarga, borrar
la entrada correspondiente de `cache/`.

---

## Comprobaciones

```bash
python -m pytest tests/ -q
```

496 tests, todos sin red. Incluyen la paridad entre el motor de Python y
su traducción a JavaScript (`web/motor.js`), que exige Node: sin Node, la
prueba falla en vez de saltarse. La verificación de los datos reales la hace
`python -m src.cargar_todo` al final de cada carga.

Seis identidades contables que deben cumplirse siempre: los dos segmentos
suman el consolidado, las líneas de producto suman su segmento, las regiones
suman el consolidado, y en cada segmento ingresos menos coste da el margen.
**Nunca se relaja una tolerancia para que algo cuadre**: un descuadre es un
error de datos, no un umbral mal puesto.

---

## Trampas de las fuentes, resueltas

Están documentadas en `docs/hallazgos-fase-0.md`. Las que más daño habrían
hecho, porque ninguna produce un error visible:

1. **Bases de split mezcladas.** EDGAR conserva cada trimestre tal como se
   publicó y deja de reexpresar los antiguos, así que la serie de acciones
   saltaba de 177 a 922 millones entre Q2 y Q3 de 2019. Se desempata por el
   filing más reciente y se normaliza por el factor de split de esa fecha.
2. **Estado de flujos acumulado.** El flujo de explotación y el capex se
   publican acumulados del ejercicio, no por trimestre. Sin desacumular no hay
   free cash flow.
3. **Selección del concepto de menor cobertura.** Tesla etiqueta los ingresos
   con dos conceptos XBRL distintos según la época; la lista de conceptos
   expresa preferencia **por periodo**, no elección global.
4. **Escala cambiante.** Las tablas de 2019 vienen en miles y las posteriores
   en millones. La escala se lee del encabezado.
5. **Segmentos cruzados.** El renderizado del 10-Q de 2023Q1 asigna a
   automoción los ingresos de energía y al revés. Se detecta con una regla de
   dominio: automoción nunca ha tenido menos ingresos que energía.
6. **Nomenclatura cambiante.** Los nombres de informes, de secciones y de
   líneas de modelos cambian entre épocas. Todo se normaliza, conservando
   siempre la etiqueta literal original.
7. **Precisión distinta entre cartas.** Cada Update Letter cubre cinco
   trimestres y un mismo dato aparece con distinta precisión en cartas
   sucesivas (3.653 MWh en una, 3,7 GWh en la siguiente). Se conserva el valor
   con más cifras significativas; solo una diferencia que no se explique por
   redondeo se trata como posible reexpresión y se avisa.

---

## Valoración

```bash
python -m src.valorar --borrador   # valora e imprime, sin escribir nada
python -m src.valorar              # valoración oficial -> dist/valoracion.json
```

- **Qué valora:** las dos unidades que Tesla reporta (automoción y energía),
  por descuento de flujos a 10 años con valor terminal de Gordon. Robotaxi, FSD
  y Optimus quedan fuera: la diferencia con la capitalización es la
  *opcionalidad implícita*.
- **Coste de capital:** CAPM con beta de 60 rentabilidades mensuales completas
  de TSLA frente a SPY y el bono del Tesoro a 10 años.
- **Reverse DCF:** crecimiento anual de ingresos que iguala valor y precio, más
  una rejilla crecimiento × margen de automoción.
- **Múltiplos:** EV/Ventas, PER, EV/EBITDA y P/FCF de cada mes con los datos
  publicados hasta entonces, y su percentil frente al histórico propio.

Supuestos en `data/assumptions.yaml`, justificados en
`docs/metodologia-valoracion.md`. **Se revisan una vez por trimestre.** Si
cambian sin cambiar `version`, la valoración oficial se detiene. La oficial
exige además el precio del mes en curso: antes de valorar, `python -m
src.cargar_mercado`.

---

## Cuadro de mando

```bash
python -m src.construir_dashboard   # -> dist/dashboard.html y dist/datos_dashboard.json
```

Se publica como artifact privado de claude.ai, cuya URL se guarda en `.env`
(`ARTIFACT_URL`). Se republica el mismo fichero para conservar la URL.

La construcción genera también `dist/web/index.html`, la misma página como
documento HTML completo (doctype, viewport y `noindex`), para publicarla en
un servidor propio: se sube ese único fichero (por ejemplo con FileZilla, por
SFTP) a la carpeta pública del servidor. Solo necesita acceso a cdnjs y a
Google Fonts. En un servidor propio la página es pública salvo que se proteja
la carpeta con contraseña desde el panel del alojamiento.

- **Se niega a construir** si la valoración no corresponde a los supuestos
  actuales (huella), al último mes o al último precio de `market_monthly.csv`,
  o si algún CSV no valida. Un precio nuevo exige volver a valorar.
- **Todas las cifras oficiales vienen de Python.** La página solo las muestra.
  Cada dato lleva su etiqueta R (reportado) o D (derivado) y su fuente en la
  tabla de trazabilidad.
- **Simulador de supuestos:** `web/motor.js` reproduce el motor de Python
  (paridad ≤ 1e-9 comprobada en la batería de tests). Al abrir la página
  recalcula los tres escenarios oficiales; si no coinciden, se desactiva.
  «Copiar como YAML» exporta los supuestos explorados con el formato de
  `data/assumptions.yaml`, para la revisión trimestral.
- **Piezas:** `src/datos_dashboard.py` (datos y KPIs derivados),
  `web/plantilla.html`, `web/estilos.css`, `web/app.js` (presentación),
  `web/simulador.js` y `web/motor.js` (simulador).

---

## Actualización mensual

En Claude Code, `/tesla-update` (la skill vive en `.claude/skills/tesla-update/`).
Dirige dos comandos y hace lo que exige juicio: preguntar, revisar la página,
republicarla en la misma URL, hacer el commit y resumir los cambios.

```bash
python -m src.actualizar preparar                         # carga, verifica e informa
python -m src.actualizar completar [--mantener-supuestos] # valora, histórico, página
```

- **`preparar`** ejecuta `cargar_todo`, compara los CSV con el último commit y
  escribe `dist/informe_actualizacion.json`: trimestres nuevos, reexpresiones,
  periodos o columnas que aparecen o desaparecen, mercado del mes y avisos de
  variaciones anómalas. Si desaparece un periodo (casi siempre, una descarga
  fallida) se detiene.
- **Trimestre financiero nuevo:** `completar` se niega a valorar hasta que el
  usuario decide, después de ver el informe, si mantiene los supuestos
  (`--mantener-supuestos`) o los revisa (versión nueva en `assumptions.yaml`).
  La pausa la garantiza `completar`; `python -m src.valorar` a mano no la
  comprueba.
- **Histórico:** cada valoración oficial deja una fila por mes en
  `data/historico_valoraciones.csv`, que alimenta el gráfico «Precio frente a
  valor» de la página.
- **Reintentos:** las respuestas 429 y 5xx, los cortes y los tiempos agotados
  se reintentan hasta 4 veces (2, 4 y 8 s, o lo que diga `Retry-After`, con un
  máximo de 60 s); un 404 o un 403 falla a la primera.

---

## Hitos

`data/milestones.yaml` documenta, con fuente y enlace en cada dato:

- **Seis hitos prioritarios** (Robotaxi a escala, Optimus comercial, FSD,
  beneficio del automóvil, energía, Tesla Semi en serie). Cada uno tiene pasos
  observables con su evidencia, las fechas que Tesla o Musk han comprometido
  (ligadas con `paso:` al paso que prometen) y, en FSD, automóvil y energía,
  métricas calculadas sobre los CSV con umbrales exigentes: FSD ≥ 2,5 millones
  de suscripciones y 5 mercados nuevos; margen de automoción sin créditos ≥ 20 %
  y operativo ≥ 10 % cuatro trimestres; ≥ 80 GWh en doce meses y margen de
  energía ≥ 28 %.
- **Historial de promesas cerradas o ajenas a los seis**, para el índice de
  deslizamiento: retraso realizado (cumplidas) y mínimo acumulado (añade las
  pendientes vencidas), con todas las fuentes y solo con las oficiales. El
  índice es informativo; no entra en la valoración.
- **Comprobación transversal:** capex del año frente a la guía, FCF de doce
  meses e investigaciones abiertas de la NHTSA.

`src/hitos.py` valida el fichero al cargarlo: fechas exactas salvo las
prometidas, enlaces, etiquetas R/E, pasos y promesas coherentes. Las métricas
usan solo trimestres consecutivos sin nulos. Los hitos se actualizan en
`/tesla-update` con evidencia que el usuario aprueba.

---

## Qué falta

- Autonomía: incidentes NHTSA (Standing General Order) y permisos (CPUC, DMV)
  automatizados, y estado del Robotaxi por ciudad.
- Matriculaciones por región (CPCA, ACEA, KBA) como indicador mensual
  adelantado de las entregas.
