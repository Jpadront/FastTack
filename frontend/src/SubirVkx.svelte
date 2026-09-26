<script>
  // Crear una sesión propia con archivos .vkx del Atlas 2, o añadir archivos a una ya creada (sid).
  // Los archivos se van acumulando: se pueden elegir de varias carpetas (una selección tras otra) o
  // arrastrarlos. Cada archivo lleva su vela (una sesión puede tener varios barcos).
  import { onMount } from 'svelte';
  import { api, velaBonita } from './api.js';

  // camp: campeonato de RaceSense (los archivos sustituyen a la telemetría de ese barco)
  let { sid = null, camp = null, onHecho } = $props();

  const CLASES = ['J/70', 'J/80', 'J/24', 'Snipe', 'ILCA', '470', '420', '49er', 'Nacra 17', 'Finn', 'Star', 'Etchells',
    'Melges 24', 'Melges 20', 'SB20', 'Dragon', 'Optimist', '29er', 'Flying Fifteen', 'RS21', 'J/111', 'Fireball'];

  let nombre = $state('');
  let clase = $state('J/70');
  let velaDefecto = '';
  let lista = $state([]);        // [{ archivo, vela, barco, estado }]
  let error = $state('');
  let progreso = $state('');
  let encima = $state(false);
  let entrada;

  onMount(async () => {
    let local = null;
    try { local = localStorage.getItem('fasttack.barco'); } catch {}
    const p = local ? { barco: local } : await api.preferencias().catch(() => null);
    if (p?.barco) velaDefecto = velaBonita(p.barco);
  });

  // «MonjoII_10-5-2025.vkx» → «MonjoII»
  const barcoDe = (n) => {
    const base = n.replace(/\.vkx$/i, '').split(/[_]/)[0];
    return base && !/^\d/.test(base) ? base : '';
  };

  function añadir(files) {
    error = '';
    const nuevos = [...files].filter((f) => /\.vkx$/i.test(f.name));
    const ignorados = files.length - nuevos.length;
    for (const f of nuevos) {
      if (lista.some((x) => x.archivo.name === f.name && x.archivo.size === f.size)) continue;
      const previo = lista[lista.length - 1];
      lista.push({ archivo: f, vela: previo?.vela || velaDefecto, barco: barcoDe(f.name) || previo?.barco || '', estado: '' });
    }
    if (ignorados) error = `${ignorados} archivo(s) sin extensión .vkx no se han añadido.`;
    if (entrada) entrada.value = '';   // así se puede volver a abrir el selector en otra carpeta
  }

  function soltar(e) {
    e.preventDefault();
    encima = false;
    añadir(e.dataTransfer?.files || []);
  }

  const tamaño = (b) => (b > 1e6 ? `${(b / 1e6).toFixed(1).replace('.', ',')} MB` : `${Math.round(b / 1e3)} kB`);

  async function enviar(e) {
    e.preventDefault();
    error = '';
    if (!lista.length) { error = 'Añade al menos un archivo .vkx.'; return; }
    if (lista.some((x) => !x.vela.trim())) { error = 'Falta la vela de algún archivo.'; return; }
    try {
      let id = sid;
      if (camp) id = camp;
      else if (!id) {
        progreso = 'Creando la sesión';
        id = (await api.crearSesion(nombre || 'Sesión propia', clase)).id;
        sid = id;   // si falla un archivo, los siguientes intentos van a la misma sesión
      }
      const pendientes = lista.filter((x) => x.estado !== 'ok');
      for (const [k, x] of pendientes.entries()) {
        progreso = `Leyendo ${x.archivo.name} (${k + 1} de ${pendientes.length})`;
        try {
          if (camp) await api.subirVkxCampeonato(camp, x.archivo, x.vela);
          else await api.subirVkx(id, x.archivo, x.vela, x.barco);
          x.estado = 'ok';
        } catch (err) {
          // un archivo repetido no es un fallo: ya está en la sesión
          x.estado = /ya está en la sesión/.test(err.message) ? 'ok' : 'error';
          if (x.estado === 'error') error = err.message;
        }
      }
      progreso = '';
      if (lista.every((x) => x.estado === 'ok')) {
        lista = [];
        onHecho?.(id);
      }
    } catch (err) {
      progreso = '';
      error = err.message;
    }
  }
