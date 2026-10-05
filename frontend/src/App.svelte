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
  <a class="marca" href="#/" aria-label="FastTack, inicio"><svg viewBox="0 0 64 64" width="28" height="28" aria-hidden="true"><defs><linearGradient id="logo-f" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#1d4a5c"/><stop offset="1" stop-color="#0b222c"/></linearGradient></defs><rect width="64" height="64" rx="16" fill="url(#logo-f)" stroke="#2f5a6b" stroke-width="1.5"/><path d="M35.87 10 L27.37 50 L9.37 50 Z" fill="#eef4f6"/><path d="M39.17 18 L47.37 50 L32.37 50 Z" fill="#ff8a52"/><rect x="10" y="53" width="44" height="3.5" rx="1.75" fill="#3d7f96"/></svg><span>Fast<b>Tack</b></span></a>
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
    padding: 10px 16px; background: #0f2a36; border-bottom: 1px solid #24414d;
    box-shadow: 0 2px 10px -6px rgba(8, 24, 32, .6);
  }
  .marca b { color: #ff8a52; font-weight: 700; }
  .marca { font: 700 21px var(--display); color: #eef4f6; text-decoration: none; letter-spacing: .02em; display: inline-flex; align-items: center; gap: 8px; }
  .barco { font: 600 15px var(--display); color: #ff8a52; background: rgba(255, 138, 82, .12); border: 1px solid rgba(255, 138, 82, .35); padding: 2px 10px; border-radius: 14px; display: inline-flex; align-items: center; gap: 6px; }
  .punto { width: 9px; height: 9px; border-radius: 50%; background: #ff8a52; }
  .pie-app { text-align: center; font: 500 12px var(--mono); color: var(--tinta-3); padding: 8px 0 20px; }
  main { max-width: 1180px; margin: 0 auto; padding: 16px 16px 48px; }
</style>
