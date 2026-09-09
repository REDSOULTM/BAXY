# Desarrollo: título citado y publicación del cierre

Sesión7000 terminó0,41,11s,GPU3497,56MiB,RAM3983,28MiB;registro intacto.
6/6publicados, hechos y continuidad correctos. **Naturalidad pendiente** en t2/t4:
prosa extensa/técnica; esto no acredita el panel C03 entero ni los100frescos.

| Turno | Hechos y utilidad | Observación |
|---|---|---|
| t1 | Correctos | Confirma cierre del título exacto, ofrece confirmar/cancelar. |
| t2 | Correctos | Cancelación sin cierre, explica demasiado el readback/maximización anterior. |
| t3 | Correctos | Vuelve a resolver y pide confirmar el cierre. |
| t4 | Correctos; prosa mejorable | Cierre verificado y respuesta publicada. «fue resuelta…el proceso se completó» narra implementación, no sólo lo que pidió la persona. |
| t5 | Correctos | It's 11:44 conserva hora real. |
| t6 | Correctos | task.list vacío verificado, respuesta EN fiel. |

Fixture propia PID8992,cerrada por BAXY tras confirmar. No limpieza externa.
La corrección del detector de repetición conserva delimitadores entre palabras;
no añade excepciones por título/aplicación y sigue rechazando repeticiones reales.
Pruebas previas:2/3 rechazaban nombres citados;después38/38 dueñas pasan.

Siguiente causa de prosa: CreateCompletionMessage recibía sólo resultados y el
mensaje actual era confirmar; se perdía el objetivo original ya conservado por
confirmaciones y cancelación. Transportar completedRequest conserva la intención
sin eliminar evidencia de pasos ni exigir una frase de salida.
