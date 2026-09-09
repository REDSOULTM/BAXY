# Reformulación de aclaración — primer contraste real

76.26 s, 3497.56 MiB GPU, 4796.38 MiB RAM; registro intacto.

| Turno | Veredicto |
|---|---|
| 1 cierra aquello | composition_failed. El modelo eligió unsupported de entrada; no ejercitó la reformulación de una decisión clarify. |
| 2 cancelar | Responde fuera de catálogo, sin aclaración pendiente válida: falla utilidad. Propuesta wifi.disconnect retirada antes de ejecutar. |
| 3 hora ES | Correcta. |
| 4 close that | Aclaración en español: idioma incorrecto. La ruta domain_confirmation omitía el helper de estilo/idioma. |
| 5 cancel that | Cancelación honesta de aclaración pendiente, en inglés. |
| 6 cálculo EN | Correcto: 84. |

3/6 útiles, 5 publicaciones. No confundir esta población con astra-routes-development:
allí cierra aquello era t6 tras cinco turnos y produjo clarify con dos preguntas;
aquí es el primero y produjo unsupported. La reformulación no quedó probada en
este contraste; las pruebas unitarias conservan el defecto original.
Hallazgo: read_request ya marca cierra aquello/close that como ambiguous_action,
pero el guard de referente sólo usaba su regex paralelo con abrir/hacer. Se hereda
la lectura común, acotando las marcas a pedidos enteros para no confundir «Do that
after opening Steam». La confirmación de dominio hereda el helper de preguntas.
