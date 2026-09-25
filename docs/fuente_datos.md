# Fuente de datos: Vakaros RaceSense

> Estado: **VERIFICADO — Fase 1 cerrada** (25-09-2026). Todas las dudas del borrador se han resuelto con descargas reales
> (J/70 Worlds 2026, regata 2 y ILCA 7 Worlds 2026 Gold, regata 1) con `fase1_muestras.py`. Los resultados están en
> `data/sample/informe_fase1.md` (el script lo regenera; la telemetría en bruto no se versiona).
> Las verificaciones se marcan con ✔ y las correcciones al borrador con **(corregido)**.

## Resumen

El reproductor de RaceSense (`player.vakaros.com/watch/...`) carga los datos de **dos APIs HTTP públicas, sin clave ni sesión**:

| Fuente | Qué da | Uso en la app |
|---|---|---|
| `https://player.vakaros.com/api/regatta?event={eventId}` | Metadatos del campeonato: divisiones, inscritos, regatas, salidas (hora, línea, OCS, distancia a la línea en el disparo) y llegadas (hora, distancia recorrida, velocidad máx.) | Lista de regatas, flota, hora de salida, clasificación |
| `https://teleapi.regatta.app` (Telemetry API 0.1.0, OpenAPI en `/openapi.json`) | Telemetría de barcos **y de balizas** (GPS, rumbo, SOG, escora, cabeceo), recorridos y ventanas de tiempo | Trazas, balizas, línea, todo el análisis |

Ninguna de las dos es una API publicada oficialmente. Son las que usa el propio visor y Vakaros puede cambiarlas sin aviso. La app las aísla en un módulo de ingesta con caché local.

## De la URL del campeonato al `eventId`

```
https://player.vakaros.com/watch/{eventId}/{división}?ts=...#race=2&boat=ESP+1214&tab=custom
```

- `eventId`: segundo segmento de la ruta (`oRkxbTpSZPbSkrmKrbj2` en el Mundial de J/70 2026).
- `división`: tercer segmento, codificado en URL (`J%2F70`). Es la **clase** de la división y, si dos divisiones comparten clase, se le añade el nombre (p. ej. `ILCA Gold`). En el Mundial de J/70 la división interna se llama `Open`.
- Otras formas de enlace aceptadas por el visor: `/?event={id}&division={div}` y `/#event={id}&division={div}`.
- `race`, `boat`, `tab` y `day` van en el *hash*: son solo estado de la vista.

## 1. `GET player.vakaros.com/api/regatta?event={eventId}`

Sobre de respuesta:

```json
{ "eventId": "...", "source": "firestore-snapshot", "revisions": [ { "validFrom": null, "doc": { ... } } ] }
```

Se usa la **última** revisión. Estructura de `doc` observada:

```
doc:         name, startDate, endDate, raceSenseEvent, divisions[]
division:    name ("Open"), boatClass, startLength ("fiveMin"), boatShapeId,
             participants[], courses[], races[]
participant: sailNumber ("ESP 1214"), boatName, bowNumber
race:        raceNumber, isPractice, timezoneOffset (µs), endTime, starts[], finishes[]
start:       id, startNumber, startTime (epoch ms), stopReason ("finished"…), prepFlag,
             startLine { leftEnd, rightEnd }, checkedInParticipants[], ocsParticipants[],
             exoneratedParticipants[], clearedOcs[], gpsCorrectionType ("dgnss"), gpsCorrectionAge,
             startingStats[] { sailNumber, serialNumber, startTime, positionAtStart,
                               headingAtStartDeg, lineLeftLocation, lineRightLocation, dtlMm, mask }
finish:      sailNumber, serialNumber, finishingTime (RFC 3339), positionAtFinish, heading,
             distanceTraveled (m), maxSpeed (nudos), lineLeftLocation, lineRightLocation, mask
```

Detalles importantes:

