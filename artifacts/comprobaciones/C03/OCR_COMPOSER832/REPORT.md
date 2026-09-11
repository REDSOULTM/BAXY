# OCR832 — composición sobre tabla sintética

Raíz: **6 válidos / 2 fallidos**. Sesión80419 recogida exit0(f7243c): ocho respuestas completas, sin reintentos, vetos, cortes ni violación de recursos. Exit0 acredita ejecución, no calidad perfecta.

32,25s; VRAM pico 3495.56MiB; RAM residente pico 755.20MiB, medidores heredados por árbol de procesos. Techo conjunto4GBVRAM. Fuente/panel/imagen/modelo/perfil intactos.

El payload físico conserva geometría y huella de imagen en8/8. Las dos falsedades ya llegan del modelo y BAXY las publica sin modificación. No se observa pérdida de filas, por lo que añadir un parser no está justificado por este panel. El control836 aislará el framing de BAXY sin cambiar casos ni datos.

## OCR832-D01 — válido

**Pedido:** En esta tabla, ¿qué aplicación tiene el valor más alto en Memoria y cuánto indica?

**Respuesta literal:**

> La aplicación con el mayor uso de memoria es Orilla, con 980,2 MB.

**Juicio raíz:** Identifica Orilla y980,2MB. El pedido fija el alcance de esta tabla; la respuesta no añade una afirmación global.

## OCR832-D02 — válido

**Pedido:** ¿Cuál de las tres filas muestra menos memoria y qué valor tiene?

**Respuesta literal:**

> La tercera fila muestra menos memoria y tiene el valor de 105,0 MB.

**Juicio raíz:** La tercera fila identifica inequívocamente Río en la imagen y devuelve105,0MB. No se exige repetir el nombre si la referencia de fila responde al pedido.

## OCR832-D03 — válido

**Pedido:** ¿Esta observación demuestra cuál es la aplicación que más memoria usa en todo mi PC?

**Respuesta literal:**

> No, esta observación no demuestra cuál es la aplicación que más memoria usa en todo el PC. Solo muestra el consumo de memoria de tres aplicaciones: Cosmos (420,5 MB), Orilla (980,2 MB) y Río (105,0 MB). Orilla usa más memoria que las otras, pero no se puede afirmar que sea la que más consume en todo el sistema, ya que no se incluyen otros procesos o aplicaciones.

**Juicio raíz:** Niega máximo global y limita evidencia a tres aplicaciones; cifras y máximo local correctos. No exige inventario completo.

## OCR832-D04 — fallido

**Pedido:** Junto a Orilla aparece un número entre paréntesis: ¿cuál es y permite saber los PID de sus integrantes?

**Respuesta literal:**

> El número entre paréntesis que aparece junto a "Orilla" es 7. Este número indica que el proceso Orilla tiene un PID de 7.

**Juicio raíz:** Inventa que7 es un PID. La imagen sólo muestra Orilla(7) sin columna PID ni miembros identificados.

## OCR832-D05 — válido

**Pedido:** List the three applications from highest to lowest in the Memoria column, including each displayed value.

**Respuesta literal:**

> 1. Orilla - 980.2 MB  
> 2. Cosmos - 420.5 MB  
> 3. Río - 105.0 MB

**Juicio raíz:** Orden descendente Orilla980,2/Cosmos420,5/Río105,0MB correcto, en inglés.

## OCR832-D06 — válido

**Pedido:** Read the Memoria column from top to bottom as displayed, pairing each value with its application name. Keep the displayed row order.

**Respuesta literal:**

> Cosmos: 420.5 MB  
> Orilla: 980.2 MB  
> Río: 105.0 MB

**Juicio raíz:** Orden visual Cosmos420,5/Orilla980,2/Río105,0MB y asociaciones correctas.

## OCR832-D07 — fallido

**Pedido:** Are any of the three applications tied in the displayed memory values? Show the values you used.

**Respuesta literal:**

> Yes, Cosmos and Orilla are tied in the displayed memory values. The values used are: Cosmos — 420.5 MB, Orilla — 980.2 MB, Río — 105.0 MB.

**Juicio raíz:** Afirma empate Cosmos-Orilla aunque sus propios valores420,5 y980,2MB son distintos.

## OCR832-D08 — válido

**Pedido:** Compare Cosmos y Río por memoria y dime en español si también puedes comparar su CPU con esta tabla.

**Respuesta literal:**

> Cosmos tiene 420,5 MB de memoria, Río tiene 105,0 MB, por lo que Cosmos consume más memoria que Río. Orilla tiene 980,2 MB, lo que indica que usa más memoria que ambos. No tengo información sobre la CPU para compararla con una tabla.

**Juicio raíz:** Compara Cosmos420,5>Río105,0MB en español y reconoce ausencia de CPU. La mención adicional de Orilla es correcta y no sustituye la comparación pedida.

Encuesta36cubiertos/706abiertos/0NA; matriz3/11. Sin crédito nuevo deH0675, aceptación, UI, voz ni generalización entre imágenes. C03 EN_CURSO.
