// Llamadas a la API de FastTack. Los errores llevan el mensaje del servidor, ya en español.
async function pedir(metodo, ruta, cuerpo) {
  const r = await fetch(ruta, {
    method: metodo,
    headers: cuerpo ? { 'Content-Type': 'application/json' } : {},
    body: cuerpo ? JSON.stringify(cuerpo) : undefined,
  });
  const datos = await r.json().catch(() => null);
  if (!r.ok) {
    const d = datos?.detail;
    const e = new Error(typeof d === 'string' ? d : d?.mensaje || `Error ${r.status}`);
    e.estado = r.status;
    e.detalle = d;
    throw e;
  }
  return datos;
}

const id = (c) => encodeURIComponent(c).replace(/%7E/g, '~');

export const api = {
  campeonatos: () => pedir('GET', '/api/campeonatos'),
  cargar: (url, division) => pedir('POST', '/api/campeonatos', { url, division }),
  campeonato: (c) => pedir('GET', `/api/campeonatos/${id(c)}`),
  renombrar: (c, nombre) => pedir('PATCH', `/api/campeonatos/${id(c)}`, { nombre }),
  eliminar: (c) => pedir('DELETE', `/api/campeonatos/${id(c)}`),
  estado: (c) => pedir('GET', `/api/campeonatos/${id(c)}/estado`),
  ajustar: (c, clave, cambios) => pedir('PATCH', `/api/campeonatos/${id(c)}/pruebas/${clave}`, cambios),
  analisis: (c, clave) => pedir('GET', `/api/campeonatos/${id(c)}/pruebas/${clave}/analisis`),
  pistas: (c, clave) => pedir('GET', `/api/campeonatos/${id(c)}/pruebas/${clave}/pistas`),
  resumen: (c, descartes) => pedir('GET', `/api/campeonatos/${id(c)}/resumen${descartes != null ? '?descartes=' + descartes : ''}`),
  debrief: (c, ambito, barco) => pedir('GET', `/api/campeonatos/${id(c)}/debrief?ambito=${encodeURIComponent(ambito)}&barco=${encodeURIComponent(barco)}`),
  generarDebrief: (c, ambito, barco, texto) => pedir('POST', `/api/campeonatos/${id(c)}/debrief`, { ambito, barco, ...(texto != null ? { texto } : {}) }),
  crearSesion: (nombre, clase) => pedir('POST', '/api/sesiones', { nombre, clase, zona: Intl.DateTimeFormat().resolvedOptions().timeZone }),
  subirVkx: async (sid, archivo, vela, nombre) => {
    const q = new URLSearchParams({ vela, nombre: nombre || '', archivo: archivo.name });
    const r = await fetch(`/api/sesiones/${sid}/vkx?${q}`, { method: 'POST', headers: { 'Content-Type': 'application/octet-stream' }, body: archivo });
    const datos = await r.json().catch(() => null);
    if (!r.ok) throw new Error(`${archivo.name}: ${typeof datos?.detail === 'string' ? datos.detail : 'error ' + r.status}`);
    return datos;
  },
  quitarVkx: (sid, n) => pedir('DELETE', `/api/sesiones/${sid}/vkx/${n}`),
  subirVkxCampeonato: async (c, archivo, vela) => {
    const q = new URLSearchParams({ vela, archivo: archivo.name });
    const r = await fetch(`/api/campeonatos/${id(c)}/vkx?${q}`, { method: 'POST', headers: { 'Content-Type': 'application/octet-stream' }, body: archivo });
    const datos = await r.json().catch(() => null);
    if (!r.ok) throw new Error(`${archivo.name}: ${typeof datos?.detail === 'string' ? datos.detail : 'error ' + r.status}`);
    return datos;
  },
  quitarVkxCampeonato: (c, n) => pedir('DELETE', `/api/campeonatos/${id(c)}/vkx/${n}`),
  temporada: (barco) => pedir('GET', `/api/temporada${barco ? '?barco=' + encodeURIComponent(barco) : ''}`),
  preferencias: () => pedir('GET', '/api/preferencias'),
  fijarBarco: (barco) => pedir('PUT', '/api/preferencias', { barco }),
};

// Hora local de la regata a partir de epoch ms y el desfase del campeonato.
export function horaLocal(ms, desfaseMs = 0, conDia = true) {
  const d = new Date(ms + desfaseMs);
  const hh = String(d.getUTCHours()).padStart(2, '0'), mm = String(d.getUTCMinutes()).padStart(2, '0');
  if (!conDia) return `${hh}:${mm}`;
  const dia = d.toLocaleDateString('es-ES', { weekday: 'short', day: 'numeric', month: 'short', timeZone: 'UTC' });
  return `${dia} · ${hh}:${mm}`;
}

export function duracion(ms) {
  const s = Math.round(ms / 1000), h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), x = s % 60;
  return (h ? `${h}:${String(m).padStart(2, '0')}` : m) + ':' + String(x).padStart(2, '0');
}

export const clave = (v) => (v || '').replace(/\s/g, '').toUpperCase();

// 'ESP1214' → 'ESP 1214' (para mostrar una vela guardada como clave)
export const velaBonita = (v) => (v || '').replace(/^([A-Z]+)\s*(\d)/, '$1 $2');