- **Varias entradas en `starts[]`** significan llamadas generales. La que vale es la última.
- **(nuevo)** Hay regatas **sin ninguna llegada** y con media flota en `ocsParticipants` (J/70: regatas 1, 4 y 7, con 50, 31 y 26 OCS). Tienen `stopReason: "finished"` igualmente.
  - La **regata 1 de J/70 fue la de entrenamiento** (confirmado por el equipo). No era oficial, por eso hubo 50 OCS, y la flota la dejó al final de la segunda ceñida.
  - **`isPractice` no la marca** (vale `false`), así que no sirve para distinguir el entrenamiento.
  - Regla: una regata sin `finishes[]` **no puntúa** y no se marca a todos DNF. Su telemetría **sí se analiza** (salida, ceñidas, rodeos) hasta donde llegó la flota.
  - Las regatas 4 y 7 de J/70 siguen sin explicación.
- **(nuevo)** `participants[]` incluye entradas que no compiten (entrenadores: `USA 0000 «Coach Chris»`, `USA 1111`, `USA 2222`). La flota de cada regata es `checkedInParticipants` de la salida válida.
- **(nuevo)** `startingStats[].serialNumber` es el nº de serie del Atlas en hexadecimal (`"73C4"`) y coincide con `sn` de la telemetría (`0x73C4`). ✔ 43/43 coincidencias en J/70 R2. En `finishes[]` suele venir vacío (99/100), así que la llegada se relaciona por `sailNumber`. `startingStats[].startTime` llega `null`.
- **(nuevo)** `divisions[].courses[].achievements[]` define el recorrido con nombres (`Start`, `M1`, `M2`, `Gate`, `R1`, `Gate 3`, `Finish`…), tipo (`startLine`, `markRounding` + `roundingDirection`, `gate`, `finishLine`) y `deviceRoles[] {role, sn}`. El `sn` va en hex de 10 dígitos (`"0238004DAB"`) y **sus 16 bits bajos son el `sn` de la telemetría** (`0x4DAB` = 19883). ✔ Todas las balizas de `/courses` casan así. En J/70 la lista es `Start, Gate, M1, M2, Finish` repetida 3 veces: parece una plantilla, no el orden de paso, así que la secuencia se sigue infiriendo con la flota.
- **La hora de salida registrada va 1 s después del minuto** (retardo del dispositivo del comité). La señal real es `floor(startTime, minuto)`.
- **Las marcas de tiempo llegan en 4 formatos**: epoch ms, RFC 3339 con `Z`, ISO **sin zona** (hora local de la regata, desplazada `timezoneOffset`) y `{seconds, nanoseconds}`. Hay que normalizarlas todas.
- `raceNumber` dentro de `finishes[]` y `startingStats[]` **no es fiable** (es un campo del dispositivo). La regata a la que pertenece una llegada es el array en el que está.
- `mask.value` es un campo de bits: el bit 0 valida la distancia y la velocidad máxima, y el bit 1 valida el rumbo.
- ✔ Coordenadas: `startLine.leftEnd/rightEnd` es **`[lat, lon]`** (27/27 casos). Todo lo que va dentro de un objeto `{coordinates: [...]}` (`positionAtStart`, `lineLeftLocation`, `lineRightLocation`, `positionAtFinish`, `raceSenseEvent.origin`) es GeoJSON **`[lon, lat]`** (8 434/8 434 casos en los dos campeonatos). La regla es por campo; el control por rango queda solo como aserción.
- ✔ `startLine.leftEnd` es el **pin** y `rightEnd` el **extremo del comité**: en la señal, la baliza `startLeft` está a 1–13 m de `leftEnd` y la `startRight` a 1–2 m de `rightEnd`.
- **Clasificación**: `finishes[]` ordenado por `finishingTime`. Solo existen los códigos OCS y DNF (un barco sin llegada es DNF). No incluye penalizaciones, retiradas ni decisiones del jurado, y **no hay general por puntos**: la general se calcula (puntuación baja, descartes configurables) y se marca como «calculada».

## 2. Telemetry API (`teleapi.regatta.app`)

| Endpoint | Parámetros | Devuelve |
|---|---|---|
| `GET /telemetry/racing-summary/{eventId}` | — | Por división y regata: `race_number`, `start_number`, `begin`, `end`, `start` (ms). **(corregido)** `start` casi siempre es igual a `begin` y **no es la señal**; no sirve para acotar regatas (ver nota al final) |
| `GET /telemetry/event-times/{eventId}` | `division?` | Rango de tiempo con datos por división |
| `GET /telemetry/event/{eventId}` | `division?`, `after` (ms, obligatorio), `before?`, `limit` (1–100 000, por defecto 1000) | Filas de telemetría en formato columnar |
| `GET /courses/{eventId}` | `division?` | Recorridos: balizas por número de serie y su función. **(corregido)** Envuelto en `{"$schema", "event_id", "courses": [ {division, name, marks[]} ]}` |
| `GET /division/short-id/{eventId}/{division}` | — | ID corto de la división |

