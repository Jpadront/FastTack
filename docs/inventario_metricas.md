# Inventario de métricas

> Estado: **Fase 2 — BORRADOR** (25-09-2026). La comparación con Track to Tactics está **pendiente**.
> Su panel y su API (`/dashboard`, `/api/catalog`) exigen sesión (`401 «Log in to access this private area»`), y el entorno de desarrollo no tiene la sesión de Chrome del usuario. Por ahora el inventario sale de la especificación del proyecto y se contrasta con lo que dan los datos de RaceSense (`docs/fuente_datos.md`). Lo que falta confirmar en el informe de ejemplo está en la última sección.

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
| TWS y Δ con la media | Estimado | Inversión de la polar J/70 con el SOG de la flota, contrastada con ERA5 | La incertidumbre más alta de todas; se indica el rango |
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

## Pendiente de confirmar en el informe de ejemplo de Track to Tactics

Sin acceso a la sesión, falta confirmar lo siguiente en el informe «Cascais Vela · Race 9» (J/70, ESP 1170):

1. Que la lista de pestañas y de columnas de las tablas coincide con este inventario, y si hay métricas que no están aquí.
2. Las definiciones que muestre la herramienta (tooltips o notas de metodología): VMG, pérdida en maniobra, modo, barco fantasma, fases de rolada.
3. Las unidades y el redondeo de cada columna.
4. **Qué prueba es «Race 9».** Probablemente sea este mismo Mundial: ESP 1170 «YUPI» está en nuestra flota. Pero «Race 9» puede ser la prueba 9 oficial (API 8, 12-09 12:15 UTC) o la regata 9 de la API (prueba 10 oficial, 12-09 14:05 UTC). El puesto y el tiempo de ESP 1170 en su informe lo aclaran: en la prueba 9 oficial (API 8) fue 18.º de 91 (1:27:11), y en la API 9 fue 7.º de 91 (1:20:15).
