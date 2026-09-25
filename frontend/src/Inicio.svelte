<script>
  import { onMount } from 'svelte';
  import { api, horaLocal } from './api.js';

  let url = $state('');
  let divisiones = $state(null);   // si el campeonato tiene varias, hay que elegir
  let division = $state('');
  let error = $state('');
  let enviando = $state(false);
  let guardados = $state([]);

  onMount(async () => { guardados = await api.campeonatos().catch(() => []); });

  async function cargar(e) {
    e.preventDefault();
    error = '';
    enviando = true;
    try {
      const r = await api.cargar(url, division || undefined);
      location.hash = `#/c/${encodeURIComponent(r.id)}`;
    } catch (err) {
      if (err.estado === 409 && err.detalle?.divisiones) {
        divisiones = err.detalle.divisiones;
        division = divisiones[0];
        error = 'Este campeonato tiene varias divisiones: elige cuál quieres analizar.';
      } else {
        error = err.message;
      }
    } finally {
      enviando = false;
    }
  }

  const fecha = (ms) => (ms ? horaLocal(ms, 0).split(' · ')[0] : '');
</script>

<section class="tarjeta cargar">
  <h1>Cargar un campeonato</h1>
  <p class="tenue">Pega el enlace del visor de RaceSense (player.vakaros.com/watch/…). Sirve cualquier campeonato; lo que ya está descargado no se vuelve a descargar.</p>
  <form onsubmit={cargar}>
    <label class="etiqueta" for="url">Enlace de RaceSense</label>
    <input id="url" class="campo num" type="url" required bind:value={url}
           placeholder="https://player.vakaros.com/watch/oRkxbTpSZPbSkrmKrbj2/J%2F70">
    {#if divisiones}
      <label class="etiqueta" for="division">División</label>
      <select id="division" class="campo" bind:value={division}>
        {#each divisiones as d}<option>{d}</option>{/each}
      </select>
    {/if}
    <button class="boton" disabled={enviando || !url}>{enviando ? 'Comprobando…' : 'Cargar'}</button>
    {#if error}<p class="error" role="alert">{error}</p>{/if}
  </form>
</section>

<section class="guardados">
  <h2>Campeonatos guardados</h2>
  {#if guardados.length}
    <ul>
      {#each guardados as c}
        <li>
          <a class="tarjeta" href={`#/c/${encodeURIComponent(c.id)}`}>
            <span><b>{c.nombre || c.id}</b><span class="tenue"> · {c.clase || c.division}</span></span>
            <span class="tenue">
              {#if c.estado === 'cargando'}Cargando…{:else if c.estado === 'error'}<span class="error">Error al cargar</span>{:else}{fecha(c.inicio)}{/if}
            </span>
          </a>
        </li>
      {/each}
    </ul>
  {:else}
    <p class="tenue">Todavía no hay ninguno. Prueba con el Mundial de J/70 2026:<br>
      <button class="enlace" onclick={() => (url = 'https://player.vakaros.com/watch/oRkxbTpSZPbSkrmKrbj2/J%2F70')}>usar el enlace del Mundial</button></p>
  {/if}
</section>

<style>
  .cargar { padding: 18px; display: grid; gap: 8px; max-width: 720px; }
  h1 { font-size: 28px; }
  h2 { font-size: 22px; margin: 28px 0 10px; }
  p { margin: 0; max-width: 65ch; }
  form { display: grid; gap: 8px; margin-top: 8px; }
  form .boton { justify-self: start; }
  ul { list-style: none; margin: 0; padding: 0; display: grid; gap: 8px; max-width: 720px; }
  li a { display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap; padding: 12px 14px; color: var(--tinta); text-decoration: none; }
  li a:hover { border-color: var(--tinta-3); }
  .enlace { background: none; border: 0; padding: 0; color: var(--foco); text-decoration: underline; }
</style>
