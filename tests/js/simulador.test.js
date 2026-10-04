const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("path");
const Motor = require(path.join(__dirname, "..", "..", "web", "motor.js"));
const Simulador = require(path.join(__dirname, "..", "..", "web", "simulador.js"));

function datosDePrueba() {
  const unidad = (g0, m, vc) => ({ crecimiento_inicial: g0, crecimiento_final: 0.03,
    margen_bruto_final: m, ventas_sobre_capital: vc, ajuste_wacc: 0 });
  const escenario = (k) => ({ automocion: unidad(0.04 * k, 0.15 + 0.02 * k, 2.5),
    energia: unidad(0.15 * k, 0.25 + 0.02 * k, 3), id_sobre_ingresos_final: 0.06,
    sga_sobre_ingresos_final: 0.05 });
  const supuestos = { version: "2026-09-23",
    comun: { horizonte_anios: 10, prima_riesgo_mercado: 0.05, meses_beta: 60,
      coste_deuda_antes_impuestos: 0.06, tipo_impositivo: 0.21, crecimiento_terminal: 0.03,
      roic_terminal: 0.15, reparto_id_automocion: 0.85 },
    escenarios: { bear: escenario(1), base: escenario(2), bull: escenario(3) } };
  const datos = { base: { ingresos: { automocion: 90e9, energia: 12e9 },
      margen_bruto: { automocion: 0.17, energia: 0.29 }, id_sobre_ingresos: 0.075,
      sga_sobre_ingresos: 0.068 },
    balance: { caja: 15e9, inversiones: 28e9, deuda: 9e9, acciones: 3.9e9 },
    wacc: 0.14, precio: 379, supuestos };
  const valoracion = { escenarios: {} };
  for (const e of ["bear", "base", "bull"]) {
    const u = Motor.proyectar(datos.base, supuestos.escenarios[e], supuestos.comun, datos.wacc);
    valoracion.escenarios[e] = { valor_por_accion: Motor.valorPorAccion(Motor.sumaUnidades(u), datos.balance) };
  }
  return { datos, valoracion };
}

test("la autoverificacion pasa si las cifras coinciden", () => {
  const { datos, valoracion } = datosDePrueba();
  assert.deepEqual(Simulador.autoverificar(datos, valoracion), []);
});

test("la autoverificacion detecta una cifra oficial distinta", () => {
  const { datos, valoracion } = datosDePrueba();
  valoracion.escenarios.base.valor_por_accion *= 1.001;
  const fallos = Simulador.autoverificar(datos, valoracion);
  assert.equal(fallos.length, 1);
  assert.equal(fallos[0].escenario, "base");
});

test("recalcular con los supuestos oficiales da la cifra oficial", () => {
  const { datos, valoracion } = datosDePrueba();
  const r = Simulador.recalcular(datos, datos.supuestos.escenarios.base,
    datos.supuestos.comun, datos.wacc);
  assert.equal(r.ok, true);
  assert.equal(r.valorPorAccion, valoracion.escenarios.base.valor_por_accion);
  assert.equal(r.precioFrenteAValor, datos.precio / r.valorPorAccion - 1);
});

test("recalcular explica un supuesto que no se puede calcular", () => {
  const { datos } = datosDePrueba();
  const comun = Object.assign({}, datos.supuestos.comun, { roic_terminal: 0.02 });
  const r = Simulador.recalcular(datos, datos.supuestos.escenarios.base, comun, datos.wacc);
  assert.equal(r.ok, false);
  assert.match(r.motivo, /ROIC/);
});

test("la autoverificacion detecta un fallo por excepcion y explica el motivo", () => {
  const { datos, valoracion } = datosDePrueba();
  // Se rompen los supuestos vigentes del escenario bear (no los que produjeron
  // la cifra oficial en valoracion): el coste de capital queda por debajo del
  // crecimiento terminal y el motor lanza al proyectar.
  const roto = JSON.parse(JSON.stringify(datos.supuestos.escenarios.bear));
  roto.automocion.ajuste_wacc = -0.5;
  roto.energia.ajuste_wacc = -0.5;
  datos.supuestos.escenarios.bear = roto;
  const fallos = Simulador.autoverificar(datos, valoracion);
  const fallo = fallos.find((f) => f.escenario === "bear");
  assert.ok(fallo, "se esperaba un fallo para el escenario bear");
  assert.equal(fallo.js, null);
  assert.match(fallo.motivo, /coste de capital/);
});

