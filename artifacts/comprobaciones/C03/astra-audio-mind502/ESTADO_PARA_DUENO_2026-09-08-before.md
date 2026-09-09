# Estado de C03 — 8 de septiembre de 2026

C03 sigue en curso. Hay correcciones integradas y ahorros medidos, pero todavía
faltan respuestas fiables en algunas confirmaciones y la aceptación completa del
producto. Los resultados de un panel pequeño no son un porcentaje del goal.

## Lo que ya está hecho

- Se consolidaron tus20 mensajes directos y las742 respuestas de la encuesta.
  Se conservaron autoría, expectativas y notas. Las instrucciones automáticas
  de otras tareas quedaron separadas de tus instrucciones.
- Se corrigieron fallos de interpretación, continuidad y transporte de hechos:
  distinguir la cuenta de Windows del nombre conversacional o guardado, conservar
  el contexto durante una aclaración, preguntar por una aplicación que falta,
  y evitar que una presentación nueva reutilice un guardado anterior.
- Se reparó una pérdida concreta en confirmaciones de exportación: Python borraba
  el destino y la posibilidad de sincronización que C# ya había suministrado.
  Los hechos ahora llegan al modelo; aún debe mejorar cómo los explica.
- Se redujo memoria del servidor y se verificó la configuración efectiva de Gemma.
  Los cambios de producto vigentes pasan1404 pruebas de sus componentes,0skips,
  y Fast completo; el build Release terminó sin errores ni advertencias.
- Tu criterio de optimización está en AGENTS.md: consultar papers, documentación
  y reproducciones de usuarios; comprobar versiones y ajustes efectivos; comparar
  calidad, latencia, RAM y VRAM. Un fallo con defaults no descarta un modelo.

## Consumo medido

| Prueba | RAM máxima | VRAM máxima | Alcance |
|---|---:|---:|---|
| Producto antes del ajuste422 |5,18GiB|3,10GiB|Se detuvo por falta de RAM libre|
| Producto Qwen3.5,437 |2,75GiB|3,10GiB|7 de8 respuestas útiles|
| Producto Gemma E2B,464 |2,59GiB|1,65GiB|7 de8 respuestas útiles|
| Compositor Gemma E2B,462 |0,98GiB|1,65GiB|No incluye toda la aplicación|
| Compositor Gemma E4B,471 |1,11GiB|3,20GiB|Calificación pequeña, calidad incompleta|

El ahorro462 mantuvo las mismas respuestas y redujo la RAM del compositor de
2,77 a0,98GiB mediante la carga bajo demanda de embeddings. Esos datos siguen
usando RAM y disco; no significa que todo BAXY esté dentro de la VRAM.

BAXY necesita RAM para la aplicación y las piezas que ejecuta la CPU.4GB de VRAM
es el techo del conjunto, no la meta de consumo. Todavía falta medir el candidato
final con interfaz, micrófono, reconocimiento y activación por voz. La suma de
conjuntos de trabajo puede contar páginas compartidas; no se ha demostrado un
mínimo universal de RAM o VRAM.

## Qué se está resolviendo

En la secuencia integrada464 ya se distingue Jordan guardado de Álvaro mencionado
sólo en conversación. Falta que la confirmación inicial explique claramente la
autorización para activar memoria. En otros casos, se omiten consecuencias al
borrar o exportar; algunas variantes inventaron riesgos y fueron rechazadas.

Se verificaron llama.cpp estable b10809 y posterior b10865, sus correcciones y
los parámetros que realmente recibe el servidor. Actualizar el backend por sí
solo no corrigió las respuestas. También se probaron perfiles documentados por
modelo, separando resultados truncados, fallos de presupuesto y fallos semánticos.

Gemma E4B cabe en su prueba de compositor, pero no resolvió todas las confirmaciones
y su modo de razonamiento llegó a23segundos en un caso. No se promovió. Los cambios
de instrucción y protocolo472–476 tampoco dieron calidad completa y no se añadieron
al producto. Se conserva la evidencia de todos los intentos.

La comparación481 ya terminó: Q4 y Q8 del mismo Qwen2507 resolvieron dos de seis
confirmaciones en cada semilla. Q8 recuperó algunos detalles, pero siguió omitiendo
consecuencias necesarias. Con las mismas capas en GPU, Q4 usó2,40GiB de VRAM y
1,80GiB de RAM; Q8 usó3,50GiB de VRAM y2,45GiB de RAM, y tardó más. Son datos
del compositor, no del producto completo. No se adoptó Q8: más precisión no resolvió
este bloqueo. Los archivos anteriores llamados q8 sólo cambiaban la caché, no los pesos.
El registro de BAXY sigue intacto y no hay una prueba diagnóstica activa.

## Reserva y cierre pendiente

Se revisó el idioma de los204 candidatos:195español,2inglés,2mezcla natural y5
pendientes de contexto. Hay192textos únicos tras normalizar mayúsculas y espacios.
Se comprobaron176literales completos contra los archivos originales y sus hashes.
Seis registros tienen el límite histórico de100caracteres; siete archivos de sesiones
antiguas no están en sus rutas originales. No se reconstruyen mensajes con respuestas
del asistente ni se convierten etiquetas de idioma en pruebas de autoría.

Aún falta revisar continuidad, entrenamiento y exposición de la reserva, congelar100
turnos antes del candidato final y adjudicar100/100 respuestas útiles y fieles. Ninguno
de estos candidatos se está utilizando para ajustar BAXY.

Para cerrar C03 también faltan las ocho rutas completas y las incidencias manuales,
averías y recuperación, interfaz real, voz física, consumo conjunto, runtime e
instalación reproducibles, continuidad de contratos y Full completamente verde sobre
el candidato final, seguido de publicación fuera de main. No hay una estimación de
horas fiable. BAXY permanece cerrado para uso manual, como pediste; la encuesta
original sigue intacta.

Estado técnico y procesos: CHECKPOINT.md y RELEVO_ACTIVO.json. Evidencia detallada:
astra-private-product464, astra-export-facts466, astra-gemma-e4b-qualification471,
astra-reserve-language475, astra-reserve-source477 y astra-qwen-precision479/480/481.

Actualización482/483: Qwen3.5-9B con su perfil recomendado y la corrección reciente
GDN completó la prueba; mejoró algunas confirmaciones pero siguió confundiendo nombres,
objetos y capacidades. No se adoptó. Su compositor usó3,75GiB RAM/2,83GiB VRAM.
También se contrastó la reserva contra327 logs privados y8134 registros de desarrollo:
ninguno de los204 candidatos apareció allí. Eso completa otra comprobación de separación;
no sustituye revisar entrenamiento, contexto ni la aceptación del producto.

## Avance485–490
485corrige clíticos de desmutear;487corrige prohibición independiente con pero/but.3155pass/0skips yFast verde.488mente confirma5seleccionescorrectas; dospedidoscontextuales reales siguen fallando. RAM1,73GiB/VRAM3,42GiB sólo mente, no consumo conjunto final.489recupera herramienta de volumen pero modelo omite desmutear yverificador carece de contexto.490perfil oficialQwen2507 documentado ycomprobado enHTTP tampoco lo resuelve; sin truncamientos ni promoción. Prueba491 de contratos de argumentos nativos en curso. Véanse RESULT/ADJ de cada corrida yCHECKPOINT para estado más reciente.
