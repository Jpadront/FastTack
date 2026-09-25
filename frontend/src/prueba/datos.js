// Lógica de la pantalla de una prueba: trazas, pestañas, ventanas de tiempo y valores instantáneos.
// Todos los tiempos en segundos desde la señal; posiciones en metros (coordenadas locales del motor).

export const HUECO_S = 15; // más de esto sin datos: el barco se muestra como «sin datos»

// Colores fijos por barco (el naranja queda reservado al barco de referencia).
const PALETA = ['#2a78d6', '#1baf7a', '#c98500', '#d55181', '#008300', '#4a3aa7', '#e34948', '#0e8a9a'];
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
      out.push({ id: fin.id, nombre: fin.nombre, tipo: 'baliza', controles: off ? [fin, off] : [fin] });
    } else {
      out.push({ id: fin.id, nombre: fin.nombre, tipo: 'baliza', controles: [fin] });
    }
  }
  out.push({ id: 'llegada', nombre: 'Llegada', tipo: 'llegada' });
  out.push({ id: 'rendimiento', nombre: 'Rendimiento', tipo: 'rendimiento' });
  return out;
}

// Ventana de tiempo (s desde la señal) de una pestaña para los barcos seleccionados.
export function ventana(p, an, sel) {
  const s = an.senal;
  const seg = (ms) => (ms - s) / 1000;
  const fin = Math.max(...an.clasificacion.map((c) => seg(c.t)));
  if (p.tipo === 'salida') return [-180, 180];
  if (p.tipo === 'rendimiento') return [-60, fin + 30];
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
export function instantaneos(an, pistas, tramo, T) {
  const s = an.senal;
  const twd = twdEn(tramo, T, s);
  const ceñida = tramo.tipo === 'ceñida';
  const eje = (tramo.rumbo_eje * Math.PI) / 180;
  const ux = Math.sin(eje), uy = Math.cos(eje);
  const filas = [];
  for (const [v, b] of Object.entries(pistas.barcos)) {
    const f = tramo.barcos[v];
    if (!f) continue;
    const e = estado(b, T);
    if (!e) continue;
    const ref = ceñida ? twd : (twd + 180) % 360;
    const vmg = e.cog != null && !e.sinDatos ? e.sog * Math.cos((dif(e.cog - ref) * Math.PI) / 180) : null;
    const twa = e.cog != null && !e.sinDatos ? Math.abs(dif(e.cog - twd)) : null;
    // Orden: primero los que ya han salido del tramo (por su hora de salida), después los que lo
    // navegan (por su avance a lo largo del eje) y al final los que aún no han entrado.
    const t_in = (f.t_entrada - s) / 1000, t_out = (f.t_salida - s) / 1000;
    const fase = T > t_out ? 0 : T >= t_in ? 1 : 2;
    const avance = e.x * ux + e.y * uy;
    filas.push({ vela: v, fase, t_out, avance, dentro: fase === 1, sinDatos: e.sinDatos, sog: e.sinDatos ? null : e.sog, vmg, twa,
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
