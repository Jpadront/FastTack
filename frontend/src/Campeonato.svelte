<script>
  import { onMount, onDestroy } from 'svelte';
  import { api, horaLocal, duracion, clave } from './api.js';
  import SubirVkx from './SubirVkx.svelte';

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

  let ajustes = $state(false);   // columnas de ajuste (viento de referencia, cuenta, reglaje)
  // Tus puestos en las pruebas que cuentan, para la banda de arriba
  const mios = $derived(!camp?.pruebas ? [] : camp.pruebas.filter((p) => !p.excluida && p.n_llegadas).map((p) => {
    const orden = Object.entries(p.llegadas).sort((a, b) => a[1] - b[1]).map(([v]) => v);
    const k = orden.indexOf(miClave);
    return { clave: p.clave, numero: p.numero, pos: k >= 0 ? k + 1 : null, de: orden.length, ocs: p.ocs.includes(miClave) };
  }));
  const conPuesto = $derived(mios.filter((m) => m.pos != null));
  const media = $derived(conPuesto.length ? conPuesto.reduce((a, m) => a + m.pos, 0) / conPuesto.length : null);
  const mejorP = $derived(conPuesto.length ? conPuesto.reduce((a, m) => (m.pos < a.pos ? m : a)) : null);
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

  const estadoTexto = { oficial: 'oficial', reconstruida: 'reconstruida', 'sin llegadas': 'sin llegadas', estimada: 'estimada' };
  const propia = $derived(camp?.fuente === 'vkx');

  // Reglaje de cada prueba: pares ajuste → valor, libres (con sugerencias)
  const AJUSTES = ['Obenques altos', 'Obenques bajos', 'Backstay', 'Pie de mástil', 'Mayor', 'Foque / génova', 'Spi', 'Peso tripulación'];
  let reglajeDe = $state(null);   // clave de la prueba que se edita
  let filasReglaje = $state([]);
  // Semáforo de datos de cada prueba ya analizada (VMG frente a la flota, motor/semaforo.py)
  const COLOR_SEM = { bien: '#1a7f4b', normal: '#d39b00', mal: '#c0392b' };
  let semaforos = $state({});
  $effect(() => { if (camp?.pruebas && miClave) api.semaforos(id, miClave).then((r) => (semaforos = r)).catch(() => {}); });
  const textoSem = (x) => (x ? `${x.nivel}: VMG mejor que el ${x.percentil} % de la flota` + (x['percentil_ceñida'] != null && x.percentil_popa != null ? ` (ceñida ${x['percentil_ceñida']} %, popa ${x.percentil_popa} %)` : '') : '');
  function editarReglaje(p) {
    if (reglajeDe === p.clave) { reglajeDe = null; return; }
    reglajeDe = p.clave;
    const r = Object.entries(p.reglaje || {});
    filasReglaje = r.length ? r.map(([k, v]) => ({ k, v })) : AJUSTES.slice(0, 3).map((k) => ({ k, v: '' }));
  }
  function copiarAnterior(p) {
    const antes = camp.pruebas.filter((q) => q.senal < p.senal && Object.keys(q.reglaje || {}).length);
    const q = antes[antes.length - 1];
    if (q) filasReglaje = Object.entries(q.reglaje).map(([k, v]) => ({ k, v }));
  }
  async function guardarReglaje(p) {
    const r = Object.fromEntries(filasReglaje.filter((f) => f.k.trim() && f.v.trim()).map((f) => [f.k.trim(), f.v.trim()]));
    await ajustar(p, { reglaje: r });
    reglajeDe = null;
  }
  async function quitarPropio(a) {
    if (!confirm(`¿Quitar ${a.archivo || 'el archivo'} (${a.vela})? El barco volverá a analizarse con los datos de RaceSense.`)) return;
    try { await api.quitarVkxCampeonato(id, a.n); await leer(); } catch (e) { error = e.message; }
  }
  async function quitar(a) {
    if (!confirm(`¿Quitar ${a.archivo || 'el archivo'} (${a.vela}) de la sesión?`)) return;
    try {
      await api.quitarVkx(id, a.n);
      await leer();
    } catch (e) {
      error = e.message;
    }
  }
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
  <a class="volver" href="#/">← Campeonatos</a>
  <header class="cab">
    <div>
      <div class="etiqueta">{camp.clase} · {camp.division} · {horaLocal(camp.inicio, camp.tz_offset_ms).split(' · ')[0]} – {horaLocal(camp.fin, camp.tz_offset_ms).split(' · ')[0]}</div>
      <h1>{camp.nombre}</h1>
      <p class="tenue">{camp.pruebas.filter((p) => !p.excluida).length} pruebas · {camp.barcos.length} {camp.barcos.length === 1 ? 'barco' : 'barcos'} · {propia ? `archivos .vkx del Atlas (${camp.archivos.length})` : `datos de RaceSense (revisión ${camp.revision})`}</p>
      <div class="acciones-camp">
        <a class="boton resumen" href={`#/c/${encodeURIComponent(id)}/resumen`}>Resumen {propia ? 'de la sesión' : 'del campeonato'} →</a>
        <button class="boton claro" aria-pressed={ajustes} onclick={() => (ajustes = !ajustes)} title="Viento de referencia, qué pruebas cuentan y reglaje de cada prueba">{ajustes ? 'Ocultar ajustes' : '⚙ Ajustes de las pruebas'}</button>
        {#if !propia}<button class="boton claro recargar" onclick={actualizar} title="Vuelve a leer el campeonato en RaceSense: pruebas y llegadas nuevas (la telemetría ya descargada se reutiliza)">↻ Actualizar pruebas</button>{/if}
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

  {#if mios.length}
    <section class="heroe" aria-label="Tus resultados en el campeonato">
      <div class="dato principal">
        <span class="et">{nombres[miClave]?.vela || barco}</span>
        <b class="num">{media == null ? '—' : media.toFixed(1).replace('.', ',') + '.º'}<small> de media</small></b>
        <span class="det">{conPuesto.length} de {mios.length} pruebas con llegada{mejorP ? ` · mejor: ${mejorP.pos}.º en la ${mejorP.numero ?? '—'}` : ''}</span>
      </div>
      <div class="dato puestos">
        <span class="et">Puesto en cada prueba</span>
        <div class="barras-p" role="img" aria-label={mios.map((m) => `prueba ${m.numero}: ${m.pos ?? (m.ocs ? 'OCS' : 'sin llegada')}`).join(', ')}>
          {#each mios as m (m.clave)}
            <a class="bp" href={`#/c/${encodeURIComponent(id)}/p/${m.clave}`} title={`Prueba ${m.numero ?? '—'}: ${m.pos ? m.pos + '.º de ' + m.de : m.ocs ? 'OCS' : 'sin llegada'}`}>
              <span class="v num">{m.pos ?? (m.ocs ? 'OCS' : '—')}</span>
              <span class="col"><span class="rel" style:height={m.pos ? `${Math.max(6, (1 - (m.pos - 1) / Math.max(1, m.de - 1)) * 100)}%` : '0'}></span></span>
              <span class="n num">{m.numero ?? '—'}</span>
            </a>
          {/each}
        </div>
      </div>
    </section>
  {/if}
  {#if camp.desactualizado && !propia}
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
          <th>Ganador</th>{#if ajustes}<th class="n">Viento ref. (kn)</th><th>Cuenta</th>{/if}
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
            <td class="n num mio">{#if semaforos[p.clave]}<i class="sem" style:background={COLOR_SEM[semaforos[p.clave].nivel]} title={`Velocidad ${textoSem(semaforos[p.clave])}`}></i>{/if}{r.mio}{#if r.de}<span class="tenue de">/{r.de}</span>{/if}</td>
            <td>{r.ganador}{#if r.tiempo}<span class="tenue num tiempo">{r.tiempo}</span>{/if}
              {#if p.n_llegadas}<a class="analizar" href={`#/c/${encodeURIComponent(id)}/p/${p.clave}`}>Analizar →</a>{/if}</td>
            {#if ajustes}<td class="n">
              <input class="campo viento num" inputmode="decimal" aria-label={`Viento de referencia de la prueba ${p.numero ?? ''}`}
                     value={p.viento_kn ?? ''} placeholder="—" title="Viento en el disparo (kn). Vacío: intensidad sin calibrar" onchange={(e) => viento(p, e.currentTarget.value)}>
            </td>
            <td>
              <label class="cuenta"><input type="checkbox" checked={!p.excluida}
                     onchange={(e) => ajustar(p, { excluida: !e.currentTarget.checked })}> {p.excluida ? 'no' : 'sí'}</label>
              {#if p.n_llegadas}<button class="enlace reglaje" onclick={() => editarReglaje(p)} title={Object.entries(p.reglaje || {}).map(([k, v]) => `${k}: ${v}`).join(' · ') || 'Sin reglaje apuntado'}>Reglaje{Object.keys(p.reglaje || {}).length ? ' ✓' : ''}</button>{/if}
            </td>{/if}
          </tr>
          {#if reglajeDe === p.clave}
            <tr class="fila-reglaje"><td colspan={ajustes ? 7 : 5}>
              <form class="reglaje-form" onsubmit={(e) => { e.preventDefault(); guardarReglaje(p); }}>
                {#each filasReglaje as f, k}
                  <div class="par">
                    <input class="campo" list="ajustes" placeholder="Ajuste" bind:value={f.k} aria-label="Ajuste">
                    <input class="campo" placeholder="Valor" bind:value={f.v} aria-label={`Valor de ${f.k || 'ajuste'}`}>
                    <button type="button" class="enlace" aria-label="Quitar" onclick={() => filasReglaje.splice(k, 1)}>✕</button>
                  </div>
                {/each}
                <p class="semaforo">{#if semaforos[p.clave]}<i class="sem" style:background={COLOR_SEM[semaforos[p.clave].nivel]}></i><b>Según los datos, fuisteis {semaforos[p.clave].nivel}</b>: {textoSem(semaforos[p.clave]).split(': ')[1]}.{:else}<span class="tenue">El semáforo de velocidad sale al analizar la prueba (botón «Analizar»).</span>{/if}</p>
                <datalist id="ajustes">{#each AJUSTES as a}<option value={a}></option>{/each}</datalist>
                <div class="acciones-reglaje">
                  <button type="button" class="enlace" onclick={() => filasReglaje.push({ k: '', v: '' })}>+ ajuste</button>
                  <button type="button" class="enlace" onclick={() => copiarAnterior(p)}>Copiar de la prueba anterior</button>
                  <button class="boton">Guardar</button>
                </div>
              </form>
            </td></tr>
          {/if}
        {/each}
      </tbody>
    </table>
  </section>
  {#if propia}
    <section class="tarjeta archivos">
      <h2>Archivos de la sesión</h2>
      <ul>
        {#each camp.archivos as a (a.n)}
          <li>
            <b>{a.vela}</b>{#if a.nombre} · {a.nombre}{/if}
            <span class="tenue">{a.archivo} · {horaLocal(a.desde, camp.tz_offset_ms)}–{horaLocal(a.hasta, camp.tz_offset_ms, false)} · {a.salidas} salidas · {a.pings} pings de línea</span>
            <button class="enlace" onclick={() => quitar(a)}>Quitar</button>
          </li>
        {/each}
      </ul>
      <details>
        <summary>Añadir archivos (otro día u otro barco)</summary>
        <SubirVkx sid={id} onHecho={leer} />
      </details>
    </section>
    <p class="tenue pie">«Estimada»: la llegada de cada barco es el final de su último tramo (los archivos no traen la línea de llegada) y las balizas salen de sus rodeos. La salida usa los pings de pin y comité del Atlas. Con pocos barcos no hay comparación con la flota ni top 5; cuantos más archivos de otros barcos del mismo día, más completo el análisis.</p>
  {:else}
    <section class="tarjeta archivos">
      <h2>Tus archivos .vkx</h2>
      <p class="tenue">RaceSense pierde muchas muestras. Si añades el registro de tu Atlas (el .vkx de cada día), tu barco se analiza con sus datos completos (maniobras, salida, escora) y el resto de la flota sigue viniendo de RaceSense.</p>
      {#if camp.propios?.length}
        <ul>
          {#each camp.propios as a (a.n)}
            <li><b>{a.vela}</b> <span class="tenue">{a.archivo} · {horaLocal(a.desde, camp.tz_offset_ms)}–{horaLocal(a.hasta, camp.tz_offset_ms, false)} · cubre {a.pruebas} {a.pruebas === 1 ? 'prueba' : 'pruebas'}</span>
              <button class="enlace" onclick={() => quitarPropio(a)}>Quitar</button></li>
          {/each}
        </ul>
      {/if}
      <details>
        <summary>Añadir archivos .vkx</summary>
        <SubirVkx camp={id} onHecho={leer} />
      </details>
    </section>
  <p class="tenue pie">«Reconstruida»: prueba o llegadas obtenidas de la telemetría porque RaceSense no las tiene (puesto provisional). «Cuenta»: desmárcala para dejar fuera una prueba (entrenamiento, anulada); la numeración se ajusta sola. Pulsa «Analizar» para abrir el análisis de una prueba.</p>
  {/if}
{/if}

<style>
  .aviso { padding: 18px; display: grid; gap: 8px; max-width: 720px; }
  .aviso p { margin: 0; }
  .rueda { display: inline-block; width: 12px; height: 12px; margin-right: 8px; border: 2px solid var(--linea); border-top-color: var(--yo); border-radius: 50%; animation: gira 1s linear infinite; vertical-align: -1px; }
  @keyframes gira { to { transform: rotate(360deg); } }
  @media (prefers-reduced-motion: reduce) { .rueda { animation: none; } }
  .volver { display: inline-block; font: 600 14px var(--display); color: var(--tinta-2); text-decoration: none; margin-bottom: 4px; }
  .cab { display: flex; justify-content: space-between; align-items: end; gap: 16px; flex-wrap: wrap; margin-bottom: 14px; }
  .cab h1 { font-size: clamp(24px, 4vw, 34px); margin-top: 2px; }
  .cab p { margin: 4px 0 0; }
  .selector { display: grid; gap: 4px; min-width: min(320px, 100%); }
  .fila { display: flex; gap: 6px; }
  .lista { overflow-x: auto; }
  .semaforo { margin: 4px 0 6px; font-size: 14px; }
  .sem { display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin: 0 6px 1px 4px; vertical-align: middle; }
  .puestos { gap: 6px; }
  .barras-p { display: flex; gap: 6px; align-items: end; height: 92px; overflow-x: auto; }
  .bp { display: grid; grid-template-rows: auto 1fr auto; justify-items: center; gap: 2px; min-width: 28px; height: 100%; text-decoration: none; color: inherit; }
  .bp .v { font-size: 12px; color: #e6eff2; }
  .bp .col { width: 18px; height: 100%; background: rgba(143, 176, 189, .15); border-radius: 3px; display: flex; align-items: end; }
  .bp .rel { width: 100%; background: #ff8a52; border-radius: 3px; }
  .bp:hover .rel { background: #ffb08a; }
  .bp .n { font-size: 11px; color: #8fb0bd; }
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
    tr.fila-reglaje { display: block; }
    tr.fila-reglaje td { display: block; }
  }
  .archivos { padding: 14px 16px; margin-top: 12px; display: grid; gap: 10px; }
  .archivos h2 { font-size: 20px; margin: 0; }
  .archivos ul { list-style: none; margin: 0; padding: 0; display: grid; gap: 6px; }
  .archivos li { display: flex; flex-wrap: wrap; gap: 4px 10px; align-items: baseline; }
  .archivos li .tenue { font-size: 14px; }
  .archivos summary { cursor: pointer; font: 600 15px var(--display); color: var(--foco); margin-bottom: 8px; }
  .enlace { background: none; border: 0; padding: 0; color: var(--foco); text-decoration: underline; font-size: 14px; }
  .reglaje { display: block; margin-top: 4px; font-size: 13px; }
  .fila-reglaje td { background: color-mix(in srgb, var(--foco) 4%, transparent); }
  .reglaje-form { display: grid; gap: 6px; max-width: 560px; }
  .par { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) auto; gap: 6px; }
  .par .campo { padding: 5px 8px; font-size: 14px; }
  .acciones-reglaje { display: flex; gap: 14px; align-items: center; flex-wrap: wrap; }
  .acciones-reglaje .boton { padding: 5px 14px; font-size: 14px; }
  .acciones-camp { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 6px; }
  .resumen { display: inline-block; text-decoration: none; font-size: 15px; padding: 7px 14px; }
  .recargar { font-size: 15px; padding: 7px 14px; }
  .aviso-act { display: flex; gap: 12px; align-items: center; justify-content: space-between; flex-wrap: wrap; padding: 10px 14px; margin-bottom: 10px; border-left: 4px solid var(--estimado); }
  .aviso-act p { margin: 0; font-size: 14px; flex: 1 1 320px; }
</style>
