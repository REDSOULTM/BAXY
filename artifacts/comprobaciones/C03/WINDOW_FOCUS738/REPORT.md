# Corrección del rechazo de foco — candidato 738

BAXY rechazaba una respuesta correcta de K2 por el orden de la cópula y por
presentar el nombre observado entre paréntesis. El candidato reconoce ambas
formas sin reescribir la respuesta ni pedir otra inferencia. El nombre
descriptivo debe estar en los datos de la misma ventana: un alias inventado o
la identidad de otra aplicación no acreditan el foco.

También conserva títulos entre comillas y evita que un proceso llamado
«Is Active» borre el predicado de «Which window is active?». Las comprobaciones
mantienen la distinción entre foco y estado normal/maximizado/minimizado,
negación, preguntas, incertidumbre, otro sujeto y campos no booleanos.

| Validación | Resultado |
|---|---|
| Primer conjunto de 219 variantes, antes de editar | 40 pass, 179 fail |
| Todas las pruebas dueñas de ventanas, revisión final | 772 pass, 0 fail, 0 skips; 2,75 s |
| Declaraciones actuales del programa STT | 17 pass, 1 skip ambiental; 1,90 s |
| `scripts/test_source_quality.ps1`, revisión final | Fast verde; Release 1,74 s, 0 advertencias y 0 errores |

El salto de STT corresponde a entradas ausentes de una campaña ciega y no
acredita audio. Las pruebas originales no se relajaron. Fast1 también pasó,
pero corresponde a la revisión anterior al ajuste de títulos entre comillas;
Fast2 acredita la fuente final.

El replay recorrió 215 registros capturados, equivalentes a 205 combinaciones
distintas de fuente, pregunta, respuesta y hechos. Nueve combinaciones son de
ventanas. Cambió una respuesta veraz de H0104/K2: antes `missing_fact`, ahora
aceptada por el validador completo. Aparece en seis registros duplicados;
no son seis aciertos independientes. Los otros resultados se conservaron.

Siguen rechazadas otras dos respuestas fieles de737: windows-focus-mixed con
el prompt de BAXY y windows-focus-reference-es con petición directa. Están
identificadas en REPLAY.json y en las respuestas privadas. Esta corrección no
cierra toda la familia de ventanas ni sustituye una prueba integrada nueva.

La fuente y las pruebas quedan como candidato en el árbol de trabajo. Las
copias `.py.txt` conservan sus bytes para revisión y recuperación. No se
promueve el modelo ni se adopta el conjunto todavía: las validaciones usan el
WIP previo de705,712 y730, y Full5 continúa rojo en los límites originales de
packaging (45 s) y salida del sidecar (3 s). Las declaraciones actuales de STT
describen ese árbol; los sellos de campañas históricas permanecen intactos.

La siguiente prioridad es resolver esos dos bloqueos de Full antes de acumular
más fuentes pendientes de adopción. C03 permanece activo, con26 requisitos de
encuesta cubiertos y716 abiertos. No se añadió cobertura con este replay.

Las preguntas, respuestas literales, hechos y validaciones antes/después están
en `%LOCALAPPDATA%/BAXY/C03-window-focus738-private/RESPUESTAS.md` y `replay.json`.
Los archivos públicos RESULT, REPLAY, PROGRAM y PINS vinculan las comprobaciones
con las fuentes exactas. No se ejecutaron modelos, UI ni voz en este tramo.
