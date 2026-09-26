<script>
  // Maniobras del barco de referencia en un tramo, fase a fase, frente al top 5 de la prueba,
  // y cómo jugó las roladas y el lado del campo (táctica).
  import Nota from '../Nota.svelte';
  import { num, fmtT, mediana } from './datos.js';

  let { tramo, ref, nombreRef, top5 = [], refTop5 = null, senalMs } = $props();
  const f = $derived(tramo.barcos[ref] || {});
  const mans = $derived(tramo.maniobras?.[ref] || []);
  const tac = $derived(f.tactica);
  const tac5 = $derived(top5.map((v) => tramo.barcos[v]?.tactica).filter(Boolean));
  const fav5 = $derived(mediana(tac5.map((t) => t.amura_favorecida_pct).filter((x) => x != null)));
  const tipo = $derived(tramo.tipo === 'ceñida' ? 'virada' : 'trasluchada');
  const n = (v, d = 1, u = '') => (v == null ? '—' : num(v, d) + u);
  const corta = (t) => (t || '').split(' que ')[0].split(':')[0].replace(' (alta)', '').replace(' (baja)', '');
  const signo = (v) => (v == null ? '—' : (v > 0 ? '+' : '') + num(v, 0) + '°');
</script>

<div class="dos">
  <section class="tarjeta bloque">
    <h3>Maniobras de {nombreRef} <span class="est">estimado</span></h3>
    {#if !mans.length}
      <p class="tenue">Sin {tipo}s en este tramo.</p>
    {:else}
      <div class="rodillo"><table class="mini">
        <thead><tr><th>Desde la señal</th><th class="n">Pérdida</th><th class="n">Giro</th><th class="n">Acelera</th><th class="n">SOG entrada → mín. → estable</th><th title="Ángulo al salir frente al top 5 (sin flota: frente a la salida habitual del barco)">Salida</th></tr></thead>
        <tbody>
          {#each mans as m}
            {@const d = m.detalle}
            <tr>
              <td class="num">{fmtT((m.t - senalMs) / 1000)}</td>
              {#if d}
                <td class="n num">{n(d.perdida_m, 0, ' m')} · {n(d.perdida_s, 1, ' s')}</td>
                <td class="n num">{n(d.duracion_giro_s, 0, ' s')}</td>
                <td class="n num">{d.tiempo_aceleracion_s == null ? 'no llega' : n(d.tiempo_aceleracion_s, 0, ' s')}</td>
                <td class="n num">{n(d.sog_entrada_kn, 1)} → {n(d.sog_minima_kn, 1)} → {n(d.sog_salida_estable_kn, 1)} kn</td>
                <td class="salida" title={d.salida || ''}>{#if d.salida_frente_al_top5_grados != null}<span class="num">{signo(d.salida_frente_al_top5_grados)}</span> {corta(d.salida)}{:else}—{/if}{#if d.encadenada} · encadenada{/if}</td>
              {:else}
                <td colspan="5" class="tenue">sin datos suficientes (hueco de telemetría)</td>
              {/if}
            </tr>
          {/each}
        </tbody>
      </table></div>
      {#if refTop5 && refTop5.referencia !== 'su salida habitual'}
        <p class="sub">Top 5 de la prueba ({refTop5.maniobras_top5} {tipo}s medidas): pérdida {n(refTop5.perdida_s_top5, 1, ' s')}, giro {n(refTop5.duracion_giro_s_top5, 0, ' s')}, acelera en {n(refTop5.tiempo_aceleracion_s_top5, 0, ' s')}, caída de velocidad {n(refTop5.caida_sog_pct_top5, 0, ' %')}.</p>
      {/if}
      <Nota>
        <p><b>Giro</b>: desde que la proa se separa 6° del rumbo de entrada hasta que llega (o pasa) a 6° del rumbo de la nueva amura. <b>Acelera</b>: desde el final del giro hasta volver al 95 % de la SOG estable de salida durante 4 s. <b>Pérdida</b>: metros (y segundos) que se habrían avanzado sin maniobrar, desde el inicio del giro hasta estar acelerado; hasta la mitad del giro, a la VMG de entrada y después a la VMG estable de la nueva amura (una rolada o una racha no cuentan como pérdida).</p>
        <p><b>Salida</b>: ángulo al viento en los 10 s tras el giro, respecto al que da más VMG en el tramo, comparado con cómo salen los 5 primeros. En ceñida, salir más cerrado tarda en acelerar y más abierto pierde altura; en popa, más profundo tarda en acelerar y más alto pierde profundidad.</p>
      </Nota>
    {/if}
  </section>
  <section class="tarjeta bloque">
    <h3>Táctica de {nombreRef} <span class="est">estimado</span></h3>
    {#if tac}
      <dl class="datos">
        <dt>En la amura favorecida</dt><dd class="num">{n(tac.amura_favorecida_pct, 0, ' %')} <span class="tenue">· top 5 {n(fav5, 0, ' %')}</span></dd>
        <dt>En la desfavorecida</dt><dd class="num">{n(tac.tiempo_en_amura_desfavorecida_s, 0, ' s')}</dd>
        <dt>{tipo === 'virada' ? 'Viradas' : 'Trasluchadas'} con la rolada</dt><dd class="num">{tac.maniobras_a_favor_de_la_rolada} a favor · {tac.maniobras_en_contra_de_la_rolada} en contra · {tac.maniobras_neutras} neutras</dd>
        <dt>Lado del campo</dt><dd>{tac.lado ?? '—'} <span class="tenue num">({n(tac.derecha_pct, 0, ' %')} a la derecha, hasta {n(tac.separacion_maxima_m, 0, ' m')} del eje)</span></dd>
      </dl>
      <Nota>
        <p><b>Amura favorecida</b>: en cada momento, de las dos amuras posibles con la TWD de ese momento, la que apunta más cerca de la baliza. Navegar en la otra es ir con la rolada en contra. Con la TWD a menos de 3° de la dirección de la baliza, las dos valen igual (no cuenta). Maniobra <b>a favor</b>: pasa de la desfavorecida a la favorecida (virar en el rolón); <b>en contra</b>: al revés. Lado: mirando a barlovento, respecto a la recta entre las balizas del tramo. Depende del viento reconstruido de la flota, que no ve las roladas locales: es orientativo.</p>
      </Nota>
    {:else}
      <p class="tenue">Sin datos suficientes en este tramo.</p>
    {/if}
  </section>
</div>

<style>
  .bloque { padding: 10px 12px; min-width: 0; }
  h3 { font-size: 15px; letter-spacing: .06em; text-transform: uppercase; color: var(--tinta-2); margin: 0 0 6px; }
  .est { color: var(--estimado); font-size: 11px; font-weight: 600; }
  .datos dd.num, td.num { font-variant-numeric: tabular-nums; }
  .datos { display: grid; grid-template-columns: auto 1fr; gap: 6px 14px; margin: 0; font-size: 15px; }
  .datos dt { color: var(--tinta-2); }
  .datos dd { margin: 0; }
  .sub { font-size: 14px; margin: 8px 0 0; color: var(--tinta-2); }
  .dos { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 10px; margin-top: 10px; }
  .rodillo { overflow-x: auto; }
  table.mini { border-collapse: collapse; width: 100%; font-size: 14px; }
  table.mini th { text-align: left; font: 600 12px var(--display); color: var(--tinta-2); padding: 4px 6px; border-bottom: 1px solid var(--linea); white-space: nowrap; }
  table.mini td { padding: 4px 6px; border-bottom: 1px solid var(--rejilla); }
  .n { text-align: right; white-space: nowrap; }
  td.salida { white-space: nowrap; }
</style>
