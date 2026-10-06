<script>
  import Nota from '../Nota.svelte';
  // Evolución del viento en un tramo: la TWD en una rosa (RosaViento) y la intensidad en una tira de
  // 10 casillas al estilo de las previsiones: los nudos, la flecha con la rolada frente a la media
  // (mismo giro que la rosa: viento de arriba) y la diferencia con la media del tramo. El color es
  // relativo al tramo (claro = menos presión, oscuro = más): con una escala absoluta de nudos todas
  // las casillas de un tramo saldrían casi iguales. Sin calibrar, la presión es la SOG mediana.
  import { num, dif } from './datos.js';
  import RosaViento from './RosaViento.svelte';

  let { tramo, T, senalMs } = $props();
  const cortes = $derived(tramo.viento.cortes);
  const calibrada = $derived(tramo.viento.tws_calibrada);
  const pct = $derived(Math.max(0, Math.min(100, ((T * 1000 + senalMs - tramo.t0) / (tramo.t1 - tramo.t0)) * 100)));
  const vals = $derived(cortes.map((c) => (calibrada ? c.tws : c.sog_mediana)));
  const validos = $derived(vals.filter((v) => v != null));
  const media = $derived(validos.length ? validos.reduce((a, b) => a + b, 0) / validos.length : null);
  const lo = $derived(Math.min(...validos)), hi = $derived(Math.max(...validos));
  const dec = $derived(calibrada ? 1 : 2);
  const ahora = $derived(cortes.findIndex((c) => Math.abs(c.pct - pct) <= 5));

  const RELATIVA = [[0, [232, 245, 233]], [0.5, [129, 199, 132]], [1, [27, 110, 60]]];
  function mezcla(escala, x) {
    if (x <= escala[0][0]) return escala[0][1];
    for (let k = 1; k < escala.length; k++) {
      const [x1, c1] = escala[k], [x0, c0] = escala[k - 1];
      if (x <= x1) { const f = (x - x0) / (x1 - x0); return c0.map((v, i) => Math.round(v + (c1[i] - v) * f)); }
    }
    return escala[escala.length - 1][1];
  }
  function color(v) {
    if (v == null) return null;
    // horquilla mínima (1 kn. de TWS, 0,3 kn. de SOG) para no pintar como grandes diferencias mínimas
    const span = Math.max(hi - lo, calibrada ? 1 : 0.3), base = (lo + hi) / 2 - span / 2;
    const c = mezcla(RELATIVA, (v - base) / span);
    const claro = (0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]) > 150;
    return { fondo: `rgb(${c.join(',')})`, tinta: claro ? '#10222b' : '#ffffff' };
  }
  const rol = (c) => dif(c.twd - tramo.viento.twd_media);
  const signo = (x, d) => { const r = Number(x.toFixed(d)); return (r > 0 ? '+' : r < 0 ? '−' : '±') + num(Math.abs(r), d); };
  // décimas con más y menos presión
  const kMax = $derived(vals.indexOf(hi)), kMin = $derived(vals.indexOf(lo));
</script>

