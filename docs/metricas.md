# Métricas de FastTack: fórmulas y validación

> Motor versión **0.4.1** (Fase 4 · hito 5). Código en `fasttack/motor/`. Todas las cifras salen del cálculo; la IA (hito 6) solo las redacta.
> Naturaleza de cada cifra: **directa** (viene de RaceSense), **calculada** (geometría y tiempos exactos) o **estimada** (depende del viento reconstruido o de una baliza estimada). La interfaz marca lo estimado.

## Convenciones

- **Coordenadas**: proyección equirrectangular local en metros (x = este, y = norte), centrada en la flota. Error < 0,1 % en un campo de pocos km.
- **Tiempos**: epoch ms (UTC). La **señal** es `startTime` del comité truncado al minuto (el registro va ~1 s tarde). Track to Tactics (TtT) usa el valor sin truncar: sus «+mm:ss» van 1 s por detrás de los nuestros.
- **Ángulos**: rumbos 0–360° desde el norte; diferencias normalizadas a (−180°, 180°]. TWD = de dónde viene el viento.
- **Escora**: `roll`, + = a estribor. **Rumbo de proa**: tal cual el dispositivo (magnético en la mayoría); no interviene en ninguna métrica, que usan el COG.
- **Lados**: izquierda/derecha del campo **mirando a barlovento**. La puerta, en cambio, se nombra **mirando a sotavento** (como la ve el barco que llega y como la nombra RaceSense con `gateLeft`/`gateRight`).
- **Huecos de telemetría**: nunca se rellenan. El COG solo existe entre muestras a ≤ 5 s.

## Calidad de los datos (cobertura)

`cobertura(tramo)` = fracción del tiempo del tramo cubierta por muestras separadas ≤ 15 s.

| Calidad | Cobertura | Qué se muestra |
|---|---|---|
| alta | ≥ 70 % | todo |
| media | 45–70 % | todo |
| baja | 25–45 % | medias (SOG, VMG, TWA, escora, cabeceo) marcadas como poco representativas; sin distancia navegada |
| insuficiente | < 25 % | «datos insuficientes» |

La **distancia navegada** exige cobertura ≥ 50 %, porque cruza los huecos en línea recta y los subestima. La **pérdida en una maniobra** exige datos densos (ningún hueco > 4 s en −30…+30 s): si no, la maniobra se cuenta pero sin pérdida.

## Recorrido y pasos por baliza (calculado; balizas sin Atlas: estimado)

1. **Eje inicial**: perpendicular a la línea de salida, hacia donde está la flota a +3 min.
2. **Rodeos**: por barco, extremos alternos de su avance a lo largo del eje con histéresis `max(150 m, 20 % de la ceñida)`. Máximos = barlovento; mínimos = sotavento.
3. **Vueltas**: moda del nº de rodeos de barlovento de los barcos que llegan. La llegada es «a barlovento» si su línea está a más del 60 % de la ceñida.
4. **Posición de cada baliza**: el Atlas con esa función (`markPort`, `gateLeft/Right`) si está a < 250 m de la mediana de los rodeos de la flota; si no, esa mediana (**estimada**).
5. **Offset**: tras la baliza de barlovento, cada barco navega de través; el rodeo del offset es la última muestra antes de bajar 40 m respecto a la baliza. Si la mediana de esos puntos está a más de 40 m en lateral, hay offset (**estimado**).
6. **Paso** de un barco = máxima aproximación a la baliza (a la de la puerta que eligió) en ±4 min de su rodeo. **Entrada/salida de la zona** = primera/última muestra a menos de 3 esloras (20,8 m).
7. **Elección de puerta**: la baliza de la puerta por la que pasó.
8. **Tramos**: salida → B1 = Ceñida 1; offset (o B1) → puerta = Popa 1; puerta → B2 = Ceñida 2; …; el rodeo baliza → offset no es tramo. Un barco cuyo parcial esté fuera de 0,5–2,5 × el parcial mediano no cuenta en ese tramo (rodeo mal detectado por un hueco) y se avisa.

