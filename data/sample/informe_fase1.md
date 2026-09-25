# Informe Fase 1 — muestras de telemetría

Generado 2026-09-25 09:47 por fase1_muestras.py

## j70

- Filas: 269,542; páginas: 3; tamaño JSON: 29.7 MB (~110 B/fila)
- Dispositivos: 109 ({'competitor': 101, 'mark': 8})

### Frecuencia de muestreo (Δt entre muestras consecutivas por dispositivo)

- **competitor**: mediana 1200 ms, p90 4200 ms, p99 25500 ms, máx 1574800 ms; Δt más frecuentes: [(1000, 23877), (1100, 13525), (1200, 11486), (500, 11023), (1500, 10058), (1300, 9321)]; mediana por dispositivo entre 300 y 4300 ms; huecos >5 s: 17307
- **mark**: mediana 500 ms, p90 1300 ms, p99 8200 ms, máx 1672900 ms; Δt más frecuentes: [(500, 15527), (400, 5093), (300, 4721), (100, 4681), (200, 4417), (600, 4270)]; mediana por dispositivo entre 300 y 7400 ms; huecos >5 s: 846
- (ts, sn) duplicados: 0; resolución: ts % 100 == 0 en 100.0% de filas
- Filas ordenadas por ts: True

### sail_number

- 100 velas distintas; sin espacio: ['BRA1440', 'BRA641', 'GBR1906', 'GER1898', 'POR570']
- Dispositivos con >1 sail_number: 0
- Velas de la telemetría que no están en participants (sin espacios): []
- SOG máx. por dispositivo (top 3): [('TUR 1486', 29.2), ('ITA 1478', 16.5), ('USA 1863', 16.1)]
- sail_number en balizas: {''}

### race_number, start_number, race_stage

- (race_number, start_number): [((2, 1), 228668), ((3, 1), 40224), ((3, 0), 637), ((4, 0), 13)]
- race_stage: [('in_progress', 128783), ('finishing', 72341), ('starting', 67227), ('finished', 1191)]
- Dispositivos que cambian de race_number dentro de la ventana: 109

### status

- Valores: [(8, 142326), (0, 65607), (11, 4634), (3, 4405), (9, 45), (1, 6)]
- Coherencia posición/SOG por status: status=0 (0000): mediana 0.38 kn, p90 0.78 kn (n=52556); status=1 (0001): mediana 0.11 kn, p90 0.65 kn (n=5); status=3 (0011): mediana 0.19 kn, p90 0.48 kn (n=3483); status=8 (1000): mediana 0.19 kn, p90 0.50 kn (n=125671); status=9 (1001): mediana 0.17 kn, p90 0.56 kn (n=39); status=11 (1011): mediana 0.18 kn, p90 0.48 kn (n=3952)
  - status=0: sog medio 5.71 kn; race_stage [('in_progress', 33246), ('finishing', 28943), ('starting', 3185)]
  - status=8: sog medio 5.63 kn; race_stage [('in_progress', 60021), ('starting', 55166), ('finishing', 26370)]
  - status=9: sog medio 5.52 kn; race_stage [('in_progress', 45)]
  - status=11: sog medio 6.70 kn; race_stage [('in_progress', 3544), ('finishing', 1047), ('finished', 43)]
  - status=1: sog medio 4.92 kn; race_stage [('in_progress', 6)]
  - status=3: sog medio 7.45 kn; race_stage [('in_progress', 2249), ('finishing', 2148), ('finished', 8)]

### sog

- Múltiplos de 0,1 m/s: 100.0%; máx 29.16 kn

### roll (signo)

- Rango roll: -47..55; pitch: -45..37
- Viento estimado (bisectriz de amuras, 1.ª ceñida) 320°. Amura estribor: n=4398, roll mediano -12°, 70% < 0. Amura babor: n=10060, roll mediano +17°, 99% > 0. ⇒ roll>0 = escora a estribor si la amura estribor da roll<0 y la babor roll>0.

### heading frente a COG (en regata, SOG > 3 kn)

- n=75768; p5/p25/p50/p75/p95 = -18.9/-6.0/+0.9/+7.0/+18.0 °; |Δ|<5° en 40%

### Balizas

