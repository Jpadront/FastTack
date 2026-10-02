<script>
  import Nota from '../Nota.svelte';
  // Escora óptima de un tramo: la media de la escora de los 5 barcos con más VMG (cifra principal),
  // frente a la del barco de referencia, y el gráfico de VMG (y SOG) relativa a los vecinos por
  // franja de escora, con esa óptima marcada. En popa, con signo (+ a sotavento, − a barlovento).
  import { num, COLOR_YO } from './datos.js';

  let { tramo, ref, nombreRef = '', titulo = null, enRangoTexto = null, nota = '', nombres = (v) => v } = $props();
  const popa = $derived(tramo.tipo !== 'ceñida');   // popa y largo: escora con signo
  const campo = $derived(popa ? 'escora_sotavento' : 'escora');
  const tituloV = $derived(titulo ?? (popa ? 'Escora óptima en popa' : 'Escora óptima en ceñida'));
  const o = $derived(tramo.escora_optima ?? {});   // sin óptima: el bloque dice por qué en lugar de desaparecer
  const c = $derived(o.curva ?? null);
  const b = $derived(tramo.barcos[ref] ?? {});
  const mia = $derived(b[campo] ?? null);
  const frente = $derived(b.escora_frente_optima ?? null);
  const enRango = $derived(b.escora_en_rango_pct ?? null);
  const g = (x) => (x == null ? '—' : num(x, 1).replace(/,0$/, '') + '°');
  const lectura = $derived(frente == null ? '' : Math.abs(frente) <= 2 ? 'en la óptima' : frente > 0 ? 'más escorado' : 'más plano');

  const W0 = 520, H = 170, M = { l: 46, r: 12, t: 12, b: 30 };
  let W = $state(W0);
  const fr = $derived(c ? c.franjas : []);
  const xLo = $derived(fr.length ? fr[0].desde : 0);
  const xHi = $derived(fr.length ? fr[fr.length - 1].hasta : 1);
  const yVals = $derived(fr.map((f) => f.vmg_rel_pct));
  const yTodos = $derived([...yVals, ...fr.map((f) => f.sog_rel_pct).filter((x) => x != null)]);
  const yLo = $derived(Math.min(...yTodos, 99) - 1), yHi = $derived(Math.max(...yTodos, 100) + 1);
  const X = (e) => M.l + ((e - xLo) / (xHi - xLo)) * (W - M.l - M.r);
  const Y = (v) => H - M.b - ((v - yLo) / (yHi - yLo)) * (H - M.t - M.b);
  let hover = $state(null);
  const clamp = (e) => Math.max(xLo, Math.min(xHi, e));
</script>