## Viento (estimado)

- **TWD por corte**: el tramo se divide en 10 cortes del tiempo del líder. En cada corte se reúnen los COG estables (cambio < 8° entre muestras; SOG > 2 kn en ceñida, > 3 kn en popa; excluidos 20 s alrededor de cada rodeo) de los barcos que navegan ese tramo. Se separan en dos grupos (2-medias circular, 6 iteraciones) y **TWD = bisectriz** (+180° en popa). Válido si cada grupo tiene ≥ 8 muestras, hay ≥ 3 barcos y la separación es de 50–130° (ceñida) o 25–150° (popa). Si no, el corte hereda la TWD anterior («arrastre», confianza 0,2). En los tramos después del primero, un corte que se aparte > 30° de la TWD con la que acabó el tramo anterior se descarta.
- **Confianza** = 0,5 × equilibrio entre grupos + 0,5 × min(1, barcos/10).
- **TWA de la flota** = media separación entre los dos grupos (ceñida) o 180° − media separación (popa). Es también el **TWA objetivo** (no hay polar fiable).
- **TWA de un barco** = |COG − TWD(t)|: ángulo táctico GPS (incluye abatimiento y corriente).
- **Presión** = SOG mediano de la flota en el corte. **TWS** solo si hay **viento de referencia** (TWS en el disparo que introduce el equipo): en la primera ceñida TWS ∝ SOG mediano, anclado al primer corte; cada tramo siguiente se ancla al último corte del anterior y varía con su propio SOG. Sin referencia, la presión es relativa y la TWS se muestra «sin calibrar».
- **Fases de rolada**: los cortes se agrupan por tendencia; una fase con cambio total < 3° es ESTABLE; si no, PROGRESIVA DERECHA (TWD aumenta) o IZQUIERDA. **Fases de presión**: igual con el umbral de 0,5 kn (TWS calibrada) o 0,2 kn de SOG mediano. **Quién la recibió primero**: en cada corte se parten las muestras por la mediana de su posición lateral respecto al eje del tramo (mirando a barlovento) y, en cada mitad con ≥ 10 muestras, se calculan el SOG mediano y la TWD por bisectriz (≥ 5 muestras por grupo). En el primer corte de una fase no estable se compara cuánto se ha movido cada lado en el sentido de la fase: el que más se ha movido la recibió primero; si la diferencia es < 30 % o faltan datos, «toda la flota».
- **Puerta favorecida**: con la TWD del último corte de la popa que acaba en la puerta y la posición de las dos balizas en el rodeo mediano, la favorecida es la que queda más a barlovento (se navega menos en la popa y menos en la ceñida siguiente); **ventaja** = diferencia a lo largo del viento, en metros. Nombre izquierda/derecha mirando a sotavento, como RaceSense.

## Métricas por barco y tramo

