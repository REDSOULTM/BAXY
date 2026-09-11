# Estado de C03 — 11 de septiembre de 2026

**C03 sigue abierto.** La tanda 811 consiguió **40 respuestas válidas de 50**, frente a 37 en 809. Recuperó diez casos y perdió siete. El candidato 810 sigue sin adoptar por esas siete regresiones; la encuesta no obtiene cobertura nueva.

Se cambió la forma de entregar la identidad de cada proceso al narrador: ahora nombre e identificador van juntos. Las filas que aparecen en las respuestas conservan sus identificadores. Las listas pasan de 9/11 a 11/11 y memoria de 3/11 a 8/11. Sin embargo, algunas respuestas todavía confunden cuántos procesos se observaron con cuántos se incluyen en la respuesta.

| Qué se midió | Resultado de 811 |
|---|---|
| Listas | 11/11 válidas. |
| Conteos | 12/12 válidas. |
| Memoria | 8/11 válidas. |
| CPU | 9/11 válidas. |
| Recurso no especificado | 0/4 válidas. |
| Memoria de aplicaciones | 0/1 válida. |
| Total | 40/50 válidas; 10 fallidas. |

| Tiempo y recursos | Resultado |
|---|---:|
| Duración de las 50 consultas consecutivas | 253,406 segundos |
| Espera mediana por respuesta | 4,512 segundos |
| Percentil 95 de espera | 7,133 segundos |
| Máximo de espera | 7,278 segundos |
| Pico de VRAM | 3.499,55859375 MiB |
| Pico de RAM residente | 2.455,98828125 MiB, inferior a 4.096 MiB |

La espera mide eventos registrados de cada turno completado, no voz. La VRAM queda bajo el techo de 4.096 MiB; RAM y VRAM se miden por separado. Hubo telemetría de GPU y cero infracciones en el árbol de procesos medido. La ejecución terminó con código 0 y mantuvo intactos sus componentes. Aún no acredita interfaz visible, voz ni el ciclo completo de BAXY funcionando junto.

| Qué falló | Qué falta resolver |
|---|---|
| Tres respuestas confunden la cantidad observada con el recorte. | Mantener los 139 observados aunque se devuelvan uno, dos o tres. |
| Seis respuestas dicen que muestran diez procesos pero enseñan uno o cuatro. | Hacer coincidir lo que se afirma con las filas que realmente aparecen. |
| Una respuesta atribuye la memoria de un proceso a toda una aplicación. | Verificar qué procesos pertenecen a la aplicación y su consumo agregado. |

En un ranking de CPU sin cantidad solicitada, presentar menos filas puede ser válido si el recorte es explícito. H0364 mostró correctamente dos máximos de CPU de 145 procesos observados y declaró esos dos; no tenía una obligación de mostrar diez. El problema pendiente es afirmar cantidades que no coinciden con lo observado o mostrado.

| Validación disponible | Resultado y límite |
|---|---|
| Siete suites del candidato 810 | 247 aprobadas, cero omisiones, 3,04 segundos. |
| Controles Fast 810 | Salida 0; compilación Release en 22,18 segundos, cero advertencias y errores; 30 archivos comprobados sin cambios. |
| Full 804, base anterior | Python: 12.714 aprobadas, 3 omisiones y 466 subpruebas. .NET: 4.642 aprobadas y 1 omisión agregada. Las 16 omisiones optativas impresas se solapan y no se suman. |

No hay Full 810 acreditada. Ninguna omisión cuenta como aprobada. Faltan la validación Full acumulada para adoptar y la Full final de cierre.

El candidato siguiente, 812, ya pasó sus controles de integración: unir cada cantidad con el grupo de procesos al que corresponde en los datos que recibe el narrador. La raíz integró siete líneas en la proyección existente, sin cambiar instrucciones ni el verificador.306pruebas aprobadas, cero omisiones, en3,34segundos; Fast correcto con compilación22,94segundos y cero advertencias/errores. Falta medir sus respuestas en las mismas50consultas; no se adopta todavía.

| Avance formal | Estado |
|---|---|
| Encuesta | 28/742 cubiertos; 714 abiertos; 0 no aplicables. |
| Matriz C03 | 3/11 cumplidas; 5 contradichas; 3 pendientes. |
| Categorías nuevas cerradas | 0; total completo no definido. |
| Ocho rutas de respuesta | Pendientes. |
| Apertura de aplicaciones | 75 casos preparados, sin ejecutar. |

Estos recuentos no son un porcentaje de cierre de C03. Siguen pendientes las demás conductas, cien turnos de aceptación, errores y recuperación, interfaz real, voz y validación final. No hay plazo fiable de cierre.

BAXY permanece cerrado para uso manual. Encuesta 742/revisión 1248 intacta; los cambios del dueño se conservan. Última publicación verificada: f4480bf2 en Goal-c03; main permanece en 5f572ee1.
