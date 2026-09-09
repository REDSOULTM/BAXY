# C03 — causa HTTP y compatibilidad de template — tramos75–76

75 mantiene6/10 útiles,122,16s,GPU3177,56MiB,RAM7313,58MiB,exit0,registro intacto. Misma fuente74 y override Qwen3.5. Hook75 captura los errores antes ausentes, sin consumir el body BytesIO. Nueve peticiones reciben HTTP400: el template sólo permite un mensaje system al inicio. Todos estos paquetes tienen un prefijo de dos o tres system; no son errores de razonamiento del modelo.

El [template oficial Qwen3.5-4B](https://huggingface.co/Qwen/Qwen3.5-4B/blob/main/chat_template.jinja), consultado2026-09-07, rechaza explícitamente un system cuyo índice no sea el primero. La restricción coincide con el backend/GGUF local medido. No se aplica como inferencia a toda la familia: Qwen3-2507 acepta los paquetes capturados, como muestran las comparaciones76.

76 cambia sólo la serialización del prefijo: todos los textos system unidos con dos saltos de línea, en orden original, antes del mismo diálogo. Los nueve paquetes dejan de fallar en Qwen3.5. Las respuestas principales de porqué/definición/nivel son útiles; las preguntas de recuperación forzada siguen siendo innecesarias o incorrectas y no se cuentan como aceptación semántica. Selector de control conserva read.text. No se ejecutan funciones.

Registrado2507: las respuestas principales se mantienen con/sin agrupación; una aclaración de recuperación sobre checksum cambia texto y añade reasoning_content. No declarar equivalencia de todos los tokens ni aceptación general. Recursos nativos: Qwen3.5 12,17s/GPU3175,56MiB/RAM4714,94MiB; registrado12,16s/GPU3497,56MiB/RAM2996,58MiB. Ambos manifiestos intactos. Promoción de modelo y cierre de producto siguen pendientes.

## 75 / t1

Entrada: Lee el archivo "C:/Users/usuario/AppData/Local/BAXY/C03-fixtures/ausente47.txt".

Final literal: No pude leer el archivo porque el sistema no soporta búsquedas con rutas absolutas.

## 75 / t2

Entrada: Lee el contenido del archivo "c03-lectura.txt" del sandbox.

Final literal: He leído el archivo "c03-lectura.txt" y su contenido es: "Lectura técnica C03: el color de control es turquesa."

## 75 / t3

Entrada: Read the file "c03-invalid-utf8.txt" in the sandbox.

Final literal: I tried to read the file "c03-invalid-utf8.txt" from the sandbox, but the operation failed because the file contains invalid UTF-8 characters.

## 75 / t4

Entrada: Lee el archivo "C:/Users/usuario/AppData/Local/BAXY/C03-fixtures/files53-outside/c03-sombra.txt".

Final literal: No pude leer el archivo porque el sistema no soporta búsquedas con rutas absolutas.

## 75 / t5

Entrada: Dime la hora.

Final literal: Son las 03:26.

## 75 / t6

Entrada: Why couldn't you read "c03-invalid-utf8.txt"?

Final literal: I couldn't read the file because the request interpretation failed.

## 75 / t7

Entrada: Explain what a checksum is in one sentence.

Final literal: I cannot explain what a checksum is because the request failed due to an interpretation error.

## 75 / t8

Entrada: ¿Qué puedes hacer en este equipo?

Final literal: Puedo abrir y cerrar programas, mover ventanas, ajustar el audio y llevar tareas, además de otras cosas más.

## 75 / t9

Entrada: Dime la hora, el audio y el uso de CPU.

Final literal: composition_failed

## 75 / t10

Entrada: Pon el volumen.

Final literal: composition_failed

### Rechazo HTTP75 / 1

Roles: system, system, system, assistant, user, assistant, user, assistant, user, assistant, user, assistant, user, assistant, user

Error: {"error":{"code":400,"message":"Unable to generate parser for this template. Automatic parser generation failed: \n------------\nWhile executing CallExpression at line 85, column 32 in source:\n...first %}↵            {{- raise_exception('System message must be at the beginnin...\n                                           ^\nError: Jinja Exception: System message must be at the beginning.","type":"invalid_request_error"}}

### Rechazo HTTP75 / 2

Roles: system, system, system, assistant, user, assistant, user, assistant, user, assistant, user, assistant, user, assistant, user

Error: {"error":{"code":400,"message":"Unable to generate parser for this template. Automatic parser generation failed: \n------------\nWhile executing CallExpression at line 85, column 32 in source:\n...first %}↵            {{- raise_exception('System message must be at the beginnin...\n                                           ^\nError: Jinja Exception: System message must be at the beginning.","type":"invalid_request_error"}}

### Rechazo HTTP75 / 3

Roles: system, system, system, assistant, user, assistant, user

Error: {"error":{"code":400,"message":"Unable to generate parser for this template. Automatic parser generation failed: \n------------\nWhile executing CallExpression at line 85, column 32 in source:\n...first %}↵            {{- raise_exception('System message must be at the beginnin...\n                                           ^\nError: Jinja Exception: System message must be at the beginning.","type":"invalid_request_error"}}

### Rechazo HTTP75 / 4

Roles: system, system, system, user

Error: {"error":{"code":400,"message":"Unable to generate parser for this template. Automatic parser generation failed: \n------------\nWhile executing CallExpression at line 85, column 32 in source:\n...first %}↵            {{- raise_exception('System message must be at the beginnin...\n                                           ^\nError: Jinja Exception: System message must be at the beginning.","type":"invalid_request_error"}}

### Rechazo HTTP75 / 5

Roles: system, system, system, user

Error: {"error":{"code":400,"message":"Unable to generate parser for this template. Automatic parser generation failed: \n------------\nWhile executing CallExpression at line 85, column 32 in source:\n...first %}↵            {{- raise_exception('System message must be at the beginnin...\n                                           ^\nError: Jinja Exception: System message must be at the beginning.","type":"invalid_request_error"}}

### Rechazo HTTP75 / 6

Roles: system, system, system, assistant, user, assistant, user

Error: {"error":{"code":400,"message":"Unable to generate parser for this template. Automatic parser generation failed: \n------------\nWhile executing CallExpression at line 85, column 32 in source:\n...first %}↵            {{- raise_exception('System message must be at the beginnin...\n                                           ^\nError: Jinja Exception: System message must be at the beginning.","type":"invalid_request_error"}}

### Rechazo HTTP75 / 7

Roles: system, system, user

Error: {"error":{"code":400,"message":"Unable to generate parser for this template. Automatic parser generation failed: \n------------\nWhile executing CallExpression at line 85, column 32 in source:\n...first %}↵            {{- raise_exception('System message must be at the beginnin...\n                                           ^\nError: Jinja Exception: System message must be at the beginning.","type":"invalid_request_error"}}

### Rechazo HTTP75 / 8

Roles: system, system, user

Error: {"error":{"code":400,"message":"Unable to generate parser for this template. Automatic parser generation failed: \n------------\nWhile executing CallExpression at line 85, column 32 in source:\n...first %}↵            {{- raise_exception('System message must be at the beginnin...\n                                           ^\nError: Jinja Exception: System message must be at the beginning.","type":"invalid_request_error"}}

### Rechazo HTTP75 / 9

Roles: system, system, system, user, assistant, user, user

Error: {"error":{"code":400,"message":"Unable to generate parser for this template. Automatic parser generation failed: \n------------\nWhile executing CallExpression at line 85, column 32 in source:\n...first %}↵            {{- raise_exception('System message must be at the beginnin...\n                                           ^\nError: Jinja Exception: System message must be at the beginning.","type":"invalid_request_error"}}

## 76 / qwen35 / error1 / captured

Último mensaje: Why couldn't you read "c03-invalid-utf8.txt"?

Error HTTP: 400; fin: None.

Respuesta bruta: null

## 76 / qwen35 / error1 / one_system

Último mensaje: Why couldn't you read "c03-invalid-utf8.txt"?

Error HTTP: None; fin: stop.

Respuesta bruta: {"role": "assistant", "content": "I couldn't read \"c03-invalid-utf8.txt\" because the file contains invalid UTF-8 characters, which caused the read operation to fail."}

## 76 / qwen35 / error2 / captured

Último mensaje: Why couldn't you read "c03-invalid-utf8.txt"?

Error HTTP: 400; fin: None.

Respuesta bruta: null

## 76 / qwen35 / error2 / one_system

Último mensaje: Why couldn't you read "c03-invalid-utf8.txt"?

Error HTTP: None; fin: stop.

Respuesta bruta: {"role": "assistant", "content": "I couldn't read \"c03-invalid-utf8.txt\" because the file contains invalid UTF-8 characters, which caused the read operation to fail."}

## 76 / qwen35 / error3 / captured

Último mensaje: Why couldn't you read "c03-invalid-utf8.txt"?

Error HTTP: 400; fin: None.

Respuesta bruta: null

## 76 / qwen35 / error3 / one_system

Último mensaje: Why couldn't you read "c03-invalid-utf8.txt"?

Error HTTP: None; fin: stop.

Respuesta bruta: {"role": "assistant", "content": "{\n  \"question\": \"Could you please clarify what you mean by 'read' in this context?\"\n}"}

## 76 / qwen35 / error4 / captured

Último mensaje: Explain what a checksum is in one sentence.

Error HTTP: 400; fin: None.

Respuesta bruta: null

## 76 / qwen35 / error4 / one_system

Último mensaje: Explain what a checksum is in one sentence.

Error HTTP: None; fin: stop.

Respuesta bruta: {"role": "assistant", "content": "A checksum is a short, fixed-length string of characters calculated from a file's data to verify its integrity and detect any corruption or tampering."}

## 76 / qwen35 / error5 / captured

Último mensaje: Explain what a checksum is in one sentence.

Error HTTP: 400; fin: None.

Respuesta bruta: null

## 76 / qwen35 / error5 / one_system

Último mensaje: Explain what a checksum is in one sentence.

Error HTTP: None; fin: stop.

Respuesta bruta: {"role": "assistant", "content": "A checksum is a short, fixed-length string of characters calculated from a file's data to verify its integrity and detect any corruption or tampering."}

## 76 / qwen35 / error6 / captured

Último mensaje: Explain what a checksum is in one sentence.

Error HTTP: 400; fin: None.

Respuesta bruta: null

## 76 / qwen35 / error6 / one_system

Último mensaje: Explain what a checksum is in one sentence.

Error HTTP: None; fin: stop.

Respuesta bruta: {"role": "assistant", "content": "{\"question\": \"What would you like to know about checksums?\"}"}

## 76 / qwen35 / error7 / captured

Último mensaje: {"user_request":"Pon el volumen.","recognized_operations":["audio.volume"],"missing_information":["level"],"response_language":"es"}

Error HTTP: 400; fin: None.

Respuesta bruta: null

## 76 / qwen35 / error7 / one_system

Último mensaje: {"user_request":"Pon el volumen.","recognized_operations":["audio.volume"],"missing_information":["level"],"response_language":"es"}

Error HTTP: None; fin: stop.

Respuesta bruta: {"role": "assistant", "content": "{\n  \"requested_fields\": [\"level\"],\n  \"question\": \"¿A qué nivel quieres que ponga el volumen?\"\n}"}

## 76 / qwen35 / error8 / captured

Último mensaje: {"user_request":"Pon el volumen.","recognized_operations":["audio.volume"],"missing_information":["level"],"response_language":"es"}

Error HTTP: 400; fin: None.

Respuesta bruta: null

## 76 / qwen35 / error8 / one_system

Último mensaje: {"user_request":"Pon el volumen.","recognized_operations":["audio.volume"],"missing_information":["level"],"response_language":"es"}

Error HTTP: None; fin: stop.

Respuesta bruta: {"role": "assistant", "content": "{\n  \"requested_fields\": [\"level\"],\n  \"question\": \"¿A qué nivel quieres que ponga el volumen?\"\n}"}

## 76 / qwen35 / error9 / captured

Último mensaje: Pon el volumen.

Error HTTP: 400; fin: None.

Respuesta bruta: null

## 76 / qwen35 / error9 / one_system

Último mensaje: Pon el volumen.

Error HTTP: None; fin: stop.

Respuesta bruta: {"role": "assistant", "content": "{\n  \"question\": \"¿Podrías decirme qué volumen tienes actualmente?\"\n}"}

## 76 / qwen35 / selector_control / captured

Último mensaje: {"previous_dialogue_for_references_only": [{"role": "assistant", "content": "¡Hola! Aquí BAXY. ¿En qué te puedo ayudar hoy?"}], "current_request_to_interpret": "Lee el archivo \"C:/Users/usuario/AppData/Local/BAXY/C03-fixtures/ausente47.txt\"."}

Error HTTP: None; fin: tool_calls.

Respuesta bruta: {"role": "assistant", "content": "", "tool_calls": [{"type": "function", "function": {"name": "baxy_filesystem__read__text", "arguments": "{}"}, "id": "RY8nR6ABlZFcmY6fHkgIVPOO8mxw1oBw"}]}

## 76 / qwen35 / selector_control / one_system

Último mensaje: {"previous_dialogue_for_references_only": [{"role": "assistant", "content": "¡Hola! Aquí BAXY. ¿En qué te puedo ayudar hoy?"}], "current_request_to_interpret": "Lee el archivo \"C:/Users/usuario/AppData/Local/BAXY/C03-fixtures/ausente47.txt\"."}

Error HTTP: None; fin: tool_calls.

Respuesta bruta: {"role": "assistant", "content": "", "tool_calls": [{"type": "function", "function": {"name": "baxy_filesystem__read__text", "arguments": "{}"}, "id": "GQBcPA3lep28qbHoRkRqRYMVpOyTli2J"}]}

## 76 / registered / error1 / captured

Último mensaje: Why couldn't you read "c03-invalid-utf8.txt"?

Error HTTP: None; fin: stop.

Respuesta bruta: {"role": "assistant", "content": "Because the file contains invalid UTF-8 characters, making it unreadable."}

## 76 / registered / error1 / one_system

Último mensaje: Why couldn't you read "c03-invalid-utf8.txt"?

Error HTTP: None; fin: stop.

Respuesta bruta: {"role": "assistant", "content": "Because the file contains invalid UTF-8 characters, making it unreadable."}

## 76 / registered / error2 / captured

Último mensaje: Why couldn't you read "c03-invalid-utf8.txt"?

Error HTTP: None; fin: stop.

Respuesta bruta: {"role": "assistant", "content": "Because the file contains invalid UTF-8 characters, making it unreadable."}

## 76 / registered / error2 / one_system

Último mensaje: Why couldn't you read "c03-invalid-utf8.txt"?

Error HTTP: None; fin: stop.

Respuesta bruta: {"role": "assistant", "content": "Because the file contains invalid UTF-8 characters, making it unreadable."}

## 76 / registered / error3 / captured

Último mensaje: Why couldn't you read "c03-invalid-utf8.txt"?

Error HTTP: None; fin: stop.

Respuesta bruta: {"role": "assistant", "content": "{\n  \"question\": \"What do you mean by 'c03-invalid-utf8.txt'?\"\n}"}

## 76 / registered / error3 / one_system

Último mensaje: Why couldn't you read "c03-invalid-utf8.txt"?

Error HTTP: None; fin: stop.

Respuesta bruta: {"role": "assistant", "content": "{\n  \"question\": \"What do you mean by 'c03-invalid-utf8.txt'?\"\n}"}

## 76 / registered / error4 / captured

Último mensaje: Explain what a checksum is in one sentence.

Error HTTP: None; fin: stop.

Respuesta bruta: {"role": "assistant", "content": "A checksum is a small piece of data used to verify that information has been transmitted or stored correctly, by detecting changes or errors."}

## 76 / registered / error4 / one_system

Último mensaje: Explain what a checksum is in one sentence.

Error HTTP: None; fin: stop.

Respuesta bruta: {"role": "assistant", "content": "A checksum is a small piece of data used to verify that information has been transmitted or stored correctly, by detecting changes or errors."}

## 76 / registered / error5 / captured

Último mensaje: Explain what a checksum is in one sentence.

Error HTTP: None; fin: stop.

Respuesta bruta: {"role": "assistant", "content": "A checksum is a small piece of data used to verify that information has been transmitted or stored correctly, by detecting changes or errors."}

## 76 / registered / error5 / one_system

Último mensaje: Explain what a checksum is in one sentence.

Error HTTP: None; fin: stop.

Respuesta bruta: {"role": "assistant", "content": "A checksum is a small piece of data used to verify that information has been transmitted or stored correctly, by detecting changes or errors."}

## 76 / registered / error6 / captured

Último mensaje: Explain what a checksum is in one sentence.

Error HTTP: None; fin: stop.

Respuesta bruta: {"role": "assistant", "content": "{ \"question\": \"What's the purpose of a checksum in data transmission?\" }"}

## 76 / registered / error6 / one_system

Último mensaje: Explain what a checksum is in one sentence.

Error HTTP: None; fin: stop.

Respuesta bruta: {"role": "assistant", "content": "{ \"question\": \"What is a checksum?\" }", "reasoning_content": "The user is asking for a simple explanation of what a checksum is. I need to provide a clear, one-sentence definition in natural English, without technical jargon or assumptions about prior knowledge. The response should be concise and accurate, focusing on the core idea: a checksum is a value used to verify data integrity.\n"}

## 76 / registered / error7 / captured

Último mensaje: {"user_request":"Pon el volumen.","recognized_operations":["audio.volume"],"missing_information":["level"],"response_language":"es"}

Error HTTP: None; fin: stop.

Respuesta bruta: {"role": "assistant", "content": "{\"requested_fields\":[\"level\"],\"question\":\"¿A qué nivel quieres poner el volumen?\"}"}

## 76 / registered / error7 / one_system

Último mensaje: {"user_request":"Pon el volumen.","recognized_operations":["audio.volume"],"missing_information":["level"],"response_language":"es"}

Error HTTP: None; fin: stop.

Respuesta bruta: {"role": "assistant", "content": "{\"requested_fields\":[\"level\"],\"question\":\"¿A qué nivel quieres poner el volumen?\"}"}

## 76 / registered / error8 / captured

Último mensaje: {"user_request":"Pon el volumen.","recognized_operations":["audio.volume"],"missing_information":["level"],"response_language":"es"}

Error HTTP: None; fin: stop.

Respuesta bruta: {"role": "assistant", "content": "{\"requested_fields\":[\"level\"],\"question\":\"¿A qué nivel quieres poner el volumen?\"}"}

## 76 / registered / error8 / one_system

Último mensaje: {"user_request":"Pon el volumen.","recognized_operations":["audio.volume"],"missing_information":["level"],"response_language":"es"}

Error HTTP: None; fin: stop.

Respuesta bruta: {"role": "assistant", "content": "{\"requested_fields\":[\"level\"],\"question\":\"¿A qué nivel quieres poner el volumen?\"}"}

## 76 / registered / error9 / captured

Último mensaje: Pon el volumen.

Error HTTP: None; fin: stop.

Respuesta bruta: {"role": "assistant", "content": "{\"question\": \"¿A qué nivel quieres que esté el volumen?\"}"}

## 76 / registered / error9 / one_system

Último mensaje: Pon el volumen.

Error HTTP: None; fin: stop.

Respuesta bruta: {"role": "assistant", "content": "{\n  \"question\": \"¿A qué nivel quieres que esté el volumen?\"\n}"}

## 76 / registered / selector_control / captured

Último mensaje: {"previous_dialogue_for_references_only": [{"role": "assistant", "content": "¡Hola! Aquí BAXY. ¿En qué te puedo ayudar hoy?"}], "current_request_to_interpret": "Lee el archivo \"C:/Users/usuario/AppData/Local/BAXY/C03-fixtures/ausente47.txt\"."}

Error HTTP: None; fin: tool_calls.

Respuesta bruta: {"role": "assistant", "content": "", "tool_calls": [{"type": "function", "function": {"name": "baxy_filesystem__read__text", "arguments": "{}"}, "id": "l9yJOOIFcAJSznWg2j1OsBqApEbdkCLb"}]}

## 76 / registered / selector_control / one_system

Último mensaje: {"previous_dialogue_for_references_only": [{"role": "assistant", "content": "¡Hola! Aquí BAXY. ¿En qué te puedo ayudar hoy?"}], "current_request_to_interpret": "Lee el archivo \"C:/Users/usuario/AppData/Local/BAXY/C03-fixtures/ausente47.txt\"."}

Error HTTP: None; fin: tool_calls.

Respuesta bruta: {"role": "assistant", "content": "", "tool_calls": [{"type": "function", "function": {"name": "baxy_filesystem__read__text", "arguments": "{}"}, "id": "hTD1qNvSg4amrqe9jFugXgM9oa6oRf8e"}]}
