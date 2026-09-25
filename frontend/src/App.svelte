<script>
  import { onMount } from 'svelte';
  import { api, velaBonita } from './api.js';
  import Inicio from './Inicio.svelte';
  import Campeonato from './Campeonato.svelte';
  // El análisis (con el mapa) se carga solo al abrir una prueba: la portada queda ligera
  const cargarPrueba = () => import('./prueba/Prueba.svelte');

  // Rutas por hash: #/ · #/c/<campeonato> · #/c/<campeonato>/p/<clave de la prueba>
  let ruta = $state(location.hash);
  let barco = $state('ESP1214');

  onMount(async () => {
    window.addEventListener('hashchange', () => (ruta = location.hash));
    try { barco = (await api.preferencias()).barco; } catch {}
  });

  const partes = $derived(ruta.startsWith('#/c/') ? ruta.slice(4).split('/p/') : []);
  const campId = $derived(partes[0] ? decodeURIComponent(partes[0]) : null);
  const pruebaClave = $derived(partes[1] || null);

  async function cambiarBarco(v) {
    barco = v;
    try { await api.fijarBarco(v); } catch {}
  }
</script>

<header class="barra">
  <a class="marca" href="#/">FastTack</a>
  <span class="barco" title="Barco de referencia"><span class="punto"></span>{velaBonita(barco)}</span>
</header>

<main>
  {#if campId && pruebaClave}
    {#key ruta}
      {#await cargarPrueba()}
        <p class="tenue">Cargando…</p>
      {:then m}
        <m.default {campId} clave={pruebaClave} {barco} />
      {/await}
    {/key}
  {:else if campId}
    {#key campId}
      <Campeonato id={campId} {barco} onBarco={cambiarBarco} />
    {/key}
  {:else}
    <Inicio />
  {/if}
</main>

<style>
  .barra {
    position: sticky; top: env(safe-area-inset-top, 0px); z-index: 10;
    display: flex; justify-content: space-between; align-items: center; gap: 12px;
    padding: 10px 16px; background: var(--panel); border-bottom: 1px solid var(--linea);
  }
  .marca { font: 700 20px var(--display); color: var(--tinta); text-decoration: none; letter-spacing: .02em; }
  .barco { font: 600 15px var(--display); color: var(--yo); display: inline-flex; align-items: center; gap: 6px; }
  .punto { width: 9px; height: 9px; border-radius: 50%; background: var(--yo); }
  main { max-width: 1180px; margin: 0 auto; padding: 16px 16px 48px; }
</style>
