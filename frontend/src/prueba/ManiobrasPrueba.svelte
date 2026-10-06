<script>
  // Maniobras de toda la prueba: viradas o trasluchadas del barco de referencia frente al top 5 o a
  // un barco. Todas sincronizadas en el instante en que la proa cruza el viento (el que da el motor),
  // con el perfil de SOG, las trayectorias con el viento siempre arriba, la consistencia y la tabla.
  // Las cifras de cada maniobra son las del motor (analizar_maniobra); aquí solo se agrupan.
  import Nota from '../Nota.svelte';
  import { estado, twdEn, fmtT, num, velaCorta, mediana, COLOR_YO } from './datos.js';

  let { an, pistas, ref, nombres = {} } = $props();
  const COLOR_OTRO = '#2a78d6';
  let tipo = $state('virada');
  let rival = $state('top5');
  const top5 = $derived(an.clasificacion.map((c) => c.vela).filter((v) => v !== ref).slice(0, 5));
  const flota = $derived(an.clasificacion.map((c) => c.vela).filter((v) => v !== ref && pistas.barcos[v]));
  const vc = (v) => velaCorta(v, nombres);
  const nombreRival = $derived(rival === 'top5' ? 'top 5' : vc(rival));

  function lista(velas) {
    const out = [];
    for (const tr of an.tramos) {
      if (tr.tipo !== (tipo === 'virada' ? 'ceñida' : 'popa')) continue;
      for (const v of velas) for (const m of tr.maniobras?.[v] || []) if (m.detalle) out.push({ ...m, v, tramo: tr });
    }
    return out.sort((a, b) => a.t - b.t);
  }
  const mias = $derived(lista([ref]));
  const otras = $derived(lista(rival === 'top5' ? top5 : [rival]));

  // Perfil de SOG y trayectoria, de −5 a +15 s. del cruce del viento (cada 0,5 s.)
  const D0 = -5, D1 = 15, PASO = 0.5;
  const OFFS = Array.from({ length: (D1 - D0) / PASO + 1 }, (_, k) => D0 + k * PASO);
  function perfil(m) {
    const b = pistas.barcos[m.v];
    if (!b) return null;
    const T = (m.t - an.senal) / 1000;
    const e0 = estado(b, T);
    if (!e0 || e0.sinDatos) return null;
    const twd = (twdEn(m.tramo, T, an.senal) * Math.PI) / 180;
    return OFFS.map((d) => {
      const e = estado(b, T + d);
      if (!e || e.sinDatos) return null;
      const dx = e.x - e0.x, dy = e.y - e0.y;
      // viento arriba: «arriba» = hacia donde viene el viento, «derecha» = perpendicular
      return { sog: e.sog, x: dx * Math.cos(twd) - dy * Math.sin(twd), y: dx * Math.sin(twd) + dy * Math.cos(twd) };
    });
  }
  const pMias = $derived(mias.map(perfil).filter(Boolean));
  const pOtras = $derived(otras.map(perfil).filter(Boolean));
  const mediaSog = (ps) => OFFS.map((_, k) => { const xs = ps.map((p) => p[k]?.sog).filter((x) => x != null); return xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null; });
  const mMias = $derived(mediaSog(pMias)), mOtras = $derived(mediaSog(pOtras));

  // Métricas medias (mediana: una maniobra mala no tapa las demás)
  const med = (ms, k) => mediana(ms.map((m) => m.detalle[k]).filter((x) => x != null));
  const METRICAS = [
    ['SOG de entrada', 'sog_entrada_kn', 2, ' kn.', 1], ['SOG mínima', 'sog_minima_kn', 2, ' kn.', 1],
    ['Caída de SOG', 'caida_sog_pct', 0, ' %', -1], ['SOG estable de salida', 'sog_salida_estable_kn', 2, ' kn.', 1],
    ['Duración del giro', 'duracion_giro_s', 1, ' s.', -1], ['Tiempo en acelerar (95 %)', 'tiempo_aceleracion_s', 1, ' s.', -1],
    ['VMG antes', 'vmg_entrada_kn', 2, ' kn.', 1], ['VMG después', 'vmg_salida_estable_kn', 2, ' kn.', 1],
    ['Pérdida', 'perdida_m', 1, ' m.', -1], ['Pérdida en tiempo', 'perdida_s', 1, ' s.', -1],
  ];
  const noAcelera = (ms) => ms.filter((m) => !m.detalle.acelerado).length;

  // Forma del giro (solo con registro denso: archivos .vkx del Atlas). Tus maniobras con menos
  // pérdida frente a las de más pérdida (mitad y mitad), para ver qué forma de girar te funciona.
  const FORMA = [
    ['Velocidad de giro máxima', 'giro_max_grados_s', 0, '°/s.'],
    ['Ángulo girado en la 1.ª mitad del giro', 'giro_primera_mitad_pct', 0, ' %'],
    ['Más allá del rumbo final (8 s. tras el giro)', 'pasada_grados', 0, '°'],
    ['SOG mínima respecto al final del giro', 'sog_minima_tras_giro_s', 1, ' s.'],
    ['Duración del giro', 'duracion_giro_s', 1, ' s.'],
    ['Pérdida en tiempo', 'perdida_s', 1, ' s.'],
  ];
  const conForma = (ms) => ms.filter((m) => m.detalle.giro_max_grados_s != null && m.detalle.perdida_s != null);
  const fMias = $derived(conForma(mias));
  const fOtras = $derived(conForma(otras));
  const partir = $derived.by(() => {
    if (fMias.length < 6) return null;
    const o = [...fMias].sort((a, b) => a.detalle.perdida_s - b.detalle.perdida_s), h = Math.floor(o.length / 2);
    return { mejores: o.slice(0, h), peores: o.slice(o.length - h) };
  });
  const tipoGiro = (pct) => (pct == null ? '—' : pct < 45 ? 'lento al principio y rápido al final' : pct > 55 ? 'rápido al principio y lento al final' : 'uniforme');
  const lecturaForma = $derived.by(() => {
    if (!partir) return null;
    const out = [], m = (ms, k) => med(ms, k);
    const a = m(partir.mejores, 'giro_primera_mitad_pct'), b = m(partir.peores, 'giro_primera_mitad_pct');
    if (a != null && b != null && Math.abs(a - b) >= 10)
      out.push(`En tus ${tipo}s con menos pérdida giras el ${num(a, 0)} % del ángulo en la primera mitad (${tipoGiro(a)}); en las de más pérdida, el ${num(b, 0)} % (${tipoGiro(b)}).`);
    const da = m(partir.mejores, 'duracion_giro_s'), db = m(partir.peores, 'duracion_giro_s');
    if (da != null && db != null && Math.abs(da - db) >= 1)
      out.push(`El giro dura ${num(da, 1)} s. en las mejores y ${num(db, 1)} s. en las peores.`);
    const pa = m(partir.mejores, 'pasada_grados'), pb = m(partir.peores, 'pasada_grados');
    if (pa != null && pb != null && Math.abs(pa - pb) >= 4)
      out.push(`Tras el giro sigues ${num(pa, 0)}° más allá del rumbo final en las mejores y ${num(pb, 0)}° en las peores.`);
    const ga = m(partir.mejores, 'giro_max_grados_s'), gb = m(partir.peores, 'giro_max_grados_s');
    if (ga != null && gb != null && Math.abs(ga - gb) >= 4)
      out.push(`Velocidad de giro máxima: ${num(ga, 0)}°/s. en las mejores y ${num(gb, 0)}°/s. en las peores.`);
    return out.length ? out : [`Tus ${tipo}s con más y menos pérdida tienen una forma de giro parecida: la diferencia no está en cómo giras.`];
  });

  // Gráficos
  let W1 = $state(560), W2 = $state(360), W3 = $state(360);
  const H1 = 220, H2 = 260, H3 = 220, M = { l: 40, r: 10, t: 12, b: 26 };
  const sogs = $derived([...pMias, ...pOtras].flatMap((p) => p.map((q) => q?.sog)).filter((x) => x != null));
  const sLo = $derived(sogs.length ? Math.floor(Math.min(...sogs)) : 0), sHi = $derived(sogs.length ? Math.ceil(Math.max(...sogs)) : 1);
  const X1 = (d) => M.l + ((d - D0) / (D1 - D0)) * (W1 - M.l - M.r);
  const Y1 = (s) => H1 - M.b - ((s - sLo) / (sHi - sLo || 1)) * (H1 - M.t - M.b);
  const linea = (vals, X, Y) => { let d = '', ok = false; vals.forEach((v, k) => { if (v == null) { ok = false; return; } d += `${ok ? 'L' : 'M'}${X(OFFS[k]).toFixed(1)} ${Y(v).toFixed(1)}`; ok = true; }); return d; };
  // trayectorias: escala común en metros
  const ext = $derived(Math.max(10, ...[...pMias, ...pOtras].flatMap((p) => p.flatMap((q) => (q ? [Math.abs(q.x), Math.abs(q.y)] : [])))));
  const X2 = (x) => W2 / 2 + (x / ext) * (W2 / 2 - 12);
  const Y2 = (y) => H2 / 2 - (y / ext) * (H2 / 2 - 12);
  const tray = (p) => { let d = '', ok = false; p.forEach((q) => { if (!q) { ok = false; return; } d += `${ok ? 'L' : 'M'}${X2(q.x).toFixed(1)} ${Y2(q.y).toFixed(1)}`; ok = true; }); return d; };
  const escala = $derived([5, 10, 20, 50, 100, 200].find((m) => m >= ext / 3) ?? 200);
  // consistencia: SOG de entrada frente a pérdida
  const puntos = $derived([...mias.map((m) => [m, true]), ...otras.map((m) => [m, false])].filter(([m]) => m.detalle.sog_entrada_kn != null && m.detalle.perdida_m != null));
  const eLo = $derived(puntos.length ? Math.floor(Math.min(...puntos.map(([m]) => m.detalle.sog_entrada_kn))) : 0);
  const eHi = $derived(puntos.length ? Math.ceil(Math.max(...puntos.map(([m]) => m.detalle.sog_entrada_kn))) : 1);
  const pHi = $derived(puntos.length ? Math.ceil(Math.max(...puntos.map(([m]) => m.detalle.perdida_m)) / 5) * 5 || 5 : 5);
  const X3 = (s) => M.l + ((s - eLo) / (eHi - eLo || 1)) * (W3 - M.l - M.r);
  const Y3 = (p) => H3 - M.b - (p / pHi) * (H3 - M.t - M.b);
  const fmtD = (d) => (d === 0 ? 'cruce' : (d > 0 ? '+' : '−') + Math.abs(d) + ' s.');
  const n = (v, d, u = '') => (v == null ? '—' : num(v, d) + u);
