<script>
  import { onMount, onDestroy } from 'svelte';
  import { api, horaLocal, duracion, clave } from './api.js';

  let { id, barco, onBarco } = $props();

  let camp = $state(null);
  let error = $state('');
  let temporizador;

  async function leer() {
    try {
      camp = await api.campeonato(id);
      error = '';
      if (camp.estado === 'cargando') temporizador = setTimeout(sondear, 1500);
    } catch (e) {
      error = e.message;
    }
  }
  async function actualizar() {
    try {
      await api.cargar(camp.url, camp.division);
      camp = { ...camp, estado: 'cargando', progreso: 'Empezando' };
      temporizador = setTimeout(sondear, 1500);
    } catch (e) {
      error = e.message;
    }
  }
  async function sondear() {
    try {
      const e = await api.estado(id);
      if (e.estado === 'cargando') {
        camp = { ...camp, progreso: e.progreso };
        temporizador = setTimeout(sondear, 1500);
      } else {
        await leer();
      }
    } catch (e) {
      error = e.message;
    }
  }
  onMount(leer);
  onDestroy(() => clearTimeout(temporizador));

  const nombres = $derived(Object.fromEntries((camp?.barcos || []).map((b) => [b.clave, b])));
  const miClave = $derived(clave(barco));

  function resultado(p) {
    const orden = Object.entries(p.llegadas).sort((a, b) => a[1] - b[1]).map(([v]) => v);
    const ganador = orden[0];
    let mio = '—';
    if (p.ocs.includes(miClave)) mio = 'OCS';
    else if (orden.includes(miClave)) mio = `${orden.indexOf(miClave) + 1}.º`;
    else if (orden.length) mio = p.estado === 'oficial' ? 'sin llegada' : 'sin dato';
    return {
      ganador: ganador ? nombres[ganador]?.vela || ganador : '—',
      tiempo: ganador ? duracion(p.llegadas[ganador] - p.senal) : '',
      mio,
      de: orden.length,
    };
  }

  async function ajustar(p, cambios) {
    try {
      camp = await api.ajustar(id, p.clave, cambios);
    } catch (e) {
      error = e.message;
    }
  }

  function viento(p, texto) {
    const v = texto.trim() === '' ? null : Number(texto.replace(',', '.'));
    if (v !== null && (isNaN(v) || v < 0 || v > 60)) { error = 'El viento de referencia va en nudos (0–60).'; return; }
    ajustar(p, { viento_kn: v });
  }

  let barcoTexto = $state('');
  $effect(() => { barcoTexto = nombres[miClave]?.vela || barco; });
  function elegirBarco(e) {
    e.preventDefault();
    const c = clave(barcoTexto.split(' · ')[0]);
    if (nombres[c]) onBarco(c);
    else error = `No encuentro «${barcoTexto}» en la flota de este campeonato.`;
  }

  const estadoTexto = { oficial: 'oficial', reconstruida: 'reconstruida', 'sin llegadas': 'sin llegadas' };
</script>

