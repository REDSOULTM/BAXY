# C03 — referencias, contexto y modelo68–71

Controles técnicos consumidos/sintéticos; ninguna reserva humana ni UI/audio. No hay ejecución de funciones en estos replays. Fuente de producto intacta desde63.

68 demuestra que retirar globalmente las respuestas del asistente rompe referencias y puede añadir una acción a una pregunta sobre un fallo. Diálogo completo5/6; sólo usuarios1/6; sin contexto1/6. El modelo registrado ya falla con diálogo completo al leer el segundo archivo: selecciona búsqueda. No se oculta ese fallo con una etiqueta de referencia correcta.

69 prueba decisión previa de necesidad de diálogo, sin reescribir la petición:5/10 clasificaciones correctas y5/10 selecciones correctas.70 retira sólo response_format, conserva prompt y presupuesto: idéntico resultado. Se descarta esta estrategia; no se añade otro clasificador al producto ni más variantes de etiqueta.

71 conserva todos los paquetes y el diálogo, cambia sólo al Qwen3.5-4B Q4_K_M heredado.9/10 selecciones correctas frente a6/10 de Qwen3-2507: recupera los cuatro archivos y leer el segundo, pero propone lectura ante ¿Por qué no pudiste?. No promoción. La mejora nativa exige recorrer producto y todos los roles, especialmente conocimiento y errores.

## selector-references68

{
  "elapsedSeconds": 12.7,
  "gpuPeakMiB": 3497.55859375,
  "ramPeakMiB": 2828.546875,
  "registrationUnchanged": true
}

### t1 / full

Entrada: Sí, hazlo.

Selección: ["baxy_filesystem__read__text"]; fin=tool_calls.

Texto bruto: 

### t1 / user_history_only

Entrada: Sí, hazlo.

Selección: []; fin=stop.

Texto bruto: No se puede determinar la acción específica solicitada en el contexto actual. Por favor, proporcione más detalles sobre qué tipo de informe se refiere o qué acción específica desea realizar.

### t1 / no_context

Entrada: Sí, hazlo.

Selección: []; fin=stop.

Texto bruto: No se puede realizar ninguna acción con la solicitud "Sí, hazlo." ya que no se especifica una tarea o acción concreta. Por favor, proporcione una solicitud más clara y detallada.

### t2 / full

Entrada: Yes, do that.

Selección: ["baxy_filesystem__search"]; fin=tool_calls.

Texto bruto: 

### t2 / user_history_only

Entrada: Yes, do that.

Selección: []; fin=stop.

Texto bruto: I cannot perform any actions or retrieve information without a specific, concrete request. Please provide a clear instruction, such as reading a file, navigating a URL, or extracting text from a document.

### t2 / no_context

Entrada: Yes, do that.

Selección: []; fin=stop.

Texto bruto: I cannot interpret or act on the request "Yes, do that." as it is vague and lacks specific instructions. Please provide a clear and concrete action or request.

### t3 / full

Entrada: Ahora léelo.

Selección: ["baxy_filesystem__read__text"]; fin=tool_calls.

Texto bruto: 

### t3 / user_history_only

Entrada: Ahora léelo.

Selección: ["baxy_filesystem__search"]; fin=tool_calls.

Texto bruto: 

### t3 / no_context

Entrada: Ahora léelo.

Selección: []; fin=stop.

Texto bruto: No se puede interpretar la solicitud "Ahora léelo" sin contexto adicional. Por favor, especifique qué necesitas leer (por ejemplo, un archivo, correo, página web, nota, etc.) para que pueda ayudarte.

### t4 / full

Entrada: Read the second one.

Selección: ["baxy_filesystem__search"]; fin=tool_calls.

Texto bruto: 

### t4 / user_history_only

Entrada: Read the second one.

Selección: ["baxy_note__search"]; fin=tool_calls.

Texto bruto: 

### t4 / no_context

Entrada: Read the second one.

