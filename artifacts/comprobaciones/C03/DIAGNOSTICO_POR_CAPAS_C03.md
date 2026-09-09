# Qué degrada a BAXY: prueba del modelo y de sus capas

Fecha: 2026-09-06. Rama Goal-c03. C03 sigue EN_CURSO.

El problema está en ambos sitios: Granite ya comete errores sin BAXY, y BAXY también puede convertir una respuesta útil en un acuse, una omisión o una salida vacía. No hay evidencia para culpar a una sola pieza ni para afirmar que basta con cambiar el modelo.

## Qué probé

El runtime registrado usa **Granite 4.2 3B Q4_K_M**. Probé también **Qwen3 4B Instruct 2507 Q4_K_M, sin LoRA**, como comparador. No cambié el registro ni descargué o entrené modelos para esta investigación.

Conversación: 9 peticiones idénticas por modelo y ocho etapas: usuario solo, identidad breve, prompt general, políticas/selección de presentación, historial, límite512→128, selección real de ruta con historial y validadores. Son144 respuestas. Temperatura0,7, top_p0,95, top_k40, min_p0,05 y seed0 constantes. Las preguntas son de desarrollo ya conocidas, no aceptación nueva.

Composición: 24 casos por modelo, ocho rutas y entradas españolas, inglesas y mixtas, primero con una instrucción sencilla y hechos sintéticos, después con el prompt del compositor, finalmente con el compositor y sus validadores. Son144 respuestas. Para atribuir rechazos se compara el borrador con el final de la MISMA llamada, conservando todos sus reintentos. Aquí algunas llamadas no tienen seed explícito: dos generaciones independientes no son un par determinista.

Después de localizar un error concreto, corregí sólo esa clasificación y repetí tres preguntas en ambos modelos: seis respuestas más. Total directo294; no significa294 aciertos ni100turnos frescos.

## Hallazgos demostrados

| Pieza | Qué ocurrió | Qué permite concluir |
|---|---|---|
| Granite sin BAXY | En gravedad afirma que las estrellas orbitan alrededor del Sol y añade «nos lleva al cielo cuando volamos (aunque no volamos)». | Hay fallos propios del modelo/configuración local. No todos vienen de BAXY. |
| Identidad y prompt general | Cambian contenido, longitud y tono; en algunos casos mejoran la respuesta y en otros empeoran. | Añadir identidad no es una degradación uniforme. No se puede medir como una resta fija. |
| Selección de presentación | Ambos modelos explican una copia de seguridad con el prompt general. Al añadir la selección de BAXY, Qwen dice «Entiendo que preguntas qué es una copia de seguridad» y Granite «What is a backup?». | BAXY clasifica una pregunta con prefijo de idioma como una observación. Es una causa concreta corregible. |
| Historial | Granite pasa de menor densidad del hielo a «ocupan menos espacio… más densa… y flote». También pasa de dos frases de fotosíntesis a una. El mismo historial ayuda a otras respuestas y Qwen conserva una explicación correcta del hielo. | El historial puede arrastrar contenido y formato. No demuestra que eliminar todo el historial sea correcto. |
| Límite de respuesta | En ambos modelos las nueve respuestas de history y budget son idénticas; ninguna de esas18 queda cortada. | El salto512→128 no causó estos fallos concretos. Un Qwen desnudo sí llegó al corte512 al extender la explicación del hielo. |
| Validación de conversación | La falsedad del hielo de Granite llega intacta a la salida guarded. | Los filtros actuales no verifican conocimiento general; un terminal exitoso no garantiza veracidad. |
| Confirmación | Granite genera «Would you like to confirm closing the window titled Panel local C03? Or cancel the action?». Se rechaza por dos preguntas. Después «Please confirm or cancel: Close the window titled Panel local C03.» se rechaza por no llevar interrogación. Final vacío. | Hay restricciones de forma que bloquean una confirmación comprensible sin mejorar la vinculación de la invocación. |
| Saludo | Qwen genera «¡Hey! Buenas, ¿cómo estás?». Tres borradores se rechazan por welcome_question; final vacío. Granite sufre lo mismo en esa entrada. | El saludo con pregunta social está penalizado en esta ruta. No es falta de capacidad del modelo. |
| Progreso | Qwen genera «I'm looking into the installed applications right now.»; acting_asserted lo rechaza. «Still working on finding the installed applications.» también se rechaza; final vacío. | Los filtros de progreso confunden redacciones válidas de trabajo en curso con otros estados. |
| Hechos del audio | Qwen devuelve «El volumen es 46.» ante volumen Y silencio. El validador lo publica aunque falta muted:false. En otros casos, los reintentos sí corrigen contradicciones. | La comprobación tiene falsos positivos y falsos negativos. No conviene desactivarla entera. |

