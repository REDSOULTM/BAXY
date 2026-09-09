# C03: límites de capacidad y continuación de aclaraciones

Pruebas de desarrollo, no aceptación fresca. Se conserva cada turno y cada intento fallido. El modelo GGUF sigue bajo override durante estas capturas; el manifiesto registrado permanece intacto. El conductor verifica publicación y estado, no inspección gráfica ni reproducción acústica.

La ruta de identidad no disponible en el catálogo ahora utiliza el compositor de errores existente. La primera prueba de continuidad descubrió dos causas: una clave anidada se interpretaba como palabra cortada y se perdía la condición de efecto verificado; la App convertía una aclaración rechazada en conversación sin conservar su objetivo. Las correcciones y las pruebas automáticas están en ASTRA-TRAMO-28.md.

## astra-boundary-product-qwen

12 turnos, 12 publicados; 61.11 s; pico GPU 3499.56 MiB.

[Todos los turnos](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-boundary-product-qwen/RESPUESTAS.md>) · [Prompts y respuestas de todos los roles](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-boundary-product-qwen/sampling.jsonl>) · [Condiciones previas](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-boundary-product-qwen/PREREG.json>)

## astra-clarification-continuation-qwen

12 turnos, 11 publicados; 74.11 s; pico GPU 3499.56 MiB.

[Todos los turnos](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-clarification-continuation-qwen/RESPUESTAS.md>) · [Prompts y respuestas de todos los roles](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-clarification-continuation-qwen/sampling.jsonl>) · [Condiciones previas](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-clarification-continuation-qwen/PREREG.json>)

## astra-product-default-kv-qwen

21 turnos, 19 publicados; 71.08 s; pico GPU 3067.56 MiB.

[Todos los turnos](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-product-default-kv-qwen/RESPUESTAS.md>) · [Prompts y respuestas de todos los roles](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-product-default-kv-qwen/sampling.jsonl>) · [Condiciones previas](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-product-default-kv-qwen/PREREG.json>)

## astra-clarification-repaired-qwen

12 turnos, 12 publicados; 76.17 s; pico GPU 3499.56 MiB.

[Todos los turnos](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-clarification-repaired-qwen/RESPUESTAS.md>) · [Prompts y respuestas de todos los roles](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-clarification-repaired-qwen/sampling.jsonl>) · [Condiciones previas](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-clarification-repaired-qwen/PREREG.json>)

## astra-clarification-grounded-qwen

12 turnos, 11 publicados; 100.23 s; pico GPU 3499.56 MiB.

[Todos los turnos](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-clarification-grounded-qwen/RESPUESTAS.md>) · [Prompts y respuestas de todos los roles](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-clarification-grounded-qwen/sampling.jsonl>) · [Condiciones previas](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-clarification-grounded-qwen/PREREG.json>)

## astra-clarification-unified-qwen

12 turnos, 12 publicados; 73.19 s; pico GPU 3499.56 MiB.

[Todos los turnos](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-clarification-unified-qwen/RESPUESTAS.md>) · [Prompts y respuestas de todos los roles](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-clarification-unified-qwen/sampling.jsonl>) · [Condiciones previas](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-clarification-unified-qwen/PREREG.json>)


## Estado comprobado al cerrar esta tanda

La última secuencia tiene12respuestas finales. Los cambios80%,60%,40% y la
restauración100% tienen verified+succeeded+applied y lectura posterior coincidente.
La pregunta mixta sobre dispositivo puede ser más directa al pedir el nivel;
ahora conserva contexto y la respuesta40% se aplica. Es desarrollo conocido.
Fast verde,1171pruebas Python+115subtests;1477pruebas del dominio;3pruebas.NET
para conservar aclaración en decisión, plan y argumentos. Full/100/UI pendientes.
