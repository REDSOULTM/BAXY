# Error PEG de H0104: atribución y límite

La segunda petición de737, H0104 con el prompt de BAXY, terminó con error500:
`The model produced output that does not match the expected peg-native format`.
La primera petición, con pregunta y hechos directos, terminó `stop`.

`server.log:31–36` del directorio privado conserva un resto no consumido que
incluye razonamiento delimitado y una respuesta final correcta sobre la ventana.
El registro marca `truncated = 0`. Se generó texto final correcto, pero la API
no lo entregó como `content`. No es un veto del validador de BAXY, que ni siquiera
se ejecuta en737; tampoco corresponde adjudicar ese error como respuesta
semánticamente incorrecta.

La fuente local del backend en
`D:/BAXYRuntime/build/llama-k2-horizon-35999d1/common/chat.cpp:3829–3881`
explica la ruta del error: `common_chat_peg_parse` concatena
`generation_prompt + input`, intenta parsearlo y en fallo final registra
`effective_input.substr(result.end)` antes de lanzar el error. Por tanto, el
registro es el resto de esa concatenación, no una captura íntegra de los tokens
muestreados. El fragmento disponible no prueba qué delimitador causó el rechazo.

Los dos prompts persistidos de H0104 terminan con el mismo prefijo nativo:
`<|ifm|im_start|>assistant\n<ifm|think>\n`.
No hay diferencia de sampler, esfuerzo ni flags. La plantilla local
`models/templates/k2-horizon.jinja:847–881` documenta los delimitadores de
razonamiento, el final assistant y ese prefill. La arena PEG generada y sus
diffs de análisis no se guardaron; la salida exitosa guarda texto ya parseado,
no todos sus tokens especiales. No se ha demostrado la regla concreta que
rechazó el caso ni una corrección del parser.

El ejecutable usado está fijado por hash en PREREG. El receipt
`K2_HORIZON_LATENCY697/BACKEND_BUILD698.json` registra la sesión de compilación
74918 y sella ese mismo ejecutable junto con snapshots de `chat.cpp`,
`chat-auto-parser-generator.cpp` y `chat-diff-analyzer.cpp`. Los cuatro hashes
actuales coinciden con el receipt. Es la procedencia de build disponible, aunque
un hash de fuente y binario por sí solo no prueba una relación criptográfica
entre ambos. No se reconstruye el backend por timestamps ni por el mero hecho
de que el checkout tenga modificaciones. La atribución demostrada termina en el
fallo del parser final. Una eventual corrección debe conservar los marcadores
y separar razonamiento de respuesta, con reproducción del fallo y regresión;
no convertir razonamiento en respuesta ni aceptar silenciosamente una salida
que incumpla el protocolo.

H0600 muestra otro tipo de salida vacía: `stop` con83 tokens de salida y uso
completo, sin error500. El agente principal verificó84 eventos SSE persistidos:
ninguno contiene `content`; el campo `reasoning_content` termina con una línea
que propone la hora. Por tanto, el cliente no perdió un fragmento visible que
estuviera en esos eventos. Sin los tokens crudos anteriores al parser no se
puede separar una respuesta nunca emitida fuera del razonamiento de una
omisión del parser. No se rescata esa línea de razonamiento como respuesta.