- sn 16525 (0x408D): 12191 muestras en regata; funciones (no está en ningún recorrido); desplazamiento respecto a la mediana p50/p95/máx = 1540/3147/3400 m; campos distintos de 0: ninguno
- sn 19800 (0x4D58): 11625 muestras en regata; funciones (no está en ningún recorrido); desplazamiento respecto a la mediana p50/p95/máx = 4/14/18 m; campos distintos de 0: ninguno
- sn 19883 (0x4DAB): 105 muestras en regata; funciones ['Start:startLeft', 'start_line[0]']; desplazamiento respecto a la mediana p50/p95/máx = 1/35/38 m; campos distintos de 0: ninguno
- sn 21253 (0x5305): 2242 muestras en regata; funciones (no está en ningún recorrido); desplazamiento respecto a la mediana p50/p95/máx = 790/4224/4311 m; campos distintos de 0: ninguno
- sn 24575 (0x5FFF): 1884 muestras en regata; funciones (no está en ningún recorrido); desplazamiento respecto a la mediana p50/p95/máx = 1213/4027/4093 m; campos distintos de 0: ninguno
- sn 25470 (0x637E): 9051 muestras en regata; funciones (no está en ningún recorrido); desplazamiento respecto a la mediana p50/p95/máx = 926/3069/3085 m; campos distintos de 0: ninguno
- sn 25639 (0x6427): 2232 muestras en regata; funciones ['Finish:finishRight', 'Gate:gateRight', 'finish_line[1]', 'gate_zone[1]']; desplazamiento respecto a la mediana p50/p95/máx = 2/499/501 m; campos distintos de 0: ninguno
- sn 25687 (0x6457): 3329 muestras en regata; funciones ['Finish:finishLeft', 'Gate:gateLeft', 'Start:startRight', 'finish_line[0]', 'gate_zone[0]', 'start_line[1]']; desplazamiento respecto a la mediana p50/p95/máx = 3/491/492 m; campos distintos de 0: ninguno
- En los recorridos pero sin telemetría en la ventana: [18759, 19228]

### /api/regatta (j70)

- Revisiones: 1; divisiones: ['Open']
- `.raceSenseEvent.origin.coordinates`: ej. [-9.4580722, 38.666954]; primer valor = lat en 0/1 (supone |lat|>|lon| en la zona)
- `.divisions[].races[].starts[].startingStats[].lineRightLocation.coordinates`: ej. [-9.382297699999999, 38.631963999999996]; primer valor = lat en 0/633 (supone |lat|>|lon| en la zona)
- `.divisions[].races[].starts[].startingStats[].positionAtStart.coordinates`: ej. [-9.3834127, 38.6309215]; primer valor = lat en 0/651 (supone |lat|>|lon| en la zona)
- `.divisions[].races[].starts[].startingStats[].lineLeftLocation.coordinates`: ej. [-9.3895059, 38.6251617]; primer valor = lat en 0/643 (supone |lat|>|lon| en la zona)
- `.divisions[].races[].starts[].startLine.leftEnd`: ej. [38.6251617, -9.3895059]; primer valor = lat en 9/9 (supone |lat|>|lon| en la zona)
- `.divisions[].races[].starts[].startLine.rightEnd`: ej. [38.631963999999996, -9.382297699999999]; primer valor = lat en 9/9 (supone |lat|>|lon| en la zona)
- `.divisions[].races[].finishes[].lineLeftLocation.coordinates`: ej. [-9.4324031, 38.6504559]; primer valor = lat en 0/569 (supone |lat|>|lon| en la zona)
- `.divisions[].races[].finishes[].lineRightLocation.coordinates`: ej. [-9.4333508, 38.649930499999996]; primer valor = lat en 0/571 (supone |lat|>|lon| en la zona)
- `.divisions[].races[].finishes[].positionAtFinish.coordinates`: ej. [-9.4326867, 38.650324399999995]; primer valor = lat en 0/571 (supone |lat|>|lon| en la zona)
- Formatos de fecha: `endDate`→epoch ×1; `endTime`→RFC3339 Z/offset ×9; `finishingTime`→RFC3339 Z/offset ×571; `startDate`→epoch ×1; `startTime`→ISO sin zona ×430; `startTime`→epoch ×9; `timezoneOffset`→epoch ×9

## ilca7

- Filas: 167,249; páginas: 2; tamaño JSON: 17.7 MB (~106 B/fila)
- Dispositivos: 63 ({'competitor': 47, 'mark': 16})

### Frecuencia de muestreo (Δt entre muestras consecutivas por dispositivo)

