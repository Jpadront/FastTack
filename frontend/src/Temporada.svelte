<script>
  // Temporada: la evolución del barco de referencia en todos sus campeonatos y sesiones, y qué
  // reglaje fue mejor por franja de viento. Solo pruebas ya analizadas; las pendientes se analizan aquí.
  import { onMount } from 'svelte';
  import { api, velaBonita, horaLocal } from './api.js';
  import { num, COLOR_YO } from './prueba/datos.js';
  import GraficoPruebas from './resumen/GraficoPruebas.svelte';
  import Nota from './Nota.svelte';

  let { barco } = $props();
  let t = $state(null), error = $state(''), progreso = $state('');

  async function leer() {
    try { t = await api.temporada(barco); } catch (e) { error = e.message; }
  }
  async function completar() {
    const pend = [...t.pendientes];
    for (const [k, p] of pend.entries()) {
      progreso = `Analizando pruebas pendientes (${k + 1} de ${pend.length})…`;
      try { await api.analisis(p.campeonato, p.clave); } catch {}
    }
    progreso = '';
    await leer();
  }
  onMount(async () => { await leer(); if (t?.pendientes.length) completar(); });

  // eje: «P3» si todo es de un campeonato; si no, la fecha (d/m)
  const etiquetas = $derived(t ? t.filas.map((f) => (campeonatos === 1 ? `P${f.numero}` : `${+f.dia.slice(8, 10)}/${+f.dia.slice(5, 7)}`)) : []);
  const serie = (fn) => [{ v: 'yo', nombre: velaBonita(barco), color: COLOR_YO, ref: true, vals: t.filas.map(fn) }];
  const GRAFICOS = [
    ['VMG en ceñida frente al top 5', 'kn', 2, (f) => f.vmg_ceñida_frente_top5],
    ['VMG en popa frente al top 5', 'kn', 2, (f) => f.vmg_popa_frente_top5],
    ['Pérdida por virada (mediana)', 's', 1, (f) => f.perdida_virada_s],
    ['Puesto (% de la flota)', '%', 0, (f) => Math.round(f.puesto_relativo * 100)],
  ];
  // media por prueba de «dónde se perdió»
  const media = $derived.by(() => {
    if (!t) return null;
    const ds = t.filas.map((f) => f.desglose).filter(Boolean);
    if (!ds.length) return null;
    const m = (k) => { const xs = ds.map((d) => d[k]).filter((x) => x != null); return xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null; };
    return { n: ds.length, partes: [['Salida', m('salida_s')], ['Velocidad', m('velocidad_s')], ['Maniobras', m('maniobras_s')], ['Táctica y resto', m('tactica_s')]], total: m('total_s') };
  });
  const campeonatos = $derived(t ? new Set(t.filas.map((f) => f.campeonato)).size : 0);
  const txt = (s) => (s == null ? 'sin datos' : `${s > 0 ? '+' : '−'}${num(Math.abs(s), 0)} s`);
  const fmt = (v, d = 2) => (v == null ? '—' : (v > 0 ? '+' : '') + num(v, d));
</script>

