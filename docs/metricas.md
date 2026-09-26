# Métricas de FastTack: fórmulas y validación

> Motor versión **0.6.6** (corriente, HDG corregido y escora óptima). Código en `fasttack/motor/`. Todas las cifras salen del cálculo; la IA (hito 6) solo las redacta.
> Naturaleza de cada cifra: **directa** (viene de RaceSense), **calculada** (geometría y tiempos exactos) o **estimada** (depende del viento reconstruido o de una baliza estimada). La interfaz marca lo estimado.

## Convenciones

- **Coordenadas**: proyección equirrectangular local en metros (x = este, y = norte), centrada en la flota. Error < 0,1 % en un campo de pocos km.
- **Tiempos**: epoch ms (UTC). La **señal** es `startTime` del comité truncado al minuto (el registro va ~1 s tarde). Track to Tactics (TtT) usa el valor sin truncar: sus «+mm:ss» van 1 s por detrás de los nuestros.
- **Ángulos**: rumbos 0–360° desde el norte; diferencias normalizadas a (−180°, 180°]. TWD = de dónde viene el viento.
- **Escora**: `roll`, + = a estribor. **Rumbo de proa**: tal cual el dispositivo (magnético en la mayoría); no interviene en ninguna métrica, que usan el COG.
- **Lados**: izquierda/derecha del campo **mirando a barlovento**. La puerta, en cambio, se nombra **mirando a sotavento** (como la ve el barco que llega y como la nombra RaceSense con `gateLeft`/`gateRight`).
- **Huecos de telemetría**: nunca se rellenan. El COG solo existe entre muestras a ≤ 5 s.

## Muestras congeladas

RaceSense repite a veces una muestra de un barco (misma posición, SOG y rumbo) durante minutos, mezclada con las reales: el barco parece saltar de un punto a otro y salen rumbos y VMG absurdos (p. ej. VMG 2,7 kn a TWA 104° en una popa a 12 kn). En el Mundial afectaba al 8–40 % de las muestras de 8 de 10 pruebas, y en Cascais Vela al 18–86 % de 5 de 9. Al leer la telemetría se quita toda muestra que repite posición, SOG y rumbo de otra anterior más de 5 s después con el barco en movimiento (> 0,5 kn); las balizas fondeadas no se tocan. La cobertura baja en consecuencia: ahora es real. Con los datos limpios, la general calculada del Mundial queda con 31 barcos en el puesto exacto y 79 de 100 a ±3 (antes 32 y 83: la prueba 3 empeora de 1,4 a 2,2 puestos de error medio y la 8 mejora de 0,9 a 0,4); la validación con Track to Tactics no cambia.

**Entrenamientos**: si el comité marca como OCS a más del 25 % de la flota, la prueba no se reconstruye (entrenamiento o anulada; el entrenamiento del Mundial tuvo 36 OCS). Se puede marcar en «Cuenta» si fue válida.

## Calidad de los datos (cobertura)

`cobertura(tramo)` = fracción del tiempo del tramo cubierta por muestras separadas ≤ 15 s.

| Calidad | Cobertura | Qué se muestra |
|---|---|---|
| alta | ≥ 70 % | todo |
| media | 45–70 % | todo |
| baja | 25–45 % | medias (SOG, VMG, TWA, escora, cabeceo) marcadas como poco representativas; sin distancia navegada |
| insuficiente | < 25 % | «datos insuficientes» |

La **distancia navegada** exige cobertura ≥ 50 %, porque cruza los huecos en línea recta y los subestima. La **pérdida en una maniobra** exige datos densos (ningún hueco > 6 s desde 25 s antes hasta que el barco está acelerado): si no, la maniobra se cuenta pero sin pérdida.

## Recorrido y pasos por baliza (calculado; balizas sin Atlas: estimado)

