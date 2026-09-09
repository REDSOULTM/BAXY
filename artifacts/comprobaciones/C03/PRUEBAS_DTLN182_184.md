# C03 — DTLN continuo y salida física —182–184

El adaptador continuo conserva exactamente el cálculo de referencia. La prueba
física183 sigue fallando: primera hora española interrumpida. No se adopta DTLN
ni se cambia fuente172, manifiesto, umbrales, wake o criterio de aceptación.

## Adaptador182

Seis comparaciones:128/512 sobre eco nativo149, voz cercana sola129 y mezcla129.
PCM idéntico a179/180 en las seis. Retardo384muestras/24ms y referencia alineada
verificados por índices independientes; entrada inválida, propiedad de hilo y
cierre comprobados. Sesión47659exit0; evidencia en astra-stream182.

128 p99 máximo4,11ms por bloque32ms;512 p99 máximo22,22ms. Coste experimental,
sin certificar recursos del producto completo. Se elige128 para diagnóstico183.
Los fallos de fidelidad de mezcla179–181 permanecen abiertos.

## Salida183

Mismo conductor completo JSONL/LLM/catálogo/voz173 y cuatro textos, con binding
experimental182; sin App/UI. Observación sólo de estado, sin taps porframe.
Driver42628 y captura27245 recogidos exit0; CLEANUP58,312s. Captura81,05s,
cero overflows en ambos streams, hilos detenidos y restauración exacta a volumen0
y mutedtrue. Un evento barge_in88780,953 durante primera hora española.
No demuestra mejora robusta respecto a173: Piper puede generar ondas distintas.

## Observación184

Parakeet registrado CPU6/beam8, sin pistas, micrófono y loopback. Crudo y
normalizado a pico0,8,16lecturas; sesión91987exit0. RESULT/PREREG en
astra-observe184 conservan todas las lecturas, hashes de audio y ventanas.
183 sólo guardó tiempo monotónico de speaking: conversión UTC mediante offset
medido después en el mismo arranque; supone ausencia de salto de reloj.
Margen1s antes/después de cada intervalo; energía de loopback queda dentro.
ASR es observación imperfecta; normalizar tampoco mejora siempre.

| Texto enviado | Mic crudo | Loopback crudo | Resultado |
|---|---|---|---|
| ¡Hola! Aquí BAXY. ¿En qué te puedo ayudar hoy? | Hola, aquí Baxi. ¿En qué te puedo ayudar hoy? | Hola, aquí Baxi. ¿En qué te puedar hoy? | Mic recupera contenido, nombre fonético |
| Son las 10:55. | Sola. | vacío | Corte confirmado por evento y fragmento de salida |
| It is 10:56. | It is ten fifty six. | It is ten fifty six. | Contenido recuperado |
| Son las 10:56. | Son las diez. | Son las diez cincuenta y seis. | Completo sólo en loopback crudo |

No son turnos humanos ni reserva100. No se acredita entrada humana, doble habla,
wake aprobado, ocho rutas o cierreC03. Siguiente185: snapshot exacto sólo después
de decidir primera interrupción para separar fallo de referencia de separación.
