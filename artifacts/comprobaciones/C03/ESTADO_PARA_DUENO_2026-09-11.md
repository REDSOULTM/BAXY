# Estado de C03 — 11 de septiembre de 2026

**C03 sigue abierto.** La tanda 809 del candidato 808 dio **37 respuestas válidas y 13 fallidas** en 50 consultas consecutivas. Empata con 807: recupera siete casos y pierde otros siete. El candidato y la categoría **siguen sin adoptar**, sin nueva cobertura de encuesta. Tras las dos tandas sin mejora neta, la raíz cambiará de estrategia; no seguirá retocando instrucciones a ciegas.

| Qué cambió | Resultado comprobado |
|---|---|
| Se sustituyó el párrafo existente para pedir todas las filas, su orden e identidades. | Las listas mejoran, pero las respuestas de memoria pierden identificadores. El total no mejora. |
| Se comprobó el candidato con sus pruebas y controles de integración. | 204 aprobadas, cero omisiones; Fast correcto. La medición de producto sigue fallando en 13 casos. |

| Qué se midió | Resultado de 809 |
|---|---|
| Respuestas válidas por grupo | Listas 9/11; conteos 12/12; CPU 9/11; memoria 3/11; recurso no especificado 4/4; memoria de aplicaciones 0/1. |
| Comparación con 807 | 37/50 en ambas; siete ganancias y siete pérdidas. Memoria pasa de 7/11 a 3/11. |
| Duración de la tanda | 243,250 segundos. |
| Espera registrada por respuesta | Mediana general 4,209 segundos; listas 6,603; conteos 3,028; percentil 95 general 6,785; máximo 7,516. |
| Pico de VRAM | 3.497,55859375 MiB; por debajo del techo de 4.096 MiB. |
| Pico de RAM residente | 2.399,80859375 MiB; inferior a 4.096 MiB y contabilizada por separado de la VRAM. |

La espera mide eventos shell de los turnos completados, no latencia de voz. Hubo telemetría GPU disponible y cero infracciones de recursos en el árbol de procesos medido. La ejecución terminó con código 0 y conservó la integridad de sus fuentes y componentes. Esto no acredita interfaz visible, voz ni el ciclo completo de BAXY funcionando junto.

| Qué sigue fallando | Qué falta resolver |
|---|---|
| Identidad en las respuestas de memoria | Mantener los identificadores de proceso exigidos, aunque los valores sean correctos. |
| Conteos y alcance | Distinguir procesos observados, filas devueltas y filas mostradas; un recorte no reduce por sí mismo el alcance accesible. |
| Listas CPU incompletas | No declarar diez filas cuando se muestran dos. |
| Memoria de una aplicación, H0675 | Verificar pertenencia y agregado antes de atribuir el consumo de un proceso a toda la aplicación. |

El caso de memoria 08 tiene respuesta final, pero falla por ausencia de identificadores; no es el antiguo fallo sin respuesta. El buen resultado de conteos, 12/12, no resuelve las confusiones de conteo presentes en otras clases de respuesta.

| Validación disponible | Resultado y límite |
|---|---|
| Seis suites dueñas de 808 | 204 aprobadas, cero omisiones, en 2,78 segundos. |
| Fast 808 | Salida 0; compilación Release en 21,84 segundos, cero advertencias y errores. |
| Última Full verde, base 804 anterior | Python: 12.714 aprobadas, 3 omisiones y 466 subpruebas. .NET: 4.642 aprobadas y 1 omisión agregada. Las 16 omisiones optativas impresas no forman un conjunto separado y no se suman. |

**No hay Full 808 acreditada.** Ninguna omisión cuenta como aprobada. Falta una Full final que cubra los cambios posteriores a la base 804. Este estado conserva las validaciones ya documentadas, sin ejecutar nuevas pruebas.

| Avance formal | Estado |
|---|---|
| Encuesta | 28/742 cubiertos; 714 abiertos; 0 no aplicables. |
| Matriz C03 | 3/11 filas cumplidas; 5 contradichas; 3 pendientes. |
| Categorías nuevas cerradas | 0; el registro no define un total completo de categorías. |
| Ocho rutas de respuesta | Pendientes. |
| Apertura de aplicaciones | 75 casos preparados, sin ejecutar. |

Estos recuentos no constituyen un porcentaje de cierre de C03. Faltan las demás conductas, aceptación de cien turnos, errores y recuperación, interfaz real, voz y validación final. Aún no hay un plazo fiable de cierre.

El candidato siguiente,810, presenta nombre y PID juntos en los datos del narrador y conserva las mediciones originales. Sus siete suites aprobaron247pruebas, sin omisiones, en3,04segundos; los controles de integración pasaron, con compilación22,18segundos y cero advertencias/errores. Falta medir sus respuestas en los mismos50casos; aún no se adopta.

BAXY permanece cerrado para uso manual. Encuesta742/revisión1248 intacta; los cambios del dueño se conservan. Última publicación verificada:860c9fdc en Goal-c03; main5f572ee1 permanece intacto.
