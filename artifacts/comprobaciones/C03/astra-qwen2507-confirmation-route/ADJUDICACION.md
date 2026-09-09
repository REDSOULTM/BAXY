# Desarrollo: confirmación de cerrar Calculadora

131.44 s; 3497.56 MiB GPU; 5330.32 MiB RAM; registro intacto.
6/8 publicados, sin confirmación acreditada. No se confirmó ningún cierre.

| Turno | Adjudicación |
|---|---|
| 1 abrir Calculadora | Error visible mente no disponible. No apertura acreditada; no pass de la operación. |
| 2 cerrar Calculadora ES | Plan app.close, pero falla antes de confirmar; composición agotada. |
| 3 cancelar | Acuse «se cancela» no demuestra cancelar una confirmación: nunca se ofreció. |
| 4 hora ES | Útil y fiel. |
| 5 cerrar Calculator EN | Plan app.close, pero falla antes de confirmar; composición agotada. |
| 6 cancel | Pregunta en español, pese a turno inglés, y «calculador»: falla. |
| 7 hora/audio EN | Útil y fiel. |
| 8 no Paint | Fiel, con frase introductoria innecesaria. |

El journal del perfil sólo acredita lecturas; no aparecen respuestas app.*.
El selector sí produce app.close. La causa exacta del fallo posterior aún no se
conservaba: MindPlanSession descartaba response.Message al terminar un paso y
lo reemplazaba por step_failed. MissionNarration además guardaba JSON de razón
como string. Reparación del transporte de causa en curso; no atribuir este
resultado al fallo histórico arguments-06 sin la respuesta concreta.

Corrección del diagnóstico: buscando también el predecesor, el journal acredita
window.resolve -> window_not_found. No hubo app.close ni confirmación exacta.
