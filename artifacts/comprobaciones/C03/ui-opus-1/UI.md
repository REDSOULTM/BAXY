# C03 — producto arrancado con `py main.py` (2026-09-05)

## Lo que sí está acreditado

`py main.py --conductor --profile … --capture … --turns-file …` arranca el
producto por la entrada de desarrollo documentada, envía entradas y publica
respuestas. Captura en `events.jsonl` de esta carpeta, `meta.pid = 19952`,
proceso `Baxy.exe` lanzado por `main.py`.

| # | Entrada | Respuesta publicada | Estado siguiente |
|---|---|---|---|
| 1 | hola | `Hola!` | BAXY disponible, entrada habilitada, 3 mensajes |
| 2 | ¿Qué hora es? | `La hora actual es 13:36.` | disponible, 5 mensajes |
| 3 | qué puedes hacer en este PC | capacidades del catálogo | disponible, 7 mensajes |
| — | `session.new` | — | la conversación vuelve a empezar |
| 4 | What time is it? | `At 13:36, it is thirteen thirty-six minutes past the hour.` | disponible, 3 mensajes |
| 5 | don't open Paint | `I will not open Paint.` | disponible, 5 mensajes |

Se observa respuesta, estado y turno siguiente, y la sesión nueva reinicia el
recuento de mensajes. Dos defectos de prosa quedan a la vista y están anotados:
la respuesta 3 usó la segunda persona («Puedes abrir…») y la 4 dijo mal la hora.
La segunda persona ya se veta como `wrong_actor` después de esta captura.

## Lo que NO está acreditado

La **ventana** se arrancó con `py main.py` (sin argumentos): proceso `Baxy`
(PID 58304), título `BAXY`, `Responding = True`, con `llama-server` vivo, es
decir la mente cargada. Pero **no pude enviar una entrada por la ventana**:

- `AppActivate` + `SendKeys` no llegó al cuadro de entrada (ni el proceso ni
  `llama-server` acumularon trabajo después de enviar las teclas).
- La automatización de interfaz (`System.Windows.Automation`) sólo expone tres
  paneles —`BAXY Field, interfaz local`, `field · gemma4` y su contenido web—:
  la conversación vive dentro de WebView2 y no está en el árbol de
  accesibilidad, así que tampoco pude leer lo publicado en la ventana.

Por tanto **el criterio de UI del goal C03 sigue incumplido**: el conductor por
`py main.py` demuestra la tubería pública completa, pero no demuestra que el
usuario vea y entienda la respuesta en la ventana. Esta carpeta sustituye a
`tramo-c-ui-4.txt`, que sólo recogía el título de la ventana; aquí al menos hay
entradas, respuestas y estado, y se dice con precisión lo que falta.

Reanudación: hace falta una vía de entrada y lectura sobre la ventana —el
puente de `Baxy.FieldUi` expuesto para pruebas, o accesibilidad habilitada en
WebView2— antes de poder cerrar este criterio.
