# Metodología de valoración

Justificación de cada supuesto de `data/assumptions.yaml`. Versión 2026-09-23,
propuesta inicial pendiente de validar por el usuario.

**Advertencia.** Herramienta analítica que refleja supuestos propios. No es
asesoramiento de inversión.

## Qué se valora y qué no

Se valoran por descuento de flujos las dos unidades que Tesla reporta como
segmentos: automoción y energía. Robotaxi, FSD y Optimus **no** entran en el
valor: la diferencia entre la capitalización y el valor de las dos unidades es
la *opcionalidad implícita*, lo que el mercado paga por negocios que aún no
generan flujos.

## Punto de partida (doce meses hasta 2026Q2)

| Magnitud | Valor |
|---|---|
| Ingresos de automoción | 90.820 M USD, margen bruto 17,4% |
| Ingresos de energía | 12.799 M USD, margen bruto 29,4% |
| I+D sobre ingresos | 7,5% |
| SG&A sobre ingresos | 6,8% |
| Margen operativo | 4,2% |

## Supuestos comunes

- **Prima de riesgo de mercado, 5%.** En el rango habitual para EE.UU. (4-6%).
- **Beta calculada, no supuesta.** 60 rentabilidades mensuales de TSLA contra
  SPY. La beta histórica de Tesla ronda 2: con un tipo sin riesgo del 4,96% da
  un coste de las acciones cercano al 15%. **Es el supuesto que más pesa en el
  resultado**: la sensibilidad al WACC (±2 puntos) va en el resultado.
- **Tipo impositivo 21%.** Tipo federal de EE.UU. El tipo efectivo de Tesla ha
  sido menor por créditos fiscales; normalizar al federal es conservador.
- **Crecimiento terminal 3%.** Por debajo del tipo sin riesgo, como exige la
  coherencia del modelo.
- **ROIC terminal 15%.** Con un 3% de crecimiento implica reinvertir un 20% del
  NOPAT a perpetuidad.
- **Reparto de la I+D, 85% a automoción.** Juicio propio: Tesla no asigna I+D
  por segmento, y el gasto en IA y conducción autónoma se concentra en
  automoción. Dos consecuencias a tener presentes:
  1. **El reparto no cambia el valor total** mientras las dos unidades tengan
     beneficio y el mismo coste de capital: solo mueve valor de una a otra. La
     sensibilidad del resultado lo muestra por unidad.
  2. **Parte de esa I+D financia la opcionalidad** (robotaxi, Optimus), pero su
     coste se carga a los negocios actuales. Eso infravalora los negocios
     actuales y, por tanto, sobrestima la opcionalidad implícita. Es un sesgo
     conocido y deliberadamente conservador.

## Escenarios

| | bear | base | bull |
|---|---|---|---|
| Automoción: crecimiento año 1 → año 10 | 0% → 2% | 8% → 3% | 15% → 4% |
| Automoción: margen bruto final | 15% | 19% | 23% |
| Energía: crecimiento año 1 → año 10 | 15% → 3% | 30% → 5% | 45% → 6% |
| Energía: margen bruto final | 22% | 28% | 32% |
| Automoción: ventas sobre capital | 2,3 | 2,5 | 2,7 |
| Energía: ventas sobre capital | 2,5 | 3,0 | 3,5 |
| I+D final sobre ingresos | 7,5% | 6,0% | 5,0% |
| SG&A final sobre ingresos | 6,5% | 5,0% | 4,5% |

- **Automoción.** Los ingresos cayeron un 3,5% en 2024 y un 6,3% en 2025. El
  escenario base supone una recuperación moderada sin robotaxi. Margen final
  del 19%: entre el 16-17% actual y el 26-27% de 2021-2022, que se dio con
  precios de venta mucho más altos.
- **Energía.** Ha crecido un 67% (2024) y un 27% (2025), con el margen pasando
  del 1% (2020) al 30% (2025). El base supone que el crecimiento se modera y el
  margen se estabiliza algo por debajo del actual por la competencia.
- **Ventas sobre capital.** Cuántos dólares de ingresos adicionales genera cada
  dólar invertido. Energía, con menos inmovilizado por dólar vendido, algo más
  alta que automoción. **Es el supuesto más decisivo para el reverse DCF:**
  junto con el margen, fija la rentabilidad del capital incremental. Si queda
  por debajo del WACC, crecer más destruye valor en el modelo. La propuesta
  inicial (2,0 en automoción) daba una rentabilidad incremental de un 12%,
  inferior al WACC del 14%; a petición del usuario se subió 0,5 en todos los
  escenarios. No hay en los datos cargados capital invertido con el que
  contrastar la cifra: queda como punto a revisar.
- **Gastos operativos.** El base supone apalancamiento operativo: la I+D y el
  SG&A crecen menos que los ingresos.

## Revisión

Estos supuestos quedan congelados hasta la revisión trimestral siguiente a los
resultados de Q3 2026. Cambiar cualquier cifra exige cambiar `version`.
