// Puente para probar Simulador.aYaml desde Python. Recibe en un JSON los
// argumentos de aYaml (supuestos, nombre, escenario, comun, wacc,
// waccOficial, fecha) y escribe el YAML resultante en stdout, tal cual, para
// que Python lo cargue con yaml.safe_load.
const fs = require("fs");
const path = require("path");
const Simulador = require(path.join(__dirname, "..", "..", "web", "simulador.js"));

const entrada = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
process.stdout.write(Simulador.aYaml(entrada.supuestos, entrada.nombre, entrada.escenario,
  entrada.comun, entrada.wacc, entrada.waccOficial, entrada.fecha));
