# FastTack

Análisis post-regata de J/70 con los datos de **Vakaros RaceSense** (dispositivos Atlas 2). Uso interno del equipo de ESP 1214 y su entrenador.

> Estado: **primera versión completa (v0.7.0), validada** (Fase 5). Carga cualquier campeonato de RaceSense, analiza cada prueba (mapa con reproductor y capas, valores instantáneos, pestañas por fase con tablas y gráficos), resume el campeonato con una general calculada y escribe debriefs con IA comparando con el top 5. Fórmulas y validación en [`docs/metricas.md`](docs/metricas.md); fuente de datos en [`docs/fuente_datos.md`](docs/fuente_datos.md); plan en [`docs/plan_fase3.html`](docs/plan_fase3.html).

Lo que hace, de un vistazo:

1. **Pegas el enlace** del visor de RaceSense → carga el campeonato y reconstruye las pruebas y llegadas que RaceSense no tiene.
2. **Analizar una prueba** → recorrido, pasos por baliza, viento reconstruido (TWD, roladas, presión), métricas por tramo y barco, salida, maniobras, laylines, puertas, barco fantasma.
3. **Resumen del campeonato** → general calculada, evolución por prueba frente a la flota y al top 5, salidas, maniobras, laylines, puertas y viento.
4. **Debrief con IA** → texto para la tripulación a partir de esas cifras; cada cifra se comprueba.

Todo es cálculo determinista con los datos de RaceSense; lo que depende del viento reconstruido va marcado como **estimado**. La IA solo redacta.

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
3. Para tenerlo a mano: en Safari, *Compartir → Añadir a pantalla de inicio* (queda con su icono y se abre a pantalla completa).

En el móvil, las pestañas de la prueba quedan fijas arriba y el reproductor fijo abajo (el botón ×4 cambia la velocidad), para mover el tiempo mientras se leen las tablas. Las explicaciones de cada cálculo están plegadas en «Cómo se calcula». Con el móvil en modo oscuro, FastTack también se ve en oscuro.

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

## Analizar una prueba

Pulsa **Analizar →** en una prueba. La primera vez se calcula el análisis y se descargan las trazas (unos segundos); después queda guardado.

- **Barcos en mapa y tabla**: solo el tuyo, top 5/10/15 de la prueba, toda la flota o *Elegir…* uno a uno. Cada barco tiene un color fijo; el tuyo, naranja.
- **Pestañas**: se generan con el recorrido real (Salida, Ceñida 1, Offset 1, Popa 1, Puerta…, Llegada, Rendimiento, Debrief IA; la pestaña del offset incluye también el paso por la baliza de barlovento). Cada una lleva el reproductor a su momento.
- **Mapa**: arrastra y haz zoom; las balizas con borde discontinuo están **estimadas** (sin Atlas). Una traza cortada o un círculo vacío = hueco de datos.
- **Corriente estimada**: flecha y valor en la esquina del mapa (la de la vuelta en curso) y detalle con su confianza en las pestañas de ceñida y popa.
- **Escora óptima** (pestañas de ceñida): rango de escora con mejor VMG frente a los barcos de alrededor, cuánto se pierde por debajo o por encima, tu escora y la del top 5, y el % de tu tiempo dentro del rango (columna «En rango»).
- **HDG corregido**: el rumbo de proa de cada barco sale en verdadero, con el desvío de su brújula y la declinación ya corregidos.
- **Capas del mapa** (botones sobre el mapa): *Presión* (SOG de cada barco frente a la flota; anillo = está acelerando), *TWD* (tinte por la rolada), *Rol* (traza en azul cuando la rolada favorece al barco, en rojo cuando le perjudica) y *SOG* (traza por velocidad). Las laylines de la baliza siguiente se ven siempre. Encima, la TWD del momento y la fase de rolada.
- **Gráficos**: en cada ceñida o popa, la evolución de TWD y presión; en *Rendimiento*, la métrica que elijas a lo largo de la prueba (pasa el cursor para ver valores).
- **Reproductor**: ▶, barra de tiempo, ×1/×4/×10/×30; hora local y tiempo desde la señal.
- Lo marcado con **\*** o «est.» es estimado con el viento reconstruido. «Datos» indica la calidad de la telemetría de cada barco en el tramo.

Enlace de ejemplo (Mundial de J/70 2026, Cascais): `https://player.vakaros.com/watch/oRkxbTpSZPbSkrmKrbj2/J%2F70`

## Resumen del campeonato

En la página del campeonato, **Resumen del campeonato →**. La primera vez analiza las pruebas que falten, una a una (unos segundos cada una; más si hay que descargar telemetría).

- **General calculada**: puntuación baja con los descartes que elijas (por defecto 1 a partir de 4 pruebas). No incluye decisiones del jurado, así que puede diferir algo de la oficial. «rec.» = llegadas reconstruidas.
- **Comparar con**: tu barco solo, o frente al top 3/5/10 de la general.
- **Gráficos por prueba**: puesto y la métrica que elijas (VMG, SOG, TWA, escora, cabeceo, pérdidas), con la mediana de la flota.
- **Escora óptima del campeonato**: todas las ceñidas juntas (y por intensidad de viento si hay viento de referencia), con tu escora y la del top 5.
- **Debrief del campeonato** al final (ver abajo).
- **Salidas, maniobras, laylines y puertas** acumuladas, y **según la intensidad del viento** (necesita el viento de referencia de cada prueba).

Si al abrir un campeonato ya guardado aparece «Hay una versión mejor de la detección…», pulsa **Actualizar**: vuelve a calcular pruebas y llegadas con la telemetría ya descargada y conserva tus ajustes.

