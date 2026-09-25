# Métricas de FastTack: fórmulas y validación

> Motor versión **0.4.2** (Fase 4 · hito 7). Código en `fasttack/motor/`. Todas las cifras salen del cálculo; la IA (hito 6) solo las redacta.
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
| Layline | estimada | desde la última maniobra antes de la baliza (o el inicio del tramo), exceso lateral más allá de la recta que sale de la baliza con el TWA de la flota, medido en perpendicular a esa recta. Lado del campo mirando hacia donde se navega (en ceñida, a barlovento; en popa, a sotavento, como Track to Tactics y las puertas) y segundos navegados fuera de la layline. No se calcula hacia la línea de llegada |
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

Motor **0.4.2** (hito 7). 34 barcos, M1 y puerta con Atlas. Comparación de todos los barcos y todos los tramos con su informe de ejemplo (en el `scratchpad` de desarrollo, no versionado). Sin viento de referencia (TWS sin calibrar).

| Qué | Resultado |
|---|---|
| Pasos por M1, puerta, M2 y llegada | diferencia mediana **1,0 s**, máx. 3,4 s (34/34 barcos). Offset 1 (estimado): mediana 5 s, máx. 8 s |
| Elección de puerta | **34/34** iguales |
| Puerta favorecida | la misma (**derecha**); ventaja 13,4 m frente a 23,6 m (depende de la TWD, ver abajo) |
| SOG por tramo | ceñidas −0,01 y −0,03 kn (correlación 0,89 y 0,83); popa 2 −0,36 kn (0,91). Popa 1 −0,93 kn (0,58): solo 8 barcos tienen ≥ 50 % de datos en ese tramo; ellos interpolan los huecos |
| Distancia navegada | correlación 0,93–0,97; la nuestra ~+33 m en ceñida (ellos remuestrean cada 3 s) |
| Escora | diferencia mediana 0,0–0,25°, correlación 0,86–0,94 |
| **TWD** | la nuestra, 4–6° a la izquierda en C1, P1 y C2 (−1° en P2). Nuestra bisectriz es exacta respecto a los COG; ellos estiman **corriente: 0,88 kn, 0,73 kn hacia sotavento** en el eje del recorrido, y corrigen con ella. Es la diferencia principal y explica también que toda la flota sobrepase laylines con nuestra TWD |
| **VMG** | la nuestra explica el resultado: correlación con el parcial **−0,92 / −0,68 / −0,86 / −0,86** (C1, P1, C2, P2) frente a **−0,14 / −0,52 / −0,15 / −0,39** la suya |
| Layline | **mismo lado 28/28** en los barcos que ambos marcan (en popa, lado mirando a sotavento, como ellos); sobrepasadas 21 frente a 23 (C1) y 17 frente a 22 (C2). No calculamos la layline a la línea de llegada (ellos marcan 8 en P2) |
| Fases de rolada | C1 estable en ambos. En popa y C2 difieren: su TWD corregida por corriente cambia la forma (p. ej. C2: ellos rolada izquierda 0–60 %, nosotros estable hasta el 85 % y luego izquierda). «Quién la recibió primero»: ellos «flota» en todas las fases; nosotros «flota» en las roladas |
| Fases de presión | no comparables sin viento de referencia: ellos usan TWS de su polar; nosotros, SOG mediano relativo (umbral 0,2 kn) |
| Pérdida en maniobras | la suya es la pérdida total del tramo; la nuestra suma solo las maniobras con datos densos (por eso 16–30 m menor). Por maniobra, las medianas coinciden (≈3 m por virada) |
| Maniobras | contamos ~1,5 menos por ceñida: las que caen dentro de un hueco de datos no se ven (ellos interpolan) |
| Salida (ESP 1170) | línea −1,4 % frente a −1,1 %; margen −6,0 m frente a −5,2 m; SOG 3,8 frente a 4,1 kn; cruce +6,0 s frente a +5,7 s; B1 4.º +9 s igual |
| +60/+180 s | definiciones distintas: la suya parece la distancia a la baliza 1; la nuestra, la distancia al primero a lo largo del eje |

**Conclusión**: pasos, puertas, velocidades, distancias, escora, salida y lado de las laylines coinciden con Track to Tactics. Las diferencias vienen de la **corriente** (ellos la estiman, nosotros no): afecta a TWD, TWA, VMG absoluta, fases de rolada y metros de layline. Estimar la corriente es la siguiente mejora del motor.

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


## Debrief con IA (texto)

- **Qué recibe la IA**: un JSON con las cifras del motor ya redondeadas como en la web (`fasttack/ia/hechos.py`). La unidad va en el nombre de cada campo (`_kn`, `_m`, `_s`, `_grados`, `_pct`) y las comparaciones con la flota vienen calculadas (`..._frente_a_la_mediana_kn`, `..._mediana_flota_...`, `..._top5_...`) para que la IA no haga cuentas.
- **Referencia: el top 5.** En una prueba, los 5 primeros de esa prueba; en el campeonato, los 5 primeros de la general (sin contar el barco analizado). Para cada tramo y cada media van la mediana del top 5 y la diferencia del barco con ella (`..._top5_...`, `..._frente_al_top5_...`), además de la mediana de la flota como contexto. Las conclusiones deben salir de las diferencias con el top 5.
- **Reglas** (`fasttack/ia/debrief.py`): solo cifras de los datos, con su unidad; lo estimado no se presenta como medido; los huecos de telemetría son un límite del análisis, no un fallo del barco; causas solo como hipótesis; formato fijo (prueba: resumen, salida, ceñidas, popas, maniobras/laylines/puertas, 3 claves; campeonato: balance, 3 puntos fuertes, 3 áreas de mejora, prioridades de entrenamiento).
- **Validación** (`fasttack/ia/validar.py`): cada número del texto, con su unidad, debe ser un redondeo (± media unidad de su último decimal) de una cifra de los datos con la misma unidad; los mm:ss se pasan a segundos. Se ignoran etiquetas (P3, Ceñida 2, top 10, velas), marcadores de lista y recuentos ≤ 3 sin unidad. Las cifras que no cuadran se resaltan; se vuelve a comprobar cada vez que se abre.
- **Caché**: el texto se guarda con la huella (SHA-1) de sus cifras; si las cifras cambian, se avisa de que conviene regenerarlo.
- **Prueba real** (Mundial, prueba 9 y campeonato, ESP 1214, Claude Code): 36 y 54 s; todas las cifras verificadas. Un texto pegado a mano con una VMG inventada (9,99 kn) queda marcado.
