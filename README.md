# FastTack

Análisis post-regata de J/70 con los datos de **Vakaros RaceSense** (dispositivos Atlas 2). Uso interno del equipo de ESP 1214 y su entrenador.

> Estado: **Fase 4 · hito 2** — carga de campeonatos y lista de pruebas (hito 1) y motor de análisis por prueba (hito 2, API `/api/campeonatos/{id}/pruebas/{clave}/analisis`; fórmulas y validación en [`docs/metricas.md`](docs/metricas.md)). Las pantallas de análisis llegan en el hito 3; el plan completo está en [`docs/plan_fase3.html`](docs/plan_fase3.html).

## Instalación (una vez)

En el Mac solo hace falta [uv](https://docs.astral.sh/uv/), que instala Python y las dependencias por su cuenta:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh     # instala uv
git clone https://github.com/Jpadront/FastTack.git
cd FastTack
```

La web va ya compilada dentro del repositorio: no hace falta Node.

## Arranque

```bash
uv run fasttack
```

Abre **http://localhost:8000** en el navegador. La primera vez tarda unos segundos más porque uv prepara el entorno.

Opciones: `--puerto 8080` para usar otro puerto; `--solo-este-ordenador` para no aceptar conexiones de la Wi-Fi. Para parar: `Ctrl+C`.

## Abrirlo en el móvil

1. El Mac y el móvil tienen que estar en **la misma Wi-Fi**.
2. Al arrancar, el terminal muestra la dirección para el móvil (p. ej. `http://192.168.1.34:8000`) y un **QR**: escanéalo con la cámara.
3. Para tenerlo a mano: en Safari, *Compartir → Añadir a pantalla de inicio*.

Si no carga: comprueba que el Mac no esté en reposo y que el cortafuegos de macOS permite conexiones entrantes a Python (*Ajustes del Sistema → Red → Cortafuegos*).

## Cargar un campeonato

1. Abre el campeonato en el visor de RaceSense y copia el enlace (`https://player.vakaros.com/watch/…`).
2. Pégalo en **Cargar un campeonato** y pulsa *Cargar*. Si tiene varias divisiones, te pedirá cuál.
3. La primera carga descarga el documento del comité y busca en la telemetría las pruebas que faltan (unos segundos por prueba). Todo queda guardado en `datos/` y no se vuelve a descargar.

En la lista de pruebas:

- **oficial**: llegadas del sistema de RaceSense.
- **reconstruida**: prueba o llegadas obtenidas de la telemetría porque RaceSense no las tiene; el puesto es provisional.
- **sin llegadas**: no se detecta una llegada de la flota (entrenamiento, anulada o sin datos). No cuenta.
- **Viento ref. (kn)**: la intensidad del viento en el disparo, si la sabéis. Sin ella, la intensidad del viento del análisis se mostrará relativa y «sin calibrar».
- **Cuenta**: desmárcala para dejar fuera una prueba; la numeración se ajusta sola.

Enlace de ejemplo (Mundial de J/70 2026, Cascais): `https://player.vakaros.com/watch/oRkxbTpSZPbSkrmKrbj2/J%2F70`

## Desarrollo

```bash
uv run pytest                       # tests
cd frontend && npm install          # web: solo para cambiarla
npm run dev                         # web en caliente en :5173 (la API sigue en :8000)
npm run build                       # compila a fasttack/web (se sube al repositorio)
```

Estructura:

| Carpeta | Qué hay |
|---|---|
| `fasttack/ingesta/` | URL → campeonato, cliente de RaceSense, normalización, caché (SQLite + Parquet), lista de pruebas |
| `fasttack/motor/` | Cálculo puro y con tests: trazas, detección de salidas y llegadas (y, en los hitos siguientes, el resto del análisis) |
| `fasttack/api/` | API FastAPI y servidor de la web |
| `frontend/` | Web (Svelte) |
| `tests/` | Tests del motor y de la ingesta |
| `docs/` | Fuente de datos, inventario de métricas, plan |
| `fase1_*.py`, `prototipo/` | Scripts de exploración de la Fase 1 y el prototipo de visor |

Variables de entorno: `FASTTACK_DATOS` (carpeta de datos; por defecto `datos/`), `FASTTACK_PAUSA_S` (pausa entre peticiones a RaceSense; por defecto 1 s).

## Datos y uso responsable

Los datos vienen de las APIs públicas que usa el visor de RaceSense, que no están documentadas oficialmente. FastTack las pide de forma moderada (secuencial, con pausa y un User-Agent identificable) y guarda todo para no repetir descargas. Uso interno del equipo; antes de abrirlo a terceros hay que pedir permiso a Vakaros. Detalles en [`docs/fuente_datos.md`](docs/fuente_datos.md).