<section class="tarjeta bloque">
  <h3>{tituloV} <span class="est">estimada</span></h3>
  {#if o.escora != null}
    <div class="cifras">
      <div><span class="etq">Los 5 con más VMG</span><b class="num">{g(o.escora)}</b>{#if o.rango}<small class="tenue">entre {g(o.rango[0])} y {g(o.rango[1])}</small>{/if}</div>
      <div><span class="etq">{nombreRef}</span><b class="num">{g(mia)}</b>{#if frente != null}<small class:mal={Math.abs(frente) > 2}>{frente > 0 ? '+' : ''}{g(frente)} · {lectura}</small>{/if}</div>
      {#if enRangoTexto || enRango != null}<div><span class="etq">Cerca de la óptima</span><b class="num">{enRangoTexto ?? enRango + ' %'}</b><small class="tenue">{enRangoTexto ? '' : 'del tiempo a ±2°'}</small></div>{/if}
    </div>
  {:else}
    <p class="sub">Sin escora óptima en este tramo: hacen falta al menos 3 barcos con datos de escora fiables{Object.keys(tramo.barcos).length < 3 ? ` (solo hay ${Object.keys(tramo.barcos).length})` : ''}. {nombreRef}: <b class="num">{g(mia)}</b>.</p>
  {/if}
  {#if popa}<p class="sub">En popa, escora con signo: <b>+</b> a sotavento, <b>−</b> a barlovento.</p>{/if}
  {#if c}
  <div class="leyenda"><span><i class="l-vmg"></i>VMG</span><span><i class="l-sog"></i>SOG</span><span><i class="l-rango"></i>franjas sin pérdida</span><span><i class="l-yo"></i>{nombreRef}</span><span><i class="l-top5"></i>óptima (5 con más VMG)</span></div>
    <div bind:clientWidth={W}>
    <svg viewBox={`0 0 ${W} ${H}`} style:height={H + 'px'} role="img" aria-label="VMG relativa por franja de escora">
      <rect x={X(c.rango[0])} y={M.t} width={Math.max(0, X(c.rango[1]) - X(c.rango[0]))} height={H - M.t - M.b} class="rango" />
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
        <circle cx={X((f.desde + f.hasta) / 2)} cy={Y(f.vmg_rel_pct)} r="5" class="punto" class:dentro={f.desde >= c.rango[0] && f.hasta <= c.rango[1]}
                role="presentation" onpointerenter={() => (hover = k)} onpointerleave={() => (hover = null)} />
      {/each}
      {#if o.escora != null}<line x1={X(clamp(o.escora))} x2={X(clamp(o.escora))} y1={M.t} y2={H - M.b} class="top5" /><text x={X(clamp(o.escora)) + 4} y={M.t + 10} class="eje">5 con más VMG</text>{/if}
      {#if mia != null}<line x1={X(clamp(mia))} x2={X(clamp(mia))} y1={M.t} y2={H - M.b} stroke={COLOR_YO} stroke-width="2" /><text x={X(clamp(mia)) + 4} y={M.t + 22} class="eje yo">{nombreRef}</text>{/if}
      {#if hover != null}
        {@const f = fr[hover]}
        <g transform={`translate(${Math.min(X(f.hasta) + 6, W - 206)}, ${M.t + 30})`}><rect width="200" height="34" rx="3" class="tip" />
          <text x="6" y="14" class="tiptxt">{f.desde}–{f.hasta}°: VMG {num(f.vmg_rel_pct, 1)} % · SOG {num(f.sog_rel_pct, 1)} %</text>
          <text x="6" y="27" class="tiptxt">{f.segmentos} tramos de 30 s. · {f.barcos} barcos</text></g>
      {/if}
    </svg>
  </div>
  {/if}
  {#if o.barcos?.length}<p class="sub">Los 5 con más VMG: {o.barcos.map(nombres).join(', ')}.</p>{/if}
  {#if nota}<p class="sub">{nota}</p>{/if}
  <Nota>Óptima = la media de la escora de los 5 barcos con más VMG del tramo, navegando estable (sin maniobras ni rodeos; no cuentan los sensores a más de 6° de la mediana de la flota). El gráfico da el contexto: cada punto es la VMG (y SOG) media de la flota en esa franja de escora, en % de la de sus vecinos (misma amura, a menos de 300 m., en los mismos 30 s: así se quitan la presión y las roladas). Si con más escora la SOG sube y la VMG baja, se va más rápido pero más abierto; si bajan las dos, falta potencia. Sombreado: franjas sin pérdida clara frente a la mejor. Es una referencia: la escora también depende del peso y del estilo de cada tripulación.</Nota>
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
  .cifras { display: flex; flex-wrap: wrap; gap: 8px 28px; margin-bottom: 4px; }
  .cifras > div { display: grid; gap: 1px; }
  .etq { font: 600 12px var(--display); color: var(--tinta-3); text-transform: uppercase; letter-spacing: .04em; }
  .cifras b { font-size: 22px; }
  .cifras small { font-size: 12px; color: var(--tinta-2); }
  .cifras small.mal { color: var(--error, #c62828); }
</style>
