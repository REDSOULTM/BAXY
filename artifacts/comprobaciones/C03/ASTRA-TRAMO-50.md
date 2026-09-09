# C03 — tramo 50: progreso nativo, dos variantes rechazadas

Estado: diagnóstico medido; **ninguna variante adoptada**. Fuente49 permanece.
C03 EN_CURSO. No cambios de producto, modelo, prompts, catálogo ni registro.

## Captura y control

Se invoca exactamente el compositor de _emit_early_turn_signal: objetivo literal,
intent=status, situation con kind=status, cause=acting y polarity=success.
No contexto ni observaciones. El instrumento captura cada payload y respuesta
antes de validación, recorte y reintento. Se reutilizan cinco peticiones técnicas
consumidas de clock49: triple hora/audio/CPU, pares ES/EN/mezcla y hora/CPU.

El payload real lleva dos mensajes: USER_MESSAGE_PROMPT como system y, en user,
texto original, situation={kind:status,state:in progress} e instrucción de idioma.
Temperatura0, max_tokens256, cache_prompt=false, enable_thinking=false.
El system ya exige hechos de situation y no presentar lo pendiente como terminado.
No hay hora14:30/14:32, CPU45% ni otra observación en la entrada.

astra-progress-purpose50, sesión45073 exit0: 10,67 s, GPU3497,56 MiB,
RAM2842,13 MiB, registro intacto. El producto aislado reproduce los borradores
del producto49: por ejemplo, el triple primero inventa14:32/45%; el reintento
publica14:30/45% porque añade «en curso». La primera transformación errónea es
la generación nativa. El verificador permite la segunda porque una palabra de
progreso en la primera frase basta, aunque esa misma frase afirme mediciones.

posts.jsonl conserva los payloads/respuestas originales, published.json la salida
del compositor con guardas. No llamar a esta primera fase «modelo sin guardas»:
las respuestas brutas están capturadas antes de ellas, pero la publicación sí las usa.

## Dos diferencias aisladas, ambas rechazadas

1. Repetición nativa de cada primer payload cambiando sólo kind=status por
   kind=progress, sin guardas ni reintentos. No mejora útil: el triple mantiene
   14:32/45%, el par español declara hora no disponible, la mezcla pregunta la
   hora y el caso CPU pide al usuario que se la diga. No se cambia la fuente.
2. astra-progress-pending50: mover el texto original a situation.pendingRequest,
   conservando kind=status y state=in progress. Misma instrucción system,
   idioma, modelo, plantilla, sampler y presupuesto. Es el concepto de petición
   pendiente heredado del compositor de confirmación, aplicado sólo en la prueba
   nativa. Cinco respuestas, ninguna adecuada: inventa horas, CPU45%, volumen60%
   o estado de audio sin observaciones. 5,92 s, GPU3497,56 MiB, RAM2819,57 MiB,
   registro intacto, exit0. No se promueve.

No hubo efectos sobre el PC ni uso de reserva humana. No es UI/voz ni benchmark
comparativo de latencia. Los scripts son c03-progress-purpose50.py y
c03-progress-pending50.py; los PREREG y posts conservan la comparación completa.
Los procesos propios terminaron y cerraron su servidor local.

## Decisión y siguiente paso

Tras dos cambios de representación sin mejora, abandonar esa estrategia. No
seguir cambiando nombres de campos ni repetir el panel por azar. La siguiente
hipótesis debe separar explícitamente la tarea de narrar progreso de contestar
la consulta original, con una instrucción de rol acotada y controles válidos/
inválidos que prueben que no se publican observaciones aún inexistentes. Heredar
lo ya investigado en INVESTIGACION_MODELO_C03.md y la narración del compositor;
no usar una frase visible fija ni retirar la ruta de progreso.

La app sigue rechazando «No hay fallos reportados» como reversed_result por
Contains("fallo"). Ese segundo bloqueo está reproducido en48 y49, con hechos y
borradores fieles: reparar su alcance/polaridad preservando fallos verdaderos.
La lectura de rutas de archivo47, reserva100, UI/voz final, contratosC04–C09,
Full final y publicación fuera de main siguen pendientes. No se aplazan ni se
declara C03 terminado. No hay bloqueo externo ni pregunta pendiente al dueño.
