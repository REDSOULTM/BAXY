# C03 — alcance de los vetos78 y enumeración79–80

78:9/10 útiles,112,17s,GPU3177,56MiB,RAM6293,96MiB,exit0,registro intacto. Se recuperan la explicación de la causa UTF8 y la pregunta por el nivel del volumen. Qwen3.5 sigue override; no UI/voz/audio físico/reserva humana ni promoción.

Fuente78: la aclaración clasificada usa el guard de invitación con su rol conocido, pero sigue rechazando familias ausentes del pedido. No se añade el verbo pon a una lista de frases. Conversación de conocimiento puede explicar un fallo anterior; las respuestas de operaciones siguen sujetas a su polaridad verificada. Sin cambios de prompts, selector ni historial.

Rojo C#:2 fail/60 pass/0 skips/4s; Python1 fail/21 deselected/0,50s. Después:1150 pytest pass/0 skips/5,78s;169 integración pass/0 skips/30s. Fast49738exit0,Release16,01s,0 avisos/errores. No Full durante reparación.

## t1 — útil

Entrada: Lee el archivo "C:/Users/usuario/AppData/Local/BAXY/C03-fixtures/ausente47.txt".

Final literal: No pude leer el archivo porque el sistema no soporta búsquedas con rutas absolutas.

Labels de progreso: []

## t2 — útil

Entrada: Lee el contenido del archivo "c03-lectura.txt" del sandbox.

Final literal: He leído el archivo "c03-lectura.txt" y su contenido es: "Lectura técnica C03: el color de control es turquesa."

Labels de progreso: []

## t3 — útil

Entrada: Read the file "c03-invalid-utf8.txt" in the sandbox.

Final literal: I tried to read the file "c03-invalid-utf8.txt" from the sandbox, but the operation failed because the file contains invalid UTF-8 characters.

Labels de progreso: []

## t4 — útil

Entrada: Lee el archivo "C:/Users/usuario/AppData/Local/BAXY/C03-fixtures/files53-outside/c03-sombra.txt".

Final literal: No pude leer el archivo porque el sistema no soporta búsquedas con rutas absolutas.

Labels de progreso: []

## t5 — útil

Entrada: Dime la hora.

Final literal: Son las 03:49.

Labels de progreso: []

## t6 — útil

Entrada: Why couldn't you read "c03-invalid-utf8.txt"?

Final literal: I couldn't read "c03-invalid-utf8.txt" because the file contains invalid UTF-8 characters, which caused the read operation to fail.

Labels de progreso: []

## t7 — útil

Entrada: Explain what a checksum is in one sentence.

Final literal: A checksum is a short, fixed-length string of characters calculated from a file's data to verify its integrity and detect any corruption or tampering.

Labels de progreso: []

## t8 — útil

Entrada: ¿Qué puedes hacer en este equipo?

Final literal: Puedo abrir y cerrar programas, mover ventanas, ajustar el audio y llevar tareas, además de otras cosas más.

Labels de progreso: []

## t9 — no útil

Entrada: Dime la hora, el audio y el uso de CPU.

Final literal: composition_failed

Labels de progreso: []

## t10 — útil

Entrada: Pon el volumen.

Final literal: ¿A qué nivel quieres que ponga el volumen?

Labels de progreso: []

## Diagnóstico de enumeración79–80

79 no reproduce el producto: usó el shortlist de herramientas de un turno de archivos, que no contenía las tres operaciones de observación. Su resultado null no sirve como baseline; se conserva el error metodológico y no se sobrescribe la evidencia.

80 aísla system.time/audio.status/system.status, todas existentes en el catálogo. Dime la hora, el audio y el uso de CPU queda en una sola cláusula y sale por el return de strict_request de effect_intent.py:12722 con sólo audio.status. El control52 que repite los verbos y el control de dos observaciones resuelven completos y en orden. unresolved_compound_contract no detecta la pérdida del nominal. No se llamó al modelo.

81 adapta la gramática existente _PURE_COORDINATED_STATUS_CLAUSE, no añade una capa. Incluye dominio sin palabra estado, uso de CPU/CPU usage y separadores de coma; sólo divide cuando TODA la cláusula es una enumeración de estados. Conserva el verbo rector. Rojo3 fail/6 pass/1615 deselected/1,17s; acotada corregida10 pass/1614 deselected/0,69s. Validación amplia y producto81 pendientes al escribir este informe.
