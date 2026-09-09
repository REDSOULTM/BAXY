# C03 — SpeexDSP aislado y contraste con el fallo125 — 2026-09-07

Fuente de producto119/124 intacta. No promoción ni aceptación final.129–133 son
procesamiento offline;134 es un candidato experimental físico por wrappers.

## Herencia, fuente y construcción

El NLMS existente procesa la emisión completa después del VAD/barge-in; véase
PRUEBAS_ECO126_128.md. Conservarlo en ese punto no resuelve el corte previo.
SpeexDSP se evalúa porque dispone de estado adaptativo y API C pequeña en CPU.
[Descarga oficial](https://www.speex.org/downloads/), consultada2026-09-07:
versión estable1.2.1. Archivo922584bytes, SHA256
8c777343e4a6399569c72abc38a95b24db56882c83dbdb6c6424a5f4aeb54d3d.
URL https://downloads.xiph.org/releases/speex/speexdsp-1.2.1.tar.gz.
urllib falló por certificado emisor; Invoke-WebRequest descargó con verificación
TLS normal. Extracción Python con filter=data, sin sobrescribir árboles previos.

Compilación MSVC14.44.35207 x64/O2/MD, config.h Windows de upstream, smallft,
mdf/fftwrap/smallft/preprocess/filterbank; sin cambios en el algoritmo upstream.
`scratchpad/c03-build-speex129.cmd`, exports c03-speex129.def. Exit0, DLL83456bytes.
Assets sólo en D:/BAXYRuntime/experiments/voice/speexdsp129, no instalados en BAXY.
COPYING leído: conservar avisos/licencia en eventual distribución. Hash de DLL
en astra-speex129/PREREG.json. No nueva dependencia Python ni uso de GPU.

[Manual primario de Speex](https://www.speex.org/docs/manual/speex-manual/node7.html):
se alimentan referencia reproducida y micrófono al filtro con estado persistente;
sincronización y retardo son condiciones, no garantías automáticas. Configuración
fija de prueba:16kHz, bloques512muestras/32ms, cola3200muestras/200ms. No se hizo
barrido de umbrales ni elección de la mejor configuración.

## 129/130: efecto aislado y fallo de configuración conservado

12936041exit0. Captura física127 existente, referencia alineada aproximadamente
por streamReadyUtc, sin búsqueda del mejor retardo. Controles separados: eco,
saludo español Piper120 añadido como voz cercana (pico0,03), y mezcla de ambos.
La voz cercana es sintética y etiquetada; no acredita entrada humana física.
Se conserva el estado del AEC durante cada señal, sin repetir el habla para entrenarlo.

129 AEC solo reduce energía del eco3,19dB y deja6frames consecutivos con VAD/energía.
La variante llamada aec_residual no aplicaba ganancia: desactivar denoise pone
gain2=1 también para el eco (fuente upstream preprocess.c:932–937). Error de la
configuración experimental, no del producto. Se preservan las dos salidas129.
130 corrige sólo eso siguiendo testecho.c: denoise predeterminado activo, AGC off,
supresión de eco predeterminada. Exit0. Reducción4,40dB, aún6frames consecutivos.
Media0,104ms/bloque, p990,127ms. La voz cercana sola pierde0,29dB; energía no prueba
que las palabras se conserven. Ninguna variante se acepta por esos números.

## 131: ASR y el detector existente

13114945exit0. ParakeetCPU sin hints sobre los mismos archivos y simulación del
contador/VAD/energía/guard existentes. El preprocesador introduce un bloque de
retardo: la comparación de eco usa el micrófono y referencia correspondientes.

| Caso | Crudo | AEC + guard |
|---|---|---|
|Eco127|0interrupciones, ASR reproduce toda la frase inglesa|0interrupciones, ASR vacío|
|Cercana sola|interrumpe190ms tras inicio añadido; «Hola, aquí Paxi. ¿En qué te puedo ayudar hoy?»|misma primera interrupción y misma transcripción|
|Mezcla|ASR vacío; primera interrupción286ms|«Hola, ¿en qué te puedo ayudar hoy?»; primera interrupción190ms|

El observador omite «aquí BAXY» en la mezcla; no adjudicar fidelidad completa.
La simulación mantiene la otra voz durante toda la frase inglesa: en vivo la
cancelación debería retirar el TTS al interrumpir. Eso requiere prueba posterior,
no permite convertir este resultado parcial en pase.127 ya era una corrida sin
corte;131 solo no demuestra resolver125.

## 132/133: contraste contra la captura que sí falló

132exit0 mantiene configuración130 y usa sólo direct125, desde ready hasta
speaking=false+1s. Excluye off-before: no entrenamiento con la frase anterior.
Reducción de eco3,35dB, siete frames consecutivos con VAD/energía sin guard.
Voz cercana sintética sola conserva actividad y pierde0,29dB. No se regeneró TTS.

13363428exit0 compara el mismo guard con/sin AEC sobre132. Ocho alineaciones
prefijadas del inicio de bloques:0,64,128,192,256,320,384,448muestras. No se elige
una favorable. Original interrumpe en8/8 entre3,807 y3,835s relativos a speaking;
AEC+guard en0/8. En las ocho lecturas crudas, ASR conserva la frase incompleta
«The file read failed because the content is invalid.»; procesado queda vacío.
Este vacío es deseado sólo en el canal de entrada para eco, nunca en la respuesta
de salida. Resultados literales en astra-speex133/RESULTS.json.

La referencia en vivo puede saltar o repetirse al leer latest512: las dos capturas
offline no prueban sincronización real. Por eso134 mide ese punto antes de integrar.

## 134: candidato físico prerregistrado

Prerregistro en astra-voice134/PREREG.json. Script c03-voice134.py y módulo aislado
speex_stream134.py. VoiceEngine/Piper reales, una frase inglesa consumida, modo
direct. Wrapper procesa micrófono antes del VAD y cálculo de energía; el guard ve
el par crudo del bloque anterior, por la latencia del preprocesador. Otro VAD y
contador originales observan los mismos bloques en sombra, sin cancelar.
Se conservan probabilidades, energías, referencias y ambas señales privadas.
No App/LLM/Core ni transcripciones enrutadas. El NLMS posterior sigue en la fuente:
no se evalúa aquí la fidelidad de transcripción interna ni se oculta esa duplicación
experimental; una adopción debe sustituirlo.

Captura31558/driver30068 terminaron exit0. Speaking5,75s,0barge_in real, ningún
error del proveedor. En265bloques, el contador original en sombra habría emitido
1barge_in. Son los mismos bloques observados, no otra reproducción elegida.
Captura36,41s, volumen restaurado exactamente a0/muted=true, sin procesos restantes.
En vivo process completo (con conversiones Python y planificación): media0,470ms,
p9910,580ms por bloque32ms; no confundir con0,10ms de llamadas C offline. La única
interrupción en sombra fue12:04:05.642752UTC. No se midió aquí GPU/RAM del producto.

13561032exit0 analiza sólo el WAV físico134 existente, sin nuevas reproducciones.
Micrófono crudo y normalizado: «The file read failed because the content is invalid
UTF 8.» Loopback crudo y normalizado: «The file read failed because the content
isn't valid UTF-8.» Se recuperan contenido, negación y UTF-8; conservar variantes
del observador. astra-analysis135/RESULT_INDEX.json fija el informe privado por hash.
La prueba respalda mover AEC antes del VAD/energía con el guard temporalmente
alineado. No acredita doble voz humana física, UI, estabilidad general ni cierre C03.

## Siguiente integración, todavía no realizada

Sustituir EchoCanceller NLMS de clips por un propietario AEC por sesión de captura,
liberado en finally por su mismo hilo. Procesar antes de VAD/segmentación/streaming
para que todas las rutas reciban la misma señal limpia. El guard usa par crudo
del bloque anterior por la latencia del preprocesador; no bajar umbrales.
Retirar el segundo AEC en _decode_utterance y sus arrays de referencia transportados
por _DecodeRequest/pre-roll; conservar una señal explícita de AEC aplicado para
el evento recognized. Los tests privados que llamaban a decode con referencia
vacía deben pasar el nuevo indicador, sin mantener una seam muerta de diagnóstico.
Probar estado/limpieza del hijo nativo, separación de sesiones y disponibilidad
real de DLL+loopback. Resolver el asset con mecanismo existente, conservar licencia
y receta reproducible antes de promover. No ejecutar Full hasta el candidato final.
