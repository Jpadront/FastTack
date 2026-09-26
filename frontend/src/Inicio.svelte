<script>
  import { onMount } from 'svelte';
  import { api, horaLocal } from './api.js';
  import SubirVkx from './SubirVkx.svelte';

  let url = $state('');
  let divisiones = $state(null);   // si el campeonato tiene varias, hay que elegir
  let division = $state('');
  let error = $state('');
  let enviando = $state(false);
  let guardados = $state([]);

  onMount(async () => { guardados = await api.campeonatos().catch(() => []); });

  let editando = $state(null), nuevoNombre = $state('');
  async function renombrar(c) {
    try {
      await api.renombrar(c.id, nuevoNombre);
      guardados = await api.campeonatos();
      editando = null;
    } catch (err) { error = err.message; }
  }
  async function eliminar(c) {
    const sesion = c.id.startsWith('vkx-');
    if (!confirm(`¿Eliminar «${c.nombre || c.id}» de la lista?` + (sesion
      ? ' Se borrarán los archivos .vkx subidos a esta sesión.'
      : ' Los datos ya descargados de RaceSense se conservan: si lo vuelves a cargar, no se descargan otra vez.'))) return;
    try {
      await api.eliminar(c.id);
      guardados = guardados.filter((x) => x.id !== c.id);
    } catch (err) { error = err.message; }
  }

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
  <h1>Análisis post-regata de vela</h1>
  <p class="tenue">Para cualquier clase que navegue con Atlas 2 de Vakaros (RaceSense): recorrido y viento reconstruidos, métricas por tramo frente a la flota y al top 5, general calculada y debrief escrito por IA con cifras comprobadas.</p>
</header>
<div class="columnas">
<section class="guardados">
  <h2>Tus campeonatos</h2>
  {#if error && !url}<p class="error" role="alert">{error}</p>{/if}
  {#if guardados.length}
    <ul>
      {#each guardados as c}
        <li>
          <div class="tarjeta ficha">
            <a class="nombre" href={`#/c/${encodeURIComponent(c.id)}`}>
              <b>{c.nombre || c.id}</b>
              <span class="tenue">{c.clase || c.division}{#if c.id.startsWith('vkx-')} · archivos .vkx{/if} · {#if c.estado === 'cargando'}cargando…{:else if c.estado === 'error'}<span class="error">error al cargar</span>{:else}{fecha(c.inicio)}{/if}</span>
            </a>
            <div class="accesos">
              <a class="acceso" href={`#/c/${encodeURIComponent(c.id)}`}>Pruebas</a>
              <a class="acceso" href={`#/c/${encodeURIComponent(c.id)}/resumen`}>Resumen</a>
              <button class="icono" title="Cambiar el nombre" aria-label={`Cambiar el nombre de ${c.nombre || c.id}`} onclick={() => { editando = c.id; nuevoNombre = c.nombre || ''; }}>✎</button>
              <button class="icono" title="Eliminar de la lista" aria-label={`Eliminar ${c.nombre || c.id}`} onclick={() => eliminar(c)}>🗑</button>
            </div>
            {#if editando === c.id}
              <form class="renombrar" onsubmit={(e) => { e.preventDefault(); renombrar(c); }}>
                <input class="campo" bind:value={nuevoNombre} aria-label="Nuevo nombre" placeholder={c.nombre_original || ''}>
                <button class="boton">Guardar</button>
                <button type="button" class="boton claro" onclick={() => (editando = null)}>Cancelar</button>
              </form>
              {#if c.nombre_original && c.nombre_original !== c.nombre}<p class="tenue original">Nombre original: {c.nombre_original} (déjalo vacío para recuperarlo)</p>{/if}
            {/if}
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
<section class="tarjeta cargar vkx">
  <h2>Sesión con archivos .vkx</h2>
  <p class="tenue">Para regatas o entrenamientos que no están en RaceSense: sube el registro de tu Atlas 2 (y, si los tienes, los de otros barcos). Las pruebas salen de las salidas marcadas con el crono del Atlas y la línea, de sus pings; llegadas y balizas se estiman con las trazas. Los archivos se quedan en tu ordenador.</p>
  <SubirVkx onHecho={(id) => (location.hash = `#/c/${encodeURIComponent(id)}`)} />
</section>
</div>

<style>
  .intro { margin: 6px 0 16px; }
  .intro h1 { font-size: clamp(26px, 4vw, 34px); }
  .intro p { margin-top: 6px; }
  .columnas { display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr); gap: 16px; align-items: start; }
  @media (max-width: 800px) { .columnas { grid-template-columns: minmax(0, 1fr); } }
  .cargar { padding: 16px; display: grid; gap: 8px; }
  .guardados { grid-row: span 2; }
  .vkx { grid-column: 2; }
  @media (max-width: 800px) { .vkx { grid-column: auto; } .guardados { grid-row: auto; } }
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
  .accesos { display: flex; gap: 6px; align-items: center; }
  .icono { background: none; border: 0; padding: 3px 6px; font-size: 15px; color: var(--tinta-3); cursor: pointer; border-radius: 8px; }
  .icono:hover { color: var(--tinta); background: color-mix(in srgb, var(--foco) 8%, transparent); }
  .renombrar { display: flex; gap: 6px; width: 100%; margin: 0; }
  .renombrar .campo { flex: 1; min-width: 0; padding: 5px 8px; }
  .renombrar .boton { padding: 5px 12px; font-size: 14px; }
  .original { font-size: 13px; width: 100%; }
  .acceso { font: 600 14px var(--display); color: var(--foco); text-decoration: none; border: 1px solid color-mix(in srgb, var(--foco) 40%, transparent);
    border-radius: 14px; padding: 3px 12px; }
  .acceso:hover { background: color-mix(in srgb, var(--foco) 10%, transparent); }
  .enlace { background: none; border: 0; padding: 0; color: var(--foco); text-decoration: underline; }
</style>
