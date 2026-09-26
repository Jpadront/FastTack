<script>
  import { onMount } from 'svelte';
  import { api, velaBonita } from './api.js';
  import Inicio from './Inicio.svelte';
  import Campeonato from './Campeonato.svelte';
  // El análisis (con el mapa) se carga solo al abrir una prueba: la portada queda ligera
  const cargarPrueba = () => import('./prueba/Prueba.svelte');
  const cargarResumen = () => import('./resumen/Resumen.svelte');
  const cargarTemporada = () => import('./Temporada.svelte');

  // Rutas por hash: #/ · #/c/<campeonato> · #/c/<campeonato>/p/<clave de la prueba> · #/c/<campeonato>/resumen
  let ruta = $state(location.hash);
  let barco = $state('ESP1214');
  let version = $state('');

  onMount(async () => {
    window.addEventListener('hashchange', () => (ruta = location.hash));
    // Barco de referencia: el de este navegador (cada miembro del equipo puede mirar el suyo); si no
    // hay, el del servidor
    let local = null;
    try { local = localStorage.getItem('fasttack.barco'); } catch {}
    if (local) barco = local;
    else { try { barco = (await api.preferencias()).barco; } catch {} }
    try { version = (await (await fetch('/api/version')).json()).version; } catch {}
  });

  const esResumen = $derived(ruta.startsWith('#/c/') && ruta.endsWith('/resumen'));
  const partes = $derived(ruta.startsWith('#/c/') ? ruta.slice(4).replace(/\/resumen$/, '').split('/p/') : []);
  const campId = $derived(partes[0] ? decodeURIComponent(partes[0]) : null);
  const pruebaClave = $derived(partes[1] || null);

  async function cambiarBarco(v) {
    barco = v;
    try { localStorage.setItem('fasttack.barco', v); } catch {}
  }
</script>

<header class="barra">
  <a class="marca" href="#/"><svg viewBox="0 0 64 64" width="24" height="24" aria-hidden="true"><rect x="1" y="1" width="62" height="62" rx="14" fill="#10222b" stroke="#4b5e67" stroke-width="2"/><path d="M20 48 L34 12 L34 48 Z" fill="#eef2f3"/><path d="M37 20 L48 44 L37 44 Z" fill="#e0622e"/><path d="M12 52 H52" stroke="#eef2f3" stroke-width="3" stroke-linecap="round"/></svg>FastTack</a>
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
  {:else if campId && esResumen}
    {#key ruta}
      {#await cargarResumen()}
        <p class="tenue">Cargando…</p>
      {:then m}
        <m.default {campId} {barco} />
      {/await}
    {/key}
  {:else if ruta.startsWith('#/temporada')}
    {#await cargarTemporada()}
      <p class="tenue">Cargando…</p>
    {:then m}
      <m.default {barco} />
    {/await}
  {:else if campId}
    {#key campId}
      <Campeonato id={campId} {barco} onBarco={cambiarBarco} />
    {/key}
  {:else}
    <Inicio />
  {/if}
</main>
<footer class="pie-app">FastTack {version ? 'v' + version : ''}</footer>

<style>
  :global(:root) { --alto-barra: 45px; }
  .barra {
    height: var(--alto-barra);
    position: sticky; top: env(safe-area-inset-top, 0px); z-index: 10;
    display: flex; justify-content: space-between; align-items: center; gap: 12px;
    padding: 10px 16px; background: var(--panel); border-bottom: 1px solid var(--linea);
  }
  .marca { font: 700 20px var(--display); color: var(--tinta); text-decoration: none; letter-spacing: .02em; display: inline-flex; align-items: center; gap: 8px; }
  .barco { font: 600 15px var(--display); color: var(--yo); display: inline-flex; align-items: center; gap: 6px; }
  .punto { width: 9px; height: 9px; border-radius: 50%; background: var(--yo); }
  .pie-app { text-align: center; font: 500 12px var(--mono); color: var(--tinta-3); padding: 8px 0 20px; }
  main { max-width: 1180px; margin: 0 auto; padding: 16px 16px 48px; }
</style>
