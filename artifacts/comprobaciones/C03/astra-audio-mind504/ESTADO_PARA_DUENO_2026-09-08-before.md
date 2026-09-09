# Avance de BAXY y C03 — 8 de septiembre de 2026

C03 sigue activo. Ya hay correcciones verificadas y ahorros de memoria, pero falta la aceptación completa del producto. Una tanda aprobada no equivale a un porcentaje del goal.

Se reunieron tus 20 mensajes directos y las 742 respuestas de la encuesta, conservando autoría y expectativas. Las instrucciones automáticas de otras tareas quedaron separadas. Esa base orienta las conductas generales junto con AGENTS.md y la identidad de BAXY.

Se corrigieron pérdidas de contexto y de hechos: distinguir la cuenta de Windows del nombre conversacional o guardado, evitar reutilizar un guardado anterior al presentarse alguien nuevo, preguntar por una aplicación que falta y conservar el destino y la posibilidad de sincronización en las confirmaciones de exportación. Algunas confirmaciones aún omiten consecuencias o explican mal la autorización; siguen pendientes.

En el audio, se corrigieron la segunda acción tras pero/but, las negaciones independientes, los clíticos de desmutear y ponle, las peticiones de volumen sin nivel y la respuesta numérica a una aclaración. El texto citado sigue siendo contenido.

La prueba real de la mente 502 comprobó tu secuencia «Ponle volumen al pc» → «Al 100, pero desmutealo»: pide el nivel cuando falta y después genera volumen 100 y silencio desactivado, con ambos argumentos correctos. El segundo pedido pasó de fallar en 6,188 segundos a preparar su interpretación y plan en unos 0,484 segundos. En esa tanda hubo 12 propuestas/aclaraciones correctas de 14 y 10 bindings correctos de 10. No se ejecutó audio físico ni la interfaz de escritorio.

El caso «perfecto, necesito lo dessilencies pls» ya pasa las pruebas focales de la siguiente corrección, 503, que está en validación. La respuesta que define desmutear aún contiene prosa interna y una oferta de control del micrófono que esa respuesta no acredita.

La fuente 501 pasó siete suites: 3377 pruebas y 121 subpruebas aprobadas, cero skips, en 48,89 segundos. Fast y compilación Release también pasaron, sin advertencias ni errores. La compuerta Full final sigue pendiente; durante la reparación se ejecutan las pruebas dueñas y Fast.

## Recursos medidos

| Medición | RAM máxima | VRAM máxima | Qué incluye |
|---|---:|---:|---|
| Producto antes del ajuste 422 | 5,18 GiB | 3,10 GiB | Se detuvo por falta de RAM libre |
| Producto Qwen3.5, 437 | 2,75 GiB | 3,10 GiB | Conductor de producto; 7/8 respuestas útiles |
| Producto Gemma E2B, 464 | 2,59 GiB | 1,65 GiB | Conductor de producto; 7/8 respuestas útiles |
| Compositor Gemma E2B, 462 | 0,98 GiB | 1,65 GiB | Servidor y compositor; no toda la aplicación |
| Gemma E2B original, 497 | 1,01 GiB | 1,64 GiB | Prueba nativa de selección; calidad incompleta |
| Mente y planes actuales, 502 | 1,73 GiB | 3,42 GiB | Qwen registrado, recursos semánticos y conductor; sin UI/voz |

El ajuste de caché y mapeo redujo RAM del producto; la carga bajo demanda de Gemma mantuvo sus respuestas y redujo RAM del compositor. Sigue habiendo uso de RAM y disco. No se ha conseguido ni demostrado que todo BAXY resida sólo en VRAM. Tampoco está medido un mínimo universal. El techo de 4 GiB corresponde al conjunto y aún falta verificar el candidato final con interfaz, micrófono, reconocimiento y activación por voz.

## Comparación de modelos

Tu criterio está escrito en AGENTS.md: investigar papers, documentación y reproducciones de usuarios; comprobar modelo, cuantización, versión de llama.cpp, plantilla y parámetros efectivos; medir calidad, tiempo, RAM y VRAM. Los defaults no bastan para descartar un modelo y una receta documentada tampoco prueba que sea el óptimo.

Se contrastaron llama.cpp b9980, estable b10809 y posterior b10865, con las correcciones aplicables a cada familia. Actualizar el backend por sí solo no corrigió la semántica. Qwen Q8 y Qwen3.5-9B se probaron con perfiles documentados, pero no resolvieron todos los fallos de confirmación/memoria y no se promovieron.

El Gemma original evitó las repeticiones de llamadas del checkpoint publicado en la comparación 497, pero siguió invirtiendo el silencio en tres respuestas contextuales y violando la interfaz sin argumentos en cuatro. Tampoco se promovió. Las reparaciones 498–501 corrigen pérdidas demostradas del código y mantienen el runtime registrado.

## Qué falta para cerrar

- Resolver las respuestas y confirmaciones restantes de las ocho rutas y los incidentes de la sesión manual, incluidos aplicaciones, reproducción, capacidades y cierre de BAXY.
- Certificar y congelar 100 turnos humanos frescos, separados del desarrollo, y obtener 100/100 respuestas útiles y fieles en español, inglés y mezcla natural. Hay 204 candidatos potenciales; todavía ninguno certificado ni ejecutado para aceptación. Faltan comprobaciones de contexto, entrenamiento y exposición.
- Verificar recuperación ante averías, interfaz real, voz y audio físico, ASR/wake y recursos del conjunto.
- Verificar runtime e instalación, continuidad C04–C09, Full final íntegramente verde y publicación fuera de main.

BAXY permanece cerrado para uso manual. La encuesta terminada se conserva. El estado técnico exacto y las sesiones activas están en CHECKPOINT.md; los resultados y fallos intermedios siguen guardados por tramo.