1. **Eje inicial**: perpendicular a la línea de salida, hacia donde está la flota a +3 min.
2. **Rodeos**: por barco, extremos alternos de su avance a lo largo del eje con histéresis `max(150 m, 20 % de la ceñida)`. Máximos = barlovento; mínimos = sotavento.
3. **Vueltas**: moda del nº de rodeos de barlovento de los barcos que llegan. La llegada es «a barlovento» si su línea está a más del 60 % de la ceñida.
4. **Posición de cada baliza**: el Atlas con esa función (`markPort`, `gateLeft/Right`) si está a < 250 m de la mediana de los rodeos de la flota; si no, esa mediana (**estimada**).
5. **Offset**: tras la baliza de barlovento, cada barco navega de través; el rodeo del offset es la última muestra antes de bajar 40 m respecto a la baliza. Si la mediana de esos puntos está a más de 40 m en lateral, hay offset (**estimado**).
6. **Paso** de un barco = máxima aproximación a la baliza (a la de la puerta que eligió) en ±4 min de su rodeo. **Entrada/salida de la zona** = primera/última muestra a menos de 3 esloras (20,8 m).
7. **Elección de puerta**: la baliza de la puerta por la que pasó.
8. **Tramos**: salida → B1 = Ceñida 1; offset (o B1) → puerta = Popa 1; puerta → B2 = Ceñida 2; …; el rodeo baliza → offset no es tramo. Un barco cuyo parcial esté fuera de 0,5–2,5 × el parcial mediano no cuenta en ese tramo (rodeo mal detectado por un hueco) y se avisa.


**Puerta de sotavento sin Atlas (o con una sola boya con Atlas)**: los puntos de rodeo de la flota se separan en lateral (respecto al eje) por el corte que más distingue dos grupos (Otsu en 1D, cada grupo ≥ 20 % de los rodeos). Si los dos grupos están a ≥ 4 esloras y a más del doble de su propia dispersión, es una puerta: cada boya es su Atlas si hay uno a menos de 3 esloras + 30 m de la mediana del grupo y, si no, esa mediana (estimada). Si no hay dos grupos claros, es una sola baliza. Mundial de Snipe 2026, pruebas 4–6: puerta con una boya con Atlas y la otra estimada, a unos 45 m (antes salía una sola baliza estimada y los barcos de la otra boya «giraban por encima»).

**Offset**: forma parte del rodeo de barlovento; no es un punto aparte en la web. La popa empieza en él; el debrief lo menciona solo si el tiempo de la baliza al offset es claramente distinto del del top 5.
## Viento (estimado)

- **TWD por corte**: el tramo se divide en 10 cortes del tiempo del líder. En cada corte se reúnen los COG estables (cambio < 8° entre muestras; SOG > 2 kn en ceñida, > 3 kn en popa; excluidos 20 s alrededor de cada rodeo) de los barcos que navegan ese tramo. Se separan en dos grupos (2-medias circular, 6 iteraciones) y **TWD = bisectriz** (+180° en popa). Válido si cada grupo tiene ≥ 8 muestras, hay ≥ 3 barcos y la separación es de 50–130° (ceñida) o 25–150° (popa). Si no, el corte hereda la TWD anterior («arrastre», confianza 0,2). En los tramos después del primero, un corte que se aparte > 30° de la TWD con la que acabó el tramo anterior se descarta.
- **Confianza** = 0,5 × equilibrio entre grupos + 0,5 × min(1, barcos/10).
- **TWA de la flota** = media separación entre los dos grupos (ceñida) o 180° − media separación (popa). Es también el **TWA objetivo** (no hay polar fiable).
- **TWA de un barco** = |COG − TWD(t)|: ángulo táctico GPS (incluye abatimiento y corriente).
- **Presión** = SOG mediano de la flota en el corte. **TWS** solo si hay **viento de referencia** (TWS en el disparo que introduce el equipo): en la primera ceñida TWS ∝ SOG mediano, anclado al primer corte; cada tramo siguiente se ancla al último corte del anterior y varía con su propio SOG. Sin referencia, la presión es relativa y la TWS se muestra «sin calibrar».
- **Fases de rolada**: los cortes se agrupan por tendencia; una fase con cambio total < 3° es ESTABLE; si no, PROGRESIVA DERECHA (TWD aumenta) o IZQUIERDA. **Fases de presión**: igual con el umbral de 0,5 kn (TWS calibrada) o 0,2 kn de SOG mediano. **Quién la recibió primero**: en cada corte se parten las muestras por la mediana de su posición lateral respecto al eje del tramo (mirando a barlovento) y, en cada mitad con ≥ 10 muestras, se calculan el SOG mediano y la TWD por bisectriz (≥ 5 muestras por grupo). En el primer corte de una fase no estable se compara cuánto se ha movido cada lado en el sentido de la fase: el que más se ha movido la recibió primero; si la diferencia es < 30 % o faltan datos, «toda la flota».
- **Puerta favorecida**: con la TWD del último corte de la popa que acaba en la puerta y la posición de las dos balizas en el rodeo mediano, la favorecida es la que queda más a barlovento (se navega menos en la popa y menos en la ceñida siguiente); **ventaja** = diferencia a lo largo del viento, en metros. Nombre izquierda/derecha mirando a sotavento, como RaceSense.

