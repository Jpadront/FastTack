<script>
  // Resumen de la prueba para el barco de referencia, lo primero que se ve: puesto, distancia al
  // ganador, frente al top 5 y causa principal (desglose del motor), y el mejor y el peor tramo.
  import { tiempo, semaforo, SEMAFORO } from './datos.js';

  let { an, ref, nombreRef = '' } = $props();
  const k = $derived(an.clasificacion.findIndex((c) => c.vela === ref));
  const total = $derived(an.clasificacion.length);
  const alGanador = $derived(k > 0 ? (an.clasificacion[k].t - an.clasificacion[0].t) / 1000 : k === 0 ? 0 : null);
  const d = $derived(an.rendimiento?.[ref]?.desglose ?? null);
  const NOMBRES = { salida_s: 'la salida', velocidad_s: 'velocidad', maniobras_s: 'maniobras', tactica_s: 'táctica y recorrido' };
  const causa = $derived.by(() => {
    if (!d || !d.total_s) return null;
    const sg = Math.sign(d.total_s);
    const c = Object.keys(NOMBRES).filter((x) => d[x] != null).map((x) => [x, d[x]]).sort((a, b) => b[1] * sg - a[1] * sg)[0];
    return c && c[1] * sg > 0 ? c : null;
  });
  const tramos = $derived((d?.por_tramo || []).filter((x) => !x.sin_datos && x.total_s != null));
  const mejor = $derived(tramos.length > 1 ? tramos.reduce((a, b) => (b.total_s < a.total_s ? b : a)) : null);
  const peor = $derived(tramos.length > 1 ? tramos.reduce((a, b) => (b.total_s > a.total_s ? b : a)) : null);
  const sem = $derived(semaforo(an, ref));
  const t = (s) => tiempo(Math.abs(s));
  const frase = (s) => (s > 0 ? `${t(s)} perdidos` : s < 0 ? `${t(s)} ganados` : 'igual');
</script>

{#if k >= 0}
<section class="heroe" aria-label={`Resultado de ${nombreRef}`}>
  <div class="dato principal">
    <span class="et">{nombreRef}</span>
    <b class="num">{k + 1}.º<small>/{total}</small></b>
    <span class="det">{k === 0 ? 'ganador de la prueba' : alGanador != null ? `a ${tiempo(alGanador)} del ganador` : ''}</span>
  </div>
  {#if sem}
    <div class="dato">
      <span class="et">Velocidad frente a la flota</span>
      <b class="txt"><i class="sem" style:background={SEMAFORO[sem.nivel]}></i>{sem.nivel}</b>
      <span class="det">VMG mejor que el {sem.percentil} % de la flota{sem['ceñida'] != null && sem.popa != null ? ` (ceñida ${sem['ceñida']} %, popa ${sem.popa} %)` : ''}</span>
    </div>
  {/if}
  {#if d}
    <div class="dato">
      <span class="et">Frente al top 5</span>
      <b class="num" class:pierde={d.total_s > 0} class:gana={d.total_s < 0}>{d.total_s > 0 ? '+' : d.total_s < 0 ? '−' : ''}{t(d.total_s)}</b>
      <span class="det">{frase(d.total_s)} en la llegada</span>
    </div>
    {#if causa}
      <div class="dato">
        <span class="et">Causa principal</span>
        <b class="txt">{NOMBRES[causa[0]]}</b>
        <span class="det">{frase(causa[1])}</span>
      </div>
    {/if}
    {#if mejor && peor && mejor !== peor}
      <div class="dato">
        <span class="et">Mejor y peor tramo</span>
        <b class="txt">{mejor.tramo} <span class="flecha">·</span> {peor.tramo}</b>
        <span class="det"><span class:pierde-c={mejor.total_s > 0} class:gana-c={mejor.total_s < 0}>{mejor.total_s > 0 ? '+' : mejor.total_s < 0 ? '−' : ''}{t(mejor.total_s)}</span> · <span class:pierde-c={peor.total_s > 0} class:gana-c={peor.total_s < 0}>{peor.total_s > 0 ? '+' : peor.total_s < 0 ? '−' : ''}{t(peor.total_s)}</span> frente al top 5</span>
      </div>
    {/if}
  {/if}
</section>
{/if}

<style>
  .sem { display: inline-block; width: 14px; height: 14px; border-radius: 50%; margin-right: 8px; vertical-align: 1px; box-shadow: 0 0 0 3px rgba(255, 255, 255, .12); }
  .flecha { color: #8fb0bd; font-weight: 400; }
</style>