Estas conclusiones usan ejemplos y transiciones inspeccionados, no una supuesta tasa universal de fallos. Una muestra pequeña y un seed no estiman la calidad general del modelo. La relación entre capas es interactiva: algunas reparan fallos introducidos antes.

## Corrección aplicada

Reutilicé `_strip_request_envelope` al elegir la presentación de conversación. Ahora se clasifica la pregunta dentro de «responde en…», conservando el texto original para que el modelo respete el idioma. No añadí respuestas fijas ni otro clasificador.

Granite, primera respuesta posterior: «Una copia de seguridad es una copia de tus archivos o datos que puedes usar para restaurar tu sistema o información después de un error, pérdida o daño.» Continúa con una explicación bilingüe redundante, pero útil según la rúbrica del dueño.

Qwen, primera respuesta posterior: «Una copia de seguridad es una copia de tus archivos o datos que se almacenan en un lugar seguro, para que si algo pasa, puedas recuperarlos.» Continúa con ejemplos de almacenamiento. Ambos dejaron de limitarse a reconocer/repetir la pregunta.

130pruebas dueñas pasan: `pytest tests/test_c03_request_preservation.py tests/test_compose_contract.py -q`. Fast completo verde: `scripts/test_source_quality.ps1 -Mode Fast`, build0errores/0advertencias. Full final sigue pendiente; este diagnóstico no cierra C03.

## Qué hacer con esta evidencia

1. Conservar el arreglo del prefijo lingüístico y revisar los filtros de forma demostrados: saludo, confirmación y progreso. Mantener verificación de hechos, polaridad y confirmación ligada a la invocación exacta.
2. Corregir la pérdida de campos solicitados antes de aceptar una narración: volumen y silencio deben sobrevivir juntos. No suplirlos con una frase fija.
3. Tratar por separado la calidad factual del modelo y el contexto que recibe. Evaluar contexto pertinente sobre casos nuevos, sin repetir las podas de historial ya descartadas como solución global.
4. Sólo después volver a medir aceptación fresca y Full. Qwen mostró ventajas en varias respuestas, pero también omisiones y errores; esta tanda no justifica promoverlo ni otro LoRA.

## Límites y trazabilidad

Se aplica la aclaración del dueño: español válido para entradas mixtas, explicaciones simples válidas, sin proporción bilingüe obligatoria ni penalización por puntuación menor. Sí importan contradicciones, omisiones solicitadas, efectos inventados y ausencia de respuesta.

La primera versión del instrumento sobrescribía el historial antes de guarded. Fue invalidada para esa comparación, preservada con MEASUREMENT_ERRATUM y reemplazada por v2, que separa datos y comprueba la igualdad de mensajes. No se mezclan sus126salidas con los294diagnósticos directos citados aquí.

Un retorno vacío del compositor no demuestra por sí solo silencio gráfico: la App puede recuperar. El conductor integrado prueba el procesamiento y publicación de mensajes de la App, kernel y providers; no es inspección visual de React, voz ni una sesión gráfica con `py main.py`.

## Todos los literales y prompts

- Conversación por capas, registered: [entradas, respuestas y borradores](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-layer-ablation-v2-registered/RESPUESTAS.md>); [prompts/condiciones/hashes](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-layer-ablation-v2-registered/PREREG.json>).

- Conversación por capas, qwen-base: [entradas, respuestas y borradores](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-layer-ablation-v2-qwen-base/RESPUESTAS.md>); [prompts/condiciones/hashes](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-layer-ablation-v2-qwen-base/PREREG.json>).

