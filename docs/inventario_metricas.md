# Inventario de métricas

> Estado: **Fase 2 — CERRADA** (25-09-2026). Revisado con el informe de ejemplo de Track to Tactics («Cascais Vela · Race 9», J/70, ESP 1170), con la cuenta del usuario.
> El resultado de la revisión está en la sección «Confirmación con Track to Tactics». Los datos del informe de ejemplo **no se guardan en el repositorio**.

## Leyenda

| Estado | Significado |
|---|---|
| **Directo** | Viene tal cual de RaceSense (telemetría o `/api/regatta`) |
| **Calculado** | Se deriva de forma exacta de datos directos (geometría, tiempos, posiciones) |
| **Estimado** | Depende del viento reconstruido, de balizas estimadas o de un modelo. En la interfaz se marca como «estimado» |
| **Diferido** | Se puede estimar, pero se deja para después de la v1 (acordado con el equipo) |
| **No disponible** | No se puede obtener con los datos de RaceSense |

## Condiciones que afectan a casi todo

Hay cuatro limitaciones de los datos que condicionan muchas métricas:

1. **Cobertura de la telemetría ≈ 50 %.** Los huecos de más de 20 s suman casi la mitad del tiempo de regata (en la mejor prueba, 73 % de cobertura). Toda métrica por tramo lleva su **% de cobertura**. Por debajo de un umbral (propuesta: 60 % del tramo), la métrica se muestra como «datos insuficientes» y no se interpola. Las más afectadas son el número de maniobras, la pérdida en maniobras, la distancia navegada y la presión instantánea.
2. **Las balizas de barlovento y sus offsets no transmiten** en el Mundial de J/70. Su posición y los pasos por ellas se estiman con los rodeos de la flota. Lo que dependa de ellas (laylines, paso por baliza 1/2, tramo de offset) hereda la marca «estimado».
3. **No hay sensor de viento ni corredera.** TWD, TWS, TWA, VMG, la presión y la corriente salen del viento reconstruido. Hay dos referencias externas para contrastar: el modelo ERA5 de Open-Meteo (horario y a unos 30 km de resolución: sirve de guía, no de medida) y la polar de J/70.
4. **Pruebas que faltan en `/api/regatta`.** Se reconstruyen desde la telemetría, sin OCS fiables. Las métricas de esas pruebas llevan la marca «prueba reconstruida».

## Cabecera

| Elemento | Estado | Fuente / cálculo | Notas |
|---|---|---|---|
| Evento, fecha, clase | Directo | `doc.name`, `startDate`, `divisions[].boatClass` | |
| Número de regata | Calculado | Numeración cronológica sin entrenamiento | No es el `raceNumber` de la API (ver fuente_datos) |
| Número de barcos | Directo | `checkedInParticipants` de la salida válida | Sin entrenadores |
| Revisión de datos | Directo | `revisions[-1]` y `validFrom` | Además: % de cobertura de la telemetría y aviso de «prueba reconstruida» |
| Barco de referencia | — | Selección del usuario | ESP 1214 por defecto |
| Selector de barcos (solo foco, toda la flota, top 5/10/15) | Calculado | Clasificación de la prueba | Color fijo por barco, guardado por campeonato |

## Pestañas por fase

| Elemento | Estado | Fuente / cálculo | Notas |
|---|---|---|---|
| Secuencia de tramos (ceñidas, popas, balizas, puerta, offset, llegada) | Estimado | Orden de rodeos de la flota + `courses[].achievements[]` | La plantilla del recorrido no da el orden ni las vueltas |
| Número de vueltas | Estimado | Nº de rodeos de barlovento de la flota | Ej.: prueba 9 → 2 rodeos de barlovento |
| Baliza simple o puerta | Calculado / Estimado | Puerta si transmite (J/70: sn 25687/25639) | Barlovento con offset: estimado |

## Mapa de cada fase

