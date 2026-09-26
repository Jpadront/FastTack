<script>
  // Debrief con IA de una prueba (ambito = su clave) o del campeonato (ambito = 'campeonato').
  // Dos caminos: Claude Code en este ordenador, o copiar las instrucciones a Claude.ai y pegar la respuesta.
  import { onMount } from 'svelte';
  import { api } from './api.js';

  let { campId, ambito, barco, titulo = 'Debrief · IA' } = $props();

  let estado = $state(null), error = $state(''), generando = $state(false);
  let manual = $state(false), pegado = $state(''), copiado = $state(false);

  async function leer() {
    try { estado = await api.debrief(campId, ambito, barco); error = ''; } catch (e) { error = e.message; }
  }
  // La generación va en segundo plano en el servidor: se consulta hasta que termina
  async function esperar() {
    generando = true;
    while (true) {
      await new Promise((r) => setTimeout(r, 3000));
      await leer();
      if (!estado?.generando) break;
    }
    generando = false;
    if (estado?.error && !estado?.vigente) error = estado.error;
  }
  onMount(async () => { await leer(); if (estado?.generando) esperar(); });

  async function generar() {
    generando = true; error = '';
    try { await api.generarDebrief(campId, ambito, barco); await esperar(); } catch (e) { error = e.message; generando = false; }
  }
  async function guardarPegado() {
    error = '';
    try { await api.generarDebrief(campId, ambito, barco, pegado); pegado = ''; manual = false; await leer(); } catch (e) { error = e.message; }
  }
  async function copiar() {
    const t = estado.instrucciones;
    try { await navigator.clipboard.writeText(t); } catch {
      // http desde el móvil: el portapapeles moderno no está disponible
      const a = document.createElement('textarea'); a.value = t; document.body.appendChild(a); a.select();
      try { document.execCommand('copy'); } catch {} a.remove();
    }
    copiado = true; setTimeout(() => (copiado = false), 2500);
  }

  // Markdown mínimo (encabezados, listas, negrita) sobre texto escapado; las cifras sin comprobar, resaltadas
  const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  function html(texto, avisos) {
    let out = '', lista = null;
    const cerrar = () => { if (lista) { out += `</${lista}>`; lista = null; } };
    for (const l of esc(texto).split('\n')) {
      const t = l.trim();
      let m;
      if (!t) { cerrar(); continue; }
      if ((m = t.match(/^#{1,4}\s+(.*)/))) { cerrar(); out += `<h4>${m[1]}</h4>`; }
      else if ((m = t.match(/^\d+[.)]\s+(.*)/))) { if (lista !== 'ol') { cerrar(); out += '<ol>'; lista = 'ol'; } out += `<li>${m[1]}</li>`; }
      else if ((m = t.match(/^[-*•]\s+(.*)/))) { if (lista !== 'ul') { cerrar(); out += '<ul>'; lista = 'ul'; } out += `<li>${m[1]}</li>`; }
      else { cerrar(); out += `<p>${t}</p>`; }
    }
    cerrar();
    out = out.replace(/\*\*(.+?)\*\*/g, '<b>$1</b>');
    for (const a of new Set(avisos)) out = out.split(esc(a)).join(`<mark title="Cifra que no está en los datos del análisis">${esc(a)}</mark>`);
    return out;
  }
  const d = $derived(estado?.debrief);
  const fecha = (ms) => new Date(ms).toLocaleString('es-ES', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
</script>

<section class="tarjeta debrief">
  <div class="cab">
    <h3>{titulo}</h3>
    {#if d}<span class="meta">{d.origen === 'manual' ? 'pegado desde Claude.ai' : 'Claude Code'} · {fecha(d.creado_en)}</span>{/if}
  </div>

  {#if error}<p class="error" role="alert">{error}</p>{/if}
  {#if !estado && !error}<p class="tenue">Cargando…</p>{/if}

  {#if d}
    {#if d.avisos.length}
      <p class="aviso">⚠ {d.avisos.length} {d.avisos.length === 1 ? 'cifra no aparece' : 'cifras no aparecen'} en los datos del análisis (resaltadas): {d.avisos.join(' · ')}. Tómalas con cautela o regenera el texto.</p>
    {:else}
      <p class="ok">✓ Todas las cifras del texto están en los datos del análisis.</p>
    {/if}
    {#if !estado.vigente}<p class="aviso">Las cifras del análisis han cambiado desde que se escribió este texto: conviene regenerarlo.</p>{/if}
    <div class="texto">{@html html(d.texto, d.avisos)}</div>
  {:else if estado}
    <p class="tenue">Aún no hay debrief. La IA solo redacta: recibe las cifras del análisis y cada cifra de su texto se comprueba contra ellas.</p>
  {/if}

  {#if estado}
    <div class="acciones">
      {#if estado.claude_code}
        <button class="boton" onclick={generar} disabled={generando}>
          {#if generando}<span class="rueda" aria-hidden="true"></span>Escribiendo… (30–60 s){:else}{d ? 'Regenerar' : 'Generar'} con Claude Code{/if}
        </button>
      {/if}
      <button class="boton claro" onclick={() => (manual = !manual)} aria-expanded={manual}>{estado.claude_code ? 'O con Claude.ai…' : 'Generar con Claude.ai…'}</button>
    </div>
    {#if !estado.claude_code}<p class="nota">Claude Code no está instalado en el ordenador donde corre FastTack: usa Claude.ai.</p>{/if}
    {#if manual}
      <ol class="pasos">
        <li><button class="boton claro peq" onclick={copiar}>{copiado ? '✓ Copiadas' : 'Copiar las instrucciones'}</button> (llevan dentro las cifras del análisis)</li>
        <li>Abre <a href="https://claude.ai/new" target="_blank" rel="noopener">claude.ai</a>, pégalas en una conversación nueva y envía.</li>
        <li>Copia la respuesta entera, pégala aquí y guarda:
          <textarea bind:value={pegado} rows="8" placeholder="## Resumen…"></textarea>
          <button class="boton peq" onclick={guardarPegado} disabled={!pegado.trim()}>Guardar el debrief</button>
        </li>
      </ol>
      <details><summary>Ver las instrucciones</summary><textarea readonly rows="10" value={estado.instrucciones}></textarea></details>
    {/if}
  {/if}
</section>

<style>
  .debrief { padding: 10px 12px; border-left: 4px solid var(--estimado); }
  .cab { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; flex-wrap: wrap; }
  h3 { font-size: 15px; letter-spacing: .06em; text-transform: uppercase; color: var(--tinta-2); }
  .meta { font-size: 12px; color: var(--tinta-3); }
  .texto { font-size: 15px; line-height: 1.5; max-width: 760px; }
  .texto :global(h4) { font: 600 14px var(--display); letter-spacing: .05em; text-transform: uppercase; color: var(--tinta-2); margin: 14px 0 4px; }
  .texto :global(p) { margin: 4px 0; }
  .texto :global(ol), .texto :global(ul) { margin: 4px 0; padding-left: 22px; }
  .texto :global(li) { margin: 3px 0; }
  .texto :global(mark) { background: color-mix(in srgb, #eda100 35%, transparent); padding: 0 2px; border-radius: 2px; }
  .ok { font-size: 13px; color: #1b7a52; margin: 4px 0; }
  .aviso { font-size: 13px; color: var(--tinta); background: color-mix(in srgb, #eda100 18%, transparent); padding: 6px 8px; border-radius: 4px; margin: 6px 0; }
  .acciones { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 10px; }
  .boton { font-size: 15px; padding: 8px 14px; }
  .peq { font-size: 14px; padding: 5px 10px; }
  .pasos { font-size: 14px; padding-left: 20px; display: grid; gap: 8px; margin: 10px 0 6px; }
  textarea { display: block; width: 100%; box-sizing: border-box; margin: 6px 0; font: 13px var(--mono); padding: 6px; border: 1px solid var(--linea); border-radius: 4px; background: var(--panel); color: var(--tinta); }
  details { font-size: 13px; color: var(--tinta-2); }
  .nota { font-size: 12px; color: var(--tinta-3); margin: 6px 0 0; }
  .rueda { display: inline-block; width: 11px; height: 11px; margin-right: 8px; border: 2px solid rgba(255,255,255,.4); border-top-color: #fff; border-radius: 50%; animation: gira 1s linear infinite; vertical-align: -1px; }
  @keyframes gira { to { transform: rotate(360deg); } }
</style>
