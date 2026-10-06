<script>
  // Rosa de la TWD de un tramo: el ángulo es la dirección real del viento (sin exagerar) y la
  // distancia al centro, el avance del tramo (anillo interior = inicio, borde = final; no se empieza
  // en el centro porque ahí los ángulos no se distinguen). La rosa se gira para
  // que la TWD media quede arriba, como mirando a barlovento: un punto a la derecha de la media es
  // viento rolado a la derecha. Solo se dibuja el sector que hace falta (±30° como mínimo).
  import { num, dif, twdEn } from './datos.js';

  let { tramo, T, senalMs } = $props();
  const R = 200, R0 = 60;
  const cortes = $derived(tramo.viento.cortes);
  const media = $derived(tramo.viento.twd_media);
  const rel = $derived(cortes.map((c) => dif(c.twd - media)));
  const A = $derived(Math.min(180, Math.max(30, Math.ceil((Math.max(...rel.map(Math.abs)) + 5) / 10) * 10)));
  // geometría: centro abajo (fuera del dibujo); si el sector pasa de 90° la rosa crece por debajo
  const ANCHO = $derived(2 * R * Math.sin((Math.min(A, 90) * Math.PI) / 180) + 90);
  const cx = $derived(ANCHO / 2), cy = R + 34;
  const ALTO = $derived(cy - (A <= 90 ? R0 : R) * Math.cos((A * Math.PI) / 180) + 14);
  const rad = (p) => R0 + ((R - R0) * p) / 100;
  const xy = (g, r) => [cx + r * Math.sin((g * Math.PI) / 180), cy - r * Math.cos((g * Math.PI) / 180)];
  const arco = (r, a0, a1) => { const [x0, y0] = xy(a0, r), [x1, y1] = xy(a1, r); return `M${x0} ${y0}A${r} ${r} 0 ${a1 - a0 > 180 ? 1 : 0} 1 ${x1} ${y1}`; };
  // sector de corona entre el anillo de inicio (R0) y el radio r
  const cuña = (r, a0, a1) => { const [x, y] = xy(a1, R0), [x0, y0] = xy(a0, R0);
    return `${arco(r, a0, a1)}L${x} ${y}A${R0} ${R0} 0 ${a1 - a0 > 180 ? 1 : 0} 0 ${x0} ${y0}Z`; };
  const norte = (g) => Math.round(((g % 360) + 360) % 360);
  // marcas cada 5° (o 10° si el sector es grande) en grados reales de la rosa
  const paso = $derived(A > 60 ? 10 : 5), cada = $derived(A > 60 ? 30 : 10);
  const marcas = $derived.by(() => {
    const out = [];
    for (let g = Math.ceil((media - A) / paso) * paso; g <= media + A + 1e-6; g += paso) out.push({ g, r: g - media, etq: norte(g) % cada === 0 });
    return out;
  });
  const pts = $derived(cortes.map((c, k) => { const [x, y] = xy(rel[k], rad(c.pct)); return { x, y, c, op: 0.3 + (0.7 * k) / Math.max(1, cortes.length - 1) }; }));
  const traza = $derived(pts.map((p, k) => (k ? 'L' : 'M') + p.x.toFixed(1) + ' ' + p.y.toFixed(1)).join(''));
  const lo = $derived(Math.min(...rel)), hi = $derived(Math.max(...rel));
  const delta = $derived(dif(cortes[cortes.length - 1].twd - cortes[0].twd));
  const pct = $derived(Math.max(0, Math.min(100, ((T * 1000 + senalMs - tramo.t0) / (tramo.t1 - tramo.t0)) * 100)));
  const ahora = $derived(xy(dif(twdEn(tramo, T, senalMs) - media), rad(pct)));
  let hover = $state(null);
  const lado = (d) => (Math.abs(d) < 0.5 ? 'sin rolada neta' : `${num(Math.abs(d), 0)}° a la ${d > 0 ? 'derecha' : 'izquierda'}`);
</script>