| Elemento | Estado | Fuente / cálculo | Notas |
|---|---|---|---|
| Trazas con etiqueta | Directo | Telemetría | Los huecos se dibujan como huecos |
| Línea de salida (pin, comité) | Directo | `startLine` + telemetría de las balizas | |
| Balizas con Atlas, puerta, llegada | Directo | Telemetría `role=mark` | Posición en cada instante (se mueven) |
| Balizas de barlovento y offsets | Estimado | Rodeos de la flota | |
| Laylines | Estimado | TWD reconstruida + ángulo de ceñida/popa de la flota | |
| Reproductor (play, hora, +mm:ss, barra, velocidad) | Directo | — | Probado en el prototipo |
| Capa **Presión instantánea** (manchas de racha, anillos en los primeros barcos) | Estimado | SOG frente a la polar según el TWA de los barcos cercanos | Muy sensible a la cobertura; umbral mínimo de barcos por zona |
| Capa **TWD instantánea** (izquierda / eje / derecha, ±10°) | Estimado | Campo de TWD reconstruido en el espacio y el tiempo | |
| Capa **Rol** (traza según el beneficio de la rolada) | Estimado | Rumbo frente a la TWD local y amura | |
| Capa **SOG** (traza coloreada por velocidad) | Directo | Telemetría | |
| TWD actual y fase de rolada | Estimado | Viento reconstruido | |
| Corriente | Diferido | Diferencia entre la deriva de la flota y la polar | Acordado: fase de análisis posterior. En la v1, el indicador aparece como «no disponible» |

## Panel de valores instantáneos

| Elemento | Estado | Fuente / cálculo | Notas |
|---|---|---|---|
| Hora y tiempo desde la señal | Directo | Señal = `floor(startTime, min)` | |
| TWD y Δ con la media del tramo | Estimado | Viento reconstruido | |
| TWS y Δ con la media | Estimado | Inversión de la polar J/70 con el SOG de la flota, calibrada con el «viento de referencia» de la prueba | Sin referencia: solo relativa y marcada «sin calibrar» (ver «Consecuencias para el diseño») |
| Tramo actual y % de progreso | Calculado | Proyección sobre el eje del tramo | Con balizas estimadas → estimado |
| Presión izquierda/derecha y Δ L-R en nudos | Estimado | TWS estimada de los barcos cercanos a cada lado | |
| Tabla: posición, barco, Δm | Calculado | Distancia al líder proyectada en el eje del tramo | |
| Tabla: SOG, HDG | Directo | Telemetría | HDG magnético por defecto → verdadero (declinación) + offset por dispositivo |
| Tabla: COG | Calculado | Posiciones sucesivas | |
| Tabla: VMG, TWA | Estimado | COG/SOG frente a la TWD reconstruida | TWA = ángulo táctico GPS (se indica en la interfaz) |

## Salida

| Elemento | Estado | Fuente / cálculo | Notas |
|---|---|---|---|
| IDs de comité y pin | Directo | `achievements` (`startLeft/startRight`) → sn | |
| Sesgo de línea (° y m hacia pin o comité) | Estimado | Línea frente a la TWD en el disparo | |
| Viento en el disparo (dirección y velocidad) | Estimado | Viento reconstruido | |
| Corriente en la salida | Diferido | — | |
| Posición en la línea (% de comité a pin) | Calculado | Proyección de la posición en el disparo | |
| Margen a la línea en el disparo (m) | Directo / Calculado | `startingStats[].dtlMm` (del dispositivo); se calcula si falta | Contrastar ambos |
| SOG en el disparo | Directo | Telemetría interpolada | Si hay un hueco en el disparo → «sin dato» |
| Cruce de línea GPS (s tras el disparo) | Calculado | Intersección de la traza con la línea | |
| VMG de 0 a 90 s | Estimado | Depende de la TWD | |
| Posición y distancia a +60 s y +180 s | Calculado / Estimado | Proyección sobre el eje hacia la baliza 1 (estimada) | |
| Primera virada (s) | Calculado | Detección de maniobras | Condicionado a la cobertura |
| Posición y gap en la baliza 1 | Estimado | Paso por la baliza 1 estimada | |
| OCS | Directo | `ocs − exonerated − clearedOcs` | En pruebas reconstruidas: «sin dato» |
| TWD de salida, TWS en el disparo, extremos de la línea | Estimado / Directo | | |

