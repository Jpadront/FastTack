<script>
  import { onMount, onDestroy, untrack } from 'svelte';
  import maplibregl from 'maplibre-gl';
  import 'maplibre-gl/dist/maplibre-gl.css';
  import { estado, puntosControl, colorBarco, indice, HUECO_S, velaCorta, derivados, presionEn, laylines, twdEn, dif,
           DIVERGENTE, RAMPA_SOG, corrienteEn, num, lineaLider, tramoEn, rejillaSalida, presionAcumulada } from './datos.js';

  // pistas: decodificadas; an: análisis; sel: Set de velas; ref: vela de referencia
  // T: tiempo actual (s desde la señal); ventana: [t0, t1] de la pestaña; nombres: vela → texto
  // capa: 'presion' | 'twd' | 'rol' | 'sog' | null; tramo: el tramo en curso (para capas y laylines)
  let { pistas, an, sel, ref, T, ventana, controlesVisibles = null, nombres = {}, capa = null, tramo = null, lider = false, fantasma = false, tramoFijo = null, enSalida = false } = $props();
  // el tramo que se navega en T (aunque la pestaña sea otra)
  const liderEn = (T) => { const t = tramoEn(an, T) || tramo; return t ? lineaLider(an, pistas, t, T) : null; };
  const ll = $derived(lider ? liderEn(T) : null);
  const corr = $derived(corrienteEn(an, T));

  let cont, lienzo, mapa, ctx;
  let listo = $state(false);
  let rangoSog = $state([0, 1]);
  const { lat0, lon0 } = pistas.proyeccion;
  const K = Math.cos((lat0 * Math.PI) / 180) * 111320;
  const aLonLat = (x, y) => [lon0 + x / K, lat0 + y / 111320];

  onMount(() => {
    mapa = new maplibregl.Map({
      container: cont,
      style: 'https://tiles.openfreemap.org/styles/positron',
      center: [lon0, lat0], zoom: 13, attributionControl: false,
      dragRotate: false, pitchWithRotate: false,
    });
    mapa.touchZoomRotate.disableRotation();
    mapa.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
    mapa.addControl(new maplibregl.AttributionControl({ compact: true }), 'bottom-right');
    mapa.on('error', () => {}); // sin conexión: seguimos con la capa propia sobre fondo liso
    mapa.on('move', dibujar);
    mapa.on('resize', () => { ajustarLienzo(); dibujar(); });
    ctx = lienzo.getContext('2d');
    ajustarLienzo();
    encuadrar();
    listo = true;
  });
  onDestroy(() => mapa?.remove());

  function ajustarLienzo() {
    const r = cont.getBoundingClientRect(), d = window.devicePixelRatio || 1;
    lienzo.width = r.width * d; lienzo.height = r.height * d;
    lienzo.style.width = r.width + 'px'; lienzo.style.height = r.height + 'px';
    ctx.setTransform(d, 0, 0, d, 0, 0);
  }

  // Encuadre de la pestaña: trazas de los seleccionados en la ventana
  export function encuadrar() {
    if (!mapa) return;
    let minx = Infinity, miny = Infinity, maxx = -Infinity, maxy = -Infinity;
    for (const v of sel) {
      const b = pistas.barcos[v];
      if (!b) continue;
      const i0 = Math.max(0, indice(b.t, ventana[0])), i1 = indice(b.t, ventana[1]);
      for (let i = i0; i <= i1; i++) {
        if (b.x[i] < minx) minx = b.x[i]; if (b.x[i] > maxx) maxx = b.x[i];
        if (b.y[i] < miny) miny = b.y[i]; if (b.y[i] > maxy) maxy = b.y[i];
      }
    }
    if (!isFinite(minx)) return;
    const m = 60;
    mapa.fitBounds([aLonLat(minx - m, miny - m), aLonLat(maxx + m, maxy + m)], { padding: 30, duration: 0, maxZoom: 17 });
  }
  // untrack: fitBounds dispara «move» → dibujar(), que lee T; sin esto el efecto dependería de T y
  // reencuadraría en cada fotograma de la reproducción, deshaciendo el zoom del usuario
  $effect(() => { ventana; sel; if (listo) untrack(encuadrar); });
  $effect(() => { T; sel; controlesVisibles; capa; tramo; lider; fantasma; tramoFijo; enSalida; if (listo) dibujar(); });

  function px(x, y) { const p = mapa.project(aLonLat(x, y)); return [p.x, p.y]; }
  function metrosPx(m) { const a = px(0, 0), b = px(m, 0); return Math.hypot(b[0] - a[0], b[1] - a[1]); }
  function colorSog(v, lo, hi) { const k = Math.max(0, Math.min(RAMPA_SOG.length - 1, Math.round(((v - lo) / (hi - lo || 1)) * (RAMPA_SOG.length - 1)))); return RAMPA_SOG[k]; }
  function colorRol(r) { return r > 0 ? DIVERGENTE.favor : r < 0 ? DIVERGENTE.contra : DIVERGENTE.neutro; }

  // Silueta de casco visto desde arriba: proa en punta, costados curvos y espejo de popa recto, con
  // un punto en el palo para distinguir proa y popa también de lejos
  function casco(X, Y, rumbo, s, color, alfa = 1) {
    ctx.save(); ctx.translate(X, Y); ctx.rotate(rumbo); ctx.globalAlpha = alfa;
    ctx.beginPath(); ctx.moveTo(0, -11 * s);
    ctx.bezierCurveTo(3.6 * s, -6.5 * s, 4.4 * s, -1 * s, 3.6 * s, 7 * s);
    ctx.lineTo(-3.6 * s, 7 * s);
    ctx.bezierCurveTo(-4.4 * s, -1 * s, -3.6 * s, -6.5 * s, 0, -11 * s); ctx.closePath();
    ctx.fillStyle = color; ctx.strokeStyle = '#ffffff'; ctx.lineWidth = 1.5; ctx.stroke(); ctx.fill();
    ctx.beginPath(); ctx.arc(0, -2.5 * s, 1.2 * s, 0, 7); ctx.fillStyle = 'rgba(255,255,255,.9)'; ctx.fill(); ctx.restore();
  }

  // Barco fantasma del tramo en curso: su camino perfecto (con las roladas sabidas de antemano) y
  // dónde iría ahora si hubiera salido de la baliza a la vez que el barco de referencia
  const COLOR_FANTASMA = '#6a5acd';
  function dibujarFantasma() {
    // el tramo de la pestaña; si no, el que navega el barco de referencia en ese momento
    const enT = (tr) => { const f = tr.barcos?.[ref]; return f && (f.t_entrada - an.senal) / 1000 <= T && T <= (f.t_salida - an.senal) / 1000; };
    const t = tramoFijo || an.tramos.find(enT) || tramoEn(an, T);
    const cam = t?.fantasma_camino;
    if (!fantasma || !cam || cam.length < 2) return;
    const P = cam.map(([x, y]) => px(x, y));
    ctx.save(); ctx.globalAlpha = 0.85; ctx.setLineDash([7, 5]); ctx.strokeStyle = COLOR_FANTASMA; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(...P[0]); for (const q of P.slice(1)) ctx.lineTo(...q); ctx.stroke(); ctx.restore();
    const ent = t.barcos?.[ref]?.t_entrada;
    if (ent == null) return;
    const seg = Math.max(0, T - (ent - an.senal) / 1000);
    let k = 1;
    while (k < cam.length - 1 && cam[k][2] < seg) k++;
    const [a, b] = [cam[k - 1], cam[k]];
    const f = b[2] > a[2] ? Math.max(0, Math.min(1, (seg - a[2]) / (b[2] - a[2]))) : 1;
    const [X, Y] = px(a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f);
    const [A, B] = [px(a[0], a[1]), px(b[0], b[1])];
    casco(X, Y, Math.atan2(B[0] - A[0], -(B[1] - A[1])), 1.2, COLOR_FANTASMA, 0.75);
    ctx.font = '600 12px "Barlow Semi Condensed", Arial, sans-serif';
    ctx.lineWidth = 3; ctx.strokeStyle = 'rgba(255,255,255,.85)'; ctx.strokeText('Fantasma', X + 9, Y + 4);
    ctx.fillStyle = COLOR_FANTASMA; ctx.fillText('Fantasma', X + 9, Y + 4);
  }

  // Línea perpendicular al viento por el líder del tramo y la paralela por el barco de referencia
  function dibujarLider() {
    const L = lider ? liderEn(T) : null;
    if (!L) return;
    const r = ((L.dir + 90) * Math.PI) / 180, lx = Math.sin(r), ly = Math.cos(r), m = 3000;
    const linea = (x, y, dash, color, ancho) => {
      ctx.setLineDash(dash); ctx.strokeStyle = color; ctx.lineWidth = ancho;
      ctx.beginPath(); ctx.moveTo(...px(x - lx * m, y - ly * m)); ctx.lineTo(...px(x + lx * m, y + ly * m)); ctx.stroke(); ctx.setLineDash([]);
    };
    ctx.globalAlpha = 0.85;
    linea(L.x, L.y, [], '#10222b', 1.5);
    const etiqueta = (texto, X, Y) => {
      ctx.font = '600 12px "Barlow Semi Condensed", Arial, sans-serif';
      ctx.lineWidth = 3; ctx.strokeStyle = 'rgba(255,255,255,.9)'; ctx.strokeText(texto, X, Y); ctx.fillStyle = '#10222b'; ctx.fillText(texto, X, Y);
    };
    const [LX, LY] = px(L.x, L.y);
    // si el barco ya lleva su nombre al lado, basta con «Líder»
    const conNombre = sel.has(L.lider) && (sel.size <= 20 || L.lider === ref);
    etiqueta(conNombre ? 'Líder' : `Líder: ${velaCorta(L.lider, nombres)}`, LX + 10, LY - 12);
    const p = L.pos[ref];
    if (p && L.lider !== ref) {
      linea(p.x, p.y, [6, 5], colorBarco(ref, ref), 1.5);
      // flecha de la distancia: de nuestro barco hasta la línea del líder, a lo largo del viento
      const d = L.detras[ref], ux = Math.sin((L.dir * Math.PI) / 180), uy = Math.cos((L.dir * Math.PI) / 180);
      const A = px(p.x, p.y), B = px(p.x + ux * d, p.y + uy * d);
      ctx.strokeStyle = colorBarco(ref, ref); ctx.lineWidth = 1.5; ctx.beginPath(); ctx.moveTo(...A); ctx.lineTo(...B); ctx.stroke();
      etiqueta(`${num(d, 0)} m.`, (A[0] + B[0]) / 2 + 8, (A[1] + B[1]) / 2);
    }
    ctx.globalAlpha = 1;
  }

  // Rótulos de las paralelas de salida: sobre cada línea, en su centro, paralelos a ella, sin quedar
  // boca abajo y encima de los barcos (en el disparo la flota se amontona justo ahí)
  function rotulosSalida(rj) {
    ctx.font = '600 11px "Barlow Semi Condensed", Arial, sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    for (const ln of rj.lineas) {
      const A = px(...ln.a), B = px(...ln.b);
      let ang = Math.atan2(B[1] - A[1], B[0] - A[0]);
      if (ang > Math.PI / 2) ang -= Math.PI; else if (ang < -Math.PI / 2) ang += Math.PI;
      ctx.save(); ctx.translate((A[0] + B[0]) / 2, (A[1] + B[1]) / 2); ctx.rotate(ang);
      ctx.lineWidth = 4; ctx.strokeStyle = '#ffffff'; ctx.strokeText(ln.d + ' m.', 0, 0);
      ctx.fillStyle = '#0f766e'; ctx.fillText(ln.d + ' m.', 0, 0);
      ctx.restore();
    }
    ctx.textAlign = 'start'; ctx.textBaseline = 'alphabetic';
  }

  function dibujar() {
    if (!ctx) return;
    const w = lienzo.clientWidth, h = lienzo.clientHeight;
    ctx.clearRect(0, 0, w, h);
    const todos = sel.size > 20;
    // Capa TWD: tinte de todo el campo según la rolada respecto a la media del tramo (±10°)
    if (capa === 'twd' && tramo) {
      const d = dif(twdEn(tramo, T, an.senal) - tramo.viento.twd_media);
      const a = Math.min(Math.abs(d), 10) / 10 * 0.28;
      if (Math.abs(d) >= 1) { ctx.fillStyle = d > 0 ? DIVERGENTE.contra : DIVERGENTE.favor; ctx.globalAlpha = a; ctx.fillRect(0, 0, w, h); ctx.globalAlpha = 1; }
    }
    // Capa de presión acumulada: celdas de 100 m. con la SOG media frente a la flota durante todo el tramo
    // (azul = más presión, naranja = menos; ±6 % satura el color)
    if (capa === 'acumulada' && tramo && tramo.tipo !== 'largo') {
      const ac = presionAcumulada(an, pistas, tramo);
      for (const c of ac.celdas) {
        const d = c.rel - 1;
        if (Math.abs(d) < 0.01) continue;
        const [X0, Y0] = px(c.x, c.y + ac.celda), [X1, Y1] = px(c.x + ac.celda, c.y);
        ctx.fillStyle = d > 0 ? '#2a78d6' : '#e8862a';
        ctx.globalAlpha = Math.min(0.55, (Math.abs(d) / 0.06) * 0.55);
        ctx.fillRect(X0, Y0, X1 - X0, Y1 - Y0);
      }
      ctx.globalAlpha = 1;
    }
    // Capa de presión: manchas alrededor de cada barco del tramo según su SOG frente a la flota
    if (capa === 'presion' && tramo) {
      const pr = presionEn(an, pistas, tramo, T), r = Math.max(14, metrosPx(120));
      for (const p of pr.pts) {
        const exceso = p.rel - 1;
        if (exceso <= 0.02) continue;
        const [X, Y] = px(p.x, p.y);
        const g = ctx.createRadialGradient(X, Y, 0, X, Y, r);
        g.addColorStop(0, `rgba(42,120,214,${Math.min(0.55, exceso * 4)})`); g.addColorStop(1, 'rgba(42,120,214,0)');
        ctx.fillStyle = g; ctx.beginPath(); ctx.arc(X, Y, r, 0, 7); ctx.fill();
        if (p.sube) { ctx.strokeStyle = '#104281'; ctx.lineWidth = 2; ctx.beginPath(); ctx.arc(X, Y, 11, 0, 7); ctx.stroke(); }
      }
    }
    // Laylines de la baliza hacia la que se navega
    if (tramo) {
      ctx.setLineDash([4, 5]); ctx.strokeStyle = '#4b5e67'; ctx.lineWidth = 1; ctx.globalAlpha = 0.7;
      for (const [a, b] of laylines(an, pistas, tramo, T)) {
        const A = px(...a), B = px(...b); ctx.beginPath(); ctx.moveTo(...A); ctx.lineTo(...B); ctx.stroke();
      }
      ctx.setLineDash([]); ctx.globalAlpha = 1;
    }
    // Salida: paralelas a 25 y 50 m. por detrás, cerradas por las laylines de comité (estribor) y pin (babor)
    const rj = enSalida ? rejillaSalida(an, pistas, T) : null;
    if (rj) {
      const COL = '#0f766e';
      // las cuatro laylines de los extremos: blanco discontinuo, con un filo oscuro tenue para que se vean
      // sobre el fondo claro; estribor con trazo largo y babor con trazo corto
      const tramos = rj.laylines.map((l) => [px(...l.a), px(...l.b), l]);
      for (const [A, B, l] of tramos) {
        ctx.setLineDash(l.amura === 'estribor' ? [8, 4] : [3, 4]);
        ctx.lineWidth = 3.5; ctx.strokeStyle = 'rgba(16,34,43,0.25)';
        ctx.beginPath(); ctx.moveTo(...A); ctx.lineTo(...B); ctx.stroke();
        ctx.lineWidth = 2; ctx.strokeStyle = '#ffffff';
        ctx.beginPath(); ctx.moveTo(...A); ctx.lineTo(...B); ctx.stroke();
      }
      ctx.setLineDash([]);
      // rótulo al final de cada layline
      ctx.font = '600 11px "Barlow Semi Condensed", Arial, sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      for (const [A, B, l] of tramos) {
        const ux = B[0] - A[0], uy = B[1] - A[1], n = Math.hypot(ux, uy) || 1;
        const X = B[0] + (ux / n) * 14, Y = B[1] + (uy / n) * 14, t = l.amura === 'estribor' ? 'E' : 'B';
        ctx.lineWidth = 3; ctx.strokeStyle = 'rgba(255,255,255,0.9)'; ctx.strokeText(t, X, Y);
        ctx.fillStyle = '#10222b'; ctx.fillText(t, X, Y);
      }
      ctx.textAlign = 'start'; ctx.textBaseline = 'alphabetic';
      ctx.strokeStyle = COL; ctx.lineWidth = 1.5; ctx.globalAlpha = 0.85;
      for (const ln of rj.lineas) {
        const A = px(...ln.a), B = px(...ln.b);
        ctx.beginPath(); ctx.moveTo(...A); ctx.lineTo(...B); ctx.stroke();
      }
      ctx.globalAlpha = 1;
    }
    // Líneas de salida y llegada, balizas
    const ctrls = an.controles.filter((c) => !controlesVisibles || controlesVisibles.has(c.id));
    for (const c of ctrls) {
      const pts = puntosControl(c, pistas, T).map((p) => px(p.x, p.y));
      if ((c.tipo === 'salida' || c.tipo === 'llegada') && pts.length === 2) {
        ctx.setLineDash(c.tipo === 'salida' ? [6, 4] : [2, 4]); ctx.strokeStyle = '#10222b'; ctx.globalAlpha = 0.6; ctx.lineWidth = 1.5;
        ctx.beginPath(); ctx.moveTo(...pts[0]); ctx.lineTo(...pts[1]); ctx.stroke(); ctx.setLineDash([]); ctx.globalAlpha = 1;
      }
      for (const [k, p] of pts.entries()) {
        ctx.beginPath(); ctx.arc(p[0], p[1], 6, 0, 7);
        ctx.fillStyle = '#ffffff'; ctx.fill(); ctx.lineWidth = 2; ctx.strokeStyle = '#4a3aa7';
        ctx.setLineDash(c.fuente === 'estimada' ? [3, 3] : []); ctx.stroke(); ctx.setLineDash([]);
        if (k === 0) {
          ctx.font = '600 12px "Barlow Semi Condensed", Arial, sans-serif'; ctx.fillStyle = '#10222b';
          ctx.fillText(c.nombre + (c.fuente === 'estimada' ? ' (estimada)' : ''), p[0] + 9, p[1] - 8);
        }
      }
    }
    dibujarLider();
    dibujarFantasma();
    // Rango de SOG de la ventana (p5–p95 de los seleccionados) para la rampa de la capa SOG
    let sogLo = 0, sogHi = 1;
    if (capa === 'sog') {
      const vals = [];
      for (const v of sel) { const b = pistas.barcos[v]; if (!b) continue; const i0 = Math.max(0, indice(b.t, ventana[0])), i1 = indice(b.t, ventana[1]); for (let i = i0; i <= i1; i += 3) vals.push(b.sog[i]); }
      vals.sort((a, b) => a - b); sogLo = vals[Math.floor(vals.length * 0.05)] ?? 0; sogHi = vals[Math.floor(vals.length * 0.95)] ?? 1;
    }
    if (capa === 'sog' && (rangoSog[0] !== sogLo || rangoSog[1] !== sogHi)) rangoSog = [sogLo, sogHi];
    // Trazas: los seleccionados desde el inicio de la ventana; con toda la flota, solo 3 min.
    const orden = [...sel].sort((a, b) => (a === ref) - (b === ref)); // el de referencia encima
    for (const v of orden) {
      const b = pistas.barcos[v];
      if (!b) continue;
      const color = colorBarco(v, ref);
      const t0 = todos && v !== ref ? Math.max(ventana[0], T - 180) : ventana[0];
      const i0 = Math.max(0, indice(b.t, t0)), i1 = indice(b.t, T);
      ctx.lineWidth = v === ref ? (capa === 'rol' ? 4 : 2.6) : todos ? 1 : capa === 'rol' ? 2.2 : 1.6; ctx.globalAlpha = todos && v !== ref ? 0.6 : 0.9;
      const e = estado(b, T);
      if (capa === 'sog' || capa === 'rol') {
        // Traza coloreada segmento a segmento
        const dv = capa === 'rol' ? derivados(an, pistas, v) : null;
        for (let i = Math.max(i0, 1); i <= i1; i++) {
          if (b.t[i] - b.t[i - 1] > HUECO_S) continue;
          if (capa === 'rol' && isNaN(dv.rol[i])) { ctx.strokeStyle = '#c3ccd0'; }   // maniobrando, rodeando o fuera del tramo
          else ctx.strokeStyle = capa === 'sog' ? colorSog(b.sog[i], sogLo, sogHi) : colorRol(dv.rol[i]);
          ctx.beginPath(); ctx.moveTo(...px(b.x[i - 1], b.y[i - 1])); ctx.lineTo(...px(b.x[i], b.y[i])); ctx.stroke();
        }
      } else {
        ctx.strokeStyle = color;
        ctx.beginPath();
        let dentro = false;
        for (let i = i0; i <= i1; i++) {
          const [X, Y] = px(b.x[i], b.y[i]);
          if (dentro && b.t[i] - b.t[i - 1] <= HUECO_S) ctx.lineTo(X, Y); else ctx.moveTo(X, Y);
          dentro = true;
        }
        if (e && !e.sinDatos) { const [X, Y] = px(e.x, e.y); ctx.lineTo(X, Y); }
        ctx.stroke();
      }
      ctx.globalAlpha = 1;
      if (!e) continue;
      const [X, Y] = px(e.x, e.y);
      if (e.sinDatos) {
        ctx.beginPath(); ctx.arc(X, Y, 4, 0, 7); ctx.strokeStyle = color; ctx.lineWidth = 1.5; ctx.stroke();
      } else {
        casco(X, Y, ((e.hdg ?? e.cog ?? 0) * Math.PI) / 180, v === ref ? 1.3 : 1, color);
      }
      if (!todos || v === ref) {
        ctx.font = `${v === ref ? 700 : 600} 12px "Barlow Semi Condensed", Arial, sans-serif`;
        ctx.lineWidth = 3; ctx.strokeStyle = 'rgba(255,255,255,.85)'; ctx.strokeText(velaCorta(v, nombres), X + 9, Y + 4);
        ctx.fillStyle = '#10222b'; ctx.fillText(velaCorta(v, nombres), X + 9, Y + 4);
      }
    }
    if (rj) rotulosSalida(rj);
  }
