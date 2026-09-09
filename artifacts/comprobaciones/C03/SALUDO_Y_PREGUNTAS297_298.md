# C03 — publicación de respuestas con preguntas posteriores

Estado EN_CURSO. No aceptación final ni promoción de modelo.

297 reproduce sin inferencia nueva las respuestas originales296 mediante chat
real y traza cada predicado. La única causa verdadera del rechazo de ambos
saludos es visible_reply_restates_the_request. El mismo guard también descarta
la primera respuesta útil sobre Lima; su reintento termina con «Lima» solamente.
El mensaje genérico de excepción «vacía o repetida» ocultaba la causa concreta;
audit_reason fue shaped_presentation. RESULT297 conserva todos los predicados.

298 sustituye la comparación de palabras de toda la respuesta por la comparación
de cada pregunta, delimitada por signos interrogativos y límites de oración.
No cambia el umbral, los demás verificadores, la generación ni el prompt.
Conserva los siete controles históricos de preguntas devueltas sin contestar.
Diez controles adicionales abarcan el saludo real, Lima, conocimientos, otro
nombre, respuestas en inglés y preguntas repetidas precedidas de otras frases.
El control chat real exige conservar la respuesta con un solo envío al modelo.

Antes:6 fallos,4 pass,925 deselected,3,37s. Después: las tres suites dueñas
test_compose_contract.py, test_llm_transport.py y test_turn_policy.py dan
1022 pass,0 skips,5,65s. NATIVE_RESULT298 repite las tres entradas296 con
modelo registrado2507, mismo servidor63490, primer payload idéntico en los
tres casos. Replay de respuestas originales y nueva inferencia coinciden:

- «me llamo emmanuel, dime hola emmanuel» → «Hola Emmanuel, ¿cómo estás? 😎».
- «me llamo Albeda» → «¡Hola Albeda! ¿Cómo estás hoy? 😎».
- «my favorite city is Lima» → «Lima's got that cool mix of old-world charm and
  modern vibes, right? 🌆 What’s your favorite spot there?».

Todas publicadas al primer intento. Ninguna escritura de memoria ni otro efecto.
Esto NO demuestra la ruta completa del saludo: AskToSave todavía interceptaba
la entrada en MainWindowViewModel. Tramo299 estudia esa frontera, conservando
las barreras de memoria explícita que ya existen en ejecución simple y planes.

Fast298 inicial pasó las fases estáticas y falló al copiar baxy-core.exe, bloqueado
por Core95028 de la UI293 abierta. No es verde ni se omite el fallo: fast.log
se conserva. Se verificaron identidad/creación de App97436, /slots libre y sólo
request_ids6/10 del agente, se guardaron seis logs privados en snapshot298 y
se detuvo exclusivamente ese árbol para recompilar y reabrir el producto.
Cuestionario101140 intocado. Validación integrada tras recompilar pendiente.

Herencia: Carter_v2/LLM_CONTEXT_MEMORY_REPORT.md distingue contexto conversacional,
proveniencia y persistencia confirmada, y propone guardas estructurales frente
a salidas inútiles. Su fallback visible fijo sigue prohibido y no se reutiliza.
La investigación de modelo/formato existente sigue vigente: aquí se cambia el
alcance determinista de una pregunta, sin otra configuración o prompt.
