# Guardia616: no hubo razonamiento efectivo

Mismos20 casos y subtipo615, perfil GoogleT1/p.95/k64/min0,3072tokens en ambos brazos. Todas40 salidas terminan, pero ninguna contiene reasoning_content, incluidas las20 con enable_thinking=true. Correctas normalizadas: directo12/20, opción thinking11/20. Es una comparación de configuración solicitada, no una medida válida de calidad con razonamiento. No se adopta el subtipo ni se sigue variando su instrucción semántica.

El contraste617 cambia de estrategia: salida nativa, sin gramática forzada, con las mismas definiciones y una instrucción de serialización JSON.613 ya demostró razonamiento real en este backend sin gramática. Se separan formato y comprensión antes de concluir incapacidad del modelo; aún no se demuestra causalidad del formato. La documentación upstream distingue gramáticas inmediatas y diferidas: https://github.com/ggml-org/llama.cpp/blob/master/docs/development/parsing.md. Esa documentación general no sustituye la prueba de esta versión/modelo.

Pico1679,988MiB GPU/1034,320MiB RAM,22,016s. Sin fuente ni registro modificados, sin UI/voz ni cobertura adicional:25/717/0. Fuente606 y su Full siguen siendo la versión validada.
