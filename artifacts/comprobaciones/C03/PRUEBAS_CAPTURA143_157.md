# C03 — captura continua, COM y eco físico — 2026-09-07

**EN_CURSO.** Fuente147 mejora dos fallos demostrados: referencia discontinua y
apertura WASAPI sin COM en el worker. No resuelve por prueba causal el corte148.
No promoción, Full, UI ni aceptación de entrada humana en este tramo.

## Fuente y validación

143: `voice_capture.py` usa callback WASAPI/ADC/cola64; `voice_aec.py` ring4s,
origen ADC y lectura por índice; `voice.py` ancla una vez y avanza512muestras.
No cambia Speex ni umbrales. Cola/ring/esperas limitados, overflow explícito,
cancelación y cierre de dispositivos. El PCM inyectado no inventa referencia
de escritorio.147 rodea open/start/close con `_com_apartment` heredado y ExitStack.
El stream se crea en `__enter__` en el hilo dueño.145/146 prueban la diferencia
con/sin COM; fuentes y límites en ASTRA-TRAMO-147.md.

Python del runtime, `-m pytest tests/test_voice_capture_clock.py
tests/test_speex_aec.py tests/test_mind_voice_runtime.py tests/test_piper_tts.py
tests/test_neural_speech_output.py tests/test_goal06_voice.py
tests/test_asset_resolution.py -q`: **148pass,0skips,11,29s**, sesión17590exit0.
`scripts/test_source_quality.ps1`: **Fast77674exit0**, Release1,39s,0avisos/errores.
Fuente143 anterior:148pass/0skips/13,12s y Fast17999exit0/Release2,85s.
Snapshot147 de14ficheros/logs, INDEX.json con huellas; no repetir verdes por rutina.

## Observaciones físicas, todas conservadas

Mismo endpoint a0,30/desmute durante pruebas, restauración exacta a0/muted=true
en todas; sin pérdidas en observadores. Capturas privadas. El driver usa VoiceEngine
sin App/LLM/Core ni ejecución de operaciones del texto reconocido.

| Prueba | Observación dentro del pipeline | Speaking / barge | Resultado |
|---|---|---|---|
|144|Ninguna|No llegó a hablar|Worker falla al start, driverexit1; captura24,08s/exit0|
|148|Ninguna|1,609s /1|Corte, driver y capturaexit0; captura33,62s|
|149|Tap AEC/VAD/guard sin alterar retornos|5,282s /0|264frames guardados; captura38,05s|
|152|Tap149 + copia del PCM generado,3inicios|5,391/5,562/5,219s;0/0/0|Todos conservados; captura56,80s|
|153|Sólo copia del PCM generado una vez por frase|5,375/5,109/5,422s;0/0/0|Sin taps por frame; captura49,45s|
|154|Tap152,6fixtures ES/EN de120|4,750/2,562/2,562/5,250/2,594/4,938s;0en6|Dos voces y contenido variado; captura75,01s|

Los wrappers149/152/154 retornan resultados originales; no ejecutan otro VAD.
Pueden alterar temporización.153 conserva sólo un observador al terminar síntesis.
Los reinicios recrean AEC/captura, **no** el objeto Silero del engine cargado.

150 verifica bit a bit continuidad entre historias149. Desfase mic−ref global
835muestras/52,19ms y correlación0,331: no identifica causa exacta de148.
151 desplaza ambos arrays149 juntos en8fases0–448step64 con nuevos estados DSP;
0barge en8/8, fase0 produce PCM limpio bitidéntico. Componente offline; no reproduce
toda la segmentación/reset/UI. Su PREREG explicita esos límites.

152 guarda para idéntico texto tres PCM generados de4,403/4,600/4,252s con huellas
distintas.153 también conserva sus tres PCM. **Repetir texto no fija el audio.**
No atribuir diferencia entre148 y149 sólo a instrumentación, ni sustituir el fallo
por los pases posteriores. Cambiar umbrales o volver a probar a ciegas no está justificado.

## Contenido físico156 y corte157

156 usa Parakeet registrado CPU6threads, sin hints, sobre WAV154 privado y cada
PCM generado; analiza crudo y normalizado conservando ambos. Sesión34732exit0.

| Fixture de regresión | Lectura del micrófono físico |
|---|---|
|Saludo BAXY|Saludo completo; ASR escribe Paxi/Baxi, generado también Baxi|
|It is07:14|Seven fourteen en ambas variantes|
|Son las07:13|Siete trece en ambas variantes|
|Error UTF-8|Normalizado recupera “The file read failed because the content is invalid UTF8”; crudo escribe “re” por “read”|
|Son las07:15|Crudo recupera siete quince; normalizado omite quince. Loopback normalizado y generado sí lo recuperan|
|Archivo no encontrado|Frase completa y ambas negaciones en todas las pistas|

Hay variantes del ASR; no se presenta como transcripción perfecta6/6 ni como
entrada humana aceptada. “in valid” aparece en algunas lecturas de “invalid” y
queda conservado. Los resultados no justifican corregir texto generado por regla.

157 examina el corte148 sin nueva reproducción, exit0: micrófono sólo “The file” /
“The file we”, loopback “The file re” / vacío. El audio quedó truncado; no aparece
otra intervención inteligible que explique el barge. Eso no prueba ausencia de
habla/ruido cercano ni recupera los bloques internos que148 no grabó.

## Estado para continuar

Fuente147 permanece candidata. No otra variación del filtro/umbral ni repetir
la misma frase buscando un pase. Siguiente medición útil: producto/UI integrado
con capturas físicas y, si reaparece corte, conservar el PCM generado y los bloques
internos de ese caso antes de cambiar el mecanismo. Los fixtures154 tienen audio
reproducible y ya cubren ambas voces para contraste. UI, entrada humana/doble habla,
sesión prolongada y runtime final aún deben verificarse;148 sigue abierto.

Revisión de reserva155 ya vio índices155–238: ahora239vistos, sin selección ni
inferencia; duplicados redactados, truncados y contexto pendiente se documentan
en RESERVA_PREVIEW155.md. Sólo41/102/128 tienen confirmación del dueño. Cierre C03
sigue exigiendo100literales humanos congelados y ocho rutas, registro/regresión,
continuidadC04–C09, Full íntegro y publicación fuera de main.
