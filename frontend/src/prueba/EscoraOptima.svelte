<script>
  // Escora óptima de una ceñida: VMG relativa a la flota por franja de escora (un eje, en %), con el
  // rango óptimo sombreado, la escora mediana del barco de referencia y la del top 5.
  import { num, mediana, COLOR_YO } from './datos.js';

  let { tramo, ref, top5 = [], nombreRef = '' } = $props();
  const o = $derived(tramo.escora_optima);
  const W0 = 520, H = 170, M = { l: 46, r: 12, t: 12, b: 30 };
  let W = $state(W0);
  const fr = $derived(o.franjas);
  const xLo = $derived(fr[0].desde), xHi = $derived(fr[fr.length - 1].hasta);
  const yVals = $derived(fr.map((f) => f.vmg_rel_pct));
  const yTodos = $derived([...yVals, ...fr.map((f) => f.sog_rel_pct).filter((x) => x != null)]);
  const yLo = $derived(Math.min(...yTodos, 99) - 1), yHi = $derived(Math.max(...yTodos, 100) + 1);
  const X = (e) => M.l + ((e - xLo) / (xHi - xLo)) * (W - M.l - M.r);
  const Y = (v) => H - M.b - ((v - yLo) / (yHi - yLo)) * (H - M.t - M.b);
  const mia = $derived(tramo.barcos[ref]?.escora ?? null);
  const enRango = $derived(tramo.barcos[ref]?.escora_en_rango_pct ?? null);
  const esc5 = $derived(mediana(top5.map((v) => tramo.barcos[v]?.escora).filter((x) => x != null)));
  const franjaMia = $derived(mia == null ? null : fr.find((f) => mia >= f.desde && mia < f.hasta));
  const mejorV = $derived(Math.max(...yVals));
  let hover = $state(null);
  const clamp = (e) => Math.max(xLo, Math.min(xHi, e));
</script>

