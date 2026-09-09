# C03 — pares literales de la regresión de reloj49

Panel técnico consumido, siete entradas idénticas a compound-shell48. No reserva humana ni acreditación de UI/audio físico. **4/7 turnos completos útiles; 6/7 respuestas finales fieles publicadas.** Los hechos y auditorías completos están en astra-clock49/paired.json.

## t1 — Falla

**Entrada:** Dime la hora, revisa el estado del audio y dime el uso de CPU.

**Progreso publicado:**

> La hora es 14:30, el audio está en curso y el uso de CPU es del 45%.

**Respuesta final:**

> La hora local es 00:27. El volumen de los altavoces (Realtek(R) Audio) está en 100 y no está silenciado. El uso actual de la CPU es del 14,375%.

Respuesta final fiel; el progreso publicado inventa 14:30 y CPU45%, sin observaciones.

## t2 — Falla

**Entrada:** Dime la hora y el estado del audio.

**Progreso publicado:**

> La hora no está disponible, pero el audio está en progreso.

**Respuesta final:**

> La hora local es 00:27. El estado del audio muestra que los altavoces (Realtek(R) Audio) están activos y con el volumen en 100. No está silenciado.

Respuesta final fiel; el progreso declara que la hora no está disponible, aunque la lectura se completa.

## t3 — Cumple

**Entrada:** Tell me the time and the volume.

**Progreso publicado:**

> Still working.

**Respuesta final:**

> The time is 00:27 on the local clock. The volume is at 100, and sound is not muted.

Progreso de trabajo en curso y respuesta inglesa con hora/volumen verificados.

## t4 — Cumple

**Entrada:** What time is it y cómo está el audio?

**Progreso publicado:**

> No sé la hora ni el estado del audio, sigue en progreso.

**Respuesta final:**

> Son las 00:27. El audio está activo en los Altavoces (Realtek(R) Audio) y el volumen está en 100.

Antes de medir declara que aún no sabe la hora/audio y que sigue en progreso; luego responde con hechos verificados.

## t5 — Cumple

**Entrada:** Dime la hora y no silencies el audio.

**Progreso publicado:**

Sin etiqueta de progreso.

**Respuesta final:**

> 00:27

Hora verificada; conserva la prohibición independiente, sin silenciar.

## t6 — Falla

**Entrada:** Dime la hora y revisa la CPU

**Progreso publicado:**

> Sigo, la CPU está en proceso.

**Respuesta final:**

> composition_failed

Hechos y borrador fieles; la app rechaza «No hay fallos reportados» con reversed_result y agota reintentos.

Borrador fiel rechazado por la app, no publicado:

> La hora es 00:27. La CPU tiene un uso del 17,36 %, 16 procesadores lógicos y modelo AMD Ryzen 7 5800H con Radeon Graphics. No hay fallos reportados.

## t7 — Cumple

**Entrada:** ¿Cómo está el audio?

**Progreso publicado:**

Sin etiqueta de progreso.

**Respuesta final:**

> El audio está activo y el volumen está en 100.

Lectura fiel de audio; recupera después del fallo de composición anterior.
