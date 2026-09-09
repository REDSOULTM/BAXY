# C03 — contraste AEC3 y doble habla — tramos 173–175

La fuente172 corrige el contador de interrupciones, pero el ensayo físico173
sigue cortando dos de cuatro salidas. AEC3 por defecto mejora la eliminación de
eco174, pero falla el control de palabras cercanas mezcladas con eco174/175.
No se adopta ni se promueve. No hay nueva prueba de UI ni audio físico en174/175.

## Fuente172 y corrida física173

Pruebas dueñas:130 pass,0 skips,7,36s; Fast55364 exit0, Release2,73s,0 avisos/errores.
173: saludo1,344s y primera hora ES1,656s cortados por barge_in; hora EN2,750s
y última hora ES2,984s sin evento. Todos los errores TTS null. No se ha verificado
que las dos salidas sin evento contengan la frase completa. Dos eventos en dos
salidas: desaparece la emisión repetida observada en168, no baja la tasa2/4.
Capture84,25s,0overflows,threadsStopped=true,restoredExactly=true (0/muted=true).
Driver41212/captura20590 terminaron exit0. No procesos propios de esas corridas.

## Herencia, alternativa y configuración

SpeexDSP1.2.1,512muestras,16k,cola3200 y preprocesador por defecto, fuente172.
Se reutilizan señales149 nativas exactas y127/129/131 de mezcla sintética ya
consumidas.149 reproduce la salida Speex bit a bit.127/129 conservan alineación
aproximada de streamReadyUtc; no atribuir ese reloj a captura nativa exacta.

