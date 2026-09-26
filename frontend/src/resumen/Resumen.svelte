<script>
  import Nota from '../Nota.svelte';
  import { onMount } from 'svelte';
  import { api, clave as claveVela } from '../api.js';
  import { COLOR_YO, PALETA, num, velaCorta } from '../prueba/datos.js';
  import Tabla from '../prueba/Tabla.svelte';
  import GraficoPruebas from './GraficoPruebas.svelte';
  import Debrief from '../Debrief.svelte';
  import EscoraOptima from '../prueba/EscoraOptima.svelte';

  let { campId, barco } = $props();

  let camp = $state(null), res = $state(null), error = $state('');
  let progreso = $state('');           // «Analizando la prueba 3 de 10…»
  let descartes = $state(null);        // null = los del servidor por defecto
  let comparar = $state('top5');
  let verFlota = $state(false);
  let metrica = $state('vmg_ceñida');

  const clavePref = `fasttack.resumen.${campId}`;
  const ref = $derived(claveVela(barco));
  const nombres = $derived(Object.fromEntries((camp?.barcos || []).map((b) => [b.clave, b])));
  const vc = (v) => velaCorta(v, nombres);

  async function pedirResumen() {
    res = await api.resumen(campId, descartes);
  }
  // Las pruebas sin análisis se calculan una a una (la primera vez puede descargar telemetría)
  async function completar() {
    const pend = [...res.pendientes];
    for (const [i, c] of pend.entries()) {
      const p = res.pruebas.find((x) => x.clave === c);
      progreso = `Analizando la prueba ${p?.numero ?? ''} (${i + 1} de ${pend.length})…`;
      try { await api.analisis(campId, c); } catch { /* una prueba sin datos no para el resto */ }
    }
    progreso = '';
    if (pend.length) await pedirResumen();
  }
  onMount(async () => {
    try { const g = JSON.parse(localStorage.getItem(clavePref) || 'null'); if (g) { descartes = g.descartes ?? null; comparar = g.comparar || 'top5'; } } catch {}
    try {
      camp = await api.campeonato(campId);
      await pedirResumen();
      await completar();
    } catch (e) { error = e.message; }
  });
  async function cambiarDescartes(d) {
    descartes = d;
    guardar();
    try { await pedirResumen(); } catch (e) { error = e.message; }
  }
  function guardar() { try { localStorage.setItem(clavePref, JSON.stringify({ descartes, comparar })); } catch {} }

  let ambitoIA = $state('campeonato');
  const nombreDia = (d) => new Date(d + 'T12:00:00Z').toLocaleDateString('es-ES', { weekday: 'long', day: 'numeric', month: 'short', timeZone: 'UTC' });
  const SECCIONES = [['r-general', 'General'], ['r-puestos', 'Puestos'], ['r-metrica', 'Por prueba'], ['r-medias', 'Medias'],
    ['r-escora', 'Escora'], ['r-salidas', 'Salidas y maniobras'], ['r-viento', 'Viento'], ['r-debrief', 'Debrief IA']];
  // Sesión con un solo barco (archivos .vkx): sin general ni puestos, que no dicen nada
  const solo = $derived((res?.inscritos ?? 0) <= 1);
  const secciones = $derived(solo ? SECCIONES.filter(([id]) => id !== 'r-general' && id !== 'r-puestos') : SECCIONES);
  const pruebas = $derived(res ? res.pruebas.map((p) => `P${p.numero}`) : []);
  const general = $derived(res?.general || []);
  const miFila = $derived(general.find((f) => f.vela === ref));
  const comparados = $derived.by(() => {
    if (!res) return [];
    const n = comparar === 'solo' ? 0 : Number(comparar.slice(3));
    return [ref, ...general.filter((f) => f.vela !== ref).slice(0, n).map((f) => f.vela)].filter((v) => res.barcos[v]);
  });
  // Colores en orden fijo de la paleta según la general (el naranja, para el barco de referencia):
  // al pasar de top 3 a top 5 los tres primeros conservan su color.
  const colores = $derived(Object.fromEntries(comparados.filter((v) => v !== ref).map((v, k) => [v, PALETA[k % PALETA.length]]).concat([[ref, COLOR_YO]])));

  // ---------- general
  const filasGeneral = $derived.by(() => {
    const visibles = verFlota ? general : general.filter((f) => comparados.includes(f.vela) || f.puesto <= 10);
    return visibles.map((f) => ({ vela: f.vela, puesto: f.puesto, neto: f.neto, total: f.total,
      ...Object.fromEntries(f.puntos.map((p, k) => [`p${k}`, p])) }));
  });
  const fPts = (p) => (p == null ? '—' : (p.desc ? '(' : '') + (p.cod ? p.cod + ' ' : '') + p.pts + (p.desc ? ')' : ''));
  const columnasGeneral = $derived(res ? [
    { k: 'vela', titulo: 'Barco', fmt: vc },
    { k: 'puesto', titulo: 'Pos.', num: true },
    ...res.pruebas.map((p, k) => ({ k: `p${k}`, titulo: `P${p.numero}${p.estado === 'reconstruida' ? ' rec.' : ''}`, num: true, fmt: fPts })),
    { k: 'neto', titulo: 'Neto', num: true },
    { k: 'total', titulo: 'Total', num: true },
  ] : []);

  // ---------- gráficos por prueba
  const serie = (fn) => comparados.map((v) => ({ v, nombre: vc(v), color: colores[v], ref: v === ref,
    vals: res.barcos[v].por_prueba.map((f, k) => fn(f, k, v)) }));
  const seriePuesto = $derived(res ? serie((_, k, v) => { const p = general.find((g) => g.vela === v).puntos[k]; return p.cod ? null : p.pts; }) : []);
  const METRICAS = [
    ['vmg_ceñida', 'VMG en ceñida', 'kn', 2, true], ['vmg_popa', 'VMG en popa', 'kn', 2, true],
    ['sog_ceñida', 'SOG en ceñida', 'kn', 2], ['sog_popa', 'SOG en popa', 'kn', 2],
    ['twa_ceñida', 'TWA en ceñida', '°', 1, true], ['twa_popa', 'TWA en popa', '°', 1, true],
    ['escora_ceñida', 'Escora en ceñida', '°', 0], ['escora_popa', 'Escora en popa', '°', 0],
    ['cabeceo_ceñida', 'Cabeceo en ceñida', '°', 0], ['cabeceo_popa', 'Cabeceo en popa', '°', 0],
    ['perdida_virada_m', 'Pérdida por virada', 'm', 1, true], ['perdida_trasluchada_m', 'Pérdida por trasluchada', 'm', 1, true],
  ];
  const m = $derived(METRICAS.find((x) => x[0] === metrica));
  const serieMetrica = $derived(res ? serie((f) => f?.rend?.[metrica] ?? null) : []);
  const flotaMetrica = $derived(res ? res.pruebas.map((p) => p.flota?.[metrica] ?? null) : []);
  // «En el top 15 de la flota en X de Y pruebas» (solo métricas con orden de la flota)
  const topRef = $derived.by(() => {
    if (!res || !res.barcos[ref]) return null;
    const r = res.barcos[ref].por_prueba.map((f) => f?.rango?.[metrica]).filter((x) => x?.pos);
    return r.length ? { top: r.filter((x) => x.pos <= 15).length, de: r.length } : null;
  });

  // ---------- tablas acumuladas
  const T = (v) => res.barcos[v].totales;
  const filasSalida = $derived(res ? comparados.map((v) => ({ vela: v, ...T(v).salida })) : []);
  const filasManiobras = $derived(res ? comparados.map((v) => ({ vela: v,
    virada: T(v).rend.perdida_virada_m, trasluchada: T(v).rend.perdida_trasluchada_m,
    lay_ok: T(v).laylines.ok + T(v).laylines.sobrepasadas ? (T(v).laylines.ok / (T(v).laylines.ok + T(v).laylines.sobrepasadas)) * 100 : null,
    lay_n: T(v).laylines.ok + T(v).laylines.sobrepasadas, lay_m: T(v).laylines.metros,
    lay_sob: T(v).laylines.sobrepasadas, lay_traf: T(v).laylines.por_trafico ?? 0,
    puertas: T(v).puertas.total ? T(v).puertas.buenas : null, puertas_n: T(v).puertas.total })) : []);
  const filasRend = $derived(res ? comparados.map((v) => ({ vela: v, pos: general.find((g) => g.vela === v)?.puesto, analizadas: T(v).analizadas, ...T(v).rend })) : []);
  const conViento = $derived(res ? res.pruebas.filter((p) => p.viento_kn != null).length : 0);
  const dudosas = $derived(res ? res.pruebas.filter((p) => p.recorrido_dudoso).map((p) => p.numero) : []);
  const analizadas = $derived(res ? res.pruebas.filter((p) => p.analizada && !p.recorrido_dudoso).length : 0);

  const fKn = (v) => num(v, 2);
  const fG = (d) => (v) => (v == null ? '—' : num(v, d) + '°');
  const fM = (v) => (v == null ? '—' : num(v, 1) + ' m');
