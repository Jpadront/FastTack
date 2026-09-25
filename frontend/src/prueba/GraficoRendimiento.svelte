<script>
  import Nota from '../Nota.svelte';
  import { onMount, onDestroy } from 'svelte';
  import uPlot from 'uplot';
  import 'uplot/dist/uPlot.min.css';
  import { derivados, fmtT, num, velaCorta, mediana } from './datos.js';

  let { an, pistas, sel, ref, T, colores, nombres = {} } = $props();

  const METRICAS = [
    { k: 'vmg_c', t: 'VMG en ceñida', campo: 'vmg', tipo: 'ceñida', u: 'kn', d: 2, est: true },
    { k: 'vmg_p', t: 'VMG en popa', campo: 'vmg', tipo: 'popa', u: 'kn', d: 2, est: true },
    { k: 'sog_c', t: 'SOG en ceñida', campo: 'sog', tipo: 'ceñida', u: 'kn', d: 2 },
    { k: 'sog_p', t: 'SOG en popa', campo: 'sog', tipo: 'popa', u: 'kn', d: 2 },
    { k: 'twa_c', t: 'TWA en ceñida', campo: 'twa', tipo: 'ceñida', u: '°', d: 0, est: true },
    { k: 'twa_p', t: 'TWA en popa', campo: 'twa', tipo: 'popa', u: '°', d: 0, est: true },
    { k: 'vir', t: 'Pérdida por virada', maniobra: 'virada', tipo: 'ceñida', u: 'm', d: 1, est: true },
    { k: 'tra', t: 'Pérdida por trasluchada', maniobra: 'trasluchada', tipo: 'popa', u: 'm', d: 1, est: true },
    { k: 'esc_c', t: 'Escora en ceñida', campo: 'escora', tipo: 'ceñida', u: '°', d: 0 },
    { k: 'esc_p', t: 'Escora en popa', campo: 'escora', tipo: 'popa', u: '°', d: 0 },
    { k: 'cab_c', t: 'Cabeceo en ceñida', campo: 'cabeceo', tipo: 'ceñida', u: '°', d: 0 },
    { k: 'cab_p', t: 'Cabeceo en popa', campo: 'cabeceo', tipo: 'popa', u: '°', d: 0 },
  ];
  const MAX_BARCOS = 15, RODEO_MS = 20000, PASO = 5, VENT_TENDENCIA = 12; // tendencia: mediana móvil de 12 × 5 s = 60 s
  let metrica = $state('vmg_c');
  let cont, plot, lectura = $state(null);
  const m = $derived(METRICAS.find((x) => x.k === metrica));
  const barcos = $derived([...sel].filter((v) => pistas.barcos[v]).sort((a, b) => (a === ref ? -1 : b === ref ? 1 : 0)).slice(0, MAX_BARCOS));

  function datos() {
    const fin = Math.max(...an.clasificacion.map((c) => (c.t - an.senal) / 1000)) + 30;
    const n = Math.ceil(fin / PASO) + 1;
    const x = Float64Array.from({ length: n }, (_, i) => i * PASO);
    const series = [];
    for (const v of barcos) {
      if (m.maniobra) {
        const y = new Array(n).fill(null);
        for (const tr of an.tramos) for (const mm of tr.maniobras[v] || [])
          if (mm.tipo === m.maniobra && mm.perdida_m != null) y[Math.round((mm.t - an.senal) / 1000 / PASO)] = mm.perdida_m;
        series.push({ v, crudo: y, tend: null });
        continue;
      }
      const b = pistas.barcos[v], d = derivados(an, pistas, v);
      const sum = new Float64Array(n), cnt = new Uint16Array(n);
      for (let i = 0; i < b.t.length; i++) {
        const k = d.tramo[i];
        if (k < 0 || an.tramos[k].tipo !== m.tipo || b.t[i] < 0) continue;
        // fuera los rodeos: 20 s tras entrar y antes de salir del tramo (según los pasos de ESTE barco)
        const f = an.tramos[k].barcos[v], ms = an.senal + b.t[i] * 1000;
        if (ms - f.t_entrada < RODEO_MS || f.t_salida - ms < RODEO_MS) continue;
        const val = m.campo === 'sog' ? b.sog[i] : d[m.campo][i];
        if (val == null || Number.isNaN(val)) continue;
        const j = Math.round(b.t[i] / PASO);
        if (j >= 0 && j < n) { sum[j] += val; cnt[j]++; }
      }
      const crudo = Array.from(sum, (s, j) => (cnt[j] ? s / cnt[j] : null));
      const tend = crudo.map((_, j) => {
        const vent = [];
        for (let q = j - VENT_TENDENCIA / 2; q <= j + VENT_TENDENCIA / 2; q++) if (crudo[q] != null) vent.push(crudo[q]);
        return crudo[j] == null || vent.length < 4 ? null : mediana(vent);
      });
      series.push({ v, crudo, tend });
    }
    return { x, series };
  }

  function construir() {
    plot?.destroy();
    if (!cont) return;
    const { x, series } = datos();
    const data = [x], defs = [{}];
    for (const s of series) {
      const c = colores[s.v] || '#7d8f97';
      data.push(s.crudo);
      defs.push(m.maniobra
        ? { label: velaCorta(s.v, nombres), stroke: c, width: 0, paths: () => null, points: { show: true, size: s.v === ref ? 9 : 7, fill: c, stroke: '#fff', width: 1.5 } }
        : { label: velaCorta(s.v, nombres) + ' (crudo)', stroke: c + '40', width: 1, points: { show: false }, spanGaps: false });
      if (!m.maniobra) {
        data.push(s.tend);
        defs.push({ label: velaCorta(s.v, nombres), stroke: c, width: s.v === ref ? 3 : 2, points: { show: false }, spanGaps: false });
      }
    }
    const bandas = an.tramos.map((tr) => ({ nombre: tr.nombre, tipo: tr.tipo, t0: (tr.t0 - an.senal) / 1000, t1: (tr.t1 - an.senal) / 1000 }));
    const opts = {
      width: cont.clientWidth, height: 280, legend: { show: false },
      scales: { x: { time: false } },
      axes: [
        { stroke: '#7d8f97', grid: { stroke: '#e3eaed', width: 1 }, values: (u, vs) => vs.map((v) => fmtT(v)), font: '11px "IBM Plex Mono", monospace' },
        { stroke: '#7d8f97', grid: { stroke: '#e3eaed', width: 1 }, label: m.u, font: '11px "IBM Plex Mono", monospace', size: 52 },
      ],
      series: defs,
      cursor: { drag: { x: false, y: false }, points: { show: false } },
      hooks: {
        drawClear: [(u) => {
          const { ctx } = u; ctx.save();
          for (const b of bandas) {
            const a = u.valToPos(b.t0, 'x', true), z = u.valToPos(b.t1, 'x', true);
            if (b.tipo === m.tipo) { ctx.fillStyle = 'rgba(106,90,205,0.06)'; ctx.fillRect(a, u.bbox.top, z - a, u.bbox.height); }
            ctx.fillStyle = '#7d8f97'; ctx.font = `${11 * devicePixelRatio}px "Barlow Semi Condensed", sans-serif`;
            ctx.fillText(b.nombre, a + 4 * devicePixelRatio, u.bbox.top + 12 * devicePixelRatio);
          }
          ctx.restore();
        }],
        draw: [(u) => {
          const X = u.valToPos(Tactual, 'x', true), { ctx } = u;
          ctx.save(); ctx.strokeStyle = '#10222b'; ctx.lineWidth = devicePixelRatio;
          ctx.beginPath(); ctx.moveTo(X, u.bbox.top); ctx.lineTo(X, u.bbox.top + u.bbox.height); ctx.stroke(); ctx.restore();
        }],
        setCursor: [(u) => {
          const i = u.cursor.idx;
          if (i == null) { lectura = null; return; }
          const vals = [];
          let k = 1;
          for (const s of series) {
            const serieVal = m.maniobra ? u.data[k][i] : u.data[k + 1][i];
            if (serieVal != null) vals.push({ v: s.v, val: serieVal });
            k += m.maniobra ? 1 : 2;
          }
          lectura = { t: u.data[0][i], vals };
        }],
      },
    };
    plot = new uPlot(opts, data, cont);
  }

  let Tactual = T;
  $effect(() => { Tactual = T; plot?.redraw(false, false); });
  $effect(() => { metrica; barcos; construir(); });
  let obs;
  onMount(() => { obs = new ResizeObserver(() => plot?.setSize({ width: cont.clientWidth, height: 280 })); obs.observe(cont); });
  onDestroy(() => { obs?.disconnect(); plot?.destroy(); });
