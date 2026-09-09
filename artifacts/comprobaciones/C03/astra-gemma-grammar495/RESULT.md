# 495 — preparación del replay, sin resultado de modelo

El prompt tokenizado coincidió con494. El primer POST/completion fue rechazadoHTTP400 antes de generar una respuesta. La fuente de la misma versión muestra diferencias entre tipos de entrada y salida: chat_format entero frente a nombre; preserved_tokens cadenas frente a IDs. Se conserva el fallo y la fuente descargada en la carpeta privada495.

No se guardó el cuerpoHTTP inicial; la causa se identifica por esas incompatibilidades de esquema, sin inventar el mensaje del servidor. No es una prueba fallida de calidad del modelo.496 corrige la adaptación y verifica equivalencia de tokens/parámetros. Registro intacto.
