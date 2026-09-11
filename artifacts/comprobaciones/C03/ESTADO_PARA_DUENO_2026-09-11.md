# Estado de C03 — 11 de septiembre de 2026

**C03 sigue abierto.** La última tanda, 815, obtuvo **39 respuestas válidas de 50**, igual que 813: recuperó diez casos y perdió diez. Al simplificar las instrucciones mejoraron los conteos y rankings, pero muchas listas dejaron de indicar cuántos procesos se habían observado. La variante no resuelve la categoría.

Ahora se han corregido dos reglas que descartaban expresiones normales y se ha dado a las respuestas de varios procesos el plazo que ya existía para listas densas. La primera confundía «current context» con código; la segunda confundía «complete» con una palabra cortada. Pasan 289 pruebas C# y 696 Python, sin omisiones. La validación completa ya pasó; ahora falta medir estas correcciones en BAXY.

| Conducta medida | Válidas 815 | Válidas 813 |
|---|---:|---:|
| Listas | 3/11 | 11/11 |
| Conteos | 12/12 | 10/12 |
| Memoria | 9/11 | 9/11 |
| CPU | 11/11 | 9/11 |
| Recurso no especificado | 4/4 | 0/4 |
| Memoria de aplicaciones | 0/1 | 0/1 |
| Total | 39/50 | 39/50 |

| Qué falló en 815 | Casos |
|---|---:|
| Publica la lista sin indicar cuántos procesos se observaron; algunas tampoco explican el alcance o recorte. | 7 |
| Agota los reintentos y no entrega la lista. | 1 |
| Agota el plazo al preparar un ranking de cinco procesos. | 1 |
| Identifica los dos procesos de mayor memoria, pero omite sus cantidades y unidades. | 1 |
| Atribuye la memoria de un proceso a toda una aplicación. | 1 |

Retirar un rechazo falso no convierte en correcta una respuesta que también omite datos solicitados. Los 50 veredictos de 815 se conservan.

| Tiempo y recursos 815 | Resultado |
|---|---:|
| Duración de 50 consultas consecutivas | 414,11 segundos |
| Espera mediana hasta terminar el turno | 5,262 segundos |
| Percentil 95 de espera | 11,051 segundos |
| Máximo de espera | 60,002 segundos |
| Pico de VRAM | 3.497,56 MiB |
| Pico de RAM residente, por separado | 2.429,73 MiB |

La VRAM queda bajo el techo de 4 GB y la guarda de 3.800 MiB. La RAM se mide aparte. Hubo cero infracciones. La espera incluye 48 respuestas publicadas y dos turnos fallidos; no mide voz ni acredita interfaz visible. El Administrador de tareas estaba abierto en 815 y no en 813: no se atribuye el aumento de espera exclusivamente al cambio de instrucciones.

La validación completa de las correcciones pasó: **12.898 pruebas Python aprobadas, 3 omisiones ambientales y 466 subpruebas**; .NET dio **4.657 aprobadas y una omisión agregada**. El registro imprime además 16 pruebas optativas que se solapan. Ninguna omisión cuenta como aprobada. El primer intento falló por tres huellas antiguas del código actual; se actualizaron esas referencias, sin cambiar los datos históricos, y se repitió la compuerta entera. Falta la medición de respuestas y el Full final de cierre.

| Avance formal | Estado |
|---|---|
| Encuesta | 28/742 cubiertos; 714 abiertos; 0 no aplicables. |
| Matriz C03 | 3/11 cumplidas; 5 contradichas; 3 pendientes. |
| Categorías nuevas cerradas | 0; total completo no definido. |
| Apertura de aplicaciones | 75 casos preparados, sin ejecutar. |

Estos recuentos no son un porcentaje de cierre. Faltan las conductas restantes, las ocho rutas, cien turnos de aceptación, recuperación, interfaz real, voz y validación final. No hay un plazo fiable de cierre.

La prueba de permisos ordinarios del Administrador de tareas no funcionó: Windows creó una instancia elevada y no expuso las filas. Esa vía queda descartada. Tras la respuesta del dueño sobre el cierre anterior, Windows todavía muestra la nueva ventana de diagnóstico; la petición de cierre ya está enviada y no bloquea las correcciones. BAXY permanece cerrado para uso manual. Encuesta 742/revisión 1248 y cambios del dueño conservados. Última publicación verificada: b997816d en Goal-c03; main 5f572ee1 intacto.
