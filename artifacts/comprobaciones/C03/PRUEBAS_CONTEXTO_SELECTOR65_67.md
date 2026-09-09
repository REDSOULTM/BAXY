# C03 — aislamiento del historial en selección65–67

Se reutilizan cuatro paquetes AUTO exactos de files64-wire/wire-29264.jsonl. La hora tomó la ruta determinista y no produjo un quinto paquete. No hay efectos, validadores de decisión ni reintentos. Conservan las instrucciones y herramientas de BAXY; no son pruebas del modelo sin wrapper. Sin reserva humana ni UI/audio.

Expectativa en los cuatro pedidos: proponer filesystem.read.text como efecto de lectura. El plan añade búsqueda e identidad y el proveedor conserva su límite. Elegir search sólo no cumple leer.

65: capturado1/4; sin contexto4/4; instrucción sobre alcance del fallo2/4. 66: capturado1/4; roles nativos2/4; sólo mensajes anteriores del usuario4/4. 67: capturado1/4; descripción de lectura más explícita2/4. Ninguna variante se ha incorporado al producto.

## selector-history65

{
  "elapsedSeconds": 13.41,
  "gpuPeakMiB": 3497.55859375,
  "ramPeakMiB": 3988.98828125,
  "registrationUnchanged": true
}

### t1 / captured

Entrada: Lee el archivo "C:/Users/usuario/AppData/Local/BAXY/C03-fixtures/ausente47.txt".

Selección: ["baxy_filesystem__read__text"]; finish_reason=tool_calls.

Texto bruto: 

### t1 / no_context

Entrada: Lee el archivo "C:/Users/usuario/AppData/Local/BAXY/C03-fixtures/ausente47.txt".

Selección: ["baxy_filesystem__read__text"]; finish_reason=tool_calls.

Texto bruto: 

### t1 / scoped_history

Entrada: Lee el archivo "C:/Users/usuario/AppData/Local/BAXY/C03-fixtures/ausente47.txt".

Selección: ["baxy_filesystem__read__text"]; finish_reason=tool_calls.

Texto bruto: 

### t2 / captured

Entrada: Lee el contenido del archivo "c03-lectura.txt" del sandbox.

Selección: ["baxy_filesystem__search"]; finish_reason=tool_calls.

Texto bruto: 

### t2 / no_context

Entrada: Lee el contenido del archivo "c03-lectura.txt" del sandbox.

Selección: ["baxy_filesystem__read__text"]; finish_reason=tool_calls.

Texto bruto: 

### t2 / scoped_history

Entrada: Lee el contenido del archivo "c03-lectura.txt" del sandbox.

Selección: ["baxy_filesystem__read__text"]; finish_reason=tool_calls.

Texto bruto: 

### t3 / captured

Entrada: Read the file "c03-invalid-utf8.txt" in the sandbox.

Selección: ["baxy_filesystem__search"]; finish_reason=tool_calls.

Texto bruto: 

### t3 / no_context

Entrada: Read the file "c03-invalid-utf8.txt" in the sandbox.

Selección: ["baxy_filesystem__read__text"]; finish_reason=tool_calls.

Texto bruto: 

### t3 / scoped_history

Entrada: Read the file "c03-invalid-utf8.txt" in the sandbox.

Selección: ["baxy_filesystem__search"]; finish_reason=tool_calls.

Texto bruto: 

### t4 / captured

Entrada: Lee el archivo "C:/Users/usuario/AppData/Local/BAXY/C03-fixtures/files53-outside/c03-sombra.txt".

Selección: []; finish_reason=stop.

Texto bruto: This is outside what I do on this PC.

### t4 / no_context

Entrada: Lee el archivo "C:/Users/usuario/AppData/Local/BAXY/C03-fixtures/files53-outside/c03-sombra.txt".

Selección: ["baxy_filesystem__read__text"]; finish_reason=tool_calls.

Texto bruto: 

### t4 / scoped_history

Entrada: Lee el archivo "C:/Users/usuario/AppData/Local/BAXY/C03-fixtures/files53-outside/c03-sombra.txt".

Selección: []; finish_reason=stop.

Texto bruto: This is outside what I do on this PC.

## selector-history66

{
  "elapsedSeconds": 10.89,
  "gpuPeakMiB": 3497.55859375,
  "ramPeakMiB": 3322.6171875,
  "registrationUnchanged": true
}

### t1 / captured

Entrada: Lee el archivo "C:/Users/usuario/AppData/Local/BAXY/C03-fixtures/ausente47.txt".

Selección: ["baxy_filesystem__read__text"]; finish_reason=tool_calls.

Texto bruto: 

### t1 / native_roles

Entrada: Lee el archivo "C:/Users/usuario/AppData/Local/BAXY/C03-fixtures/ausente47.txt".

Selección: ["baxy_filesystem__read__text"]; finish_reason=tool_calls.

Texto bruto: 

### t1 / user_history_only

Entrada: Lee el archivo "C:/Users/usuario/AppData/Local/BAXY/C03-fixtures/ausente47.txt".

Selección: ["baxy_filesystem__read__text"]; finish_reason=tool_calls.

Texto bruto: 

### t2 / captured

Entrada: Lee el contenido del archivo "c03-lectura.txt" del sandbox.

Selección: ["baxy_filesystem__search"]; finish_reason=tool_calls.

Texto bruto: 

### t2 / native_roles

Entrada: Lee el contenido del archivo "c03-lectura.txt" del sandbox.

Selección: ["baxy_filesystem__read__text"]; finish_reason=tool_calls.

Texto bruto: 

### t2 / user_history_only

Entrada: Lee el contenido del archivo "c03-lectura.txt" del sandbox.

