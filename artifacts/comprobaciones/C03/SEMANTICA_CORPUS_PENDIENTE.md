# Corpus pendiente para la Fase 3.5 (semántica unificada, Fable 5.1)

Regla del dueño (2026-09-21): un fallo de **lectura** visto en una tanda no se parcha con otro regex; se anota aquí
y la fila queda abierta hasta que la capa semántica unificada lo cubra (prompt:
`PROMPT_FABLE_SEMANTICA_2026-09-23.md`). Un fallo de adaptador o de fixture NO va aquí: se arregla y se re-mide.

Formato de cada entrada (una por línea de tabla; sin datos privados del dueño, sólo la forma del pedido):

| Tanda / caso | Forma del pedido (literal o variante) | Qué hizo BAXY | Qué debía hacer | Fila(s) |
|---|---|---|---|---|

## Ya conocidos al traspaso (2026-09-21)

| Origen | Forma del pedido | Qué hizo BAXY | Qué debía hacer | Fila(s) |
|---|---|---|---|---|
| Auditoría semántica 2026-09-20 | «mandale/decile … a <persona>» con un solo destinatario resoluble | preguntó el cliente | resolver el canal y enviar; preguntar sólo con ambigüedad real (D24) | H0019, H0024, H0045, H0074, H0198, H0231, H0408, H0536 |
| Auditoría semántica 2026-09-20 | «abre Steel.» / «abres team» (nombre mal oído, un solo candidato instalado) | preguntó o no abrió | app.open de Steam (regla 2026-09-19: lo mal dicho lo arregla BAXY) | H0227, H0398, H0521 |
| Auditoría semántica 2026-09-20 | «cambiá a la otra ventana» | preguntó | window.resolve de las visibles y activar la de atrás | H0263 |
| Auditoría semántica 2026-09-20 | «quiero que lo veas y de qué se trata» («lo» = la pantalla) | preguntó el antecedente | capture.screenshot + ocr.read | H0528 |
| Auditoría semántica 2026-09-20 | «abrí Marvel…» (el único juego instalado parecido) | preguntó | lanzar el único candidato | H0682 |

## Añadidos por las tandas del notebook

(la sesión del notebook añade filas aquí)