## Debrief con IA

En cada prueba (pestaña **Debrief IA**) y al final del resumen del campeonato. La IA solo redacta: recibe las cifras del análisis y **cada cifra de su texto se comprueba** contra ellas; las que no aparecen se resaltan con un aviso.

- **Generar con Claude Code**: si Claude Code está instalado en el ordenador donde corre FastTack (comando `claude`, con la sesión iniciada con tu cuenta), FastTack le pide el texto directamente. Tarda 30–60 s y usa tu plan de Claude, sin claves ni coste aparte.
- **Con Claude.ai**: *Copiar las instrucciones* (llevan las cifras), pegarlas en una conversación nueva de claude.ai, y pegar la respuesta en FastTack. Sirve desde cualquier sitio, también desde el móvil.
- El texto se guarda y se reutiliza. Si cambian las cifras (nueva versión del motor, viento de referencia…), avisa de que conviene regenerarlo.

- **Referencia: el top 5.** Las conclusiones salen de comparar con los 5 primeros de la prueba (o de la general, en el campeonato); la mediana de la flota queda como contexto.

Para instalar Claude Code en el Mac (sin Node ni permisos de administrador):

```bash
curl -fsSL https://claude.ai/install.sh | bash
```

Abre una ventana nueva del Terminal, ejecuta `claude` una vez para iniciar sesión con tu cuenta de Claude (suscripción, no clave de API) y sal con `/exit`. Arranca FastTack desde una ventana abierta después de instalarlo. Si `claude` no se encuentra: `echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc && source ~/.zshrc`.

## Actualizar FastTack

- **Con git** (si lo clonaste): `git pull` dentro de la carpeta.
- **Con el ZIP**: descarga el nuevo, copia la subcarpeta `datos/` de la versión anterior dentro de la nueva (así no se vuelve a descargar nada) y borra la anterior.

Después, recarga el navegador con Cmd+Shift+R y comprueba la versión al pie de la página. Los análisis se recalculan solos cuando cambia la versión del motor.

## Validación

- **Frente a Track to Tactics** (Cascais Vela, prueba 9, 34 barcos): pasos por baliza a ±2 s (offset estimado ±8 s), elección de puerta 34/34, puerta favorecida la misma, SOG, distancia y escora con correlaciones de 0,83–0,97, salida y lado de las laylines iguales (28/28). Nuestra VMG explica el resultado del tramo mucho mejor (correlación con el parcial −0,68 a −0,92 frente a −0,14 a −0,52). La diferencia principal es la TWD (4–6°). **Corriente**: ellos dan 0,9 kn en esa prueba, con una referencia externa; nosotros estimamos 0,26 kn en el mismo sentido, con dos métodos independientes que coinciden.
- **Frente a la clasificación oficial** (Mundial 2026, 100 barcos, 10 pruebas): 83 de 100 barcos a ±3 puestos en la general calculada, incluidas 4 pruebas reconstruidas desde la telemetría; las diferencias son decisiones del jurado.
- **Flujo completo** desde una instalación vacía (Cascais Vela, vista de móvil): carga en 7 s, resumen con las 9 pruebas analizadas en ~2 min, debrief en ~35 s, sin errores.

Detalles en [`docs/metricas.md`](docs/metricas.md).

## Limitaciones conocidas

- **Corriente**: estimada (sin corredera) a partir de las brújulas y el GPS de la flota, con un nivel de confianza; es una por prueba y por vuelta, no un mapa por zonas. Las laylines ya la incluyen; TWD y TWA siguen siendo sobre el fondo.
- **Sin anemómetro ni corredera**: todo el viento es reconstruido desde la flota; la intensidad solo se calibra con el viento de referencia que introduzcáis.
- **Huecos de telemetría** (RaceSense guarda ~50 % de las muestras): lo que pasa dentro de un hueco no se ve (maniobras, pérdidas); cada métrica lleva su calidad de datos.
- **General calculada** sin decisiones del jurado (DSQ, redress…). Las llegadas reconstruidas son provisionales.
- **Recorrido dudoso**: si las balizas estimadas no cuadran con la duración de la prueba, la prueba cuenta en la general pero sus métricas no entran en el resumen (en el Mundial, la prueba 4).
- No se calcula la layline hacia la línea de llegada. Sin PDF (fuera de v1).

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
| `fasttack/motor/` | Cálculo puro y con tests: trazas, detección de salidas y llegadas, recorrido, viento, tramos, salida, análisis de una prueba, resumen y general calculada |
| `fasttack/ia/` | Debrief: cifras para la IA, instrucciones, validación de cifras y caché |
| `fasttack/api/` | API FastAPI y servidor de la web |
| `frontend/` | Web (Svelte) |
| `tests/` | Tests del motor y de la ingesta |
| `docs/` | Fuente de datos, inventario de métricas, plan |
| `fase1_*.py`, `prototipo/` | Scripts de exploración de la Fase 1 y el prototipo de visor |

Variables de entorno: `FASTTACK_DATOS` (carpeta de datos; por defecto `datos/`), `FASTTACK_PAUSA_S` (pausa entre peticiones a RaceSense; por defecto 1 s), `FASTTACK_CLAUDE` (comando de Claude Code; por defecto `claude`).

## Datos y uso responsable

Los datos vienen de las APIs públicas que usa el visor de RaceSense, que no están documentadas oficialmente. FastTack las pide de forma moderada (secuencial, con pausa y un User-Agent identificable) y guarda todo para no repetir descargas. Uso interno del equipo; antes de abrirlo a terceros hay que pedir permiso a Vakaros. Detalles en [`docs/fuente_datos.md`](docs/fuente_datos.md).