- Compositor y validadores, registered: [entradas, respuestas y borradores](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-compositor-ablation-registered/RESPUESTAS.md>); [prompts/condiciones/hashes](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-compositor-ablation-registered/PREREG.json>).

- Compositor y validadores, qwen-base: [entradas, respuestas y borradores](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-compositor-ablation-qwen-base/RESPUESTAS.md>); [prompts/condiciones/hashes](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-compositor-ablation-qwen-base/PREREG.json>).

- Reproducción tras corregir prefijo, registered: [entradas, respuestas y borradores](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-layer-wrapper-fixed-registered/RESPUESTAS.md>); [prompts/condiciones/hashes](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-layer-wrapper-fixed-registered/PREREG.json>).

- Reproducción tras corregir prefijo, qwen-base: [entradas, respuestas y borradores](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-layer-wrapper-fixed-qwen-base/RESPUESTAS.md>); [prompts/condiciones/hashes](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-layer-wrapper-fixed-qwen-base/PREREG.json>).


## Recursos medidos

| Corrida | Segundos | Pico GPU MiB |
|---|---:|---:|
| astra-layer-ablation-v2-registered | 102.67 | 2687.55 |
| astra-layer-ablation-v2-qwen-base | 131.11 | 3499.56 |
| astra-compositor-ablation-registered | 58.66 | 2687.55 |
| astra-compositor-ablation-qwen-base | 53.27 | 3499.56 |
| astra-layer-wrapper-fixed-registered | 6.36 | 2687.55 |
| astra-layer-wrapper-fixed-qwen-base | 6.94 | 3497.56 |

Todos esos procesos terminaron sin error fatal y con el registro intacto; ambos modelos quedaron por debajo de4096MiB en este diagnóstico. Esto no certifica otros perfiles ni todos los componentes simultáneos.

## Aplicación integrada con Granite registrado

21turnos; 21finales publicados. Publicar no equivale a responder bien. PicoGPU2447.55MiB; registro intacto=True.

Tres fallos factuales inequívocos llegaron a publicación: t6 dice audio silenciado aunque el provider y el prompt conservan muted:false; t14 afirma mayor y menor densidad del hielo; t18 afirma cierre después de cancelar, cuando sólo se completó una lectura window.resolve. La siguiente resolución encuentra todavía la ventana y el cierre real sucede tras confirmar en t20. En t6/t18 el borrador falso se acepta y la App lo publica literalmente: la información no se perdió en el provider ni en el kernel.

La confirmación t17 también demuestra degradación por el validador: el primer borrador nombraba la ventana; tras rechazar dos preguntas termina en «¿Confirmar o cancelar?». La misión sigue ligada a su invocación, pero la redacción pierde información. El producto cerró la ventana vacía propia tras la confirmación posterior; no fue necesario cerrarla durante la limpieza.

[Las respuestas integradas y su evaluación](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-layer-product-registered/RESPUESTAS.md>) · [Prompts y respuestas de todos los roles LLM](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-layer-product-registered/sampling.jsonl>) · [Cierre del proceso](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-layer-product-registered/RESULT.json>)

## Actualización: correcciones verificadas y límites pendientes

Se corrigieron cuatro restricciones de presentación demostradas por las capturas:
saludos con pregunta social, puntuación de confirmaciones, verbos capitalizados
interpretados como nombres propios y redacciones válidas de progreso. La pregunta
de conocimiento sigue exigiendo respuesta; la confirmación conserva su invocación
exacta y sus opciones. El progreso se contrasta con la primera afirmación, no con
un gerundio que aparezca después de afirmar un éxito. No se eliminaron las guardas
de hechos ni se añadieron respuestas fijas.

Prueba directa posterior de nueve casos por modelo: Qwen base dio nueve respuestas
útiles; Granite dio cinco útiles, una pendiente de revisión y tres fallos.
Después, Qwen base completó los 21 turnos integrados de desarrollo con 21 respuestas
útiles y fieles bajo la rúbrica del dueño. Hay gramática mejorable; no es motivo
para reprobar una respuesta comprensible. Son casos conocidos, NO 100 turnos
nuevos de aceptación. La captura de Granite anterior no tiene exactamente esta
misma versión de fuente: no se atribuye toda la diferencia sólo al cambio de modelo.