- **competitor**: mediana 1600 ms, p90 3500 ms, p99 14700 ms, máx 481600 ms; Δt más frecuentes: [(1500, 6577), (1400, 6239), (1300, 4821), (1000, 4187), (2000, 4141), (1600, 4030)]; mediana por dispositivo entre 1500 y 1700 ms; huecos >5 s: 4700
- **mark**: mediana 500 ms, p90 2000 ms, p99 6000 ms, máx 96100 ms; Δt más frecuentes: [(500, 15288), (100, 10981), (400, 7607), (200, 6153), (600, 5794), (300, 4597)]; mediana por dispositivo entre 400 y 3600 ms; huecos >5 s: 1089
- (ts, sn) duplicados: 0; resolución: ts % 100 == 0 en 100.0% de filas
- Filas ordenadas por ts: True

### sail_number

- 47 velas distintas; sin espacio: []
- Dispositivos con >1 sail_number: 0
- Velas de la telemetría que no están en participants (sin espacios): []
- SOG máx. por dispositivo (top 3): [('CYP 212431', 11.5), ('IRL 216101', 11.3), ('NED 211160', 11.1)]
- sail_number en balizas: {''}

### race_number, start_number, race_stage

- (race_number, start_number): [((1, 1), 160278), ((2, 0), 6971)]
- race_stage: [('finishing', 111929), ('starting', 30012), ('in_progress', 14253), ('finished', 11055)]
- Dispositivos que cambian de race_number dentro de la ventana: 62

### status

- Valores: [(8, 83739), (11, 3965), (0, 1567), (9, 10)]
- Coherencia posición/SOG por status: status=0 (0000): mediana 0.16 kn, p90 0.43 kn (n=1181); status=8 (1000): mediana 0.16 kn, p90 0.43 kn (n=73931); status=9 (1001): mediana 0.51 kn, p90 0.83 kn (n=8); status=11 (1011): mediana 0.16 kn, p90 0.41 kn (n=3201)
  - status=0: sog medio 4.66 kn; race_stage [('finishing', 1255), ('starting', 312)]
  - status=8: sog medio 4.87 kn; race_stage [('finishing', 51745), ('starting', 18008), ('in_progress', 7658)]
  - status=9: sog medio 4.63 kn; race_stage [('in_progress', 8), ('starting', 2)]
  - status=11: sog medio 5.06 kn; race_stage [('finishing', 3131), ('in_progress', 428), ('finished', 406)]

### sog

- Múltiplos de 0,1 m/s: 100.0%; máx 11.47 kn

### roll (signo)

- Rango roll: -127..101; pitch: -28..90
- Viento estimado (bisectriz de amuras, 1.ª ceñida) 80°. Amura estribor: n=4371, roll mediano -5°, 68% < 0. Amura babor: n=3543, roll mediano +6°, 72% > 0. ⇒ roll>0 = escora a estribor si la amura estribor da roll<0 y la babor roll>0.

### heading frente a COG (en regata, SOG > 3 kn)

- n=34350; p5/p25/p50/p75/p95 = -17.4/-6.9/+0.5/+8.9/+23.1 °; |Δ|<5° en 34%

### Balizas

