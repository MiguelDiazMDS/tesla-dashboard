// Prueba de humo de la pagina: ejecuta motor.js, simulador.js y app.js con un
// DOM minimo y un Chart simulado, sobre los datos de un datos_dashboard.json
// (HUMO_DATOS; por defecto dist/datos_dashboard.json). Comprueba que no hay
// errores con hitos, con hitos a null y sin la libreria de graficos.
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const RAIZ = path.join(__dirname, "..", "..");
const WEB = path.join(RAIZ, "web");
const RUTA_DATOS = process.env.HUMO_DATOS || path.join(RAIZ, "dist", "datos_dashboard.json");
const PLANTILLA = fs.readFileSync(path.join(WEB, "plantilla.html"), "utf8");
const PIEZAS = ["motor.js", "simulador.js", "app.js"].map((f) => fs.readFileSync(path.join(WEB, f), "utf8"));
const VALORES = { "sel-multiplo": "ev_ventas", "sim-desglose-unidad": "total", "sim-escenario": "base" };

class Nodo {
  constructor(tag, id) {
    this.tagName = tag; this.id = id || ""; this.className = ""; this._texto = ""; this.children = [];
    this.style = { setProperty() {} }; this.dataset = {}; this.hidden = false; this.attrs = {};
    this.value = VALORES[id] || ""; this._html = ""; this.parent = null;
    this.classList = { add: (c) => { this.className += " " + c; } };
  }
  set textContent(t) { this._texto = String(t); this.children = []; }
  get textContent() {
    return this._texto + this.children.map((c) => (typeof c === "string" ? c : c.textContent)).join("");
  }
  set innerHTML(h) { this._html = String(h); this.children = []; }
  get innerHTML() { return this._html; }
  append(...xs) { for (const x of xs) { if (x && typeof x === "object") x.parent = this; this.children.push(x); } }
  appendChild(x) { this.append(x); return x; }
  replaceChildren(...xs) { this.children = []; this._texto = ""; this.append(...xs); }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  getAttribute(k) { return this.attrs[k]; }
  removeAttribute(k) { delete this.attrs[k]; }
  addEventListener() {}
  querySelector() { return new Nodo("input"); }
  closest(selector) {
    const clases = selector.split(",").map((s) => s.trim().replace(/^\./, ""));
    for (let e = this; e; e = e.parent) {
      if (clases.some((c) => (" " + e.className + " ").includes(" " + c + " "))) return e;
    }
    return null;
  }
  getBoundingClientRect() { return { height: 50 }; }
  focus() {}
  select() {}
  set href(v) { this.attrs.href = v; }
  get href() { return this.attrs.href; }
  set target(v) { this.attrs.target = v; }
  get target() { return this.attrs.target; }
  set rel(v) { this.attrs.rel = v; }
  get rel() { return this.attrs.rel; }
  set title(v) { this.attrs.title = v; }
  get title() { return this.attrs.title; }
}

function recorrer(raiz, visitar) {
  const pila = [raiz];
  while (pila.length) {
    const e = pila.pop();
    if (e && typeof e === "object") { visitar(e); pila.push(...e.children); }
  }
}

// Ejecuta la pagina y devuelve el DOM, los graficos creados y los errores.
function ejecutarPagina(datos, { conChart = true } = {}) {
  const porId = {};
  for (const [, id] of PLANTILLA.matchAll(/id="([^"]+)"/g)) porId[id] = new Nodo("div", id);
  porId.datos = new Nodo("script", "datos");
  porId.datos._texto = JSON.stringify(datos);
  const buscar = (id) => {
    let hallado = null;
    for (const raiz of Object.values(porId)) {
      recorrer(raiz, (e) => { if (!hallado && e.id === id) hallado = e; });
      if (hallado) break;
    }
    return hallado;
  };
  const document = {
    getElementById: (id) => porId[id] || buscar(id),
    createElement: (t) => new Nodo(t),
    createTextNode: (t) => String(t),
    querySelector: () => null,
    querySelectorAll: () => [],
    documentElement: { style: { setProperty() {} } },
  };
  const graficos = {};
  const errores = [];
  class Chart {
    constructor(lienzo, cfg) {
      graficos[lienzo.id] = cfg;
      // Ejercita los callbacks de ejes y tooltips, que solo se llaman al dibujar.
      for (const eje of Object.values(cfg.options.scales || {})) {
        if (eje.ticks && eje.ticks.callback) [0, 1, 2, 2020, 2020.5].forEach((v, i) => eje.ticks.callback(v, i));
      }
      const tt = cfg.options.plugins && cfg.options.plugins.tooltip && cfg.options.plugins.tooltip.callbacks;
      if (tt) {
        cfg.data.datasets.forEach((ds) => ds.data.forEach((raw, i) => {
          const c = { dataset: ds, raw, dataIndex: i };
          if (tt.label) tt.label(c);
          if (tt.title) tt.title([c]);
        }));
      }
    }
    destroy() {}
    update() {}
  }
  Chart.defaults = { font: {}, plugins: { tooltip: {} } };
  const contexto = vm.createContext({
    document, console: { log() {}, error: (e) => errores.push(e) },
    getComputedStyle: () => ({ getPropertyValue: () => "#808080" }),
    Intl, navigator: {}, Chart: conChart ? Chart : undefined,
  });
  contexto.window = contexto;
  for (const pieza of PIEZAS) vm.runInContext(pieza, contexto);
  return { porId, graficos, errores };
}