Selección: ["baxy_filesystem__read__text"]; finish_reason=tool_calls.

Texto bruto: 

### t3 / captured

Entrada: Read the file "c03-invalid-utf8.txt" in the sandbox.

Selección: ["baxy_filesystem__search"]; finish_reason=tool_calls.

Texto bruto: 

### t3 / native_roles

Entrada: Read the file "c03-invalid-utf8.txt" in the sandbox.

Selección: []; finish_reason=stop.

Texto bruto: No puedo leer archivos con nombres como "c03-invalid-utf8.txt" porque no tengo acceso directo a archivos con nombres específicos en el sandbox. Por favor, revise el nombre del archivo o proporcione más detalles.

### t3 / user_history_only

Entrada: Read the file "c03-invalid-utf8.txt" in the sandbox.

Selección: ["baxy_filesystem__read__text"]; finish_reason=tool_calls.

Texto bruto: 

### t4 / captured

Entrada: Lee el archivo "C:/Users/usuario/AppData/Local/BAXY/C03-fixtures/files53-outside/c03-sombra.txt".

Selección: []; finish_reason=stop.

Texto bruto: This is outside what I do on this PC.

### t4 / native_roles

Entrada: Lee el archivo "C:/Users/usuario/AppData/Local/BAXY/C03-fixtures/files53-outside/c03-sombra.txt".

Selección: []; finish_reason=stop.

Texto bruto: No pude leer el archivo porque el sistema no soporta la búsqueda por ruta absoluta.

### t4 / user_history_only

Entrada: Lee el archivo "C:/Users/usuario/AppData/Local/BAXY/C03-fixtures/files53-outside/c03-sombra.txt".

Selección: ["baxy_filesystem__read__text"]; finish_reason=tool_calls.

Texto bruto: 

## selector-catalog67

{
  "elapsedSeconds": 12.42,
  "gpuPeakMiB": 3497.55859375,
  "ramPeakMiB": 3850.34375,
  "registrationUnchanged": true
}

### t1 / captured

Entrada: Lee el archivo "C:/Users/usuario/AppData/Local/BAXY/C03-fixtures/ausente47.txt".

Selección: ["baxy_filesystem__read__text"]; finish_reason=tool_calls.

Texto bruto: 

### t1 / file_description

Entrada: Lee el archivo "C:/Users/usuario/AppData/Local/BAXY/C03-fixtures/ausente47.txt".

Selección: ["baxy_filesystem__read__text"]; finish_reason=tool_calls.

Texto bruto: 

### t2 / captured

Entrada: Lee el contenido del archivo "c03-lectura.txt" del sandbox.

Selección: ["baxy_filesystem__search"]; finish_reason=tool_calls.

Texto bruto: 

### t2 / file_description

Entrada: Lee el contenido del archivo "c03-lectura.txt" del sandbox.

Selección: ["baxy_filesystem__read__text"]; finish_reason=tool_calls.

Texto bruto: 

### t3 / captured

Entrada: Read the file "c03-invalid-utf8.txt" in the sandbox.

Selección: ["baxy_filesystem__search"]; finish_reason=tool_calls.

Texto bruto: 

### t3 / file_description

Entrada: Read the file "c03-invalid-utf8.txt" in the sandbox.

Selección: ["baxy_filesystem__search"]; finish_reason=tool_calls.

Texto bruto: 

### t4 / captured

Entrada: Lee el archivo "C:/Users/usuario/AppData/Local/BAXY/C03-fixtures/files53-outside/c03-sombra.txt".

Selección: []; finish_reason=stop.

Texto bruto: This is outside what I do on this PC.

### t4 / file_description

Entrada: Lee el archivo "C:/Users/usuario/AppData/Local/BAXY/C03-fixtures/files53-outside/c03-sombra.txt".

Selección: ["baxy_filesystem__search"]; finish_reason=tool_calls.

Texto bruto: 

## Decisión y siguiente comparación

La retirada del historial o únicamente de las respuestas anteriores restablece la selección en4/4: hay evidencia causal de contaminación por prosa previa. Eso NO autoriza borrar el historial de todos los pedidos: faltan controles de referencias cuyo efecto se encuentre sólo en una oferta o explicación del asistente. El contexto de conversación y grounding debe conservarse. Los intentos de añadir instrucciones, cambiar roles o retocar la descripción no resuelven; no repetir esas variantes. La siguiente hipótesis debe separar intención actual y referencias necesarias, con contrastes antes de editar fuente.

Reutilización: ASTRA47 e INVESTIGACION_FORMATO_Y_CLASIFICACION_C03.md ya fijan diferencias entre contexto de conversación y protocolo nativo. El caso actual es selección, no respuesta de conocimiento; no extender starts_new_definition_topic a acciones. is_elliptical_followup exige interrogativo y NO sirve para close that/hazlo. No añadir un detector de referencias parcial sin demostrar esos contrastes.

Instrumentación:65 primero se detuvo antes de PREREG/inferencia por esperar5 AUTO; corregido a4 y ejecutado una sola vez. 66 deriva del script65: su PREREG conserva el method anterior y añade comparison66 que describe la comparación efectiva; posts.jsonl demuestra que no_context/scoped_history NO se ejecutaron en66. Esa duplicación de metadatos se conserva y queda aclarada aquí, sin alterar la preregistración. El añadido extra del script no se usa en66/67.

Producción actual: sólo guard del proveedor63 añadido desde fuente58; descripción pública, historial y selector intactos. PRUEBAS_ARCHIVOS63_64.md conserva2/5 y las negativas posteriores. No cierre de C03. El script de progreso64 está preparado, no ejecutado.
