/* global Chart, Motor, Simulador */
// Presentacion del cuadro de mando. Las cifras oficiales vienen incrustadas
// desde Python; este fichero solo las muestra y conduce el simulador.
(function () {
  "use strict";

  const DATOS = JSON.parse(document.getElementById("datos").textContent);
  const V = DATOS.valoracion;
  const T = DATOS.trimestral;
  const M = DATOS.mensual;
  const periodos = T.map((f) => f.period);

  // ---------- Formato ----------
  const cache = {};
  const nf = (d) => cache[d] || (cache[d] = new Intl.NumberFormat("es-ES",
    { minimumFractionDigits: d, maximumFractionDigits: d, useGrouping: "always" }));
  const vacio = (x) => x === null || x === undefined || Number.isNaN(x);
  const f = {
    num: (x, d = 0) => (vacio(x) ? "—" : nf(d).format(x)),
    usd: (x, d = 2) => (vacio(x) ? "—" : nf(d).format(x) + " USD"),
    milM: (x, d = 0) => (vacio(x) ? "—" : nf(d).format(x / 1e9) + " mil M USD"),
    pct: (x, d = 1) => (vacio(x) ? "—" : nf(d).format(x * 100) + " %"),
    pctSigno: (x, d = 0) => (vacio(x) ? "—" : (x > 0 ? "+" : "") + nf(d).format(x * 100) + " %"),
    veces: (x, d = 1) => (vacio(x) ? "—" : nf(d).format(x) + "×"),
  };
  // Los textos de los datos se escapan antes de entrar en innerHTML.
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;" })[c]);
  // Eje: 0 decimales si el valor es entero, 1 si tiene uno, 2 en otro caso.
  const casiEntero = (x) => Math.abs(x - Math.round(x)) < 1e-9;
  const ejeAuto = (v) => f.num(v, casiEntero(v) ? 0 : casiEntero(v * 10) ? 1 : 2);
  const poner = (id, texto) => { const el = document.getElementById(id); if (el) el.textContent = texto; };
  // Importe protagonista: la cifra grande y la unidad pequena al lado.
  function ponerImporte(id, cifra, unidad) {
    const el = document.getElementById(id);
    if (!el) return;
    const numero = document.createElement("span");
    numero.textContent = cifra;
    el.replaceChildren(numero);
    if (unidad && cifra !== "—") {
      const u = document.createElement("span");
      u.className = "unidad";
      u.textContent = unidad;
      el.append(" ", u);
    }
  }
  const soloNum = (x, d) => (vacio(x) ? "—" : nf(d).format(x));
  const soloPctSigno = (x, d) => (vacio(x) ? "—" : (x > 0 ? "+" : "") + nf(d).format(x * 100));
  const serie = (campo, escala = 1) => T.map((r) => (vacio(r[campo]) ? null : r[campo] / escala));

  // ---------- Cabecera ----------
  function pintarResumen() {
    const base = V.escenarios.base;
    poner("r-version", `Supuestos ${V.version_supuestos} · doce meses hasta ${V.ttm_hasta} · valorado el ${V.fecha}`);
    ponerImporte("r-precio", soloNum(V.precio, 2), "USD");
    poner("r-mes-precio", V.precio_obtenido ? "Precio del " + V.precio_obtenido : "Mes " + V.mes_precio);
    ponerImporte("r-valor-base", soloNum(base.valor_por_accion, 2), "USD");
    poner("r-bear", f.usd(V.escenarios.bear.valor_por_accion));
    poner("r-bull", f.usd(V.escenarios.bull.valor_por_accion));
    ponerImporte("r-pfv", soloPctSigno(base.precio_frente_a_valor, 0), "%");
    // Rojo si el precio esta por encima del valor; verde si no.
    if (!vacio(base.precio_frente_a_valor)) {
      document.getElementById("r-pfv").classList.add(base.precio_frente_a_valor > 0 ? "alerta" : "bien");
    }
    ponerImporte("r-opcionalidad", soloNum(V.opcionalidad_implicita / 1e9, 0), "mil M USD");
    poner("r-opcionalidad-pct", f.pct(V.opcionalidad_implicita / V.capitalizacion, 0) + " de la capitalización");
    const g = V.crecimiento_implicito;
    if (vacio(g)) poner("r-crecimiento", "No se alcanza");
    else ponerImporte("r-crecimiento", soloNum(g * 100, 1), "%");
    poner("r-crecimiento-nota", vacio(g) ? (V.crecimiento_implicito_motivo || "")
      : `Ingresos anuales durante ${V.horizonte_anios} años, con los márgenes del escenario base`);
    const cc = V.coste_capital;
    poner("n-coste-capital", `WACC ${f.pct(cc.wacc, 2)}: tipo sin riesgo ${f.pct(cc.tipo_sin_riesgo, 2)}, beta ${f.num(cc.beta, 2)}, prima ${f.pct(cc.prima_riesgo, 1)}.`);
    const pares = [...new Set(T.filter((r) => r.etiqueta_volumen).map((r) => `${r.etiqueta_volumen} / ${r.etiqueta_nicho}`))];
    poner("n-etiquetas", "Nombres que usó Tesla en cada época: " + pares.join(" → ") + ".");
  }

  // ---------- Graficos ----------
  // Estilo: la serie protagonista en rojo (linea de 3 px con area degradada
  // del 23 % al 0 %, o barras con el ultimo periodo en rojo) y las
  // comparaciones en gris discontinuo. El resto de series, en grises.
  const token = (nombre) => getComputedStyle(document.documentElement).getPropertyValue(nombre).trim();
  const graficos = [];

  function aplicarTema() {
    Chart.defaults.color = token("--tinta-suave");
    Chart.defaults.borderColor = token("--linea");
    Chart.defaults.font.family = token("--fuente");
    Chart.defaults.font.size = 12;
    Object.assign(Chart.defaults.plugins.tooltip, {
      backgroundColor: token("--superficie-2"), borderColor: token("--linea"), borderWidth: 1,
      titleColor: token("--tinta"), bodyColor: token("--tinta-suave"), padding: 10,
      cornerRadius: 8, boxPadding: 4,
    });
  }

  // Un grafico que falla deja su aviso y no impide dibujar los demas.
  function registrar(id, construir) {
    const lienzo = document.getElementById(id);
    if (!lienzo) return;
    try {
      const entrada = { id, lienzo, construir, grafico: crear(lienzo, construir) };
      graficos.push(entrada);
    } catch (error) {
      avisarFallo(lienzo, error);
    }
  }

  // Chart.js exige un tipo en la raiz aunque cada serie declare el suyo.
  const crear = (lienzo, construir) => new Chart(lienzo, Object.assign({ type: "bar" }, construir()));

  function reconstruir(entrada) {
    entrada.grafico.destroy();
    entrada.grafico = crear(entrada.lienzo, entrada.construir);
  }

  function opciones({ titulo = "", apilado = false, formatoEje = ejeAuto, derecho = null } = {}) {
    const o = {
      responsive: true, maintainAspectRatio: false, animation: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { position: "bottom", labels: { boxWidth: 10, boxHeight: 10, padding: 14 } },
        tooltip: { callbacks: { label: (c) => ` ${c.dataset.label}: ${c.dataset.formato(c.raw)}` } },
      },
      scales: {
        x: { stacked: apilado, grid: { display: false }, border: { display: false },
          ticks: { maxRotation: 0, autoSkipPadding: 16 } },
        y: { stacked: apilado, title: { display: !!titulo, text: titulo }, border: { display: false },
          ticks: { callback: (v) => formatoEje(v) }, grid: { color: token("--linea") } },
      },
    };
    if (derecho) {
      o.scales.y1 = { position: "right", grid: { display: false }, border: { display: false },
        title: { display: true, text: derecho.titulo }, ticks: { callback: (v) => derecho.formato(v) } };
    }
    return o;
  }

  // "#e31937" y 0.23 -> "rgba(227, 25, 55, 0.23)"
  function conOpacidad(hex, alfa) {
    const h = hex.replace("#", "");
    const n = parseInt(h.length === 3 ? h.split("").map((x) => x + x).join("") : h, 16);
    return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alfa})`;
  }

  // Relleno vertical del 23 % de opacidad arriba al 0 % abajo.
  const degradado = (hex) => (contexto) => {
    const { ctx, chartArea } = contexto.chart;
    if (!chartArea) return conOpacidad(hex, 0);
    const g = ctx.createLinearGradient(0, chartArea.top, 0, chartArea.bottom);
    g.addColorStop(0, conOpacidad(hex, 0.23));
    g.addColorStop(1, conOpacidad(hex, 0));
    return g;
  };

  const barras = (label, data, color, formato, extra = {}) =>
    Object.assign({ type: "bar", label, data, backgroundColor: color, borderColor: color, formato,
      borderRadius: 3, maxBarThickness: 28 }, extra);
  // Barras de una sola serie: gris, con el ultimo periodo con dato en rojo.
  function barrasDestacadas(label, data, formato, extra = {}) {
    let ultimo = -1;
    data.forEach((v, i) => { if (!vacio(v)) ultimo = i; });
    const colores = data.map((_, i) => (i === ultimo ? token("--acento") : token("--gris-3")));
    return barras(label, data, colores, formato, extra);
  }
  const linea = (label, data, color, formato, extra = {}) =>
    Object.assign({ type: "line", label, data, borderColor: color, backgroundColor: color, formato,
      borderWidth: 2, pointRadius: 0, pointHoverRadius: 4, tension: 0.25, spanGaps: false }, extra);
  // Serie principal: roja, 3 px, con area degradada.
  const principal = (label, data, formato, extra = {}) =>
    linea(label, data, token("--acento"), formato, Object.assign({ borderWidth: 3, fill: "start",
      backgroundColor: degradado(token("--acento")), pointHoverBackgroundColor: token("--acento") }, extra));
  // Comparacion: gris discontinua.
  const comparacion = (label, data, formato, extra = {}) =>
    linea(label, data, token("--gris-2"), formato, Object.assign({ borderDash: [6, 5] }, extra));

  const fmtMilM = (x) => (vacio(x) ? "—" : f.num(x, 1) + " mil M USD");
  const fmtPct = (x) => (vacio(x) ? "—" : f.num(x, 1) + " %");
  const fmtMiles = (x) => (vacio(x) ? "—" : f.num(x, 1) + " mil vehículos");

  function pintarGraficos() {
    const c = (n) => token(n);
    registrar("g-entregas", () => ({ data: { labels: periodos, datasets: [
      barras("Línea de volumen", serie("deliveries_volumen", 1e3), c("--automocion"), fmtMiles, { stack: "e" }),
      barras("Línea de nicho", serie("deliveries_nicho", 1e3), c("--gris-4"), fmtMiles, { stack: "e" }),
      comparacion("Producción, línea de volumen", serie("production_volumen", 1e3), fmtMiles,
        { stack: "pv", borderColor: c("--gris-1"), backgroundColor: c("--gris-1") }),
      comparacion("Producción, línea de nicho", serie("production_nicho", 1e3), fmtMiles, { stack: "pn" }),
    ] }, options: opciones({ titulo: "miles de vehículos", apilado: true }) }));

    registrar("g-inventario", () => ({ data: { labels: periodos, datasets: [
      barras("Días de inventario", serie("days_inventory"), c("--gris-4"), (x) => (vacio(x) ? "—" : f.num(x, 0) + " días")),
      linea("Producción / entregas", serie("ratio_produccion_entregas"), c("--acento"), (x) => (vacio(x) ? "—" : f.num(x, 2)),
        { yAxisID: "y1", borderWidth: 3 }),
    ] }, options: opciones({ titulo: "días", derecho: { titulo: "producción / entregas", formato: (v) => f.num(v, 2) } }) }));

    registrar("g-unitario", () => ({ data: { labels: periodos, datasets: [
      principal("ASP implícito", serie("asp_implicito", 1e3), (x) => (vacio(x) ? "—" : f.num(x, 1) + " mil USD")),
      comparacion("Coste por vehículo", serie("coste_por_vehiculo", 1e3), (x) => (vacio(x) ? "—" : f.num(x, 1) + " mil USD")),
    ] }, options: opciones({ titulo: "miles de USD por vehículo" }) }));

    registrar("g-almacenamiento", () => ({ data: { labels: periodos, datasets: [
      barrasDestacadas("Almacenamiento desplegado", serie("storage_deployed_gwh"), (x) => (vacio(x) ? "—" : f.num(x, 2) + " GWh")),
    ] }, options: opciones({ titulo: "GWh" }) }));

    registrar("g-energia", () => ({ data: { labels: periodos, datasets: [
      barras("Ingresos", serie("revenue_energy_segment", 1e9), c("--gris-4"), fmtMilM),
      linea("Margen bruto", T.map((r) => (vacio(r.margen_energia) ? null : r.margen_energia * 100)), c("--acento"), fmtPct,
        { yAxisID: "y1", borderWidth: 3 }),
    ] }, options: opciones({ titulo: "mil M USD", derecho: { titulo: "%", formato: (v) => ejeAuto(v) + " %" } }) }));

    registrar("g-fsd", () => {
      const filas = T.filter((r) => !vacio(r.fsd_subscriptions));
      return { data: { labels: filas.map((r) => r.period), datasets: [
        barrasDestacadas("Suscripciones activas", filas.map((r) => r.fsd_subscriptions / 1e6), (x) => (vacio(x) ? "—" : f.num(x, 2) + " millones")),
      ] }, options: opciones({ titulo: "millones" }) };
    });

    registrar("g-diferidos", () => ({ data: { labels: periodos, datasets: [
      barras("Corriente", serie("deferred_revenue_current", 1e9), c("--acento"), fmtMilM, { stack: "d" }),
      barras("No corriente", serie("deferred_revenue_noncurrent", 1e9), c("--gris-4"), fmtMilM, { stack: "d" }),
    ] }, options: opciones({ titulo: "mil M USD", apilado: true }) }));

    const lineasProducto = [
      ["revenue_auto_sales", "Venta de vehículos", "--acento"],
      ["revenue_reg_credits", "Créditos regulatorios", "--gris-1"],
      ["revenue_auto_leasing", "Leasing de automoción", "--gris-2"],
      ["revenue_services", "Servicios y otros", "--gris-3"],
      ["revenue_energy_sales", "Venta de energía", "--gris-4"],
      ["revenue_energy_leasing", "Leasing de energía", "--gris-5"],
    ];
    // Sin venta de vehiculos no hay desglose: el trimestre entero queda vacio
    // para que unas barras parciales no parezcan una caida de ingresos.
    const conDesglose = (r) => !vacio(r.revenue_auto_sales);
    registrar("g-lineas", () => ({ data: { labels: periodos, datasets: lineasProducto.map(([campo, nombre, color]) =>
      barras(nombre, T.map((r) => (conDesglose(r) && !vacio(r[campo]) ? r[campo] / 1e9 : null)),
        c(color), fmtMilM, { stack: "l", borderRadius: 0 })) },
      options: opciones({ titulo: "mil M USD", apilado: true }) }));

    registrar("g-regiones", () => ({ data: { labels: periodos, datasets: [
      barras("EE. UU.", serie("revenue_us", 1e9), c("--acento"), fmtMilM, { stack: "r", borderRadius: 0 }),
      barras("China", serie("revenue_china", 1e9), c("--gris-2"), fmtMilM, { stack: "r", borderRadius: 0 }),
      barras("Resto del mundo", serie("revenue_other", 1e9), c("--gris-4"), fmtMilM, { stack: "r", borderRadius: 0 }),
    ] }, options: opciones({ titulo: "mil M USD", apilado: true }) }));

    const pctSerie = (campo) => T.map((r) => (vacio(r[campo]) ? null : r[campo] * 100));
    registrar("g-margenes", () => ({ data: { labels: periodos, datasets: [
      principal("Bruto de automoción sin créditos", pctSerie("margen_auto_sin_creditos"), fmtPct),
      linea("Bruto de energía", pctSerie("margen_energia"), c("--gris-1"), fmtPct),
      comparacion("Operativo", pctSerie("margen_operativo"), fmtPct),
    ] }, options: opciones({ titulo: "%" }) }));

    registrar("g-caja", () => ({ data: { labels: periodos, datasets: [
      barrasDestacadas("Flujo de caja libre", serie("fcf", 1e9), fmtMilM),
      comparacion("Capex", serie("capex", 1e9), fmtMilM),
    ] }, options: opciones({ titulo: "mil M USD" }) }));

    registrar("g-acciones", () => ({ data: { labels: periodos, datasets: [
      principal("Acciones en circulación", serie("shares_outstanding", 1e6), (x) => (vacio(x) ? "—" : f.num(x, 0) + " millones")),
    ] }, options: opciones({ titulo: "millones" }) }));

    const H = DATOS.historico || [];
    const pocos = H.length < 6;
    // Con un solo mes no hay franja que dibujar (hace falta un segundo punto
    // para el area entre bear y bull): bear y bull se marcan como rayas grises.
    const unSoloMes = H.length === 1;
    const puntos = pocos ? { pointRadius: 3, pointHoverRadius: 5 } : {};
    const fmtUsd = (x) => f.usd(x);
    const ordenTooltip = { "Precio": 0, "Valor base": 1, "Bull": 2, "Bear": 3 };
    registrar("g-historico", () => {
      const o = opciones({ titulo: "USD por acción" });
      // La franja bear-bull se explica en la nota: fuera de la leyenda.
      o.plugins.legend.labels.filter = (item) => item.text !== "Bear" && item.text !== "Bull";
      o.plugins.tooltip.itemSort = (a, b) =>
        ordenTooltip[a.dataset.label] - ordenTooltip[b.dataset.label];
      const bear = unSoloMes
        ? { borderWidth: 0, pointRadius: 9, pointStyle: "line", pointBorderWidth: 2, pointBorderColor: c("--gris-2") }
        : { borderWidth: 0, pointRadius: 0 };
      const bull = unSoloMes
        ? { borderWidth: 0, pointRadius: 9, pointStyle: "line", pointBorderWidth: 2, pointBorderColor: c("--gris-2") }
        : { borderWidth: 0, pointRadius: 0, fill: "-1", backgroundColor: conOpacidad(c("--gris-2"), 0.12) };
      return { data: { labels: H.map((h) => h.mes), datasets: [
        linea("Bear", H.map((h) => h.vpa_bear), c("--gris-5"), fmtUsd, bear),
        linea("Bull", H.map((h) => h.vpa_bull), c("--gris-5"), fmtUsd, bull),
        comparacion("Valor base", H.map((h) => h.vpa_base), fmtUsd, puntos),
        principal("Precio", H.map((h) => h.precio), fmtUsd, puntos),
      ] }, options: o };
    });

    registrar("g-sotp", () => {
      const nombres = ["bear", "base", "bull"];
      return { data: { labels: ["Bear", "Base", "Bull"], datasets: [
        barras("Automoción", nombres.map((e) => V.escenarios[e].valor_unidades.automocion / 1e9), c("--automocion"), fmtMilM,
          { stack: "s", borderRadius: 0, maxBarThickness: 64 }),
        barras("Energía", nombres.map((e) => V.escenarios[e].valor_unidades.energia / 1e9), c("--gris-3"), fmtMilM,
          { stack: "s", borderRadius: 0, maxBarThickness: 64 }),
      ] }, options: opciones({ titulo: "mil M USD", apilado: true }) };
    });

    registrar("g-multiplo", () => {
      const clave = document.getElementById("sel-multiplo").value;
      const valores = M.map((m) => (vacio(m[clave]) ? null : m[clave]));
      const mediana = V.multiplos[clave].mediana;
      const fmt = (x) => f.veces(x, 1);
      return { data: { labels: M.map((m) => m.month), datasets: [
        principal("Múltiplo mensual", valores, fmt),
        comparacion("Mediana del periodo", valores.map(() => mediana), fmt),
      ] }, options: opciones() };
    });
    document.getElementById("sel-multiplo").addEventListener("change", () => {
      const entrada = graficos.find((g) => g.id === "g-multiplo");
      if (entrada) reconstruir(entrada);
    });
  }

  const enumerar = (xs) => (xs.length < 2 ? xs.join("")
    : xs.slice(0, -1).join(", ") + " y " + xs[xs.length - 1]);

  // Nota bajo los ingresos por linea, calculada con los datos.
  function pintarNotaLineas() {
    const sinDesglose = T.filter((r) => vacio(r.revenue_auto_sales)).map((r) => r.period);
    const primerLeasing = T.find((r) => !vacio(r.revenue_energy_leasing));
    const partes = [];
    if (sinDesglose.length) partes.push(`Sin desglose por línea en ${enumerar(sinDesglose)}.`);
    if (primerLeasing) partes.push(`El leasing de energía se publica por separado desde ${primerLeasing.period}.`);
    poner("n-lineas", partes.join(" "));
  }

  function pintarNotaHistorico() {
    const H = DATOS.historico || [];
    if (!H.length) { poner("n-historico", "Todavía no hay valoraciones registradas."); return; }
    if (H.length === 1) {
      poner("n-historico", `La serie empieza en ${H[0].mes}; se añade un punto con cada ` +
        "actualización mensual. Las marcas grises son los valores bear y bull; con más " +
        "meses forman una franja.");
      return;
    }
    const franja = "La franja gris va del valor bear al bull.";
    poner("n-historico", H.length < 6
      ? `La serie empieza en ${H[0].mes}; se añade un punto con cada actualización mensual. ${franja}`
      : franja);
  }

  function sinGraficos() {
    document.querySelectorAll(".lienzo").forEach((l) => {
      const aviso = document.createElement("div");
      aviso.className = "sin-grafico";
      aviso.textContent = "No se ha podido cargar la librería de gráficos.";
      l.appendChild(aviso);
    });
  }

  // ---------- Tablas ----------
  function pintarRejilla() {
    const r = V.rejilla;
    const maximo = Math.max(V.precio, ...r.valor_por_accion.flat().filter((v) => !vacio(v)));
    let alguna = false;
    let html = "<thead><tr><th scope=\"col\">Crecimiento anual \\ margen de automoción</th>" +
      r.margenes_automocion.map((m) => `<th scope="col">${esc(f.pct(m, 0))}</th>`).join("") + "</tr></thead><tbody>";
    r.crecimientos.forEach((g, i) => {
      html += `<tr><th scope="row">${esc(f.pct(g, 0))}</th>`;
      r.valor_por_accion[i].forEach((v) => {
        if (vacio(v)) {
          html += "<td style=\"--i:0%\">—</td>";
          return;
        }
        const alcanza = v >= V.precio;
        alguna = alguna || alcanza;
        const intensidad = Math.max(0, Math.min(1, v / maximo)) * 45;
        html += `<td class="${alcanza ? "alcanza" : ""}" style="--i:${intensidad.toFixed(1)}%">${esc(f.num(v, 0))}</td>`;
      });
      html += "</tr>";
    });
    document.getElementById("t-rejilla").innerHTML = html + "</tbody>";
    poner("n-rejilla", "Valor por acción en USD con los demás supuestos del escenario base. " + (alguna
      ? `Recuadradas, las combinaciones que alcanzan el precio (${f.usd(V.precio)}).`
      : `Ninguna combinación alcanza el precio (${f.usd(V.precio)}).`));
  }

  function pintarMultiplos() {
    const nombres = { ev_ventas: "EV/Ventas", per: "PER", ev_ebitda: "EV/EBITDA", p_fcf: "P/FCF" };
    let html = "<thead><tr><th scope=\"col\">Múltiplo</th><th scope=\"col\">Actual</th><th scope=\"col\">Mediana del periodo</th><th scope=\"col\">Percentil</th></tr></thead><tbody>";
    for (const [clave, nombre] of Object.entries(nombres)) {
      const m = V.multiplos[clave];
      html += `<tr><td>${esc(nombre)}</td><td>${esc(f.veces(m.actual))}</td><td>${esc(f.veces(m.mediana))}</td><td>${vacio(m.percentil) ? "—" : esc(f.num(m.percentil * 100, 0))}</td></tr>`;
    }
    document.getElementById("t-multiplos").innerHTML = html + "</tbody>";
  }

  // "+2%" -> "WACC +2 p. p."; "+0%" es el oficial.
  function nombreDeltaWacc(delta) {
    const m = /^([+-])(\d+(?:[.,]\d+)?)%$/.exec(delta);
    if (!m) return "WACC " + delta;
    if (Number(m[2].replace(",", ".")) === 0) return "WACC oficial";
    return `WACC ${m[1] === "-" ? "\u2212" : "+"}${m[2].replace(".", ",")} p. p.`;
  }

  function pintarSensibilidad() {
    const s = V.sensibilidad;
    let html = "<thead><tr><th scope=\"col\">Supuesto</th><th scope=\"col\">Valor por acción o de la unidad</th></tr></thead><tbody>";
    for (const [delta, valor] of Object.entries(s.wacc)) {
      html += `<tr><td>${esc(nombreDeltaWacc(delta))}</td><td>${esc(f.usd(valor))}</td></tr>`;
    }
    for (const [reparto, v] of Object.entries(s.reparto_id_automocion)) {
      html += `<tr><td>I+D ${esc(reparto.replace("%", " %"))} a automoción</td><td>automoción ${esc(f.milM(v.automocion))} · energía ${esc(f.milM(v.energia))}</td></tr>`;
    }
    document.getElementById("t-sensibilidad").innerHTML = html + "</tbody>";
  }

  function pintarRetorno() {
    const nombres = { desde_2019: "Desde 2019", ultimos_12_meses: "Últimos 12 meses", en_el_anio: "En lo que va de año" };
    let html = "<thead><tr><th scope=\"col\">Periodo</th><th scope=\"col\">En USD</th><th scope=\"col\">En EUR</th><th scope=\"col\">Efecto divisa</th></tr></thead><tbody>";
    for (const [clave, nombre] of Object.entries(nombres)) {
      const r = DATOS.retorno_eur[clave];
      html += r ? `<tr><td>${esc(nombre)} (${esc(r.desde)} a ${esc(r.hasta)})</td><td>${esc(f.pctSigno(r.usd, 1))}</td><td>${esc(f.pctSigno(r.eur, 1))}</td><td>${esc(f.pctSigno(r.efecto_divisa, 1))}</td></tr>`
        : `<tr><td>${esc(nombre)}</td><td colspan="3">Sin datos del mes inicial</td></tr>`;
    }
    document.getElementById("t-retorno").innerHTML = html + "</tbody>";
  }

  function pintarFuentes() {
    const titulos = { R: "Reportado", D: "Derivado", E: "Estimado" };
    let html = "<thead><tr><th scope=\"col\" class=\"texto\">Dato</th><th scope=\"col\" class=\"texto\">Tipo</th><th scope=\"col\" class=\"texto\">Fuente</th><th scope=\"col\">Último periodo</th><th scope=\"col\">Obtenido</th></tr></thead><tbody>";
    for (const k of DATOS.trazabilidad) {
      html += `<tr><td class="texto">${esc(k.kpi)}</td><td class="texto"><span class="etiqueta" title="${esc(titulos[k.etiqueta] || "")}">${esc(k.etiqueta)}</span></td><td class="texto">${esc(k.fuente)}</td><td>${esc(k.ultimo_periodo || "—")}</td><td>${esc(k.obtenido || "—")}</td></tr>`;
    }
    document.getElementById("t-fuentes").innerHTML = html + "</tbody>";
  }

  // ---------- Simulador ----------
  const CAMPOS_UNIDAD = [
    ["crecimiento_inicial", "Crecimiento del primer año", -0.2, 0.8, "pct"],
    ["crecimiento_final", "Crecimiento del último año", -0.05, 0.2, "pct"],
    ["margen_bruto_final", "Margen bruto final", 0.05, 0.5, "pct"],
    ["ventas_sobre_capital", "Ventas sobre capital", 0.5, 6, "num"],
    ["ajuste_wacc", "Ajuste sobre el WACC", -0.03, 0.05, "pct"],
  ];
  const CAMPOS_GASTOS = [
    ["id_sobre_ingresos_final", "I+D final sobre ingresos", 0.01, 0.15, "pct"],
    ["sga_sobre_ingresos_final", "SG&A final sobre ingresos", 0.01, 0.15, "pct"],
  ];
  const CAMPOS_COMUN = [
    ["tipo_impositivo", "Tipo impositivo", 0.05, 0.35, "pct"],
    ["crecimiento_terminal", "Crecimiento terminal", 0, 0.05, "pct"],
    ["roic_terminal", "ROIC terminal", 0.03, 0.5, "pct"],
    ["reparto_id_automocion", "I+D asignada a automoción", 0, 1, "pct"],
  ];
  const sim = { nombre: "base", escenario: null, comun: null, wacc: null };
  const controles = [];

  function control(contenedor, id, etiqueta, min, max, tipo, leer, escribir) {
    const fila = document.createElement("div");
    fila.className = "control";
    fila.innerHTML = `<label for="${esc(id)}">${esc(etiqueta)}</label><output id="${esc(id)}-v" for="${esc(id)}"></output>` +
      `<input type="range" id="${esc(id)}" min="${min}" max="${max}" step="any">`;
    document.getElementById(contenedor).appendChild(fila);
    const input = fila.querySelector("input");
    const salida = fila.querySelector("output");
    const mostrar = () => { salida.textContent = tipo === "pct" ? f.pct(leer(), 2) : f.num(leer(), 2); };
    input.addEventListener("input", () => {
      const decimales = tipo === "pct" ? 4 : 2;
      const factor = Math.pow(10, decimales);
      escribir(Math.round(parseFloat(input.value) * factor) / factor);
      mostrar();
      recalcular();
    });
    controles.push(() => { input.value = String(leer()); mostrar(); });
  }

  function construirControles() {
    for (const unidad of ["automocion", "energia"]) {
      for (const [campo, etiqueta, min, max, tipo] of CAMPOS_UNIDAD) {
        control("sim-" + unidad, `sim-${unidad}-${campo}`, etiqueta, min, max, tipo,
          () => sim.escenario[unidad][campo], (v) => { sim.escenario[unidad][campo] = v; });
      }
    }
    for (const [campo, etiqueta, min, max, tipo] of CAMPOS_GASTOS) {
      control("sim-gastos", "sim-" + campo, etiqueta, min, max, tipo,
        () => sim.escenario[campo], (v) => { sim.escenario[campo] = v; });
    }
    for (const [campo, etiqueta, min, max, tipo] of CAMPOS_COMUN) {
      control("sim-comun", "sim-" + campo, etiqueta, min, max, tipo,
        () => sim.comun[campo], (v) => { sim.comun[campo] = v; });
    }
    control("sim-comun", "sim-wacc", "WACC", 0.05, 0.25, "pct",
      () => sim.wacc, (v) => { sim.wacc = v; });
  }

  function cargarEscenario(nombre) {
    const s = DATOS.simulador;
    sim.nombre = nombre;
    sim.escenario = Simulador.copia(s.supuestos.escenarios[nombre]);
    sim.comun = Simulador.copia(s.supuestos.comun);
    sim.wacc = s.wacc;
    controles.forEach((sincronizar) => sincronizar());
    recalcular();
  }

  function recalcular() {
    const r = Simulador.recalcular(DATOS.simulador, sim.escenario, sim.comun, sim.wacc);
    const cifras = document.getElementById("sim-cifras");
    const motivo = document.getElementById("sim-motivo");
    const explicacion = document.getElementById("sim-explicacion");
    // Sin calculo valido no se exportan supuestos.
    document.getElementById("sim-copiar").disabled = !r.ok;
    if (!r.ok) {
      cifras.hidden = true;
      explicacion.hidden = true;
      motivo.hidden = false;
      motivo.textContent = "Estos supuestos no se pueden calcular: " + r.motivo + ".";
      return;
    }
    cifras.hidden = false;
    explicacion.hidden = false;
    motivo.hidden = true;
    ultimoResultado = r;
    seguro("sim-explicacion", () => pintarDesglose(r));
    const oficial = V.escenarios[sim.nombre].valor_por_accion;
    ponerImporte("sim-vpa", soloNum(r.valorPorAccion, 2), "USD");
    poner("sim-dif", `${f.pctSigno(r.valorPorAccion / oficial - 1, 1)} frente al valor oficial del escenario ${sim.nombre} (${f.usd(oficial)})`);
    poner("sim-pfv", f.pctSigno(r.precioFrenteAValor));
    poner("sim-opcionalidad", f.milM(r.opcionalidad));
    poner("sim-v-auto", f.milM(r.unidades.automocion));
    poner("sim-v-energia", f.milM(r.unidades.energia));
    poner("sim-g", vacio(r.crecimientoImplicito) ? "No se alcanza el precio" : f.pct(r.crecimientoImplicito));
  }

  // ---------- Desglose del descuento de flujos ----------
  let ultimoResultado = null;
  let graficoDesglose = null;
  const NOMBRE_UNIDAD = { automocion: "automoción", energia: "energía" };
  const milM1 = (x) => (vacio(x) ? "—" : f.num(x / 1e9, 1) + " mil M USD");
  const pct2 = (x) => f.pct(x, 2);

  // Suma, año a año, las series de las unidades elegidas.
  function sumarUnidades(desglose, unidades) {
    const n = desglose[unidades[0]].fcff.length;
    const serie = (k) => Array.from({ length: n }, (_, t) =>
      unidades.reduce((s, u) => s + desglose[u][k][t], 0));
    const total = (k) => unidades.reduce((s, u) => s + desglose[u][k], 0);
    return { n, fcff: serie("fcff"), descontados: serie("descontados"), vpFlujos: total("vpFlujos"),
      nopatTerminal: total("nopatTerminal"), terminal: total("terminal"),
      vpTerminal: total("vpTerminal"), valor: total("valor") };
  }

  function paso(lista, numero, texto, valor, clases = "") {
    const li = document.createElement("li");
    if (clases) li.className = clases;
    const num = document.createElement("span");
    num.className = "paso-num";
    num.textContent = numero;
    const t = document.createElement("span");
    t.className = "paso-texto";
    // El texto admite un tramo en negrita marcado con **...**, sin HTML.
    texto.split("**").forEach((trozo, i) => {
      if (!trozo) return;
      const nodo = i % 2 ? document.createElement("strong") : document.createTextNode(trozo);
      if (i % 2) nodo.textContent = trozo;
      t.appendChild(nodo);
    });
    const v = document.createElement("span");
    v.className = "paso-valor";
    v.textContent = valor;
    li.append(num, t, v);
    lista.appendChild(li);
  }

  function pintarGraficoDesglose(d) {
    if (typeof Chart === "undefined") return;
    const etiquetas = Array.from({ length: d.n }, (_, i) => `Año ${i + 1}`);
    const nominal = d.fcff.map((x) => x / 1e9);
    const presente = d.descontados.map((x) => x / 1e9);
    if (graficoDesglose) {
      graficoDesglose.data.labels = etiquetas;
      graficoDesglose.data.datasets[0].data = nominal;
      graficoDesglose.data.datasets[1].data = presente;
      graficoDesglose.update("none");
      return;
    }
    aplicarTema();
    graficoDesglose = crear(document.getElementById("g-desglose"), () => ({
      data: { labels: etiquetas, datasets: [
        barras("Flujo libre", nominal, token("--gris-3"), fmtMilM),
        barras("Valor presente", presente, token("--acento"), fmtMilM),
      ] },
      options: opciones({ titulo: "mil M USD" }),
    }));
  }

  function pintarDesglose(r) {
    const seleccion = document.getElementById("sim-desglose-unidad").value;
    const unidades = seleccion === "total" ? ["automocion", "energia"] : [seleccion];
    const d = sumarUnidades(r.desglose, unidades);
    const comun = sim.comun;
    const g = comun.crecimiento_terminal;
    const tasas = unidades.map((u) => r.desglose[u].tasa);
    const textoTasa = unidades.length === 1 ? pct2(tasas[0])
      : unidades.map((u, i) => `${NOMBRE_UNIDAD[u]} ${pct2(tasas[i])}`).join(", ");
    const nombre = unidades.length === 1 ? NOMBRE_UNIDAD[unidades[0]] : "las dos unidades";

    pintarGraficoDesglose(d);
    const lista = document.getElementById("sim-pasos");
    lista.replaceChildren();
    const nominal = d.fcff.reduce((s, x) => s + x, 0);
    paso(lista, 1, `**Flujos libres, años 1 a ${d.n}:** ${milM1(nominal)} en total, descontados a ${textoTasa}`,
      milM1(d.vpFlujos));
    const sinCredito = d.nopatTerminal <= 0
      ? " Sin crédito de reinversión porque el NOPAT es negativo." : "";
    paso(lista, 2, `**Valor terminal al final del año ${d.n}:** NOPAT del año ${d.n + 1} ` +
      `(${milM1(d.nopatTerminal)}) × (1 − g ÷ ROIC) ÷ (r − g), con g ${pct2(g)} y ROIC ` +
      `${pct2(comun.roic_terminal)} = ${milM1(d.terminal)}; descontado ${d.n} años.${sinCredito}`,
      milM1(d.vpTerminal));
    const peso = d.valor > 0 ? f.pct(d.vpTerminal / d.valor, 0) : "—";
    paso(lista, 3, `**Valor de ${nombre}** (el valor terminal pesa ${peso})`, milM1(d.valor), "resultado");
    if (unidades.length === 2) {
      const b = DATOS.simulador.balance;
      const acciones = d.valor + b.caja + b.inversiones - b.deuda;
      paso(lista, 4, `**+ caja e inversiones − deuda:** ${milM1(b.caja + b.inversiones)} − ` +
        `${milM1(b.deuda)}`, milM1(acciones));
      paso(lista, 5, `**÷ acciones en circulación** (${f.num(b.acciones / 1e6, 0)} millones)`,
        f.usd(r.valorPorAccion), "resultado final");
    }
    poner("sim-formula", `VP = Σ FCFₜ ÷ (1 + r)ᵗ · VT = NOPAT${sub(d.n + 1)} × (1 − g ÷ ROIC) ÷ (r − g) · ` +
      `VP(VT) = VT ÷ (1 + r)${sup(d.n)}`);
    pintarAnioCero(r);
  }

  const SUB = "₀₁₂₃₄₅₆₇₈₉";
  const SUP = "⁰¹²³⁴⁵⁶⁷⁸⁹";
  const sub = (n) => String(n).split("").map((c) => SUB[c]).join("");
  const sup = (n) => String(n).split("").map((c) => SUP[c]).join("");

  function pintarAnioCero(r) {
    const a = DATOS.simulador.anio_cero || {};
    ponerImporte("sim-fcf-reportado", soloNum(vacio(a.fcf_reportado) ? null : a.fcf_reportado / 1e9, 2),
      "mil M USD");
    poner("sim-fcf-reportado-nota", vacio(a.fcf_reportado) ? "Sin dato"
      : `Flujo operativo ${milM1(a.ocf)} − capex ${milM1(a.capex)}. Doce meses hasta ${a.hasta}.`);
    const m = r.anioCero;
    ponerImporte("sim-fcf-modelo", soloNum(m ? m.fcf / 1e9 : null, 2), "mil M USD");
    poner("sim-fcf-modelo-nota", m
      ? `NOPAT ${milM1(m.nopat)} − reinversión ${milM1(m.reinversion)}. Con los supuestos del simulador.`
      : "Faltan los ingresos de los doce meses anteriores.");
  }

  // Fecha de hoy en hora local (toISOString daria la fecha UTC).
  function hoyLocal() {
    const d = new Date();
    const dos = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${dos(d.getMonth() + 1)}-${dos(d.getDate())}`;
  }

  function copiarYaml() {
    const aviso = document.getElementById("sim-copiado");
    const area = document.getElementById("sim-yaml");
    let texto;
    try {
      texto = Simulador.aYaml(DATOS.simulador.supuestos, sim.nombre, sim.escenario,
        sim.comun, sim.wacc, DATOS.simulador.wacc, hoyLocal());
    } catch (error) {
      area.hidden = true;
      aviso.textContent = "No se puede exportar: " + error.message + ".";
      return;
    }
    Promise.resolve()
      .then(() => navigator.clipboard.writeText(texto))
      .then(() => {
        area.hidden = true;
        aviso.textContent = "Copiado. Pégalo en data/assumptions.yaml y revisa la versión antes de valorar.";
      })
      .catch(() => {
        area.value = texto;
        area.hidden = false;
        area.focus();
        area.select();
        aviso.textContent = "El navegador no permite copiar desde aquí: el texto está seleccionado, cópialo con Ctrl+C.";
      });
  }

  function iniciarSimulador() {
    const caja = document.getElementById("verificacion");
    let fallos;
    try {
      fallos = Simulador.autoverificar(DATOS.simulador, V);
    } catch (error) {
      fallos = [{ escenario: "todos", js: null, python: null, motivo: error.message }];
    }
    if (fallos.length > 0) {
      caja.dataset.estado = "fallo";
      caja.textContent = "El simulador no reproduce el motor oficial (" +
        fallos.map((x) => (x.motivo ? `${x.escenario}: ${x.motivo}`
          : `${x.escenario}: ${f.usd(x.js, 6)} frente a ${f.usd(x.python, 6)}`)).join("; ") +
        "). Simulador desactivado.";
      document.getElementById("sim-controles").setAttribute("inert", "");
      document.getElementById("sim-resultado").hidden = true;
      document.getElementById("sim-explicacion").hidden = true;
      return;
    }
    caja.dataset.estado = "ok";
    caja.textContent = "Simulador verificado: reproduce las tres cifras oficiales del motor de Python.";
    construirControles();
    document.getElementById("sim-escenario").addEventListener("change", (e) => cargarEscenario(e.target.value));
    document.getElementById("sim-desglose-unidad").addEventListener("change", () => {
      if (ultimoResultado) seguro("sim-explicacion", () => pintarDesglose(ultimoResultado));
    });
    document.getElementById("sim-restablecer").addEventListener("click", () => cargarEscenario(sim.nombre));
    document.getElementById("sim-copiar").addEventListener("click", copiarYaml);
    cargarEscenario("base");
  }

  // ---------- Hitos ----------
  // Todo el texto de los datos entra con textContent; los enlaces solo si son https.
  const HI = DATOS.hitos;
  const nodo = (etiqueta, clase, texto) => {
    const n = document.createElement(etiqueta);
    if (clase) n.className = clase;
    if (texto !== undefined && texto !== null) n.textContent = texto;
    return n;
  };
  const esHttps = (url) => typeof url === "string" && /^https:\/\/[^\s/]+\.[^\s/]+/.test(url);
  function enlace(url, texto, titulo) {
    if (!esHttps(url)) return nodo("span", null, texto);
    const a = nodo("a", "enlace-fuente", texto);
    a.href = url;
    a.target = "_blank";
    a.rel = "noopener";
    if (titulo) a.title = titulo;
    return a;
  }
  const etiquetaRE = (e) => {
    const s = nodo("span", "etiqueta", e);
    s.title = e === "E" ? "Evidencia de terceros" : "Reportado por Tesla o un registro oficial";
    return s;
  };
  const meses1 = (x) => (vacio(x) ? "—" : f.num(x, 1) + " meses");
  const plural = (n, uno, varios) => `${n} ${n === 1 ? uno : varios}`;
  const NOMBRE_ESTADO = { "logrado": "Logrado", "en curso": "En curso", "no iniciado": "No iniciado" };
  // Tipos de barra de la linea temporal, calculados en Python (barra.tipo).
  const NOMBRE_TIPO = { cumplido: "Cumplido", adelantado: "Cumplido antes de la primera fecha",
    retrasado: "Retrasado", en_plazo: "En plazo", abandonado: "Abandonado", sin_fecha: "Logrado por métricas, sin fecha" };
  const COLOR_TIPO = { cumplido: "--bien", retrasado: "--acento", en_plazo: "--gris-2", adelantado: "--gris-2",
    abandonado: "--gris-5" };
  // Marca de estado con texto accesible, no solo el simbolo.
  function marcaEstado(clase, simbolo, texto) {
    const m = nodo("span", clase, simbolo);
    m.title = texto;
    m.setAttribute("role", "img");
    m.setAttribute("aria-label", texto);
    return m;
  }

  function cifraHito(contenedor, rotulo, valor, unidad, nota) {
    const c = nodo("div", "cifra");
    const r = nodo("span", "rotulo", rotulo + " ");
    const d = nodo("span", "etiqueta", "D");
    d.title = "Derivado";
    r.append(d);
    const v = nodo("span", "valor");
    v.append(nodo("span", null, valor));
    if (unidad && valor !== "—") v.append(" ", nodo("span", "unidad", unidad));
    c.append(r, v, nodo("span", "nota", nota));
    contenedor.append(c);
  }

  function pintarResumenHitos() {
    const cont = document.getElementById("hitos-resumen");
    cont.replaceChildren();
    const t = HI.indice.todas;
    const o = HI.indice.oficiales;
    const detalle = (clave) => `Mediana ${meses1(t[clave].mediana)} (${plural(t[clave].n, "hito", "hitos")}). ` +
      `Solo promesas oficiales: media ${meses1(o[clave].media)}, mediana ${meses1(o[clave].mediana)} ` +
      `(${plural(o[clave].n, "hito", "hitos")}).`;
    cifraHito(cont, "Deslizamiento realizado", soloNum(t.realizado.media, 1), "meses",
      t.realizado.n ? "Media del retraso de los hitos cumplidos frente a su primera fecha prometida. " + detalle("realizado")
        : "Todavía no hay hitos cumplidos con fecha prometida.");
    cifraHito(cont, "Deslizamiento mínimo acumulado", soloNum(t.minimo.media, 1), "meses",
      t.minimo.n ? "Cumplidos y pendientes vencidos: el retraso final será al menos este. " + detalle("minimo")
        : "Sin hitos cumplidos ni pendientes vencidos.");
    const ph = HI.indice.pct_cumplidos_historial;
    cifraHito(cont, "Historial cumplido", vacio(ph.valor) ? "—" : soloNum(ph.valor * 100, 0), "%",
      ph.total ? `${ph.cumplidos} de ${ph.total} promesas del historial.` : "Todavía no hay promesas en el historial.");
    cifraHito(cont, "Pendientes vencidos", String(t.retrasados), "",
      `Su primera fecha prometida ya pasó. ${t.a_tiempo} en plazo · ${plural(t.abandonados, "abandonado", "abandonados")}.`);
  }

  function bloqueTexto(rotulo, texto) {
    const b = nodo("div", "bloque-hito");
    b.append(nodo("span", "rotulo", rotulo), nodo("p", null, texto));
    return b;
  }

  function bloquePasos(h) {
    const b = nodo("div", "bloque-hito");
    const pasos = h.pasos || [];
    const req = h.requeridos || [];
    const hechos = (lista) => lista.filter((p) => p.cumplido).length;
    b.append(nodo("span", "rotulo", req.length
      ? `Pasos · ${hechos(pasos.filter((p) => req.includes(p.id)))} de ${req.length} requeridos cumplidos`
      : `Pasos · ${hechos(pasos)} de ${pasos.length} cumplidos`));
    const ul = nodo("ul", "pasos-hito");
    for (const p of pasos) {
      const c = p.cumplido;
      const li = nodo("li");
      const marca = marcaEstado("marca" + (c ? " si" : ""), c ? "✓" : "○", c ? "Cumplido" : "Pendiente");
      const texto = nodo("span", null, p.texto);
      if (req.length && !req.includes(p.id)) texto.append(nodo("span", "nota", " · no requerido"));
      const meta = nodo("span", "paso-meta");
      meta.append(etiquetaRE(p.etiqueta));
      if (c) {
        meta.append(nodo("span", null, c.fecha));
        if (!vacio(c.valor)) meta.append(nodo("span", null, "cifra: " + f.num(c.valor, 0)));
        meta.append(enlace(c.enlace, "fuente", c.fuente));
      } else {
        meta.append(nodo("span", null, "Pendiente"));
      }
      li.append(marca, texto, meta);
      if (p.nota) li.append(nodo("p", "paso-nota", p.nota));
      ul.append(li);
    }
    b.append(ul);
    return b;
  }

  // Valor y umbral de una metrica, en texto, segun su unidad.
  function textoMetrica(m) {
    const v = m.valor;
    const u = m.umbral;
    const sinDato = vacio(v);
    switch (m.unidad) {
      case "suscripciones":
        return { valor: sinDato ? "sin dato" : f.num(v / 1e6, 2) + " millones", umbral: `umbral ≥ ${f.num(u / 1e6, 1)} millones` };
      case "trimestres":
        return { valor: sinDato ? "sin dato"
          : `${plural(v, "trimestre seguido", "trimestres seguidos")} al alza (objetivo ${f.num(u, 0)})`, umbral: null };
      case "mercados":
        return { valor: plural(v, "mercado", "mercados"), umbral: `umbral ≥ ${f.num(u, 0)} desde ${HI.fecha_base_mercados}` };
      case "GWh":
        return { valor: sinDato ? "sin dato" : f.num(v, 1) + " GWh", umbral: `umbral ≥ ${f.num(u, 0)} GWh` };
      case "ratio":
        if (m.id === "entregas_12m") {
          return { valor: sinDato ? "sin dato" : f.pctSigno(v, 1), umbral: "umbral: sin caída" };
        }
        return { valor: sinDato ? "sin dato" : "el peor, " + f.pct(v, 1), umbral: `umbral ≥ ${f.pct(u, 0)}` };
      default:
        return { valor: sinDato ? "sin dato" : f.num(v, 2), umbral: vacio(u) ? null : "umbral " + f.num(u, 2) };
    }
  }

  function bloqueMetricas(h) {
    const b = nodo("div", "bloque-hito");
    b.append(nodo("span", "rotulo", "Métricas automáticas"));
    const ul = nodo("ul", "metricas-hito");
    for (const m of h.metricas) {
      const li = nodo("li");
      const marca = marcaEstado("marca" + (m.cumple === true ? " si" : m.cumple === false ? " no" : ""),
        m.cumple === true ? "✓" : m.cumple === false ? "✗" : "–",
        m.cumple === true ? "En umbral" : m.cumple === false ? "Por debajo del umbral" : "Sin dato");
      const t = textoMetrica(m);
      const meta = nodo("span", "paso-meta");
      meta.append(nodo("span", "metrica-valor", t.valor));
      if (t.umbral) meta.append(nodo("span", null, t.umbral));
      li.append(marca, nodo("span", null, m.nombre), meta);
      ul.append(li);
    }
    b.append(ul);
    return b;
  }

  // Minigraficos: la serie ligada a cada hito, en los ultimos doce trimestres.
  const MINI = {
    fsd: { titulo: "Suscripciones activas de FSD", nota: "Barras: millones de suscripciones; discontinua: umbral.",
      aria: "Suscripciones activas de FSD por trimestre y umbral" },
    automovil: { titulo: "Márgenes, doce trimestres", nota: "Rojo: bruto de automoción sin créditos; gris: operativo; discontinuas: umbrales.",
      aria: "Margen bruto de automoción sin créditos y margen operativo por trimestre, con sus umbrales" },
    energia: { titulo: "Almacenamiento y margen, doce trimestres", nota: "Barras: GWh desplegados; línea roja: margen bruto (eje derecho).",
      aria: "GWh desplegados y margen bruto de energía por trimestre" },
  };

  function bloqueMini(h) {
    const cfg = MINI[h.id];
    const b = nodo("div", "bloque-hito");
    const lienzo = nodo("div", "lienzo lienzo-mini");
    const canvas = nodo("canvas");
    canvas.id = "g-hito-" + h.id;
    canvas.setAttribute("role", "img");
    canvas.setAttribute("aria-label", cfg.aria);
    lienzo.append(canvas);
    b.append(nodo("span", "rotulo", cfg.titulo), lienzo, nodo("p", "nota", cfg.nota));
    return b;
  }

  function textoRetraso(d) {
    if (d.tipo === "realizado") {
      return d.meses >= 0 ? `cumplido con ${meses1(d.meses)} de retraso sobre la primera fecha`
        : `cumplido ${meses1(-d.meses)} antes de la primera fecha`;
    }
    if (d.tipo === "minimo") return `retraso de al menos ${meses1(d.meses)} sobre la primera fecha`;
    if (d.tipo === "abandonado") return "abandonado";
    return "dentro de plazo";
  }

  // Una linea por grupo de promesas: las que apuntan a un paso y las del hito completo.
  function grupoPromesas(g) {
    const caja = nodo("div", "grupo-promesa");
    const d = g.deslizamiento;
    const pv = g.promesa_vigente;
    caja.append(nodo("span", "grupo-titulo", g.paso ? g.texto : "El hito completo"));
    const p = nodo("p");
    p.append("Fecha vigente: ", nodo("strong", null, pv.fecha_prometida));
    if (pv.fecha_prometida !== d.vigente) p.append(` (hasta el ${d.vigente})`);
    p.append(`, declarada el ${pv.declarada} por ${pv.fuente_tipo === "musk" ? "Musk" : "Tesla"} · `,
      enlace(pv.enlace, "fuente", pv.fuente));
    caja.append(p);
    if (pv.cita) caja.append(nodo("p", "nota cita", `«${pv.cita}»`));
    const partes = [`${plural(d.re_promesas, "re-promesa", "re-promesas")} desde la primera fecha (${d.primera})`];
    if (d.re_promesas > 0 && !vacio(d.meses_vigente_vs_primera)) {
      partes.push(`la fecha se ha movido ${meses1(d.meses_vigente_vs_primera)}`);
    }
    if (!g.en_indice) {
      partes.push("logrado por métricas; sin fecha de cumplimiento, no entra en el índice");
    } else {
      if (g.cumplimiento) partes.push(`cumplido el ${g.cumplimiento.fecha}`);
      partes.push(textoRetraso(d));
      if (d.tipo === "minimo" && d.vencida_vigente) partes.push("la fecha vigente también ha vencido");
    }
    caja.append(nodo("p", "nota", partes.join("; ") + "."));
    const o = g.deslizamiento_oficial;
    if (g.en_indice && o && o.primera !== d.primera) {
      caja.append(nodo("p", "nota", `Solo promesas oficiales: primera fecha ${o.primera}; ${textoRetraso(o)}.`));
    } else if (g.en_indice && !o) {
      caja.append(nodo("p", "nota", "Ninguna promesa de fuente oficial: no entra en el índice solo oficial."));
    }
    return caja;
  }

  function bloqueGrupos(h) {
    const b = nodo("div", "bloque-hito");
    b.append(nodo("span", "rotulo", "Fechas comprometidas por Tesla"));
    const grupos = h.grupos_promesas || [];
    if (!grupos.length) b.append(nodo("p", "nota", "Sin fechas prometidas documentadas."));
    for (const g of grupos) b.append(grupoPromesas(g));
    return b;
  }

  function tarjetaHito(h) {
    const t = nodo("article", "tarjeta-hito");
    t.id = "hito-" + h.id;
    const cab = nodo("div", "tarjeta-cabecera");
    const h3 = nodo("h3");
    h3.append(nodo("span", "prioridad", String(h.prioridad)), nodo("span", null, h.titulo));
    const chips = nodo("div", "chips");
    chips.append(nodo("span", "chip" + (h.estado === "logrado" ? " chip-logrado" : ""), NOMBRE_ESTADO[h.estado] || h.estado));
    if (h.estancado) chips.append(nodo("span", "chip chip-estancado", "Estancado"));
    cab.append(h3, chips);
    if (h.estancado) {
      const e = h.estancado;
      const p = nodo("p", "nota alerta-texto", `Estancado desde ${e.desde}: ${e.motivo} · `);
      p.append(enlace(e.enlace, "fuente", e.fuente));
      cab.append(p);
    }
    t.append(cab, bloqueTexto("Qué debe ocurrir", h.que_debe_ocurrir),
      bloqueTexto("Qué demostraría", h.que_demostraria));
    if ((h.pasos || []).length) t.append(bloquePasos(h));
    if ((h.metricas || []).length) t.append(bloqueMetricas(h));
    if (MINI[h.id]) t.append(bloqueMini(h));
    t.append(bloqueGrupos(h));
    return t;
  }

  function pintarTarjetasHitos() {
    const cont = document.getElementById("hitos-tarjetas");
    cont.replaceChildren(...HI.hitos.map(tarjetaHito));
  }

  function pintarTransversal() {
    const cont = document.getElementById("hitos-transversal");
    cont.replaceChildren();
    const caja = HI.transversal.caja;
    const bc = nodo("section", "caja");
    bc.append(nodo("h3", null, "Caja"));
    if (!caja) {
      bc.append(nodo("p", "nota", "Sin guía de capex documentada."));
    } else {
      const guia = nodo("p", "nota", `Guía de Tesla para ${caja.anio}: ${caja.texto_guia} (${milM1(caja.guia)}) · `);
      guia.append(enlace(caja.enlace, "fuente", caja.fuente));
      if (caja.completo) {
        const cuota = caja.cuota_guia;
        bc.append(nodo("p", null, `Capex de ${caja.anio} en ${plural(caja.trimestres_anio, "trimestre", "trimestres")}: ` +
          `${milM1(caja.capex_anio)}, ${f.pct(cuota, 0)} de la guía.`));
        const porcentaje = Math.max(0, Math.min(100, (cuota || 0) * 100));
        const barra = nodo("div", "barra-progreso");
        const relleno = nodo("span");
        relleno.style.width = porcentaje.toFixed(1) + "%";
        barra.append(relleno);
        barra.setAttribute("role", "progressbar");
        barra.setAttribute("aria-label", "Capex del año frente a la guía");
        barra.setAttribute("aria-valuemin", "0");
        barra.setAttribute("aria-valuemax", "100");
        barra.setAttribute("aria-valuenow", String(Math.round(porcentaje)));
        bc.append(barra);
        const q = caja.trimestres_restantes;
        bc.append(nodo("p", "nota", caja.capex_restante <= 0 ? "La guía ya está alcanzada."
          : q === 0 ? `El año está cerrado: faltaron ${milM1(caja.capex_restante)} para la guía.`
            : `Faltan ${milM1(caja.capex_restante)} en ${plural(q, "trimestre", "trimestres")} ` +
              `(${milM1(caja.capex_por_trimestre_restante)} por trimestre).`));
      } else {
        bc.append(nodo("p", "nota", `Capex de ${caja.anio} sin dato completo: ${caja.motivo_incompleto || "faltan datos"}.`));
      }
      bc.append(guia);
      bc.append(nodo("p", null, `Flujo de caja libre de doce meses: ${vacio(caja.fcf_12m) ? "sin dato" : milM1(caja.fcf_12m)}.`));
    }
    const bs = nodo("section", "caja");
    bs.append(nodo("h3", null, "Seguridad"));
    const seg = HI.transversal.seguridad || [];
    if (!seg.length) {
      bs.append(nodo("p", "nota", "Sin investigaciones abiertas documentadas."));
    } else {
      const ul = nodo("ul", "lista-seguridad");
      for (const s of seg) {
        const li = nodo("li");
        const meta = nodo("span", "paso-meta");
        meta.append(nodo("span", null, s.estado), nodo("span", null, "abierta desde " + s.abierta_desde),
          enlace(s.enlace, "fuente", s.fuente));
        li.append(nodo("span", null, s.texto), meta);
        ul.append(li);
      }
      bs.append(ul);
    }
    cont.append(bc, bs);
  }

  // Una fila por grupo de promesas de los prioritarios y por entrada del historial.
  // La barra (desde, hasta, tipo) viene calculada de Python; sin barra, fuera del indice.
  function filasHistorial() {
    const filas = [];
    for (const h of HI.hitos) {
      for (const g of h.grupos_promesas || []) {
        filas.push({ titulo: g.paso ? `${h.titulo} · ${g.texto}` : h.titulo,
          criterio: g.paso ? `Paso del hito prioritario ${h.prioridad}` : `Hito prioritario ${h.prioridad} completo`,
          d: g.deslizamiento, barra: g.barra, tipo: g.barra ? g.barra.tipo : "sin_fecha",
          fechas: g.fechas_prometidas || [],
          promesas: (h.promesas || []).filter((p) => (p.paso || null) === g.paso), cumplimiento: null });
      }
    }
    for (const h of HI.historial) {
      if (!h.deslizamiento) continue;
      filas.push({ titulo: h.titulo, criterio: h.criterio, d: h.deslizamiento, barra: h.barra,
        tipo: h.barra ? h.barra.tipo : "sin_fecha", fechas: h.fechas_prometidas || [], promesas: h.promesas || [],
        cumplimiento: h.cumplimiento });
    }
    return filas;
  }

  function pintarTablaHistorial() {
    const filas = filasHistorial();
    const tabla = document.getElementById("t-historial");
    if (!filas.length) {
      tabla.innerHTML = "<tbody><tr><td class=\"texto\">Todavía no hay promesas documentadas.</td></tr></tbody>";
      return;
    }
    let html = "<thead><tr><th scope=\"col\" class=\"texto\">Hito</th><th scope=\"col\" class=\"texto\">Criterio</th>" +
      "<th scope=\"col\">Primera fecha</th><th scope=\"col\">Vigente</th><th scope=\"col\" class=\"texto\">Estado</th>" +
      "<th scope=\"col\">Retraso (meses)</th><th scope=\"col\" class=\"texto\">Fuentes</th></tr></thead><tbody>";
    const a = (url, texto, titulo) => (esHttps(url)
      ? `<a class="enlace-fuente" href="${esc(url)}" target="_blank" rel="noopener" title="${esc(titulo || "")}">${esc(texto)}</a>`
      : esc(texto));
    for (const x of filas) {
      const d = x.d;
      const retraso = !x.barra || vacio(d.meses) ? "—" : x.tipo === "retrasado" ? "≥ " + f.num(d.meses, 1) : f.num(d.meses, 1);
      const promesas = [...x.promesas].sort((p, q) => String(p.declarada).localeCompare(String(q.declarada)));
      const fuentes = promesas.map((p) => a(p.enlace, p.declarada, `${p.fuente}: ${p.fecha_prometida}`));
      if (x.cumplimiento && x.cumplimiento.enlace) fuentes.push(a(x.cumplimiento.enlace, "cumplimiento", x.cumplimiento.fuente));
      html += `<tr><td class="texto">${esc(x.titulo)}</td><td class="texto">${esc(x.criterio || "—")}</td>` +
        `<td>${esc(d.primera)}</td><td>${esc(d.vigente)}</td><td class="texto">${esc(NOMBRE_TIPO[x.tipo] || x.tipo)}</td>` +
        `<td>${esc(retraso)}</td><td class="texto">${fuentes.join(" ")}</td></tr>`;
    }
    tabla.innerHTML = html + "</tbody>";
  }

  // "2026-06-30" -> 2026,49: posicion en un eje lineal de años.
  function anioDecimal(iso) {
    const [a, m, d] = String(iso).split("-").map(Number);
    const inicio = Date.UTC(a, 0, 1);
    return a + (Date.UTC(a, m - 1, d) - inicio) / (Date.UTC(a + 1, 0, 1) - inicio);
  }

  const recortar = (s, n) => (s.length > n ? s.slice(0, n - 1).trimEnd() + "…" : s);

  // Chart.js no dibuja bordes discontinuos en las barras: este complemento
  // repasa con trazo discontinuo las que van hacia atras (en plazo o adelantadas).
  const bordeDiscontinuo = (invertidas, color) => ({
    id: "bordeDiscontinuo",
    afterDatasetsDraw(chart) {
      const meta = chart.getDatasetMeta(0);
      const ctx = chart.ctx;
      ctx.save();
      ctx.setLineDash([4, 3]);
      ctx.lineWidth = 1.5;
      ctx.strokeStyle = color;
      meta.data.forEach((barra, i) => {
        if (!invertidas[i]) return;
        const { x, y, base, height } = barra.getProps(["x", "y", "base", "height"], true);
        ctx.strokeRect(Math.min(x, base), y - height / 2, Math.abs(x - base), height);
      });
      ctx.restore();
    },
  });

  function pintarGraficoHistorial() {
    const filas = filasHistorial().filter((x) => x.barra);
    const lienzo = document.getElementById("lienzo-historial");
    if (!filas.length) {
      document.getElementById("g-historial").closest(".grafico").hidden = true;
      return;
    }
    lienzo.style.height = Math.max(160, filas.length * 30 + 56) + "px";
    // Etiquetas unicas: el eje de categorias situa los puntos por su etiqueta.
    const vistas = {};
    const etiquetas = filas.map((x) => {
      vistas[x.titulo] = (vistas[x.titulo] || 0) + 1;
      return vistas[x.titulo] > 1 ? `${x.titulo} (${vistas[x.titulo]})` : x.titulo;
    });
    const tramos = filas.map((x) => [anioDecimal(x.barra.desde), anioDecimal(x.barra.hasta)]);
    const puntos = [];
    filas.forEach((x, i) => x.fechas.forEach((fecha) => puntos.push({ x: anioDecimal(fecha), y: etiquetas[i], fecha })));
    const todos = tramos.flat().concat(puntos.map((p) => p.x));
    const invertidas = filas.map((x) => x.barra.invertida);
    const colores = filas.map((x, i) => (invertidas[i]
      ? conOpacidad(token(COLOR_TIPO[x.tipo] || "--gris-2"), 0.3) : token(COLOR_TIPO[x.tipo] || "--gris-3")));
    registrar("g-historial", () => ({
      data: { labels: etiquetas, datasets: [
        { type: "bar", label: "Retraso", indexAxis: "y", data: tramos, backgroundColor: colores, borderColor: colores,
          borderRadius: 3, borderSkipped: false, maxBarThickness: 16 },
        { type: "scatter", label: "Fechas prometidas", data: puntos, backgroundColor: token("--tinta"),
          borderColor: token("--superficie"), borderWidth: 1, pointRadius: 4, pointHoverRadius: 6 },
      ] },
      plugins: [bordeDiscontinuo(invertidas, token("--gris-1"))],
      options: {
        responsive: true, maintainAspectRatio: false, animation: false,
        interaction: { mode: "nearest", intersect: true },
        plugins: {
          legend: { display: false },
          tooltip: { callbacks: {
            title: (items) => (items[0].dataset.type === "scatter" ? items[0].raw.y : etiquetas[items[0].dataIndex]),
            label: (c) => {
              if (c.dataset.type === "scatter") return ` Fecha prometida: ${c.raw.fecha}`;
              const x = filas[c.dataIndex];
              return ` ${NOMBRE_TIPO[x.tipo]}: de ${x.barra.desde} a ${x.barra.hasta}` +
                (vacio(x.d.meses) ? "" : ` (${f.num(x.d.meses, 1)} meses)`);
            },
          } },
        },
        scales: {
          x: { type: "linear", min: Math.floor(Math.min(...todos)), max: Math.ceil(Math.max(...todos)),
            border: { display: false }, grid: { color: token("--linea") },
            ticks: { stepSize: 1, callback: (v) => (Number.isInteger(v) ? String(v) : "") } },
          y: { type: "category", labels: etiquetas, border: { display: false }, grid: { display: false },
            ticks: { autoSkip: false, callback: (v, i) => recortar(String(etiquetas[i] ?? ""), 18) } },
        },
      },
    }));
  }

  function opcionesMini(config) {
    const o = opciones(config);
    o.plugins.legend.display = false;
    o.scales.x.ticks.maxTicksLimit = 4;
    o.scales.y.ticks.maxTicksLimit = 4;
    o.scales.y.title.display = false;
    if (o.scales.y1) {
      o.scales.y1.ticks.maxTicksLimit = 4;
      o.scales.y1.title.display = false;
    }
    return o;
  }

  function pintarGraficosHitos() {
    const porId = Object.fromEntries(HI.hitos.map((h) => [h.id, h]));
    const umbral = (hito, id) => {
      const m = ((porId[hito] || {}).metricas || []).find((x) => x.id === id);
      return m ? m.umbral : null;
    };
    const ult = T.slice(-12);
    const etiquetas = ult.map((r) => r.period);
    const pct = (campo) => ult.map((r) => (vacio(r[campo]) ? null : r[campo] * 100));
    const constante = (v, n) => Array.from({ length: n }, () => (vacio(v) ? null : v));
    if (porId.fsd) {
      registrar("g-hito-fsd", () => {
        const filas = T.filter((r) => !vacio(r.fsd_subscriptions)).slice(-12);
        const fmt = (x) => (vacio(x) ? "—" : f.num(x, 2) + " millones");
        const u = umbral("fsd", "suscripciones");
        return { data: { labels: filas.map((r) => r.period), datasets: [
          barrasDestacadas("Suscripciones activas", filas.map((r) => r.fsd_subscriptions / 1e6), fmt),
          comparacion("Umbral", constante(vacio(u) ? null : u / 1e6, filas.length), fmt),
        ] }, options: opcionesMini() };
      });
    }
    if (porId.automovil) {
      registrar("g-hito-automovil", () => {
        const u1 = umbral("automovil", "margen_auto_sin_creditos");
        const u2 = umbral("automovil", "margen_operativo");
        return { data: { labels: etiquetas, datasets: [
          principal("Bruto de automoción sin créditos", pct("margen_auto_sin_creditos"), fmtPct),
          linea("Operativo", pct("margen_operativo"), token("--gris-1"), fmtPct),
          comparacion("Umbral sin créditos", constante(vacio(u1) ? null : u1 * 100, ult.length), fmtPct),
          comparacion("Umbral operativo", constante(vacio(u2) ? null : u2 * 100, ult.length), fmtPct,
            { borderColor: token("--gris-4"), backgroundColor: token("--gris-4") }),
        ] }, options: opcionesMini({ formatoEje: (v) => ejeAuto(v) + " %" }) };
      });
    }
    if (porId.energia) {
      registrar("g-hito-energia", () => ({ data: { labels: etiquetas, datasets: [
        barras("Almacenamiento desplegado", ult.map((r) => (vacio(r.storage_deployed_gwh) ? null : r.storage_deployed_gwh)),
          token("--gris-4"), (x) => (vacio(x) ? "—" : f.num(x, 2) + " GWh")),
        linea("Margen bruto", pct("margen_energia"), token("--acento"), fmtPct, { yAxisID: "y1", borderWidth: 3 }),
      ] }, options: opcionesMini({ derecho: { titulo: "%", formato: (v) => ejeAuto(v) + " %" } }) }));
    }
    pintarGraficoHistorial();
  }

  function pintarHitos() {
    if (!HI) {
      poner("n-hitos-version", "Todavía no hay hitos documentados.");
      for (const id of ["hitos-resumen", "hitos-tarjetas", "hitos-transversal", "hitos-historial"]) {
        document.getElementById(id).hidden = true;
      }
      return;
    }
    poner("n-hitos-version", `Datos documentados a ${HI.version} · retrasos calculados a ${HI.hoy}`);
    seguro("hitos-resumen", pintarResumenHitos);
    seguro("hitos-tarjetas", pintarTarjetasHitos);
    seguro("hitos-transversal", pintarTransversal);
    seguro("t-historial", pintarTablaHistorial);
  }

  // ---------- Robustez ----------
  // Deja un aviso en el bloque que contiene al elemento y registra el error.
  function avisarFallo(elemento, error) {
    console.error(error);
    const bloque = (elemento && elemento.closest(".grafico, .bloque-tabla, .cabecera, .seccion")) ||
      document.querySelector(".pagina");
    if (!bloque) return;
    const aviso = document.createElement("p");
    aviso.className = "nota";
    aviso.textContent = "No se ha podido mostrar este bloque: " +
      (error && error.message ? error.message : String(error)) + ".";
    bloque.appendChild(aviso);
  }

  function seguro(idAncla, pintar) {
    try {
      pintar();
    } catch (error) {
      avisarFallo(document.getElementById(idAncla), error);
    }
  }

  // Alto real de la navegacion fija: los resultados del simulador se pegan debajo.
  function medirNavegacion() {
    const nav = document.querySelector(".navegacion");
    if (!nav) return;
    const fijar = () => document.documentElement.style.setProperty("--alto-nav",
      Math.ceil(nav.getBoundingClientRect().height) + "px");
    fijar();
    if (typeof ResizeObserver !== "undefined") new ResizeObserver(fijar).observe(nav);
  }

  // ---------- Arranque ----------
  seguro("resumen", medirNavegacion);
  seguro("resumen", pintarResumen);
  seguro("t-rejilla", pintarRejilla);
  seguro("t-multiplos", pintarMultiplos);
  seguro("t-sensibilidad", pintarSensibilidad);
  seguro("t-retorno", pintarRetorno);
  seguro("t-fuentes", pintarFuentes);
  seguro("n-lineas", pintarNotaLineas);
  seguro("n-historico", pintarNotaHistorico);
  seguro("verificacion", iniciarSimulador);
  // Antes de los graficos: las tarjetas crean los lienzos de sus minigraficos.
  seguro("hitos", pintarHitos);
  if (typeof Chart === "undefined") {
    seguro("volumenes", sinGraficos);
  } else {
    seguro("volumenes", () => {
      // Tema unico: no hace falta redibujar al cambiar el tema del visor.
      aplicarTema();
      pintarGraficos();
    });
    if (HI) seguro("hitos", pintarGraficosHitos);
  }
})();
