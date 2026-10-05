<script>
  // Insignia de la clase en pequeño: el logo que el usuario haya puesto en <datos>/logos; si no, el
  // oficial de las clases que trae FastTack (public/clases: J/70, Snipe, ORC; ver LEEME.txt); si no,
  // una insignia propia, como la de la vela.
  import { logosDisponibles } from './api.js';

  let { clase = '', tam = 34 } = $props();
  const slug = $derived((clase || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9]/g, ''));
  // texto y color de las clases más comunes; el resto, sus siglas con un color fijo por nombre
  const CONOCIDAS = [
    [/^j70/, 'J/70', '#0f2a36'], [/^j80/, 'J/80', '#7a1f2b'], [/^j24/, 'J/24', '#1e4f8a'], [/^snipe/, 'SNIPE', '#c62828'],
    [/orc|crucero|irc/, 'ORC', '#1f5fae'], [/ilca|laser/, 'ILCA', '#1a7f4b'], [/^470/, '470', '#245ea8'], [/^420/, '420', '#2e7d9a'],
    [/49er/, '49er', '#111827'], [/^29er/, '29er', '#6b2fa3'], [/opti/, 'OPTI', '#e0622e'], [/^star/, '★', '#0b3a75'],
    [/drag/, 'D', '#3b5b2b'], [/etchells/, 'E22', '#38404a'], [/sb20/, 'SB20', '#d4342c'], [/melges/, 'M', '#00838f'],
    [/finn/, 'FINN', '#2b3a67'], [/nacra/, 'N17', '#00796b'], [/tp52/, 'TP52', '#222222'], [/^6m|6metro/, '6mR', '#5d4037'],
  ];
  const PALETA = ['#1f5fae', '#1a7f4b', '#6b2fa3', '#00838f', '#7a1f2b', '#38404a', '#a35c00'];
  const propia = $derived.by(() => {
    const k = CONOCIDAS.find(([re]) => re.test(slug));
    if (k) return { texto: k[1], color: k[2] };
    let h = 0;
    for (const ch of slug) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
    const texto = (clase || '?').replace(/[^A-Za-z0-9/]/g, '').slice(0, 4).toUpperCase() || '?';
    return { texto, color: PALETA[h % PALETA.length] };
  });
  const INCLUIDOS = [[/^j70/, '/clases/j70.png'], [/^snipe/, '/clases/snipe.svg'], [/orc|crucero/, '/clases/orc.png']];
  let fallo = $state(false);
  const src = $derived(fallo || !slug ? null : $logosDisponibles.has(slug) ? `/api/logos/${slug}` : INCLUIDOS.find(([re]) => re.test(slug))?.[1] ?? null);
  const tamTexto = $derived(propia.texto.length >= 5 ? tam * 0.24 : propia.texto.length >= 4 ? tam * 0.27 : propia.texto.length === 3 ? tam * 0.32 : tam * 0.4);
</script>

{#if src}
  <img class="ins" {src} alt={clase} title={clase} width={tam} height={tam} onerror={() => (fallo = true)}>
{:else}
  <svg class="ins" viewBox="0 0 40 40" width={tam} height={tam} role="img" aria-label={`Clase ${clase}`}>
    <title>{clase}</title>
    <rect x="1" y="1" width="38" height="38" rx="10" fill={propia.color} />
    <text x="20" y="21" text-anchor="middle" dominant-baseline="middle" fill="#fff" font-family="Barlow Semi Condensed, Arial Narrow, Arial, sans-serif"
          font-weight="700" font-style="italic" font-size={tamTexto * 40 / tam}>{propia.texto}</text>
  </svg>
{/if}

<style>
  .ins { flex: none; display: block; border-radius: 10px; object-fit: contain; }
  img.ins { background: #fff; border: 1px solid var(--linea); padding: 2px; }
</style>
