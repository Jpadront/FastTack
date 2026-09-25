<script>
  import { onMount, onDestroy } from 'svelte';
  import maplibregl from 'maplibre-gl';
  import 'maplibre-gl/dist/maplibre-gl.css';
  import { estado, puntosControl, colorBarco, indice, HUECO_S, velaCorta } from './datos.js';

  // pistas: decodificadas; an: análisis; sel: Set de velas; ref: vela de referencia
  // T: tiempo actual (s desde la señal); ventana: [t0, t1] de la pestaña; nombres: vela → texto
  let { pistas, an, sel, ref, T, ventana, controlesVisibles = null, nombres = {} } = $props();

  let cont, lienzo, mapa, ctx;
  let listo = $state(false);
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
  $effect(() => { ventana; sel; if (listo) encuadrar(); });
  $effect(() => { T; sel; controlesVisibles; if (listo) dibujar(); });

  function px(x, y) { const p = mapa.project(aLonLat(x, y)); return [p.x, p.y]; }

  function dibujar() {
    if (!ctx) return;
    const w = lienzo.clientWidth, h = lienzo.clientHeight;
    ctx.clearRect(0, 0, w, h);
    const todos = sel.size > 20;
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
    // Trazas: los seleccionados desde el inicio de la ventana; con toda la flota, solo 3 min
    const orden = [...sel].sort((a, b) => (a === ref) - (b === ref)); // el de referencia encima
    for (const v of orden) {
      const b = pistas.barcos[v];
      if (!b) continue;
      const color = colorBarco(v, ref);
      const t0 = todos && v !== ref ? Math.max(ventana[0], T - 180) : ventana[0];
      const i0 = Math.max(0, indice(b.t, t0)), i1 = indice(b.t, T);
      ctx.strokeStyle = color; ctx.lineWidth = v === ref ? 2.6 : todos ? 1 : 1.6; ctx.globalAlpha = todos && v !== ref ? 0.6 : 0.9;
      ctx.beginPath();
      let dentro = false;
      for (let i = i0; i <= i1; i++) {
        const [X, Y] = px(b.x[i], b.y[i]);
        if (dentro && b.t[i] - b.t[i - 1] <= HUECO_S) ctx.lineTo(X, Y); else ctx.moveTo(X, Y);
        dentro = true;
      }
      const e = estado(b, T);
      if (e && !e.sinDatos) { const [X, Y] = px(e.x, e.y); ctx.lineTo(X, Y); }
      ctx.stroke(); ctx.globalAlpha = 1;
      if (!e) continue;
      const [X, Y] = px(e.x, e.y);
      if (e.sinDatos) {
        ctx.beginPath(); ctx.arc(X, Y, 4, 0, 7); ctx.strokeStyle = color; ctx.lineWidth = 1.5; ctx.stroke();
      } else {
        const rumbo = ((e.hdg ?? e.cog ?? 0) * Math.PI) / 180;
        ctx.save(); ctx.translate(X, Y); ctx.rotate(rumbo);
        const s = v === ref ? 1.3 : 1;
        ctx.beginPath(); ctx.moveTo(0, -9 * s); ctx.lineTo(5 * s, 6 * s); ctx.lineTo(-5 * s, 6 * s); ctx.closePath();
        ctx.fillStyle = color; ctx.strokeStyle = '#ffffff'; ctx.lineWidth = 1.5; ctx.stroke(); ctx.fill(); ctx.restore();
      }
      if (!todos || v === ref) {
        ctx.font = `${v === ref ? 700 : 600} 12px "Barlow Semi Condensed", Arial, sans-serif`;
        ctx.lineWidth = 3; ctx.strokeStyle = 'rgba(255,255,255,.85)'; ctx.strokeText(velaCorta(v, nombres), X + 9, Y + 4);
        ctx.fillStyle = '#10222b'; ctx.fillText(velaCorta(v, nombres), X + 9, Y + 4);
      }
    }
  }
</script>

<div class="mapa" bind:this={cont}>
  <canvas bind:this={lienzo} aria-hidden="true"></canvas>
</div>

<style>
  .mapa { position: relative; width: 100%; height: 100%; background: var(--agua); border-radius: 6px; overflow: hidden; }
  canvas { position: absolute; inset: 0; pointer-events: none; z-index: 2; }
  :global(.maplibregl-ctrl-top-right) { z-index: 3; }
</style>
