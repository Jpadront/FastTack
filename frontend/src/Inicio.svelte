<script>
  import { onMount } from 'svelte';
  import { api, horaLocal } from './api.js';
  import SubirVkx from './SubirVkx.svelte';
  import Insignia from './Insignia.svelte';

  let url = $state('');
  let divisiones = $state(null);   // si el campeonato tiene varias, hay que elegir
  let division = $state('');
  let error = $state('');
  let enviando = $state(false);
  let guardados = $state([]);

  onMount(async () => { guardados = await api.campeonatos().catch(() => []); });

  // Buscador: por nombre, clase, división, año o mes (sin tildes ni mayúsculas) y filtro por clase;
  // los más recientes primero
  let busca = $state(''), clase = $state('');
  const norm = (t) => (t || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z0-9\s]/g, '');
  const MESES_B = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];
  const clases = $derived([...new Set(guardados.map((c) => c.clase).filter(Boolean))].sort());
  const ordenados = $derived([...guardados].sort((a, b) => (b.inicio || 0) - (a.inicio || 0)));
  const visibles = $derived(ordenados.filter((c) => {
    if (clase && c.clase !== clase) return false;
    const f = c.inicio ? new Date(c.inicio) : null;
    const texto = norm([c.nombre, c.nombre_original, c.id, c.clase, c.division, f?.getFullYear(), f ? MESES_B[f.getMonth()] : ''].join(' '));
    return norm(busca).split(/\s+/).filter(Boolean).every((p) => texto.includes(p));
  }));

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

  const fecha = (ms) => (ms ? horaLocal(ms, 0).split(' · ')[0] + ' ' + new Date(ms).getFullYear() : '');
</script>

<header class="intro">
  <div class="autor">Software de análisis de datos para vela · desarrollado por <b>Javier Padrón</b></div>
  <h1>Análisis post-regata de vela</h1>
  <p>Dónde ganas y dónde pierdes, tramo a tramo, frente a la flota y al top 5. Con los datos del Atlas 2 de Vakaros, en cualquier clase.</p>
  <ul class="rasgos">
    <li><b>Recorrido y viento</b> reconstruidos con los GPS de la flota</li>
    <li><b>Tramo a tramo</b>: velocidad, maniobras, táctica y escora</li>
    <li><b>Debrief e informe PDF</b> con cifras comprobadas</li>
  </ul>
</header>
<div class="columnas">
<section class="guardados">
  <div class="titulo-lista"><h2>Tus campeonatos</h2>{#if guardados.length}<a class="acceso" href="#/temporada">Tu temporada →</a>{/if}</div>
  {#if error && !url}<p class="error" role="alert">{error}</p>{/if}
  {#if guardados.length}
    <div class="buscador">
      <input class="campo" type="search" bind:value={busca} placeholder="Buscar regata, clase, año o mes…" aria-label="Buscar campeonato">
      {#if clases.length > 1}
        <div class="clases" role="group" aria-label="Filtrar por clase">
          <button class:activo={!clase} aria-pressed={!clase} onclick={() => (clase = '')}>Todas</button>
          {#each clases as k}<button class:activo={clase === k} aria-pressed={clase === k} onclick={() => (clase = clase === k ? '' : k)}>{k}</button>{/each}
        </div>
      {/if}
      {#if busca || clase}<span class="tenue cuenta">{visibles.length} de {guardados.length}</span>{/if}
    </div>
    {#if !visibles.length}<p class="tenue">Ningún campeonato coincide con la búsqueda.</p>{/if}
    <ul>
      {#each visibles as c (c.id)}
        <li>
          <div class="tarjeta ficha">
            <Insignia clase={c.clase || c.division} />
            <a class="nombre" href={`#/c/${encodeURIComponent(c.id)}`}>
              <b>{c.nombre || c.id}</b>
              <span class="tenue">{c.clase || c.division}{c.id.startsWith('vkx-') ? ' · archivos .vkx' : ''} · {#if c.estado === 'cargando'}cargando…{:else if c.estado === 'error'}<span class="error">error al cargar</span>{:else}{fecha(c.inicio)}{/if}</span>
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
<details class="anadir" open={!guardados.length}>
<summary class="boton">＋ Cargar un campeonato o una sesión .vkx</summary>
<div class="dos-cargas">
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
</details>
</div>

<style>
  .intro { margin: 6px 0 18px; padding: 22px 24px 20px; border-radius: 12px; color: #e6eff2;
    background: radial-gradient(120% 140% at 100% 0%, #1d4a5c 0%, #0f2a36 55%, #0b222c 100%);
    box-shadow: 0 8px 26px -14px rgba(8, 24, 32, .7); }
  .autor { font: 600 13px var(--display); letter-spacing: .08em; text-transform: uppercase; color: #8fb0bd; margin-bottom: 6px; }
  .autor b { color: #ff8a52; font-weight: 700; }
  .intro h1 { font-size: clamp(28px, 4.5vw, 40px); color: #fff; }
  .intro p { margin-top: 8px; color: #b8ced6; font-size: 17px; }
  .rasgos { list-style: none; padding: 0; margin: 14px 0 0; display: flex; flex-wrap: wrap; gap: 8px; }
  .rasgos li { font-size: 14px; color: #cfe0e6; background: rgba(255, 255, 255, .06); border: 1px solid rgba(255, 255, 255, .12); border-radius: 16px; padding: 4px 12px; }
  .rasgos b { color: #ff8a52; font-weight: 600; }
  .columnas { display: grid; gap: 16px; }
  .anadir > summary { list-style: none; display: inline-block; }
  .anadir > summary::-webkit-details-marker { display: none; }
  .anadir[open] > summary { margin-bottom: 12px; }
  .dos-cargas { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 16px; align-items: start; }
  @media (max-width: 800px) { .dos-cargas { grid-template-columns: minmax(0, 1fr); } }
  .cargar { padding: 16px; display: grid; gap: 8px; }
  .buscador { display: flex; flex-wrap: wrap; gap: 8px 12px; align-items: center; margin: 0 0 10px; }
  .buscador .campo { max-width: 360px; flex: 1 1 240px; }
  .clases { display: flex; flex-wrap: wrap; gap: 4px; }
  .clases button { font: 600 13px var(--display); padding: 4px 10px; border-radius: 14px; border: 1px solid var(--linea); background: var(--panel); color: var(--tinta-2); }
  .clases button.activo { background: var(--tinta); color: var(--panel); border-color: var(--tinta); }
  .cuenta { font-size: 13px; }
  .titulo-lista { display: flex; justify-content: space-between; align-items: baseline; gap: 10px; }
  h2 { font-size: 22px; margin: 0 0 10px; }
  .cargar h2 { margin: 0; }
  p { margin: 0; max-width: 65ch; }
  form { display: grid; gap: 8px; margin-top: 8px; }
  form .boton { justify-self: start; }
  .guardados ul { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 10px; }
  .ficha { display: flex; justify-content: space-between; align-items: center; gap: 10px 14px; flex-wrap: wrap; padding: 14px 16px; border-left: 4px solid var(--yo); transition: border-color .15s, box-shadow .15s; }
  .ficha:hover { box-shadow: 0 4px 14px -10px rgba(8, 24, 32, .5); }
  .ficha:hover { border-color: var(--tinta-3); }
  .nombre { flex: 1 1 auto; min-width: 0; display: grid; gap: 2px; color: var(--tinta); text-decoration: none; font: 700 20px var(--display); }
  .nombre .tenue { font: 400 14px var(--texto); }
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
