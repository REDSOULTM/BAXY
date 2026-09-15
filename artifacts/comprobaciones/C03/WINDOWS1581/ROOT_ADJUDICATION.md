# WINDOWS1581 — adjudicación de la raíz

## WINDOWS1581 — estado vigente 2026-09-15T17:40:21.033027+00:00

Parcial: 5 aprobados, 0 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 536/742 | 206 | 0 | >=410 | 5/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 409 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); WINDOWS1581 añade 1. No se cuentan revalidaciones.

Siguiente acción: WINDOWS1581: 5 ejecutados, 5 aprobados, 0 fallidos, 1 créditos (índices [0]); Organizar ventanas y pestañas 7/13. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/WINDOWS1581/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 88.63 s acumulados; pico GPU 3497.56 MiB; pico RAM 1628.43 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0527 | passed | Lectura verificada, dato observado en el final y una sola pregunta por cuál ventana enfocar, sin enfocar ninguna; crédito con dos variantes aprobadas. | Turno ordinario: window.resolve de sólo lectura completada y verificada; cero confirmaciones y violaciones; pins intactos. |
| 1 | windows1581-dev-01 | passed | Lectura verificada, dato observado en el final y una sola pregunta por cuál ventana enfocar, sin enfocar ninguna. | Turno ordinario: window.resolve de sólo lectura completada y verificada; cero confirmaciones y violaciones; pins intactos. |
| 2 | windows1581-dev-02 | passed | Lectura verificada, dato observado en el final y una sola pregunta por cuál ventana enfocar, sin enfocar ninguna. | Turno ordinario: window.resolve de sólo lectura completada y verificada; cero confirmaciones y violaciones; pins intactos. |
| 3 | windows1581-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | windows1581-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 88.63 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1628.43 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