{#if error}<p class="error" role="alert">{error}</p>{/if}

{#if !camp}
  <p class="tenue">Cargando…</p>
{:else if camp.estado === 'cargando'}
  <section class="tarjeta aviso">
    <h1>{camp.nombre || 'Campeonato'}</h1>
    <p><span class="rueda" aria-hidden="true"></span>{camp.progreso || 'Descargando'}…</p>
    <p class="tenue">La primera vez tarda un poco: se buscan en la telemetría las pruebas que RaceSense no tiene. Después queda guardado.</p>
  </section>
{:else if camp.estado === 'error' && !camp.pruebas}
  <section class="tarjeta aviso">
    <h1>No se ha podido cargar</h1>
    <p class="error">{camp.error}</p>
    <a class="boton claro" href="#/">Volver</a>
  </section>
{:else}
  <header class="cab">
    <div>
      <div class="etiqueta">{camp.clase} · {camp.division} · {horaLocal(camp.inicio, camp.tz_offset_ms).split(' · ')[0]} – {horaLocal(camp.fin, camp.tz_offset_ms).split(' · ')[0]}</div>
      <h1>{camp.nombre}</h1>
      <p class="tenue">{camp.pruebas.filter((p) => !p.excluida).length} pruebas · {camp.barcos.length} barcos · datos de RaceSense (revisión {camp.revision})</p>
      <div class="acciones-camp">
        <a class="boton resumen" href={`#/c/${encodeURIComponent(id)}/resumen`}>Resumen del campeonato →</a>
        <button class="boton claro recargar" onclick={actualizar} title="Vuelve a leer el campeonato en RaceSense: pruebas y llegadas nuevas (la telemetría ya descargada se reutiliza)">↻ Actualizar pruebas</button>
      </div>
    </div>
    <form class="selector" onsubmit={elegirBarco}>
      <label class="etiqueta" for="barco">Barco de referencia</label>
      <div class="fila">
        <input id="barco" class="campo" list="flota" bind:value={barcoTexto} autocomplete="off">
        <button class="boton claro">Usar</button>
      </div>
      <datalist id="flota">
        {#each camp.barcos as b}<option value={`${b.vela}${b.nombre ? ' · ' + b.nombre : ''}`}></option>{/each}
      </datalist>
    </form>
  </header>

  {#if camp.desactualizado}
    <section class="tarjeta aviso-act" role="status">
      <p><b>Hay una versión mejor de la detección de pruebas y llegadas.</b> Vuelve a cargar el campeonato para aplicarla: la telemetría ya descargada se reutiliza y tus ajustes (viento, numeración, «Cuenta») se mantienen.</p>
      <button class="boton" onclick={actualizar}>Actualizar</button>
    </section>
  {/if}
  <section class="tarjeta lista">
    <table>
      <thead>
        <tr>
          <th class="n">Nº</th><th>Día y señal</th><th>Estado</th><th class="n">{nombres[miClave]?.vela || barco}</th>
          <th>Ganador</th><th class="n">Viento ref. (kn)</th><th>Cuenta</th>
        </tr>
      </thead>
      <tbody>
        {#each camp.pruebas as p (p.clave)}
          {@const r = resultado(p)}
          <tr class:excluida={p.excluida}>
            <td class="n num grande">{#if p.n_llegadas}<a class="abrir" href={`#/c/${encodeURIComponent(id)}/p/${p.clave}`} aria-label={`Analizar la prueba ${p.numero ?? ''}`}>{p.numero ?? '—'}</a>{:else}{p.numero ?? '—'}{/if}</td>
            <td>
              {horaLocal(p.senal, camp.tz_offset_ms)}
              {#if p.nota}<div class="nota" title={p.nota}>{p.nota}</div>{/if}
            </td>
            <td><span class="chip {p.estado.replace(' ', '-')}">{estadoTexto[p.estado]}</span></td>
            <td class="n num mio">{r.mio}{#if r.de}<span class="tenue de">/{r.de}</span>{/if}</td>
            <td>{r.ganador}{#if r.tiempo}<span class="tenue num tiempo">{r.tiempo}</span>{/if}
              {#if p.n_llegadas}<a class="analizar" href={`#/c/${encodeURIComponent(id)}/p/${p.clave}`}>Analizar →</a>{/if}</td>
            <td class="n">
              <input class="campo viento num" inputmode="decimal" aria-label={`Viento de referencia de la prueba ${p.numero ?? ''}`}
                     value={p.viento_kn ?? ''} placeholder="—" title="Viento en el disparo (kn). Vacío: intensidad sin calibrar" onchange={(e) => viento(p, e.currentTarget.value)}>
            </td>
            <td>
              <label class="cuenta"><input type="checkbox" checked={!p.excluida}
                     onchange={(e) => ajustar(p, { excluida: !e.currentTarget.checked })}> {p.excluida ? 'no' : 'sí'}</label>
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  </section>
  <p class="tenue pie">«Reconstruida»: prueba o llegadas obtenidas de la telemetría porque RaceSense no las tiene (puesto provisional). «Cuenta»: desmárcala para dejar fuera una prueba (entrenamiento, anulada); la numeración se ajusta sola. Pulsa «Analizar» para abrir el análisis de una prueba.</p>
{/if}

<style>
  .aviso { padding: 18px; display: grid; gap: 8px; max-width: 720px; }
  .aviso p { margin: 0; }
  .rueda { display: inline-block; width: 12px; height: 12px; margin-right: 8px; border: 2px solid var(--linea); border-top-color: var(--yo); border-radius: 50%; animation: gira 1s linear infinite; vertical-align: -1px; }
  @keyframes gira { to { transform: rotate(360deg); } }
  @media (prefers-reduced-motion: reduce) { .rueda { animation: none; } }
  .cab { display: flex; justify-content: space-between; align-items: end; gap: 16px; flex-wrap: wrap; margin-bottom: 14px; }
  .cab h1 { font-size: clamp(24px, 4vw, 34px); margin-top: 2px; }
  .cab p { margin: 4px 0 0; }
  .selector { display: grid; gap: 4px; min-width: min(320px, 100%); }
  .fila { display: flex; gap: 6px; }
  .lista { overflow-x: auto; }
  table { border-collapse: collapse; width: 100%; font-size: 15px; }
  th { text-align: left; font: 600 12px var(--display); letter-spacing: .06em; text-transform: uppercase; color: var(--tinta-2); padding: 10px 10px 8px; border-bottom: 1px solid var(--linea); white-space: nowrap; }
  td { padding: 9px 10px; border-bottom: 1px solid var(--rejilla); vertical-align: top; }
  .n { text-align: right; }
  .grande { font-size: 18px; font-weight: 500; }
  .mio { color: var(--yo); font-weight: 600; white-space: nowrap; }
  .de { margin-left: 4px; font-weight: 400; }
  .nota { font-size: 13px; color: var(--tinta-3); max-width: 46ch; display: -webkit-box; -webkit-line-clamp: 1; line-clamp: 1; -webkit-box-orient: vertical; overflow: hidden; }
  tr.excluida td { color: var(--tinta-3); }
  tr.excluida .mio { color: var(--tinta-3); }
  .viento { width: 7ch; text-align: right; padding: 5px 8px; font-size: 14px; }
  .viento::placeholder { color: var(--tinta-3); }
  .tiempo { margin-left: 8px; }
  .cuenta { display: inline-flex; gap: 6px; align-items: center; white-space: nowrap; }
  .pie { font-size: 14px; max-width: 90ch; margin-top: 10px; }
  .abrir { color: inherit; text-decoration: none; }
  .analizar { display: inline-block; margin-left: 10px; font: 600 14px var(--display); color: var(--foco); text-decoration: none; white-space: nowrap;
    border: 1px solid color-mix(in srgb, var(--foco) 40%, transparent); border-radius: 14px; padding: 1px 10px; }
  .analizar:hover { background: color-mix(in srgb, var(--foco) 10%, transparent); }
  tbody tr:hover td { background: color-mix(in srgb, var(--foco) 4%, transparent); }

  /* Móvil: cada prueba es una ficha */
  @media (max-width: 700px) {
    table, tbody, tr, td { display: block; }
    thead { display: none; }
    tr { display: grid; grid-template-columns: auto 1fr auto; gap: 2px 10px; padding: 10px 12px; border-bottom: 1px solid var(--rejilla); }
    td { border: 0; padding: 0; }
    td:nth-child(1) { grid-row: span 2; align-self: center; }
    td:nth-child(2) { grid-column: 2; }
    td:nth-child(3) { grid-column: 3; justify-self: end; }
    td:nth-child(4) { grid-column: 3; text-align: right; }
    td:nth-child(5) { grid-column: 2 / 4; font-size: 14px; display: flex; align-items: center; gap: 6px; }
    td:nth-child(5) .analizar { margin-left: auto; }
    td:nth-child(6), td:nth-child(7) { display: flex; align-items: center; gap: 6px; margin-top: 4px; }
    td:nth-child(6) { grid-column: 2; }
    td:nth-child(7) { grid-column: 3; justify-content: flex-end; }
    td:nth-child(6)::before { content: 'Viento kn'; font: 600 12px var(--display); letter-spacing: .06em; text-transform: uppercase; color: var(--tinta-2); }
    td:nth-child(7)::before { content: 'Cuenta'; font: 600 12px var(--display); letter-spacing: .06em; text-transform: uppercase; color: var(--tinta-2); }
    .n { text-align: left; }
  }
  .acciones-camp { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 6px; }
  .resumen { display: inline-block; text-decoration: none; font-size: 15px; padding: 7px 14px; }
  .recargar { font-size: 15px; padding: 7px 14px; }
  .aviso-act { display: flex; gap: 12px; align-items: center; justify-content: space-between; flex-wrap: wrap; padding: 10px 14px; margin-bottom: 10px; border-left: 4px solid var(--estimado); }
  .aviso-act p { margin: 0; font-size: 14px; flex: 1 1 320px; }
</style>
