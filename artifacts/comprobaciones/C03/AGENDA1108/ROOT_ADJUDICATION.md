# AGENDA1108 — adjudicación de la raíz

## AGENDA1108 — estado vigente 2026-09-12T22:46:26.1663680Z

Parcial: 1 aprobados, 1 fallidos, 9 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 198/742 | 544 | 0 | >=72 | 0/35 |

Procedencia de primeras altas: Cota inferior: 28 primeras altas Kiro y44 de retorno dentro del12 de septiembre; incluye H0572 de1104 una sola vez. No revalidaciones ni fechas de actualización.

Siguiente acción: Reparar la inversión de hablante/destinatario en el generador de aclaraciones compartido, propuesta CLARIFICATION1109, y medir AGENDA1110: cuatro alarmas y H0137, conservando pares pertinentes. Fuente1107 resuelve la ambigüedad del slot, no el actor. DIALOGUE1098/1106 siguen pendientes; límites previos sin hipótesis nueva no se repiten.

Evidencia: `artifacts/comprobaciones/C03/AGENDA1108/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 45.61 s acumulados; pico GPU 3493.56 MiB; pico RAM 1580.05 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 2; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | agenda1097-dev-01 | passed | Aclaración AM/PM pertinente. | Conserva la hora dada y pregunta por el periodo, sin programar. |
| 1 | agenda1097-dev-02 | failed | Invierte quién pide y quién recibe la alarma. | La pregunta usa la voz del usuario y pide que éste despierte al asistente. |

Recursos: 45.61 s de segmentos; pico GPU 3493.56 MiB; pico RAM 1580.05 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