Selección: []; fin=stop.

Texto bruto: I cannot interpret or act on "Read the second one" without additional context or specific instructions. Please provide more details about what you'd like me to read or perform.

### t5 / full

Entrada: No, solo búscalo.

Selección: ["baxy_filesystem__search"]; fin=tool_calls.

Texto bruto: 

### t5 / user_history_only

Entrada: No, solo búscalo.

Selección: ["baxy_filesystem__search"]; fin=tool_calls.

Texto bruto: 

### t5 / no_context

Entrada: No, solo búscalo.

Selección: []; fin=stop.

Texto bruto: No se puede interpretar la solicitud como una acción concreta. Por favor, especifique qué desea buscar o realizar.

### t6 / full

Entrada: ¿Por qué no pudiste?

Selección: []; fin=stop.

Texto bruto: No pude leer el archivo porque la búsqueda no admite rutas absolutas.

### t6 / user_history_only

Entrada: ¿Por qué no pudiste?

Selección: ["baxy_filesystem__read__text"]; fin=tool_calls.

Texto bruto: 

### t6 / no_context

Entrada: ¿Por qué no pudiste?

Selección: []; fin=stop.

Texto bruto: No se puede realizar ninguna acción con la solicitud "¿Por qué no pudiste?". Esta consulta es una pregunta de conversación o reflexión, no requiere una acción específica en el sistema.

## selector-context69

{
  "elapsedSeconds": 16.36,
  "gpuPeakMiB": 3497.55859375,
  "ramPeakMiB": 4227.4140625,
  "registrationUnchanged": true
}

### file1 / candidate

Entrada: Lee el archivo "C:/Users/usuario/AppData/Local/BAXY/C03-fixtures/ausente47.txt".

Selección: ["baxy_filesystem__read__text"]; fin=tool_calls.

Texto bruto: 

Decisión previa: {"needs_dialogue": false}

### file2 / candidate

Entrada: Lee el contenido del archivo "c03-lectura.txt" del sandbox.

Selección: ["baxy_filesystem__read__text"]; fin=tool_calls.

Texto bruto: 

Decisión previa: {"needs_dialogue": false}

### file3 / candidate

Entrada: Read the file "c03-invalid-utf8.txt" in the sandbox.

Selección: ["baxy_filesystem__read__text"]; fin=tool_calls.

Texto bruto: 

Decisión previa: {"needs_dialogue": false}

### file4 / candidate

Entrada: Lee el archivo "C:/Users/usuario/AppData/Local/BAXY/C03-fixtures/files53-outside/c03-sombra.txt".

Selección: ["baxy_filesystem__read__text"]; fin=tool_calls.

Texto bruto: 

Decisión previa: {"needs_dialogue": false}

### reft1 / candidate

Entrada: Sí, hazlo.

Selección: []; fin=stop.

Texto bruto: No se puede realizar ninguna acción con la solicitud "Sí, hazlo." ya que no se especifica una tarea o acción concreta. Por favor, proporcione más detalles sobre lo que desea que se haga.

Decisión previa: {"needs_dialogue": false}

### reft2 / candidate

Entrada: Yes, do that.

Selección: []; fin=stop.

Texto bruto: I cannot interpret or act on the request "Yes, do that." as it is vague and lacks specific instructions. Please provide a clear and concrete action or request.

Decisión previa: {"needs_dialogue": false}

### reft3 / candidate

Entrada: Ahora léelo.

Selección: []; fin=stop.

Texto bruto: No se puede interpretar la solicitud "Ahora léelo" sin contexto adicional. Por favor, especifique qué necesitas leer (por ejemplo, un archivo, correo, página web, nota, etc.) para que pueda ayudarte.

Decisión previa: {"needs_dialogue": false}

### reft4 / candidate

Entrada: Read the second one.

Selección: []; fin=stop.