[pywebrtc-audio0.2.0](https://github.com/strands-labs/pywebrtc-audio), consultado
2026-09-07: wheel CPython312 Windows x64 de513.391bytes, SHA
0dabbdadd5d7fd7dcb88323266e5e14d46aaa136c58fa0573c4b0323b683c80b.
Descarga aislada en D:/BAXYRuntime/experiments/voice/webrtc174, sin instalación
en runtime. Fuente distribuida también conservada y verificada con PyPI.
MODIFICATIONS.md declara extracción ewan-xu/AEC3 y modificaciones; no identifica
un commit exacto de WebRTC. No describirla como idéntica al Chrome actual.

AEC3 16k mono, bloques continuos de160muestras, estado frío por caso;
stream_delay_ms=0 (estimador interno), HPF intrínseco, sin NS/AGC añadidos.
Sin rellenar de silencio cada bloque512. Se descarta sólo el resto final menor
a10ms en AEC3 y a32ms en Speex; no afecta la ventana hablada interior.
El análisisVAD usa umbral0,5/energía0,004/floor1,8 y contador consecutivo172.
Omite guard crudo: son candidatos máximos, no eventos reales de cancelación.

## Medición local

| Señal | Método | Bloques de habla | Candidatos sin guard | Mayor secuencia |
|---|---|---:|---:|---:|
| native_echo149 | raw | 120 | 44 | 7 |
| native_echo149 | speex | 42 | 6 | 6 |
| native_echo149 | webrtc | 0 | 0 | 0 |
| physical_echo | raw | 127 | 25 | 7 |
| physical_echo | speex | 33 | 6 | 6 |
| physical_echo | webrtc | 0 | 0 | 0 |
| near_only | raw | 86 | 45 | 9 |
| near_only | speex | 86 | 45 | 10 |
| near_only | webrtc | 87 | 45 | 9 |
| physical_echo_plus_synthetic_near | raw | 113 | 64 | 14 |
| physical_echo_plus_synthetic_near | speex | 92 | 49 | 14 |
| physical_echo_plus_synthetic_near | webrtc | 67 | 28 | 8 |
| cold_silence | raw | 0 | 0 | 0 |
| cold_silence | speex | 0 | 0 | 0 |
| cold_silence | webrtc | 0 | 0 | 0 |

AEC3 media~0,075ms por10ms; Speex~0,135ms por32ms. Ambos CPU; no se mide aquí
VRAM/RAM de producto combinado. rssDelta incluye buffers/allocador y no equivale
a memoria aislada del algoritmo. Latencia observada del control cercano:127
muestras AEC3,511 Speex por correlación; no se ha integrado el adaptador512→160.

## Palabras preservadas y perdidas

Entrada cercana sintética heredada120: «¡Hola! Aquí BAXY. ¿En qué te puedo ayudar hoy?».
Parakeet registrado,CPU6/beam8,sin hints,misma ventana131 para cada método:

| Control | Método | Texto observado174 |
|---|---|---|
| near_only | raw | Hola, aquí Paxi. ¿En qué te puedo ayudar hoy? |
| near_only | speex | Hola, aquí Paxi. ¿En qué te puedo ayudar hoy? |
| near_only | webrtc | Hola, aquí Baxi. ¿En qué te puedo ayudar hoy? |
| physical_echo_plus_synthetic_near | raw | (vacío) |
| physical_echo_plus_synthetic_near | speex | Hola, ¿en qué te puedo ayudar hoy? |
| physical_echo_plus_synthetic_near | webrtc | Exactly. |

Observación175 del mismo PCM: Parakeet normalizado a pico0,8; Nemotron3.5 ya
instalado,CPU6/greedy/auto,silencio final0,66s heredado116, crudo y normalizado.
No cambia el cancelador ni se regenera señal. Resultados completos:

| Control | Método | Observador | Normalizado | Texto observado175 |
|---|---|---|---|---|
| near_only | raw | parakeet | True | Hola, aquí Paxi. ¿En qué te puedo ayudar hoy? |
| near_only | raw | nemotron | False | Dólar aki baxir.  ¿En qué te puedo ayudar hoy? |
| near_only | raw | nemotron | True | ¿En qué te puedo ayudar hoy |
| near_only | speex | parakeet | True | Hola, aquí Paxi. ¿En qué te puedo ayudar hoy? |
| near_only | speex | nemotron | False | ¿En qué te puedo ayudar hoy |
| near_only | speex | nemotron | True | Aki baxis en qué te puedora hoy |
| near_only | webrtc | parakeet | True | Hola, aquí Baxi. ¿En qué te puedo ayudar hoy? |
| near_only | webrtc | nemotron | False | Dólar, ¿en qué te puedo ayudar hoy |
| near_only | webrtc | nemotron | True | Dólar en qué te puedo ayudar hoy |
| physical_echo_plus_synthetic_near | raw | parakeet | True | (vacío) |
| physical_echo_plus_synthetic_near | raw | nemotron | False | en que tedo ayudar hoy |
| physical_echo_plus_synthetic_near | raw | nemotron | True | Poland Aki Baksi, ¿en qué te puedo ayudar hoy |
| physical_echo_plus_synthetic_near | speex | parakeet | True | Hola, aquí Taxi. ¿En qué te puedo ayudar hoy? |
| physical_echo_plus_synthetic_near | speex | nemotron | False | en qué te puedo ayudar hoy |
| physical_echo_plus_synthetic_near | speex | nemotron | True | ¿En qué tedo ayudar hoy |
| physical_echo_plus_synthetic_near | webrtc | parakeet | True | Exactly. |
| physical_echo_plus_synthetic_near | webrtc | nemotron | False | (vacío) |
| physical_echo_plus_synthetic_near | webrtc | nemotron | True | en qué puedo ayudar hoy |

El caso mezclado AEC3 pierde contenido ante ambos observadores. Normalizar no
recupera la frase íntegra. La ausencia de candidatos de eco no basta para adoptarlo.
Las variantes de nombre Baxi/Paxi no se confunden con omitir toda la frase.

## Decisión y siguiente contraste

176 observa salida lineal y final con la API nativa EchoControl::ProcessCapture
y GetMetrics. No cambia duración/umbrales de barge ni parámetros de supresión.
Primero exige comparar salida final de compilación local con wheel174 para
distinguir la diferencia de build del punto observado. No asumir pérdida en la
supresión residual sin ver salida intermedia.
Conservative_initial_phase no se cambia: aec_state.cc:91–101/283–312 prolonga
los tiempos iniciales, no demuestra recuperar voz cercana por su nombre.

Goal EN_CURSO.100 humanos sin congelar/ejecutar; ocho rutas finales, audio/ingreso,
averías/recuperación, promoción/regresión/continuidadC04–C09,Full/publicación
siguen pendientes. Fuente172 y manifiesto registrado intactos durante174/175.
