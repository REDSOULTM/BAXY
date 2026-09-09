# Confirmaciones484 — generación por partes, calificación previa a implementar

Causa a contrastar: el contrato actual pide una sola pregunta con opciones literales.
Tras conservar los hechos466, mejorar precisión481 y probar perfiles por modelo482,
las omisiones persisten.472–476 probaron obligación en prosa y roles, sin resolverlo.
Ahora cambia la estructura de generación: tres valores escritos por el modelo,
para acción/objeto, consecuencias suministradas y decisión. Sólo sus valores se unen;
no hay frases visibles fijas, ejemplos resueltos ni un segundo modelo corrector.

Herencia: INVESTIGACION_FORMATO_Y_CLASIFICACION_C03.md y1_toolcalling.md: la gramática
asegura forma, no acierto. Los paneles schema279/294 eran selección/argumentos de tools,
no este compositor. No se reabre aquel selector. Reutilizar el generador estructurado
ya soportado por llama.cpp; si se adopta, sustituye la generación libre en esta ruta.

Contraste2026-09-08: https://arxiv.org/abs/2408.02442 y reproducción con notebooks
https://blog.dottxt.ai/say-what-you-mean.html muestran por qué no atribuir calidad al
formato sin conservar tarea y evaluación. Documentación exacta:
https://github.com/ggml-org/llama.cpp/blob/5266f24da/grammars/README.md explica que el
JSONSchema no se inyecta como instrucción al modelo. Se declara por eso el contrato
en system y se usa la misma descripción y esquema para todos los casos; no se prueba
un esquema oculto. El conjunto es un mecanismo de generación, no una ablación que
atribuya cualquier ganancia únicamente a GBNF o a unas palabras nuevas.

Fuente466/solicitud/situation/contrato literal preservados, perfil oficial Qwen2507,
Q4 allGPU/b10809. Dos semillas fijadas antes;12 confirmaciones+4controles memoria.
Preservar cada JSON bruto, valores visibles, reparaciones, stop y recursos. La sintaxis
perfecta puede seguir fallando semánticamente. No se usan ni ejecutan mensajes reservados.
Criterios de voz/acción/riesgo no se rebajan. Si falla, no barrido de nombres/campos.