Texto bruto: I cannot interpret or act on "Read the second one" without additional context or specific instructions. Please provide more details about what you'd like me to read or perform.

Decisión previa: {"needs_dialogue": false}

### reft5 / candidate

Entrada: No, solo búscalo.

Selección: []; fin=stop.

Texto bruto: No se puede interpretar la solicitud como una acción concreta. Por favor, especifique qué desea buscar o qué acción desea realizar.

Decisión previa: {"needs_dialogue": false}

### reft6 / candidate

Entrada: ¿Por qué no pudiste?

Selección: []; fin=stop.

Texto bruto: No pude leer el archivo porque la búsqueda no admite rutas absolutas.

Decisión previa: {"needs_dialogue": true}

## selector-context70

{
  "elapsedSeconds": 13.61,
  "gpuPeakMiB": 3497.55859375,
  "ramPeakMiB": 4228.01953125,
  "registrationUnchanged": true
}

### file1 / candidate

Entrada: Lee el archivo "C:/Users/usuario/AppData/Local/BAXY/C03-fixtures/ausente47.txt".

Selección: ["baxy_filesystem__read__text"]; fin=tool_calls.

Texto bruto: 

Decisión previa: {"needs_dialogue": false}

### file2 / candidate

Entrada: Lee el contenido del archivo "c03-lectura.txt" del sandbox.

Selección: ["baxy_filesystem__read__text"]; fin=tool_calls.

Texto bruto: 

Decisión previa: {"needs_dialogue": false}

### file3 / candidate

Entrada: Read the file "c03-invalid-utf8.txt" in the sandbox.

Selección: ["baxy_filesystem__read__text"]; fin=tool_calls.

Texto bruto: 

Decisión previa: {"needs_dialogue": false}

### file4 / candidate

Entrada: Lee el archivo "C:/Users/usuario/AppData/Local/BAXY/C03-fixtures/files53-outside/c03-sombra.txt".

Selección: ["baxy_filesystem__read__text"]; fin=tool_calls.

Texto bruto: 

Decisión previa: {"needs_dialogue": false}

### reft1 / candidate

Entrada: Sí, hazlo.

Selección: []; fin=stop.

Texto bruto: No se puede realizar ninguna acción con la solicitud "Sí, hazlo." ya que no se especifica una tarea o acción concreta. Por favor, proporcione más detalles sobre lo que desea que se haga.

Decisión previa: {"needs_dialogue": false}

### reft2 / candidate

Entrada: Yes, do that.

Selección: []; fin=stop.

Texto bruto: I cannot interpret or act on the request "Yes, do that." as it is vague and lacks specific instructions. Please provide a clear and concrete action or request.

Decisión previa: {"needs_dialogue": false}

### reft3 / candidate

Entrada: Ahora léelo.

Selección: []; fin=stop.

Texto bruto: No se puede interpretar la solicitud "Ahora léelo" sin contexto adicional. Por favor, especifique qué necesitas leer (por ejemplo, un archivo, correo, página web, nota, etc.) para que pueda ayudarte.

Decisión previa: {"needs_dialogue": false}

### reft4 / candidate

Entrada: Read the second one.

Selección: []; fin=stop.

Texto bruto: I cannot interpret or act on "Read the second one" without additional context or specific instructions. Please provide more details about what you'd like me to read or perform.

Decisión previa: {"needs_dialogue": false}

### reft5 / candidate

Entrada: No, solo búscalo.

Selección: []; fin=stop.

Texto bruto: No se puede interpretar la solicitud como una acción concreta. Por favor, especifique qué desea buscar o qué acción desea realizar.

Decisión previa: {"needs_dialogue": false}

### reft6 / candidate

Entrada: ¿Por qué no pudiste?

Selección: []; fin=stop.

Texto bruto: No pude leer el archivo porque la búsqueda no admite rutas absolutas.

Decisión previa: {"needs_dialogue": true}

## selector-qwen35-71

