<script>
  // Una métrica por prueba: una línea por barco (el de referencia más gruesa) y, si se da, la
  // mediana de la flota en gris discontinuo. Huecos = prueba sin dato. Un solo eje.
  import { num } from '../prueba/datos.js';

  let { pruebas, series, flota = null, invertido = false, unidad = '', decimales = 1, altura = 220, titulo = '' } = $props();

  const M = { l: 48, r: 14, t: 12, b: 28 };
  let W = $state(600);
  let hover = $state(null);

  const todos = $derived([...series.flatMap((s) => s.vals), ...(flota || [])].filter((v) => v != null));
  const rango = $derived.by(() => {
    if (!todos.length) return [0, 1];
    let lo = Math.min(...todos), hi = Math.max(...todos);
    if (invertido) lo = Math.min(lo, 1);
    const pad = (hi - lo) * 0.08 || 1;
    return [invertido ? Math.max(1, lo - pad) : lo - pad, hi + pad];
  });
  const X = (k) => M.l + (pruebas.length === 1 ? 0.5 : k / (pruebas.length - 1)) * (W - M.l - M.r);
  const Y = (v) => {
    const f = (v - rango[0]) / (rango[1] - rango[0]);
    return invertido ? M.t + f * (altura - M.t - M.b) : altura - M.b - f * (altura - M.t - M.b);
  };
  function camino(vals) {
    let d = '', abierto = false;
    vals.forEach((v, k) => { if (v == null) { abierto = false; return; } d += (abierto ? 'L' : 'M') + X(k).toFixed(1) + ' ' + Y(v).toFixed(1); abierto = true; });
    return d;
  }
  const marcas = $derived.by(() => {
    const [lo, hi] = rango, n = 4, out = [];
    for (let i = 0; i <= n; i++) out.push(lo + ((hi - lo) * i) / n);
    return out;
  });
  function mover(e) {
    const r = e.currentTarget.getBoundingClientRect();
    const x = ((e.clientX - r.left) / r.width) * W;
    let k = 0;
    pruebas.forEach((_, i) => { if (Math.abs(X(i) - x) < Math.abs(X(k) - x)) k = i; });
    hover = k;
  }
  const filasTip = $derived(hover == null ? [] : series.map((s) => ({ ...s, v: s.vals[hover] })).filter((s) => s.v != null)
    .sort((a, b) => (invertido ? a.v - b.v : b.v - a.v)));
</script>

<div class="g" bind:clientWidth={W}>
  <svg viewBox={`0 0 ${W} ${altura}`} style:height={altura + 'px'} role="img" aria-label={titulo}
       onpointermove={mover} onpointerleave={() => (hover = null)}>
    {#each marcas as m}
      <line x1={M.l} x2={W - M.r} y1={Y(m)} y2={Y(m)} class="rej" />
      <text x={M.l - 6} y={Y(m) + 4} class="eje" text-anchor="end">{num(m, invertido ? 0 : decimales)}</text>
    {/each}
    {#each pruebas as p, k}
      <text x={X(k)} y={altura - 8} class="eje" text-anchor="middle">{p}</text>
    {/each}
    {#if hover != null}<line x1={X(hover)} x2={X(hover)} y1={M.t} y2={altura - M.b} class="cursor" />{/if}
    {#if flota}<path d={camino(flota)} class="flota" />{/if}
    {#each series as s (s.v)}
      <path d={camino(s.vals)} fill="none" stroke={s.color} stroke-width={s.ref ? 3 : 2} stroke-linejoin="round" />
      {#each s.vals as v, k}{#if v != null}<circle cx={X(k)} cy={Y(v)} r={s.ref ? 4.5 : 3.5} fill={s.color} class="punto" />{/if}{/each}
    {/each}
  </svg>
  {#if hover != null && (filasTip.length || flota?.[hover] != null)}
    <div class="tip" style:left={Math.min(X(hover) + 10, W - 190) + 'px'}>
      <b>{pruebas[hover]}</b>
      {#each filasTip as s}<div><i style:background={s.color}></i>{s.nombre}<span class="num">{num(s.v, invertido ? 0 : decimales)}{unidad ? ' ' + unidad : ''}</span></div>{/each}
      {#if flota?.[hover] != null}<div class="tenue"><i class="gris"></i>mediana flota<span class="num">{num(flota[hover], decimales)}{unidad ? ' ' + unidad : ''}</span></div>{/if}
    </div>
  {/if}
</div>

<style>
  .g { position: relative; width: 100%; }
  svg { width: 100%; display: block; touch-action: pan-y; }
  .rej { stroke: var(--rejilla); stroke-width: 1; }
  .eje { font: 500 11px var(--mono); fill: var(--tinta-3); }
  .cursor { stroke: var(--tinta-3); stroke-width: 1; }
  .flota { fill: none; stroke: #8a969c; stroke-width: 1.5; stroke-dasharray: 5 4; }
  .punto { stroke: var(--panel); stroke-width: 2; }
  .tip { position: absolute; top: 4px; min-width: 170px; background: var(--panel); border: 1px solid var(--linea); border-radius: 5px;
         padding: 6px 8px; font-size: 12px; box-shadow: 0 2px 8px rgba(0,0,0,.08); pointer-events: none; }
  .tip div { display: flex; align-items: center; gap: 6px; }
  .tip span { margin-left: auto; padding-left: 10px; }
  .tip i { display: inline-block; width: 10px; height: 3px; border-radius: 2px; }
  .tip i.gris { background: #8a969c; }
</style>
