# C03 — validación integrada del veto74

6/10 útiles frente a5/10 en72. Se recupera t3 con exactamente el primer borrador que72 vetó. Fuente63 + Python74; Qwen3.5 sigue como override sin promoción. Selector/historial/prompts intactos. 123,12s, GPU3177,56MiB, RAM6983,55MiB, exit0; registro intacto. No UI/voz/audio físico ni reserva humana.

Aceptado el arreglo local de falsos vetos: t3 publica la causa UTF8 real. C03 completo sigue abierto. t6/t7 fallan en conversation_reply con HTTPError y t10 en turn_preparation con HTTPError. El hook47 no capturaba excepciones;75 instrumenta ese punto antes de inferir una causa. t9 sigue vetado por hechos adicionales: no se ha relajado extra_claim.

## t1 — útil

Entrada: Lee el archivo "C:/Users/usuario/AppData/Local/BAXY/C03-fixtures/ausente47.txt".

Final literal: No pude leer el archivo porque el sistema no soporta búsquedas con rutas absolutas.

Labels de progreso publicados: []

## t2 — útil

Entrada: Lee el contenido del archivo "c03-lectura.txt" del sandbox.

Final literal: He leído el archivo "c03-lectura.txt" del sandbox. El contenido es: "Lectura técnica C03: el color de control es turquesa."

Labels de progreso publicados: []

## t3 — útil

Entrada: Read the file "c03-invalid-utf8.txt" in the sandbox.

Final literal: I tried to read the file "c03-invalid-utf8.txt" from the sandbox, but the operation failed because the file contains invalid UTF-8 characters.

Labels de progreso publicados: []

## t4 — útil

Entrada: Lee el archivo "C:/Users/usuario/AppData/Local/BAXY/C03-fixtures/files53-outside/c03-sombra.txt".

Final literal: No pude leer el archivo porque el sistema no soporta búsquedas con rutas absolutas.

Labels de progreso publicados: []

## t5 — útil

Entrada: Dime la hora.

Final literal: Son las 03:21.

Labels de progreso publicados: []

## t6 — no útil

Entrada: Why couldn't you read "c03-invalid-utf8.txt"?

Final literal: I couldn't read the file because the request interpretation failed.

Labels de progreso publicados: []

## t7 — no útil

Entrada: Explain what a checksum is in one sentence.

Final literal: I cannot explain what a checksum is because the request failed due to an interpretation error.

Labels de progreso publicados: []

## t8 — útil

Entrada: ¿Qué puedes hacer en este equipo?

Final literal: Puedo abrir y cerrar programas, mover ventanas, ajustar el audio y llevar tareas, además de otras cosas más.

Labels de progreso publicados: []

## t9 — no útil

Entrada: Dime la hora, el audio y el uso de CPU.

Final literal: composition_failed

Labels de progreso publicados: []

## t10 — no útil

Entrada: Pon el volumen.

Final literal: composition_failed

Labels de progreso publicados: []

## Validación de fuente

Python312 -m pytest tests/test_compose_contract.py tests/test_c03_request_preservation.py tests/test_turn_policy.py -q:1105 pass/0 skips/5,67s. Fast70202exit0, Release2,86s, 0 avisos/errores. Full no ejecutado durante reparación. Los logs están junto a este panel.
