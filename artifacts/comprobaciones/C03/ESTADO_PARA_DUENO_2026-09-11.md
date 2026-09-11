# Estado de C03 — 11 de septiembre de 2026

C03 sigue abierto. Las mismas 50 consultas de procesos dieron **37 respuestas válidas y 13 fallidas**, frente a 28 en la tanda anterior. Las listas esperan mucho menos. El cambio aún no se adopta porque conserva errores y pierde cuatro casos que habían funcionado en una tanda anterior. `main` sigue intacto.

| Qué cambió | Resultado comprobado |
|---|---|
| Las listas densas reciben el plazo que ya tenían las de ventanas. | Las listas válidas suben de 2 a 10 de 11; la mediana baja de 30,82 a 5,12 segundos. |
| Terminó la validación completa. | Python: 12.714 aprobadas,3 omisiones,466 subpruebas. .NET: 4.642 aprobadas y 1 omisión agregada; también imprime 16 omisiones optativas, que no se suman aparte. Ninguna omisión cuenta como aprobada. |
| Se restauraron dos recibos antiguos a los bytes guardados en Git. | Los datos no cambiaron; tres controles de integridad aprobados. Se conserva el primer fallo de validación. |
| Se preparó apertura de aplicaciones. | 75 casos conservados y observación de ventanas revisada; todavía sin ejecutar. |

| Qué se midió | Qué ocurrió |
|---|---|
| Las mismas 50 consultas, seguidas. | 37 válidas y 13 fallidas. Frente a la tanda inmediatamente anterior: 12 recuperadas y 3 perdidas. Frente a 801: 6 recuperadas y 4 perdidas. |
| Listas, conteos, CPU y memoria. | Listas 10/11; conteos 12/12; CPU8/11; memoria 5/11; recurso no especificado 2/4; memoria de aplicaciones 0/1. |
| Tiempo de espera registrado. | Mediana general 4,39 segundos; listas 5,12; conteos 2,99. No incluye audio. |
| Pico de VRAM de BAXY. | 3.497,56 MiB, equivalentes a 3,67 GB, bajo el techo de 4 GB. |
| Pico de RAM residente de BAXY. | 2.392,75 MiB, equivalentes a 2,51 GB, separado de la VRAM. Esta tanda no infringió los límites. |

La medición usa el producto sin ventana ni voz; todavía no certifica todo BAXY funcionando junto. Se conserva el modelo elegido y su configuración.

| Qué falló | Efecto visible |
|---|---|
| Algunas listas no coinciden con lo que anuncian. | Muestran menos procesos o no explican que son una parte de lo observado. |
| Se pierden identificadores o se altera el orden. | Las respuestas sobre memoria no siempre permiten distinguir cada proceso o respetar el ranking. |
| Una respuesta queda rechazada. | El modelo repite un código interno en seis intentos y el usuario termina sin respuesta. |
| Se confunde un proceso con una aplicación. | La memoria de un proceso se presenta como la de toda la aplicación. |

| Qué falta | Próximo paso |
|---|---|
| Reparar las respuestas sobre procesos. | Corregir por separado cómo se explica el alcance y cómo se conservan las filas; medir cada cambio con los mismos 50 casos. |
| Completar las demás conductas de C03. | Aplicaciones, demás requisitos, ocho rutas de respuesta, aceptación de cien turnos, errores y recuperación, interfaz real, voz y validación final. |

**Avance formal:** encuesta **28/742** cubiertos; filas C03 **3/11** cumplidas, 5 contradichas y 3 pendientes. **Categorías: 0 nuevas cerradas en este relevo; el registro todavía no establece un total completo.** Método: contar estados y adjudicaciones existentes; un panel pequeño no es porcentaje del goal. **Estimación de cierre:** todavía sin plazo fiable por los defectos pendientes y la aceptación completa.

Última publicación de evidencia: `7ecd2274` en `Goal-c03`. Candidato actual sin adoptar. BAXY cerrado para uso manual; encuesta original de 742 respuestas y revisión 1248 intacta. La reparación del alcance pasó 198 pruebas específicas, sin omisiones, y los controles de integración con compilación correcta. Se prepara su confirmación en los mismos 50 casos.