### Telemetría: `/telemetry/event`

```json
{ "Fields": ["ts","sn","division","sail_number","race_number","start_number","race_stage",
             "role","latitude","longitude","pitch","roll","heading","sog","status"],
  "Rows": [[1788789452900,20422,"Open","ESP 1283",1,1,"finished","competitor",
            38.6271904,-9.3918211,5,-3,41,6.609056,8], ...] }
```

| Campo | Significado | Observaciones |
|---|---|---|
| `ts` | Epoch ms (UTC) | Resolución de 100 ms |
| `sn` | Nº de serie del Atlas 2 | Identifica el dispositivo; se relaciona con el barco mediante `sail_number` |
| `sail_number` | Vela | Vacío en balizas. ✔ Puede no llevar espacio (`BRA1440`, `BRA641`, `GBR1906`, `GER1898`, `POR570`), igual que en `participants` y en las listas OCS. Clave = sin espacios y en mayúsculas: casan las 100 velas de J/70 y las 47 de ILCA. ✔ Una vela puede tener **dos dispositivos** (`USA 684`: sn 23418 y 30311), así que se agrupa por vela y no por `sn` |
| `race_number`, `start_number` | Regata o salida en la que está el dispositivo | ✔ No son fiables: en la ventana de la regata 2 de J/70 aparecen `race_number` 2 y 3, y todos los dispositivos cambian de valor dentro de la ventana. **Nunca se usan como clave**: la regata se acota por tiempo con `/api/regatta` (señal − 10 min … última llegada + 5 min) |
| `race_stage` | `pre_start`, `starting`, `in_progress`, `finishing`, `finished` | **(nuevo)** No es fiable: alterna entre valores en muestras consecutivas del mismo dispositivo. No se usa |
| `role` | `competitor` o `mark` | **Las balizas llevan su propio Atlas y se transmite su posición** |
| `latitude`, `longitude` | Grados WGS84 | |
| `heading` | Rumbo de proa (°) | Enteros. ✔ Es rumbo de proa real, no COG: heading − COG tiene mediana +0,5…+0,9° y p5/p95 de −19/+23° (deriva, corriente, ruido). **(corregido)** Cada Atlas 2 se configura en verdadero o magnético y **la mayoría va en magnético**; la telemetría no dice cuál. Regla: se asume **magnético** y se pasa a verdadero sumando la declinación (WMM, en la posición y la fecha del evento; Cascais ≈ −1°, Dublín ≈ −2°). Por dispositivo, la mediana de heading − COG va de −12° a +10° (un caso de +30°): el error de alineación de la instalación es mucho mayor que la declinación, así que verdadero/magnético **no se puede detectar** con los datos. Se calibra un **offset por dispositivo** contra el COG en tramos estables (absorbe también un dispositivo que esté en verdadero), con ajuste manual por barco en la app |
| `sog` | Velocidad sobre el fondo, **nudos** | ✔ Siempre múltiplo de 0,1 m/s (5,442752 kn = 2,8 m/s). **(nuevo)** Hay picos espurios (29,2 kn en un J/70): hay que filtrar valores atípicos |
| `roll` | **Escora (°)** | Enteros con signo. ✔ **`roll > 0` = escora a estribor, `roll < 0` = escora a babor.** En la primera ceñida, con el viento estimado: J/70 amura babor +17° (99 % > 0), amura estribor −12° (70 % < 0); ILCA babor +6° (72 % > 0), estribor −5° (68 % < 0). **(nuevo)** Hay dispositivos con desviación fija (+20° en las dos amuras) y valores fuera de rango (−127): hace falta calibrar un offset por dispositivo y recortar |
| `pitch` | **Cabeceo (°)** | Enteros |
| `status` | Estado del dispositivo o del GPS | ✔ Valores vistos: 0, 1, 3, 8, 9, 11 (combinaciones de los bits 0, 1 y 3). **No indica validez**: todas las filas tienen posición y SOG coherentes. Con `8` (bit 3) la coherencia posición/SOG es algo mejor que con `0` (mediana 0,19 frente a 0,38 kn en J/70; igual en ILCA). Hipótesis: bit 3 = fix con corrección (`gpsCorrectionType: "dgnss"`). Decisión: **no se filtra por status**; como mucho sirve para ponderar. Las balizas llevan siempre 0 |