test("la autoverificacion trata una cifra oficial no finita como fallo", () => {
  const { datos, valoracion } = datosDePrueba();
  valoracion.escenarios.base.valor_por_accion = NaN;
  const fallos = Simulador.autoverificar(datos, valoracion);
  assert.equal(fallos.length, 1);
  assert.equal(fallos[0].escenario, "base");
});

test("recalcular con valor por accion no positivo da precioFrenteAValor nulo", () => {
  const { datos } = datosDePrueba();
  const datosEndeudados = Object.assign({}, datos,
    { balance: Object.assign({}, datos.balance, { deuda: 5000e9 }) });
  const r = Simulador.recalcular(datosEndeudados, datos.supuestos.escenarios.base,
    datos.supuestos.comun, datos.wacc);
  assert.equal(r.ok, true);
  assert.ok(r.valorPorAccion <= 0, `se esperaba un valor por accion no positivo, dio ${r.valorPorAccion}`);
  assert.equal(r.precioFrenteAValor, null);
});

test("el YAML mezcla el escenario explorado con los oficiales, no con los tres", () => {
  const { datos } = datosDePrueba();
  // 0.2345 no coincide con el margen oficial de ningun escenario: si el
  // codigo escribiera el explorado en el sitio equivocado (o en los tres),
  // esta prueba lo detectaria.
  const explorado = JSON.parse(JSON.stringify(datos.supuestos.escenarios.base));
  explorado.automocion.margen_bruto_final = 0.2345;
  const texto = Simulador.aYaml(datos.supuestos, "base", explorado,
    datos.supuestos.comun, 0.14, 0.14, "2026-10-01");
  assert.match(texto, /version: "2026-10-01"/);
  assert.match(texto, /margen_bruto_final: 0.2345/);
  // El bear y el bull oficiales, palabra por palabra, deben seguir presentes.
  const oficialBear = Simulador.aYaml(datos.supuestos, "bear", datos.supuestos.escenarios.bear,
    datos.supuestos.comun, 0.14, 0.14, "2026-10-01");
  const bloqueBear = oficialBear.split("escenarios:")[1].split("\n\n")[0];
  assert.ok(texto.includes(bloqueBear.trim()), "el bloque bear no coincide con el oficial");
});

test("el YAML escribe los decimales sin notacion exponencial", () => {
  const { datos } = datosDePrueba();
  const explorado = JSON.parse(JSON.stringify(datos.supuestos.escenarios.base));
  explorado.automocion.ajuste_wacc = 1e-7;
  const texto = Simulador.aYaml(datos.supuestos, "base", explorado,
    datos.supuestos.comun, 0.14, 0.14, "2026-10-01");
  assert.match(texto, /ajuste_wacc: 0.0000001/);
  assert.doesNotMatch(texto, /[0-9]e-[0-9]/);
});

test("aYaml lanza si el escenario no existe", () => {
  const { datos } = datosDePrueba();
  assert.throws(() => Simulador.aYaml(datos.supuestos, "avanzado",
    datos.supuestos.escenarios.base, datos.supuestos.comun, 0.14, 0.14, "2026-10-01"),
    /no existe/);
});

test("aYaml lanza si el roic terminal no supera al crecimiento terminal", () => {
  const { datos } = datosDePrueba();
  const comunRoto = Object.assign({}, datos.supuestos.comun,
    { roic_terminal: 0.01, crecimiento_terminal: 0.03 });
  assert.throws(() => Simulador.aYaml(datos.supuestos, "base",
    datos.supuestos.escenarios.base, comunRoto, 0.14, 0.14, "2026-10-01"),
    /roic_terminal debe superar/);
});

test("aYaml avisa si el WACC explorado difiere del oficial", () => {
  const { datos } = datosDePrueba();
  const texto = Simulador.aYaml(datos.supuestos, "base", datos.supuestos.escenarios.base,
    datos.supuestos.comun, 0.16, 0.14, "2026-10-01");
  assert.match(texto, /ATENCION: WACC explorado 16\.00 % frente al oficial 14\.00 %/);
});

test("aYaml no avisa si el WACC explorado coincide con el oficial", () => {
  const { datos } = datosDePrueba();
  const texto = Simulador.aYaml(datos.supuestos, "base", datos.supuestos.escenarios.base,
    datos.supuestos.comun, 0.14, 0.14, "2026-10-01");
  assert.doesNotMatch(texto, /ATENCION/);
});

