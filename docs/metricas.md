# Métricas de FastTack: fórmulas y validación

> Motor versión **0.2.0** (Fase 4 · hito 2). Código en `fasttack/motor/`. Todas las cifras salen del cálculo; la IA (hito 6) solo las redacta.
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
- **Fases de rolada**: los cortes se agrupan por tendencia; una fase con cambio total < 3° es ESTABLE; si no, PROGRESIVA DERECHA (TWD aumenta) o IZQUIERDA. **Fases de presión**: igual con el umbral de 0,5 kn (TWS calibrada) o 0,2 kn de SOG mediano. «Quién la recibió primero» queda pendiente (necesita la presión local por barco, hito 4).

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

Las 10 pruebas se analizan (2–8 s cada una): 2 vueltas, puerta con Atlas, balizas de barlovento y offsets estimados (en las pruebas 7 y 8 M1 sí transmite). La telemetría del Mundial es mucho más pobre: en algunos tramos más del 60 % del tiempo está en huecos de más de 30 s, y muchos barcos quedan con calidad «baja». La prueba 4 (reconstruida) es la peor: pocos barcos con pasos fiables y viento sin datos en dos tramos.
