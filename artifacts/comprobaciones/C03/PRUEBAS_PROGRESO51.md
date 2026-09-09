# C03 — progreso51: entradas y respuestas literales

Mismos siete controles técnicos de49, no reserva humana ni UI/audio físico. **6/7 turnos completos útiles**, incluyendo progreso. Las observaciones y auditorías están en astra-progress51/paired.json.

## t1 — Cumple

**Entrada:** Dime la hora, revisa el estado del audio y dime el uso de CPU.

**Progreso:**

> Estoy revisando el estado del audio y el uso de CPU, pero aún no tengo los datos completos. El proceso sigue en curso.

**Respuesta final:**

> La hora local es 00:44. El volumen de los altavoces (Realtek(R) Audio) está en 100 y no está silenciado. El uso actual de la CPU es del 5,77%.

## t2 — Cumple

**Entrada:** Dime la hora y el estado del audio.

**Progreso:**

> Estoy trabajando en el audio, aún no tengo la hora exacta ni el estado definitivo.

**Respuesta final:**

> La hora local es 00:44. El estado del audio muestra que los altavoces (Realtek(R) Audio) están activos y con el volumen en 100. No está silenciado.

## t3 — Cumple

**Entrada:** Tell me the time and the volume.

**Progreso:**

> I'm still working on getting the time and volume for you.

**Respuesta final:**

> The time is 00:44. Volume is at 100%. Sound is not muted.

## t4 — Cumple

**Entrada:** What time is it y cómo está el audio?

**Progreso:**

> Estoy revisando el estado del audio y aún no tengo la hora exacta.

**Respuesta final:**

> Son las 00:44. El audio está activo en los Altavoces (Realtek(R) Audio) y el volumen está en 100.

## t5 — Cumple

**Entrada:** Dime la hora y no silencies el audio.

**Progreso:**

Sin etiqueta de progreso.

**Respuesta final:**

> 00:44

## t6 — Falla

**Entrada:** Dime la hora y revisa la CPU

**Progreso:**

> Estoy revisando la CPU, pero aún no tengo la hora. El trabajo sigue en progreso.

**Respuesta final:**

> composition_failed

La app rechaza este borrador fiel por «fallos» pese a estar negado; no se publicó:

> La hora es 00:44. La CPU tiene un uso del 20%, 16 procesadores lógicos y modelo AMD Ryzen 7 5800H con Radeon Graphics. No hay fallos reportados.

## t7 — Cumple

**Entrada:** ¿Cómo está el audio?

**Progreso:**

Sin etiqueta de progreso.

**Respuesta final:**

> El audio está activo y el volumen está en 100.

El progreso de t4 necesitó tres intentos: los dos primeros eran declaraciones honestas de desconocimiento seguidas de trabajo en curso, rechazadas por el control que exige la señal de progreso en la primera frase. El tercero fue útil y se publicó. No afirmar que todos los avisos pasan a la primera.