### Viento con pocos barcos (método de «amuras»)

Con menos de 3 barcos en un tramo (sesiones con archivos .vkx), un corte casi nunca tiene las dos amuras a la vez y la bisectriz no sale. Entonces:
1. Con todas las muestras estables del tramo se separan los dos rumbos de las amuras (c1, c2) y su medio ángulo (TWA del barco en el tramo, que se supone constante).
2. En cada corte, cada muestra da una bisectriz: COG + medio ángulo en una amura, COG − medio ángulo en la otra (se descartan las que están a más de 25° de su amura: maniobras). La TWD del corte es su mediana circular (+180° en popa).
3. Rumbos de las amuras en el corte (para laylines): c1 y c2 girados lo que haya rolado la TWD.

Una rolada se ve en la amura en la que se navega; si el barco cambia de modo (orzar para ganar altura, arribar para velocidad) se confunde con una rolada. Confianza: la mitad del equilibrio entre amuras (≤ 0,5). Con un barco sintético a TWD fija, el error es < 3°.

## Sesiones con archivos .vkx: llegada estimada

Sin línea de llegada, la de cada barco se estima con su propia traza:
1. **Fin de la regata del barco**: la SOG (mediana móvil de 90 s, rejilla de 5 s) cae por debajo del 55 % de la mediana de los 10 primeros minutos; si no, la ventana acaba 6 min antes de la señal siguiente.
2. **Último tramo**: desde el último extremo del avance a lo largo del eje (rodeo de barlovento o sotavento, como en el recorrido).
3. **Llegada**: el punto más avanzado de ese tramo (el más a sotavento si es una popa), sin pasar más de 250 m del nivel de la baliza anterior en ese sentido.
4. **Llegada «limpia»**: el barco se para en los 5 min siguientes. Si no (vuelve a puerto navegando), la llegada es el paso más cercano, en el último tramo, al punto mediano de las llegadas limpias del mismo día (a menos de 300 m); si no lo hay, se marca como poco fiable.
5. La línea de llegada de la prueba es el punto mediano de las llegadas de sus barcos (para saber si se llega a barlovento o a sotavento).

Con los archivos de ESP 1214 del 9 y el 10 de mayo de 2025 (Barcelona, 8 pruebas barlovento-sotavento a 2 vueltas): 5 llegadas limpias y 3 por referencia (a 66–122 m del punto del día); pruebas de 34–42 min.

## Corriente (estimada)

Sin corredera, la corriente se estima con toda la flota (`fasttack/motor/corriente.py`), una por prueba y otra por vuelta (la marea cambia durante la prueba):

- **Método principal (brújula).** Para cada barco, tramo y amura, COG − HDG = δ + abatimiento + (c · n)/SOG, donde δ es el desvío fijo de la brújula de ese barco (montaje, magnético o verdadero), el abatimiento solo existe en ceñida (con signo opuesto en cada amura) y n es el vector unitario 90° a la derecha del rumbo. Con la flota navegando en cuatro rumbos (dos amuras en ceñida y dos en popa) se resuelven por mínimos cuadrados la corriente c, el abatimiento y un δ por barco (suma cero). Se descartan las brújulas con desvío > 15° y las observaciones anómalas (> 3 desviaciones robustas) y se vuelve a resolver. Mínimo 8 barcos con ceñida y popa.
- **Comprobación independiente (velocidades).** En ceñida un barco va igual de rápido por el agua en las dos amuras: la media de las velocidades sobre el fondo de las dos amuras, fuera del eje, es la corriente transversal. **Confianza**: alta si las dos componentes transversales difieren ≤ 0,15 kn; media si ≤ 0,3 kn con el mismo signo; baja en otro caso.
- **Uso.** Las **laylines sobre el fondo** salen de los rumbos reales de la flota en cada amura (centros de los dos grupos de COG del corte), que ya incluyen la corriente; antes eran simétricas (TWD ± TWA). TWD y TWA siguen siendo **sobre el fondo** (la bisectriz de los COG): con la corriente transversal típica (0,1–0,3 kn) el sesgo es de 1–3°.
- **Validación.** Flota sintética con corriente, abatimiento y desvíos conocidos (tests): se recupera con ±0,12 kn y se descarta la brújula estropeada. Mundial (8 pruebas analizadas): 0,09–0,35 kn con confianza alta en 6; 0,66 kn (media) y 0,84 kn (baja) en las pruebas 6 y 5. En las 7 pruebas comparadas, los dos métodos dan el mismo signo de corriente transversal. Cascais Vela P9: 0,26 kn hacia 79° (0,15 kn hacia sotavento y 0,21 kn hacia la derecha, confianza alta); Track to Tactics da 0,88 kn hacia 117° (0,73 y 0,48 kn): mismo sentido en las dos componentes, pero el triple de intensidad. Su método se llama «admin-reference», lo que sugiere una referencia externa (modelo de marea) y no la telemetría; nuestros dos métodos independientes coinciden en valores menores.