| Métrica | Naturaleza | Fórmula |
|---|---|---|
| Parcial | calculada | paso por la baliza final − paso por la inicial (salida: la señal) |
| Posición, gap | calculada | orden y diferencia de tiempo en el paso por la baliza final |
| SOG | directa | media ponderada por tiempo (cada muestra pesa su intervalo, máx. 5 s) |
| VMG | estimada | media de SOG · cos(COG − TWD(t)) (en popa, respecto a TWD + 180°) |
| TWA | estimada | media de \|COG − TWD(t)\| |
| Distancia navegada | calculada | suma de los segmentos entre muestras (cobertura ≥ 50 %) |
| Maniobras | estimada | cambios del lado del viento (COG respecto a TWD) mantenidos ≥ 15 s; las pegadas (< 20 s) a un rodeo no cuentan, salvo al inicio de la ceñida desde la salida |
| Pérdida en maniobra (m) | estimada | VMG de referencia = media de −30…−10 s y de +20…+30 s; pérdida = referencia × 30 s − avance real entre −10 y +20 s (≥ 0) |
| Layline | estimada | desde la última maniobra antes de la baliza (o el inicio del tramo), exceso lateral más allá de la recta que sale de la baliza con el TWA de la flota, medido en perpendicular a esa recta. Lado del campo y segundos navegados fuera de la layline |
| Escora, cabeceo | directa | mediana de \|roll − desviación del sensor\| y de pitch; IQR. **Desviación del sensor** = media de la escora mediana en amura babor y en amura estribor (en ceñida); 0 si faltan datos de alguna |
| Modo | estimada | frente a la mediana de la flota en el tramo. Ceñida: TWA < med − 1,5° y SOG < med → ALTURA; TWA > med + 1,5° y SOG > med → VELOCIDAD; si no, VMG. Popa: TWA > med + 3° y SOG < med → PROFUNDO; TWA < med − 3° y SOG > med → VELOCIDAD |
| Barco fantasma | estimada | recorre el tramo con el TWA de la flota y siempre en la amura favorecida: en cada corte avanza largo/10 a lo largo del eje y navega (largo/10) / cos(α − \|δ\|), con δ = TWD del corte − rumbo del eje (en popa, con TWD + 180°) |
| Eficiencia de roladas | estimada | (fantasma − distancia navegada) / fantasma |

## Salida

| Métrica | Naturaleza | Fórmula |
|---|---|---|
| Posición en la línea | calculada | proyección del barco sobre comité→pin en la señal (0 % comité, 100 % pin) |
| Margen | calculada | distancia a la línea en la señal; negativo = por detrás («corto»), positivo = sobre la línea |
| SOG en el disparo | directa | interpolada en la señal |
| Cruce GPS | calculada | primer paso del lado de salida al del recorrido desde 30 s antes de la señal (s tras la señal) |
| VMG 0–90 s | estimada | VMG media en los 90 s tras la señal (si hay ≥ 60 % de datos) |
| +60 / +180 s | estimada | orden y distancia al primero por el avance hacia la baliza 1 a lo largo del eje, entre los barcos que salen (a < 300 m de la línea en la señal o que la cruzan) |
| 1.ª virada | estimada | primera maniobra de la ceñida 1 |
| Baliza 1 | calculada | posición y gap en su paso |
| OCS | directa | lista del comité (`ocs` − exonerados − `clearedOcs`); «sobre la línea (GPS)» si el margen es positivo |
| Sesgo de la línea | estimada | extremo más a barlovento según la TWD en el disparo; grados = asin(ventaja / largo de la línea); metros = ventaja a barlovento |

## Capas del mapa y valores instantáneos (estimado)

- **Cada barco en su tramo**: los valores instantáneos (VMG, TWA) se calculan con el tramo que navega cada barco según sus propios pasos por baliza, no el del líder ni el de la pestaña: mientras unos ya van de popa, otros siguen en la ceñida o en el offset. Entre la baliza y el offset (rodeo) no hay VMG. Las tablas por tramo y las medias ya usaban los tiempos de entrada y salida de cada barco.
- **Fases de rolada y presión**: contiguas; cada cambio se sitúa entre los centros de los cortes (corte k = k·10 + 5 %), la primera fase desde el 0 % y la última hasta el 100 %.

- **Presión instantánea**: mancha azul alrededor de cada barco del tramo cuyo SOG supera en > 2 % la mediana de la flota en ese instante (más intensa cuanto más la supera); un anillo marca los barcos cuyo SOG ha subido > 6 % de la mediana en los últimos 30 s. Es un indicador de presión, no una medida del viento: la SOG también depende del rumbo y del mar.
- **Presión izquierda–derecha** (panel): SOG mediano de los barcos a la izquierda menos el de los barcos a la derecha de la mediana lateral (mirando a barlovento). «Equilibrada» si la diferencia es < 3 % de la mediana.
- **TWD instantánea**: tinte del campo según la TWD del instante frente a la media del tramo (azul = rolada a la izquierda, rojo = a la derecha; saturado a ±10°).
- **Laylines** (siempre, en el tramo en curso): rectas desde la baliza final del tramo con el TWA de la flota y la TWD del instante.
- **Rol**: colorea la traza según la rolada del momento a favor (azul) o en contra (rojo) de la amura en que navega el barco. **SOG**: colorea la traza con una rampa azul entre el p5 y el p95 de la ventana visible.
- **Corriente**: no disponible (se estimará más adelante).

