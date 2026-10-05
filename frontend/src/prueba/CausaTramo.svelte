<script>
  // Qué decidió el tramo: el desglose del motor frente al top 5 (rendimiento.desglose: salida,
  // velocidad, maniobras y táctica) con su componente mayor como causa principal, y qué mirar según
  // las cifras del propio tramo. No hay cálculo nuevo: solo se ordena lo que ya da el motor.
  import { num, tiempo, mediana } from './datos.js';

  let { desglose, tramo, ref, top5 = [], salida = null, nombreRef = '' } = $props();
  const fila = $derived((desglose?.por_tramo || []).find((x) => x.tramo === tramo.nombre) || null);
  const f = $derived(tramo.barcos[ref] || {});
  const cinco = $derived(top5.map((v) => tramo.barcos[v]).filter(Boolean));
  const m5 = (k) => mediana(cinco.map((x) => x[k]).filter((x) => x != null));
  const NOMBRES = { salida_s: 'salida', velocidad_s: 'velocidad', maniobras_s: 'maniobras', tactica_s: 'táctica y recorrido' };
  const partes = $derived(fila && !fila.sin_datos ? Object.keys(NOMBRES).filter((k) => fila[k] != null && (k !== 'salida_s' || fila[k] !== 0)).map((k) => [k, fila[k]]) : []);
  // causa principal: lo que más pesó en el sentido del resultado (pérdida si perdió, ganancia si ganó)
  const principal = $derived.by(() => {
    if (!partes.length || !fila.total_s) return null;
    const sg = Math.sign(fila.total_s);
    const c = [...partes].sort((a, b) => b[1] * sg - a[1] * sg)[0];
    return c[1] * sg > 0 ? c : null;
  });
  const escala = $derived(Math.max(10, ...partes.map(([, v]) => Math.abs(v))));
  const t = (s) => tiempo(Math.abs(s));
  const signoG = (v, d, u) => (v == null ? '—' : (v > 0 ? '+' : v < 0 ? '−' : '') + num(Math.abs(v), d) + u);
  const ceñida = $derived(tramo.tipo === 'ceñida');

  // qué mirar, con las cifras del tramo frente a la mediana del top 5
  const pistas = $derived.by(() => {
    if (!principal) return [];
    const k = principal[0], out = [];
    if (k === 'velocidad_s') {
      const ds = f.sog != null && m5('sog') != null ? f.sog - m5('sog') : null;
      const dt = f.twa != null && m5('twa') != null ? f.twa - m5('twa') : null;
      if (ds != null) out.push(`SOG ${signoG(ds, 2, ' kn.')} frente al top 5`);
      if (dt != null) out.push(`TWA ${signoG(dt, 1, '°')} (${ceñida ? (dt > 0 ? 'más abierto' : 'más cerrado') : (dt > 0 ? 'más bajo' : 'más alto')})`);
      if (ds != null && dt != null) out.push(ds < -0.1 && Math.abs(dt) < 1.5 ? 'a igual ángulo te faltó velocidad: trimado, peso o escora (mira la escora óptima)'
        : ceñida && dt > 1.5 ? 'navegaste más abierto que el top 5 sin ganar la velocidad que lo compense: busca más altura'
        : !ceñida && dt < -1.5 ? 'navegaste más alto que el top 5 sin ganar la velocidad que lo compense: baja más'
        : ceñida && dt < -1.5 && ds < -0.1 ? 'navegaste más cerrado y más lento que el top 5: abre un poco para ganar velocidad'
        : !ceñida && dt > 1.5 && ds < -0.1 ? 'navegaste más bajo y más lento que el top 5: sube un poco para ganar velocidad'
        : 'mira el modo y la escora frente al top 5');
    } else if (k === 'maniobras_s') {
      out.push(`${f.maniobras ?? '—'} maniobras (top 5: ${m5('maniobras') == null ? '—' : num(m5('maniobras'), 0)})`);
      if (f.perdida_m != null) out.push(`${num(f.perdida_m, 0)} m. perdidos en ellas (top 5: ${m5('perdida_m') == null ? '—' : num(m5('perdida_m'), 0) + ' m.'})`);
      out.push('mira la pestaña Maniobras: menos maniobras o mejor ejecución');
    } else if (k === 'salida_s') {
      const b = salida?.barcos?.[ref];
      const d5 = mediana(top5.map((v) => salida?.barcos?.[v]?.dist_60).filter((x) => x != null));
      if (b?.dist_60 != null) out.push(`a los 60 s. estabas a ${num(b.dist_60, 0)} m. del primero (top 5: ${d5 == null ? '—' : num(d5, 0) + ' m.'})`);
      out.push('mira la comparativa y la aceleración en la pestaña Salida');
    } else {
      const lay = f.layline;
      if (lay?.estado === 'SOBREPASADA') out.push(`layline sobrepasada ${num(lay.metros, 0)} m.`);
      const fav = f.tactica?.amura_favorecida_pct, fav5 = mediana(cinco.map((x) => x.tactica?.amura_favorecida_pct).filter((x) => x != null));
      if (fav != null) out.push(`${num(fav, 0)} % en la amura favorecida (top 5: ${fav5 == null ? '—' : num(fav5, 0) + ' %'})`);
      const sr = f.tactica?.roles_en_contra_sin_responder;
      if (sr) out.push(`${sr} role${sr > 1 ? 's' : ''} en contra sin responder`);
      if (f.vs_fantasma_m != null) out.push(`${num(Math.abs(f.vs_fantasma_m), 0)} m. ${f.vs_fantasma_m > 0 ? 'más' : 'menos'} que el fantasma`);
      out.push('incluye también rodeos y lo que no se mide aparte');
    }
    return out;
  });