## Rumbo de proa (HDG) corregido

El HDG de cada Atlas puede estar en magnético o en verdadero y tener un error de montaje. El ajuste de la corriente estima un **desvío por barco** (COG − HDG que no explican la corriente ni el abatimiento). La media de la flota se fija en la **declinación magnética** del campo de regatas y la fecha (modelo magnético mundial WMM 2025, p. ej. −1,0° en Cascais en septiembre de 2026), porque la mayoría de los Atlas van en magnético. Para las brújulas descartadas (desvío > 15°), el desvío se calcula después con la corriente ya fija. **HDG corregido = HDG del dispositivo + desvío del barco** (rumbo verdadero); sin desvío estimado, solo se suma la declinación. En el Mundial, 15 de 96 barcos tienen desvíos > 5° (máx. 79°). La declinación también mejora la corriente transversal (antes se suponía desvío medio 0).

## Escora óptima en ceñida (estimada)

Para cada ceñida (`fasttack/motor/escora.py`):

1. **Segmentos de 30 s** por barco, fuera de los rodeos (20 s) y de las maniobras (30 s antes, 15 s después), con ≥ 70 % de datos y rumbo estable. En cada uno: escora = mediana de |roll − desviación del sensor|; VMG media.
2. **VMG y SOG relativas a los vecinos**: VMG (y SOG) del segmento / mediana de las de los segmentos de otros barcos **en la misma amura** a < 300 m y ±30 s (≥ 3 barcos). Misma amura porque una rolada local favorece a una amura y perjudica a la otra. Los vecinos tienen el mismo viento: se quitan la presión y las roladas, también las locales. Comparar con toda la flota daba un óptimo falso, porque quien pilla una racha escora más y va más rápido aunque la escora no sea la causa.
3. **Franjas de 2°** (≥ 30 segmentos y ≥ 8 barcos). La mejor franja es la de mayor VMG relativa menos su error típico (una franja con pocos datos no gana por ruido). **Rango óptimo**: franjas contiguas a la mejor que pierden < 1 %. Una franja es **claramente peor** si pierde ≥ 1 % y más de 2 errores típicos; se da la pérdida de la más cercana por debajo y por encima del rango.
4. **VMG frente a SOG**: si por encima del rango la SOG sigue subiendo (≥ 1,5 puntos más que la VMG) pero la VMG baja, con más escora se va más rápido pero más abierto o con más abatimiento («sobreescora»); si bajan las dos, falta potencia. Ejemplo: Mundial P1, C1, a 20–22°: SOG 102,4 %, VMG 96,7 %.
5. **Concluyente** si alguna franja es claramente peor; si no, «la escora no marca diferencias» en ese tramo. Por barco: % del tiempo dentro del rango (solo si es concluyente).

**Campeonato** (Resumen): se juntan las franjas de todas las ceñidas (cada una ya relativa a sus vecinos), con media ponderada por segmentos y error típico combinado, y se aplica la misma regla. Si hay viento de referencia, también por intensidad (< 10, 10–15, > 15 kn; ≥ 2 ceñidas). Por barco: cuántas de sus ceñidas tuvieron la escora mediana dentro del rango. Mundial (18 ceñidas, 13.658 segmentos de 30 s; según el equipo, casi todas con 20–25 kn): mejor franja 16–18°, rango 14–20°, −1,2 % a 12–14° y −6,6 % a 8–10°; ESP 1214, 16 de 17 ceñidas en el rango (mediana 16,5°); top 5, mediana 15°.