## Ceñidas y popas

| Elemento | Estado | Fuente / cálculo | Notas |
|---|---|---|---|
| Gráfico de evolución del viento (TWS normalizado frente al % del líder, TWD por fase) | Estimado | | |
| Parcial y gap | Calculado / Estimado | Tiempos de paso (estimados en barlovento) | |
| VMG, SOG, TWA medios | Estimado (SOG directo) | | Solo con muestras válidas |
| Distancia navegada | Calculado | Suma de la traza | Los huecos se cubren en línea recta y se marcan; subestima |
| Número de maniobras | Calculado | Cambio de amura (viradas) o de banda (trasluchadas) según el rumbo | Maniobras perdidas en huecos: se cuentan con el cambio de amura, pero sin métricas de pérdida |
| Pérdida en maniobras (m) | Estimado | VMG real frente a la VMG de antes, en una ventana alrededor de la maniobra | Solo maniobras sin huecos en la ventana |
| Layline (OK / sobrepasada, lado y m) | Estimado | Baliza estimada + ángulo de ceñida | |
| Escora media y cabeceo medio | Directo | `roll`, `pitch` con offset por dispositivo | Signo: + estribor |
| Modo (VMG, VMG/soak…) | Estimado | Distribución del TWA frente a la SOG | Criterio a definir en metricas.md |
| Viento en 10 cortes internos (TWD media, TWS estimada, TWA objetivo) | Estimado | TWA objetivo de la polar J/70 | |
| Fases de rolada (tramo %, tipo, magnitud, quién la recibió primero) | Estimado | Serie de TWD del tramo | |
| Fases de presión (tramo %, tipo, Δ kn, quién la recibió primero) | Estimado | Serie de TWS del tramo | |
| Eficiencia de roladas frente al barco fantasma (m, %) | Estimado | Ruta de referencia simulada con la polar y el viento reconstruido | Definición en metricas.md |

## Balizas, puerta y llegada

| Elemento | Estado | Fuente / cálculo | Notas |
|---|---|---|---|
| Tabla de paso (posición, barco, tiempo, gap) | Calculado / Estimado | Cruce o rodeo de la baliza | Barlovento: estimado |
| Elección de puerta | Calculado | Baliza de la puerta más cercana en el rodeo | |
| Lado favorecido y ventaja (m) | Estimado | Distancia a barlovento de las dos balizas respecto a la TWD | |
| Tiempo de maniobra en la puerta (entrada → salida) | Calculado | Zona de 3 esloras | Condicionado a la cobertura |
| Llegada | Directo | `finishes[].finishingTime` | En pruebas reconstruidas: cruce de línea detectado (error mediano 0,3 s) |

## Rendimiento (toda la regata)

| Elemento | Estado | Fuente / cálculo | Notas |
|---|---|---|---|
| Gráfico con métrica seleccionable (VMG, SOG, TWA, escora, cabeceo; ceñida y popa) | Directo / Estimado | | Datos crudos en tenue + tendencia robusta (mediana móvil) |
| Pérdida por virada y por trasluchada | Estimado | | |
| Tabla de medias ordenable | Directo / Estimado | | Con la columna «cobertura %» |

## Debrief de entrenador con IA

