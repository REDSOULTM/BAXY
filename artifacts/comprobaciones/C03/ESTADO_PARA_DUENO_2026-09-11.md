# Estado de C03 — 11 de septiembre de 2026

**C03 sigue abierto.** La tanda 822 obtuvo **43 respuestas válidas de 50**, frente a 40 en la tanda 819: recuperó siete casos y perdió cuatro. Las listas vuelven a informar cuántos procesos se observaron. Todos los turnos entregaron respuesta.

| Conducta medida | Válidas 822 | Válidas 819 |
|---|---:|---:|
| Listas | 10/11 | 4/11 |
| Conteos | 10/12 | 11/12 |
| Memoria | 9/11 | 11/11 |
| CPU | 10/11 | 10/11 |
| Recurso no especificado | 4/4 | 4/4 |
| Memoria de aplicaciones | 0/1 | 0/1 |
| Total | 43/50 | 40/50 |

| Qué falló en 822 | Casos |
|---|---:|
| Expone un nombre de campo interno en la respuesta. | 4 |
| Da el conteo correcto sin explicar que sólo incluye procesos accesibles. | 2 |
| Atribuye la memoria de un proceso a toda una aplicación. | 1 |

La siguiente corrección sustituye la referencia al campo interno por palabras naturales en una sola frase. Pasaron 696 pruebas específicas sin omisiones,17 pruebas de referencias y una omisión ambiental por datos históricos ausentes. También pasó la comprobación de código y compilaciónRelease, sin advertencias ni errores. Falta medir de nuevo los mismos 50 casos.

| Tiempo y recursos 822 | Resultado |
|---|---:|
| Duración de 50 consultas consecutivas | 266,797 segundos |
| Espera mediana | 4,753 segundos |
| Percentil 95 de espera | 7,474 segundos |
| Máximo de espera | 8,780 segundos |
| Pico de VRAM | 3.497,56 MiB |
| Pico de RAM residente, separado | 2.413,78 MiB |

La VRAM queda bajo el techo de 4 GB y la guarda de 3.800 MiB. Hubo cero infracciones. La RAM se mide aparte. La espera incluye los 50 terminales; no mide voz ni acredita interfaz visible. La mediana anterior era 4,024 segundos: mejoran las listas, con mayor espera en esta ejecución.

El último Full acumulado pasó:12.898 pruebasPython aprobadas,3 omisiones ambientales y 466 subpruebas; .NET dio 4.657 aprobadas y una omisión agregada. Imprime además 16 pruebas optativas que se solapan. Ninguna omisión cuenta como aprobada. El primer intento falló por tres referencias antiguas del código actual; se corrigieron y se repitió la compuerta completa. Ambos resultados se conservan. Falta el Full final sobre el candidato de cierre.

| Avance formal | Estado |
|---|---|
| Encuesta | 28/742 cubiertos;714 abiertos;0 no aplicables. |
| MatrizC03 | 3/11 cumplidas;5 contradichas;3 pendientes. |
| Categorías nuevas cerradas | 0;total completo no definido. |
| Apertura de aplicaciones | 75 casos preparados, sin ejecutar. |

Estos recuentos no son un porcentaje de cierre. Faltan las conductas restantes, las ocho rutas, cien turnos de aceptación, recuperación, interfaz real, voz y validación final. No hay un plazo fiable de cierre.

BAXY permanece cerrado para uso manual. Encuesta 742/revisión 1248 y cambios del dueño conservados. Última publicación verificada:df941680 en Goal-c03; main 5f572ee1 intacto. Resultados 822 y corrección 823 listos para publicar.