const DATOS = JSON.parse(fs.readFileSync(RUTA_DATOS, "utf8"));
const mensajes = (errores) => errores.map((e) => (e && e.stack) || String(e)).join("\n");

test("la pagina se pinta sin errores con hitos", () => {
  assert.ok(DATOS.hitos, "los datos de prueba deben traer hitos");
  const { porId, graficos, errores } = ejecutarPagina(DATOS);
  assert.equal(errores.length, 0, mensajes(errores));
  const tarjetas = porId["hitos-tarjetas"].children;
  assert.equal(tarjetas.length, DATOS.hitos.hitos.length);
  for (const id of ["g-hito-fsd", "g-hito-automovil", "g-hito-energia", "g-historial"]) {
    assert.ok(graficos[id], `falta el grafico ${id}`);
  }
  // Los enlaces abren en otra pestana sin acceso a la ventana de origen.
  let enlaces = 0;
  const bloques = ["hitos-resumen", "hitos-tarjetas", "hitos-transversal"].map((id) => porId[id]);
  bloques.forEach((b) => recorrer(b, (e) => {
    if (e.tagName === "a") {
      enlaces += 1;
      assert.match(e.href, /^https:\/\//);
      assert.equal(e.target, "_blank");
      assert.equal(e.rel, "noopener");
    }
  }));
  assert.ok(enlaces > 0);
  assert.match(porId["t-historial"].innerHTML, /rel="noopener"/);
  assert.doesNotMatch(porId["t-historial"].innerHTML, /<\/a><a /, "los enlaces de fuentes van separados");
  // Una linea por grupo de promesas en cada tarjeta, y marcas con texto accesible.
  tarjetas.forEach((tarjeta, i) => {
    let grupos = 0;
    recorrer(tarjeta, (e) => {
      if (e.className === "grupo-promesa") grupos += 1;
      if (/\bmarca\b/.test(e.className)) assert.ok(e.attrs["aria-label"], "marca sin aria-label");
    });
    assert.equal(grupos, DATOS.hitos.hitos[i].grupos_promesas.length, DATOS.hitos.hitos[i].id);
  });
  // Una barra por grupo en el indice y por entrada del historial con promesas.
  const barras = DATOS.hitos.hitos.flatMap((h) => h.grupos_promesas).filter((g) => g.barra).length +
    DATOS.hitos.historial.filter((h) => h.barra).length;
  assert.equal(graficos["g-historial"].data.datasets[0].data.length, barras);
});

test("sin hitos la seccion lo dice y no pinta nada mas", () => {
  const { porId, graficos, errores } = ejecutarPagina({ ...DATOS, hitos: null });
  assert.equal(errores.length, 0, mensajes(errores));
  assert.equal(porId["n-hitos-version"].textContent, "Todavía no hay hitos documentados.");
  for (const id of ["hitos-resumen", "hitos-tarjetas", "hitos-transversal", "hitos-historial"]) {
    assert.equal(porId[id].hidden, true, id);
  }
  assert.equal(graficos["g-historial"], undefined);
});

test("sin la libreria de graficos la pagina no falla", () => {
  const { porId, graficos, errores } = ejecutarPagina(DATOS, { conChart: false });
  assert.equal(errores.length, 0, mensajes(errores));
  assert.deepEqual(Object.keys(graficos), []);
  assert.equal(porId["hitos-tarjetas"].children.length, DATOS.hitos.hitos.length);
});