{
  "elapsedSeconds": 12.89,
  "gpuPeakMiB": 3175.5625,
  "ramPeakMiB": 4529.921875,
  "registrationUnchanged": true
}

### file1 / candidate

Entrada: Lee el archivo "C:/Users/usuario/AppData/Local/BAXY/C03-fixtures/ausente47.txt".

Selección: ["baxy_filesystem__read__text"]; fin=tool_calls.

Texto bruto: 

### file2 / candidate

Entrada: Lee el contenido del archivo "c03-lectura.txt" del sandbox.

Selección: ["baxy_filesystem__read__text"]; fin=tool_calls.

Texto bruto: 

### file3 / candidate

Entrada: Read the file "c03-invalid-utf8.txt" in the sandbox.

Selección: ["baxy_filesystem__read__text"]; fin=tool_calls.

Texto bruto: 

### file4 / candidate

Entrada: Lee el archivo "C:/Users/usuario/AppData/Local/BAXY/C03-fixtures/files53-outside/c03-sombra.txt".

Selección: ["baxy_filesystem__read__text"]; fin=tool_calls.

Texto bruto: 

### reft1 / candidate

Entrada: Sí, hazlo.

Selección: ["baxy_filesystem__read__text"]; fin=tool_calls.

Texto bruto: 

### reft2 / candidate

Entrada: Yes, do that.

Selección: ["baxy_filesystem__search"]; fin=tool_calls.

Texto bruto: 

### reft3 / candidate

Entrada: Ahora léelo.

Selección: ["baxy_filesystem__read__text"]; fin=tool_calls.

Texto bruto: 

### reft4 / candidate

Entrada: Read the second one.

Selección: ["baxy_filesystem__read__text"]; fin=tool_calls.

Texto bruto: 

### reft5 / candidate

Entrada: No, solo búscalo.

Selección: ["baxy_filesystem__search"]; fin=tool_calls.

Texto bruto: 

### reft6 / candidate

Entrada: ¿Por qué no pudiste?

Selección: ["baxy_filesystem__read__text"]; fin=tool_calls.

Texto bruto: No pude leer el archivo porque la búsqueda en el sandbox no admite rutas absolutas. Necesito usar una ruta relativa o el nombre del archivo directamente para poder acceder a él.



## Herencia, contraste actual y límites

Se reutilizan _bounded_history, los paquetes64 y la separación de contexto47. is_elliptical_followup excluye órdenes deícticas y no se fuerza a otro dominio. [Context engineering, fuente primaria consultada2026-09-07](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) motiva seleccionar información relevante; no certifica un clasificador para Qwen.69/70 lo refutan localmente.

El activo Qwen3.5 ya existía. scratchpad/c03-native-qwen35.log y su variante thinking registran pruebas antiguas de conversación con fallos factuales y perfiles diferentes. No se borran ni se extrapola éxito de selección a conocimiento. Las rutas astra-native-qwen35/gpu.json y astra-native-qwen35-thinking/gpu.json no existían al consultarlas; no se atribuyen recursos antiguos sin evidencia.71 mide los actuales y guarda llama-command.json.

[Ficha oficial Qwen3.5-4B consultada2026-09-07](https://huggingface.co/Qwen/Qwen3.5-4B) admite no-thinking mediante enable_thinking=false y publica perfil general0.7/top_p0.8/top_k20/min_p0/presence1.5. 71 usa selección determinista0,seed0,256 tokens para aislar cambio de modelo. No adapta aún toda la inferencia. 3slots de4096,KVq8,ngl99,b9980CUDA; GPU3175,56MiB,RAM4529,92MiB,12,89s,registro intacto.

Prueba72: mismo prefijo de5 archivos y5 transferencias con override de modelo sólo en perfil aislado. Sin registro/promoción, sin cambios de código, sin detector69. Mide por la entrada real de producto y conserva payloads/causas/rechazos. El conductor no acredita UI/audio físico.