</script>

{#if error}
  <p class="error" role="alert">{error}</p>
  <a class="boton claro" href={`#/c/${encodeURIComponent(campId)}`}>Volver al campeonato</a>
{:else if !res}
  <p class="tenue"><span class="rueda" aria-hidden="true"></span>Calculando la general…</p>
{:else}
  <header class="cab">
    <div>
      <a class="volver" href={`#/c/${encodeURIComponent(campId)}`}>← {camp.nombre}</a>
      <h1>Resumen {camp.fuente === 'vkx' ? 'de la sesión' : 'del campeonato'}</h1>
      {#if solo}<p class="meta">{res.pruebas.length} pruebas · 1 barco (archivos .vkx): métricas de tu barco, sin comparación con la flota</p>{:else}
      <p class="meta">{res.pruebas.length} pruebas · {res.inscritos} barcos · general <b>calculada</b> con
        <select aria-label="Descartes" value={res.descartes} onchange={(e) => cambiarDescartes(Number(e.currentTarget.value))}>
          {#each [0, 1, 2, 3] as d}<option value={d}>{d} {d === 1 ? 'descarte' : 'descartes'}{d === res.descartes_defecto ? ' (por defecto)' : ''}</option>{/each}
        </select>
      </p>{/if}
    </div>
    {#if !solo}
    <div class="seleccion">
      <span class="etiqueta">Comparar con</span>
      <div class="modos" role="group" aria-label="Comparar con">
        {#each [['solo', 'Solo mi barco'], ['top3', 'Top 3'], ['top5', 'Top 5'], ['top10', 'Top 10']] as [k, t]}
          <button class:activo={comparar === k} aria-pressed={comparar === k} onclick={() => { comparar = k; guardar(); }}>{t}</button>
        {/each}
      </div>
    </div>
    {/if}
  </header>

  {#if progreso}<p class="progreso" role="status"><span class="rueda" aria-hidden="true"></span>{progreso} Las métricas se completan al terminar.</p>{/if}

  {#if solo}
  {:else if miFila}
    <section class="tiles">
      <div class="tarjeta tile"><i>Puesto calculado</i><b class="num">{miFila.puesto}.º</b><small>de {res.inscritos}</small></div>
      <div class="tarjeta tile"><i>Puntos netos</i><b class="num">{miFila.neto}</b><small>total {miFila.total}</small></div>
      <div class="tarjeta tile"><i>Mejor prueba</i><b class="num">{Math.min(...miFila.puntos.map((p) => p.pts))}.º</b><small>{pruebas[miFila.puntos.findIndex((p) => p.pts === Math.min(...miFila.puntos.map((q) => q.pts)))]}</small></div>
      <div class="tarjeta tile"><i>Puesto medio</i><b class="num">{num(miFila.puntos.filter((p) => !p.cod).reduce((a, p) => a + p.pts, 0) / Math.max(1, miFila.puntos.filter((p) => !p.cod).length), 1)}</b><small>en las pruebas terminadas</small></div>
    </section>
  {:else}
    <p class="tenue">Tu barco ({barco}) no aparece en las llegadas de este campeonato: elige otro en la página del campeonato.</p>
  {/if}

  <nav class="indice" aria-label="Secciones del resumen">
    {#each secciones as [id, t]}<button onclick={() => document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })}>{t}</button>{/each}
  </nav>
  {#if !solo}
  <div id="r-general" class="ancla"></div>
  <Tabla titulo="General calculada" {ref} colores={colores} filas={filasGeneral} ordenInicial="puesto" columnas={columnasGeneral}
    nota={`Puntuación baja sin penalizaciones ni decisiones del jurado (DSQ, redress…): puede diferir de la oficial. OCS (solo con la lista del comité fiable) y sin llegada (DNF) = ${res.inscritos + 1} puntos. Entre paréntesis, los descartes. «rec.»: llegadas reconstruidas desde la telemetría. Empates: RRS A8.`} />
  <button class="boton claro mas" onclick={() => (verFlota = !verFlota)}>{verFlota ? 'Ver solo el top 10 y los comparados' : `Ver toda la flota (${general.length})`}</button>

  <div id="r-puestos" class="ancla"></div>
  <section class="tarjeta bloque">
    <h3>Puesto por prueba</h3>
    <div class="leyenda">{#each comparados as v}<span><i style:background={colores[v]}></i>{vc(v)}</span>{/each}</div>
    <GraficoPruebas {pruebas} series={seriePuesto} invertido titulo="Puesto por prueba" />
    <p class="nota">Arriba, mejores puestos. Huecos: OCS o sin llegada.</p>
  </section>
  {/if}

  <div id="r-metrica" class="ancla"></div>
  <section class="tarjeta bloque">
    <div class="cabm">
      <h3>{m[1]} por prueba <span class="tenue">({m[2]})</span>{#if m[4]}<span class="est"> estimado</span>{/if}</h3>
      <label class="sel">Métrica <select bind:value={metrica}>{#each METRICAS as x}<option value={x[0]}>{x[1]}</option>{/each}</select></label>
    </div>
    <div class="leyenda">{#each comparados as v}<span><i style:background={colores[v]}></i>{vc(v)}</span>{/each}<span class="tenue"><i class="gris"></i>mediana de la flota</span></div>
    <GraficoPruebas {pruebas} series={serieMetrica} flota={flotaMetrica} unidad={m[2]} decimales={m[3]} titulo={m[1]} />
    <p class="nota">
      {#if topRef}{vc(ref)}: entre los 15 {metrica.startsWith('perdida') ? 'que menos pierden' : 'mejores'} de la flota en {topRef.top} de {topRef.de} pruebas. {/if}
      Medias de cada prueba del análisis por tramos. {analizadas} de {res.pruebas.length} pruebas con métricas{#if dudosas.length}; sin métricas la {dudosas.map((n) => 'P' + n).join(', ')} (recorrido reconstruido dudoso){/if}.
    </p>
  </section>

  <div id="r-medias" class="ancla"></div>
  <Tabla titulo="Medias del campeonato" {ref} {colores} filas={filasRend} ordenInicial="pos"
    nota="Medias de las pruebas con métricas, ponderadas por la cobertura de datos de cada barco en cada prueba. * estimado con el viento reconstruido."
    columnas={[
      { k: 'vela', titulo: 'Barco', fmt: vc }, { k: 'pos', titulo: 'Pos.', num: true }, { k: 'analizadas', titulo: 'Pruebas', num: true },
      { k: 'vmg_ceñida', titulo: 'VMG ↑', num: true, est: true, fmt: fKn }, { k: 'vmg_popa', titulo: 'VMG ↓', num: true, est: true, fmt: fKn },
      { k: 'sog_ceñida', titulo: 'SOG ↑', num: true, fmt: fKn }, { k: 'sog_popa', titulo: 'SOG ↓', num: true, fmt: fKn },
      { k: 'twa_ceñida', titulo: 'TWA ↑', num: true, est: true, fmt: fG(1) }, { k: 'twa_popa', titulo: 'TWA ↓', num: true, est: true, fmt: fG(1) },
      { k: 'escora_ceñida', titulo: 'Escora ↑', num: true, fmt: fG(0) }, { k: 'escora_popa', titulo: 'Escora ↓', num: true, fmt: fG(0) },
      { k: 'cabeceo_ceñida', titulo: 'Cabeceo ↑', num: true, fmt: fG(0) }, { k: 'cabeceo_popa', titulo: 'Cabeceo ↓', num: true, fmt: fG(0) },
    ]} />

  <div id="r-escora" class="ancla"></div>
  {#if res.escora}
    {@const e = res.escora}
    {@const mio = e.barcos[ref]}
    <div class="bloque-ia">
      <EscoraOptima titulo="Escora óptima en ceñida · todo el campeonato" {ref} nombreRef={vc(ref)}
        top5={general.filter((f) => f.vela !== ref).slice(0, 5).map((f) => f.vela)}
        tramo={{ escora_optima: e.todas, barcos: Object.fromEntries(Object.entries(e.barcos).map(([v, x]) => [v, { escora: x.escora_mediana }])) }}
        enRangoTexto={mio ? `${mio.en_rango} de ${mio.ceñidas} ceñidas con la escora mediana en el rango` : null}
        nota={`Todas las ceñidas juntas (${e.todas.ceñidas} ceñidas, ${e.todas.segmentos} tramos de 30 s): vale si las pruebas fueron con un viento parecido. Si no, añade el viento de referencia de cada prueba y se separa por intensidad.${e.por_viento.length ? ' Por intensidad: ' + e.por_viento.map((x) => `${x.tramo}: ${x.rango[0]}–${x.rango[1]}° (${x.ceñidas} ceñidas)`).join(' · ') + '.' : ''} Top 5 = los 5 primeros de la general.`} />
    </div>
  {/if}

  <div id="r-salidas" class="ancla"></div>
  <div class="dos">
    <Tabla titulo="Salidas acumuladas" {ref} {colores} filas={filasSalida} ordenInicial="top10_60"
      nota="Solo las salidas con datos del barco en el disparo. Margen negativo = por detrás de la línea. +60 s: puesto avanzando hacia la baliza 1. * estimado."
      columnas={[
        { k: 'vela', titulo: 'Barco', fmt: vc }, { k: 'pruebas', titulo: 'Con datos', num: true },
        { k: 'margen_m', titulo: 'Margen medio', num: true, fmt: fM },
        { k: 'posicion_linea_pct', titulo: 'Línea C→P', num: true, fmt: (v) => (v == null ? '—' : num(v, 0) + ' %') },
        { k: 'top10_60', titulo: 'Top 10 a +60 s', num: true, est: true, fmt: (v, f) => (f.con_60 ? `${v} de ${f.con_60}` : '—') },
        { k: 'ocs', titulo: 'OCS', num: true }, { k: 'sobre_linea_gps', titulo: 'Sobre la línea (GPS)', num: true },
      ]} />
    <Tabla titulo="Maniobras, laylines y puertas" {ref} {colores} filas={filasManiobras} ordenInicial="virada"
      nota="Pérdida media por maniobra con datos suficientes. Layline OK: tramos que llegan a la baliza sin sobrepasar la layline. Puerta favorecida: solo puertas con ventaja ≥ 5 m. * estimado."
      columnas={[
        { k: 'vela', titulo: 'Barco', fmt: vc },
        { k: 'virada', titulo: 'Virada', num: true, est: true, fmt: fM }, { k: 'trasluchada', titulo: 'Trasluchada', num: true, est: true, fmt: fM },
        { k: 'lay_ok', titulo: 'Layline OK', num: true, est: true, fmt: (v, f) => (v == null ? '—' : `${num(v, 0)} % de ${f.lay_n}`) },
        { k: 'lay_m', titulo: 'Sobrepasada', num: true, est: true, fmt: (v) => (v == null ? '—' : '+' + num(v, 0) + ' m') },
        { k: 'lay_traf', titulo: 'Por tráfico', num: true, est: true, ayuda: 'Sobrepasadas en las que había tráfico (no podía virar o la layline estaba ocupada)', fmt: (v, f) => (f.lay_sob ? `${v} de ${f.lay_sob}` : '—') },
        { k: 'puertas', titulo: 'Puerta favorecida', num: true, est: true, fmt: (v, f) => (v == null ? '—' : `${v} de ${f.puertas_n}`) },
      ]} />
  </div>

  <div id="r-viento" class="ancla"></div>
  <section class="tarjeta bloque">
    <h3>Según la intensidad del viento <span class="est">estimado</span></h3>
    {#if !conViento}
      <p class="tenue">Necesita el viento de referencia de cada prueba: añádelo en la lista de pruebas del campeonato (columna «Viento ref.»).</p>
    {:else}
      <div class="rodillo"><table class="mini">
        <thead><tr><th>Barco</th>{#each res.barcos[comparados[0]].totales.viento as t}<th class="n" colspan="3">{t.tramo}</th>{/each}</tr>
          <tr><th></th>{#each res.barcos[comparados[0]].totales.viento as _}<th class="n">Pruebas</th><th class="n">Puesto medio</th><th class="n">VMG ↑ / ↓</th>{/each}</tr></thead>
        <tbody>{#each comparados as v}<tr class:yo={v === ref}><td><span class="punto" style:background={colores[v]}></span>{vc(v)}</td>
          {#each T(v).viento as t}<td class="n num">{t.pruebas}</td><td class="n num">{t.puesto_medio == null ? '—' : num(t.puesto_medio, 1)}</td><td class="n num">{t.vmg_ceñida == null ? '—' : num(t.vmg_ceñida, 2) + ' / ' + num(t.vmg_popa, 2)}</td>{/each}</tr>{/each}</tbody>
      </table></div>
      <Nota>Con el viento de referencia que has introducido ({conViento} de {res.pruebas.length} pruebas). El puesto medio usa los puntos de cada prueba (incluidos OCS y sin llegada).</Nota>
    {/if}
  </section>

  <div id="r-debrief" class="ancla"></div>
  {#if miFila}
    <section class="tarjeta bloque selector-ia">
      <h3>Debrief · IA</h3>
      <div class="modos" role="group" aria-label="Qué debrief">
        <button class:activo={ambitoIA === 'campeonato'} aria-pressed={ambitoIA === 'campeonato'} onclick={() => (ambitoIA = 'campeonato')}>Campeonato (hasta ahora)</button>
        {#each res.dias as d}
          <button class="dia" class:activo={ambitoIA === 'dia:' + d} aria-pressed={ambitoIA === 'dia:' + d} onclick={() => (ambitoIA = 'dia:' + d)}>{nombreDia(d)}</button>
        {/each}

      </div>
      {#if ambitoIA === 'campeonato' && (res.pendientes.length || progreso)}
        <p class="nota">Aún se están analizando {res.pendientes.length} prueba(s): el debrief usará las ya analizadas. Cuando terminen, te avisará para regenerarlo.</p>
      {:else if ambitoIA === 'campeonato'}
        <p class="nota">Con las {res.pruebas.length} pruebas disputadas hasta ahora; si hay pruebas nuevas, avisa para regenerarlo.</p>

      {:else}
        <p class="nota">Lo que más costó ese día, lo que funcionó y qué trabajar (con el rol responsable), a partir del detalle de cada tramo. Solo las pruebas de ese día ({res.pruebas.filter((p) => 'dia:' + p.dia === ambitoIA).map((p) => 'P' + p.numero).join(', ')}), comparadas con el top 5 del día, y cómo quedas en la general al terminarlo.</p>
      {/if}
    </section>
    {#key ambitoIA}
      <div class="bloque-ia"><Debrief {campId} ambito={ambitoIA} barco={ref}
        titulo={ambitoIA === 'campeonato' ? `Debrief del campeonato · ${vc(ref)} · IA` : `Debrief del ${nombreDia(ambitoIA.slice(4))} · ${vc(ref)} · IA`} /></div>
    {/key}
  {/if}
{/if}

<style>
  .rueda { display: inline-block; width: 12px; height: 12px; margin-right: 8px; border: 2px solid var(--linea); border-top-color: var(--yo); border-radius: 50%; animation: gira 1s linear infinite; vertical-align: -1px; }
  @keyframes gira { to { transform: rotate(360deg); } }
  .cab { display: flex; justify-content: space-between; align-items: end; gap: 12px 20px; flex-wrap: wrap; margin-bottom: 10px; }
  .volver { font: 600 14px var(--display); color: var(--tinta-2); text-decoration: none; }
  h1 { font-size: clamp(24px, 4vw, 32px); margin-top: 2px; }
  .meta { margin: 4px 0 0; font-size: 14px; display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
  select { font: 500 14px var(--texto); padding: 3px 6px; border: 1px solid var(--linea); border-radius: 4px; background: var(--panel); color: var(--tinta); }
  .seleccion { display: grid; gap: 4px; }
  .modos { display: flex; gap: 4px; flex-wrap: wrap; }
  .modos button { font: 600 13px var(--display); padding: 5px 9px; border-radius: 4px; border: 1px solid var(--linea); background: var(--panel); }
  .modos button.activo { background: var(--tinta); color: var(--panel); border-color: var(--tinta); }
  .progreso { font-size: 14px; color: var(--tinta-2); }
  .tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; margin-bottom: 10px; }
  .tile { padding: 10px 12px; display: grid; gap: 2px; }
  .tile i { font: 600 11px var(--display); letter-spacing: .06em; text-transform: uppercase; color: var(--tinta-2); font-style: normal; }
  .tile b { font-size: 28px; font-weight: 600; color: var(--tinta); }
  .tile small { font-size: 12px; color: var(--tinta-3); }
  :global(main) > .tarjeta, .bloque { margin-top: 10px; }
  .mas { margin: 6px 0 0; font-size: 14px; padding: 6px 12px; }
  .bloque { padding: 10px 12px; min-width: 0; }
  .bloque h3 { font-size: 15px; letter-spacing: .06em; text-transform: uppercase; color: var(--tinta-2); margin-bottom: 6px; }
  .cabm { display: flex; justify-content: space-between; align-items: center; gap: 8px; flex-wrap: wrap; }
  .sel { font: 600 12px var(--display); color: var(--tinta-2); display: flex; gap: 6px; align-items: center; }
  .leyenda { display: flex; flex-wrap: wrap; gap: 4px 12px; font: 600 13px var(--display); margin: 4px 0 6px; }
  .leyenda i { display: inline-block; width: 12px; height: 3px; border-radius: 2px; margin-right: 5px; vertical-align: middle; }
  .leyenda i.gris { background: #8a969c; }
  .est { color: var(--estimado); font-size: 11px; font-weight: 600; }
  .nota { font-size: 12px; color: var(--tinta-3); margin: 6px 0 0; }
  .dos { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 460px), 1fr)); gap: 10px; margin-top: 10px; }
  .dos > :global(*) { min-width: 0; }
  .rodillo { overflow-x: auto; }
  table.mini { border-collapse: collapse; width: 100%; font-size: 13px; }
  .mini th { font: 600 11px var(--display); letter-spacing: .05em; text-transform: uppercase; color: var(--tinta-2); text-align: left; padding: 4px 6px; border-bottom: 1px solid var(--linea); white-space: nowrap; }
  .mini td { padding: 4px 6px; border-bottom: 1px solid var(--rejilla); white-space: nowrap; }
  .mini .n { text-align: right; }
  tr.yo td { background: color-mix(in srgb, var(--yo) 14%, transparent); font-weight: 600; }
  .punto { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; }
  .bloque-ia { margin-top: 10px; }
  .selector-ia { margin-top: 10px; display: grid; gap: 6px; }
  .selector-ia .modos { overflow-x: auto; flex-wrap: nowrap; scrollbar-width: none; }
  .selector-ia .modos button { flex: none; }
  .selector-ia .modos button.dia::first-letter { text-transform: uppercase; }
  .indice { position: sticky; top: var(--alto-barra, 45px); z-index: 20; display: flex; gap: 4px; overflow-x: auto; scrollbar-width: none;
    background: var(--fondo); padding: 6px 0; margin: 4px 0 2px; border-bottom: 1px solid var(--linea); }
  .indice::-webkit-scrollbar { display: none; }
  .indice button { flex: none; font: 600 13px var(--display); padding: 4px 10px; border-radius: 14px; border: 1px solid var(--linea); background: var(--panel); color: var(--tinta-2); }
  .indice button:hover { color: var(--tinta); border-color: var(--tinta-3); }
  .ancla { scroll-margin-top: calc(var(--alto-barra, 45px) + 48px); }
</style>
