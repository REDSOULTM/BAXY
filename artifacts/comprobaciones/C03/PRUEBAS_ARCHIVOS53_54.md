# C03 — lecturas de archivo, tramos53–54

Cinco controles técnicos consumidos; no son reserva humana ni prueba de UI/voz.
La confirmación del dueño sobre tres turnos ingleses sigue limitada a ADMISIBILIDAD_DUENO_2026-09-06.md; estos archivos no proceden de ella.

Se prepararon archivos UTF8, UTF8 inválido y dos homónimos dentro/fuera del sandbox. CASES.json conserva rutas, contenido esperado y hashes. No se solicitó escribir ni borrar.

## files53-baseline: 1/5 útiles

68.09s; GPU3497.56MiB; RAM5328.06MiB; exit0; registro intacto=True.

Evidencia: [paired.json](astra-files53-baseline/paired.json), [CASES.json](astra-files53-baseline/CASES.json).

### t1

Entrada: Lee el archivo "C:/Users/usuario/AppData/Local/BAXY/C03-fixtures/ausente47.txt".

Final (published_final): ¿Cuál es la ruta del archivo que deseas leer?

Adjudicación: No útil: repide ruta ya proporcionada o pide un ID interno; no leyó el archivo.

### t2

Entrada: Lee el contenido del archivo "c03-lectura.txt" del sandbox.

Final (published_final): ¿Cuál es la ruta del archivo que deseas leer?

Adjudicación: No útil: repide ruta ya proporcionada o pide un ID interno; no leyó el archivo.

### t3

Entrada: Read the file "c03-invalid-utf8.txt" in the sandbox.

Final (published_final): ¿Cuál es el ID del recurso del archivo que deseas leer?

Adjudicación: No útil: repide ruta ya proporcionada o pide un ID interno; no leyó el archivo.

### t4

Entrada: Lee el archivo "C:/Users/usuario/AppData/Local/BAXY/C03-fixtures/files53-outside/c03-sombra.txt".

Final (published_final): ¿Cuál es la ruta del archivo que deseas leer?

Adjudicación: No útil: repide ruta ya proporcionada o pide un ID interno; no leyó el archivo.

### t5

Entrada: Dime la hora.

Final (published_final): 01:06

Adjudicación: Útil: hora observada y sesión recuperada.

## files53-candidate: 1/5 útiles

76.06s; GPU3497.56MiB; RAM5197.95MiB; exit0; registro intacto=True.

Evidencia: [paired.json](astra-files53-candidate/paired.json), [CASES.json](astra-files53-candidate/CASES.json).

### t1

Entrada: Lee el archivo "C:/Users/usuario/AppData/Local/BAXY/C03-fixtures/ausente47.txt".

Final (published_final): No pude leer el archivo porque el plan está incompleto.

Adjudicación: No útil: el error interno no explica el límite solicitado; no acredita búsqueda global ni identidad exterior.

### t2

Entrada: Lee el contenido del archivo "c03-lectura.txt" del sandbox.

Final (composition_failed): composition_failed

Adjudicación: No útil: el error interno no explica el límite solicitado; no acredita búsqueda global ni identidad exterior.

### t3

Entrada: Read the file "c03-invalid-utf8.txt" in the sandbox.

Final (composition_failed): composition_failed

Adjudicación: No útil: falta prosa final que conserve la causa real del archivo UTF8 inválido.

### t4

Entrada: Lee el archivo "C:/Users/usuario/AppData/Local/BAXY/C03-fixtures/files53-outside/c03-sombra.txt".

Final (published_final): No pude leer el archivo porque el plan está incompleto.

Adjudicación: No útil: el error interno no explica el límite solicitado; no acredita búsqueda global ni identidad exterior.

### t5

Entrada: Dime la hora.

Final (published_final): 01:11

Adjudicación: Útil: hora observada y sesión recuperada.

## files53-boundary: 1/5 útiles

87.12s; GPU3497.56MiB; RAM5381.73MiB; exit0; registro intacto=True.

Evidencia: [paired.json](astra-files53-boundary/paired.json), [CASES.json](astra-files53-boundary/CASES.json).

### t1

Entrada: Lee el archivo "C:/Users/usuario/AppData/Local/BAXY/C03-fixtures/ausente47.txt".

Final (published_final): No pude leer el archivo porque el resultado no se verificó.

Adjudicación: No útil: el error interno no explica el límite solicitado; no acredita búsqueda global ni identidad exterior.

### t2

Entrada: Lee el contenido del archivo "c03-lectura.txt" del sandbox.

Final (composition_failed): composition_failed

Adjudicación: No útil: el provider sí leyó y el borrador fue fiel, pero el veto del filename impidió publicarlo.

### t3

Entrada: Read the file "c03-invalid-utf8.txt" in the sandbox.

Final (composition_failed): composition_failed

Adjudicación: No útil: falta prosa final que conserve la causa real del archivo UTF8 inválido.

### t4

Entrada: Lee el archivo "C:/Users/usuario/AppData/Local/BAXY/C03-fixtures/files53-outside/c03-sombra.txt".

Final (published_final): No pude leer el archivo porque el resultado no se verificó.

Adjudicación: No útil: el error interno no explica el límite solicitado; no acredita búsqueda global ni identidad exterior.

### t5

Entrada: Dime la hora.

Final (published_final): 01:20

Adjudicación: Útil: hora observada y sesión recuperada.

## files54-literals: 2/5 útiles

74.09s; GPU3497.56MiB; RAM5322.07MiB; exit0; registro intacto=True.

Evidencia: [paired.json](astra-files54-literals/paired.json), [CASES.json](astra-files54-literals/CASES.json).

### t1

Entrada: Lee el archivo "C:/Users/usuario/AppData/Local/BAXY/C03-fixtures/ausente47.txt".

Final (published_final): No pude leer el archivo porque el resultado no se verificó.

Adjudicación: No útil: el error interno no explica el límite solicitado; no acredita búsqueda global ni identidad exterior.

### t2

Entrada: Lee el contenido del archivo "c03-lectura.txt" del sandbox.

Final (published_final): El contenido del archivo "c03-lectura.txt" es: "Lectura técnica C03: el color de control es turquesa."

Adjudicación: Útil: contenido UTF8 real; búsqueda y lectura comparten la identidad verificada. Sin aviso verbal adicional.

### t3

Entrada: Read the file "c03-invalid-utf8.txt" in the sandbox.

Final (composition_failed): composition_failed

Adjudicación: No útil: falta prosa final que conserve la causa real del archivo UTF8 inválido.

### t4

Entrada: Lee el archivo "C:/Users/usuario/AppData/Local/BAXY/C03-fixtures/files53-outside/c03-sombra.txt".

Final (published_final): No pude leer el archivo porque el resultado no se verificó.

Adjudicación: No útil: el error interno no explica el límite solicitado; no acredita búsqueda global ni identidad exterior.

### t5

Entrada: Dime la hora.

Final (published_final): 01:26

Adjudicación: Útil: hora observada y sesión recuperada.
