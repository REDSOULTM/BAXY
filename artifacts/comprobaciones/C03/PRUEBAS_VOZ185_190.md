# C03 — variabilidad física y señales reproducibles —185–190

No hay nuevo arreglo de producto ni aceptación de audio. DTLN128 se mantiene
experimental:183 cortó la primera hora española;185 y187 no registraron cortes.
Esto no borra183 ni prueba robustez.187 conserva además el PCM generado y la
señal exacta del cancelador;188 reproduce el cálculo sin diferencia alguna.

## Ejecuciones y limpieza

185 driver96589/captura13341 recogidos exit0.79,55s de captura y56,422s de
conductor. Cero overflows; hilos detenidos y endpoint restaurado a0/mutedtrue.
Snapshot previsto sólo tras primer barge_in: no existe porque no hubo evento.
El analizador preparado para ese snapshot no se ejecutó y fue retirado.

187 driver52688/captura89539 recogidos exit0.76,31s de captura y55,797s de
conductor. Cero overflows; hilos detenidos y restauración exacta. Trace acotado
en memoria,1249bloques/39,968s, guardado al salir. Observación altera scheduling;
no se atribuye a ella la diferencia respecto a183/185. Se conservan cuatro PCM
Piper originales con texto, tasa22050Hz, modelo y hora; no se regeneraron.

186 sesión30401 y189 sesión2240 recogidas exit0:16lecturas por ejecución.
Parakeet registrado CPU6beam8 sin pistas; crudo y pico0,8. Ventanas por UTC
pareado a estado con margen1s, mismas limitaciones de primer sonido real.

## Lecturas literales de audio físico

Las columnas son observaciones de reconocimiento, no respuestas nuevas de BAXY.
Se conserva lo incorrecto y vacío; recuperar una variante no convierte todo en pass.

| Ensayo | Salida | Canal | Crudo | Normalizado |
|---|---:|---|---|---|
| 185 | 1 | microphone | Hola, aquí Paxi. ¿En qué te puedo ayudar hoy? | Hola, aquí Basi. ¿En qué te puedo ayudar hoy? |
| 185 | 1 | loopback | Hola, aquí Baxi. ¿En qué te puedo ayudar hoy? | Hola, aquí Baxi. ¿En qué te puedo ayudar hoy? |
| 185 | 2 | microphone | Son las diez cincuenta y cinco. | Son las diez. |
| 185 | 2 | loopback | Son las diez. | Son las diez cincuenta y cinco. |
| 185 | 3 | microphone | (vacío) | (vacío) |
| 185 | 3 | loopback | (vacío) | It is 1056. |
| 185 | 4 | microphone | Son las diez cincuenta y seis. | Son las diez. |
| 185 | 4 | loopback | Son las diez. | Son las diez cincuenta y seis. |
| 187 | 1 | microphone | Hola, aquí Paxi. ¿En qué te puedo ayudar hoy? | Hola, aquí Baxi. ¿En qué te puedo ayudar hoy? |
| 187 | 1 | loopback | Hola, aquí Baxi. ¿En qué te puedo ayudar hoy? | Hola, aquí Baxi. ¿En qué te puedo ayud hoy? |
| 187 | 2 | microphone | Son las diez cincuenta y cinco. | Son las diez. |
| 187 | 2 | loopback | Son las diez. | Son las diez. |
| 187 | 3 | microphone | (vacío) | (vacío) |
| 187 | 3 | loopback | It is ten. | It is ten. |
| 187 | 4 | microphone | Son las diez cincuenta y seis. | Son las diez cincuenta y seis. |
| 187 | 4 | loopback | Son las diez. | Son las diez. |

Salidas enviadas:1«¡Hola! Aquí BAXY. ¿En qué te puedo ayudar hoy?»;
2«Son las10:55.»;3«It is10:56.»;4«Son las10:56.» (literales con espacios
exactos en PREREG185/187).185 recupera cada contenido en alguna lectura;
187 inglés no se recupera completo. Esto no equivale a detectar un corte.

## Reproducción188

Sesión21835 recogida exit0.1249bloques DTLN128 bitidénticos a187; probabilidades
VAD también idénticas en1249/1249. Referencia continua verificada por solapamiento.
128 y512 dan cero bloques de habla sobre esta señal de eco. Coste512 p99
19,38ms por32ms, máximo32,42ms;128 p99 2,69ms. No certifica coste combinado.
No se acreditan doble habla ni interrupciones contrafactuales: máscara speaking
congelada de187. Los fallos de mezcla129/179–181 siguen pendientes.

El [artículo DTLN-AEC](https://arxiv.org/html/2010.14337), secciones2.4 y4,
consultado2026-09-07, describe entrenamiento con retardos de10–100ms y una
mayor dificultad al separar voces parecidas. No exige alinear a retardo cero.
Por ello no hay fundamento aquí para un barrido de desplazamientos ni para
atribuir automáticamente el fallo de mezcla al retardo acústico de52ms.

## Origen frente a reproducción190

Comando compare190 terminó exit0: ocho lecturas sobre cuatro PCM originales,
sin pistas, con1s de silencio a cada lado; amplitud original y ajustada mediante
mínimos cuadrados al loopback. Nada se sintetizó otra vez. Datos en
astra-compare190; todos los bloques de200ms y lecturas se conservan.

| Salida | Parakeet original Piper | Original a ganancia estimada de loopback | Correlación global |
|---|---|---|---:|
| 1 | Hola, aquí Baxi. ¿En qué te puedo ayudar hoy? | Hola, aquí Baxi. ¿En qué te puedo ayudar hoy? | 0.6973 |
| 2 | Son las diez. | Son las diez. | 0.5780 |
| 3 | It is ten. | It is ten. | 0.4824 |
| 4 | Son las diez cincuenta y seis. | Son las diez. | 0.5836 |

El inglés ya se reconoce como «It is ten.» desde el PCM generado, antes de
altavoces/AEC. Esto impide atribuir esa omisión de ASR al cancelador o a otro
corte. No demuestra por sí solo que Piper omita los minutos: falta un observador
independiente de la misma onda. Correlaciones0,48–0,70 y diferencias por bloque
no prueban igualdad de reproducción; ajuste global no corrige deriva/filtrado.
No se cambia timeout, volumen ni pronunciación sin localizar la primera pérdida.

## Herencia para controles humanos y pendientes

Se consultó biblioteca/01_INVENTARIO.md por corpus/voz/STT. El reporte histórico
gemma4-agent/documentacion/03_voz_stt/research/baseline_real_voice.txt declara
84clips RED y180terceros, con WER elevado; REPORTE_NOCHE_STT_PARAKEET_2026_05_23.md
remite a scripts/stt_real_voice_eval.py y download_fleurs_es.py. No se han
localizado/verificado sus audios; no se acredita procedencia por el título ni
se cuentan como reserva100. barge_in.md es diseño histórico, no instrucción;
no se adopta su umbral500ms ni su propuesta de omitir audio durante voz.

Siguiente: observador independiente sobre PCM187 congelado y loopback189 para
distinguir pronunciación de error de reconocimiento; no repetir frases físicas
ni descargar otro cancelador. Conservar también fallo183 y mezcla129.
Fuente172 y runtime registrado intactos, sin Full nuevo/commit/push. C03 activo
íntegro: ocho rutas finales,100humanos congelados y100/100, averías, UI/voz/wake,
4GB, promoción reproducible, continuidadC04–C09, Full y publicación.
