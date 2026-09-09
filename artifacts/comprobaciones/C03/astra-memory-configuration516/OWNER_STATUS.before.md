# Avance de BAXY y C03 — 8 de septiembre de 2026

C03 sigue activo. Ya hay correcciones verificadas y ahorros de memoria, pero falta la aceptación completa del producto. Una tanda aprobada no equivale a un porcentaje del goal.

Se reunieron tus 20 mensajes directos y las 742 respuestas de la encuesta, conservando autoría y expectativas. Las instrucciones automáticas de otras tareas quedaron separadas. Esa base orienta las conductas generales junto con AGENTS.md y la identidad de BAXY.

Se corrigieron pérdidas de contexto y de hechos: distinguir la cuenta de Windows del nombre conversacional o guardado, evitar reutilizar un guardado anterior al presentarse alguien nuevo, preguntar por una aplicación que falta y conservar el destino y la posibilidad de sincronización en las confirmaciones de exportación. Algunas confirmaciones aún omiten consecuencias o explican mal la autorización; siguen pendientes.

En el audio, se corrigieron la segunda acción tras pero/but, las negaciones independientes, los clíticos de desmutear y ponle, las peticiones de volumen sin nivel y la respuesta numérica a una aclaración. El texto citado sigue siendo contenido.

La prueba real de la mente 502 comprobó tu secuencia «Ponle volumen al pc» → «Al 100, pero desmutealo»: pide el nivel cuando falta y después genera volumen 100 y silencio desactivado, con ambos argumentos correctos. El segundo pedido pasó de fallar en 6,188 segundos a preparar su interpretación y plan en unos 0,484 segundos. En esa tanda hubo 12 propuestas/aclaraciones correctas de 14 y 10 bindings correctos de 10. No se ejecutó audio físico ni la interfaz de escritorio.

Las correcciones de audio ya pasaron por la mente real. «perfecto, necesito lo dessilencies pls» propone silencio desactivado; «Al100,pero desmutealo» conserva volumen100 y silencio desactivado. En la última tanda integrada,507, hubo18 propuestas/aclaraciones o respuestas útiles de20 y11 planes/argumentos correctos de11. El audio físico y la interfaz con estas correcciones siguen pendientes.

También se corrigió una frontera de conversación: el selector de herramientas estaba entregando su explicación interna como respuesta. Se eliminó ese transporte y la conversación existente vuelve a redactar bajo la identidad y el idioma de BAXY. Esto corrigió además una respuesta que atribuía a BAXY el nombre del usuario. No se añadieron respuestas fijas.

La fuente506 pasó siete suites:3404 pruebas y121 subpruebas aprobadas, cero skips,53,88s. Fast y compilación Release pasaron, sin advertencias ni errores. Full final sigue pendiente. Dos fallos de conversación aún permanecen: una definición española inexacta y el recuerdo que acepta un nombre escrito equivocadamente por el asistente en vez del que declaró el usuario.

Se comparó el perfil actual con el perfil oficial de Qwen2507 en los mismos siete casos y dos semillas. La revisión semántica final dejó ambos perfiles en5/7 con semilla0 y6/7 con semilla17; los28 casos tuvieron generación real auditada y ninguna salida se cortó. La recomendación por sí sola no resolvió los fallos. La regla de procedencia509 no corrigió el recuerdo equivocado y no se adoptó. Los controles añadidos ya pasaban antes. La prueba510 conserva todo el contenido y quién lo escribió, pero compara presentarlo como turnos previos o como datos citados; se comprueba que aún permita responder sobre lo que dijo el asistente. Todavía es un diagnóstico privado, no una solución adoptada.

## Recursos medidos

| Medición | RAM máxima | VRAM máxima | Qué incluye |
|---|---:|---:|---|
| Producto antes del ajuste 422 | 5,18 GiB | 3,10 GiB | Se detuvo por falta de RAM libre |
| Producto Qwen3.5, 437 | 2,75 GiB | 3,10 GiB | Conductor de producto; 7/8 respuestas útiles |
| Producto Gemma E2B, 464 | 2,59 GiB | 1,65 GiB | Conductor de producto; 7/8 respuestas útiles |
| Compositor Gemma E2B, 462 | 0,98 GiB | 1,65 GiB | Servidor y compositor; no toda la aplicación |
| Gemma E2B original, 497 | 1,01 GiB | 1,64 GiB | Prueba nativa de selección; calidad incompleta |
| Mente, planes y conversación, 507 | 1,74 GiB | 3,42 GiB | Qwen registrado, recursos semánticos y conductor; sin UI/voz |

El ajuste de caché y mapeo redujo RAM del producto; la carga bajo demanda de Gemma mantuvo sus respuestas y redujo RAM del compositor. Sigue habiendo uso de RAM y disco. No se ha conseguido ni demostrado que todo BAXY resida sólo en VRAM. Tampoco está medido un mínimo universal. El techo de 4 GiB corresponde al conjunto y aún falta verificar el candidato final con interfaz, micrófono, reconocimiento y activación por voz.

## Comparación de modelos

Tu criterio está escrito en AGENTS.md: investigar papers, documentación y reproducciones de usuarios; comprobar modelo, cuantización, versión de llama.cpp, plantilla y parámetros efectivos; medir calidad, tiempo, RAM y VRAM. Los defaults no bastan para descartar un modelo y una receta documentada tampoco prueba que sea el óptimo.

Se contrastaron llama.cpp b9980, estable b10809 y posterior b10865, con las correcciones aplicables a cada familia. Actualizar el backend por sí solo no corrigió la semántica. Qwen Q8 y Qwen3.5-9B se probaron con perfiles documentados, pero no resolvieron todos los fallos de confirmación/memoria y no se promovieron.

El Gemma original evitó las repeticiones de llamadas del checkpoint publicado en la comparación 497, pero siguió invirtiendo el silencio en tres respuestas contextuales y violando la interfaz sin argumentos en cuatro. Tampoco se promovió. Las reparaciones498–506 corrigen pérdidas demostradas del código y mantienen el runtime registrado. El ensayo508 del perfil de conversación tampoco justifica promover un cambio de configuración.

## Qué falta para cerrar

- Resolver las respuestas y confirmaciones restantes de las ocho rutas y los incidentes de la sesión manual, incluidos aplicaciones, reproducción, capacidades y cierre de BAXY.
- Certificar y congelar 100 turnos humanos frescos, separados del desarrollo, y obtener 100/100 respuestas útiles y fieles en español, inglés y mezcla natural. Hay 204 candidatos potenciales; todavía ninguno certificado ni ejecutado para aceptación. Faltan comprobaciones de contexto, entrenamiento y exposición.
- Verificar recuperación ante averías, interfaz real, voz y audio físico, ASR/wake y recursos del conjunto.
- Verificar runtime e instalación, continuidad C04–C09, Full final íntegramente verde y publicación fuera de main.

BAXY permanece cerrado para uso manual. La encuesta terminada se conserva. El estado técnico exacto y las sesiones activas están en CHECKPOINT.md; los resultados y fallos intermedios siguen guardados por tramo.
