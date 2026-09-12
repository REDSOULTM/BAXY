# AGENDA1097 — adjudicación de la raíz

## AGENDA1097 — estado vigente 2026-09-12T21:14:14.6044640Z

Parcial: 1 aprobados, 12 fallidos, 10 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 197/742 | 545 | 0 | >=71 | 0/35 |

Procedencia de primeras altas: Al menos 28 primeras altas de Kiro y 43 del retorno acreditadas el 12 de septiembre; esta tanda no suma crédito. No se cuentan revalidaciones.

Siguiente acción: Ejecutar FILES1099, dos literales de contenido truncado con pares y límites sellados, mientras se prepara AGENDA1100 para conservar información ya suministrada al pedir una aclaración temporal. Los ocho literales de agenda permanecen sin ejecutar por pares fallidos; no repetir la tanda completa. Fuente 1100 aún no integrada ni medida, con seis literales potencialmente relacionados y un séptimo pendiente de aislamiento. Límites conversacionales fallidos separados; ningún cierre de categoría o de C03.

Evidencia: `artifacts/comprobaciones/C03/AGENDA1097/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 322.33 s acumulados; pico GPU 3497.56 MiB; pico RAM 1684.26 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 13; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 8 | agenda1097-dev-01 | failed | Pidió de nuevo la hora que ya estaba indicada. | La aclaración no conservó la información temporal aportada. Sin operaciones. |
| 9 | agenda1097-dev-02 | failed | Ofreció opciones de alarma sin resolver la ambigüedad temporal. | La respuesta no aclaró el dato que faltaba. Sin operaciones. |
| 14 | agenda1097-dev-07 | failed | Prometió un recordatorio no creado y no pidió la hora faltante. | La respuesta mezcló una promesa futura con un fallo de interpretación; no hubo operaciones. |
| 15 | agenda1097-dev-08 | failed | Volvió a preguntar qué recordar pese a estar indicado. | La aclaración no conservó los datos aportados. Sin operaciones. |
| 16 | agenda1097-dev-09 | failed | Rechazó globalmente la reunión en lugar de aclarar lo necesario. | No distinguió entre datos o configuración faltantes y capacidad inexistente. Sin operaciones. |
| 17 | agenda1097-dev-10 | failed | Preguntó si debía hacer lo que ya se le había pedido. | No aclaró los datos faltantes para la reunión. Sin operaciones. |
| 12 | agenda1097-dev-05 | failed | El recordatorio acabó en un error de interpretación. | No produjo la aclaración útil requerida. Sin operaciones. |
| 13 | agenda1097-dev-06 | failed | Rechazó globalmente un recordatorio que necesitaba aclaración. | No preguntó por la precisión temporal ausente. Sin operaciones. |
| 18 | agenda1097-boundary-01 | failed | Respuesta inconexa a la prohibición de programar. | No realizó operaciones, pero tampoco reconoció de forma útil la restricción. |
| 19 | agenda1097-boundary-02 | failed | Añadió un período horario que la cita no expresaba. | Explicó la cita sin actuar, pero incorporó una precisión no sustentada. |
| 20 | agenda1097-boundary-03 | failed | Trató una posibilidad futura como una solicitud rechazada. | No atendió al carácter hipotético del comentario. Sin operaciones. |
| 21 | agenda1097-boundary-04 | failed | Rechazó como encargo un relato sobre el pasado. | No reconoció el contenido narrado como declaración de la persona. Sin operaciones. |
| 22 | agenda1097-boundary-05 | passed | Explicó correctamente el contraste conceptual solicitado. | Diferenció un intervalo de tiempo de un instante de aviso, sin operaciones. |

Recursos: 322.33 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1684.26 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
