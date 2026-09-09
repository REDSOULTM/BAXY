# C03 — resultados observados y bienvenida atrasada

Panel astra-qwen2507-routes (18 heredados): máximo 13/18 útiles, 16 publicados.
3499.56 MiB, 131.39s; archivo propio intacto y retirado. Ver ADJUDICACION.md.
Causas: consulta narrada como cambio, recorte que oculta el borrador, pregunta
clarificadora rechazada, explicación mixed agotada, eliminación desviada a move.
No se usa el acuse cancelar para acreditar una confirmación que nunca ocurrió.

Se retiran time_clip y clock_only_clip: un borrador inválido debe recomponerse.
La instrucción de status deja de ordenar state change y pide resultados verificados.
Dos pruebas antes rojas, después 218 pass/101 subtests (C03, voz, planner); Ruff verde.
Contraste astra-qwen2507-read-results: máximo 6/8, 3497.56 MiB, 79.28s.
Consulta ES ya no inventa modificación; hora mixed conserva prosa. Fallo nuevo:
bienvenida t0, iniciada antes de la primera petición, publica después del resultado.
La cola sólo consulta isStale ANTES de esperar; la publicación directa tampoco
revalida el turno después de inferencia. Reparación acotada en curso.

Lingua 2.2.0 sólo en scratchpad: 13/16 segmentaciones, falla mezclas breves;
no se incorpora al producto. La investigación de R82 rechazaba retirar el detector
de entrada; aquí se buscaba sustituir sólo el guard lexical de salida, sin éxito.
No añadir otra lista de palabras ni repetir el panel de seis sobre cifrado.
Full sigue reservado al cierre; no aceptación 100 ni promoción de modelo.
