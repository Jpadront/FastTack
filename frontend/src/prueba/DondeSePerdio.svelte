<script>
  // Dónde perdió (o ganó) tiempo el barco de referencia frente al top 5 de la prueba.
  import Nota from '../Nota.svelte';
  import { num, tiempo } from './datos.js';

  let { desglose: d, nombreRef = '', nombres = (v) => v } = $props();
  // En el orden de la prueba: la salida y cada tramo (el primero sin la salida), con su reparto debajo
  const partes = $derived(d ? [
    { nombre: 'Salida', s: d.salida_s },
    ...d.por_tramo.map((t, k) => t.sin_datos ? { nombre: t.tramo, s: null }
      : { nombre: t.tramo, s: t.total_s - (k === 0 ? (t.salida_s ?? 0) : 0),
          detalle: [['velocidad', t.velocidad_s], ['maniobras', t.maniobras_s], ['táctica y resto', t.tactica_s]] }),
  ] : []);
  const escala = $derived(Math.max(30, ...partes.map((x) => Math.abs(x.s ?? 0))));
  const porTipo = $derived(d ? [['velocidad', d.velocidad_s], ['maniobras', d.maniobras_s], ['táctica y resto', d.tactica_s]] : []);
  const txt = (s) => (s == null ? 'sin datos' : tiempo(s, 0, true));
</script>

{#if d}
<section class="tarjeta donde">
  <div class="cab">
    <h3>Dónde se perdió la prueba <span class="est">estimado</span></h3>
    <p class="total">{nombreRef} frente al top 5: <b class="num" class:pierde={d.total_s > 0} class:gana={d.total_s < 0}>{d.total_s > 0 ? `${tiempo(d.total_s)} perdidos` : d.total_s < 0 ? `${tiempo(-d.total_s)} ganados` : 'igual'}</b></p>
  </div>
  <div class="barras">
    {#each partes as { nombre, s, detalle }}
      <span class="nombre">{nombre}</span>
      <span class="eje">
        <i class="barra" class:pierde={s > 0} class:gana={s < 0}
           style:width={`${(Math.abs(s ?? 0) / escala) * 50}%`} style:left={s < 0 ? `${50 - (Math.abs(s) / escala) * 50}%` : '50%'}></i>
      </span>
      <span class="valor num" class:pierde={s > 0} class:gana={s < 0} class:tenue={s == null}>{txt(s)}</span>
      {#if detalle}<small class="det num">{detalle.map(([k, v]) => `${k} ${tiempo(v, 0, true)}`).join(' · ')}</small>{/if}
    {/each}
  </div>
  <p class="tipo">Por tipo: {#each porTipo as [k, v], i}{i ? ' · ' : ''}{k} <b class="num" class:pierde={v > 0} class:gana={v < 0}>{tiempo(v, 0, true)}</b>{/each}</p>
  <Nota>
    <p>En el orden de la prueba: la salida y cada tramo (el primero, sin la salida). Cada tramo se compara con el tiempo mediano de los 5 primeros en ese tramo, así que la suma de los tramos no coincide exactamente con la diferencia en la llegada (el total de arriba). Tiempo perdido (+) o ganado (−) frente a los 5 primeros de la prueba ({d.frente_a.map(nombres).join(', ')}). <b>Velocidad</b>: con tu VMG navegando estable (sin maniobras ni rodeos) frente a la del top 5, lo que tardarías en cada tramo; incluye el aire sucio. <b>Maniobras</b>: segundos perdidos en viradas y trasluchadas (las que caen en huecos de datos, a la mediana de las medidas). <b>Salida</b>: metros por detrás del primero a los 60 s. frente al top 5, pasados a segundos. <b>Táctica y resto</b>: lo que falta hasta la diferencia real en la llegada (roladas, lado, laylines, rodeos{d.tramos_sin_datos ? ` y ${d.tramos_sin_datos} tramo(s) sin datos suficientes` : ''}).</p>
  </Nota>
</section>
{/if}

<style>
  .donde { padding: 10px 14px; margin-bottom: 10px; }
  .cab { display: flex; justify-content: space-between; align-items: baseline; gap: 8px 16px; flex-wrap: wrap; }
  h3 { font-size: 15px; letter-spacing: .06em; text-transform: uppercase; color: var(--tinta-2); margin: 0; }
  .est { color: var(--estimado); font-size: 11px; }
  .total { margin: 0; font-size: 15px; }
  .barras { display: grid; grid-template-columns: max-content minmax(0, 1fr) 13ch; gap: 6px 10px; align-items: center; margin: 8px 0 4px; }
  .nombre { font-size: 14px; color: var(--tinta-2); }
  .det { grid-column: 1 / -1; font-size: 11px; color: var(--tinta-3); margin: -5px 0 2px; }
  .tipo { margin: 2px 0 4px; font-size: 13px; color: var(--tinta-2); }
  .eje { position: relative; height: 12px; border-left: 0; }
  .eje::before { content: ''; position: absolute; left: 50%; top: -2px; bottom: -2px; border-left: 1px solid var(--linea); }
  .barra { position: absolute; top: 0; bottom: 0; border-radius: 3px; }
  .barra.pierde { background: #e34948; }
  .barra.gana { background: #2a78d6; }
  .valor { text-align: right; font-size: 14px; }
  .pierde { color: #c0392b; }
  .gana { color: #1c5cab; }
  .barra.pierde, .barra.gana { color: inherit; }
</style>
