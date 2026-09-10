# Separar el modelo de BAXY y comprobar la integración

La preocupación del dueño está respaldada por evidencia: una integración puede perder respuestas que el modelo produce correctamente. Los resultados dentro de BAXY no bastan para clasificar la capacidad nativa de K2 ni para descartar un modelo.

La primera comparación 696–698 conservaba instrucciones de BAXY; sus 860 respuestas no aislaban al modelo. La corrección 699 ejecutó las mismas 50 tareas completas en seis perfiles, 300 respuestas sin system, herramientas ni schema de BAXY, con plantillas y ajustes documentados por modelo. No dividió el panel en dos mitades. Es un diagnóstico dirigido, no un benchmark general, y las diferencias de cuantización, backend y presupuesto están declaradas en [REPORTE699](../K2_HORIZON_NATIVE699/REPORTE699.md).

La comparación 737 mantuvo iguales hechos, backend y sampler de K2 en 57 pares, cambiando la petición directa por el prompt de redacción de BAXY. Registró 14 aciertos sólo con BAXY y 3 sólo con la petición directa. Aísla esa parte del prompt; una pasada no caracteriza variabilidad entre semillas ni acredita todas las capas. Hay también errores de entrega que no se deben atribuir a calidad semántica. Véase [REPORT737](../FACTS_PROMPT737/REPORT.md).

El código revisado contiene perfiles explícitos para Granite y una reparación de actor para Qwen (`src/baxy_mind/llm.py:322–372`), además de adaptación de plantilla/transporte (`:5859–5878`). Los validadores de ventana revisados no reciben la familia del modelo. Esa ausencia de nombres no demuestra neutralidad: pueden aceptar mejor las formulaciones habituales de un modelo. La adaptación permitida debe respetar el protocolo y la receta del modelo; la veracidad y la autoridad del catálogo son requisitos comunes.

752B ejecutó 73 turnos de la categoría completa de estado: 50 requisitos humanos y 23 variantes, sobre fuente 751 publicada 4d3885c7 y Qwen registrado. Esta tanda comprueba reparaciones de producto; no compara modelos ni adopta un perfil nuevo. Entradas y criterios son los originales 689/729, panel SHA 5880182539982018f8472524a36ef0eb2fab80a67a4cf80bb3a5fe7cb568d669.

Resultado conservador: **49 acreditados, 22 fallos sustantivos y 2 casos de precisión sin acreditar**. Estos últimos conservan el contenido esencial, pero truncan algunas cifras; aceptarlos elevaría el diagnóstico a 51/73. No se introduce un umbral nuevo ni se concede cobertura. Las consultas de disco y CPU de esta tanda sí obtuvieron respuestas fieles a lecturas frescas, incluidas las dos variantes con tópico antepuesto que antes fallaban. No se atribuye el cambio de puntuación de otra corrida exclusivamente al código: el estado del PC y las generaciones cambian.

| Primera pérdida o límite observado | Casos |
|---|---:|
| Inventario ejecutado, sin composición final capturada/entregada | 2 |
| Inventario no seleccionado o vetado | 3 |
| Borrador fiel de foco rechazado por el validador | 1 |
| Respuesta desde historia, sin nueva lectura | 2 |
| RAM total llamada disponible | 3 |
| Lectura soportada no ejecutada | 7 |
| Internet no medido o Wi-Fi ampliado a cualquier red | 2 |
| Ranking por CPU acumulada presentado como consumo actual | 2 |
| Precisión numérica conservadoramente sin acreditar | 2 |

Un ejemplo directo del sesgo de integración es windows-focus-mixed: el proveedor verificó la ventana con foco y el modelo la identificó correctamente; 18 borradores fueron rechazados por la gramática del validador. Son repeticiones del mismo turno, no 18 casos independientes. H0209/H0663 también muestran propuestas correctas de inventario vetadas en domain_grounding. En la variante inglesa el modelo primero eligió una operación equivocada y después actuó el veto: no se agrupan ambas causas como si fueran una.

El pico muestreado del árbol del conductor fue 3499,56MiB de VRAM (**3,418GiB**) y 2504,98MiB de RAM residente sumada (**2,446GiB**). Es suma de working sets, no RAM privada exclusiva. La telemetría cada 250 ms puede omitir picos más breves. No hubo corte por recursos; 267,687 s de campaña. La mediana de trazas de turno fue 0,960 s y el máximo 27,474 s, incluyendo recuperación; no son tiempos de pantalla/voz. No se acredita el presupuesto conjunto con voz e interfaz visible.

Se verificó el comando efectivo: b9980 CUDA 12.4, ngl 99, ctx 12288 / 3 slots, b2048 / ub256, FA, KV q8_0, reasoning off, cache RAM 0, no-mmap. Modelo, manifiesto, fuente, DLL y runner conservaron sus hashes. 752B terminó exit 0; sesión 91878 recogida, sin inferencia activa. El intento 752 anterior se detuvo por un error del observador al escribir el relevo, antes de medición y de terminales; su código y logs permanecen en STATUS_BATCH752. No cuenta como resultado del modelo.

Siguiente: capturar la petición y el error de las composiciones de inventario que hoy faltan en la auditoría, y reparar las pérdidas estructurales de interpretación/validación con controles de formulaciones distintas. No cambiar modelo, presupuesto o criterios para ocultar esos fallos. Los dos casos de precisión no justifican desviar el trabajo de los bloqueos de capacidad. Las consultas de red y procesos requieren también corregir la observación antes de exigir al modelo una respuesta que los datos no prueban.

No se editó fuente productiva en este tramo: no corresponde repetir Full. La validación de fuente 751 y Full 7 son antecedentes, no aceptación nueva de esta tanda. C03 sigue activo; encuesta: 26 cubiertos, 716 abiertos y 0 no aplicables. Quedan la generalización completa, reserva, UI real, voz/loopback frente a AEC, recursos conjuntos, matriz y Full final. Los literales, payloads, borradores y adjudicaciones están únicamente en el directorio privado C03-status-batch752b-private, en RESPUESTAS.md, ADJUDICACION.md y review.json. RESULT.json publica identificadores, razones y huellas.

REGISTRY_UPDATE.json acredita el enlace de esta corrida a las 50 filas humanas correspondientes, manteniendo intactos textos, autorías, expectativas y estados. La autorización posterior del dueño permite usar históricos y desarrollo para generalización de encuesta; la frescura de la reserva se evalúa aparte.
