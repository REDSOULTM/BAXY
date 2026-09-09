# C03 — límite físico del detector de eco — 2026-09-07

Fuente119/124 sin cambios en estos tramos. No promoción ni aceptación acústica.

## 126: contenido de las capturas existentes

`scratchpad/c03-analyze-voice126.py`, Python runtime, sesión68875exit0.
Sólo lectura de WAV privados123/125, con hashes comprobados. ParakeetCPU registrado,
sin hints ni texto esperado: lectura cruda y normalizada conservadas por separado.
Ventanas speaking±0,5s; origen streamReadyUtc aproximado, no timestamp ADC.
Índice público: astra-analysis126/RESULT_INDEX.json; detalle privado analysis126.json
en cada C03-voice123-private/C03-voice125-private bajo LOCALAPPDATA/BAXY.

| Ensayo/fase | Micrófono crudo | Loopback crudo |
|---|---|---|
|123 off-before|The file read failed because the content is invalid UTF-8.|The file read failed because the content is invalid UTF-8.|
|123 direct|vacío|The file|
|123 off-after|The file read failed because the content is invalid UTF 8.|The file read failed because the content is invalid UTF-8.|
|125 off-before|The file read failed because the content is invalid UTF-8.|The file read failed because the content is invalid UTF-8.|
|125 direct|The file read failed because the content is invalid.|The file read failed because the content is invalid.|
|125 off-after|The file read failed because the content is invalid UTF 8.|The file read failed because the content is invalid UTF-8.|

Normalizar no recupera los segmentos direct;123 devuelve «Yeah.»,125 conserva la
misma frase incompleta. En125 off-after, loopback normalizado pierde el8 que sí
recupera crudo: preservar la discrepancia del observador. Son controles consumidos,
no reserva humana ni una prueba de que no existiese otro sonido en la habitación.
La ausencia de UTF-8 coincide con cancelación registrada, no con fallo de Piper.

## 127: observar el par exacto que recibe el detector

Driver73458exit0/captura49180exit0. Una fase direct, misma frase, fuente119/124,
VoiceEngine/Piper/micrófono/altavoz reales. Wrappers llaman VAD y _looks_like_echo
originales y devuelven su resultado intacto; copian entradas/salidas a memoria y
las guardan al terminar. No App, LLM, enrutamiento de transcripciones ni efectos.
Instrumentación y fase inicial diferentes de125 pueden alterar tiempos: diagnóstico,
no comparación de aceptación. PREREG,RESULTS,EVENTS,AUDIO_RESULT en astra-voice127.

Speaking5,562s,0barge_in, ningún error de proveedor. Captura32,31s; volumen restaurado
exactamente a0/muted=true. Ambos procesos terminaron. Una ejecución sin corte no
borra123/125 ni demuestra estabilidad; no se repite hasta conseguir una favorable.

## 128: la referencia está presente, la similitud no basta

`scratchpad/c03-analyze-reference128.py` exit0, lectura offline3,34s. Observaciones
privadas127:263framesVAD,126llamadas de eco,27true.23frames cumplen energía y VAD;
10 de ellos devuelven false. Se compara la correlación máxima con el historial
exacto recibido y, como cota diagnóstica, con toda la captura externa de loopback.
En9/10 de esos falsos, incluso la búsqueda completa queda por debajo de0,55.
Ejemplos (índice VAD:score runtime/score captura completa):98:0,513/0,512;
105:0,463/0,465;152:0,453/0,454;183:0,465/0,521.203:0,502/0,565 es la excepción.
No demuestra por sí solo que todos sean eco: sí descarta que ampliar el retardo
recupere suficiente similitud en esos9frames. OBSERVATION_INDEX.json fija hashes.

La hipótesis siguiente es el cambio acústico entre altavoz y micrófono: un eco
filtrado/reverberado no es sólo una copia atenuada y retrasada. No bajar el umbral
para ajustar estos controles. Tampoco cambiar la duración de barge-in para ocultarlo.
El contador actual además no se reinicia en frames no vocales; queda observado en
voice.py:2352–2367, sin atribuirle125 ni parchearlo sin la secuencia de ese ensayo.

## Herencia y alternativa acotada

Inventario histórico consultado por título: barge_in.md,2026-06-04, diseño sin
medición de AEC (ya leído en123). Índice09.5 registra conservar_actual, no un motor
histórico mejor demostrado. El EchoCanceller actual en voice_aec.py:153–225 procesa
clips completos y reinicia NLMS; voice.py:2600 lo llama después de formar la emisión.
No puede corregir la señal que el VAD/barge-in ya consumió en voice.py:2342–2367.

Contraste primario consultado2026-09-07:
[Speex, cancelación de eco y diagnóstico](https://www.speex.org/docs/manual/speex-manual/node7.html)
describe filtrado adaptativo con referencia de reproducción, estado persistente,
sincronización y límites ante distorsión/no coincidencia de relojes. Es una alternativa
CPU para medir, no adoptada ni declarada superior por la documentación.
[WebRTC AEC3, interfaz fijada por revisión](https://webrtc.googlesource.com/src/+/b8a19df71c5bac5ca62d4dcc4515c9c74212c525/modules/audio_processing/aec3/echo_canceller3.h)
separa referencia de render y captura; es otra alternativa, coste Windows sin verificar.
El siguiente paso es contrastar un AEC existente en Windows sobre estas capturas,
con controles de voz cercana/silencio/doble voz y coste, antes de otra prueba física.
Si sustituye al NLMS actual, retirarlo: no sumar motores. No se descargó ni integró
ningún AEC en126–128. C03 sigue EN_CURSO con todos los pendientes del CHECKPOINT.