| Elemento | Estado | Fuente / cálculo | Notas |
|---|---|---|---|
| Qué lo decidió / Tu barco / Diagnóstico / Próxima regata | Calculado (texto por IA) | La IA solo recibe métricas calculadas y las cita | Si una métrica es estimada o tiene poca cobertura, el texto lo dice |
| Categoría del diagnóstico (salida, geometría/distancia, ejecución/maniobras, rendimiento) | Calculado | Regla determinista por atribución de la pérdida frente a los mejores; la IA no la elige | |

## Resumen del campeonato (añadido)

| Elemento | Estado | Fuente / cálculo | Notas |
|---|---|---|---|
| Resultados por regata | Directo | `finishes[]` + pruebas reconstruidas | Sin penalizaciones de jurado |
| General (top 5 por defecto) | Calculado | Puntuación baja con descartes configurables | Marcada como «calculada» |
| Estadísticas de salida acumuladas | Mixto | | |
| Medias de rendimiento por regata y totales (ceñida y popa) | Estimado | | Ponderadas por cobertura |
| Pérdidas medias en maniobras, aciertos de layline y de puerta | Estimado | | |
| Evolución y tendencias según la intensidad del viento | Estimado | Por tramos de TWS estimada | La TWS estimada es la variable más incierta: los tramos de viento serán anchos |
| Debrief de campeonato con IA (3 fuertes, 3 mejoras, prioridades) | Calculado (texto por IA) | | |

## Lo que no se puede calcular con RaceSense

- **Velocidad por el agua, abatimiento real y corriente medida**: no hay corredera. Se pueden estimar, pero no medir.
- **TWS y TWD medidas**: no hay anemómetro. Todo el viento es reconstruido.
- **Clasificación oficial con penalizaciones, retiradas y jurado**: no está en los datos.
- **Trimado, velas y reglajes**: no hay sensores.
- **Tramos con huecos de telemetría**: lo que ocurre dentro de un hueco (p. ej. la pérdida de una virada hecha durante un corte) no se puede recuperar.

## Confirmación con Track to Tactics

Revisión del informe de ejemplo «Cascais Vela · Race 9» (J/70, 34 barcos, barco ESP 1170): pestañas, tablas, capas del mapa, debrief y estructura de los datos que carga la página. Se replica la **funcionalidad y las métricas**, no sus textos, su código ni su identidad visual.

### Qué es «Race 9»

- **Cascais Vela** (28–30 ago 2026) es **otro evento**, no el Mundial. En RaceSense es `NxFrzPhBiHHrg9C0XHHz`, y nuestra ingesta lo carga sin cambios: 9 pruebas y 34 llegadas en la 9. Sirve para validar la Fase 5 y como «otra URL de campeonato».
- «Race 9» es el `raceNumber` 9 del documento del comité (señal 30-08, 14:00 UTC). El contador de los dispositivos la llama 10: el mismo desfase que en el Mundial.
- En este evento **M1 y M2 sí transmiten**. TtT las toma de la posición del Atlas en cada rodeo, y los offsets de los rodeos de la flota.

### Coincide con el inventario

- **Cabecera**: evento, fecha, regata, clase, nº de barcos y versión. Barco de referencia. Selector «barcos en mapa y tabla».
- **Pestañas**: Salida, Ceñida 1, Baliza 1, Popa 1, Puerta, Ceñida 2, Baliza 2, Popa 2, Llegada y Rendimiento.
- **Capas del mapa**: presión instantánea, TWD instantánea, rol y SOG. Reproductor con ×4.
- **Panel instantáneo**: hora y +mm:ss desde la señal; TWD y TWS con su Δ respecto a la media; tramo y % de progreso; presión izquierda/derecha con Δ L-R. Tabla con #, barco, Δm, SOG, VMG, TWA, COG y HDG.
- **Salida**: tabla con las 12 columnas del inventario. Resumen con comité, pin, sesgo (° y m), viento en el disparo y corriente.
- **Ceñidas y popas**: tabla con posición, barco, parcial, gap, VMG, SOG, TWA, distancia, maniobras, pérdida (m), layline, escora, cabeceo y modo. Viento en 10 cortes, fases de rolada, fases de presión y eficiencia frente al barco fantasma.
- **Balizas, puerta y llegada**: posición, barco, tiempo, gap y elección de puerta. En la puerta, además, el lado favorecido y la ventaja en m.
- **Rendimiento**: 12 métricas seleccionables (VMG, SOG, TWA, escora y cabeceo en ceñida y en popa, más pérdida por virada y por trasluchada) y la tabla de medias.
- **Debrief IA** en cada pestaña, con los cuatro apartados y la categoría del diagnóstico.

