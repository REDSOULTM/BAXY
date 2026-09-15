# AUDIO1579 — adjudicación de la raíz

## AUDIO1579 — estado vigente 2026-09-15T17:34:50.409412+00:00

Parcial: 5 aprobados, 0 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 535/742 | 207 | 0 | >=409 | 5/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 408 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); AUDIO1579 añade 1. No se cuentan revalidaciones.

Siguiente acción: AUDIO1579: 5 ejecutados, 5 aprobados, 0 fallidos, 1 créditos (índices [0]); Audio y volumen 46/51. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/AUDIO1579/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 81.55 s acumulados; pico GPU 3497.56 MiB; pico RAM 1485.84 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0067 | passed | Lectura verificada, dato observado en el final y una sola pregunta por la cantidad del volumen, sin cambiarlo; crédito con dos variantes aprobadas. | Turno ordinario: system.time de sólo lectura completada y verificada; cero confirmaciones y violaciones; pins intactos. |
| 1 | audio1579-dev-01 | passed | Lectura verificada, dato observado en el final y una sola pregunta por la cantidad del volumen, sin cambiarlo. | Turno ordinario: system.time de sólo lectura completada y verificada; cero confirmaciones y violaciones; pins intactos. |
| 2 | audio1579-dev-02 | passed | Lectura verificada, dato observado en el final y una sola pregunta por la cantidad del volumen, sin cambiarlo. | Turno ordinario: system.time de sólo lectura completada y verificada; cero confirmaciones y violaciones; pins intactos. |
| 3 | audio1579-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | audio1579-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 81.55 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1485.84 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
