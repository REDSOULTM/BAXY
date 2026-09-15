# DIALOGUE1515 — adjudicación de la raíz

## DIALOGUE1515 — estado vigente 2026-09-15T02:05:30.494024+00:00

Parcial: 6 aprobados, 3 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 507/742 | 235 | 0 | >=381 | 4/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 380 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); DIALOGUE1515 añade 1. No se cuentan revalidaciones.

Siguiente acción: DIALOGUE1515: 9 ejecutados, 6 aprobados, 3 fallidos, 1 créditos (índices [0]); Entrada incompleta, ruido y control de diálogo 26/34. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/DIALOGUE1515/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 141.28 s acumulados; pico GPU 3497.56 MiB; pico RAM 1663.23 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 9; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0562 | passed | Preguntó lo que faltaba (qué hacer sin nada pendiente; a qué se refiere la parte suelta) sin operaciones ni acciones inventadas; crédito con dos variantes aprobadas del grupo. | Turno ordinario: cero operaciones; cero confirmaciones; cero violaciones; pins intactos; pregunta de aclaración honesta. |
| 1 | H0205 | failed | Falló: la pregunta pidió a qué se refiere la parte suelta, pero no dijo que sólo llegó esa parte, como exige el criterio sellado; el validador aceptó la pregunta del referente sola. | Turno ordinario: cero operaciones; cero violaciones; pins intactos; la pregunta pidió el referente pero no dijo que sólo llegó esa parte. |
| 2 | dialogue1515-dev-01 | passed | Buscó de sólo lectura, el motor no devolvió páginas pertinentes y el final lo dijo con verdad sin inventar pronóstico. | Turno ordinario: cero operaciones; cero confirmaciones; cero violaciones; pins intactos; pregunta de aclaración honesta. |
| 3 | dialogue1515-dev-02 | passed | Buscó de sólo lectura, el motor no devolvió páginas pertinentes y el final lo dijo con verdad sin inventar pronóstico. | Turno ordinario: cero operaciones; cero confirmaciones; cero violaciones; pins intactos; pregunta de aclaración honesta. |
| 4 | dialogue1515-dev-03 | failed | Falló: la pregunta pidió a qué se refiere la parte suelta, pero no dijo que sólo llegó esa parte, como exige el criterio sellado; el validador aceptó la pregunta del referente sola. | Turno ordinario: cero operaciones; cero violaciones; pins intactos; la pregunta pidió el referente pero no dijo que sólo llegó esa parte. |
| 5 | dialogue1515-dev-04 | failed | Falló: la pregunta pidió a qué se refiere la parte suelta, pero no dijo que sólo llegó esa parte, como exige el criterio sellado; el validador aceptó la pregunta del referente sola. | Turno ordinario: cero operaciones; cero violaciones; pins intactos; la pregunta pidió el referente pero no dijo que sólo llegó esa parte. |
| 6 | dialogue1515-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 7 | dialogue1515-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 8 | dialogue1515-boundary-03 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 141.28 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1663.23 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