</script>

<section class="tarjeta bloque">
  <h3>Maniobras de la prueba <span class="est">estimado</span></h3>
  <p class="sub">Todas sincronizadas en el instante en que la proa cruza el viento (0 s.). Las cifras de cada maniobra son las mismas de las pestañas de los tramos.</p>
  <div class="controles">
    <div class="modos" role="group" aria-label="Tipo de maniobra">
      <button class:activo={tipo === 'virada'} aria-pressed={tipo === 'virada'} onclick={() => (tipo = 'virada')}>Viradas</button>
      <button class:activo={tipo === 'trasluchada'} aria-pressed={tipo === 'trasluchada'} onclick={() => (tipo = 'trasluchada')}>Trasluchadas</button>
    </div>
    <label>Comparar con
      <select bind:value={rival}>
        <option value="top5">Top 5 de la prueba</option>
        {#each flota as v}<option value={v}>{vc(v)}</option>{/each}
      </select>
    </label>
  </div>
  <div class="fichas">
    <div><i>{vc(ref)}</i><b class="num">{mias.length}</b><small>{tipo}s medidas{#if mias.length} · {noAcelera(mias)} sin acelerar al 95 %{/if}</small></div>
    <div><i>{nombreRival}</i><b class="num">{otras.length}</b><small>{tipo}s medidas{#if otras.length} · {noAcelera(otras)} sin acelerar al 95 %{/if}</small></div>
  </div>
  {#if !mias.length && !otras.length}
    <p class="tenue">No hay {tipo}s con datos suficientes en esta prueba.</p>
  {:else}
  <div class="leyenda"><span><i style:background={COLOR_YO}></i>{vc(ref)}</span><span><i style:background={COLOR_OTRO}></i>{nombreRival}</span><span class="tenue">líneas finas: cada maniobra · gruesas: la media</span></div>
  <div class="rejilla">
    <div>
      <h4>SOG durante la maniobra</h4>
      <div bind:clientWidth={W1}>
        <svg viewBox={`0 0 ${W1} ${H1}`} style:height={H1 + 'px'} role="img" aria-label="SOG durante la maniobra">
          {#each Array.from({ length: sHi - sLo + 1 }, (_, k) => sLo + k) as v}<line x1={M.l} x2={W1 - M.r} y1={Y1(v)} y2={Y1(v)} class="rej" /><text x={M.l - 6} y={Y1(v) + 4} class="eje" text-anchor="end">{v}</text>{/each}
          {#each [-5, 0, 5, 10, 15] as d}<line x1={X1(d)} x2={X1(d)} y1={M.t} y2={H1 - M.b} class="rej" class:cero={d === 0} /><text x={X1(d)} y={H1 - 8} class="eje" text-anchor={d === 15 ? "end" : d === -5 ? "start" : "middle"}>{fmtD(d)}</text>{/each}
          <text x={M.l - 6} y={M.t - 2} class="eje" text-anchor="end">kn.</text>
          {#each pOtras as p}<path d={linea(p.map((q) => q?.sog), X1, Y1)} class="fina" stroke={COLOR_OTRO} />{/each}
          {#each pMias as p}<path d={linea(p.map((q) => q?.sog), X1, Y1)} class="fina" stroke={COLOR_YO} />{/each}
          <path d={linea(mOtras, X1, Y1)} class="gruesa" stroke={COLOR_OTRO} />
          <path d={linea(mMias, X1, Y1)} class="gruesa" stroke={COLOR_YO} />
        </svg>
      </div>
    </div>
    <div>
      <h4>Trayectorias, con el viento arriba (−5 a +15 s.)</h4>
      <div bind:clientWidth={W2}>
        <svg viewBox={`0 0 ${W2} ${H2}`} style:height={H2 + 'px'} role="img" aria-label="Trayectorias de las maniobras con el viento arriba">
          <line x1={W2 / 2} x2={W2 / 2} y1="6" y2={H2 - 6} class="rej cero" />
          <line x1="6" x2={W2 - 6} y1={H2 / 2} y2={H2 / 2} class="rej" />
          <text x={W2 / 2 + 4} y="16" class="eje">viento ↓</text>
          {#each pOtras as p}<path d={tray(p)} class="tray" stroke={COLOR_OTRO} />{/each}
          {#each pMias as p}<path d={tray(p)} class="tray" stroke={COLOR_YO} />{/each}
          <line x1="12" x2={12 + (escala / ext) * (W2 / 2 - 12)} y1={H2 - 12} y2={H2 - 12} class="esc" />
          <text x="12" y={H2 - 16} class="eje">{escala} m.</text>
        </svg>
      </div>
    </div>
    <div>
      <h4>Consistencia: SOG de entrada frente a pérdida</h4>
      <div bind:clientWidth={W3}>
        <svg viewBox={`0 0 ${W3} ${H3}`} style:height={H3 + 'px'} role="img" aria-label="SOG de entrada frente a metros perdidos">
          {#each [0, pHi / 2, pHi] as p}<line x1={M.l} x2={W3 - M.r} y1={Y3(p)} y2={Y3(p)} class="rej" /><text x={M.l - 6} y={Y3(p) + 4} class="eje" text-anchor="end">{num(p, 0)} m.</text>{/each}
          {#each Array.from({ length: eHi - eLo + 1 }, (_, k) => eLo + k) as s}<text x={X3(s)} y={H3 - 8} class="eje" text-anchor={s === eHi ? "end" : "middle"}>{s} kn.</text>{/each}
          {#each puntos as [m, mio]}<circle cx={X3(m.detalle.sog_entrada_kn)} cy={Y3(m.detalle.perdida_m)} r={mio ? 5 : 3.5} fill={mio ? COLOR_YO : COLOR_OTRO} fill-opacity={mio ? 1 : 0.6} stroke="var(--panel)" stroke-width="1.5"><title>{vc(m.v)} · {m.tramo.nombre} · {n(m.detalle.sog_entrada_kn, 2, ' kn.')} → {n(m.detalle.perdida_m, 1, ' m.')}</title></circle>{/each}
        </svg>
      </div>
      <p class="pie">Un grupo compacto es una ejecución repetible; compara maniobras parecidas, no la mejor aislada.</p>
    </div>
  </div>
  <h4>Medias (mediana de las maniobras)</h4>
  <div class="rodillo">
    <table class="mini">
      <thead><tr><th></th><th class="n">{vc(ref)}</th><th class="n">{nombreRival}</th><th class="n">Diferencia</th></tr></thead>
      <tbody>
        {#each METRICAS as [et, k, d, u, mejor]}
          {@const a = med(mias, k)}{@const b = med(otras, k)}{@const dif = a != null && b != null ? a - b : null}
          <tr><td>{et}</td><td class="n num">{n(a, d, u)}</td><td class="n num">{n(b, d, u)}</td>
            <td class="n num" class:bien={dif != null && dif * mejor > 0 && Math.abs(dif) >= 10 ** -d} class:mal={dif != null && dif * mejor < 0 && Math.abs(dif) >= 10 ** -d}>{dif == null ? '—' : (dif > 0 ? '+' : dif < 0 ? '−' : '') + num(Math.abs(dif), d) + u}</td></tr>
        {/each}
      </tbody>
    </table>
  </div>
  {#if fMias.length}
    <h4>Forma del giro <span class="est">estimada</span></h4>
    <p class="sub">Tu giro típico: <b>{tipoGiro(med(fMias, 'giro_primera_mitad_pct'))}</b> ({num(med(fMias, 'giro_primera_mitad_pct'), 0)} % del ángulo en la primera mitad, {fMias.length} {tipo}s con registro del Atlas).</p>
    {#if lecturaForma}<ul class="lectura">{#each lecturaForma as l}<li>{l}</li>{/each}</ul>{/if}
    <div class="rodillo">
      <table class="mini">
        <thead><tr><th></th><th class="n">{vc(ref)}</th>{#if partir}<th class="n">Con menos pérdida ({partir.mejores.length})</th><th class="n">Con más pérdida ({partir.peores.length})</th>{/if}{#if fOtras.length}<th class="n">{nombreRival}</th>{/if}</tr></thead>
        <tbody>
          {#each FORMA as [et, k, d, u]}
            <tr><td>{et}</td><td class="n num">{n(med(fMias, k), d, u)}</td>
              {#if partir}<td class="n num">{n(med(partir.mejores, k), d, u)}</td><td class="n num">{n(med(partir.peores, k), d, u)}</td>{/if}
              {#if fOtras.length}<td class="n num">{n(med(fOtras, k), d, u)}</td>{/if}</tr>
          {/each}
        </tbody>
      </table>
    </div>
    <p class="pie">Solo con el registro del Atlas (2 muestras por segundo): la telemetría de RaceSense no tiene muestras suficientes dentro de un giro de 4 a 8 s. Ángulo en la 1.ª mitad: por debajo del 45 % el giro empieza lento y acaba rápido; por encima del 55 %, al revés. «Más allá del rumbo final»: cuánto sigues girando tras el giro antes de asentarte en la nueva amura (en ceñida, arribar para acelerar o pasarte; en popa, orzar). SOG mínima: segundos tras el final del giro en que la velocidad toca fondo (negativo = durante el giro). Con menos y más pérdida: tus maniobras partidas por la mitad según la pérdida{partir ? '' : ' (hacen falta al menos 6)'}.</p>
  {/if}
  <h4>Cada maniobra</h4>
  <div class="rodillo">
    <table class="mini">
      <thead><tr><th>Barco</th><th>Tramo</th><th class="n">Desde la señal</th><th class="n">Entrada</th><th class="n">Mínima</th><th class="n">Estable</th><th class="n">Giro</th>{#if fMias.length}<th class="n">1.ª mitad</th><th class="n">Giro máx.</th>{/if}<th class="n">Acelera</th><th class="n">Pérdida</th></tr></thead>
      <tbody>
        {#each [...mias, ...(rival === 'top5' ? [] : otras)].sort((a, b) => a.t - b.t) as m}
          {@const d = m.detalle}
          <tr class:yo={m.v === ref}>
            <td><span class="punto" style:background={m.v === ref ? COLOR_YO : COLOR_OTRO}></span>{vc(m.v)}</td><td>{m.tramo.nombre}</td>
            <td class="n num">{fmtT((m.t - an.senal) / 1000)}</td>
            <td class="n num">{n(d.sog_entrada_kn, 2, ' kn.')}</td><td class="n num">{n(d.sog_minima_kn, 2, ' kn.')}</td><td class="n num">{n(d.sog_salida_estable_kn, 2, ' kn.')}</td>
            <td class="n num">{n(d.duracion_giro_s, 0, ' s.')}</td>
            {#if fMias.length}<td class="n num">{n(d.giro_primera_mitad_pct, 0, ' %')}</td><td class="n num">{n(d.giro_max_grados_s, 0, '°/s.')}</td>{/if}
            <td class="n num">{d.tiempo_aceleracion_s == null ? 'no llega' : n(d.tiempo_aceleracion_s, 0, ' s.')}</td>
            <td class="n num">{n(d.perdida_m, 1, ' m.')}{d.encadenada ? ' · encadenada' : ''}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
  {/if}
  <Nota>El instante 0 es cuando la proa cruza el viento (cambio de amura que da el motor). Entrada: SOG estable de −25 a −8 s.; mínima: la más baja de la maniobra; estable: la de la nueva amura (+25 a +45 s.); acelera: desde el final del giro hasta volver al 95 % de la estable durante 4 s. (como mucho 60 s.). Pérdida: lo que se habría avanzado hacia el viento sin maniobrar menos lo que se avanzó (las roladas se cargan a la amura, no a la maniobra). Con el top 5, sus maniobras se juntan; la tabla de abajo muestra solo las tuyas (o las del barco elegido). Las trayectorias se dibujan con el GPS y el viento estimado del tramo.</Nota>
</section>

<style>
  .bloque { padding: 10px 12px; min-width: 0; }
  h3 { font-size: 15px; letter-spacing: .06em; text-transform: uppercase; color: var(--tinta-2); margin-bottom: 2px; }
  h4 { font: 600 12px var(--display); letter-spacing: .05em; text-transform: uppercase; color: var(--tinta-2); margin: 10px 0 4px; }
  .est { color: var(--estimado); font-size: 11px; }
  .sub, .pie { margin: 0 0 6px; font-size: 13px; color: var(--tinta-2); }
  .pie { font-size: 12px; color: var(--tinta-3); }
  .controles { display: flex; flex-wrap: wrap; gap: 8px 18px; align-items: center; margin: 6px 0; font-size: 14px; }
  .controles select { margin-left: 6px; font: inherit; padding: 3px 6px; }
  .modos { display: flex; gap: 4px; }
  .modos button { font: 600 13px var(--display); padding: 4px 10px; border-radius: 14px; border: 1px solid var(--linea); background: var(--panel); color: var(--tinta-2); cursor: pointer; }
  .modos button.activo { background: var(--tinta); color: var(--panel); border-color: var(--tinta); }
  .lectura { margin: 2px 0 8px; padding-left: 18px; font-size: 13px; color: var(--tinta); }
  .fichas { display: flex; flex-wrap: wrap; gap: 8px 28px; margin: 6px 0; }
  .fichas div { display: grid; gap: 1px; }
  .fichas i { font: 600 12px var(--display); color: var(--tinta-3); text-transform: uppercase; letter-spacing: .04em; font-style: normal; }
  .fichas b { font-size: 22px; }
  .fichas small { font-size: 12px; color: var(--tinta-2); }
  .leyenda { display: flex; flex-wrap: wrap; gap: 4px 14px; font: 600 12px var(--display); color: var(--tinta-2); margin: 4px 0; }
  .leyenda i { display: inline-block; width: 14px; height: 3px; border-radius: 2px; margin-right: 5px; vertical-align: middle; }
  .rejilla { display: grid; grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr) minmax(0, 1fr); gap: 14px; }
  @media (max-width: 900px) { .rejilla { grid-template-columns: minmax(0, 1fr); } }
  svg { width: 100%; display: block; }
  .rej { stroke: var(--rejilla); stroke-width: 1; }
  .rej.cero { stroke: var(--tinta-3); stroke-dasharray: 4 3; }
  .eje { font: 500 10px var(--mono); fill: var(--tinta-3); }
  .fina { fill: none; stroke-width: 1; stroke-opacity: .3; }
  .gruesa { fill: none; stroke-width: 2.5; }
  .tray { fill: none; stroke-width: 1.5; stroke-opacity: .7; }
  .esc { stroke: var(--tinta-2); stroke-width: 2; }
  .rodillo { overflow-x: auto; }
  table.mini { border-collapse: collapse; width: 100%; font-size: 13px; }
  .mini th { font: 600 11px var(--display); letter-spacing: .05em; text-transform: uppercase; color: var(--tinta-2); text-align: left; padding: 4px 8px; border-bottom: 1px solid var(--linea); white-space: nowrap; }
  .mini td { padding: 4px 8px; border-bottom: 1px solid var(--rejilla); white-space: nowrap; }
  .mini .n { text-align: right; }
  .mini tr.yo td { background: color-mix(in srgb, var(--yo) 10%, transparent); }
  .bien { color: #1b7f3b; font-weight: 600; }
  .mal { color: var(--error, #c62828); font-weight: 600; }
  .punto { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; }
</style>
