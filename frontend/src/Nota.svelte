<script>
  // Nota al pie de un bloque: si es corta se ve; si es larga (cómo se calcula), queda plegada.
  let { texto = '', corto = 140, resumen = 'Cómo se calcula', children = null } = $props();
  const largo = $derived(children != null || texto.length > corto);
</script>

{#if largo}
  <details class="ayuda"><summary>{resumen}</summary>
    <div class="cuerpo">{#if children}{@render children()}{:else}{texto}{/if}</div>
  </details>
{:else if texto}
  <p class="nota-corta">{texto}</p>
{/if}

<style>
  .nota-corta { font-size: 12px; color: var(--tinta-3); margin: 6px 0 0; }
  .ayuda { margin: 6px 0 0; font-size: 12px; color: var(--tinta-3); }
  .ayuda summary { cursor: pointer; font: 600 12px var(--display); letter-spacing: .04em; color: var(--tinta-2); list-style: none; display: inline-flex; align-items: center; gap: 5px; }
  .ayuda summary::-webkit-details-marker { display: none; }
  .ayuda summary::before { content: 'i'; display: inline-grid; place-items: center; width: 15px; height: 15px; border-radius: 50%;
    border: 1px solid currentColor; font: italic 700 10px Georgia, serif; }
  .ayuda[open] summary { margin-bottom: 4px; }
  .cuerpo { line-height: 1.45; max-width: 90ch; }
</style>