- **No hay COG**: se calcula a partir de las posiciones sucesivas. **No hay viento**: ni TWD ni TWS, así que se reconstruyen a partir de la flota.
- ✔ **Frecuencia de muestreo**: **no es 1 Hz fijo**. Barcos: Δt mediano 1,2 s (J/70) y 1,6 s (ILCA), p90 3,4–4,2 s y huecos > 5 s frecuentes (17 000 en la regata de J/70). Balizas: Δt mediano 0,5 s. Marcas de tiempo siempre múltiplo de 100 ms. Sin duplicados `(ts, sn)`. El análisis tiene que **remuestrear o interpolar** y tolerar huecos.
- ✔ **Volumen** (**corregido**): `/telemetry/event` devuelve **todos los dispositivos de la división** en una sola serie ordenada por `ts`, así que se pagina por regata y no por dispositivo. Son unos 110 B por fila en JSON y gzip lo reduce unas 5,4 veces.
  - J/70 R2 (111 min, 109 dispositivos): 269 542 filas, 29,7 MB en JSON (unos 5,4 MB por la red), 3 peticiones de < 1 s.
  - ILCA Gold R1 (73 min, 63 dispositivos): 167 249 filas, 17,7 MB, 2 peticiones.
  - Una regata cabe en unos 3–6 MB comprimidos en caché.
- ✔ Paginación: `after` es **inclusivo** (cada página repite 1–2 filas de la anterior), así que se deduplica por `(ts, sn)`.

### Recorridos: `/courses`

```json
{"division":"Open","name":"Default","marks":[
  {"sn":19883,"achievement_type":"start_line","mark_index":0},
  {"sn":25687,"achievement_type":"start_line","mark_index":1},
  {"sn":18759,"achievement_type":"port_rounding_zone","mark_index":0},
  {"sn":19228,"achievement_type":"port_rounding_zone","mark_index":0},
  {"sn":25687,"achievement_type":"gate_zone","mark_index":0},
  {"sn":25639,"achievement_type":"gate_zone","mark_index":1},
  {"sn":25687,"achievement_type":"finish_line","mark_index":0},
  {"sn":25639,"achievement_type":"finish_line","mark_index":1}]}
```

- Da la **función** de cada baliza (línea de salida, baliza a dejar por babor, puerta, llegada), pero **no la secuencia del recorrido ni el número de vueltas**.
- ✔ En J/70, el sn 25687 es el extremo del comité en la salida (a 2 m de `startLine.rightEnd`), y también la puerta izquierda y la llegada izquierda. Hacia el minuto 60 se desplaza unos 490 m **a la vez que** 25639 (puerta y llegada derecha): se recoloca la puerta/llegada. Es decir, un mismo dispositivo cambia de función y de sitio durante la regata, y la posición se toma siempre en el instante de cada paso.
- **(nuevo)** Las balizas transmiten **solo posición**: `sog`, `heading`, `roll`, `pitch` y `status` valen siempre 0.
- **(nuevo)** Hay dispositivos `role=mark` que **no están en ningún recorrido**. Son embarcaciones de apoyo: neumáticas que se mueven 1–4 km (J/70: 16525, 21253, 24575, 25470; ILCA: 30835, 30911, 30966) y barcos fondeados junto al comité (J/70: 19800; ILCA: 28881 y 30894, a unos 43 m de `rightEnd`; 11011). Se excluyen del recorrido; como mucho, se muestran en una capa aparte.
- **(nuevo)** Los recorridos (`/courses` y `/api/regatta`) son la **definición actual**, no una por regata. En J/70 R2 no hay telemetría de M1 ni M2 (sn 18759 y 19228), así que no transmitieron. **Regla: cuando una baliza no transmite, su posición se supone a partir de la flota**, en el punto donde los barcos la rodean (cambio de rumbo y de amura o trasluchada concentrados en el mismo sitio), y se recalcula si cambia a lo largo de la regata. Se marca como «estimada».
- **Hay que inferir la secuencia de tramos** a partir de los barcos: el orden en que la flota rodea cada baliza (paso a menos de X m con cambio de rumbo) da el recorrido real de cada regata (vueltas, offset, puerta o baliza simple). Así se generan las pestañas dinámicas.
- Las balizas pueden moverse durante la regata (cambios de recorrido): como se transmite su posición, se usa la posición en el instante de cada paso.

