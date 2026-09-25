<script>
  import { onDestroy } from 'svelte';
  import { fmtT } from './datos.js';

  // T enlazado; ventana [t0, t1] en s desde la señal; senalMs y desfase para la hora local
  let { T = $bindable(), ventana, senalMs, desfaseMs = 0 } = $props();
  let jugando = $state(false);
  let velocidad = $state(4);
  let ultimo = 0, id;

  function paso(ahora) {
    if (!jugando) return;
    T = Math.min(ventana[1], T + ((ahora - ultimo) / 1000) * velocidad);
    ultimo = ahora;
    if (T >= ventana[1]) { jugando = false; return; }
    id = requestAnimationFrame(paso);
  }
  function alternar() {
    jugando = !jugando;
    if (jugando) {
      if (T >= ventana[1] - 0.5) T = ventana[0];
      ultimo = performance.now();
      id = requestAnimationFrame(paso);
    }
  }
  onDestroy(() => cancelAnimationFrame(id));

  const hora = $derived.by(() => {
    const d = new Date(senalMs + T * 1000 + desfaseMs);
    return [d.getUTCHours(), d.getUTCMinutes(), d.getUTCSeconds()].map((n) => String(n).padStart(2, '0')).join(':');
  });
</script>

<div class="rep">
  <button class="play" onclick={alternar} aria-label={jugando ? 'Pausar' : 'Reproducir'}>{jugando ? '❚❚' : '▶'}</button>
  <input type="range" min={ventana[0]} max={ventana[1]} step="0.5" bind:value={T} aria-label="Momento de la prueba">
  <div class="reloj num"><b>{fmtT(T)}</b><span>{hora}</span></div>
  <!-- en el móvil, un solo botón que va cambiando de velocidad -->
  <button class="vel-movil num" onclick={() => (velocidad = { 1: 4, 4: 10, 10: 30, 30: 1 }[velocidad])} aria-label={`Velocidad ×${velocidad}; pulsa para cambiar`}>×{velocidad}</button>
  <div class="vel" role="group" aria-label="Velocidad de reproducción">
    {#each [1, 4, 10, 30] as v}
      <button class:activo={velocidad === v} aria-pressed={velocidad === v} onclick={() => (velocidad = v)}>×{v}</button>
    {/each}
  </div>
</div>

<style>
  .rep { display: grid; grid-template-columns: auto minmax(0, 1fr) auto auto; gap: 10px; align-items: center; background: var(--panel); border: 1px solid var(--linea); border-radius: 6px; padding: 8px 10px; }
  .play { width: 38px; height: 34px; border-radius: 5px; border: 0; background: var(--tinta); color: var(--panel); font-size: 14px; }
  input { width: 100%; accent-color: var(--yo); }
  .reloj { display: grid; text-align: right; line-height: 1.15; font-size: 12px; color: var(--tinta-2); }
  .reloj b { font-size: 16px; color: var(--tinta); font-weight: 500; }
  .vel { display: flex; gap: 3px; }
  .vel button { font: 500 12px var(--mono); padding: 4px 7px; border-radius: 4px; border: 1px solid var(--linea); background: var(--panel); }
  .vel button.activo { background: var(--tinta); color: var(--panel); border-color: var(--tinta); }
  .vel-movil { display: none; font: 500 13px var(--mono); padding: 6px 8px; border-radius: 4px; border: 1px solid var(--linea); background: var(--panel); min-width: 44px; }
  /* Móvil: el reproductor queda fijo abajo para mover el tiempo mientras se leen las tablas */
  @media (max-width: 900px) {
    .rep { position: fixed; left: 8px; right: 8px; bottom: calc(8px + env(safe-area-inset-bottom, 0px)); z-index: 30;
      grid-template-columns: auto minmax(0, 1fr) auto auto; box-shadow: 0 4px 18px rgba(16, 34, 43, .22); }
    .vel { display: none; }
    .vel-movil { display: block; }
  }
</style>
