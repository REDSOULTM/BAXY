# C03 — UI real: `py main.py`, entradas tecleadas y respuesta leída

Corrida `ui-opus-2/` (2026-09-05). `py main.py --ui-probe … --ui-capture …`
arranca la **ventana** y `FieldUiProbe` escribe cada turno en el mismo
`input[aria-label="message input"]` que usa una persona, envía el mismo
formulario y lee las filas que la ventana muestra (`.activity-scroll .act`).
No hay vía nueva al producto: es el compositor real y el DOM real.

`meta.pid = 50484`, proceso `Baxy.exe` lanzado por `main.py`.

| Turno tecleado | Lo que muestra la ventana |
|---|---|
| (arranque) | `Hola.` |
| hola | `Hola` |
| ¿Qué hora es? | `A las 15:27.` |
| qué puedes hacer en este PC | `Puedo ayudarte a abrir y cerrar programas, mover y enfocar ventanas, leer y ajustar el audio, leer la hora y el estado del equipo…` |
| What time is it? | `The time is 15:28.` |
| don't open Paint | `I will not open Paint.` |
| ¿por qué importa la hora? | `La hora importa porque ayuda a coordinar tareas, eventos y sincronizar actividades en tiempo real…` |

Siete de siete útiles y fieles, con el turno siguiente siempre disponible: el
`input` vuelve a estar habilitado antes de cada envío (la sonda espera a que lo
esté). Título de ventana `BAXY`, sin errores de arranque.

## Lo que esta corrida encontró y se reparó

La primera pasada (misma sonda, antes de las reparaciones) publicó en el
arranque: «Claro, por favor proporciona la frase que deseas que contenga la
situación.greeting, y la redacto en español…», y agotó la composición de «qué
puedes hacer en este PC». Dos causas, las dos reparadas:

- La bienvenida de arranque no tiene pedido del que leer un saludo, así que el
  payload no traía `greeting` mientras el prompt lo nombraba. Ahora un turno de
  bienvenida lleva su saludo por su propio `kind`.
- Nombrar un campo del contrato (`situación.greeting`) no se vetaba. Ahora es
  `internal_code`, sin confundir un punto final tras «situación».

Sin la sonda, ninguno de los dos se habría visto: el conductor sin ventana no
publica la bienvenida de arranque de la misma forma. Sustituye a
`tramo-c-ui-4.txt` (sólo título) y a `ui-opus-1` (sólo conductor).
