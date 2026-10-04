// Logica del simulador de supuestos, sin DOM. La usa web/app.js y se prueba
// con Node en tests/js/simulador.test.js.
const Simulador = (function () {
  "use strict";
  const M = (typeof module !== "undefined" && module.exports)
    ? require("./motor.js") : Motor;

  const ESCENARIOS = ["bear", "base", "bull"];
  const UNIDADES = ["automocion", "energia"];
  const ORDEN_COMUN = ["horizonte_anios", "prima_riesgo_mercado", "meses_beta",
    "coste_deuda_antes_impuestos", "tipo_impositivo", "crecimiento_terminal",
    "roic_terminal", "reparto_id_automocion"];
  const ORDEN_UNIDAD = ["crecimiento_inicial", "crecimiento_final",
    "margen_bruto_final", "ventas_sobre_capital", "ajuste_wacc"];

  const copia = (x) => JSON.parse(JSON.stringify(x));

  function valorar(datos, escenario, comun, wacc) {
    const unidades = M.proyectar(datos.base, escenario, comun, wacc);
    return { unidades, vpa: M.valorPorAccion(M.sumaUnidades(unidades), datos.balance) };
  }

  function recalcular(datos, escenario, comun, wacc) {
    try {
      const { unidades, vpa } = valorar(datos, escenario, comun, wacc);
      const acciones = datos.balance.acciones;
      return {
        ok: true,
        valorPorAccion: vpa,
        precioFrenteAValor: vpa > 0 ? datos.precio / vpa - 1 : null,
        opcionalidad: datos.precio * acciones - vpa * acciones,
        unidades: { automocion: unidades.automocion.valor, energia: unidades.energia.valor },
        crecimientoImplicito: M.crecimientoImplicito(datos.precio, datos.base, escenario,
          comun, wacc, datos.balance),
        // Piezas del descuento por unidad, para explicar el calculo.
        desglose: unidades,
        anioCero: datos.anio_cero && datos.anio_cero.ingresos_previos
          ? M.fcfAnioBase(datos.base, datos.anio_cero.ingresos_previos, escenario, comun)
          : null,
      };
    } catch (error) {
      return { ok: false, motivo: error.message };
    }
  }

  // Recalcula los tres escenarios oficiales y los compara con Python.
  function autoverificar(datos, valoracion, tolerancia = 1e-9) {
    const fallos = [];
    for (const nombre of ESCENARIOS) {
      const oficial = valoracion.escenarios[nombre].valor_por_accion;
      let js;
      try {
        js = valorar(datos, datos.supuestos.escenarios[nombre], datos.supuestos.comun,
          datos.wacc).vpa;
      } catch (error) {
        fallos.push({ escenario: nombre, js: null, python: oficial, diferencia: null,
          motivo: error.message });
        continue;
      }
      const diferencia = Math.abs(js - oficial) / Math.max(Math.abs(oficial), 1e-300);
      if (!(diferencia <= tolerancia)) {
        fallos.push({ escenario: nombre, js, python: oficial, diferencia });
      }
    }
    return fallos;
  }

  // Decimal sin notacion exponencial, que YAML leeria como texto.
  function numero(x) {
    if (!Number.isFinite(x)) throw new Error("hay un supuesto que no es un numero");
    return x.toFixed(10).replace(/\.?0+$/, "");
  }

  const DIFERENCIA_MINIMA = 1e-12;
  const difieren = (a, b) => Math.abs(a - b) > DIFERENCIA_MINIMA;

  function cambiosComun(comunOficial, comunFinal) {
    const cambios = [];
    for (const k of ORDEN_COMUN) {
      if (difieren(comunFinal[k], comunOficial[k])) {
        cambios.push(`comun.${k}: ${numero(comunOficial[k])} -> ${numero(comunFinal[k])} ` +
          "(afecta a los tres escenarios)");
      }
    }
    return cambios;
  }

  function cambiosEscenario(nombre, oficial, explorado) {
    const cambios = [];
    for (const u of UNIDADES) {
      for (const k of ORDEN_UNIDAD) {
        if (difieren(explorado[u][k], oficial[u][k])) {
          cambios.push(`${nombre}.${u}.${k}: ${numero(oficial[u][k])} -> ` +
            `${numero(explorado[u][k])}`);
        }
      }
    }
    for (const k of ["id_sobre_ingresos_final", "sga_sobre_ingresos_final"]) {
      if (difieren(explorado[k], oficial[k])) {
        cambios.push(`${nombre}.${k}: ${numero(oficial[k])} -> ${numero(explorado[k])}`);
      }
    }
    return cambios;
  }

  function aYaml(supuestos, nombre, escenario, comun, wacc, waccOficial, fecha) {
    if (!ESCENARIOS.includes(nombre)) {
      throw new Error(`el escenario "${nombre}" no existe: debe ser bear, base o bull`);
    }
    const comunFinal = Object.assign({}, supuestos.comun, comun);
    if (comunFinal.roic_terminal <= comunFinal.crecimiento_terminal) {
      throw new Error("comun.roic_terminal debe superar a comun.crecimiento_terminal");
    }
    const escenarios = Object.assign({}, supuestos.escenarios, { [nombre]: escenario });

    const cambios = [
      ...cambiosComun(supuestos.comun, comunFinal),
      ...cambiosEscenario(nombre, supuestos.escenarios[nombre], escenario),
    ];

    const difiereWacc = difieren(wacc, waccOficial);
    const lineaWacc = difiereWacc
      ? `# ATENCION: WACC explorado ${(wacc * 100).toFixed(2)} % frente al oficial ` +
        `${(waccOficial * 100).toFixed(2)} %; el YAML no lo recoge porque el motor lo calcula.`
      : `# El WACC del simulador (${(waccOficial * 100).toFixed(2)} %) no se exporta: ` +
        "el motor lo calcula.";

    const l = [
      `# Supuestos exportados desde el simulador del cuadro de mando el ${fecha},`,
      `# partiendo del escenario ${nombre} de la version ${supuestos.version}.`,
      lineaWacc,
      "# Revisa las cifras y la version antes de sustituir data/assumptions.yaml.",
    ];
    if (cambios.length === 0) {
      l.push(`# Sin cambios respecto a la version ${supuestos.version}.`);
    } else {
      l.push(`# Cambios respecto a la version ${supuestos.version}:`);
      for (const c of cambios) l.push(`#   ${c}`);
    }
    l.push(`version: "${fecha}"`, "", "comun:");
    for (const k of ORDEN_COMUN) l.push(`  ${k}: ${numero(comunFinal[k])}`);
    l.push("", "escenarios:");
    ESCENARIOS.forEach((e, i) => {
      l.push(`  ${e}:`);
      for (const u of UNIDADES) {
        l.push(`    ${u}:`);
        for (const k of ORDEN_UNIDAD) l.push(`      ${k}: ${numero(escenarios[e][u][k])}`);
      }
      l.push(`    id_sobre_ingresos_final: ${numero(escenarios[e].id_sobre_ingresos_final)}`);
      l.push(`    sga_sobre_ingresos_final: ${numero(escenarios[e].sga_sobre_ingresos_final)}`);
      if (i < ESCENARIOS.length - 1) l.push("");
    });
    return l.join("\n") + "\n";
  }

  return { ESCENARIOS, copia, recalcular, autoverificar, aYaml };
})();

if (typeof module !== "undefined" && module.exports) module.exports = Simulador;
