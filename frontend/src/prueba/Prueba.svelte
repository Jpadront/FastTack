<script>
  import { onMount, untrack } from 'svelte';
  import { api, horaLocal, clave as claveVela } from '../api.js';
  import { decodificarPistas, pestanas, ventana as ventanaDe, colorBarco, fmtT, fmtDur, num, velaCorta, tramoEn, twdEn, faseEn, corrienteEn } from './datos.js';
  import Mapa from './Mapa.svelte';
  import Reproductor from './Reproductor.svelte';
  import Panel from './Panel.svelte';
  import Tabla from './Tabla.svelte';
  import GraficoViento from './GraficoViento.svelte';
  import GraficoRendimiento from './GraficoRendimiento.svelte';
  import Debrief from '../Debrief.svelte';
  import EscoraOptima from './EscoraOptima.svelte';

  let { campId, clave, barco } = $props();

  let camp = $state(null), an = $state(null), pistas = $state(null);
  let error = $state(''), cargando = $state('Cargando el análisis…');
  let pestana = $state('salida');
  let T = $state(-60);
  let modo = $state('top5');
  let manual = $state(new Set());
  let verSelector = $state(false);
  let capa = $state(null);

  const clavePref = `fasttack.sel.${campId}`;
  onMount(async () => {
    try { const g = JSON.parse(localStorage.getItem(clavePref) || 'null'); if (g) { modo = g.modo; manual = new Set(g.manual || []); } } catch {}
    try {
      camp = await api.campeonato(campId);
      cargando = 'Calculando el análisis (la primera vez tarda unos segundos)…';
      an = await api.analisis(campId, clave);
      cargando = 'Descargando las trazas…';
      pistas = decodificarPistas(await api.pistas(campId, clave));
      cargando = '';
      T = -60;
    } catch (e) {
      error = e.message; cargando = '';
    }
  });

  const ref = $derived(claveVela(barco));
  const nombres = $derived(Object.fromEntries((camp?.barcos || []).map((b) => [b.clave, b])));
  const clasif = $derived(an ? an.clasificacion.map((c) => c.vela) : []);
  const sel = $derived.by(() => {
    if (!an || !pistas) return new Set();
    let s;
    if (modo === 'foco') s = new Set([ref]);
    else if (modo === 'flota') s = new Set(Object.keys(pistas.barcos));
    else if (modo === 'manual') s = new Set([...manual, ref]);
    else s = new Set([...clasif.slice(0, Number(modo.slice(3))), ref]);
    return new Set([...s].filter((v) => pistas.barcos[v]));
  });
  $effect(() => { try { localStorage.setItem(clavePref, JSON.stringify({ modo, manual: [...manual] })); } catch {} });

  const tabs = $derived(an ? pestanas(an) : []);
  const tab = $derived(tabs.find((t) => t.id === pestana) || tabs[0]);
  const vent = $derived(tab && an ? ventanaDe(tab, an, sel) : [0, 1]);
  // Al cambiar de pestaña, el reproductor va al inicio de su ventana (no al cambiar la selección)
  $effect(() => { pestana; untrack(() => { if (tab) T = tab.tipo === 'salida' ? -60 : vent[0]; }); });
  const colores = $derived(Object.fromEntries([...sel].map((v) => [v, colorBarco(v, ref)])));
  const posFinal = $derived(Object.fromEntries(clasif.map((v, k) => [v, k + 1])));
  const vc = (v) => velaCorta(v, nombres);
  // Tramo en curso para las capas del mapa: el de la pestaña o el del reproductor
  const trMapa = $derived(an ? (tab?.tipo === 'tramo' ? tab.tramo : tramoEn(an, T)) : null);
  const twdAhora = $derived(trMapa ? twdEn(trMapa, T, an.senal) : null);
  const faseAhora = $derived(trMapa ? faseEn(trMapa, T, an.senal) : null);
  const corrAhora = $derived(an ? corrienteEn(an, T) : null);
  const CAPAS = [['presion', 'Presión'], ['twd', 'TWD'], ['rol', 'Rol'], ['sog', 'SOG']];
  const lado = (v) => ({ IZQUIERDA: 'izquierda', DERECHA: 'derecha', flota: 'toda la flota' })[v] || '—';
  const desfase = $derived(camp?.tz_offset_ms || 0);
  const controlesTab = $derived.by(() => {
    if (!tab || !an) return null;
    if (tab.tipo === 'salida') return new Set(['salida', 'b1']);
    if (tab.tipo === 'tramo') return new Set([tab.tramo.desde, tab.tramo.hasta, 'o' + tab.tramo.desde.slice(1)]);
    if (tab.tipo === 'baliza') return new Set(tab.controles.map((c) => c.id));
    if (tab.tipo === 'llegada') return new Set(['llegada']);
    return null;
  });

  function alternarManual(v) {
    const m = new Set(modo === 'manual' ? manual : sel);
    m.has(v) ? m.delete(v) : m.add(v);
    manual = m; modo = 'manual';
  }

  // ---------- filas de las tablas
  const seg = (ms) => (ms - an.senal) / 1000;
  const filasSalida = $derived(an?.salida ? Object.entries(an.salida.barcos).filter(([v]) => sel.has(v))
    .map(([v, f]) => ({ vela: v, ...f, pos_final: posFinal[v] })) : []);
  const filasTramo = $derived(tab?.tipo === 'tramo' ? Object.entries(tab.tramo.barcos).filter(([v]) => sel.has(v))
    .map(([v, f]) => ({ vela: v, ...f, baja: f.calidad === 'baja' || f.calidad === 'insuficiente',
      layline_txt: f.layline?.estado === 'SOBREPASADA' ? `${f.layline.lado === 'DERECHA' ? 'Dcha' : 'Izda'} +${num(f.layline.metros, 0)} m` : f.layline?.estado === 'OK' ? 'OK' : '—' })) : []);
  function filasPaso(cid) {
    const pasos = Object.entries(an.pasos).filter(([, p]) => p[cid]).map(([v, p]) => ({ vela: v, ...p[cid] }));
    pasos.sort((a, b) => a.t - b.t);
    const t0 = pasos[0]?.t;
    return pasos.map((p, k) => ({ ...p, pos: k + 1, tiempo: seg(p.t), gap: (p.t - t0) / 1000,
      zona: p.entrada != null && p.salida != null ? (p.salida - p.entrada) / 1000 : null })).filter((p) => sel.has(p.vela));
  }
  const filasLlegada = $derived(an ? an.clasificacion.filter((c) => sel.has(c.vela))
    .map((c) => ({ ...c, gap: c.tiempo_s - an.clasificacion[0].tiempo_s })) : []);
  const filasRend = $derived(an ? Object.entries(an.rendimiento).filter(([v]) => sel.has(v))
    .map(([v, r]) => ({ vela: v, pos: posFinal[v] ?? null, ...r })) : []);

  const fBarco = (v) => vc(v);
  const fGrados = (d = 0) => (v) => (v == null ? '—' : num(v, d) + '°');
  const fM = (v) => (v == null ? '—' : num(v, 0) + ' m');
  const fKn = (v) => num(v, 2);
  const fS = (v) => (v == null ? '—' : `${num(v, 0)} s`);
