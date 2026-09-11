# Estado de C03 — 11 de septiembre de 2026

**C03 sigue abierto.** La tanda819 obtuvo **40 respuestas válidas de 50**, frente a39 en815: recuperó tres casos y perdió dos. Todos los turnos entregaron respuesta. Las correcciones de reglas y plazos eliminaron los agotamientos de esta ejecución.

| Conducta medida | Válidas819 | Válidas815 |
|---|---:|---:|
| Listas | 4/11 | 3/11 |
| Conteos | 11/12 | 12/12 |
| Memoria | 11/11 | 9/11 |
| CPU | 10/11 | 11/11 |
| Recurso no especificado | 4/4 | 4/4 |
| Memoria de aplicaciones | 0/1 | 0/1 |
| Total | 40/50 | 39/50 |

| Qué falló en819 | Casos |
|---|---:|
| Enumera procesos sin indicar cuántos se observaron; algunas listas también omiten su alcance. | 7 |
| Da el conteo correcto sin explicar que sólo incluye procesos accesibles. | 1 |
| Dice que muestra diez procesos, pero enumera dos. | 1 |
| Atribuye la memoria de un proceso a toda una aplicación. | 1 |

La siguiente corrección añade una frase a las instrucciones existentes para que se informe la población observada. Pasará sus pruebas y una nueva tanda con los mismos50 casos antes de decidir su resultado.

| Tiempo y recursos819 | Resultado |
|---|---:|
| Duración de50 consultas consecutivas | 243,828 segundos |
| Espera mediana hasta terminar el turno | 4,024 segundos |
| Percentil95 de espera | 7,145 segundos |
| Máximo de espera | 7,550 segundos |
| Pico de VRAM | 3.497,56 MiB |
| Pico de RAM residente, por separado | 2.405,50 MiB |

La VRAM queda bajo el techo de4GB y la guarda de3.800MiB. Hubo cero infracciones. La RAM se mide por separado. La espera incluye los50 terminales; no mide voz ni acredita interfaz visible. En815 la mediana era5,262 segundos y el máximo60,002. Las observaciones del PC cambian entre ejecuciones, por lo que no se atribuye toda variación a una reparación aislada.

La validación completa de las reparaciones pasó: **12.898 pruebas Python aprobadas,3 omisiones ambientales y466 subpruebas**; .NET dio **4.657 aprobadas y una omisión agregada**. El registro imprime además16 pruebas optativas que se solapan. Ninguna omisión cuenta como aprobada. El primer intento falló por tres huellas antiguas del código actual; se corrigieron esas referencias y se repitió la compuerta completa. El primer resultado rojo se conserva. Falta el Full final sobre el candidato de cierre.

| Avance formal | Estado |
|---|---|
| Encuesta | 28/742 cubiertos;714 abiertos;0 no aplicables. |
| Matriz C03 | 3/11 cumplidas;5 contradichas;3 pendientes. |
| Categorías nuevas cerradas | 0; total completo no definido. |
| Apertura de aplicaciones | 75 casos preparados, sin ejecutar. |

Estos recuentos no son un porcentaje de cierre. Faltan las conductas restantes, las ocho rutas, cien turnos de aceptación, recuperación, interfaz real, voz y validación final. No hay un plazo fiable de cierre.

La vía de permisos ordinarios del Administrador de tareas quedó descartada: Windows creó una instancia elevada y no expuso las filas. La confirmación de cierre del dueño está recibida; Windows todavía registra PID8204, sin bloquear este trabajo. No se repite la solicitud. BAXY permanece cerrado para uso manual. Encuesta742/revisión1248 y cambios del dueño conservados. Última publicación verificada:1b395b18 en Goal-c03; main5f572ee1 intacto.
