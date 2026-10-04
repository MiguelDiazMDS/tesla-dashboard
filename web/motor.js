// Nucleo del calculo de valoracion, traduccion literal de src/dcf.py,
// src/sotp.py y src/reverse_dcf.py. Mismas operaciones en el mismo orden,
// para que la aritmetica coincida: tests/test_paridad_js.py lo comprueba.
// La paridad exigida es de 1e-9 relativo, no bit a bit: Math.pow de V8 y el
// pow de la libreria de C que usa Python pueden diferir en 1 ulp.
// Funciones puras. Funciona en la pagina (global Motor) y en Node (require).
const Motor = (function () {
  "use strict";
  const UNIDADES = ["automocion", "energia"];

  const pct = (x) => (x * 100).toFixed(2).replace(".", ",") + " %";

  function trayectoria(inicial, final, anios) {
    if (anios < 1) throw new Error("el horizonte debe ser de al menos un anio");
    if (anios === 1) return [final];
    const paso = (final - inicial) / (anios - 1);
    const serie = [];
    for (let i = 0; i < anios; i++) serie.push(inicial + paso * i);
    return serie;
  }

  // sum() de Python: desde la 3.12 suma los float con compensacion de
  // Neumaier, no uno detras de otro. Se reproduce el algoritmo de CPython
  // (builtin_sum_impl) para que el redondeo coincida.
  function sumaPython(valores) {
    if (valores.length === 0) return 0;
    let resultado = 0 + valores[0];
    let c = 0.0;
    for (let i = 1; i < valores.length; i++) {
      const x = valores[i];
      const t = resultado + x;
      if (Math.abs(resultado) >= Math.abs(x)) {
        c += (resultado - t) + x;
      } else {
        c += (x - t) + resultado;
      }
      resultado = t;
    }
    if (c && Number.isFinite(c)) resultado += c;
    return resultado;
  }

  // Cada flujo a valor de hoy: el del año t se divide entre (1 + tasa)^t.
  function descontar(flujos, tasa) {
    const descontados = [];
    for (let t = 1; t <= flujos.length; t++) {
      descontados.push(flujos[t - 1] / Math.pow(1 + tasa, t));
    }
    return descontados;
  }

  function valorPresente(flujos, tasa) {
    return sumaPython(descontar(flujos, tasa));
  }

  function valorTerminal(nopatSiguiente, tasa, crecimiento, roic) {
    if (tasa <= crecimiento) {
      throw new Error(`el coste de capital (${pct(tasa)}) debe superar al ` +
        `crecimiento terminal (${pct(crecimiento)})`);
    }
    if (roic <= crecimiento) {
      throw new Error(`el ROIC terminal (${pct(roic)}) debe superar al ` +
        `crecimiento terminal (${pct(crecimiento)})`);
    }
    const reinversion = nopatSiguiente > 0 ? crecimiento / roic : 0.0;
    return nopatSiguiente * (1 - reinversion) / (tasa - crecimiento);
  }

  function nopat(ebit, tipoImpositivo) {
    return ebit > 0 ? ebit * (1 - tipoImpositivo) : ebit;
  }

  function proyectar(base, escenario, comun, waccBase, repartoId) {
    const n = comun.horizonte_anios;
    // En Python un horizonte no entero falla en range(); aqui hay que pararlo.
    if (!Number.isInteger(n)) {
      throw new Error("el horizonte debe ser un numero entero de anios");
    }
    const tipo = comun.tipo_impositivo;
    const gTerminal = comun.crecimiento_terminal;
    const reparto = repartoId === undefined || repartoId === null
      ? comun.reparto_id_automocion : repartoId;
    const cuotaId = { automocion: reparto, energia: 1 - reparto };

    const ingresos = {};
    for (const unidad of UNIDADES) {
      const supuesto = escenario[unidad];
      const serie = [];
      let nivel = base.ingresos[unidad];
      for (const g of trayectoria(supuesto.crecimiento_inicial,
                                  supuesto.crecimiento_final, n)) {
        nivel *= 1 + g;
        serie.push(nivel);
      }
      ingresos[unidad] = serie;
    }
    const total = [];
    for (let t = 0; t < n; t++) total.push(sumaPython(UNIDADES.map((u) => ingresos[u][t])));
    const ratioId = trayectoria(base.id_sobre_ingresos, escenario.id_sobre_ingresos_final, n);
    const ratioSga = trayectoria(base.sga_sobre_ingresos, escenario.sga_sobre_ingresos_final, n);

    const resultado = {};
    for (const unidad of UNIDADES) {
      const supuesto = escenario[unidad];
      const margenes = trayectoria(base.margen_bruto[unidad], supuesto.margen_bruto_final, n);
      const ebit = [];
      const fcff = [];
      let anterior = base.ingresos[unidad];
      for (let t = 0; t < n; t++) {
        const ventas = ingresos[unidad][t];
        const gastoId = ratioId[t] * total[t] * cuotaId[unidad];
        const gastoSga = ratioSga[t] * ventas;
        const resultadoOperativo = ventas * margenes[t] - gastoId - gastoSga;
        const reinversion = (ventas - anterior) / supuesto.ventas_sobre_capital;
        ebit.push(resultadoOperativo);
        fcff.push(nopat(resultadoOperativo, tipo) - reinversion);
        anterior = ventas;
      }
      const tasa = waccBase + supuesto.ajuste_wacc;
      const nopatTerminal = nopat(ebit[n - 1], tipo) * (1 + gTerminal);
      const terminal = valorTerminal(nopatTerminal, tasa, gTerminal, comun.roic_terminal);
      // Mismas operaciones que valorPresente(fcff, tasa) + terminal / (1 + tasa)^n,
      // conservando las piezas para explicar el calculo en la pagina.
      const descontados = descontar(fcff, tasa);
      const vpFlujos = sumaPython(descontados);
      const vpTerminal = terminal / Math.pow(1 + tasa, n);
      const valor = vpFlujos + vpTerminal;
      // Un supuesto ausente o no numerico no lanza en JavaScript: se propaga
      // como NaN. Python habria fallado antes; aqui se falla al final.
      if (!Number.isFinite(valor)) {
        throw new Error("supuestos incompletos o no numericos");
      }
      resultado[unidad] = { ingresos: ingresos[unidad], ebit, fcff, valor, tasa, descontados,
        vpFlujos, nopatTerminal, terminal, vpTerminal };
    }
    return resultado;
  }

  // FCF del modelo en el año base: NOPAT por unidad con los margenes y
  // ratios de gasto del año base, menos la reinversion que exige el
  // crecimiento del ultimo año. No interviene en la valoracion.
  function fcfAnioBase(base, ingresosPrevios, escenario, comun, repartoId) {
    const tipo = comun.tipo_impositivo;
    const reparto = repartoId === undefined || repartoId === null
      ? comun.reparto_id_automocion : repartoId;
    const cuotaId = { automocion: reparto, energia: 1 - reparto };
    const total = sumaPython(UNIDADES.map((u) => base.ingresos[u]));
    const unidades = {};
    for (const u of UNIDADES) {
      const ventas = base.ingresos[u];
      const ebitU = ventas * base.margen_bruto[u] - base.id_sobre_ingresos * total * cuotaId[u] -
        base.sga_sobre_ingresos * ventas;
      const nopatU = nopat(ebitU, tipo);
      const reinversion = (ventas - ingresosPrevios[u]) / escenario[u].ventas_sobre_capital;
      unidades[u] = { ebit: ebitU, nopat: nopatU, reinversion, fcf: nopatU - reinversion };
    }
    const suma = (k) => sumaPython(UNIDADES.map((u) => unidades[u][k]));
    return { unidades, nopat: suma("nopat"), reinversion: suma("reinversion"), fcf: suma("fcf") };
  }

  function sumaUnidades(unidades) {
    return sumaPython(UNIDADES.map((u) => unidades[u].valor));
  }

  function valorPorAccion(valorUnidades, balance) {
    return (valorUnidades + balance.caja + balance.inversiones - balance.deuda) /
      balance.acciones;
  }

  function conCrecimiento(escenario, g) {
    const copia = Object.assign({}, escenario);
    for (const u of UNIDADES) {
      copia[u] = Object.assign({}, escenario[u],
        { crecimiento_inicial: g, crecimiento_final: g });
    }
    return copia;
  }

  function valorConCrecimiento(g, base, escenario, comun, wacc, balance) {
    const unidades = proyectar(base, conCrecimiento(escenario, g), comun, wacc);
    return valorPorAccion(sumaUnidades(unidades), balance);
  }

  function crecimientoImplicito(precio, base, escenario, comun, wacc, balance,
                                minimo = -0.10, maximo = 0.80, paso = 0.01,
                                tolerancia = 1e-4) {
    const diferencia = (g) =>
      valorConCrecimiento(g, base, escenario, comun, wacc, balance) - precio;
    let gPrevio = minimo;
    let dPrevio = diferencia(minimo);
    if (dPrevio === 0) return gPrevio;
    // round() de Python redondea al par en los empates y Math.round hacia
    // arriba; con los valores por defecto el cociente (~90) no es un empate
    // y ambos dan lo mismo.
    const pasos = Math.round((maximo - minimo) / paso);
    for (let i = 1; i <= pasos; i++) {
      const g = minimo + i * paso;
      const d = diferencia(g);
      if ((dPrevio < 0) !== (d < 0) || d === 0) {
        let bajo = gPrevio;
        let alto = g;
        let dBajo = dPrevio;
        while (alto - bajo > tolerancia) {
          const medio = (bajo + alto) / 2;
          const dMedio = diferencia(medio);
          if ((dBajo < 0) === (dMedio < 0)) {
            bajo = medio;
            dBajo = dMedio;
          } else {
            alto = medio;
          }
        }
        return (bajo + alto) / 2;
      }
      gPrevio = g;
      dPrevio = d;
    }
    return null;
  }

  return {
    UNIDADES, sumaPython, trayectoria, descontar, valorPresente, valorTerminal, nopat, proyectar,
    fcfAnioBase, sumaUnidades, valorPorAccion, valorConCrecimiento, crecimientoImplicito,
  };
})();

if (typeof module !== "undefined" && module.exports) module.exports = Motor;
