# Estado de C03 — 11 de septiembre de 2026

**C03 sigue abierto. La última tanda obtuvo 49 respuestas válidas de 50**, frente a 43 en la anterior: recuperó seis casos y no perdió ninguno. Las listas, los conteos y los rankings de procesos pasaron todas sus variantes. Ocho requisitos más de la encuesta quedaron acreditados.

| Conducta medida | Última tanda | Anterior |
|---|---:|---:|
| Listas de procesos | 11/11 | 10/11 |
| Conteos de procesos | 12/12 | 10/12 |
| Memoria de procesos | 11/11 | 9/11 |
| CPU | 11/11 | 10/11 |
| Recurso no especificado | 4/4 | 4/4 |
| Memoria de aplicaciones | 0/1 | 0/1 |
| Total | 49/50 | 43/50 |

El fallo restante atribuye la memoria de un proceso a toda una aplicación. Una aplicación puede tener varios procesos, y esa lectura no demuestra su consumo conjunto. La pregunta sigue pendiente. Se está trabajando en conservar la identidad y la estructura de una lectura de pantalla para poder comprobar el grupo y su memoria; todavía no se cuenta como solución.

| Tiempo y recursos | Resultado |
|---|---:|
| Duración de 50 consultas consecutivas | 246,829 segundos |
| Espera mediana | 4,229 segundos |
| Percentil 95 de espera | 6,672 segundos |
| Máximo de espera | 7,352 segundos |
| Pico de VRAM | 3.497,56 MiB |
| Pico de RAM residente, separado | 2.454,28 MiB |

La VRAM quedó bajo el techo de 4 GB. Hubo cero infracciones de las guardas y los 50 turnos entregaron respuesta. La espera mediana anterior fue 4,753 segundos. Estas mediciones no acreditan la interfaz visible ni la voz.

La corrección pasó 696 pruebas específicas sin omisiones, 17 pruebas de referencias y una omisión ambiental por datos históricos ausentes. También pasó la comprobación de código y compilación, sin advertencias ni errores. El último Full acumulado anterior tuvo 12.898 pruebas Python aprobadas, tres omisiones ambientales y 466 subpruebas; .NET tuvo 4.657 aprobadas y una omisión agregada, con 16 pruebas optativas impresas que se solapan. Las omisiones no cuentan como aprobadas. Falta el Full final del candidato de cierre.

| Avance formal | Estado |
|---|---|
| Encuesta | 36/742 cubiertos; 706 abiertos; 0 no aplicables. |
| Matriz C03 | 3/11 cumplidas; 5 contradichas; 3 pendientes. |
| Categorías nuevas cerradas | 0; total completo aún no definido. |
| Apertura de aplicaciones | 75 casos preparados, sin ejecutar. |

El avance se cuenta por requisitos verificados con todas sus variantes pertinentes. El 49/50 de este panel no es el porcentaje de cierre de C03. Faltan las conductas restantes, las ocho rutas de respuesta, cien turnos de aceptación, recuperación, interfaz real, voz y validación final. No hay un plazo fiable de cierre.

BAXY permanece cerrado para uso manual. La encuesta original y los cambios del dueño se conservan. La fuente medida está publicada en Goal-c03, commit f70ea94c; main sigue intacto. El [informe824](PROCESS_BATCH824/REPORT.md) y la [adopción de ocho requisitos](PROCESS_BATCH824/ADOPTION.json) conservan la evidencia y sus límites.
