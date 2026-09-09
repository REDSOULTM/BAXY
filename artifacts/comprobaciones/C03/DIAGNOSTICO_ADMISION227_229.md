# C03 —227–229: confirmación de interrupción y conservación del inicio

227 reproduce los cuatro controles humanos RAW213 sobre fuente225; muestras,
rangos y cancelaciones coinciden exactamente con226. Un observador del ducker
lee cinco escalares del frame real _capture_loop cuando begin_utterance se
ejecuta. Las cuatro aperturas espurias empiezan en frame96, speaking=True,
barge_frames=1, probabilidad0.92497462, energía0.00940122, noise_floor0.00143617.
La inserción humana comienza después, muestra59109. Esta causa se establece
antes del cambio de fuente; no se infiere sólo del texto ASR.

228 añade la condición de tres bloques también a la apertura. Dos tests nuevos
fallan primero sobre225 (1/2bloques abrían transcripción), después125tests
correspondientes pasan; Ruff verde. Replay228 de los1316frames221 mantiene
cero segmentos. Sin embargo229 detecta pérdida de la palabra «Se» en el humano0
con eco: segmento inicial pasa de88576 a95232,6656muestras/416ms menos. El
reconocedor responde «Recomienda…» frente a «Se recomienda…». La candidata228
queda rechazada; su snapshot y resultados se conservan.

Los otros tres controles RAW conservan contenido humano y pierden el segmento
espurio; las cuatro voces solas quedan idénticas. No se usa esa mejora parcial
para aceptar una pérdida humana. Las cancelaciones son idénticas en8/8.

Siguiente230: usar el búfer de utterance existente como candidato provisional,
sin ducking, streaming ni ASR hasta confirmar los tres bloques; conservar su
inicio aunque haya energía baja intermedia. Descartar al finalizar si nunca se
admite. La salida que termina debe permitir admitir voz humana posterior. No
ampliar pre-roll o umbrales ni añadir otro capturador/cola paralela.
