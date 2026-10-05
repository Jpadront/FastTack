<script>
  // Aceleración en la salida: SOG (GPS) de cada barco seleccionado de −60 s. a +60 s. del disparo,
  // y una tabla con la SOG en momentos comparables (−30, −10, disparo, +10, +30 s.).
  import Nota from '../Nota.svelte';
  import { estado, num, velaCorta } from './datos.js';

  let { pistas, sel, ref, colores = {}, nombres = {} } = $props();
  const T0 = -60, T1 = 60, PASO = 1;
  const MOMENTOS = [-30, -10, 0, 10, 30];
  const sogEn = (v, T) => { const b = pistas.barcos[v]; const e = b ? estado(b, T) : null; return e && !e.sinDatos ? e.sog : null; };
  // el barco de referencia primero y dibujado el último (encima)
  const velas = $derived([...sel].filter((v) => pistas.barcos[v]).sort((a, b) => (a === ref ? -1 : b === ref ? 1 : a.localeCompare(b))));
  const series = $derived(velas.map((v) => {
    const pts = [];
    for (let T = T0; T <= T1; T += PASO) pts.push([T, sogEn(v, T)]);
    return { v, pts };
  }));
  const filas = $derived(velas.map((v) => ({ v, sog: MOMENTOS.map((T) => sogEn(v, T)) })));
  const todos = $derived(series.flatMap((s) => s.pts.map((p) => p[1])).filter((x) => x != null));
  const yLo = $derived(todos.length ? Math.max(0, Math.floor(Math.min(...todos))) : 0);
  const yHi = $derived(todos.length ? Math.ceil(Math.max(...todos)) : 1);

  const H = 200, M = { l: 40, r: 12, t: 14, b: 26 };
  let W = $state(640);
  const X = (T) => M.l + ((T - T0) / (T1 - T0)) * (W - M.l - M.r);
  const Y = (v) => H - M.b - ((v - yLo) / (yHi - yLo || 1)) * (H - M.t - M.b);
  const camino = (pts) => {
    let d = '', dentro = false;
    for (const [T, s] of pts) {
      if (s == null) { dentro = false; continue; }
      d += `${dentro ? 'L' : 'M'}${X(T).toFixed(1)} ${Y(s).toFixed(1)}`;
      dentro = true;
    }
    return d;
  };
  const marcasY = $derived.by(() => { const n = yHi - yLo, paso = n > 6 ? 2 : 1; const out = []; for (let v = yLo; v <= yHi; v += paso) out.push(v); return out; });
  let hover = $state(null);   // T bajo el ratón
  function mover(ev) {
    const r = ev.currentTarget.getBoundingClientRect();
    const T = Math.round(T0 + ((ev.clientX - r.left - M.l) / (W - M.l - M.r)) * (T1 - T0));
    hover = T >= T0 && T <= T1 ? T : null;
  }
  const fmtM = (T) => (T === 0 ? 'disparo' : (T > 0 ? '+' : '−') + Math.abs(T) + ' s.');
</script>

