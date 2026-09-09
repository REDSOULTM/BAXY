# C03 — aclaración y adjudicación expresa del dueño

El dueño corrigió la rúbrica tras leer PRUEBAS_RECIENTES_C03.md. Esta aclaración
manda sobre la interpretación anterior del asistente; no cambia respuestas ni
hechos capturados, y no representa una mejora del modelo.

Spanglish incluye español con palabras inglesas, marcas y nombres de productos.
Una petición mixta puede recibir respuesta natural en español. No se exige
alternar idiomas ni traducir una idea. Un saludo bilingüe es aceptable. Se respeta
un idioma pedido expresamente, sin inventar cuotas de frases de cada lengua.
Una explicación sencilla puede ser suficiente; el usuario puede pedir profundizar.

## Cuatro respuestas aprobadas por el dueño

Captura: astra-lora-pilot2-product/paired.json. Se mantienen literales en el informe.

| Turno | Respuesta | Adjudicación actual |
|---|---|---|
| t6 | Son las 13:23; el volumen está al 100% y el audio no está silenciado. | APROBADO por el dueño: el español es válido para esta petición mixta. |
| t7 | ¡Hola! Bienvenido; welcome to the chat. | APROBADO por el dueño: bienvenida aceptable; preferiría coma, pero no lo hace fallar. |
| t8 | La criptografía protege los datos usando códigos; only authorized users can read them. | APROBADO por el dueño como explicación simple de cifrado. |
| t9 | Una copia de seguridad es un archivo; it stores data in case the original is lost or corrupted. | APROBADO por el dueño como explicación simple de copia de seguridad. |

La captura pasa de13/21 a17/21 por corrección de rúbrica, sin volver a ejecutarla.
No se aprueba automáticamente todo el resto ni se elimina evidencia anterior.
La adjudicación anterior se conserva como ADJUDICACION_PRE_ACLARACION.md.
Contradicciones claras (3:23 frente a13:23, mismo volumen que ocupa más espacio),
acciones no verificadas y respuestas que no atienden al pedido siguen siendo fallos.

## Nueva investigación solicitada

El dueño pide probar el LLM individualmente y añadir piezas de BAXY para localizar
la degradación. Se suspenden nuevos ajustes y la promoción de adaptadores hasta
esa comparación. Distinguir Granite registrado de candidatos Qwen experimentales.
Congelar preguntas, hechos, configuración y muestras por modelo; comparar primero
modelo desnudo, identidad, políticas, historial y validación/reintentos, y después
compositor y aplicación real. No confundir un diagnóstico sin efectos con la UI.