## Qué datos hay y cuáles no

| Dato | ¿Hay? | Fuente |
|---|---|---|
| Posición GPS de cada barco | Sí | telemetría |
| SOG | Sí | telemetría |
| Rumbo de proa (HDG) | Sí | telemetría (magnético por defecto → verdadero con la declinación; offset por dispositivo) |
| COG | Se calcula | posiciones |
| Escora y cabeceo | **Sí** | telemetría (`roll`, `pitch`) |
| Posición de las balizas en el tiempo | Sí, si transmiten | telemetría `role=mark` + `/courses`. Si no transmiten, se estima a partir de la flota |
| Línea de salida (pin y comité) | Sí | `start.startLine` + telemetría |
| Hora de salida (señal) | Sí | `start.startTime` (redondeado al minuto) |
| OCS | Sí | `ocsParticipants` − `exoneratedParticipants` − `clearedOcs` |
| Distancia a la línea en el disparo | Sí (del dispositivo) | `startingStats[].dtlMm` |
| Hora de llegada, distancia recorrida y velocidad máxima | Sí | `finishes[]` |
| Clasificación por regata | Sí (por hora de llegada) | `finishes[]` |
| General con penalizaciones, retiradas y jurado | **No** | se calcula y se marca como calculada |
| Viento (TWD y TWS) | **No** | se reconstruye (estimado) |
| Corriente | **No** | se estima como la diferencia entre SOG/COG y la velocidad y el rumbo por el agua (estimado; con poca precisión sin corredera) |
| Nombre y función de cada baliza | Sí | `divisions[].courses[].achievements[]` (sn hex → 16 bits bajos) |
| Secuencia del recorrido y vueltas | **No** | se infiere a partir de los pasos de la flota |

## Prueba con otro campeonato

`GET /telemetry/racing-summary/5JsqWPmBU6P7G5rk15ic` (Mundial de ILCA 7 2026, Elimination Series) devuelve 3 divisiones (Bronze, Silver y Gold) con 6 regatas cada una, en el mismo formato. ✔ El mismo flujo sirve para otros campeonatos. ✔ Telemetría de Gold R1 descargada y analizada: mismo formato, 47 barcos y 16 dispositivos baliza (10 de ellos en el recorrido).

Nota (**corregido**): en `racing-summary`, `begin` y `end` **no son la duración de la regata**, sino la ventana en la que los dispositivos están en esa regata (llega hasta el comienzo de la siguiente, a veces al día siguiente). Además, `start` no es la señal. En J/70, la «regata 1» del resumen (07-09, 13:09–13:57 UTC) es la salida anulada, y la ventana de la regata 2 empieza el día anterior. **Las ventanas de descarga se calculan con `/api/regatta`**: desde `floor(startTime, minuto)` − 10 min hasta la última `finishingTime` + 5 min.

## Uso responsable y condiciones

- Los [términos de servicio de Vakaros](https://www.vakaros.com/policies/terms-of-service) se refieren a la app Vakaros Connect. No mencionan el acceso automatizado ni el reproductor RaceSense, pero prohíben extraer el código fuente de la app. Aquí **no se usa código de Vakaros**: solo se leen los mismos JSON públicos que carga el visor.
- Son APIs no documentadas, así que no hay garantía de estabilidad.
- Medidas en la app: **caché permanente** (una regata terminada se descarga una sola vez), peticiones secuenciales con pausa y un `User-Agent` identificable. No se redistribuyen datos en bruto.
- Antes de **publicar** la app para terceros conviene pedir permiso a Vakaros. Para uso propio del equipo, el riesgo es bajo. *(No es asesoramiento legal.)*