</script>

{#if error}
  <p class="error" role="alert">{error}</p>
  <a class="boton claro" href={`#/c/${encodeURIComponent(campId)}`}>Volver al campeonato</a>
{:else if cargando}
  <p class="tenue"><span class="rueda" aria-hidden="true"></span>{cargando}</p>
{:else}
  {@const p = an.prueba}
  <header class="cab">
    <div>
      <a class="volver" href={`#/c/${encodeURIComponent(campId)}`}>← {camp.nombre}</a>
      <h1>Prueba {p.numero ?? '—'} <span class="tenue sub">· {horaLocal(an.senal, desfase)}</span></h1>
      <p class="meta">
        {camp.clase} · {an.clasificacion.length} llegadas · {an.vueltas} vueltas
        {#if p.estado === 'reconstruida'}<span class="chip reconstruida">reconstruida</span>{/if}
        {#if !p.viento_kn}<span class="chip">viento sin calibrar</span>{:else}<span class="chip">viento ref. {num(p.viento_kn, 1)} kn</span>{/if}
        <span class="tenue">· motor {an.version}</span>
      </p>
    </div>
    <div class="seleccion">
      <span class="etiqueta">Barcos en mapa y tabla</span>
      <div class="modos" role="group" aria-label="Barcos en mapa y tabla">
        {#each [['foco', 'Solo foco'], ['top5', 'Top 5'], ['top10', 'Top 10'], ['top15', 'Top 15'], ['flota', 'Toda la flota']] as [m, t]}
          <button class:activo={modo === m} aria-pressed={modo === m} onclick={() => (modo = m)}>{t}</button>
        {/each}
        <button class:activo={verSelector} onclick={() => (verSelector = !verSelector)}>Elegir… ({sel.size})</button>
      </div>
    </div>
  </header>
  {#if verSelector}
    <section class="tarjeta elegir">
      {#each clasif as v}
        <label><input type="checkbox" checked={sel.has(v)} disabled={v === ref} onchange={() => alternarManual(v)}>
          <span class="punto" style:background={colorBarco(v, ref)}></span>{posFinal[v]}. {vc(v)}</label>
      {/each}
    </section>
  {/if}

  <nav class="pestanas" aria-label="Fases de la prueba">
    {#each tabs as t}
      <button class:activa={pestana === t.id} aria-current={pestana === t.id} onclick={() => (pestana = t.id)}>{t.nombre}</button>
    {/each}
  </nav>

  <div class="rejilla">
    <div class="izq">
      <div class="capas">
        <div class="modos" role="group" aria-label="Capa del mapa">
          <button class:activo={capa === null} aria-pressed={capa === null} onclick={() => (capa = null)}>Colores de barco</button>
          {#each CAPAS as [k, t]}<button class:activo={capa === k} aria-pressed={capa === k} onclick={() => (capa = capa === k ? null : k)}>{t}</button>{/each}
        </div>
        <div class="indic num">
          <span>TWD <b>{num(twdAhora, 0)}°</b> <span class="est">est.</span></span>
          {#if faseAhora}<span>· {faseAhora.tipo.toLowerCase()}{faseAhora.primero && faseAhora.primero !== 'flota' ? ' (primero ' + lado(faseAhora.primero) + ')' : ''}</span>{/if}
          {#if corrAhora}<span>· corriente {num(corrAhora.velocidad_kn, 1)} kn hacia {num(corrAhora.hacia_grados, 0)}° <span class="est">est.</span></span>{:else}<span class="tenue">· corriente sin estimar</span>{/if}
        </div>
      </div>
      <div class="mapabox"><Mapa {pistas} {an} {sel} {ref} {T} ventana={vent} controlesVisibles={controlesTab} {nombres} {capa} tramo={trMapa} /></div>
      <Reproductor bind:T ventana={vent} senalMs={an.senal} desfaseMs={desfase} />
    </div>
    <div class="der">
      <Panel {an} {pistas} {T} {sel} {ref} tramo={tab.tipo === 'tramo' ? tab.tramo : null} desfaseMs={desfase} {nombres} />
    </div>
  </div>

  <div class="contenido">
    {#if tab.tipo === 'salida' && an.salida}
      {@const s = an.salida}
      <section class="tarjeta resumen">
        <div><i>Comité · pin</i><b class="num">{an.controles[0].sn.slice().reverse().map((x) => x ?? '—').join(' · ')}</b></div>
        <div><i>Sesgo de la línea <span class="est">est.</span></i><b>{num(s.sesgo.grados, 1)}° {s.sesgo.extremo === 'PIN' ? 'pin' : 'comité'} · {num(s.sesgo.metros, 0)} m</b></div>
        <div><i>Viento en el disparo <span class="est">est.</span></i><b>{num(s.twd_disparo, 0)}° · {s.tws_disparo ? num(s.tws_disparo, 1) + ' kn' : 'sin calibrar'}</b></div>
        <div><i>Línea</i><b>{num(s.sesgo.largo_linea_m, 0)} m</b></div>
        <div><i>Corriente <span class="est">est.</span></i>{#if an.corriente}<b>{num(an.corriente.velocidad_kn, 2)} kn hacia {num(an.corriente.hacia_grados, 0)}°</b><small class="tenue">confianza {an.corriente.confianza}</small>{:else}<b class="tenue">sin estimar</b>{/if}</div>
      </section>
      <Tabla titulo="Comparativa de apertura" {ref} {colores} filas={filasSalida} ordenInicial="pos_60"
        nota="Margen negativo = por detrás de la línea en el disparo. +60/+180: puesto y distancia al primero avanzando hacia la baliza 1. * estimado con el viento reconstruido."
        columnas={[
          { k: 'vela', titulo: 'Barco', fmt: fBarco },
          { k: 'posicion_linea_pct', titulo: 'Línea C→P', num: true, fmt: (v) => (v == null ? '—' : num(v, 0) + ' %') },
          { k: 'margen_m', titulo: 'Margen', num: true, fmt: (v) => (v == null ? '—' : num(v, 1) + ' m') },
          { k: 'sog_disparo', titulo: 'SOG disparo', num: true, fmt: fKn },
          { k: 'cruce_s', titulo: 'Cruce GPS', num: true, fmt: (v) => (v == null ? '—' : '+' + num(v, 0) + ' s') },
          { k: 'vmg_0_90', titulo: 'VMG 0–90 s', num: true, est: true, fmt: fKn },
          { k: 'pos_60', titulo: '+60', num: true, est: true },
          { k: 'dist_60', titulo: 'Δ60', num: true, est: true, fmt: fM },
          { k: 'pos_180', titulo: '+180', num: true, est: true },
          { k: 'dist_180', titulo: 'Δ180', num: true, est: true, fmt: fM },
          { k: 'primera_virada_s', titulo: '1.ª virada', num: true, est: true, fmt: fS },
          { k: 'pos_b1', titulo: 'Baliza 1', num: true, fmt: (v, f) => (v == null ? '—' : `${v}.º${f.gap_b1_s ? ' +' + f.gap_b1_s + ' s' : ''}`) },
          { k: 'ocs', titulo: 'OCS', fmt: (v, f) => (v !== 'NO' ? 'sí' : f.sobre_linea_gps ? 'sobre la línea (GPS)' : 'no') },
        ]} />
    {:else if tab.tipo === 'tramo'}
      {@const tr = tab.tramo}
      <section class="tarjeta resumen">
        <div><i>TWD media <span class="est">est.</span></i><b>{num(tr.viento.twd_media, 0)}°</b></div>
        <div><i>TWA de la flota <span class="est">est.</span></i><b>{tr.viento.twa_flota == null ? '—' : num(tr.viento.twa_flota, 0) + '°'}</b></div>
        <div><i>Largo</i><b>{fM(tr.largo_m)}</b></div>
        <div><i>Barco fantasma <span class="est">est.</span></i><b>{fM(tr.fantasma_m)}</b></div>
        <div><i>Líder</i><b>{vc(Object.entries(tr.barcos).find(([, f]) => f.posicion === 1)?.[0] || '')}</b></div>
      </section>
      <Tabla titulo={`Rendimiento en ${tr.nombre}`} {ref} {colores} filas={filasTramo} ordenInicial="posicion"
        nota={`En gris, barcos con pocos datos en el tramo (calidad baja). * estimado con el viento reconstruido. Pérdida: suma de las maniobras con datos suficientes. Layline: lado del campo ${tr.tipo === 'popa' ? 'mirando a sotavento' : 'mirando a barlovento'}.`}
        columnas={[
          { k: 'vela', titulo: 'Barco', fmt: fBarco },
          { k: 'posicion', titulo: 'Pos.', num: true },
          { k: 'parcial_s', titulo: 'Parcial', num: true, fmt: fmtDur },
          { k: 'gap_s', titulo: 'Gap', num: true, fmt: (v) => (v ? '+' + fmtDur(v) : '—') },
          { k: 'vmg', titulo: 'VMG', num: true, est: true, fmt: fKn },
          { k: 'sog', titulo: 'SOG', num: true, fmt: fKn },
          { k: 'twa', titulo: 'TWA', num: true, est: true, fmt: fGrados(1) },
          { k: 'distancia_m', titulo: 'Distancia', num: true, fmt: fM },
          { k: 'maniobras', titulo: 'Man.', num: true, est: true },
          { k: 'perdida_m', titulo: 'Pérdida', num: true, est: true, fmt: fM },
          { k: 'layline_txt', titulo: 'Layline', est: true },
          { k: 'escora', titulo: 'Escora', num: true, fmt: fGrados(0) },
          ...(tr.tipo === 'ceñida' && tr.escora_optima ? [{ k: 'escora_en_rango_pct', titulo: 'En rango', num: true, est: true, ayuda: 'Tiempo con la escora en el rango óptimo del tramo', fmt: (v) => (v == null ? '—' : num(v, 0) + ' %') }] : []),
          { k: 'cabeceo', titulo: 'Cabeceo', num: true, fmt: fGrados(0) },
          { k: 'modo', titulo: 'Modo', est: true, fmt: (v) => ({ VMG: 'VMG', ALTURA: 'altura', VELOCIDAD: 'velocidad', PROFUNDO: 'profundo' })[v] || '—' },
          { k: 'eficiencia_pct', titulo: 'vs fantasma', num: true, est: true, fmt: (v, f) => (v == null ? '—' : `${f.vs_fantasma_m > 0 ? '+' : ''}${num(f.vs_fantasma_m, 0)} m · ${num(v, 1)} %`) },
          { k: 'calidad', titulo: 'Datos', fmt: (v, f) => `${v} (${num(f.cobertura * 100, 0)} %)` },
        ]} />
      {#if tr.tipo === 'ceñida' && tr.escora_optima}
        <EscoraOptima tramo={tr} {ref} nombreRef={vc(ref)} top5={an.clasificacion.map((c) => c.vela).filter((v) => v !== ref).slice(0, 5)} />
      {/if}
      <GraficoViento tramo={tr} {T} senalMs={an.senal} />
      <div class="dos">
        <section class="tarjeta bloque">
          <h3>Viento en 10 cortes <span class="est">estimado</span></h3>
          <div class="rodillo"><table class="mini">
            <thead><tr><th class="n">Tramo</th><th class="n">TWD</th><th class="n">{tr.viento.tws_calibrada ? 'TWS' : 'Presión (SOG)'}</th><th class="n">TWA flota</th><th class="n">Confianza</th></tr></thead>
            <tbody>{#each tr.viento.cortes as c}<tr class:tenue={c.fuente === 'arrastre'}>
              <td class="n num">{c.pct} %</td><td class="n num">{num(c.twd, 0)}°</td>
              <td class="n num">{tr.viento.tws_calibrada ? num(c.tws, 1) + ' kn' : num(c.sog_mediana, 2) + ' kn'}</td>
              <td class="n num">{c.twa_flota == null ? '—' : num(c.twa_flota, 0) + '°'}</td>
              <td class="n num">{c.fuente === 'arrastre' ? 'sin datos' : num(c.confianza * 100, 0) + ' %'}</td></tr>{/each}</tbody>
          </table></div>
        </section>
        <section class="tarjeta bloque">
          <h3>Fases de rolada</h3>
          <table class="mini"><thead><tr><th>Tramo</th><th>Tipo</th><th class="n">Δ</th><th>Primero</th></tr></thead>
            <tbody>{#each tr.fases_rolada as f}<tr><td class="num">{f.desde_pct}–{f.hasta_pct} %</td><td>{f.tipo.toLowerCase()}</td><td class="n num">{f.delta > 0 ? '+' : ''}{num(f.delta, 1)}°</td><td>{lado(f.primero)}</td></tr>{/each}</tbody></table>
          <h3 class="h3b">Fases de presión</h3>
          <table class="mini"><thead><tr><th>Tramo</th><th>Tipo</th><th class="n">Δ</th><th>Primero</th></tr></thead>
            <tbody>{#each tr.fases_presion as f}<tr><td class="num">{f.desde_pct}–{f.hasta_pct} %</td><td>{f.tipo.toLowerCase()}</td><td class="n num">{f.delta > 0 ? '+' : ''}{num(f.delta, 2)} kn{tr.viento.tws_calibrada ? '' : ' SOG'}</td><td>{lado(f.primero)}</td></tr>{/each}</tbody></table>
          <p class="nota">Primero: el lado del campo (mirando a barlovento) que recibió antes la rolada o el cambio de presión. «Toda la flota» si llegó a la vez. Estimado.</p>
        </section>
      </div>
      {#if an.corriente}
        {@const c = an.corriente}
        {@const comp = (x, pos, neg) => `${num(Math.abs(x), 2)} kn ${x >= 0 ? pos : neg}`}
        <section class="tarjeta bloque">
          <h3>Corriente <span class="est">estimada</span></h3>
          <div class="rodillo"><table class="mini"><thead><tr><th>Periodo</th><th class="n">Corriente</th><th class="n">A lo largo del recorrido</th><th class="n">Transversal</th><th>Confianza</th></tr></thead>
            <tbody>
              <tr><td>Toda la prueba</td><td class="n num">{num(c.velocidad_kn, 2)} kn → {num(c.hacia_grados, 0)}°</td><td class="n num">{comp(c.a_favor_kn, 'hacia barlovento', 'hacia sotavento')}</td><td class="n num">{comp(c.derecha_kn, 'hacia la derecha', 'hacia la izquierda')}</td><td>{c.confianza}</td></tr>
              {#each c.por_vuelta || [] as v}{#if v.confianza}
                <tr><td>Vuelta {v.vuelta}</td><td class="n num">{num(v.velocidad_kn, 2)} kn → {num(v.hacia_grados, 0)}°</td><td class="n num">{comp(v.a_favor_kn, 'hacia barlovento', 'hacia sotavento')}</td><td class="n num">{comp(v.derecha_kn, 'hacia la derecha', 'hacia la izquierda')}</td><td>{v.confianza}</td></tr>
              {/if}{/each}
            </tbody></table></div>
          <p class="nota">Sin corredera: sale de comparar el rumbo de proa (brújula del Atlas) con el rumbo sobre el fondo de toda la flota, descontando el desvío de cada brújula y el abatimiento ({num(c.abatimiento_grados, 1)}°). Se comprueba con la diferencia de velocidad entre amuras en ceñida (transversal {c.transversal_velocidades_kn == null ? 'sin dato' : num(c.transversal_velocidades_kn, 2) + ' kn'}): confianza alta si coinciden (±0,15 kn). {c.barcos} barcos{c.brujulas_descartadas.length ? `; ${c.brujulas_descartadas.length} brújula(s) descartada(s) por desvío > 15°` : ''}. Derecha/izquierda mirando a barlovento. Las laylines sobre el fondo ya la incluyen; TWD y TWA son sobre el fondo.</p>
        </section>
      {/if}
    {:else if tab.tipo === 'baliza'}
      {#each tab.controles as c}
        {#if c.puerta}
          <section class="tarjeta resumen">
            <div><i>Puerta favorecida <span class="est">est.</span></i><b>{lado(c.puerta.favorecida)} <small class="tenue">(mirando a sotavento)</small></b></div>
            <div><i>Ventaja <span class="est">est.</span></i><b>{num(c.puerta.ventaja_m, 0)} m</b></div>
            <div><i>TWD en el paso <span class="est">est.</span></i><b>{num(c.puerta.twd, 0)}°</b></div>
            <div><i>Cómo se mide</i><b class="peq">metros a barlovento que gana la baliza favorecida con la TWD del paso</b></div>
          </section>
        {/if}
        <Tabla titulo={`Paso por ${c.nombre}${c.fuente === 'estimada' ? ' (baliza estimada)' : ''}`} {ref} {colores} filas={filasPaso(c.id)} ordenInicial="pos"
          nota={c.tipo === 'sotavento' && c.sn.length === 2 ? 'Puerta: izquierda y derecha mirando a sotavento (como la ve el barco que llega). La ventaja estimada de cada lado va arriba.' : 'Zona: tiempo dentro de 3 esloras de la baliza.'}
          columnas={[
            { k: 'vela', titulo: 'Barco', fmt: fBarco },
            { k: 'pos', titulo: 'Pos.', num: true },
            { k: 'tiempo', titulo: 'Tiempo', num: true, fmt: fmtDur },
            { k: 'gap', titulo: 'Gap', num: true, fmt: (v) => (v ? '+' + fmtDur(v) : '—') },
            { k: 'zona', titulo: 'En la zona', num: true, fmt: fS },
            ...(c.tipo === 'sotavento' && c.sn.length === 2 ? [{ k: 'puerta', titulo: 'Puerta', fmt: (v) => (v ? v.toLowerCase() : '—') }] : []),
          ]} />
      {/each}
    {:else if tab.tipo === 'llegada'}
      <Tabla titulo="Llegada" {ref} {colores} filas={filasLlegada} ordenInicial="posicion"
        nota={p.estado === 'reconstruida' ? 'Llegadas reconstruidas desde la telemetría: puesto provisional.' : 'Orden de llegada registrado por RaceSense, sin penalizaciones ni decisiones del jurado.'}
        columnas={[
          { k: 'vela', titulo: 'Barco', fmt: fBarco },
          { k: 'posicion', titulo: 'Pos.', num: true },
          { k: 'tiempo_s', titulo: 'Tiempo', num: true, fmt: fmtDur },
          { k: 'gap', titulo: 'Gap', num: true, fmt: (v) => (v ? '+' + fmtDur(v) : '—') },
        ]} />
    {:else if tab.tipo === 'rendimiento'}
      <GraficoRendimiento {an} {pistas} {sel} {ref} {T} {colores} {nombres} />
      <Tabla titulo="Medias de la prueba" {ref} {colores} filas={filasRend} ordenInicial="pos"
        nota="Pulsa una columna para ordenar. Medias ponderadas por el tiempo de cada tramo con datos. El gráfico de arriba muestra la evolución de cada métrica a lo largo de la prueba."
        columnas={[
          { k: 'vela', titulo: 'Barco', fmt: fBarco },
          { k: 'pos', titulo: 'Pos.', num: true },
          { k: 'vmg_ceñida', titulo: 'VMG ↑', num: true, est: true, fmt: fKn },
          { k: 'vmg_popa', titulo: 'VMG ↓', num: true, est: true, fmt: fKn },
          { k: 'sog_ceñida', titulo: 'SOG ↑', num: true, fmt: fKn },
          { k: 'sog_popa', titulo: 'SOG ↓', num: true, fmt: fKn },
          { k: 'twa_ceñida', titulo: 'TWA ↑', num: true, est: true, fmt: fGrados(1) },
          { k: 'twa_popa', titulo: 'TWA ↓', num: true, est: true, fmt: fGrados(1) },
          { k: 'perdida_virada_m', titulo: 'Virada', num: true, est: true, fmt: fM },
          { k: 'perdida_trasluchada_m', titulo: 'Trasluchada', num: true, est: true, fmt: fM },
          { k: 'escora_ceñida', titulo: 'Escora ↑', num: true, fmt: fGrados(0) },
          { k: 'escora_popa', titulo: 'Escora ↓', num: true, fmt: fGrados(0) },
          { k: 'cabeceo_ceñida', titulo: 'Cabeceo ↑', num: true, fmt: fGrados(0) },
          { k: 'cabeceo_popa', titulo: 'Cabeceo ↓', num: true, fmt: fGrados(0) },
          { k: 'cobertura', titulo: 'Datos', num: true, fmt: (v) => (v == null ? '—' : num(v * 100, 0) + ' %') },
        ]} />
    {:else if tab.tipo === 'debrief'}
      <Debrief {campId} ambito={clave} barco={ref} titulo={`Debrief de la prueba ${p.numero ?? ''} · ${vc(ref)} · IA`} />
    {/if}

    {#if an.avisos.length}
      <details class="tarjeta avisos"><summary>Avisos sobre los datos ({an.avisos.length})</summary><ul>{#each an.avisos as a}<li>{a}</li>{/each}</ul></details>
    {/if}
  </div>
{/if}

<style>
  .rueda { display: inline-block; width: 12px; height: 12px; margin-right: 8px; border: 2px solid var(--linea); border-top-color: var(--yo); border-radius: 50%; animation: gira 1s linear infinite; vertical-align: -1px; }
  @keyframes gira { to { transform: rotate(360deg); } }
  .cab { display: flex; justify-content: space-between; align-items: end; gap: 12px 20px; flex-wrap: wrap; margin-bottom: 10px; }
  .volver { font: 600 14px var(--display); color: var(--tinta-2); text-decoration: none; }
  h1 { font-size: clamp(24px, 4vw, 32px); margin-top: 2px; }
  .sub { font-size: .6em; font-weight: 500; }
  .meta { margin: 4px 0 0; display: flex; gap: 6px; flex-wrap: wrap; align-items: center; font-size: 14px; }
  .seleccion { display: grid; gap: 4px; }
  .modos { display: flex; gap: 4px; flex-wrap: wrap; }
  .modos button { font: 600 13px var(--display); padding: 5px 9px; border-radius: 4px; border: 1px solid var(--linea); background: var(--panel); }
  .modos button.activo { background: var(--tinta); color: var(--panel); border-color: var(--tinta); }
  .elegir { padding: 10px 12px; display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 4px 12px; max-height: 240px; overflow: auto; margin-bottom: 10px; font-size: 14px; }
  .elegir label { display: flex; gap: 6px; align-items: center; white-space: nowrap; }
  .punto { display: inline-block; width: 8px; height: 8px; border-radius: 50%; }
  .pestanas { display: flex; gap: 2px; overflow-x: auto; border-bottom: 1px solid var(--linea); margin-bottom: 10px; scrollbar-width: thin; }
  .pestanas button { font: 600 15px var(--display); padding: 8px 12px; border: 0; background: none; color: var(--tinta-2); white-space: nowrap; border-bottom: 3px solid transparent; }
  .pestanas button.activa { color: var(--tinta); border-bottom-color: var(--yo); }
  .rejilla { display: grid; grid-template-columns: minmax(0, 1fr) 380px; gap: 10px; align-items: start; }
  .izq { display: grid; gap: 8px; min-width: 0; }
  .capas { display: flex; justify-content: space-between; align-items: center; gap: 6px 12px; flex-wrap: wrap; }
  .indic { font-size: 13px; color: var(--tinta-2); display: flex; gap: 4px; flex-wrap: wrap; }
  .peq { font-size: 12px !important; font-weight: 500 !important; color: var(--tinta-3); }
  .mapabox { height: min(62vh, 560px); min-height: 300px; }
  @media (max-width: 900px) { .rejilla { grid-template-columns: minmax(0, 1fr); } .mapabox { height: 46vh; } }
  .contenido { display: grid; grid-template-columns: minmax(0, 1fr); gap: 10px; margin-top: 10px; }
  .resumen { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; padding: 10px 12px; }
  .resumen div { display: grid; gap: 2px; }
  .resumen i { font: 600 11px var(--display); letter-spacing: .06em; text-transform: uppercase; color: var(--tinta-2); font-style: normal; }
  .resumen b { font-size: 16px; font-weight: 600; }
  .resumen small { font-size: 12px; }
  .est { color: var(--estimado); font-size: 11px; font-weight: 600; }
  .dos { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 10px; }
  .bloque { padding: 10px 12px; }
  .bloque h3 { font-size: 15px; letter-spacing: .06em; text-transform: uppercase; color: var(--tinta-2); margin-bottom: 6px; }
  .h3b { margin-top: 12px; }
  .rodillo { overflow-x: auto; }
  table.mini { border-collapse: collapse; width: 100%; font-size: 13px; }
  .mini th { font: 600 11px var(--display); letter-spacing: .05em; text-transform: uppercase; color: var(--tinta-2); text-align: left; padding: 4px 6px; border-bottom: 1px solid var(--linea); }
  .mini td { padding: 4px 6px; border-bottom: 1px solid var(--rejilla); }
  .mini .n { text-align: right; }
  tr.tenue td { color: var(--tinta-3); }
  .nota { font-size: 12px; color: var(--tinta-3); margin: 6px 0 0; }
  .avisos { padding: 8px 12px; font-size: 14px; color: var(--tinta-2); }
  .avisos ul { margin: 6px 0 0; padding-left: 18px; }
</style>
