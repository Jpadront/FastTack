<script>
  import Nota from '../Nota.svelte';
  // Evolución del viento en un tramo: TWD y presión frente al % del tramo (dos gráficos, un eje cada
  // uno). El cursor sigue al reproductor. Todo estimado a partir de la flota.
  import { num } from './datos.js';

  let { tramo, T, senalMs } = $props();
  const H = 130, M = { l: 58, r: 14, t: 14, b: 22 };
  let W = $state(520); // ancho real del contenedor: el texto no escala
  const cortes = $derived(tramo.viento.cortes);
  const calibrada = $derived(tramo.viento.tws_calibrada);
  const pct = $derived(Math.max(0, Math.min(100, ((T * 1000 + senalMs - tramo.t0) / (tramo.t1 - tramo.t0)) * 100)));
  let hover = $state(null);

  function escala(vals, pad) {
    const v = vals.filter((x) => x != null);
    let lo = Math.min(...v), hi = Math.max(...v);
    if (hi - lo < pad) { const c = (lo + hi) / 2; lo = c - pad / 2; hi = c + pad / 2; }
    return [lo, hi];
  }
  const X = (p) => M.l + (p / 100) * (W - M.l - M.r);
  function serie(vals, lo, hi) {
    const Y = (v) => H - M.b - ((v - lo) / (hi - lo)) * (H - M.t - M.b);
    let d = '', abierto = false;
    cortes.forEach((c, k) => { const v = vals[k]; if (v == null) { abierto = false; return; } d += (abierto ? 'L' : 'M') + X(c.pct).toFixed(1) + ' ' + Y(v).toFixed(1); abierto = true; });
    return { d, Y };
  }
  // TWD desenrollada alrededor de la media para que 359→1 no salte
  const twd = $derived(cortes.map((c) => tramo.viento.twd_media + (((c.twd - tramo.viento.twd_media + 540) % 360) - 180)));
  const pres = $derived(cortes.map((c) => (calibrada ? c.tws : c.sog_mediana)));
  const eTwd = $derived(escala(twd, 6));
  const ePres = $derived(escala(pres, calibrada ? 2 : 0.6));
  const sTwd = $derived(serie(twd, ...eTwd));
  const sPres = $derived(serie(pres, ...ePres));

  function mover(e) {
    const r = e.currentTarget.getBoundingClientRect();
    const p = ((e.clientX - r.left) / r.width * W - M.l) / (W - M.l - M.r) * 100;
    let k = 0; cortes.forEach((c, i) => { if (Math.abs(c.pct - p) < Math.abs(cortes[k].pct - p)) k = i; });
    hover = k;
  }
</script>

<section class="tarjeta bloque">
  <h3>Evolución del viento <span class="est">estimado</span></h3>
  <div bind:clientWidth={W}>
  {#each [['TWD (°)', sTwd, eTwd, twd, (v) => num(((v % 360) + 360) % 360, 0) + '°'], [calibrada ? 'TWS (kn)' : 'Presión: SOG mediano de la flota (kn)', sPres, ePres, pres, (v) => num(v, calibrada ? 1 : 2) + ' kn']] as [titulo, s, e, vals, fmt]}
    <div class="g">
      <div class="tit">{titulo}</div>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={titulo} onpointermove={mover} onpointerleave={() => (hover = null)}>
        {#each [0, 0.5, 1] as f}
          {@const y = H - M.b - f * (H - M.t - M.b)}
          <line x1={M.l} x2={W - M.r} y1={y} y2={y} class="rej" />
          <text x={M.l - 6} y={y + 4} class="eje" text-anchor="end">{fmt(e[0] + f * (e[1] - e[0]))}</text>
        {/each}
        {#each [0, 25, 50, 75, 100] as p}<text x={X(p)} y={H - 6} class="eje" text-anchor="middle">{p} %</text>{/each}
        <path d={s.d} class="linea" />
        {#each cortes as c, k}{#if vals[k] != null}<circle cx={X(c.pct)} cy={s.Y(vals[k])} r={c.fuente === 'arrastre' ? 3 : 4} class:arrastre={c.fuente === 'arrastre'} class="punto" />{/if}{/each}
        <line x1={X(pct)} x2={X(pct)} y1={M.t} y2={H - M.b} class="cursor" />
        {#if hover != null && vals[hover] != null}
          <g transform={`translate(${Math.min(X(cortes[hover].pct), W - 124)}, ${M.t})`}>
            <rect width="112" height="20" rx="3" class="tip" /><text x="6" y="14" class="tiptxt">{cortes[hover].pct} % · {fmt(vals[hover])}</text>
          </g>
        {/if}
      </svg>
    </div>
  {/each}
  </div>
  <Nota>Eje horizontal: % del tiempo del líder en el tramo. Puntos huecos: cortes sin datos suficientes (se arrastra el valor anterior). La línea vertical sigue al reproductor.</Nota>
</section>

<style>
  .bloque { padding: 10px 12px; }
  h3 { font-size: 15px; letter-spacing: .06em; text-transform: uppercase; color: var(--tinta-2); margin-bottom: 4px; }
  .est { color: var(--estimado); font-size: 11px; }
  .g { margin-top: 4px; }
  .tit { font: 600 12px var(--display); color: var(--tinta-2); }
  svg { width: 100%; height: 130px; display: block; touch-action: pan-y; }
  .rej { stroke: var(--rejilla); stroke-width: 1; }
  .eje { font: 500 10px var(--mono); fill: var(--tinta-3); }
  .linea { fill: none; stroke: var(--estimado); stroke-width: 2; }
  .punto { fill: var(--estimado); stroke: var(--panel); stroke-width: 2; }
  .punto.arrastre { fill: var(--panel); stroke: var(--estimado); stroke-width: 1.5; }
  .cursor { stroke: var(--tinta); stroke-width: 1; }
  .tip { fill: var(--tinta); }
  .tiptxt { font: 500 11px var(--mono); fill: var(--panel); }
  .nota { font-size: 12px; color: var(--tinta-3); margin: 4px 0 0; }
</style>