</script>

<div class="mapa" bind:this={cont}>
  <canvas bind:this={lienzo} aria-hidden="true"></canvas>
  {#if lider && !ll}
    <div class="lider-info">Línea del líder: sin posiciones recientes en este momento (huecos de datos)</div>
  {:else if ll}
    <div class="lider-info">
      {#if ll.lider === ref}<b>{velaCorta(ref, nombres)}</b> lidera el tramo
      {:else if ll.detras[ref] != null}<b class="num">{num(ll.detras[ref], 0)} m.</b> por detrás de la línea de {velaCorta(ll.lider, nombres)}
      {:else}Líder del tramo: {velaCorta(ll.lider, nombres)}{/if}
      <span class="est">est.</span>
    </div>
  {/if}
  {#if corr}
    <div class="corr" title={`Corriente estimada (${corr.ambito}), confianza ${corr.confianza}: ${num(corr.velocidad_kn, 2)} kn. hacia ${num(corr.hacia_grados, 0)}°`}>
      <svg viewBox="-12 -12 24 24" width="22" height="22" aria-hidden="true" style:transform={`rotate(${corr.hacia_grados}deg)`}>
        <path d="M0 10 V-8 M-5 -3 L0 -9 L5 -3" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" />
      </svg>
      <span><b class="num">{num(corr.velocidad_kn, 1)} kn.</b> corriente <span class="est">est.</span></span>
    </div>
  {/if}
  {#if capa === 'sog'}
    <div class="leyenda"><span class="num">{rangoSog[0].toFixed(1)}</span>{#each RAMPA_SOG as c}<i style:background={c}></i>{/each}<span class="num">{rangoSog[1].toFixed(1)} kn.</span></div>
  {:else if capa === 'rol'}
    <div class="leyenda"><i style:background={DIVERGENTE.favor}></i>en la amura favorecida <i style:background={DIVERGENTE.contra}></i>con la rolada en contra <i style:background={DIVERGENTE.neutro}></i>igual <span class="est">est.</span>
      {#if tramo?.barcos[ref]?.tactica?.amura_favorecida_pct != null}<span class="pct">· {velaCorta(ref, nombres)}: <b class="num">{num(tramo.barcos[ref].tactica.amura_favorecida_pct, 0)} %</b> del {tramo.nombre} en la favorecida</span>{/if}</div>
  {:else if capa === 'twd'}
    <div class="leyenda"><i style:background={DIVERGENTE.favor}></i>rolada izquierda <i style:background={DIVERGENTE.contra}></i>rolada derecha (±10°) <span class="est">est.</span></div>
  {:else if capa === 'acumulada'}
    <div class="leyenda"><i style:background="#2a78d6"></i>más presión <i style:background="#e8862a"></i>menos, durante todo el tramo (SOG frente a la flota, celdas de 100 m.) <span class="est">est.</span></div>
  {:else if capa === 'presion'}
    <div class="leyenda"><i style:background="#2a78d6"></i>más SOG que la flota (racha) · anillo: la acaba de recibir <span class="est">est.</span></div>
  {:else if enSalida}
    <div class="leyenda"><span class="raya larga"></span>E: layline de estribor <span class="raya corta"></span>B: layline de babor, a comité y pin · paralelas a 25 y 50 m. <span class="est">est.</span></div>
  {/if}
</div>

<style>
  .mapa { position: relative; width: 100%; height: 100%; background: #dce7eb; color-scheme: light; border-radius: 6px; overflow: hidden; }
  canvas { position: absolute; inset: 0; pointer-events: none; z-index: 2; }
  :global(.maplibregl-ctrl-top-right) { z-index: 3; }
  .corr { position: absolute; left: 8px; top: 8px; z-index: 3; display: flex; align-items: center; gap: 4px; background: rgba(255,255,255,.9);
    color: #10222b; border-radius: 4px; padding: 2px 8px 2px 4px; font: 500 12px var(--display); }
  .corr svg { color: #2a78d6; }
  .corr .est { color: #6a5acd; }
  .raya { display: inline-block; width: 18px; height: 0; border-top: 2px dashed #4b5e67; vertical-align: middle; }
  .raya.corta { border-top-style: dotted; }
  .leyenda { position: absolute; left: 8px; bottom: 8px; z-index: 3; display: flex; align-items: center; gap: 4px; flex-wrap: wrap;
    background: rgba(255,255,255,.9); color: #10222b; border-radius: 4px; padding: 3px 8px; font: 500 12px var(--display); max-width: calc(100% - 120px); }
  .lider-info { position: absolute; left: 50%; transform: translateX(-50%); top: 8px; z-index: 3; background: rgba(255,255,255,.92); color: #10222b;
    border-radius: 4px; padding: 3px 10px; font: 500 13px var(--display); white-space: nowrap; }
  .lider-info .est { color: #6a5acd; font-size: 11px; }
  .leyenda .pct { margin-left: 4px; }
  .leyenda i { display: inline-block; width: 14px; height: 8px; border-radius: 2px; }
  .leyenda .est { color: #6a5acd; }
</style>
