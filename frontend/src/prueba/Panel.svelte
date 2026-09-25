<script>
  import { instantaneos, twsEn, tramoEn, fmtT, num, dif, velaCorta, colorBarco, presionEn } from './datos.js';

  let { an, pistas, T, sel, ref, tramo = null, desfaseMs = 0, nombres = {} } = $props();

  const tr = $derived(tramo ?? tramoEn(an, T));
  const inst = $derived(instantaneos(an, pistas, tr, T));
  const tws = $derived(twsEn(tr, T, an.senal));
  const mediaTwd = $derived(tr.viento.twd_media);
  const pres = $derived(presionEn(an, pistas, tr, T));
  // Diferencia de presión izquierda − derecha (mirando a barlovento), en SOG mediano; umbral: 3 % de la mediana
  const lr = $derived.by(() => {
    if (pres.lr == null) return null;
    const u = 0.03 * pres.med;
    return { d: pres.lr, lado: Math.abs(pres.lr) < u ? null : pres.lr > 0 ? 'izquierda' : 'derecha' };
  });
  const filas = $derived(inst.filas.filter((f) => sel.has(f.vela)).slice(0, 15));
  const progreso = $derived(Math.max(0, Math.min(100, ((T * 1000 + an.senal - tr.t0) / (tr.t1 - tr.t0)) * 100)));
  const hora = $derived.by(() => {
    const d = new Date(an.senal + T * 1000 + desfaseMs);
    return [d.getUTCHours(), d.getUTCMinutes(), d.getUTCSeconds()].map((n) => String(n).padStart(2, '0')).join(':');
  });
</script>

<section class="tarjeta panel">
  <div class="cab">
    <div><span class="etiqueta">Valores instantáneos</span><div class="num hora">{hora} <span class="tenue">{fmtT(T)} desde la señal</span></div></div>
  </div>
  <div class="kv">
    <div><i>TWD <span class="est">est.</span></i><b class="num">{num(inst.twd, 0)}°</b><small class="num">{dif(inst.twd - mediaTwd) >= 0 ? '+' : ''}{num(dif(inst.twd - mediaTwd), 1)}° vs media</small></div>
    <div><i>TWS <span class="est">est.</span></i>{#if tws != null}<b class="num">{num(tws, 1)} kn</b>{:else}<b class="tenue sin">sin calibrar</b><small>añade el viento de referencia</small>{/if}</div>
    <div><i>Tramo</i><b>{tr.nombre}</b><small class="num">{num(progreso, 0)} % del líder</small></div>
  </div>
  <div class="lr">
    <i>Presión izq.–dcha. <span class="est">est.</span></i>
    {#if lr}<span>{lr.lado ? 'más presión a la ' + lr.lado : 'equilibrada'} <span class="num tenue">({lr.d >= 0 ? '+' : ''}{num(lr.d, 2)} kn de SOG, mirando a barlovento)</span></span>
    {:else}<span class="tenue">pocos barcos con datos en el tramo</span>{/if}
  </div>
  <div class="rodillo">
    <table>
      <thead><tr><th class="n">#</th><th>Barco</th><th class="n">Δm</th><th class="n">SOG</th><th class="n">VMG<span class="est">*</span></th><th class="n">TWA<span class="est">*</span></th><th class="n">COG</th><th class="n">HDG</th></tr></thead>
      <tbody>
        {#each filas as f (f.vela)}
          <tr class:yo={f.vela === ref} class:tenue={f.sinDatos}>
            <td class="n num">{f.pos}</td>
            <td><span class="punto" style:background={colorBarco(f.vela, ref)}></span>{velaCorta(f.vela, nombres)}{#if f.otro}<span class="otro">{f.suyo}</span>{/if}</td>
            <td class="n num">{f.dm == null ? '—' : num(f.dm, 0)}</td>
            <td class="n num">{f.sinDatos ? 'sin datos' : num(f.sog, 2)}</td>
            <td class="n num">{num(f.vmg, 2)}</td>
            <td class="n num">{f.twa == null ? '—' : num(f.twa, 0) + '°'}</td>
            <td class="n num">{f.cog == null ? '—' : num(f.cog, 0) + '°'}</td>
            <td class="n num">{f.hdg == null ? '—' : num(f.hdg, 0) + '°'}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
  <p class="nota">* TWA y VMG: ángulo táctico GPS (COG frente a la TWD reconstruida), cada barco en su propio tramo (etiqueta gris si no es el del panel; «rodeo» = rodeando una baliza o en el offset). RaceSense no tiene sensor de viento. HDG tal cual el dispositivo.</p>
</section>

<style>
  .panel { padding: 10px 12px; display: grid; gap: 8px; align-content: start; }
  .hora { font-size: 15px; font-weight: 500; }
  .kv { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
  .kv div { display: grid; gap: 1px; }
  .kv i { font: 600 11px var(--display); letter-spacing: .06em; text-transform: uppercase; color: var(--tinta-2); font-style: normal; }
  .kv b { font-size: 17px; font-weight: 600; }
  .kv b.sin { font-size: 14px; }
  .kv small { font-size: 12px; color: var(--tinta-3); }
  .est { color: var(--estimado); font-size: 10px; margin-left: 2px; }
  .lr { font-size: 13px; display: flex; gap: 6px; flex-wrap: wrap; align-items: baseline; }
  .lr i { font: 600 11px var(--display); letter-spacing: .06em; text-transform: uppercase; color: var(--tinta-2); font-style: normal; }
  .rodillo { overflow-x: auto; }
  table { border-collapse: collapse; width: 100%; font-size: 13px; }
  th { font: 600 11px var(--display); letter-spacing: .05em; text-transform: uppercase; color: var(--tinta-2); text-align: left; padding: 4px 6px; border-bottom: 1px solid var(--linea); white-space: nowrap; }
  td { padding: 4px 6px; border-bottom: 1px solid var(--rejilla); white-space: nowrap; }
  .n { text-align: right; }
  .otro { margin-left: 5px; font: 600 10px var(--display); color: var(--tinta-3); text-transform: uppercase; letter-spacing: .04em; }
  tr.yo td { background: color-mix(in srgb, var(--yo) 14%, transparent); font-weight: 600; }
  tr.tenue td { color: var(--tinta-3); }
  .punto { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; }
  .nota { font-size: 12px; color: var(--tinta-3); margin: 0; }
</style>
