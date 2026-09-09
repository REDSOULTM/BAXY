# C03 — resultado169–170 y siguiente diagnóstico

Fuente164 permanece intacta y validada. No procesos propios activos.
169 repite el sidecar168 con una observación nueva: al primer barge_in, después
de cancelar y reenviar el evento original, copia una vez los arrays del frame
y el ring. No hace trabajo adicional por frame antes de la decisión.
Driver96694/captura92547 exit0. Cierre57,719s; captura77,03s, restauración exacta
de volumen0/mutedtrue y todos los hilos terminados.

El primer corte ocurre durante el saludo: speaking1,485s, sin error TTS.
Después hay otros eventos wake y una transcripción «Yeah.»; no se ejecutan
operaciones por esas transcripciones en este conductor. El wake heredado usa
un manifiesto sin calibración aprobada: estos eventos no acreditan uso humano.
Las salidas posteriores al snapshot no son controles independientes intactos.

170 analiza los arrays exactos del primer corte. VAD0,8479277; energía limpia
0,00687914; suelo de ruido0,00108865; tercer frame de interrupción. La historia
usada por el guard coincide bit a bit con el ring. Correlación máxima0,3497310,
retardo903muestras (56,44ms): está dentro de la ventana de250ms. Buscar en todo
el ring de4s no obtiene mejor coincidencia. No hay prueba de historia omitida
o desfase fuera de la ventana en ESTE frame. Tampoco se prueba sólo con esto
ausencia de voz cercana. No bajar el umbral0,55 para aprobar este ejemplo.

Siguiente: contrastar por qué AEC y la discriminación de doble habla no separan
la salida propia en este inicio. Partir de astra-analysis170/RESULTS.json y sus
inputs privados fijados. La rama de hipótesis de ampliar ventana/reordenar
historia carece de apoyo en este frame; no repetir los barridos de fases151.
No editar DSP hasta establecer un mecanismo y un contraste que conserve una
interrupción real. C03 sigue abierto: audio, reserva100, promoción, continuidad,
Full final y publicación. Véase HANDOFF.md para el estado compacto vigente.
