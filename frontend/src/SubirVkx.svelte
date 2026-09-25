<script>
  // Crear una sesión propia con archivos .vkx del Atlas 2, o añadir archivos a una ya creada (sid).
  import { onMount } from 'svelte';
  import { api, velaBonita } from './api.js';

  let { sid = null, onHecho } = $props();

  const CLASES = ['J/70', 'J/80', 'J/24', 'Snipe', 'ILCA', '470', '420', '49er', 'Nacra 17', 'Finn', 'Star', 'Etchells',
    'Melges 24', 'Melges 20', 'SB20', 'Dragon', 'Optimist', '29er', 'Flying Fifteen', 'RS21', 'J/111', 'Fireball'];

  let nombre = $state('');
  let clase = $state('J/70');
  let vela = $state('');
  let barco = $state('');
  let archivos = $state([]);
  let error = $state('');
  let progreso = $state('');
  let entrada;

  onMount(async () => {
    if (!sid) {
      const p = await api.preferencias().catch(() => null);
      if (p?.barco) vela = velaBonita(p.barco);
    }
  });

  function elegir(e) {
    archivos = [...e.currentTarget.files];
    if (archivos.length) {
      // «MonjoII_10-5-2025.vkx» → propone el barco
      const base = archivos[0].name.replace(/\.vkx$/i, '').split(/[_-]/)[0];
      if (!barco && base && !/^\d/.test(base)) barco = base;
    }
  }

  async function enviar(e) {
    e.preventDefault();
    error = '';
    if (!archivos.length) { error = 'Elige al menos un archivo .vkx.'; return; }
    try {
      let id = sid;
      if (!id) {
        progreso = 'Creando la sesión';
        id = (await api.crearSesion(nombre || 'Sesión propia', clase)).id;
      }
      for (const [k, a] of archivos.entries()) {
        progreso = `Leyendo ${a.name} (${k + 1} de ${archivos.length})`;
        await api.subirVkx(id, a, vela, barco);
      }
      progreso = '';
      archivos = [];
      if (entrada) entrada.value = '';
      onHecho?.(id);
    } catch (err) {
      progreso = '';
      error = err.message;
    }
  }
</script>

<form onsubmit={enviar}>
  {#if !sid}
    <label class="etiqueta" for="s-nombre">Nombre</label>
    <input id="s-nombre" class="campo" bind:value={nombre} placeholder="Regata de Barcelona, mayo 2025">
    <label class="etiqueta" for="s-clase">Clase</label>
    <input id="s-clase" class="campo" list="s-clases" bind:value={clase}>
    <datalist id="s-clases">{#each CLASES as c}<option value={c}></option>{/each}</datalist>
  {/if}
  <div class="dos">
    <div>
      <label class="etiqueta" for="s-vela">Vela del barco</label>
      <input id="s-vela" class="campo" required bind:value={vela} placeholder="ESP 1214">
    </div>
    <div>
      <label class="etiqueta" for="s-barco">Nombre del barco</label>
      <input id="s-barco" class="campo" bind:value={barco} placeholder="opcional">
    </div>
  </div>
  <label class="etiqueta" for="s-arch">Archivos .vkx de ese barco (uno por día)</label>
  <input id="s-arch" class="campo" type="file" accept=".vkx" multiple bind:this={entrada} onchange={elegir}>
  <button class="boton" disabled={!!progreso || !archivos.length || !vela}>{progreso ? progreso + '…' : sid ? 'Añadir' : 'Crear la sesión'}</button>
  {#if error}<p class="error" role="alert">{error}</p>{/if}
</form>

<style>
  form { display: grid; gap: 8px; }
  form .boton { justify-self: start; }
  .dos { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 8px; }
  .dos > div { display: grid; gap: 8px; }
  p { margin: 0; }
</style>