Con estos datos la relación es una **meseta**, no un pico (±1 % entre 12° y 20°): por eso se da un rango y no un valor único. Lo más claro y repetido es la **pérdida por escora baja**: por debajo de 10–14°, entre −2 % y −10 % de VMG frente a los vecinos. En el Mundial, la mejor franja es 16–18° en la mayoría de las ceñidas, y el top 5 navega dentro o al lado del rango. Es una asociación en la flota, no un experimento: la escora también depende del peso y del estilo de cada tripulación. Validado con datos sintéticos (óptimo conocido, sin efecto, pocos datos).

### Escora óptima en popa

Igual que en ceñida, pero con la escora con signo: + a sotavento, − a barlovento (en popa se escora a barlovento a propósito con poco viento). Mundial P9, popa 1 (20–25 kn): rango óptimo 0–4°, escorar ≥ 6° a sotavento pierde un 3–5 % de VMG frente a los vecinos.

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
| Pérdida en maniobra (m y s) | estimada | por fases (ver «Maniobras por fases»): lo que se habría avanzado sin maniobrar desde el inicio del giro hasta estar acelerado, menos lo que se avanzó; hasta la mitad del giro a la VMG de entrada y después a la VMG estable de la nueva amura. En segundos: metros / VMG media de las dos amuras |
| Layline | estimada | desde la última maniobra antes de la baliza (o el inicio del tramo): el barco está fuera si la demora a la baliza queda fuera del cono entre los rumbos sobre el fondo de las dos amuras de la flota (con la corriente incluida; si no hay, TWD ± TWA de la flota); exceso = distancia en perpendicular a la layline de esa amura. Lado del campo mirando hacia donde se navega (en ceñida, a barlovento; en popa, a sotavento, como Track to Tactics y las puertas) y segundos navegados fuera de la layline. No se calcula hacia la línea de llegada |
| Motivo del sobrepaso de layline | estimada | entre el cruce de la layline (sobre la amura anterior) y la última maniobra, con las posiciones de toda la flota cada 5 s (`fasttack/motor/trafico.py`): **no podía virar** si en ≥ 50 % de ese tiempo había un barco a menos de 3 esloras en el sector hacia el que tenía que girar; **tráfico en la layline** si al cruzarla ya había ≥ 3 barcos por ella delante (en la nueva amura, a menos de 3 esloras de la recta y más cerca de la baliza); si no, **cálculo**. Mundial P9: 55 de 90 sobrepasos de la ceñida 1 por cálculo y 28 porque no podía virar; en Cascais Vela (flota más compacta) predomina el tráfico |
| Escora, cabeceo | directa | mediana de \|roll − desviación del sensor\| y de pitch; IQR. **Desviación del sensor** = media de la escora mediana en amura babor y en amura estribor (en ceñida); 0 si faltan datos de alguna |
| Modo | estimada | frente a la mediana de la flota en el tramo. Ceñida: TWA < med − 1,5° y SOG < med → ALTURA; TWA > med + 1,5° y SOG > med → VELOCIDAD; si no, VMG. Popa: TWA > med + 3° y SOG < med → PROFUNDO; TWA < med − 3° y SOG > med → VELOCIDAD |
| Barco fantasma | estimada | recorre el tramo con el TWA de la flota y siempre en la amura favorecida: en cada corte avanza largo/10 a lo largo del eje y navega (largo/10) / cos(α − \|δ\|), con δ = TWD del corte − rumbo del eje (en popa, con TWD + 180°) |
| Eficiencia de roladas | estimada | (fantasma − distancia navegada) / fantasma |

## Maniobras por fases (estimado)

