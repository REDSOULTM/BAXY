# Estado de C03

C03 sigue abierto. El relevo está publicado y la ampliación de salida de las listas de procesos tiene sus pruebas verdes. `main` permanece intacto.

| Qué cambió | Resultado comprobado |
|---|---|
| Se preservó el trabajo anterior y se registró este relevo | Publicado en `Goal-c03`; última validación publicada: `b4fdfdf4`. |
| Las listas densas pueden usar el doble de espacio de respuesta | 30 pruebas focalizadas y 3277 de regresión aprobadas; 1 omisión ambiental de STT y 121 subpruebas aprobadas. Fast pasó. Falta demostrar la mejora en el panel completo. |
| Se corrigió un recibo de cobertura desactualizado | Ya refleja los 28 casos acreditados anteriormente; no son dos mejoras nuevas de este relevo. |

| Qué se midió | Qué ocurrió |
|---|---|
| La misma tanda de 50 consultas sobre procesos | Se interrumpió por falta de RAM tras nueve respuestas completas: tres válidas y seis fallidas. Se conserva el décimo turno interrumpido. |
| Pico de VRAM de BAXY durante esta tanda | 3497,56 MiB (3,42 GiB), por debajo del techo de 4 GiB. |
| Pico de RAM residente de BAXY durante esta tanda | 2350,11 MiB (2,30 GiB), separado de la VRAM. La memoria libre del sistema cayó a 662,12 MiB. |

La medición usa el producto sin ventana ni voz; todavía no certifica el consumo de todo BAXY junto. El espacio mayor de respuesta conserva el modelo elegido y su configuración.

| Qué falló | Qué falta |
|---|---|
| Varias instancias aparecen reducidas a un solo nombre | Reparar la conservación de las identidades y comprobar listas completas. La propuesta se prepara en un worktree aislado. |
| Algunas listas muestran menos procesos de los que deberían | Comprobar todas las filas solicitadas, incluidos nombres repetidos. |
| La memoria de un proceso se presenta como la de toda una aplicación | Completar la agrupación verificable de aplicaciones antes de afirmar cuál consume más. |
| No hubo RAM libre suficiente para terminar la tanda | Reanudar los 41 casos restantes con los mismos criterios cuando haya margen, conservando lo ya medido. |
| C03 tiene más conductas pendientes | Después siguen aplicaciones, demás requisitos, las ocho rutas de respuesta, aceptación de cien, errores y recuperación, interfaz real, voz y Full final. |

Avance formal: **encuesta 28/742 cubiertos; filas C03 3/11 cumplidas, 5 contradichas y 3 pendientes**. No hay una partición formal completa de categorías en el registro: **0 categorías nuevas cerradas en este relevo; total de categorías todavía no acreditado**. Método: contar los estados y las adjudicaciones existentes, sin convertir resultados parciales en porcentaje del goal. Estimación de cierre: todavía no hay un plazo fiable; depende de completar las categorías y la aceptación, no del número de pruebas técnicas.

No queda BAXY abierto para uso manual. La encuesta original y sus 742 respuestas se conservan intactas.
