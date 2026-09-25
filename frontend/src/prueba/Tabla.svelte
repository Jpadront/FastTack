<script>
  import Nota from '../Nota.svelte';
  // columnas: [{ k, titulo, fmt?, num?, est? (estimado), ayuda? }]; filas: objetos con .vela
  let { columnas, filas, ref, colores = {}, titulo = '', nota = '', ordenInicial = null } = $props();
  let orden = $state(ordenInicial);
  let asc = $state(true);

  const vista = $derived.by(() => {
    if (!orden) return filas;
    const k = orden;
    return [...filas].sort((a, b) => {
      const x = a[k], y = b[k];
      if (x == null && y == null) return 0;
      if (x == null) return 1;
      if (y == null) return -1;
      return (x < y ? -1 : x > y ? 1 : 0) * (asc ? 1 : -1);
    });
  });
  function ordenar(k) {
    if (orden === k) asc = !asc; else { orden = k; asc = true; }
  }
</script>

<section class="tarjeta bloque">
  {#if titulo}<h3>{titulo}</h3>{/if}
  <div class="rodillo">
    <table>
      <thead>
        <tr>
          {#each columnas as c, i}
            <th class:n={c.num} class:fija={i === 0} title={c.ayuda || ''}>
              <button onclick={() => ordenar(c.k)} aria-label={`Ordenar por ${c.titulo}`}>
                {c.titulo}{#if c.est}<span class="est" title="Estimado">*</span>{/if}{#if orden === c.k}<span aria-hidden="true">{asc ? ' ↑' : ' ↓'}</span>{/if}
              </button>
            </th>
          {/each}
        </tr>
      </thead>
      <tbody>
        {#each vista as f (f.vela)}
          <tr class:yo={f.vela === ref} class:tenue={f.baja}>
            {#each columnas as c, i}
              <td class:n={c.num} class:fija={i === 0} class:num={c.num}>
                {#if i === 0 && colores[f.vela]}<span class="punto" style:background={colores[f.vela]}></span>{/if}{c.fmt ? c.fmt(f[c.k], f) : (f[c.k] ?? '—')}
              </td>
            {/each}
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
  {#if nota}<div class="pie-nota"><Nota texto={nota} /></div>{/if}
</section>

<style>
  .bloque { padding: 10px 0 6px; }
  h3 { font-size: 15px; letter-spacing: .06em; text-transform: uppercase; color: var(--tinta-2); padding: 0 12px 6px; }
  .rodillo { overflow-x: auto; }
  table { border-collapse: collapse; width: 100%; font-size: 14px; }
  th { text-align: left; white-space: nowrap; border-bottom: 1px solid var(--linea); padding: 0; }
  th button { font: 600 11px var(--display); letter-spacing: .06em; text-transform: uppercase; color: var(--tinta-2); background: none; border: 0; padding: 6px 8px; width: 100%; text-align: inherit; white-space: nowrap; }
  th.n button { text-align: right; }
  td { padding: 5px 8px; border-bottom: 1px solid var(--rejilla); white-space: nowrap; background: var(--panel); }
  .n { text-align: right; }
  .fija { position: sticky; left: 0; z-index: 1; }
  th.fija { background: var(--panel); }
  tr.yo td { background: color-mix(in srgb, var(--yo) 14%, var(--panel)); font-weight: 600; }
  tr.tenue td { color: var(--tinta-3); }
  .punto { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; }
  .est { color: var(--estimado); margin-left: 1px; }
  .pie-nota { padding: 0 12px; }
</style>