La prueba adicional de doce turnos evita una conclusión prematura: ante
«Open EstudioC03Inexistente.» Qwen publicó «I cannot open EstudioC03Inexistente as
it does not exist.» sin una lectura que comprobara su inexistencia. Las variantes
española, inglesa y mixta tomaron la misma ruta explicit_conversation/unsupported;
la diferencia fue la redacción y su recuperación, no el enrutamiento principal.

El código permite localizar esa frontera: _catalog_unavailable_turn_decision
(src/baxy_mind/__main__.py:5459) considera las peticiones open/abre sin identidad
autenticada en el catálogo como no soportadas. Eso no demuestra inexistencia en
el PC. Es una limitación de resolución/capacidad, no un resultado app_not_found
de un provider. No se debe inventar la causa a partir del nombre del objeto.

Dos intentos fallidos se conservan: aclarar esa limitación en el prompt no cambió
la respuesta falsa. Añadir una guarda causal bloqueó el texto, pero agotó los
reintentos. En la prueba integrada hubo 11 publicaciones de 12 turnos, un
composition_failed, y después dos respuestas que confundieron la petición actual
con la cancelación anterior. Son fallos, no aprobados. Se RETIRARON ese prompt
experimental y la guarda; no se continúa acumulando filtros por frase.

La fuente llm.py volvió exactamente al SHA256
c80241a416a41505841d1580a0adebf4b9724e5d7d908013b6e426e17a20c0aa,
que ya tenía Fast verde (0 errores, 0 advertencias). Tras retirar el experimento:
`pytest tests/test_c03_request_preservation.py tests/test_compose_contract.py
tests/test_goal06_voice.py -q`: 148 passed in 2.07s, sin skips.

El runtime registrado sigue siendo Granite. Los diagnósticos Qwen usan GGUF
explícito y KV q8; el producto por defecto usa KV q4. El pico Qwen integrado fue
3497,56 MiB en 21 turnos y 3499,56 MiB en la prueba adicional, dentro de 4096 MiB
para esos procesos medidos. No certifica voz/wake y todos los componentes juntos.

Falta para C03: resolver la veracidad/recuperación de errores y probar la
continuación real de aclaraciones; fijar un runtime reproducible sin overrides;
100 turnos nuevos adjudicados, averías, UI real y Full final. La investigación
por capas está realizada; C03 continúa EN_CURSO y no se declara terminado.

- astra-presentation-guards-fixed-registered: [entradas y respuestas literales](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-presentation-guards-fixed-registered/RESPUESTAS.md>); [resultado del proceso](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-presentation-guards-fixed-registered/RESULT.json>).
- astra-presentation-guards-fixed-qwen-base: [entradas y respuestas literales](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-presentation-guards-fixed-qwen-base/RESPUESTAS.md>); [resultado del proceso](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-presentation-guards-fixed-qwen-base/RESULT.json>).
- astra-presentation-product-qwen: [entradas y respuestas literales](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-presentation-product-qwen/RESPUESTAS.md>); [resultado del proceso](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-presentation-product-qwen/RESULT.json>).
- astra-clarification-error-qwen: [entradas y respuestas literales](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-clarification-error-qwen/RESPUESTAS.md>); [resultado del proceso](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-clarification-error-qwen/RESULT.json>).
- astra-unsupported-evidence-qwen-base: [entradas y respuestas literales](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-unsupported-evidence-qwen-base/RESPUESTAS.md>); [resultado del proceso](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-unsupported-evidence-qwen-base/RESULT.json>).
- astra-unsupported-cause-qwen-base: [entradas y respuestas literales](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-unsupported-cause-qwen-base/RESPUESTAS.md>); [resultado del proceso](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-unsupported-cause-qwen-base/RESULT.json>).
- astra-clarification-error-guarded-qwen: [entradas y respuestas literales](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-clarification-error-guarded-qwen/RESPUESTAS.md>); [resultado del proceso](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/astra-clarification-error-guarded-qwen/RESULT.json>).