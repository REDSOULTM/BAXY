# Alcance de la comparación

El compositor no pone seed explícito en todos los payloads. El instrumento preservó esa ausencia: dos llamadas con el mismo prompt pueden producir redacciones diferentes. Las etapas plain/prompt son exploratorias, no pares deterministas. La igualdad de mensajes sí se comprobó antes de guarded. Para atribuir un rechazo al validador, usar el primer borrador y los reintentos de ESA MISMA llamada guarded, capturados en posts.jsonl y compose-audit.jsonl; RESPUESTAS.md los incluye. No atribuir al validador diferencias entre dos generaciones independientes.

Los hechos son sintéticos y conocidos por el instrumento. No prueban lecturas reales del PC ni la publicación final de la aplicación. Un retorno vacío es un fallo en esta frontera, no prueba por sí solo de silencio de la UI (la App puede intentar recuperación).
