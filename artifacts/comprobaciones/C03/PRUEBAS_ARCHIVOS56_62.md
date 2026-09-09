# C03 — lectura y causas: tramos56–62

Desarrollo técnico consumido. No reserva humana, UI ni audio físico.

56 copia la identidad única verificada;57 conserva error de operación;58 acepta modales negativos sin exigir primera persona. Producto58:3/5 útiles, no cierre de C03.166 integración pass/0 skips/14s;3140 pytest pass/121 subtests/0 skips/45,45s;Fast58 verde, Release16,80s,0 avisos/errores.

## files56-identity

Resultado: {"exitCode": 0, "stopReason": null, "elapsedSeconds": 79.08, "gpuPeakMiB": 3497.55859375, "gpuAttributionAvailable": true, "ramPeakMiB": 5041.58203125, "registrationUnchanged": true}

### t1

Entrada: Lee el archivo "C:/Users/usuario/AppData/Local/BAXY/C03-fixtures/ausente47.txt".

Final (published_final): No pude buscar el archivo porque no hay datos sobre la búsqueda en el sistema.

Útil: no. Progreso visible: []

### t2

Entrada: Lee el contenido del archivo "c03-lectura.txt" del sandbox.

Final (published_final): El contenido del archivo "c03-lectura.txt" es: "Lectura técnica C03: el color de control es turquesa."

Útil: sí. Progreso visible: []

### t3

Entrada: Read the file "c03-invalid-utf8.txt" in the sandbox.

Final (composition_failed): composition_failed

Útil: no. Progreso visible: []

### t4

Entrada: Lee el archivo "C:/Users/usuario/AppData/Local/BAXY/C03-fixtures/files53-outside/c03-sombra.txt".

Final (published_final): No pude encontrar el archivo porque no hay datos de búsqueda disponibles.

Útil: no. Progreso visible: []

### t5

Entrada: Dime la hora.

Final (published_final): 01:43

Útil: sí. Progreso visible: []

[Payloads, borradores y vetos](astra-files56-identity/paired.json).

## files57-cause

Resultado: {"exitCode": 0, "stopReason": null, "elapsedSeconds": 77.09, "gpuPeakMiB": 3497.55859375, "gpuAttributionAvailable": true, "ramPeakMiB": 5316.66796875, "registrationUnchanged": true}

### t1

Entrada: Lee el archivo "C:/Users/usuario/AppData/Local/BAXY/C03-fixtures/ausente47.txt".

Final (published_final): No pude buscar el archivo porque no hay datos sobre la búsqueda en el sistema.

Útil: no. Progreso visible: []

### t2

Entrada: Lee el contenido del archivo "c03-lectura.txt" del sandbox.

Final (published_final): El contenido del archivo "c03-lectura.txt" es: "Lectura técnica C03: el color de control es turquesa."

Útil: sí. Progreso visible: []

### t3

Entrada: Read the file "c03-invalid-utf8.txt" in the sandbox.

Final (composition_failed): composition_failed

Útil: no. Progreso visible: []

### t4

Entrada: Lee el archivo "C:/Users/usuario/AppData/Local/BAXY/C03-fixtures/files53-outside/c03-sombra.txt".

Final (published_final): No pude encontrar el archivo porque no hay datos de búsqueda disponibles.

Útil: no. Progreso visible: []

### t5

Entrada: Dime la hora.

Final (published_final): 01:47

Útil: sí. Progreso visible: []

[Payloads, borradores y vetos](astra-files57-cause/paired.json).

## files58-modal

Resultado: {"exitCode": 0, "stopReason": null, "elapsedSeconds": 71.09, "gpuPeakMiB": 3497.55859375, "gpuAttributionAvailable": true, "ramPeakMiB": 5401.0078125, "registrationUnchanged": true}

### t1

Entrada: Lee el archivo "C:/Users/usuario/AppData/Local/BAXY/C03-fixtures/ausente47.txt".

Final (published_final): No pude buscar el archivo porque no hay datos sobre la búsqueda en el sistema.

Útil: no. Progreso visible: []

### t2

Entrada: Lee el contenido del archivo "c03-lectura.txt" del sandbox.

Final (published_final): El contenido del archivo "c03-lectura.txt" es: "Lectura técnica C03: el color de control es turquesa."

