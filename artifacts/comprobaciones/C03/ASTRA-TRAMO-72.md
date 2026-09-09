# C03 — recuperación y modelo heredado — tramos68–72

Estado: Qwen3.5 medido en producto aislado y no promovido; registro sigue Qwen3-2507.
No cambios de producción desde el guard63. C03 completo EN_CURSO.

68 refuta borrar historial/respuestas:5/6 con contexto completo,1/6 sólo usuarios,
1/6 sin contexto. Read the second one falla incluso completo.69/70 clasificación
previa needs_dialogue produce5/10 decisiones/selecciones correctas, tanto con
JSON Schema como salida libre. Descartada, no añadir otro clasificador.
PRUEBAS_REFERENCIAS_Y_MODELO68_71.md conserva métodos, literales y fuentes.

Cambio de hipótesis: mismo input/contexto/tools/prompts/sampler, modelo heredado
Qwen3.5-4B Q4_K_M.71 selecciona9/10 frente a6/10 con2507. Es más capaz en este
panel, pero añade lectura a ¿Por qué no pudiste?. No validar ese efecto ni ignorarlo.
GPU3175,56MiB,RAM4529,92MiB,12,89s,26501exit0,registro intacto. Comando nativo
real y hashes en PREREG/llama-command. No-thinking,3x4096,KVq8,ngl99,b9980CUDA.
Se conservan fallos de conocimiento de las pruebas antiguas qwen35; otro rol/perfil.

72 terminó97303exit0, files72-qwen35: mismo prefijo técnico de5 archivos53–64,
después pregunta por el fallo UTF8, checksum, capacidades, hora/audio/CPU y
volumen sin nivel (debe aclarar sin cambiar audio). Sólo override de GGUF en
proceso aislado; hook47 observa paquetes. No afinar sampler ni prompts de paso.
Resultado5/10 útiles,137,17s,GPU3177,56MiB,RAM6653,66MiB,registro intacto.
No promover. PRUEBAS_PRODUCTO_Y_HECHOS72_73.md/TRAMO72_73_PINS.json conservan
todos los turnos, borradores rechazados y resultados. No hubo boot_stage.label
no nulo; no confundir borradores de progreso con publicación.
73 reemplaza resultados previos por fuente tipada en replay nativo2507:8/10
frente a6/10, pero no recupera file2/file3. No cambio a historial de producción.
No UI/audio humano, reserva100 ni promoción acreditados. No Full durante reparación.
