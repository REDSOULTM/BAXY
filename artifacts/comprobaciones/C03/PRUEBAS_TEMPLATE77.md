# C03 — template integrado77

7/10 útiles frente a6/10 en74/75. Se elimina el rechazo HTTP y se recupera checksum. 125,11s,GPU3177,56MiB,RAM6765,18MiB,exit0,registro intacto. Cada paquete HTTP real contiene como máximo un system. Qwen3.5 sigue en override; no promoción ni UI/voz/audio/reserva humana.

t6: el chat nativo explica UTF8 correctamente; C# lo veta como looks_like_failure y los tres intentos de recomposición Python como asserted_failure. t10: la aclaración nativa pregunta el nivel, pero C# la rechaza como unsolicited_catalog; el fallback pierde el dato pendiente y pregunta por dispositivo. t9: el reconocedor determinista explicit_effects selecciona sólo audio.status; no es una pérdida introducida por el modelo. Estas tres causas siguen abiertas.

Four owner suites:1149 pass/0 skips/5,62s; Fast31677exit0,Release1,51s,0 avisos/errores. Logs preservados junto al panel. No Full durante reparación.

## t1 — útil

Entrada: Lee el archivo "C:/Users/usuario/AppData/Local/BAXY/C03-fixtures/ausente47.txt".

Final literal: No pude leer el archivo porque el sistema no soporta búsquedas con rutas absolutas.

Labels de progreso: []

Borrador (error, sin veto Python): No pude leer el archivo porque el sistema no soporta búsquedas con rutas absolutas.

## t2 — útil

Entrada: Lee el contenido del archivo "c03-lectura.txt" del sandbox.

Final literal: He leído el archivo "c03-lectura.txt" y su contenido es: "Lectura técnica C03: el color de control es turquesa."

Labels de progreso: []

Borrador (status, sin veto Python): He leído el archivo "c03-lectura.txt" y su contenido es: "Lectura técnica C03: el color de control es turquesa."

## t3 — útil

Entrada: Read the file "c03-invalid-utf8.txt" in the sandbox.

Final literal: I tried to read the file "c03-invalid-utf8.txt" from the sandbox, but the operation failed because the file contains invalid UTF-8 characters.

Labels de progreso: []

Borrador (error, sin veto Python): I tried to read the file "c03-invalid-utf8.txt" from the sandbox, but the operation failed because the file contains invalid UTF-8 characters.

## t4 — útil

Entrada: Lee el archivo "C:/Users/usuario/AppData/Local/BAXY/C03-fixtures/files53-outside/c03-sombra.txt".

Final literal: No pude leer el archivo porque el sistema no soporta búsquedas con rutas absolutas.

Labels de progreso: []

Borrador (error, sin veto Python): No pude leer el archivo porque el sistema no soporta búsquedas con rutas absolutas.

## t5 — útil

Entrada: Dime la hora.

Final literal: Son las 03:35.

Labels de progreso: []

Borrador (status, sin veto Python): Son las 03:35.

## t6 — no útil

Entrada: Why couldn't you read "c03-invalid-utf8.txt"?

Final literal: composition_failed

Labels de progreso: []

Borrador (conversation, asserted_failure): I couldn't read that file because it contains invalid UTF-8 characters, which caused the error.

Borrador (conversation, asserted_failure): I could not read the file because the situation provided does not include any information about the file's content or the reason for the failure.

Borrador (conversation, asserted_failure): I couldn't read the file because it contains invalid UTF-8 characters that my system cannot process.

Borrador (status, sin veto Python): I'm still working on reading that file.

## t7 — útil

Entrada: Explain what a checksum is in one sentence.

Final literal: A checksum is a short, fixed-length string of characters calculated from a file's data to verify its integrity and detect any corruption or tampering.

Labels de progreso: []

## t8 — útil

Entrada: ¿Qué puedes hacer en este equipo?

Final literal: Puedo abrir y cerrar programas, mover ventanas, ajustar el audio y llevar tareas, además de otras cosas más.

Labels de progreso: []

Borrador (conversation, sin veto Python): Puedo abrir y cerrar programas, mover ventanas, ajustar el audio y llevar tareas, además de otras cosas más.

## t9 — no útil

Entrada: Dime la hora, el audio y el uso de CPU.

Final literal: composition_failed

Labels de progreso: []

Borrador (status, extra_claim): La hora es 10:42. El volumen está al 100% y el audio no está silenciado. El uso de CPU es del 2%.

Borrador (status, extra_claim): La hora es 10:42, el volumen está al 100% y el uso de CPU es del 2%.

Borrador (status, sin veto Python): Estoy revisando los datos actuales para darte la hora, el nivel de audio y el uso de CPU.

## t10 — no útil

Entrada: Pon el volumen.

Final literal: ¿A qué dispositivo quieres ajustar el volumen?

Labels de progreso: []

Borrador (clarification, sin veto Python): ¿A qué dispositivo quieres ajustar el volumen?