</script>

{#if fila && !fila.sin_datos}
<section class="tarjeta bloque">
  <h3>Qué decidió el tramo <span class="est">estimado</span></h3>
  <p class="total">{nombreRef} frente al top 5: <b class="num" class:pierde={fila.total_s > 0} class:gana={fila.total_s < 0}>{fila.total_s > 0 ? `${t(fila.total_s)} perdidos` : fila.total_s < 0 ? `${t(fila.total_s)} ganados` : 'igual'}</b>
    {#if principal} · causa principal: <b>{NOMBRES[principal[0]]}</b> ({principal[1] > 0 ? t(principal[1]) + ' perdidos' : t(principal[1]) + ' ganados'}){/if}</p>
  <div class="barras">
    {#each partes as [k, v]}
      <div class="fila" class:prin={principal?.[0] === k}>
        <span class="et">{NOMBRES[k]}</span>
        <span class="pista"><span class="eje"></span>{#if v}<span class="barra" class:pierde={v > 0} class:gana={v < 0} style:left={v > 0 ? '50%' : `${50 - (Math.abs(v) / escala) * 50}%`} style:width={`${(Math.abs(v) / escala) * 50}%`}></span>{/if}</span>
        <span class="val num" class:pierde={v > 0} class:gana={v < 0}>{v ? tiempo(v, 0, true) : '0 s.'}</span>
      </div>
    {/each}
  </div>
  {#if pistas.length}<p class="mirar"><b>Qué mirar:</b> {pistas.join(' · ')}.</p>{/if}
  <p class="nota">Desglose de «Dónde se perdió la prueba» para este tramo (+ perdido, − ganado frente a la mediana del top 5). La causa principal es la parte que más pesó en el resultado del tramo.</p>
</section>
{/if}

<style>
  .bloque { padding: 10px 12px; min-width: 0; }
  h3 { font-size: 15px; letter-spacing: .06em; text-transform: uppercase; color: var(--tinta-2); margin-bottom: 4px; }
  .est { color: var(--estimado); font-size: 11px; }
  .total { margin: 0 0 6px; font-size: 14px; }
  .barras { display: grid; gap: 3px; max-width: 640px; }
  .fila { display: grid; grid-template-columns: 150px minmax(0, 1fr) 120px; gap: 8px; align-items: center; font-size: 13px; color: var(--tinta-2); }
  .fila.prin .et { color: var(--tinta); font-weight: 700; }
  .pista { position: relative; height: 10px; }
  .eje { position: absolute; left: 50%; top: -2px; bottom: -2px; width: 1px; background: var(--linea); }
  .barra { position: absolute; top: 1px; height: 8px; border-radius: 2px; }
  .barra.pierde { background: var(--error, #c62828); }
  .barra.gana { background: #2a78d6; }
  .val { text-align: right; white-space: nowrap; }
  .pierde { color: var(--error, #c62828); }
  .gana { color: #2a78d6; }
  .mirar { margin: 8px 0 2px; font-size: 13px; color: var(--tinta-2); }
  .nota { margin: 4px 0 0; font-size: 12px; color: var(--tinta-3); }
</style>
