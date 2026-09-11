# Estado de C03

C03 sigue abierto. Se completaron las 50 consultas de procesos:28 respuestas válidas y22 fallidas. El plazo de redacción corta varias listas largas; se está validando su corrección en el límite existente. `main` permanece intacto.

| Qué cambió | Resultado comprobado |
|---|---|
| Se preservó el trabajo anterior y se registró este relevo | Publicado en `Goal-c03`; última validación publicada: `b4fdfdf4`. |
| Las listas densas pueden usar el doble de espacio de respuesta | 30 pruebas focalizadas y3277 de regresión aprobadas;1 omisión ambiental de STT y121 subpruebas. Fast pasó, pero el panel real demuestra que ese cambio solo no basta. |
| Se ajusta el plazo de las listas densas de procesos | Reutiliza el límite ya existente para ventanas. Pruebas de la corrección en curso; falta confirmar la mejora real. |
| Se corrigió un recibo de cobertura desactualizado | Ya refleja los 28 casos acreditados anteriormente; no son dos mejoras nuevas de este relevo. |

| Qué se midió | Qué ocurrió |
|---|---|
| La misma tanda de50 consultas sobre procesos | Completa en segmentos9+41:28 válidas y22 fallidas. Frente a la anterior:2 recuperadas y9 perdidas. Se conserva el intento interrumpido por RAM. |
| Consultas sobre cuántos procesos hay |12/12 correctas, con el límite de lo que pudo observar. Todavía no se acredita nueva cobertura porque el candidato sigue sin adoptar.|
| Pico de VRAM de BAXY durante esta tanda |3497,56MiB (3,67GB), por debajo del techo de4GB.|
| Pico de RAM residente de BAXY durante esta tanda |2436,58MiB (2,55GB), separado de la VRAM. La primera parte se detuvo al quedar662,12MiB libres; la continuación terminó sin violar las guardas.|

La medición usa el producto sin ventana ni voz; todavía no certifica el consumo de todo BAXY junto. El espacio mayor de respuesta conserva el modelo elegido y su configuración.

| Qué falló | Qué falta |
|---|---|
| Varias instancias aparecen reducidas a un solo nombre | Comprobar listas completas después de corregir el plazo. El verificador propuesto queda fuera mientras rechace formatos válidos. |
| Algunas listas muestran menos procesos de los que deberían | Comprobar todas las filas solicitadas, incluidos nombres repetidos. |
| La memoria de un proceso se presenta como la de toda una aplicación | Completar la agrupación verificable de aplicaciones antes de afirmar cuál consume más. |
| Varias listas terminan sin respuesta | Validar que el plazo de redacción permita completar los datos ya obtenidos; no añadir otra capa de filtros. |
| C03 tiene más conductas pendientes | Después siguen aplicaciones, demás requisitos, las ocho rutas de respuesta, aceptación de cien, errores y recuperación, interfaz real, voz y Full final. |

Avance formal: **encuesta 28/742 cubiertos; filas C03 3/11 cumplidas, 5 contradichas y 3 pendientes**. No hay una partición formal completa de categorías en el registro: **0 categorías nuevas cerradas en este relevo; total de categorías todavía no acreditado**. Método: contar los estados y las adjudicaciones existentes, sin convertir resultados parciales en porcentaje del goal. Estimación de cierre: todavía no hay un plazo fiable; depende de completar las categorías y la aceptación, no del número de pruebas técnicas.

No queda BAXY abierto para uso manual. La encuesta original y sus 742 respuestas se conservan intactas.