### Añadidos al inventario

| Elemento | Estado | Notas |
|---|---|---|
| Descarga del debrief de equipo en PDF | Calculado | Existe en la referencia. **Propuesta: fuera de la v1** (decidir en la Fase 3) |
| Gráfico de la salida: TWD en el disparo, de −3 a +3 min | Estimado | |
| Offsets como balizas propias (Offset 1, Offset 2) con su tiempo de paso | Estimado | Rodeo de la flota tras la baliza de barlovento |
| Zona de baliza: entrada y salida por barco y baliza | Calculado | Base del «tiempo de maniobra» en balizas y puerta |
| Por cada corte de viento: confianza y origen (bisectriz de COG de la flota o arrastre del corte anterior) | Estimado | Útil para marcar los cortes poco fiables |
| Layline indicada como «lado + metros» (p. ej. «Derecha +72 m») y segundos navegados fuera de la layline | Estimado | |
| Dispersión (IQR) de la escora y del cabeceo | Directo | |
| Lado del campo por tramo (mediana de la distancia lateral al eje) | Estimado | Lo usa el debrief |

### Métodos de la referencia (según los nombres que aparecen en sus datos)

- **TWD**: bisectriz de los COG de la flota. Es el mismo método que ya usamos.
- **TWA**: |COG − TWD|, un «ángulo táctico GPS».
- **TWS**: ajuste a la polar de J/70 con SOG y TWA, **más una calibración manual**. Un administrador introduce el viento del comité (16 kn en el disparo). La estimación sin calibrar era **7,25 kn**, con un offset de +8,75 kn.
- **Corriente**: también la fija un administrador (0 kn en el ejemplo).
- **Laylines**: polar J/70 con TWD, TWS y corriente.
- **Presión local**: barcos a menos de 120 m, con una captura cada 15 s.
- **Barco fantasma**: una distancia de referencia por tramo. La eficiencia es (fantasma − navegada) / fantasma. Comprobado con el ejemplo: 3633 m frente a 3606 m → +0,8 %.
- **Hora de la señal**: `startTime` sin redondear, es decir, 1 s después del minuto. Nosotros truncamos al minuto, así que nuestros «+mm:ss» irán 1 s por delante de los suyos.

### Consecuencias para el diseño

1. **La TWS absoluta no se puede estimar bien sin una referencia.** Ni la polar sin calibrar (7,25 kn) ni el modelo ERA5 de Open-Meteo (8,3 kn a las 14:00 UTC, con 323° que sí cuadran en dirección) se acercan a los 16 kn del comité. Propuesta: un campo **«viento de referencia»** por prueba (TWS en el disparo, del comité o del propio equipo). Sin él, la TWS se muestra **relativa** (Δ respecto a la media) y marcada «sin calibrar». Esto afecta a las laylines, a la presión y a las tendencias por intensidad de viento.
2. **La IA de la referencia comete errores de unidades.** Llama «segundos» a pérdidas que en la tabla están en metros (p. ej. 17,8 m → «17.84s»). En nuestra app, el texto de la IA se **valida automáticamente**: cada número que cite tiene que existir en las métricas, con su unidad. Si no, se regenera o se avisa.
3. **Numeración de pruebas**: la referencia usa el `raceNumber` del documento del comité, no la numeración cronológica. En la validación de la Fase 5 hay que emparejar por la hora de la señal.