Útil: sí. Progreso visible: []

### t3

Entrada: Read the file "c03-invalid-utf8.txt" in the sandbox.

Final (published_final): The file contains invalid UTF-8 sequences, which cannot be properly read or processed.

Útil: sí. Progreso visible: []

### t4

Entrada: Lee el archivo "C:/Users/usuario/AppData/Local/BAXY/C03-fixtures/files53-outside/c03-sombra.txt".

Final (published_final): No pude encontrar el archivo porque no hay datos de búsqueda disponibles.

Útil: no. Progreso visible: []

### t5

Entrada: Dime la hora.

Final (published_final): 01:53

Útil: sí. Progreso visible: []

[Payloads, borradores y vetos](astra-files58-modal/paired.json).

## Comparaciones nativas59–62

Conservan identidad, instrucciones, template y límites de BAXY; se toma la primera respuesta HTTP sin validadores/reintentos. No son modelo sin wrapper.59 añade scope=sandbox;60 cambia la causa a no matches in the searched scope;61 especifica filesystem sandbox. 62 cambia la hipótesis: fallo tipado antes de buscar una ruta absoluta no admitida por el contrato de búsqueda por nombres. Es una simulación causal, aún no conducta medida del proveedor.

### files-scope59

{
  "elapsedSeconds": 5.7,
  "gpuPeakMiB": 3495.55859375,
  "ramPeakMiB": 2819.01953125,
  "registrationUnchanged": true
}

t1 / baseline: No se pudo leer el archivo porque no se encontraron datos en la búsqueda del sistema.

t1 / scope: No se pudo leer el archivo porque no se encontró datos sobre la búsqueda en el sistema.

t4 / baseline: No se encontró el archivo solicitado. No se pudieron acceder a los datos del sistema.

t4 / scope: No se encontró el archivo solicitado. No se pudieron acceder a los datos necesarios para realizar la búsqueda.

### files-empty60

{
  "elapsedSeconds": 4.89,
  "gpuPeakMiB": 3495.55859375,
  "ramPeakMiB": 2817.26953125,
  "registrationUnchanged": true
}

t1 / files-empty60: No se encontró el archivo en el ámbito buscado.

t4 / files-empty60: No se encontró el archivo solicitado en el ámbito buscado.

### files-sandbox61

{
  "elapsedSeconds": 5.2,
  "gpuPeakMiB": 3495.55859375,
  "ramPeakMiB": 2816.8203125,
  "registrationUnchanged": true
}

t1 / files-sandbox61: No se encontró el archivo en el entorno de sistema.

t4 / files-sandbox61: No se encontró el archivo en el entorno de sandbox.

### files-path62

{
  "elapsedSeconds": 7.14,
  "gpuPeakMiB": 3495.55859375,
  "ramPeakMiB": 2818.6953125,
  "registrationUnchanged": true
}

t1 / baseline: No se pudo leer el archivo porque no se encontraron datos en la búsqueda del sistema.

t1 / unsupported: No pude leer el archivo porque el sistema no soporta la búsqueda por ruta absoluta.

t4 / baseline: No se encontró el archivo solicitado. No se pudieron acceder a los datos del sistema.

t4 / unsupported: No se puede acceder al archivo porque el sistema no soporta la búsqueda por ruta absoluta.

Decisión:59 no mejora;60 elimina indisponibilidad inventada pero omite el alcance concreto;61 sólo lo concreta en uno de dos casos. 62 explica la limitación real en ambos casos. Procede validar el error en el proveedor y repetir el producto, sin ampliar acceso ni sustituir rutas por nombres.

Contraste actual consultado2026-09-07: [Path.IsPathFullyQualified, .NET10](https://learn.microsoft.com/en-us/dotnet/api/system.io.path.ispathfullyqualified?view=net-10.0) distingue rutas absolutas de las rooted dependientes del directorio/unidad actual. Se reutiliza esa API, sin parser de rutas propio. El catálogo actual ya define búsqueda por nombres confinada al sandbox; se conserva ese alcance.

Pendientes: progreso que infirió UTF8 del nombre en55, causas de búsquedas vacías normales, validación completa de C03. Ausencia de avisos en58 no demuestra reparación del progreso.
