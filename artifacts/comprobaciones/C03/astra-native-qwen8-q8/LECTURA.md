# Qwen3 8B con carga parcial — desarrollo, 2026-09-06

Activo heredado, Q4_K_M de 5.027.783.488 bytes, huella en PREREGISTRO.json.
20 capas en GPU, resto CPU, caché q8_0, contexto 4096 por slot y tres slots.
Perfil de texto sin thinking: temperatura 0.7, top_p 0.8, top_k 20, min_p 0,
según [Qwen](https://huggingface.co/Qwen/Qwen3-8B#best-practices).
No se modificó el registro. BAXY sigue usando Granite.

El rechazo histórico de este activo era de selección de herramientas, no de
estas doce preguntas de contenido. En este diagnóstico se contrapuso el
compositor anterior (llm.py e275ccd2…) con un prompt directo, ambas llamadas con
el mismo sampler y seed por pregunta. Todas son desarrollo, nunca aceptación.

El compositor da 10/12 respuestas útiles: corrige las dos operaciones en español,
pero en la tercera repite la definición de multiplicar sin dar 84. El caso de
cifrado pierde spanglish y añade la distinción falsa «en lugar de letras, usa
números y símbolos». El brazo directo también falla: en el primer caso dice que
no da la respuesta y que no es 96. No basta para promover este candidato.

Sí mejora definiciones de router y checksum frente a varios modelos pequeños.
Tiempo de cada composición: 6.4–16.3 s; pico atribuido del proceso de diagnóstico
3315.57 MiB. No certifica voz, UI ni el límite de toda BAXY. El coste de CPU y los
plazos de los otros roles requieren comparación integrada antes de cualquier
promoción. Esta medición precede la retirada del contrato que imponía usar sólo
los hechos observados incluso en conversación; no describe esa fuente posterior.