<section class="tarjeta bloque">
  <h3>Escora óptima en ceñida <span class="est">estimada</span></h3>
  {#if o.concluyente}
    <p class="titular">Rango óptimo <b>{o.rango[0]}–{o.rango[1]}°</b> (mejor franja {o.mejor[0]}–{o.mejor[1]}°).
      {#if o.debajo}Por debajo de {o.debajo.hasta_grados}°, <b>−{num(o.debajo.perdida_pct, 1)} %</b> de VMG frente a los vecinos.{/if}
      {#if o.encima}Por encima de {o.encima.desde_grados}°, <b>−{num(o.encima.perdida_pct, 1)} %</b>.{/if}</p>
  {:else}
    <p class="titular">En este tramo la escora <b>no marca diferencias</b> entre {o.rango[0]} y {o.rango[1]}° (la mejor franja, {o.mejor[0]}–{o.mejor[1]}°, no se distingue de las demás).</p>
  {/if}
  {#if o.sobreescora}<p class="titular">Por encima de {o.sobreescora.desde_grados}° se va más rápido (SOG {num(o.sobreescora.sog_rel_pct, 1)} %) pero se pierde altura: la VMG baja a {num(o.sobreescora.vmg_rel_pct, 1)} %.</p>{/if}
  <p class="sub">{nombreRef}: escora mediana <b class="num">{mia == null ? '—' : num(mia, 0) + '°'}</b>{#if enRango != null}, {enRango} % del tiempo en el rango{/if}{#if franjaMia && franjaMia.vmg_rel_pct < mejorV} · su franja, {num(franjaMia.vmg_rel_pct - mejorV, 1)} % frente a la mejor{/if} · top 5: <b class="num">{esc5 == null ? '—' : num(esc5, 0) + '°'}</b></p>
  <div class="leyenda"><span><i class="l-vmg"></i>VMG</span><span><i class="l-sog"></i>SOG</span><span><i class="l-rango"></i>rango óptimo</span><span><i class="l-yo"></i>{nombreRef}</span><span><i class="l-top5"></i>top 5</span></div>
  <div bind:clientWidth={W}>
    <svg viewBox={`0 0 ${W} ${H}`} style:height={H + 'px'} role="img" aria-label="VMG relativa por franja de escora">
      <rect x={X(o.rango[0])} y={M.t} width={X(o.rango[1]) - X(o.rango[0])} height={H - M.t - M.b} class="rango" />
      {#each [yLo + 1, 100, yHi - 1] as v}
        <line x1={M.l} x2={W - M.r} y1={Y(v)} y2={Y(v)} class="rej" class:cien={v === 100} />
        <text x={M.l - 6} y={Y(v) + 4} class="eje" text-anchor="end">{num(v, 0)} %</text>
      {/each}
      {#each fr as f}<text x={X(f.desde)} y={H - 10} class="eje" text-anchor="middle">{f.desde}°</text>{/each}
      <text x={X(xHi)} y={H - 10} class="eje" text-anchor="middle">{xHi}°</text>
      {#if fr[0].sog_rel_pct != null}<path d={fr.map((f, k) => `${k ? 'L' : 'M'}${X((f.desde + f.hasta) / 2)} ${Y(f.sog_rel_pct)}`).join(' ')} class="linea-sog" />
        {#each fr as f}<circle cx={X((f.desde + f.hasta) / 2)} cy={Y(f.sog_rel_pct)} r="3" class="punto-sog" />{/each}{/if}
      <path d={fr.map((f, k) => `${k ? 'L' : 'M'}${X((f.desde + f.hasta) / 2)} ${Y(f.vmg_rel_pct)}`).join(' ')} class="linea" />
      {#each fr as f, k}
        <circle cx={X((f.desde + f.hasta) / 2)} cy={Y(f.vmg_rel_pct)} r="5" class="punto" class:dentro={f.desde >= o.rango[0] && f.hasta <= o.rango[1]}
                role="presentation" onpointerenter={() => (hover = k)} onpointerleave={() => (hover = null)} />
      {/each}
      {#if esc5 != null}<line x1={X(clamp(esc5))} x2={X(clamp(esc5))} y1={M.t} y2={H - M.b} class="top5" /><text x={X(clamp(esc5)) + 4} y={M.t + 10} class="eje">top 5</text>{/if}
      {#if mia != null}<line x1={X(clamp(mia))} x2={X(clamp(mia))} y1={M.t} y2={H - M.b} stroke={COLOR_YO} stroke-width="2" /><text x={X(clamp(mia)) + 4} y={M.t + 22} class="eje yo">{nombreRef}</text>{/if}
      {#if hover != null}
        {@const f = fr[hover]}
        <g transform={`translate(${Math.min(X(f.hasta) + 6, W - 206)}, ${M.t + 30})`}><rect width="200" height="34" rx="3" class="tip" />
          <text x="6" y="14" class="tiptxt">{f.desde}–{f.hasta}°: VMG {num(f.vmg_rel_pct, 1)} % · SOG {num(f.sog_rel_pct, 1)} %</text>
          <text x="6" y="27" class="tiptxt">{f.segmentos} tramos de 30 s · {f.barcos} barcos</text></g>
      {/if}
    </svg>
  </div>
  <p class="nota">Cada punto: VMG (y SOG) media de la flota en esa franja de escora, en % de la de sus vecinos (barcos en la misma amura a menos de 300 m en los mismos 30 s, con el mismo viento: así se quitan la presión y las roladas, también las locales). Tramos de 30 s en rumbo estable, sin rodeos ni maniobras. Si con más escora la SOG sube y la VMG baja, se va más rápido pero más abierto o con más abatimiento; si bajan las dos, falta potencia. Sombreado: rango sin franjas claramente peores que la mejor (≥ 1 % y más que el ruido). Es una asociación en la flota: la escora también depende del peso y del estilo de cada tripulación.</p>
</section>

<style>
  .bloque { padding: 10px 12px; min-width: 0; }
  h3 { font-size: 15px; letter-spacing: .06em; text-transform: uppercase; color: var(--tinta-2); margin-bottom: 4px; }
  .est { color: var(--estimado); font-size: 11px; }
  .titular { margin: 2px 0; font-size: 14px; }
  .sub { margin: 2px 0 6px; font-size: 13px; color: var(--tinta-2); }
  svg { width: 100%; display: block; }
  .rango { fill: color-mix(in srgb, #2a78d6 12%, transparent); }
  .rej { stroke: var(--rejilla); stroke-width: 1; }
  .rej.cien { stroke: var(--linea); }
  .eje { font: 500 10px var(--mono); fill: var(--tinta-3); }
  .eje.yo { fill: var(--tinta-2); }
  .linea { fill: none; stroke: #2a78d6; stroke-width: 2; }
  .punto { fill: #8a969c; stroke: var(--panel); stroke-width: 2; }
  .linea-sog { fill: none; stroke: #8a969c; stroke-width: 1.5; stroke-dasharray: 5 4; }
  .punto-sog { fill: #8a969c; }
  .leyenda { display: flex; flex-wrap: wrap; gap: 4px 12px; font: 600 12px var(--display); color: var(--tinta-2); margin: 2px 0 4px; }
  .leyenda i { display: inline-block; width: 14px; height: 0; margin-right: 5px; vertical-align: middle; border-top: 2px solid; }
  .l-vmg { border-color: #2a78d6 !important; }
  .l-sog { border-top: 2px dashed #8a969c !important; }
  .l-rango { height: 8px !important; border: 0 !important; background: color-mix(in srgb, #2a78d6 18%, transparent); }
  .l-yo { border-color: #e0622e !important; }
  .l-top5 { border-top: 2px dashed var(--tinta-2) !important; }
  .punto.dentro { fill: #2a78d6; }
  .top5 { stroke: var(--tinta-2); stroke-width: 1.5; stroke-dasharray: 4 3; }
  .tip { fill: var(--tinta); }
  .tiptxt { font: 500 11px var(--mono); fill: var(--panel); }
  .nota { font-size: 12px; color: var(--tinta-3); margin: 4px 0 0; }
</style>