<a class="volver" href="#/">← Campeonatos</a>
<h1>Temporada de {velaBonita(barco)}</h1>
{#if error}<p class="error">{error}</p>{/if}
{#if !t}
  <p class="tenue">Cargando…</p>
{:else}
  <p class="tenue">{t.filas.length} pruebas analizadas en {campeonatos} {campeonatos === 1 ? 'campeonato o sesión' : 'campeonatos y sesiones'}{#if progreso} · {progreso}{/if}</p>
  {#if !t.filas.length}
    <p>Todavía no hay pruebas analizadas de {velaBonita(barco)}.</p>
  {:else}
    {#if media}
      <section class="tarjeta bloque">
        <h3>Dónde se pierde de media <span class="est">estimado</span></h3>
        <p class="sub">Por prueba, frente al top 5 ({media.n} pruebas): <b>{txt(media.total)}</b>.</p>
        <div class="partes">
          {#each media.partes as [n, s]}<div><i>{n}</i><b class="num" class:pierde={s > 0} class:gana={s < 0}>{txt(s)}</b></div>{/each}
        </div>
      </section>
    {/if}
    <div class="graficos">
      {#each GRAFICOS as [titulo, unidad, dec, fn]}
        <section class="tarjeta bloque">
          <h3>{titulo} <span class="tenue">({unidad})</span></h3>
          <GraficoPruebas pruebas={etiquetas} series={serie(fn)} {unidad} decimales={dec} altura={170} {titulo} invertido={unidad === '%'} />
        </section>
      {/each}
    </div>
    <section class="tarjeta bloque">
      <h3>Reglaje por franja de viento <span class="est">orientativo</span></h3>
      {#if t.reglajes.length}
        <div class="rodillo"><table class="mini">
          <thead><tr><th>Ajuste</th><th>Valor</th><th>Viento</th><th class="n">Pruebas</th><th class="n">VMG ceñida vs top 5</th><th class="n">VMG popa vs top 5</th><th class="n">Puesto</th></tr></thead>
          <tbody>{#each t.reglajes as r}<tr><td>{r.ajuste}</td><td>{r.valor}</td><td>{r.franja}</td><td class="n num">{r.pruebas}</td>
            <td class="n num">{fmt(r.vmg_ceñida_frente_top5)} kn</td><td class="n num">{fmt(r.vmg_popa_frente_top5)} kn</td>
            <td class="n num">{r.puesto_relativo == null ? '—' : num(r.puesto_relativo * 100, 0) + ' %'}</td></tr>{/each}</tbody>
        </table></div>
        <Nota><p>Media de las pruebas con cada valor del ajuste, separadas por el viento de referencia de la prueba. Con pocas pruebas por casilla es orientativo: el viento, la flota y el día también cambian.</p></Nota>
      {:else}
        <p class="tenue">Apunta el reglaje de cada prueba en la página del campeonato (botón «Reglaje») y el viento de referencia: aquí verás qué valor de cada ajuste fue mejor en cada franja de viento cuando haya al menos dos valores distintos.</p>
      {/if}
    </section>
    <section class="tarjeta bloque">
      <h3>Pruebas</h3>
      <div class="rodillo"><table class="mini">
        <thead><tr><th>Día</th><th>Campeonato</th><th class="n">Prueba</th><th class="n">Puesto</th><th>Viento</th><th>Reglaje</th></tr></thead>
        <tbody>{#each [...t.filas].reverse() as f}<tr>
          <td class="num">{f.dia.split('-').reverse().join('/')}</td><td>{f.nombre}</td>
          <td class="n"><a href={`#/c/${encodeURIComponent(f.campeonato)}/p/${f.clave}`}>P{f.numero}</a></td>
          <td class="n num">{f.puesto}/{f.barcos}</td><td class="num">{f.viento_kn ? num(f.viento_kn, 0) + ' kn' : '—'}</td>
          <td class="tenue">{Object.entries(f.reglaje).map(([k, v]) => `${k}: ${v}`).join(' · ') || '—'}</td></tr>{/each}</tbody>
      </table></div>
    </section>
  {/if}
{/if}

<style>
  .volver { display: inline-block; font: 600 14px var(--display); color: var(--tinta-2); text-decoration: none; margin-bottom: 4px; }
  h1 { font-size: clamp(24px, 4vw, 34px); margin: 2px 0 4px; }
  .bloque { padding: 10px 14px; margin-top: 10px; min-width: 0; }
  h3 { font-size: 15px; letter-spacing: .06em; text-transform: uppercase; color: var(--tinta-2); margin: 0 0 6px; }
  .est { color: var(--estimado); font-size: 11px; }
  .sub { margin: 0 0 6px; }
  .partes { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }
  @media (max-width: 600px) { .partes { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
  .partes div { display: grid; gap: 2px; }
  .partes i { font-style: normal; font-size: 13px; color: var(--tinta-2); }
  .partes b { font-size: 20px; }
  .pierde { color: #c0392b; }
  .gana { color: #1c5cab; }
  .graficos { display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); gap: 0 10px; }
  @media (max-width: 500px) { .graficos { grid-template-columns: minmax(0, 1fr); } }
  .rodillo { overflow-x: auto; }
  table.mini { border-collapse: collapse; width: 100%; font-size: 14px; }
  table.mini th { text-align: left; font: 600 12px var(--display); color: var(--tinta-2); padding: 4px 6px; border-bottom: 1px solid var(--linea); white-space: nowrap; }
  table.mini td { padding: 4px 6px; border-bottom: 1px solid var(--rejilla); }
  .n { text-align: right; white-space: nowrap; }
</style>
