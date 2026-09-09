# Conversación con perfil propio de Qwen2507

Revisión semántica v2: ambos perfiles obtienen5/7 con semilla0 y6/7 con semilla17. Una definición válida sobre salida de audio/voz no tiene que enumerar todos los sentidos; el rechazo anterior era demasiado estricto. Se conservan RESULT-v1 y ADJUDICATION-v1. No cambia la comparación entre perfiles ni el fallo de recuerdo. Se probó la recomendación oficial T0,7/top-p0,8/top-k20/min-p0/presence0/repeat1 frente al perfil registrado, sin modificar mensajes, contratos, fuente, backend o precisión.28 de28 casos tuvieron generación real con el perfil auditado; sólo cambiaron campos de muestreo. Las84respuestas HTTP terminaron en stop; máximo87tokens de salida y2223totales, sin cortes.

Persisten la definición española inexacta y la prioridad deMorgan(asistente) sobreJordan(usuario). La configuración recomendada no los resuelve. No se promueve ni se sigue barriendo temperaturas. Esto no es una conclusión global contraQwen; se ha descartado esta intervención concreta sobre estos payloads.

RAM1770,398MiB/GPU3497,559MiB;74,313s; registro intacto. Sin efectos/UI/voz/aceptación. Sesión90270 recogida exit0. Fuente oficial: https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507, Best Practices. El límite256 se mantuvo para respuestas breves y todas acabaron naturalmente; no se convirtió un corte en pass.