- sn 11011 (0x2B03): 8897 muestras en regata; funciones (no está en ningún recorrido); desplazamiento respecto a la mediana p50/p95/máx = 63/123/221 m; campos distintos de 0: ninguno
- sn 27834 (0x6CBA): 2240 muestras en regata; funciones ['Gate 4:gateRight', 'gate_zone[1]']; desplazamiento respecto a la mediana p50/p95/máx = 1/37/56 m; campos distintos de 0: ninguno
- sn 27843 (0x6CC3): 2176 muestras en regata; funciones ['Gate 4:gateLeft', 'gate_zone[0]']; desplazamiento respecto a la mediana p50/p95/máx = 1/2/28 m; campos distintos de 0: ninguno
- sn 27966 (0x6D3E): 1317 muestras en regata; funciones ['Start:startLeft', 'start_line[0]']; desplazamiento respecto a la mediana p50/p95/máx = 1/4/67 m; campos distintos de 0: ninguno
- sn 28036 (0x6D84): 2005 muestras en regata; funciones ['Finish:finishLeft', 'Gate 3:gateLeft', 'gate_zone[0]']; desplazamiento respecto a la mediana p50/p95/máx = 1/1/2 m; campos distintos de 0: ninguno
- sn 28151 (0x6DF7): 644 muestras en regata; funciones ['R2:markPort', 'port_rounding_zone[0]']; desplazamiento respecto a la mediana p50/p95/máx = 1/1/1 m; campos distintos de 0: ninguno
- sn 28181 (0x6E15): 1266 muestras en regata; funciones ['R1:markPort', 'port_rounding_zone[0]']; desplazamiento respecto a la mediana p50/p95/máx = 1/2/2 m; campos distintos de 0: ninguno
- sn 28214 (0x6E36): 9209 muestras en regata; funciones ['Finish:finishLeft', 'finish_line[0]']; desplazamiento respecto a la mediana p50/p95/máx = 4/82/162 m; campos distintos de 0: ninguno
- sn 28881 (0x70D1): 1416 muestras en regata; funciones (no está en ningún recorrido); desplazamiento respecto a la mediana p50/p95/máx = 3/8/13 m; campos distintos de 0: ninguno
- sn 30822 (0x7866): 1085 muestras en regata; funciones ['Start:startRight', 'start_line[1]']; desplazamiento respecto a la mediana p50/p95/máx = 0/1/1 m; campos distintos de 0: ninguno
- sn 30835 (0x7873): 9727 muestras en regata; funciones (no está en ningún recorrido); desplazamiento respecto a la mediana p50/p95/máx = 549/1114/1243 m; campos distintos de 0: ninguno
- sn 30894 (0x78AE): 2330 muestras en regata; funciones (no está en ningún recorrido); desplazamiento respecto a la mediana p50/p95/máx = 3/8/12 m; campos distintos de 0: ninguno
- sn 30905 (0x78B9): 1773 muestras en regata; funciones ['Finish:finishRight', 'Gate 3:gateRight', 'gate_zone[1]']; desplazamiento respecto a la mediana p50/p95/máx = 1/1/4 m; campos distintos de 0: ninguno
- sn 30911 (0x78BF): 7624 muestras en regata; funciones (no está en ningún recorrido); desplazamiento respecto a la mediana p50/p95/máx = 365/1197/1247 m; campos distintos de 0: ninguno
- sn 30966 (0x78F6): 7133 muestras en regata; funciones (no está en ningún recorrido); desplazamiento respecto a la mediana p50/p95/máx = 562/855/890 m; campos distintos de 0: ninguno
- sn 30996 (0x7914): 2349 muestras en regata; funciones ['Finish:finishRight', 'finish_line[1]']; desplazamiento respecto a la mediana p50/p95/máx = 1/1/2 m; campos distintos de 0: ninguno

### /api/regatta (ilca7)

- Revisiones: 1; divisiones: ['Gold', 'Silver', 'Bronze']
- `.divisions[].races[].finishes[].lineRightLocation.coordinates`: ej. [-6.1529395, 53.3236682]; primer valor = lat en 0/802 (supone |lat|>|lon| en la zona)
- `.divisions[].races[].finishes[].positionAtFinish.coordinates`: ej. [-6.1522342, 53.323316999999996]; primer valor = lat en 0/802 (supone |lat|>|lon| en la zona)
- `.divisions[].races[].finishes[].lineLeftLocation.coordinates`: ej. [-6.152192899999999, 53.323287799999996]; primer valor = lat en 0/802 (supone |lat|>|lon| en la zona)
- `.divisions[].races[].starts[].startingStats[].lineLeftLocation.coordinates`: ej. [-6.1456681, 53.3206746]; primer valor = lat en 0/799 (supone |lat|>|lon| en la zona)
- `.divisions[].races[].starts[].startingStats[].positionAtStart.coordinates`: ej. [-6.145687, 53.3206327]; primer valor = lat en 0/797 (supone |lat|>|lon| en la zona)
- `.divisions[].races[].starts[].startingStats[].lineRightLocation.coordinates`: ej. [-6.1452675, 53.3177108]; primer valor = lat en 0/793 (supone |lat|>|lon| en la zona)
- `.divisions[].races[].starts[].startLine.rightEnd`: ej. [53.3177117, -6.1452604]; primer valor = lat en 18/18 (supone |lat|>|lon| en la zona)
- `.divisions[].races[].starts[].startLine.leftEnd`: ej. [53.3206746, -6.1456681]; primer valor = lat en 18/18 (supone |lat|>|lon| en la zona)
- Formatos de fecha: `endDate`→epoch ×1; `endTime`→RFC3339 Z/offset ×18; `finishingTime`→RFC3339 Z/offset ×803; `startDate`→epoch ×1; `startTime`→ISO sin zona ×385; `startTime`→epoch ×18; `timezoneOffset`→epoch ×18