<section class="tarjeta bloque">
  <h3>Aceleración en la salida</h3>
  <p class="sub">SOG del GPS de −60 s. a +60 s. del disparo. La tabla fija momentos comparables.</p>
  {#if velas.length <= 12}
    <div class="leyenda">{#each velas as v}<span class:yo={v === ref}><i style:background={colores[v]}></i>{velaCorta(v, nombres)}</span>{/each}</div>
  {/if}
  <div bind:clientWidth={W}>
    <svg viewBox={`0 0 ${W} ${H}`} style:height={H + 'px'} role="img" aria-label="SOG alrededor del disparo"
         onpointermove={mover} onpointerleave={() => (hover = null)}>
      {#each marcasY as v}
        <line x1={M.l} x2={W - M.r} y1={Y(v)} y2={Y(v)} class="rej" />
        <text x={M.l - 6} y={Y(v) + 4} class="eje" text-anchor="end">{v}</text>
      {/each}
      {#each [-60, -30, 0, 30, 60] as T}
        <line x1={X(T)} x2={X(T)} y1={M.t} y2={H - M.b} class="rej" class:disparo={T === 0} />
        <text x={X(T)} y={H - 8} class="eje" text-anchor="middle">{T === 0 ? 'disparo' : (T > 0 ? '+' : '') + T + ' s.'}</text>
      {/each}
      <text x={M.l - 6} y={M.t - 3} class="eje" text-anchor="end">kn.</text>
      {#each [...series].reverse() as s (s.v)}
        <path d={camino(s.pts)} fill="none" stroke={colores[s.v]} stroke-width={s.v === ref ? 2.5 : 1.5} stroke-opacity={s.v === ref ? 1 : 0.75} />
      {/each}
      {#if hover != null}
        {@const vals = series.map((s) => [s.v, s.pts[(hover - T0) / PASO]?.[1]]).filter(([, x]) => x != null).sort((a, b) => b[1] - a[1]).slice(0, 8)}
        <line x1={X(hover)} x2={X(hover)} y1={M.t} y2={H - M.b} class="cruz" />
        {#each vals as [v, x]}<circle cx={X(hover)} cy={Y(x)} r="3.5" fill={colores[v]} stroke="var(--panel)" stroke-width="1.5" />{/each}
        <g transform={`translate(${X(hover) > W / 2 ? X(hover) - 168 : X(hover) + 8}, ${M.t})`}>
          <rect width="160" height={18 + vals.length * 14} rx="3" class="tip" />
          <text x="8" y="14" class="tiptxt b">{fmtM(hover)}</text>
          {#each vals as [v, x], k}<text x="8" y={28 + k * 14} class="tiptxt">{velaCorta(v, nombres)}: {num(x, 2)} kn.</text>{/each}
        </g>
      {/if}
    </svg>
  </div>
  <div class="rodillo">
    <table class="mini">
      <thead><tr><th>Barco</th>{#each MOMENTOS as T}<th class="n">{fmtM(T)}</th>{/each}</tr></thead>
      <tbody>
        {#each filas as f (f.v)}
          <tr class:yo={f.v === ref}>
            <td><span class="punto" style:background={colores[f.v]}></span>{velaCorta(f.v, nombres)}</td>
            {#each f.sog as s}<td class="n num">{s == null ? '—' : num(s, 2) + ' kn.'}</td>{/each}
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
  <Nota>Velocidad sobre el fondo (GPS), no velocidad en el agua: con corriente cambia de forma parecida para todos los barcos cercanos. Sirve para ver quién llega lanzado al disparo y quién tiene que acelerar después.</Nota>
</section>

<style>
  .bloque { padding: 10px 12px; min-width: 0; }
  h3 { font-size: 15px; letter-spacing: .06em; text-transform: uppercase; color: var(--tinta-2); margin-bottom: 2px; }
  .sub { margin: 0 0 6px; font-size: 13px; color: var(--tinta-2); }
  svg { width: 100%; display: block; touch-action: pan-y; }
  .rej { stroke: var(--rejilla); stroke-width: 1; }
  .rej.disparo { stroke: var(--tinta-2); stroke-dasharray: 4 3; }
  .eje { font: 500 10px var(--mono); fill: var(--tinta-3); }
  .cruz { stroke: var(--tinta-2); stroke-width: 1; }
  .tip { fill: var(--tinta); opacity: .92; }
  .tiptxt { font: 500 11px var(--mono); fill: var(--panel); }
  .tiptxt.b { font-weight: 700; }
  .leyenda { display: flex; flex-wrap: wrap; gap: 4px 12px; font: 600 12px var(--display); color: var(--tinta-2); margin: 2px 0 4px; }
  .leyenda i { display: inline-block; width: 14px; height: 3px; border-radius: 2px; margin-right: 5px; vertical-align: middle; }
  .leyenda .yo { color: var(--tinta); }
  .rodillo { overflow-x: auto; margin-top: 6px; }
  table.mini { border-collapse: collapse; width: 100%; font-size: 13px; }
  .mini th { font: 600 11px var(--display); letter-spacing: .05em; text-transform: uppercase; color: var(--tinta-2); text-align: left; padding: 4px 8px; border-bottom: 1px solid var(--linea); white-space: nowrap; }
  .mini td { padding: 4px 8px; border-bottom: 1px solid var(--rejilla); white-space: nowrap; }
  .mini .n { text-align: right; }
  .mini tr.yo td { background: color-mix(in srgb, var(--yo) 14%, transparent); font-weight: 600; }
  .punto { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; }
</style>