## Gráficos

- **Evolución del viento** (pestañas de tramo): TWD y presión (o TWS calibrada) en los 10 cortes, en dos gráficos con un eje cada uno.
- **Rendimiento**: VMG, SOG, TWA, escora y cabeceo en ceñida o en popa frente al tiempo desde la señal (medias de 5 s en tenue y mediana móvil de 60 s destacada; solo los tramos de ese tipo según los pasos por baliza de cada barco, sin los 20 s junto a cada rodeo) y pérdida de cada virada o trasluchada como puntos. Máximo 15 barcos.

## Rendimiento (toda la prueba)

Medias de VMG, SOG, TWA, escora y cabeceo en ceñida y en popa, ponderadas por el parcial de cada tramo con datos; pérdida media por virada y por trasluchada (solo maniobras con pérdida medida).

## Validación con Cascais Vela · prueba 9 (frente a Track to Tactics)

Datos: 34 barcos, M1 y puerta con Atlas. Comparación de todos los barcos y todos los tramos con su informe de ejemplo (`scratchpad`, no versionado).

| Qué | Resultado |
|---|---|
| Pasos por M1, puerta, M2 y llegada | diferencia mediana **0,0 s**, máx. 2 s (34/34 barcos) |
| Elección de puerta | **34/34** iguales |
| Parciales de popa (desde el offset) | 504 s frente a 493 s y 517 s frente a 525 s (ESP 1170); ellos acaban en la entrada a la zona |
| SOG por tramo | diferencia mediana −0,01 kn (ceñida), correlación 0,83–0,91 |
| Distancia navegada | correlación 0,93–0,97; nuestra ~+33 m en ceñida (ellos remuestrean cada 3 s e interpolan) |
| Escora | diferencia mediana 0,0–0,25°, correlación 0,89–0,94 |
| Pérdida en virada | mediana 3,3 m frente a 2,9 m (C1) y 2,9 m frente a 3,2 m (C2) |
| Pérdida en trasluchada | menor que la suya (0–9 m frente a 15–19 m) con planeo; nuestras ventanas exigen datos densos (pocas medidas) |
| Salida (ESP 1170) | línea −1,4 % frente a −1,1 %; margen −6,0 m frente a −5,2 m; SOG 3,8 frente a 4,1 kn; cruce +6,0 s frente a +5,7 s (con la misma señal); B1 4.º +9 s igual |
| **TWD** | la nuestra, 5–6° a la izquierda de la suya en ceñida (312,8° frente a 317,7°). Nuestra bisectriz es exacta respecto a los datos: las amuras navegan a 271° y 353,5° (bisectriz 312,25°). La suya deja la flota con TWA muy asimétricos (36° y 47°); probablemente corrige los COG con su estimación de corriente |
| **VMG** | la nuestra explica el resultado: correlación con el parcial del tramo **−0,92 / −0,86 / −0,91** (C1, C2, P2) frente a **−0,14 / −0,15 / −0,33** la suya |
| Maniobras | contamos ~1,5 menos por ceñida: las que caen dentro de un hueco de datos no se pueden ver (ellos interpolan la traza) |
| Layline | mismo lado; metros distintos (21,6 frente a 71,6 m en C1 de ESP 1170): su layline usa polar, corriente y su TWD |
| +60/+180 s | definiciones distintas: la suya parece la distancia a la baliza 1 (1.603 m), la nuestra la distancia al primero a lo largo del eje |

## Pruebas del Mundial de J/70 2026

