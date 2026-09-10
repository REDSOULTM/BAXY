# Reintento con y sin el borrador rechazado — 792

Eliminar el campo rejected_draft no recuperó respuestas finales en esta comparación: **A32/50 y B32/50**, con los mismos32 casos correctos. No se incorpora esa eliminación al runtime. Los fallos de multiplicidad siguen presentes; se cambia el foco a los bloqueantes de integración ya demostrados.

Cada brazo recibió las mismas50 tareas completas, con el compositor real, Qwen registrado y los plazos existentes de4/9 segundos. B eliminó únicamente rejected_draft del JSON de corrección factual; se conservaron los otros campos y el resto del mensaje. El orden alternó AB/BA. Las100 primeras peticiones fueron idénticas a las congeladas; los parámetros efectivos se verificaron en las124 respuestas HTTP exitosas. Se registraron133 intentos,124 éxitos y9 errores, todos con resultado terminal.

| Resultado | A original | B sin borrador en la corrección |
|---|---:|---:|
| Respuestas completas correctas | 32/50 | 32/50 |
| Timeout | 4 | 5 |
| Final vacío sin error HTTP | 5 | 4 |
| Mediana del tiempo final | 1,156s | 1,048s |

Solo48 de50 pares tuvieron primer texto idéntico: H0103 y inventory785-2-3 difirieron antes de la intervención. No se atribuye esa diferencia a B. Las medianas incluyen fallos y no demuestran por sí solas una mejora de rendimiento. El caso4-1 perdió la entrega en ambos brazos por timeout después de un veto antiguo; la diferencia frente a790 no acredita una regresión causada por791.

Root revisó los10 finales diferentes de790 y los9 textos nuevos; los90 finales idénticos conservan su adjudicación. B corrigió la cronología inventada en el segundo borrador de H0023, pero no hubo entrega: el verificador cuenta cero explorer cuando el modelo escribe Explorador. Eso identifica otra discrepancia, no acredita recuperación ni autoriza una lista fija de alias. Los inventarios4-2,5-2 y6-2 siguen perdiendo las cantidades por título.

Duración285,859s; pico3499,56MiB de VRAM y765,25MiB de RAM residente del árbol del compositor/servidor. No son recursos del producto completo. Todas las huellas de fuente, modelo, manifiesto y driver permanecieron intactas. Sesión59555 terminada con exit0 y recogida; sin inferencia activa.

Candidato791 preservado y validado, sin adoptar todavía. Encuesta28cubiertos/714abiertos/0NA. Esta prueba no acredita reserva, UI, voz ni comparación nativa de modelos. La selección de modelo se cierra por orden del dueño en [DECISION_MODELO792.md](../DECISION_MODELO792.md); continúa C03 con Qwen y solo bloqueantes.
