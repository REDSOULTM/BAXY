# Nombre de archivo conservado — desarrollo, 2026-09-06

**1/3 respuestas correctas, 3/3 publicadas.** Se reparó el falso positivo de
proyección: el pedido y el nombre del archivo llegan íntegros al diálogo y al
compositor. La confirmación y cancelación todavía no funcionan en este recorrido.
Runtime Granite registrado, fuente/binario en PREREGISTRO.json; proceso exit 0.

| # | Respuesta | Veredicto |
|---|---|---|
| 1 | No puedo borrar el archivo C03-Prueba-Respuesta-20260906.txt porque la solicitud es ambigua. | Falla: nombre y carpeta concretos; no hubo confirmación exacta. |
| 2 | No puedo procesar la solicitud por falta de claridad. | Falla: cancelar era claro, no explica honestamente el estado. |
| 3 | The capital of Peru is Lima. | Pasa; disponible sin misión pendiente. |

El fixture quedó intacto; FIXTURE-POST.json verifica la huella y registra la
limpieza posterior del único archivo propio por el agente. Ningún efecto de
BAXY ni cancelación semánticamente correcta se deducen de esa limpieza.

La reparación de proyección tiene contraste 3 fail/4 pass antes y 1784 pass/0
skips de los dos owners después. Se reutiliza FilesystemOrDocumentPattern del
owner para sus extensiones; prefijos conocidos, etiquetas de secretos y JWT
siguen protegidos. No se eliminó el detector genérico de credenciales.

## Siguiente causa, todavía no resuelta

shell-trace.jsonl: decision.start en 23835 ms, mind.request.failed/request_timeout
en 26767 ms y decision.ready/unavailable en 26950 ms. Ese registro de timeout
no incluye el identificador de la operación: comprobar su relación exacta antes
de atribuir el plazo de unos tres segundos a turn.decide (su constante es 22 s).
No se generó turn-audit.jsonl. La composición recibe
`failure/ambiguous_request`, que convierte indisponibilidad en culpa del pedido.

MainWindowViewModel.TryExecuteWithMindAsync retorna false al no recibir decisión;
el fallback de ExecuteMissionInputAsync alrededor de línea 799 produce esa causa.
La siguiente reparación debe conservar la causa real de fallo y recuperar la
decisión, sin añadir otro filtro de frases ni atribuir este caso sólo al modelo.
No aceptación fresca, Full ni cierre de C03.
