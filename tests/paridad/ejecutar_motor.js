// Ejecuta web/motor.js sobre los casos que genera la prueba de Python.
// Un caso que lanza devuelve {error}; un resultado no finito tumba el script,
// porque el motor nunca debe devolverlo en silencio.
const fs = require("fs");
const path = require("path");
const Motor = require(path.join(__dirname, "..", "..", "web", "motor.js"));

function exigirFinito(indice, nombre, x) {
  if (!Number.isFinite(x)) {
    throw new Error(`caso ${indice}: ${nombre} no es finito (${x})`);
  }
}

const casos = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const salida = casos.map((c, i) => {
  let r;
  try {
    const unidades = Motor.proyectar(c.base, c.escenario, c.comun, c.wacc);
    r = {
      valor_por_accion: Motor.valorPorAccion(Motor.sumaUnidades(unidades), c.balance),
      unidades: { automocion: unidades.automocion.valor, energia: unidades.energia.valor },
      crecimiento_implicito: Motor.crecimientoImplicito(
        c.precio, c.base, c.escenario, c.comun, c.wacc, c.balance),
    };
  } catch (e) {
    return { error: e.message };
  }
  exigirFinito(i, "valor_por_accion", r.valor_por_accion);
  exigirFinito(i, "unidad automocion", r.unidades.automocion);
  exigirFinito(i, "unidad energia", r.unidades.energia);
  if (r.crecimiento_implicito !== null) {
    exigirFinito(i, "crecimiento_implicito", r.crecimiento_implicito);
  }
  return r;
});
process.stdout.write(JSON.stringify(salida));