Cada virada o trasluchada (`tramos.analizar_maniobra`), con el rumbo de proa (COG si no hay brújula):
- **Entrada** (25 a 8 s antes): rumbo, SOG y VMG estables en la amura de partida.
- **Giro**: desde que la proa se separa > 6° del rumbo de entrada hasta que llega a menos de 6° del rumbo de la nueva amura, o lo pasa (salida más arribada/orzada).
- **Aceleración**: desde el final del giro hasta que la SOG vuelve al 95 % de la estable de la nueva amura (25–45 s tras el giro) durante 4 s (como mucho 60 s; si no llega, «no llega»).
- **Pérdida**: ver la tabla. Asignar a cada amura su propia VMG hace que una rolada o una racha no cuenten como pérdida de la maniobra (se cargan a la amura: táctica).
- **Caída de velocidad**: SOG mínima frente a la de entrada.
- **Ángulo de salida**: TWA media en los 10 s tras el giro, respecto a la TWA con la que el barco saca más VMG en el tramo (franjas de 2°, ≥ 30 s). Recién salidos, todos los barcos abaten y arriban para acelerar (el COG da un ángulo mayor que la proa), así que la referencia es cómo salen **los 5 primeros de la prueba**: en ceñida, más cerrado que ellos tarda en acelerar y más abierto pierde altura; en popa al revés, más profundo tarda en acelerar y más alto pierde profundidad (tolerancia ±3°). Sin flota (sesiones .vkx), frente a la salida habitual del propio barco en esa prueba.
- No se miden: maniobras encadenadas sin tiempo de estabilizar (se mide solo con la VMG de entrada), giros de más de 115° (virar y arribar a un través, rodeos) o con una amura de VMG < 60 % de la otra.

Validación: con la ventana fija anterior (−10…+20 s) un barco que tarda más de 20 s en acelerar no contaba esa parte. En el Mundial (P9, 100 barcos, 20–25 kn) se miden 325 de 1 375 maniobras (el resto caen en huecos de RaceSense o no son limpias): virada mediana 4,1 m (2,1 s), giro 7,5 s, aceleración 14 s, caída de SOG 37 %; trasluchada 3,8 m (1,6 s), giro 7 s, aceleración 11 s. En la sesión .vkx de ESP 1214 (2 Hz sin huecos) se miden todas: virada 3,6 m (2,2 s), giro 5 s, aceleración 14,5 s. Frente a Track to Tactics (Cascais Vela P9, pérdida media por virada): ESP 1170 7,6 m frente a 5,6 m; «65» 3,1 m frente a 2,7 m. En la flota del Mundial la pérdida apenas cambia con el ángulo de salida (en 20–25 kn): por eso se compara con el top 5 y no con un ángulo «óptimo» absoluto.

## Táctica por tramo (estimado)

`fasttack/motor/tactica.py`, por barco y tramo (sin maniobras ni rodeos):
- **Amura favorecida**: en cada instante, de las dos amuras posibles con la TWD de ese momento y el ángulo al viento del barco, la que apunta más cerca de la baliza. % del tiempo en ella y segundos en la otra (con la TWD a < 3° de la dirección de la baliza no cuenta).
- **Maniobras a favor / en contra de la rolada**: pasan de la amura desfavorecida a la favorecida (virar en el rolón) o al revés (10–40 s antes y después).
- **Lado del campo**: distancia lateral a la recta entre las balizas del tramo, mirando a barlovento; % a la derecha y separación máxima.
- Validación (Mundial, 6 pruebas, 20 tramos): la correlación entre el % en la amura favorecida y el parcial del tramo va en el sentido esperado (más tiempo en la favorecida, parcial menor) en 14 de 20 tramos, pero es débil (mediana −0,17): la TWD de la flota no ve las roladas locales. Usar la TWD de cada lado del campo no la mejora. Es orientativa.

## Dónde se perdió la prueba (estimado)

Tarjeta arriba de cada prueba (`rendimiento.desglose`): segundos perdidos (+) o ganados (−) por el barco de referencia frente al tiempo mediano de los 5 primeros (sin él). Por tramo con datos (calidad alta o media):
- **Velocidad** = largo del tramo / VMG estable propia − largo / VMG estable mediana del top 5 (VMG navegando sin maniobras ni rodeos; incluye el aire sucio).
- **Maniobras** = segundos perdidos en las maniobras del tramo (las no medidas por huecos, a la mediana de las medidas) − los del top 5.
- **Salida** (primera ceñida) = (metros por detrás del primero a los 60 s − mediana del top 5) / VMG propia; «sin datos» si el barco no tiene datos en la señal.
- **Táctica y resto** = la diferencia real en la llegada menos lo anterior: roladas, lado, laylines, rodeos y los tramos sin datos.
Mundial P9, ESP 1214: 136 s perdidos, casi todos de velocidad (+141 s); maniobras +5 s; táctica y resto −10 s. En la flota, la parte de velocidad está relacionada con el puesto final (correlación 0,42–0,64).

## Archivos .vkx propios en un campeonato de RaceSense