<div class="rosa">
  <div class="tit">TWD · rosa del tramo</div>
  <svg viewBox={`0 0 ${ANCHO} ${ALTO}`} style:width={`${ANCHO}px`} role="img" aria-label={`Rosa de la TWD: de ${norte(cortes[0].twd)}° a ${norte(cortes[cortes.length - 1].twd)}°, ${lado(delta)}`}>
    <path d={cuña(R, -A, A)} class="fondo" />
    <path d={cuña(R, lo, hi)} class="rango" />
    {#each [25, 50, 75, 100] as p}<path d={arco(rad(p), -A, A)} class="anillo" />{/each}
    {#each marcas as m}
      {@const [x0, y0] = xy(m.r, R)}{@const [x1, y1] = xy(m.r, R + (m.etq ? 7 : 4))}{@const [xt, yt] = xy(m.r, R + 17)}
      <line x1={x0} y1={y0} x2={x1} y2={y1} class="marca" />
      {#if m.etq}<text x={xt} y={yt + 4} class="eje" text-anchor="middle">{norte(m.g)}°</text>{/if}
    {/each}
    {#each [0, 25, 50, 75] as p}{@const [x, y] = xy(-A, rad(p))}<text x={x - 7} y={y + 3} class="eje peq" text-anchor="end">{p} %</text>{/each}
    <line x1={cx} y1={cy - R0} x2={xy(0, R)[0]} y2={xy(0, R)[1]} class="media" />
    <path d={traza} class="linea" />
    {#each pts as p, k}
      <circle cx={p.x} cy={p.y} r={p.c.fuente === 'arrastre' ? 3 : 4.5} class="punto" class:arrastre={p.c.fuente === 'arrastre'} style:fill-opacity={p.c.fuente === 'arrastre' ? 1 : p.op} />
      <circle cx={p.x} cy={p.y} r="12" class="diana" role="presentation" onpointerenter={() => (hover = k)} onpointerleave={() => (hover = null)} />
    {/each}
    <path d={arco(rad(pct), -A, A)} class="cursor" />
    <circle cx={ahora[0]} cy={ahora[1]} r="5" class="ahora" />
    {#if hover != null}
      {@const p = pts[hover]}
      <g transform={`translate(${Math.max(4, Math.min(p.x - 56, ANCHO - 116))}, ${Math.max(2, p.y - 30)})`}>
        <rect width="112" height="20" rx="3" class="tip" /><text x="56" y="14" class="tiptxt" text-anchor="middle">{p.c.pct} % · {norte(p.c.twd)}°</text>
      </g>
    {/if}
  </svg>
  <div class="pie">
    <span><i>← máx. izquierda</i><b>{norte(media + lo)}°</b> <small>({lo > 0 ? '+' : lo < 0 ? '−' : '±'}{num(Math.abs(lo), 0)}°)</small></span>
    <span class="med"><i>media</i><b>{norte(media)}°</b></span>
    <span class="der"><i>máx. derecha →</i><b>{norte(media + hi)}°</b> <small>({hi > 0 ? '+' : hi < 0 ? '−' : '±'}{num(Math.abs(hi), 0)}°)</small></span>
  </div>
  <p class="res">De <b>{norte(cortes[0].twd)}°</b> a <b>{norte(cortes[cortes.length - 1].twd)}°</b>: {lado(delta)} · horquilla {num(hi - lo, 0)}°</p>
</div>

<style>
  .rosa { display: flex; flex-direction: column; align-items: center; }
  .tit { font: 600 12px var(--display); color: var(--tinta-2); align-self: flex-start; }
  svg { max-width: 100%; height: auto; display: block; }
  .fondo { fill: var(--agua); fill-opacity: .45; stroke: var(--linea); }
  .rango { fill: var(--estimado); fill-opacity: .1; }
  .anillo { fill: none; stroke: var(--rejilla); stroke-width: 1; }
  .marca { stroke: var(--tinta-3); stroke-width: 1; }
  .eje { font: 500 10px var(--mono); fill: var(--tinta-3); }
  .eje.peq { font-size: 9px; }
  .media { stroke: var(--tinta-3); stroke-width: 1; stroke-dasharray: 4 3; }
  .linea { fill: none; stroke: var(--estimado); stroke-width: 2; stroke-linejoin: round; }
  .punto { fill: var(--estimado); stroke: var(--panel); stroke-width: 2; }
  .punto.arrastre { fill: var(--panel); stroke: var(--estimado); stroke-width: 1.5; }
  .diana { fill: transparent; }
  .cursor { fill: none; stroke: var(--tinta); stroke-width: 1; stroke-dasharray: 2 3; }
  .ahora { fill: var(--tinta); stroke: var(--panel); stroke-width: 2; }
  .tip { fill: var(--tinta); }
  .tiptxt { font: 500 11px var(--mono); fill: var(--panel); }
  .pie { display: grid; grid-template-columns: 1fr auto 1fr; gap: 10px; align-items: baseline; width: 100%; max-width: 440px; font: 500 11px var(--mono); color: var(--tinta-3); }
  .pie b { color: var(--tinta-2); font-weight: 700; }
  .pie small { font-size: 10px; }
  .pie .der { text-align: right; }
  .pie i { display: block; font-style: normal; }
  .pie .med { text-align: center; }
  .med { color: var(--tinta-2); }
  .res { font-size: 13px; color: var(--tinta-2); margin: 4px 0 0; text-align: center; }
</style>