</script>

<form onsubmit={enviar}>
  {#if !sid && !camp}
    <label class="etiqueta" for="s-nombre">Nombre</label>
    <input id="s-nombre" class="campo" bind:value={nombre} placeholder="Regata de Barcelona, mayo 2025">
    <label class="etiqueta" for="s-clase">Clase</label>
    <input id="s-clase" class="campo" list="s-clases" bind:value={clase}>
    <datalist id="s-clases">{#each CLASES as c}<option value={c}></option>{/each}</datalist>
  {/if}

  <span class="etiqueta">Archivos .vkx</span>
  <div class="zona" class:encima role="group" aria-label="Archivos .vkx"
       ondragover={(e) => { e.preventDefault(); encima = true; }} ondragleave={() => (encima = false)} ondrop={soltar}>
    {#if lista.length}
      <ul>
        {#each lista as x, k (x.archivo.name + x.archivo.size)}
          <li class:ok={x.estado === 'ok'} class:mal={x.estado === 'error'}>
            <span class="nombre" title={x.archivo.name}>{x.archivo.name} <small class="tenue">{tamaño(x.archivo.size)}{x.estado === 'ok' ? ' · añadido' : x.estado === 'error' ? ' · error' : ''}</small></span>
            <input class="campo vela" aria-label={`Vela de ${x.archivo.name}`} placeholder="Vela" bind:value={x.vela} disabled={x.estado === 'ok'}>
            {#if !camp}<input class="campo barco" aria-label={`Nombre del barco de ${x.archivo.name}`} placeholder="Barco (opcional)" bind:value={x.barco} disabled={x.estado === 'ok'}>{:else}<span></span>{/if}
            <button type="button" class="quitar" aria-label={`Quitar ${x.archivo.name}`} onclick={() => lista.splice(k, 1)} disabled={!!progreso}>✕</button>
          </li>
        {/each}
      </ul>
    {:else}
      <p class="tenue vacio">Arrastra aquí los archivos, o elígelos con el botón. Puedes añadir de varias carpetas: cada vez que eliges, se suman a la lista.</p>
    {/if}
    <button type="button" class="boton claro" onclick={() => entrada.click()} disabled={!!progreso}>+ Añadir archivos…</button>
    <input class="oculto" type="file" accept=".vkx" multiple bind:this={entrada} onchange={(e) => añadir(e.currentTarget.files)}>
  </div>

  <button class="boton" disabled={!!progreso || !lista.length}>{progreso ? progreso + '…' : camp ? 'Añadir al campeonato' : sid ? `Añadir ${lista.length || ''} a la sesión` : 'Crear la sesión'}</button>
  {#if error}<p class="error" role="alert">{error}</p>{/if}
</form>

<style>
  form { display: grid; gap: 8px; }
  form > .boton { justify-self: start; }
  p { margin: 0; }
  .zona { display: grid; gap: 8px; padding: 10px; border: 1.5px dashed var(--linea); border-radius: 10px; }
  .zona.encima { border-color: var(--foco); background: color-mix(in srgb, var(--foco) 6%, transparent); }
  .zona > .boton { justify-self: start; font-size: 14px; padding: 5px 12px; }
  .vacio { font-size: 14px; }
  .oculto { display: none; }
  ul { list-style: none; margin: 0; padding: 0; display: grid; gap: 6px; }
  li { display: grid; grid-template-columns: minmax(0, 1fr) 11ch 14ch auto; gap: 6px; align-items: center; }
  li.ok .nombre small { color: var(--bien, #2e7d32); }
  li.mal .nombre small { color: var(--error, #c62828); }
  .nombre { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 14px; }
  li .campo { padding: 5px 8px; font-size: 14px; min-width: 0; }
  .quitar { background: none; border: 0; color: var(--tinta-3); font-size: 15px; padding: 4px 6px; cursor: pointer; }
  .quitar:hover { color: var(--tinta); }
  @media (max-width: 520px) {
    li { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) auto; }
    .nombre { grid-column: 1 / -1; }
  }
</style>
