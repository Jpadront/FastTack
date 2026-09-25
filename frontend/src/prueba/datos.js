// Lógica de la pantalla de una prueba: trazas, pestañas, ventanas de tiempo y valores instantáneos.
// Todos los tiempos en segundos desde la señal; posiciones en metros (coordenadas locales del motor).

export const HUECO_S = 15; // más de esto sin datos: el barco se muestra como «sin datos»

// Colores fijos por barco (el naranja queda reservado al barco de referencia).
// Validada con la guía de visualización (daltonismo y separación); cada traza lleva además su etiqueta.
export const PALETA = ['#2a78d6', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#4a3aa7', '#e34948'];
export const COLOR_YO = '#e0622e';
export function colorBarco(vela, ref) {
  if (vela === ref) return COLOR_YO;
  let h = 0;
  for (const ch of vela) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return PALETA[h % PALETA.length];
}

export function decodificarPistas(p) {
  const barcos = {};
  for (const [v, b] of Object.entries(p.barcos)) {
    barcos[v] = {
      t: Float64Array.from(b.t, (x) => x / 10),
      x: Float64Array.from(b.x, (x) => x / 10),
      y: Float64Array.from(b.y, (x) => x / 10),
      sog: Float32Array.from(b.sog, (x) => x / 10),
      cog: Float32Array.from(b.cog),
      hdg: Float32Array.from(b.hdg),
      roll: Float32Array.from(b.roll),
    };
  }
  const balizas = {};
  for (const [sn, b] of Object.entries(p.balizas)) {
    balizas[sn] = { t: Float64Array.from(b.t, (x) => x / 10), x: Float64Array.from(b.x, (x) => x / 10), y: Float64Array.from(b.y, (x) => x / 10) };
  }
  return { senal: p.senal, proyeccion: p.proyeccion, barcos, balizas };
}

// Índice de la última muestra con t ≤ T (búsqueda binaria).
export function indice(ts, T) {
  let lo = 0, hi = ts.length - 1;
  if (!ts.length || T < ts[0]) return -1;
  while (lo < hi) {
    const m = (lo + hi + 1) >> 1;
    if (ts[m] <= T) lo = m; else hi = m - 1;
  }
  return lo;
}

// Estado de un barco en T: interpolado solo si las muestras vecinas están a ≤ HUECO_S.
export function estado(b, T) {
  const i = indice(b.t, T);
  if (i < 0) return null;
  const j = Math.min(i + 1, b.t.length - 1);
  const dt = b.t[j] - b.t[i];
  if (T - b.t[i] > HUECO_S && !(j > i && dt <= HUECO_S)) return { x: b.x[i], y: b.y[i], sinDatos: true, i };
  const f = j > i && dt > 0 && dt <= HUECO_S ? (T - b.t[i]) / dt : 0;
  const cog = b.cog[i] >= 0 ? b.cog[i] : b.cog[j] >= 0 ? b.cog[j] : null;
  return {
    x: b.x[i] + (b.x[j] - b.x[i]) * f, y: b.y[i] + (b.y[j] - b.y[i]) * f,
    sog: b.sog[i] + (b.sog[j] - b.sog[i]) * f, cog, hdg: b.hdg[i], roll: b.roll[i], sinDatos: false, i,
  };
}

export function balizaEn(b, T) {
  if (!b) return null;
  const i = Math.max(0, indice(b.t, T));
  return { x: b.x[i], y: b.y[i] };
}

// Posición de un control (del análisis) en T: Atlas si se mueve, si no su punto fijo.
export function puntosControl(c, pistas, T) {
  const pts = [];
  (c.sn || []).forEach((sn) => {
    const p = sn != null ? balizaEn(pistas.balizas[String(sn)], T) : null;
    if (p) pts.push(p);
  });
  if (!pts.length && c.xy) pts.push({ x: c.xy[0], y: c.xy[1] });
  return pts;
}

export const dif = (a) => ((((a + 180) % 360) + 360) % 360) - 180;

// TWD del tramo en T interpolando entre cortes (s desde la señal).
export function twdEn(tramo, T, senalMs) {
  const c = tramo.viento.cortes;
  const ts = c.map((k) => (k.t - senalMs) / 1000);
  if (T <= ts[0]) return c[0].twd;
  if (T >= ts[ts.length - 1]) return c[c.length - 1].twd;
  let k = 0;
  while (ts[k + 1] < T) k++;
  const f = (T - ts[k]) / (ts[k + 1] - ts[k]);
  return (c[k].twd + dif(c[k + 1].twd - c[k].twd) * f + 360) % 360;
}

export function twsEn(tramo, T, senalMs) {
  const c = tramo.viento.cortes;
  let mejor = c[0];
  for (const k of c) if (Math.abs((k.t - senalMs) / 1000 - T) < Math.abs((mejor.t - senalMs) / 1000 - T)) mejor = k;
  return mejor.tws;
}

// Pestañas según el recorrido real de la prueba.
export function pestanas(an) {
  const out = [{ id: 'salida', nombre: 'Salida', tipo: 'salida' }];
  for (const tr of an.tramos) {
    out.push({ id: tr.id, nombre: tr.nombre, tipo: 'tramo', tramo: tr });
    const fin = an.controles.find((c) => c.id === tr.hasta);
    if (!fin || fin.tipo === 'llegada') continue;
    if (fin.tipo === 'barlovento') {
      const off = an.controles.find((c) => c.id === `o${fin.id.slice(1)}`);
      // La pestaña del rodeo de barlovento se llama por el offset, que es donde acaba el rodeo
      out.push({ id: fin.id, nombre: off ? off.nombre : fin.nombre, tipo: 'baliza', controles: off ? [fin, off] : [fin] });
    } else {
      out.push({ id: fin.id, nombre: fin.nombre, tipo: 'baliza', controles: [fin] });
    }
  }
  out.push({ id: 'llegada', nombre: 'Llegada', tipo: 'llegada' });
  out.push({ id: 'rendimiento', nombre: 'Rendimiento', tipo: 'rendimiento' });
  out.push({ id: 'debrief', nombre: 'Debrief IA', tipo: 'debrief' });
  return out;
}

// Ventana de tiempo (s desde la señal) de una pestaña para los barcos seleccionados.
export function ventana(p, an, sel) {
  const s = an.senal;
  const seg = (ms) => (ms - s) / 1000;
  const fin = Math.max(...an.clasificacion.map((c) => seg(c.t)));
  if (p.tipo === 'salida') return [-180, 180];
  if (p.tipo === 'rendimiento' || p.tipo === 'debrief') return [-60, fin + 30];
  if (p.tipo === 'llegada') {
    const ts = an.clasificacion.filter((c) => sel.has(c.vela)).map((c) => seg(c.t));
    const t0 = seg(an.clasificacion[0].t);
    return [t0 - 90, Math.max(t0, ...ts) + 60];
  }
  if (p.tipo === 'tramo') {
    const filas = Object.entries(p.tramo.barcos).filter(([v]) => sel.has(v)).map(([, f]) => f);
    const t0 = seg(p.tramo.t0), t1 = seg(p.tramo.t1);
    return [t0, Math.max(t1, ...filas.map((f) => seg(f.t_salida)))];
  }
  // baliza (y su offset): alrededor de los pasos de los seleccionados
  const ts = [];
  for (const c of p.controles) {
    for (const [v, pv] of Object.entries(an.pasos)) {
      const x = pv[c.id];
      if (x && (sel.has(v) || !sel.size)) ts.push(seg(x.entrada ?? x.t), seg(x.salida ?? x.t));
    }
  }
  const mediana = seg(p.controles[0].t_mediano);
  return ts.length ? [Math.min(...ts) - 45, Math.max(...ts) + 45] : [mediana - 120, mediana + 120];
}

// Tramo que navega el líder en T (para el panel en pestañas que no son de tramo).
export function tramoEn(an, T) {
  const s = an.senal;
  let actual = an.tramos[0];
  for (const tr of an.tramos) if ((tr.t0 - s) / 1000 <= T) actual = tr;
  return actual;
}

// Valores instantáneos de todos los barcos en un tramo: avance a lo largo del eje, VMG, TWA…
// VMG y TWA de cada barco se calculan con SU tramo en T (sus propios pasos por baliza): mientras
// unos ya navegan la popa, otros siguen en la ceñida o en el offset.
export function instantaneos(an, pistas, tramo, T) {
  const s = an.senal;
  const twd = twdEn(tramo, T, s);
  const eje = (tramo.rumbo_eje * Math.PI) / 180;
  const ux = Math.sin(eje), uy = Math.cos(eje);
  const filas = [];
  for (const [v, b] of Object.entries(pistas.barcos)) {
    const f = tramo.barcos[v];
    if (!f) continue;
    const e = estado(b, T);
    if (!e) continue;
    const suyo = tramoDeBarco(an, v, T);  // null: antes de la salida, en un rodeo/offset o ya llegado
    let vmg = null, twa = null;
    if (suyo && e.cog != null && !e.sinDatos) {
      const w = suyo === tramo ? twd : twdEn(suyo, T, s);
      const ref = suyo.tipo === 'ceñida' ? w : (w + 180) % 360;
      vmg = e.sog * Math.cos((dif(e.cog - ref) * Math.PI) / 180);
      twa = Math.abs(dif(e.cog - w));
    }
    // Orden: primero los que ya han salido del tramo (por su hora de salida), después los que lo
    // navegan (por su avance a lo largo del eje) y al final los que aún no han entrado.
    const t_in = (f.t_entrada - s) / 1000, t_out = (f.t_salida - s) / 1000;
    const fase = T > t_out ? 0 : T >= t_in ? 1 : 2;
    const avance = e.x * ux + e.y * uy;
    filas.push({ vela: v, fase, t_out, avance, dentro: fase === 1, suyo: suyo ? suyo.nombre : T < 0 ? 'presalida' : T > (an.clasificacion.find((c) => c.vela === v)?.t - s) / 1000 ? 'llegado' : 'rodeo', otro: T >= 0 && suyo !== tramo, sinDatos: e.sinDatos, sog: e.sinDatos ? null : e.sog, vmg, twa,
                 cog: e.sinDatos ? null : e.cog, hdg: e.sinDatos ? null : e.hdg });
  }
  filas.sort((a, b) => a.fase - b.fase || (a.fase === 0 ? a.t_out - b.t_out : b.avance - a.avance));
  const lider = filas.find((f) => f.fase === 1);
  filas.forEach((f, k) => { f.pos = k + 1; f.dm = f.fase === 1 && lider ? lider.avance - f.avance : null; });
  return { twd, filas };
}

export const fmtT = (seg) => {
  const neg = seg < 0, a = Math.abs(Math.round(seg));
  const h = Math.floor(a / 3600), m = Math.floor((a % 3600) / 60), x = a % 60;
  return (neg ? '−' : '+') + (h ? `${h}:${String(m).padStart(2, '0')}` : m) + ':' + String(x).padStart(2, '0');
};
export const fmtDur = (seg) => (seg == null ? '—' : fmtT(seg).slice(1));
export const num = (v, d = 1) => (v == null ? '—' : Number(v).toLocaleString('es-ES', { minimumFractionDigits: d, maximumFractionDigits: d }));

// 'ESP1214' → 'ESP 1214' (texto corto para el mapa)
export const velaCorta = (v, nombres = {}) => nombres[v]?.vela || v.replace(/^([A-Z]+)(\d)/, '$1 $2');


// ---------------------------------------------------------------- hito 4: capas y gráficos

export const DIVERGENTE = { favor: '#2a78d6', contra: '#e34948', neutro: '#8a969c' };
// Rampa secuencial azul (claro → oscuro) para la SOG
export const RAMPA_SOG = ['#b7d3f6', '#86b6ef', '#5598e7', '#2a78d6', '#1c5cab', '#104281', '#0d366b'];

// Tramo en el que navega un barco en t (según sus pasos por baliza)
export function tramoDeBarco(an, v, tSeg) {
  const ms = an.senal + tSeg * 1000;
  for (const tr of an.tramos) {
    const f = tr.barcos[v];
    if (f && ms >= f.t_entrada && ms <= f.t_salida) return tr;
  }
  return null;
}

// Valores derivados por muestra de un barco (memorizados): tramo, TWD, rolada, VMG, TWA, escora
const _memo = new WeakMap();
export function derivados(an, pistas, v) {
  const b = pistas.barcos[v];
  if (!b) return null;
  let porAn = _memo.get(an);
  if (!porAn) { porAn = new Map(); _memo.set(an, porAn); }
  if (porAn.has(v)) return porAn.get(v);
  const n = b.t.length, off = an.offsets_escora?.[v] || 0;
  const d = { tramo: new Int16Array(n).fill(-1), twd: new Float32Array(n).fill(NaN), rol: new Float32Array(n).fill(NaN),
              vmg: new Float32Array(n).fill(NaN), twa: new Float32Array(n).fill(NaN), escora: new Float32Array(n), cabeceo: new Float32Array(n) };
  const rangos = an.tramos.map((tr) => { const f = tr.barcos[v]; return f ? [(f.t_entrada - an.senal) / 1000, (f.t_salida - an.senal) / 1000] : null; });
  for (let i = 0; i < n; i++) {
    d.escora[i] = Math.abs(b.roll[i] - off);
    d.cabeceo[i] = b.pitch ? b.pitch[i] : NaN;
    const k = rangos.findIndex((r) => r && b.t[i] >= r[0] && b.t[i] <= r[1]);
    if (k < 0) continue;
    const tr = an.tramos[k];
    d.tramo[i] = k;
    const twd = twdEn(tr, b.t[i], an.senal);
    d.twd[i] = twd;
    if (b.cog[i] < 0) continue;
    const ceñida = tr.tipo === 'ceñida';
    const ref = ceñida ? twd : (twd + 180) % 360;
    d.vmg[i] = b.sog[i] * Math.cos((dif(b.cog[i] - ref) * Math.PI) / 180);
    d.twa[i] = Math.abs(dif(b.cog[i] - twd));
    // Beneficio de la rolada: con TWA constante el rumbo gira con el viento. Ganancia de avance
    // hacia la baliza respecto al rumbo que tendría con el viento medio del tramo.
    const delta = dif(twd - tr.viento.twd_media);
    const r = (a) => Math.cos((dif(a - tr.rumbo_eje) * Math.PI) / 180);
    d.rol[i] = r(b.cog[i]) - r(b.cog[i] - delta);
  }
  porAn.set(v, d);
  return d;
}

// Fase de rolada en curso (según el % del tramo)
export function faseEn(tr, T, senalMs) {
  const pct = ((T * 1000 + senalMs - tr.t0) / (tr.t1 - tr.t0)) * 100;
  return tr.fases_rolada.find((f) => pct >= f.desde_pct && pct < f.hasta_pct) || null;
}

// Presión instantánea: SOG de cada barco del tramo frente a la mediana de la flota del tramo;
// lado izquierdo/derecho (mirando a barlovento) por su posición lateral respecto al eje.
export function presionEn(an, pistas, tr, T) {
  const s = an.senal, ceñida = tr.tipo === 'ceñida';
  const eje = (tr.rumbo_eje * Math.PI) / 180, ux = Math.sin(eje), uy = Math.cos(eje);
  const pts = [];
  for (const [v, f] of Object.entries(tr.barcos)) {
    if (T < (f.t_entrada - s) / 1000 || T > (f.t_salida - s) / 1000) continue;
    const e = estado(pistas.barcos[v] || { t: [] }, T);
    if (!e || e.sinDatos) continue;
    const e30 = estado(pistas.barcos[v], T - 30);
    let lat = e.x * uy - e.y * ux; if (!ceñida) lat = -lat;  // derecha mirando a barlovento
    pts.push({ vela: v, x: e.x, y: e.y, sog: e.sog, sog30: e30 && !e30.sinDatos ? e30.sog : null, lat });
  }
  if (pts.length < 4) return { pts: [], lr: null };
  const med = mediana(pts.map((p) => p.sog));
  pts.forEach((p) => { p.rel = p.sog / med; p.sube = p.sog30 != null && (p.sog - p.sog30) / med > 0.06; });
  const latMed = mediana(pts.map((p) => p.lat));
  const izq = pts.filter((p) => p.lat < latMed).map((p) => p.sog), der = pts.filter((p) => p.lat >= latMed).map((p) => p.sog);
  const lr = izq.length >= 2 && der.length >= 2 ? mediana(izq) - mediana(der) : null;
  return { pts, lr, med };
}

export function mediana(a) {
  const x = [...a].sort((p, q) => p - q);
  return x.length ? (x.length % 2 ? x[(x.length - 1) / 2] : (x[x.length / 2 - 1] + x[x.length / 2]) / 2) : null;
}

// Laylines del tramo desde su baliza final (con Atlas o estimada): rectas con el TWA de la flota
export function laylines(an, pistas, tr, T) {
  const fin = an.controles.find((c) => c.id === tr.hasta);
  if (!fin || !tr.viento.twa_flota) return [];
  // Rumbos sobre el fondo de cada amura en el corte más cercano (incluyen la corriente); si no hay,
  // TWD ± TWA de la flota. Las rectas salen de la baliza en sentido contrario al de la navegación.
  const pctT = ((T * 1000 + an.senal - tr.t0) / (tr.t1 - tr.t0)) * 100;
  const conRumbos = tr.viento.cortes.filter((c) => c.rumbos);
  let rumbos;
  if (conRumbos.length) {
    const c = conRumbos.reduce((m, x) => (Math.abs(x.pct - pctT) < Math.abs(m.pct - pctT) ? x : m));
    rumbos = c.rumbos.map((k) => (k + 180) % 360);
  } else {
    const twd = twdEn(tr, T, an.senal), ceñida = tr.tipo === 'ceñida';
    const a = ceñida ? tr.viento.twa_flota : 180 - tr.viento.twa_flota;
    rumbos = ceñida ? [(twd + 180 - a + 360) % 360, (twd + 180 + a) % 360] : [(twd - a + 360) % 360, (twd + a) % 360];
  }
  const out = [];
  for (const p of puntosControl(fin, pistas, T)) {
    for (const r of rumbos) {
      const rad = (r * Math.PI) / 180;
      out.push([[p.x, p.y], [p.x + Math.sin(rad) * 2500, p.y + Math.cos(rad) * 2500]]);
    }
  }
  return out;
}

// Corriente estimada en T: la de la vuelta en curso si se pudo estimar, si no la de toda la prueba.
export function corrienteEn(an, T) {
  const c = an.corriente;
  if (!c) return null;
  const v = (c.por_vuelta || []).find((x) => x.confianza && T >= x.desde_s && T <= x.hasta_s);
  return v ? { ...v, ambito: `vuelta ${v.vuelta}` } : { ...c, ambito: 'toda la prueba' };
}
