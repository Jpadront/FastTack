<script>
  // Polar del tramo: VMG según el ángulo al viento (TWA) del barco de referencia frente al top 5,
  // con el ángulo de máxima VMG marcado. Un eje (VMG, kn); la SOG va en la etiqueta al pasar el ratón.
  import { num, mediana, COLOR_YO } from './datos.js';

  let { tramo, ref, nombreRef = '', top5 = [] } = $props();
  const W0 = 520, H = 170, M = { l: 40, r: 12, t: 10, b: 28 };
  let W = $state(W0);
  const mia = $derived((tramo.barcos[ref]?.polar || []).filter((x) => x.s >= 15));
  // top 5: mediana por franja de los que tienen esa franja
  const t5 = $derived.by(() => {
    const por = {};
    for (const v of top5) for (const x of tramo.barcos[v]?.polar || []) (por[x.twa] ||= []).push(x);
    return Object.entries(por).filter(([, xs]) => xs.length >= 2)
      .map(([twa, xs]) => ({ twa: +twa, vmg: mediana(xs.map((x) => x.vmg)), sog: mediana(xs.map((x) => x.sog)), n: xs.length }))
      .sort((a, b) => a.twa - b.twa);
  });
  const todos = $derived([...mia, ...t5]);
  const xLo = $derived(Math.min(...todos.map((p) => p.twa)) - 1), xHi = $derived(Math.max(...todos.map((p) => p.twa)) + 1);
  const yLo = $derived(Math.min(...todos.map((p) => p.vmg)) - 0.1), yHi = $derived(Math.max(...todos.map((p) => p.vmg)) + 0.1);
  const X = (a) => M.l + ((a - xLo) / (xHi - xLo || 1)) * (W - M.l - M.r);
  const Y = (v) => H - M.b - ((v - yLo) / (yHi - yLo || 1)) * (H - M.t - M.b);
  const maxDe = (xs) => (xs.filter((x) => (x.s ?? 30) >= 30).length ? xs.filter((x) => (x.s ?? 30) >= 30) : xs).reduce((m, x) => (x.vmg > m.vmg ? x : m), { vmg: -Infinity });
  const mMia = $derived(mia.length ? maxDe(mia) : null), m5 = $derived(t5.length ? maxDe(t5) : null);
  const linea = (xs) => xs.map((p, k) => `${k ? 'L' : 'M'}${X(p.twa).toFixed(1)},${Y(p.vmg).toFixed(1)}`).join(' ');
  let hover = $state(null);
</script>

{#if mia.length >= 3}
<section class="tarjeta bloque">
  <h3>Polar del tramo <span class="est">estimada</span></h3>
  <p class="titular">{nombreRef}: más VMG a <b class="num">{num(mMia.twa, 0)}°</b> de TWA ({num(mMia.vmg, 2)} kn){#if m5 && m5.vmg > -Infinity}&nbsp;· top 5 a <b class="num">{num(m5.twa, 0)}°</b> ({num(m5.vmg, 2)} kn){/if}.</p>
  <div class="leyenda"><span><i style:background={COLOR_YO}></i>{nombreRef}</span>{#if t5.length}<span><i class="t5"></i>top 5 (mediana)</span>{/if}</div>
  <div bind:clientWidth={W}>
    <svg viewBox={`0 0 ${W} ${H}`} style:height={H + 'px'} role="img" aria-label="VMG según el ángulo al viento">
      {#each [0, 0.5, 1] as f}
        {@const v = yLo + f * (yHi - yLo)}
        <line x1={M.l} x2={W - M.r} y1={Y(v)} y2={Y(v)} class="rejilla" />
        <text x={M.l - 6} y={Y(v) + 4} class="eje" text-anchor="end">{num(v, 1)}</text>
      {/each}
      {#each todos.map((p) => p.twa).filter((a, k, xs) => xs.indexOf(a) === k && Math.round(a) % (tramo.tipo === 'ceñida' ? 4 : 10) < 2) as a}
        <text x={X(a)} y={H - 8} class="eje" text-anchor="middle">{num(a, 0)}°</text>
      {/each}
      {#if t5.length}<path d={linea(t5)} class="t5l" />{/if}
      <path d={linea(mia)} class="yo" style:stroke={COLOR_YO} />
      {#each mia as p}<circle cx={X(p.twa)} cy={Y(p.vmg)} r="4" style:fill={COLOR_YO} class="punto" role="presentation"
        onmouseenter={() => (hover = p)} onmouseleave={() => (hover = null)} />{/each}
      {#if mMia}<line x1={X(mMia.twa)} x2={X(mMia.twa)} y1={M.t} y2={H - M.b} class="marca" style:stroke={COLOR_YO} />{/if}
      {#if m5 && m5.vmg > -Infinity}<line x1={X(m5.twa)} x2={X(m5.twa)} y1={M.t} y2={H - M.b} class="marca t5m" />{/if}
    </svg>
  </div>
  {#if hover}<p class="sub num">TWA {num(hover.twa, 0)}° · VMG {num(hover.vmg, 2)} kn · SOG {num(hover.sog, 2)} kn · {hover.s} s</p>
  {:else}<p class="sub">VMG mediana por franja de ángulo al viento ({tramo.tipo === 'ceñida' ? '2°' : '5°'}), navegando estable (sin maniobras ni rodeos). Sin anemómetro, vale para el viento de este tramo.</p>{/if}
</section>
{/if}

<style>
  .bloque { padding: 10px 12px; min-width: 0; }
  h3 { font-size: 15px; letter-spacing: .06em; text-transform: uppercase; color: var(--tinta-2); margin: 0 0 4px; }
  .est { color: var(--estimado); font-size: 11px; }
  .titular { margin: 0 0 4px; font-size: 15px; }
  .sub { margin: 4px 0 0; font-size: 13px; color: var(--tinta-2); }
  .leyenda { display: flex; gap: 12px; font-size: 13px; color: var(--tinta-2); }
  .leyenda i { display: inline-block; width: 14px; height: 3px; margin-right: 5px; vertical-align: middle; border-radius: 2px; }
  .leyenda i.t5 { background: var(--tinta-3); }
  svg { width: 100%; display: block; }
  .rejilla { stroke: var(--rejilla); }
  .eje { font-size: 11px; fill: var(--tinta-3); }
  .yo { fill: none; stroke-width: 2; }
  .t5l { fill: none; stroke: var(--tinta-3); stroke-width: 2; stroke-dasharray: 4 3; }
  .punto { stroke: var(--panel); stroke-width: 1.5; }
  .marca { stroke-width: 1; stroke-dasharray: 2 3; }
  .t5m { stroke: var(--tinta-3); }
</style>