En la página del campeonato, «Tus archivos .vkx»: el registro del Atlas de un barco de la flota sustituye la telemetría de RaceSense de ese barco en el tiempo que cubre el archivo (`ingesta/propios.py`); el resto de la flota sigue viniendo de RaceSense. Así el barco propio no tiene huecos (maniobras, salida, escora completas). Se comprueba que la vela esté en la flota y que el archivo cubra alguna prueba; al añadir o quitar un archivo se recalculan los análisis.

## Temporada y reglaje

`fasttack/temporada.py`: por cada prueba analizada del barco (sin recorrido dudoso): puesto relativo, VMG en ceñida y en popa frente a la mediana del top 5 de la prueba, pérdida mediana por virada (s), laylines, regularidad mediana y el desglose de «dónde se perdió». Reglaje: para cada ajuste con al menos dos valores, media de esos indicadores por valor y por franja de viento de referencia (< 8, 8–12, 12–16, > 16 kn, o «sin viento de referencia»). Es una media de pocas pruebas en condiciones distintas: orientativo.

## Rendimiento dentro del tramo (estimado)

`fasttack/motor/rendimiento.py`, navegando estable (sin rodeos, 20 s, ni maniobras, ±15 s):
- **Polar del tramo**: VMG y SOG medianas por franja de TWA (2° en ceñida, 5° en popa; ≥ 15 s por franja) del barco de referencia frente a la mediana del top 5; se marca la TWA de máxima VMG (franjas con ≥ 30 s). Sin anemómetro, vale para el viento de ese tramo.
- **Regularidad**: VMG media de cada ventana de 30 s (alineadas para toda la flota) dividida por la mediana de la flota en esa ventana; la regularidad es la desviación típica de ese cociente (%). Así las rachas y roladas, que tiene toda la flota, no cuentan. Menor = más regular. Sin flota (< 3 barcos por ventana), respecto a la mediana del propio barco. Mundial P9: correlación con la VMG del tramo de −0,42 a −0,95 (los irregulares van más lentos).
- **Set tras barlovento** (solo para el debrief): banda de 5–15 s tras el rodeo (offset o baliza) frente a la de 20–45 s: «trasluchando» si cambia, «directo» si no.
- **Rodeo** (solo para el debrief): tiempo dentro de la zona (3 esloras) de la baliza de final de tramo y SOG de entrada, mínima y de salida, frente al top 5.

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

### Viento a lo largo de la línea (estimado)

La línea se divide en tercios (comité, centro, pin) según dónde cruzó cada barco. De +10 a +60 s, cada muestra de un barco da una TWD = COG ± TWA de la flota en la primera ceñida (según la amura; se descartan las que se apartan > 20° de ese ángulo). TWD del barco = media circular; de la zona = media de sus barcos (≥ 3); presión = SOG mediana. Se da la rolada de cada tercio frente a la TWD del disparo. Casi todos salen en la misma amura, por eso no se usa la bisectriz. Supone que todos navegan al mismo ángulo: un barco en aire sucio que arriba o uno que orza lo desvían; con muchos barcos por zona se compensa.

### Posicionamiento en la salida (estimado)

Con las posiciones GPS de todos los barcos que salen, cada 2 s de −30 a +90 s (`salida.posicionamiento`, distancias en esloras de la clase):
- **Llegada a la línea**: **pasado** si está en el lado del recorrido en la señal; **pronto** si 10 s antes estaba a menos de una eslora de la línea y en la señal su SOG es < 70 % de la mediana de la primera fila (a ≤ 2 esloras de la línea): tuvo que frenar; **tarde** si en la señal estaba a más de 2 esloras y cruza > 5 s después; si no, **a tiempo**.
- **Hueco a sotavento / barlovento**: distancia lateral en la señal al barco más cercano a la par (±1,5 esloras a lo largo del rumbo) por cada lado; «libre» si no hay nadie a menos de 6.
- **Aire sucio (primeros 90 s)**: tiempo con otro barco a ≤ 6 esloras en la dirección de la que llega el viento aparente (TWD girada 15° hacia proa, ±15°); quién y desde qué lado. **Planchado** si ≥ 30 % y el barco estaba a barlovento.
- **Sotavento en posición segura (primeros 60 s)**: barco a sotavento a ≤ 1,5 esloras de lado y de 0 a 2 esloras delante: no deja arribar para acelerar (≥ 50 %).
- Validación (Mundial, 5 pruebas, 247 salidas con datos): puesto mediano a los 60 s: a tiempo 18, tarde 29, pasado 51; aire limpio 22, en aire sucio 35,5, planchado desde barlovento 44,5. El hueco a sotavento y el sotavento en posición segura no separan tanto (22,5 frente a 22): se dan como contexto.

