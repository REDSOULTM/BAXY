# Lecturas fieles y reloj sin recorte — desarrollo

79.28 s, 3497.56 MiB VRAM, 4526.49 MiB RAM. Registro intacto.

| Turno | Veredicto |
|---|---|
| 1 hora ES al arrancar | Hora correcta tras reintento, seguida de bienvenida t0 atrasada. Falla publicación: el saludo queda como terminal. |
| 2 hora/audio ES | Datos fieles, sin afirmar que modificó audio. «muteado» es comprensible, estilo mejorable. |
| 3 hora EN | Correcta. |
| 4 hora/audio EN | Datos fieles, estilo telegráfico. |
| 5 hora mixed | «Son 06:36, six thirty-six.» conserva hora y ES/EN; pequeño eco numérico natural. |
| 6 hora/audio mixed | Falla: todos los intentos sólo ES, termina composition_failed. |
| 7 saludo EN | Correcto. |
| 8 no abras Paint | Correcto, no ejecuta apertura. |

Máximo 6/8 útiles; no panel verde. El cambio de lecturas retira el éxito inventado
del panel previo. El recorte eliminado deja al modelo redactar/reintentar el dato.
T1 no perdió el dato en inferencia: events.jsonl muestra result seguido de welcome;
audit identifica bienvenida t0 y resultado t1. Revisar vigencia después de esperas.
