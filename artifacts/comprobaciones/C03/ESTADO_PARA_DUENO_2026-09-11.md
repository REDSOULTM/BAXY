# Estado de C03 — 11 de septiembre de 2026

**C03 sigue abierto.** La última tanda, 813, obtuvo **39 respuestas válidas de 50**, frente a 40 en 811: recuperó tres casos y perdió cuatro. La variante 812 no mejora el conjunto y no se adopta como solución. Las identidades de los procesos siguen conservándose en las filas mostradas.

Se probó dar cada cantidad junto con su significado: procesos observados o filas seleccionadas. Eso recuperó algunos rankings, pero no eliminó las confusiones entre ambas cantidades. La siguiente prueba retira una obligación innecesaria: recitar ambas cantidades incluso cuando sólo se pide un ranking. Conserva los conteos solicitados, las filas y el alcance de la observación.

| Conducta medida | Válidas 813 | Válidas 811 |
|---|---:|---:|
| Listas | 11/11 | 11/11 |
| Conteos | 10/12 | 12/12 |
| Memoria | 9/11 | 8/11 |
| CPU | 9/11 | 9/11 |
| Recurso no especificado | 0/4 | 0/4 |
| Memoria de aplicaciones | 0/1 | 0/1 |
| Total | 39/50 | 40/50 |

| Qué falló en 813 | Casos |
|---|---:|
| Dice que muestra diez procesos, pero aparecen cuatro o cinco. | 6 |
| Confunde una fila devuelta con la cantidad total observada. | 2 |
| Publica el nombre de un campo interno. | 1 |
| Agota los reintentos y no entrega respuesta. | 1 |
| Atribuye la memoria de un proceso a toda una aplicación. | 1 |

La respuesta agotada fue rechazada por contener «current context», una expresión normal que una regla trata como código. Además, afirmaba haber comprobado fuera del alcance observado. Ambos defectos quedan separados; retirar ese veto no convierte la respuesta en verdadera.

| Tiempo y recursos 813 | Resultado |
|---|---:|
| Duración de 50 consultas consecutivas | 262,844 segundos |
| Espera mediana hasta terminar el turno | 4,726 segundos |
| Percentil 95 de espera | 7,016 segundos |
| Máximo de espera | 9,587 segundos |
| Pico de VRAM | 3.497,56 MiB |
| Pico de RAM residente, por separado | 2.449,81 MiB |

La VRAM queda bajo el techo de 4 GB y la guarda operativa de 3.800 MiB. La RAM se mide aparte. Hubo cero infracciones. La espera incluye 49 respuestas publicadas y un turno fallido; no mide voz. Esta ejecución no acredita interfaz visible ni el conjunto completo de BAXY funcionando con voz.

812 pasó 306 pruebas, cero omisiones, en 3,34 segundos; Fast correcto y compilación Release 22,94 segundos, sin advertencias ni errores. 814 pasó las mismas 306 pruebas en 3,62 segundos; Fast pasó: compilación Release en 25,34 segundos, sin advertencias ni errores. El Full 804 anterior dio 12.714 pruebas Python aprobadas, 3 omisiones y 466 subpruebas; .NET 4.642 aprobadas y 1 omisión agregada, con 16 optativas impresas que se solapan. Ninguna omisión cuenta como aprobada. Faltan Full acumulado de adopción y Full final.

| Avance formal | Estado |
|---|---|
| Encuesta | 28/742 cubiertos; 714 abiertos; 0 no aplicables. |
| Matriz C03 | 3/11 cumplidas; 5 contradichas; 3 pendientes. |
| Categorías nuevas cerradas | 0; total completo no definido. |
| Apertura de aplicaciones | 75 casos preparados, sin ejecutar. |

Estos recuentos no son un porcentaje de cierre. Faltan las conductas restantes, las ocho rutas, cien turnos de aceptación, recuperación, interfaz real, voz y validación final. No hay un plazo fiable de cierre.

La prueba de permisos ordinarios del Administrador de tareas no funcionó: Windows creó de nuevo una instancia elevada y no expuso las filas. La vía queda descartada en esta máquina. Se pidió cerrar esa ventana; el trabajo independiente continúa. BAXY permanece cerrado para uso manual. Encuesta 742/revisión 1248 y cambios del dueño conservados. Última publicación verificada: 2bb04ef4 en Goal-c03; main 5f572ee1 intacto.