Las 10 pruebas se analizan (2–8 s cada una): 2 vueltas, puerta con Atlas, balizas de barlovento y offsets estimados (en las pruebas 7 y 8 M1 sí transmite). La telemetría del Mundial es mucho más pobre: en algunos tramos más del 60 % del tiempo está en huecos de más de 30 s, y muchos barcos quedan con calidad «baja». La prueba 4 (reconstruida) es la peor: pocos barcos con pasos fiables y viento sin datos en dos tramos. El motor la marca como **recorrido dudoso** (ver abajo): sus llegadas cuentan en la general, sus métricas por tramo no entran en el resumen.

### Recorrido dudoso

Si el parcial mediano de algún tramo queda fuera de 0,4–2,5 veces la duración mediana de la prueba repartida entre sus tramos, las balizas estimadas están mal situadas: el análisis lo avisa y el resumen del campeonato deja fuera sus métricas. En el Mundial solo lo activa la prueba 4 (parciales de 0,59 / 0,18 / 0,19 / 3,39 veces lo esperado; en las demás, entre 0,54 y 1,59).

## Resumen del campeonato

- **General calculada** (puntuación baja, RRS apéndice A), sin penalizaciones ni decisiones del jurado. Puesto en la prueba = orden entre los que llegan, quitando los OCS del comité si su lista es fiable (en las pruebas reconstruidas no lo es). OCS y sin llegada (DNF/DNC, no se distinguen) = inscritos + 1; **inscritos** = barcos con alguna llegada (RaceSense lista también dispositivos de prueba). Descartes configurables: por defecto 1 a partir de 4 pruebas. Empates: A8.1 y A8.2.
- **Medias del campeonato**: medias de las pruebas con métricas, ponderadas por la cobertura de cada barco en cada prueba. **Mediana de la flota** por prueba y **top 15**: solo barcos con cobertura ≥ 50 %.
- **Salidas acumuladas**: solo salidas con datos del barco en el disparo. **Layline OK** = tramos que llegan a la baliza sin sobrepasar. **Puerta favorecida**: solo puertas con ventaja ≥ 5 m.
- **Según la intensidad del viento**: agrupa por el viento de referencia que introduce el equipo (< 10, 10–15, > 15 kn).

### Validación de la general con la clasificación oficial del Mundial

Comparada con los resultados oficiales publicados por el club organizador (100 barcos, 10 pruebas, 1 descarte):

| Prueba | Origen de las llegadas | Error medio de puesto (barcos que terminan en ambas) | Terminan y no detectamos |
|---|---|---|---|
| 1, 2, 5, 6, 9, 10 | RaceSense (oficial) | 0,3–1,8 | 0–2 |
| 3 | reconstruida | 1,4 | 3 |
| 4 | reconstruida | 0,6 | 1 |
| 7 | reconstruida | 0,4 | 1 |
| 8 | reconstruida | 0,9 | 1 |

- **General**: 32 barcos en el puesto exacto, 83 de 100 a ±3 puestos, error medio 2,1. ESP 1214: 25.º con 264 puntos (oficial: 23.º con 259); puestos por prueba 40, 59, 16, 34, 37, 8, (61), 38, 14, 18 frente a 40, 56, 16, 34, 37, 8, (62), 37, 14, 17.
- Las diferencias que quedan son casi todas decisiones del jurado (DSQ, DNS, PRP, RDG…), que no están en los datos y desplazan un puesto al resto de la flota.
- **Mejora de la detección de llegadas** (ingesta versión 2): un cruce de la línea se acepta aunque haya un hueco de datos de hasta 90 s sobre ella, con la hora interpolada en el segmento. Antes se exigían muestras a ≤ 10 s y, con la cobertura de RaceSense, muchos barcos que terminaron quedaban sin llegada: en la prueba 4 el error medio pasó de 7,8 a 0,6 puestos (de 12 barcos sin detectar a 1) y la general de 75 a 83 barcos a ±3.
