<script>
  import Nota from '../Nota.svelte';
  // Escora óptima de un tramo: la media de la escora de los 5 barcos con más VMG, frente a la del
  // barco de referencia. En popa, con signo (+ a sotavento, − a barlovento).
  import { num } from './datos.js';

  let { tramo, ref, nombreRef = '', titulo = null, enRangoTexto = null, nota = '', nombres = (v) => v } = $props();
  const popa = $derived(tramo.tipo === 'popa');
  const campo = $derived(popa ? 'escora_sotavento' : 'escora');
  const tituloV = $derived(titulo ?? (popa ? 'Escora óptima en popa' : 'Escora óptima en ceñida'));
  const o = $derived(tramo.escora_optima);
  const b = $derived(tramo.barcos[ref] ?? {});
  const mia = $derived(b[campo] ?? null);
  const frente = $derived(b.escora_frente_optima ?? null);
  const enRango = $derived(b.escora_en_rango_pct ?? null);
  const g = (x) => (x == null ? '—' : num(x, 1).replace(/,0$/, '') + '°');
  const lectura = $derived(frente == null ? '' : Math.abs(frente) <= 2 ? 'en la óptima' : frente > 0 ? 'más escorado' : 'más plano');
</script>

<section class="tarjeta bloque">
  <h3>{tituloV} <span class="est">estimada</span></h3>
  <div class="cifras">
    <div><span class="etq">Los 5 con más VMG</span><b class="num">{g(o.escora)}</b>{#if o.rango}<small class="tenue">entre {g(o.rango[0])} y {g(o.rango[1])}</small>{/if}</div>
    <div><span class="etq">{nombreRef}</span><b class="num">{g(mia)}</b>{#if frente != null}<small class:mal={Math.abs(frente) > 2}>{frente > 0 ? '+' : ''}{g(frente)} · {lectura}</small>{/if}</div>
    {#if enRangoTexto || enRango != null}<div><span class="etq">Cerca de la óptima</span><b class="num">{enRangoTexto ?? enRango + ' %'}</b><small class="tenue">{enRangoTexto ? '' : 'del tiempo a ±2°'}</small></div>{/if}
  </div>
  {#if popa}<p class="sub">En popa, escora con signo: <b>+</b> a sotavento, <b>−</b> a barlovento.</p>{/if}
  {#if o.barcos?.length}<p class="sub">Barcos: {o.barcos.map(nombres).join(', ')}.</p>{/if}
  {#if nota}<p class="sub">{nota}</p>{/if}
  <Nota>Escora óptima = la media de la escora mediana de los 5 barcos con más VMG del tramo (navegando estable, sin rodeos ni maniobras). No cuentan los sensores que no cuadran con la flota (a más de 6° de la mediana). Es una referencia: la escora también depende del peso y del estilo de cada tripulación.</Nota>
</section>

<style>
  .bloque { padding: 10px 12px; min-width: 0; }
  h3 { font-size: 15px; letter-spacing: .06em; text-transform: uppercase; color: var(--tinta-2); margin-bottom: 6px; }
  .est { color: var(--estimado); font-size: 11px; }
  .cifras { display: flex; flex-wrap: wrap; gap: 8px 28px; margin-bottom: 4px; }
  .cifras > div { display: grid; gap: 1px; }
  .etq { font: 600 12px var(--display); color: var(--tinta-3); text-transform: uppercase; letter-spacing: .04em; }
  .cifras b { font-size: 22px; }
  .cifras small { font-size: 12px; color: var(--tinta-2); }
  .cifras small.mal { color: var(--error, #c62828); }
  .sub { margin: 2px 0; font-size: 13px; color: var(--tinta-2); }
</style>