<section class="tarjeta bloque">
  <h3>Evolución del viento <span class="est">estimado</span></h3>
  <div class="rejilla">
    <RosaViento {tramo} {T} {senalMs} />
    <div class="pres">
      <div class="tit">{calibrada ? 'TWS' : 'Presión: SOG mediana de la flota'} · tira del tramo</div>
      <div class="tira" style:--n={cortes.length} role="table" aria-label="Intensidad del viento por décimas del tramo">
        <div class="fila etq" role="row">{#each cortes as c}<span role="columnheader">{c.pct} %</span>{/each}</div>
        <div class="fila flechas" role="row">
          {#each cortes as c}
            <span role="cell" title={`TWD ${Math.round(((c.twd % 360) + 360) % 360)}° (${signo(rol(c), 0)}° frente a la media)`}>
              <svg viewBox="-10 -10 20 20" aria-hidden="true"><g transform={`rotate(${rol(c)})`}><path d="M0 -7 L0 6 M-3.5 2 L0 6.5 L3.5 2" /></g></svg>
            </span>
          {/each}
        </div>
        <div class="fila valores" role="row">
          {#each cortes as c, k}
            {@const col = color(vals[k])}
            <span role="cell" class:arrastre={c.fuente === 'arrastre'} class:ahora={k === ahora} style:background={col?.fondo} style:color={col?.tinta}
                  title={`${c.pct} %: ${vals[k] == null ? 'sin dato' : num(vals[k], dec) + ' kn.'}${c.fuente === 'arrastre' ? ' (sin datos: valor anterior)' : ''}`}>
              {vals[k] == null ? '—' : num(vals[k], dec)}
            </span>
          {/each}
        </div>
        <div class="fila difs" role="row">{#each vals as v}<span role="cell" class:mas={v != null && v - media >= 0.05} class:menos={v != null && v - media <= -0.05}>{v == null || media == null ? '' : signo(v - media, dec)}</span>{/each}</div>
      </div>
      {#if media != null}
        <p class="res">Media <b>{num(media, dec)} kn.</b> · de {num(lo, dec)} a {num(hi, dec)} kn. · más presión al <b>{cortes[kMax].pct} %</b>, menos al <b>{cortes[kMin].pct} %</b></p>
      {/if}
      <p class="sub">Color relativo al tramo: claro = menos presión, oscuro = más.{calibrada ? '' : ' Sin calibrar: SOG mediana de la flota en kn.'}</p>
    </div>
  </div>
  <Nota>Rosa: el ángulo es la TWD real (girada para que la media quede arriba, mirando a barlovento) y la distancia al centro, el % del tramo (anillo interior = inicio, borde = final); los puntos se oscurecen con el tiempo y el sombreado marca la horquilla. Tira: cada casilla es una décima del tiempo del líder en el tramo; el número son los nudos, la flecha la rolada frente a la media (mismo giro que la rosa) y debajo la diferencia con la media del tramo. Casillas tenues: cortes sin datos suficientes (se arrastra el valor anterior). La casilla recuadrada sigue al reproductor.</Nota>
</section>

<style>
  .bloque { padding: 10px 12px; }
  h3 { font-size: 15px; letter-spacing: .06em; text-transform: uppercase; color: var(--tinta-2); margin-bottom: 4px; }
  .est { color: var(--estimado); font-size: 11px; }
  .rejilla { display: grid; grid-template-columns: minmax(260px, 420px) 1fr; gap: 16px; align-items: center; }
  .pres { min-width: 0; }
  @media (max-width: 720px) { .rejilla { grid-template-columns: 1fr; } }
  .tit { font: 600 12px var(--display); color: var(--tinta-2); margin-bottom: 6px; }
  .tira { display: grid; gap: 2px; }
  .fila { display: grid; grid-template-columns: repeat(var(--n), minmax(0, 1fr)); gap: 2px; text-align: center; }
  .etq span { font: 500 10px var(--mono); color: var(--tinta-3); }
  .flechas svg { width: 22px; height: 22px; display: block; margin: 0 auto; }
  .flechas path { fill: none; stroke: var(--tinta-2); stroke-width: 1.6; stroke-linecap: round; stroke-linejoin: round; }
  .valores span { font: 700 15px var(--mono); padding: 10px 0; border-radius: 3px; border: 2px solid transparent; }
  .valores span.arrastre { opacity: .45; }
  .valores span.ahora { border-color: var(--tinta); }
  .difs span { font: 500 10px var(--mono); color: var(--tinta-3); }
  .difs span.mas { color: #1a7f4b; }
  .difs span.menos { color: #c0392b; }
  .res { font-size: 13px; color: var(--tinta-2); margin: 8px 0 0; }
  .sub { font-size: 12px; color: var(--tinta-3); margin: 4px 0 0; }
  @media (max-width: 480px) { .valores span { font-size: 12px; padding: 8px 0; } .etq span, .difs span { font-size: 8.5px; } }
</style>
