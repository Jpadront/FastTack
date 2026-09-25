<script>
  import { onMount } from 'svelte';
  import { api, velaBonita } from './api.js';
  import Inicio from './Inicio.svelte';
  import Campeonato from './Campeonato.svelte';

  // Rutas por hash: #/  y  #/c/<id del campeonato>
  let ruta = $state(location.hash);
  let barco = $state('ESP1214');

  onMount(async () => {
    window.addEventListener('hashchange', () => (ruta = location.hash));
    try { barco = (await api.preferencias()).barco; } catch {}
  });

  const campId = $derived(ruta.startsWith('#/c/') ? decodeURIComponent(ruta.slice(4)) : null);

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
  {#if campId}
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