## Capas del mapa y valores instantáneos (estimado)

- **Amura favorecida** (capa): cada tramo de la traza en azul si navega en la amura favorecida (la que apunta más cerca de la baliza con la TWD de ese momento, como en «Táctica por tramo»), en rojo si va con la rolada en contra, en gris si da igual (TWD a < 3° de la dirección de la baliza) y en gris claro si está maniobrando o rodeando (a más de 25° de su ángulo de amura). La leyenda da el % del tramo en la favorecida del barco de referencia.
- **Línea del líder**: recta perpendicular al viento (TWD del momento) por la posición del barco más avanzado del tramo que se navega (hacia barlovento en ceñida, hacia sotavento en popa), y la paralela por el barco de referencia; los metros son la distancia entre las dos a lo largo del viento («escalera»). En los huecos de RaceSense se usa la última posición si es de hace ≤ 30 s.

- **Cada barco en su tramo**: los valores instantáneos (VMG, TWA) se calculan con el tramo que navega cada barco según sus propios pasos por baliza, no el del líder ni el de la pestaña: mientras unos ya van de popa, otros siguen en la ceñida o en el offset. Entre la baliza y el offset (rodeo) no hay VMG. Las tablas por tramo y las medias ya usaban los tiempos de entrada y salida de cada barco.
- **Fases de rolada y presión**: contiguas; cada cambio se sitúa entre los centros de los cortes (corte k = k·10 + 5 %), la primera fase desde el 0 % y la última hasta el 100 %.

- **Presión instantánea**: mancha azul alrededor de cada barco del tramo cuyo SOG supera en > 2 % la mediana de la flota en ese instante (más intensa cuanto más la supera); un anillo marca los barcos cuyo SOG ha subido > 6 % de la mediana en los últimos 30 s. Es un indicador de presión, no una medida del viento: la SOG también depende del rumbo y del mar.
- **Presión izquierda–derecha** (panel): SOG mediano de los barcos a la izquierda menos el de los barcos a la derecha de la mediana lateral (mirando a barlovento). «Equilibrada» si la diferencia es < 3 % de la mediana.
- **TWD instantánea**: tinte del campo según la TWD del instante frente a la media del tramo (azul = rolada a la izquierda, rojo = a la derecha; saturado a ±10°).
- **Laylines** (siempre, en el tramo en curso): rectas desde la baliza final del tramo con el TWA de la flota y la TWD del instante.
- **Rol**: colorea la traza según la rolada del momento a favor (azul) o en contra (rojo) de la amura en que navega el barco. **SOG**: colorea la traza con una rampa azul entre el p5 y el p95 de la ventana visible.
- **Corriente**: estimada por prueba y por vuelta (ver «Corriente»); flecha y valor en la esquina del mapa, y detalle en las pestañas de tramo.

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

**Conclusión**: pasos, puertas, velocidades, distancias, escora, salida y lado de las laylines coinciden con Track to Tactics. Las diferencias vienen sobre todo de la TWD: ellos la corrigen con una corriente de 0,88 kn tomada de una referencia externa; nuestra estimación desde la telemetría (motor 0.5, ver «Corriente») da 0,26 kn en el mismo sentido. Afecta a TWD, TWA, VMG absoluta, fases de rolada y metros de layline.

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
- **Debrief del día**: el resumen se calcula solo con las pruebas del día (sin descartes; penalización con los inscritos de todo el campeonato), con el top 5 del día como referencia; se añade la general calculada al terminar el día. La escora óptima se toma de todas las ceñidas del campeonato hasta ese día (un día solo tiene pocos datos). Formato: balance del día, lo que funcionó, lo que hay que corregir, 3 claves para mañana.
- **Debrief del campeonato en curso**: usa las pruebas analizadas hasta ese momento e indica si el campeonato sigue en curso y cuántas pruebas faltan por analizar.
- **Caché**: el texto se guarda con la huella (SHA-1) de sus cifras; si las cifras cambian, se avisa de que conviene regenerarlo.
- **Prueba real** (Mundial, prueba 9 y campeonato, ESP 1214, Claude Code): 36 y 54 s; todas las cifras verificadas. Un texto pegado a mano con una VMG inventada (9,99 kn) queda marcado.
