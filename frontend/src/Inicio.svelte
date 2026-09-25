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

<header class="intro">
  <h1>Análisis post-regata de J/70</h1>
  <p class="tenue">Con los datos de los Atlas de RaceSense: recorrido y viento reconstruidos, métricas por tramo frente a la flota y al top 5, general calculada y debrief escrito por IA con cifras comprobadas.</p>
</header>
<div class="columnas">
<section class="guardados">
  <h2>Tus campeonatos</h2>
  {#if guardados.length}
    <ul>
      {#each guardados as c}
        <li>
          <div class="tarjeta ficha">
            <a class="nombre" href={`#/c/${encodeURIComponent(c.id)}`}>
              <b>{c.nombre || c.id}</b>
              <span class="tenue">{c.clase || c.division} · {#if c.estado === 'cargando'}cargando…{:else if c.estado === 'error'}<span class="error">error al cargar</span>{:else}{fecha(c.inicio)}{/if}</span>
            </a>
            <div class="accesos">
              <a class="acceso" href={`#/c/${encodeURIComponent(c.id)}`}>Pruebas</a>
              <a class="acceso" href={`#/c/${encodeURIComponent(c.id)}/resumen`}>Resumen</a>
            </div>
          </div>
        </li>
      {/each}
    </ul>
  {:else}
    <p class="tenue">Todavía no hay ninguno. Prueba con el Mundial de J/70 2026:<br>
      <button class="enlace" onclick={() => (url = 'https://player.vakaros.com/watch/oRkxbTpSZPbSkrmKrbj2/J%2F70')}>usar el enlace del Mundial</button></p>
  {/if}
</section>
<section class="tarjeta cargar">
  <h2>Cargar un campeonato</h2>
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
</div>

<style>
  .intro { margin: 6px 0 16px; }
  .intro h1 { font-size: clamp(26px, 4vw, 34px); }
  .intro p { margin-top: 6px; }
  .columnas { display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr); gap: 16px; align-items: start; }
  @media (max-width: 800px) { .columnas { grid-template-columns: minmax(0, 1fr); } }
  .cargar { padding: 16px; display: grid; gap: 8px; }
  h2 { font-size: 22px; margin: 0 0 10px; }
  .cargar h2 { margin: 0; }
  p { margin: 0; max-width: 65ch; }
  form { display: grid; gap: 8px; margin-top: 8px; }
  form .boton { justify-self: start; }
  ul { list-style: none; margin: 0; padding: 0; display: grid; gap: 8px; }
  .ficha { display: flex; justify-content: space-between; align-items: center; gap: 10px 14px; flex-wrap: wrap; padding: 12px 14px; }
  .ficha:hover { border-color: var(--tinta-3); }
  .nombre { display: grid; gap: 2px; color: var(--tinta); text-decoration: none; font-size: 17px; }
  .nombre .tenue { font-size: 14px; }
  .accesos { display: flex; gap: 6px; }
  .acceso { font: 600 14px var(--display); color: var(--foco); text-decoration: none; border: 1px solid color-mix(in srgb, var(--foco) 40%, transparent);
    border-radius: 14px; padding: 3px 12px; }
  .acceso:hover { background: color-mix(in srgb, var(--foco) 10%, transparent); }
  .enlace { background: none; border: 0; padding: 0; color: var(--foco); text-decoration: underline; }
</style>