test("aYaml dice que no hay cambios cuando el escenario y el comun coinciden con los oficiales", () => {
  const { datos } = datosDePrueba();
  const texto = Simulador.aYaml(datos.supuestos, "base", datos.supuestos.escenarios.base,
    datos.supuestos.comun, 0.14, 0.14, "2026-10-01");
  assert.match(texto, /# Sin cambios respecto a la version 2026-09-23\./);
});

test("aYaml lista en la cabecera los campos cambiados respecto a la version oficial", () => {
  const { datos } = datosDePrueba();
  const explorado = JSON.parse(JSON.stringify(datos.supuestos.escenarios.base));
  explorado.automocion.margen_bruto_final = 0.2345;
  const comunExplorado = Object.assign({}, datos.supuestos.comun, { tipo_impositivo: 0.25 });
  const texto = Simulador.aYaml(datos.supuestos, "base", explorado, comunExplorado,
    0.14, 0.14, "2026-10-01");
  assert.match(texto, /comun\.tipo_impositivo: 0\.21 -> 0\.25 \(afecta a los tres escenarios\)/);
  assert.match(texto, /base\.automocion\.margen_bruto_final: 0\.19 -> 0\.2345/);
});

test("las piezas del descuento suman exactamente el valor de cada unidad", () => {
  const { datos } = datosDePrueba();
  const u = Motor.proyectar(datos.base, datos.supuestos.escenarios.base, datos.supuestos.comun, datos.wacc);
  for (const nombre of ["automocion", "energia"]) {
    const p = u[nombre];
    assert.equal(p.vpFlujos + p.vpTerminal, p.valor);
    assert.equal(Motor.sumaPython(p.descontados), p.vpFlujos);
    assert.equal(p.descontados.length, datos.supuestos.comun.horizonte_anios);
    assert.equal(p.tasa, datos.wacc + datos.supuestos.escenarios.base[nombre].ajuste_wacc);
    assert.equal(p.vpTerminal, p.terminal / Math.pow(1 + p.tasa, 10));
  }
});

test("FCF del año base calculado a mano", () => {
  const base = { ingresos: { automocion: 100, energia: 20 },
    margen_bruto: { automocion: 0.2, energia: 0.3 }, id_sobre_ingresos: 0.05, sga_sobre_ingresos: 0.04 };
  const escenario = { automocion: { ventas_sobre_capital: 2 }, energia: { ventas_sobre_capital: 4 } };
  const comun = { tipo_impositivo: 0.25, reparto_id_automocion: 0.8 };
  const r = Motor.fcfAnioBase(base, { automocion: 90, energia: 15 }, escenario, comun);
  // automocion: EBIT 20 - 4,8 - 4 = 11,2; NOPAT 8,4; reinversion 10/2 = 5
  // energia: EBIT 6 - 1,2 - 0,8 = 4; NOPAT 3; reinversion 5/4 = 1,25
  const cerca = (a, b) => assert.ok(Math.abs(a - b) < 1e-12, `${a} != ${b}`);
  cerca(r.unidades.automocion.fcf, 3.4);
  cerca(r.unidades.energia.fcf, 1.75);
  cerca(r.nopat, 11.4);
  cerca(r.reinversion, 6.25);
  cerca(r.fcf, 5.15);
});

test("recalcular devuelve el desglose y el FCF del año cero", () => {
  const { datos } = datosDePrueba();
  datos.anio_cero = { hasta: "2026Q2", ocf: 18, capex: 12, fcf_reportado: 6,
    ingresos_previos: { automocion: 80e9, energia: 10e9 } };
  const r = Simulador.recalcular(datos, datos.supuestos.escenarios.base, datos.supuestos.comun, datos.wacc);
  assert.equal(r.desglose.automocion.valor, r.unidades.automocion);
  assert.equal(r.desglose.energia.descontados.length, 10);
  const esperado = Motor.fcfAnioBase(datos.base, datos.anio_cero.ingresos_previos,
    datos.supuestos.escenarios.base, datos.supuestos.comun);
  assert.equal(r.anioCero.fcf, esperado.fcf);
});

test("sin ingresos previos no hay FCF del modelo en el año cero", () => {
  const { datos } = datosDePrueba();
  const r = Simulador.recalcular(datos, datos.supuestos.escenarios.base, datos.supuestos.comun, datos.wacc);
  assert.equal(r.anioCero, null);
});