</script>

<section class="tarjeta bloque">
  <div class="cab">
    <h3>{m.t} <span class="tenue">({m.u})</span>{#if m.est}<span class="est"> estimado</span>{/if}</h3>
    <label class="sel">Métrica
      <select bind:value={metrica}>{#each METRICAS as x}<option value={x.k}>{x.t}</option>{/each}</select>
    </label>
  </div>
  <div class="leyenda">
    {#each barcos as v}<span><i style:background={colores[v]}></i>{velaCorta(v, nombres)}</span>{/each}
    {#if sel.size > MAX_BARCOS}<span class="tenue">(se muestran {MAX_BARCOS} de {sel.size})</span>{/if}
  </div>
  <div class="grafico" bind:this={cont}></div>
  <p class="lect num">
    {#if lectura}{fmtT(lectura.t)} · {#each lectura.vals as l, k}{k ? ' · ' : ''}{velaCorta(l.v, nombres)} {num(l.val, m.d)} {m.u}{/each}
    {:else}Pasa el cursor por el gráfico para ver los valores.{/if}
  </p>
  <Nota>{m.maniobra ? 'Cada punto es una maniobra con datos suficientes para medir su pérdida.' : 'Datos crudos (medias de 5 s) en tenue; tendencia robusta (mediana móvil de 60 s) destacada. Solo tramos de ' + m.tipo + ' (sombreados), cada barco con sus propios pasos por baliza y sin los 20 s de cada rodeo. La línea vertical sigue al reproductor.'}</Nota>
</section>

<style>
  .bloque { padding: 10px 12px; }
  .cab { display: flex; justify-content: space-between; align-items: center; gap: 8px; flex-wrap: wrap; }
  h3 { font-size: 15px; letter-spacing: .06em; text-transform: uppercase; color: var(--tinta-2); }
  .est { color: var(--estimado); font-size: 11px; }
  .sel { font: 600 12px var(--display); color: var(--tinta-2); display: flex; gap: 6px; align-items: center; }
  select { font: 500 14px var(--texto); padding: 4px 6px; border: 1px solid var(--linea); border-radius: 4px; background: var(--panel); color: var(--tinta); }
  .leyenda { display: flex; flex-wrap: wrap; gap: 4px 12px; font: 600 13px var(--display); margin: 6px 0; }
  .leyenda i { display: inline-block; width: 12px; height: 3px; border-radius: 2px; margin-right: 5px; vertical-align: middle; }
  .bloque { min-width: 0; overflow: hidden; }
  .grafico { width: 100%; min-height: 280px; overflow: hidden; }
  .lect { font-size: 12px; color: var(--tinta-2); margin: 4px 0 0; min-height: 1.4em; }
  .nota { font-size: 12px; color: var(--tinta-3); margin: 2px 0 0; }
</style>
