# K2: qué cambia al añadir el prompt de BAXY

La comparación terminó: 57 pares, 114 peticiones. El prompt completo de redacción de BAXY mejora el resultado agregado de este conjunto, pero también produce pérdidas concretas. Cada fallo necesita atribución a la capa donde aparece.

| Medida | Pregunta y hechos directos | Prompt de BAXY |
|---|---:|---:|
| Respuestas fieles | 28/57 | 39/57 |
| Fallos de respuesta con datos suficientes | 24/57 | 10/57 |
| Observación insuficiente para el alcance | 5/57 | 5/57 |
| Entrega fallida o vacía | 0/57 | 3/57 |
| Mediana de respuesta final completa (s) | 12.984 | 3.335 |
| Mediana hasta primer texto visible (s) | 9.843 | 3.132 |
| Mediana de generación (tokens/s) | 53.590 | 53.408 |
| Respuestas fieles completas antes de 4 s | 1/57 | 25/57 |

En pares: 25 aciertos compartidos, 14 aciertos sólo con el prompt de BAXY, 3 sólo con la petición directa y 15 pares sin respuesta acreditable en ninguno. Las insuficiencias del dato se conservan aparte, no como un fallo semántico puro del modelo.

El caso H0037 ejemplifica una pérdida: la respuesta directa conserva batería al 96%, sin carga y con corriente conectada; con el prompt de BAXY se niega esa conexión y aparece texto en otro idioma. H0600 entrega la hora directamente, mientras el otro brazo termina sin content. H0625 muestra un error propio de redacción: aun con la capacidad observada, el brazo BAXY afirma 12 GB. En sentido contrario, el prompt reduce varias explicaciones inventadas sobre memoria, GPU y salud del equipo.

En windows-focus-mixed, el brazo BAXY produjo 1.176 tokens y completó en 22,328 s; el primer texto visible llegó a los 22,015 s. El coste principal de esa llamada estaba antes de la respuesta visible. H0350 agotó 120 s de observación sin respuesta final en ese brazo. El presupuesto del producto sigue intacto.

El servidor K2 alcanzó **3448.23 MiB de VRAM (3.367 GiB)** y **801.99 MiB de RAM residente**. Son cifras del servidor, no de BAXY completo. No hubo corte por los guardas de recursos. Duración de campaña: 1406.61 s.

La puntuación es conservadora sobre la respuesta completa. Los casos fronterizos están identificados en ADJUDICATION: permitir la truncación 14,46% en lugar del redondeo 14,47%, aceptar la clasificación AMD integrada a partir del nombre comercial o interpretar el imperativo de H0433 como una errata añade hasta tres aciertos al brazo BAXY. Interpretar favorablemente la coordenada negativa y la hipótesis de batería llena añade hasta dos al directo; penalizar la interpretación de la pregunta como etiqueta en H0037 resta uno al directo. Estas sensibilidades no sustituyen las adjudicaciones principales ni cambian los tests del producto. Las filas de observación insuficiente también pueden tener errores adicionales de redacción, detallados por caso.

El error 500 H0104 pertenece al parser final del servidor: su log conserva un resto con respuesta correcta, pero la API no entregó content. H0600 es distinto: 84 eventos SSE contienen razonamiento y ningún fragmento visible, con stop normal. La causa previa al parser de esa salida vacía no queda identificada. Véase PARSER_ATTRIBUTION.md; no se usa razonamiento como respuesta.

La comparación utiliza K2 Q4 con su plantilla y razonamiento alto; ambas variantes comparten backend, sampler y hechos. La receta se apoya en [la documentación oficial de IFM](https://huggingface.co/IFM/K2-Horizon-3.7B#best-practices). El contexto local de 8.192 tokens y el backend llama.cpp siguen siendo diferencias frente a su referencia BF16/SGLang. Una sola pasada por caso no mide variabilidad entre semillas. El método y los límites de streaming, contexto y timeout están en METHOD.md.

Las pruebas nativas 699 y la integración 736 responden preguntas distintas: 699 mide capacidades sin BAXY; 736 localiza pérdidas en el producto. Esta comparación 737 aísla únicamente el prompt de redacción. No es una nueva comparación completa K2–Qwen ni una validación de todas las capas.

**Siguiente trabajo:** reparar las transformaciones de BAXY ya demostradas que vetan operaciones o prosa correctas, y reproducir el fallo PEG con el parser exacto antes de modificar el backend. Conservar esta comparación como control; cambiar una pieza y comprobar la primera pérdida antes de otra tanda integrada. No promover K2 ni atribuirle fallos de datos, veto o transporte.

C03 continúa activo: encuesta con 26 cubiertos, 716 abiertos y 0 no aplicables; Full5 rojo por los límites originales de packaging y sidecar; validación final de producto/UI/voz y resto del alcance pendientes. Esta comparación no adopta fuente, no cambia manifiesto, no añade cobertura y no ejecuta Full por un diagnóstico sin cambios de producto.

Evidencia pública: PREREG.json, PREFLIGHT.json, RESULT.json, TRANSPORT.json, ADJUDICATION.json y PINS.json. Preguntas, respuestas y payloads completos permanecen en el directorio privado local C03-facts-prompt737-private, en RESPUESTAS.md y sus trazas originales.
