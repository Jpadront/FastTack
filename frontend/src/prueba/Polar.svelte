<script>
  // Frente a tus vecinos: ángulo al viento, SOG y VMG del barco de referencia frente a los barcos que
  // tenía al lado (misma amura, a menos de 300 m., en los mismos 30 s.: mismo viento), y lo mismo del
  // top 5. Sustituye a la polar: sin anemómetro, el ángulo de máxima VMG no se puede medir (ver Nota).
  import Nota from '../Nota.svelte';
  import { num, mediana } from './datos.js';

  let { tramo, ref, nombreRef = '', top5 = [] } = $props();
  const popa = $derived(tramo.tipo === 'popa');
  const mio = $derived(tramo.barcos[ref]?.vecinos ?? null);
  const de5 = $derived(top5.map((v) => tramo.barcos[v]?.vecinos).filter(Boolean));
  const t5 = $derived(de5.length >= 2 ? {
    twa_frente_vecinos: mediana(de5.map((x) => x.twa_frente_vecinos)),
    sog_frente_vecinos_pct: mediana(de5.map((x) => x.sog_frente_vecinos_pct)),
    vmg_frente_vecinos_pct: mediana(de5.map((x) => x.vmg_frente_vecinos_pct)),
  } : null);
  const ang = (d) => (d == null ? '—' : Math.abs(d) < 0.5 ? 'igual' : `${num(Math.abs(d), 1)}° más ${d > 0 ? (popa ? 'bajo' : 'abierto') : (popa ? 'alto' : 'cerrado')}`);
  const pct = (p) => (p == null ? '—' : Math.abs(p) < 0.5 ? 'igual' : `${p > 0 ? '+' : '−'}${num(Math.abs(p), 1)} %`);
</script>

{#if mio}
<section class="tarjeta bloque">
  <h3>Frente a tus vecinos <span class="est">estimado</span></h3>
  <table>
    <thead><tr><th></th><th>Ángulo al viento</th><th>SOG</th><th>VMG</th></tr></thead>
    <tbody>
      <tr class="yo"><td>{nombreRef}</td><td class="num">{ang(mio.twa_frente_vecinos)}</td><td class="num" class:mal={mio.sog_frente_vecinos_pct <= -1} class:bien={mio.sog_frente_vecinos_pct >= 1}>{pct(mio.sog_frente_vecinos_pct)}</td><td class="num" class:mal={mio.vmg_frente_vecinos_pct <= -1} class:bien={mio.vmg_frente_vecinos_pct >= 1}>{pct(mio.vmg_frente_vecinos_pct)}</td></tr>
      {#if t5}<tr><td>Top 5</td><td class="num">{ang(t5.twa_frente_vecinos)}</td><td class="num">{pct(t5.sog_frente_vecinos_pct)}</td><td class="num">{pct(t5.vmg_frente_vecinos_pct)}</td></tr>{/if}
    </tbody>
  </table>
  <p class="sub">Mediana de {mio.segmentos} tramos de 30 s. navegando estable, frente a los barcos en tu misma amura a menos de 300 m. en esos mismos 30 s. (tienen tu mismo viento).</p>
  <Nota>Sustituye a la polar del tramo. Sin anemómetro, el ángulo de máxima VMG no se puede medir: comparando cada barco consigo mismo, cuando parece ir 4–8° más cerrado que sus vecinos su SOG apenas cambia y su VMG sube un 5–11 %. Un barco que de verdad ciñe 8° más cerrado pierde mucha velocidad, así que esas diferencias son viento local (roles que los de al lado no tienen), no el timón, y la «polar» siempre daba la máxima VMG en el ángulo más cerrado. Lo que sí es fiable, con muchos tramos de 30 s., es si navegas más abierto o más cerrado, más rápido o más lento, que los barcos que tienes al lado.</Nota>
</section>
{/if}

<style>
  .bloque { padding: 10px 12px; min-width: 0; }
  h3 { font-size: 15px; letter-spacing: .06em; text-transform: uppercase; color: var(--tinta-2); margin: 0 0 6px; }
  .est { color: var(--estimado); font-size: 11px; }
  table { border-collapse: collapse; width: 100%; font-size: 14px; }
  th { text-align: left; font: 600 12px var(--display); color: var(--tinta-3); text-transform: uppercase; letter-spacing: .04em; padding: 2px 8px 4px 0; }
  td { padding: 4px 8px 4px 0; border-top: 1px solid var(--rejilla); }
  tr.yo td { font-weight: 600; }
  .mal { color: var(--error, #c62828); }
  .bien { color: #1c5cab; }
  .sub { margin: 6px 0 0; font-size: 13px; color: var(--tinta-2); }
</style>
