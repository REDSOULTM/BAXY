# CLOCK1335 — adjudicación de la raíz

## CLOCK1335 — estado vigente 2026-09-14T04:26:08.222780+00:00

Parcial: 5 aprobados, 0 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 396/742 | 346 | 0 | >=270 | 3/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 269 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); CLOCK1335 añade 1. No se cuentan revalidaciones.

Siguiente acción: CLOCK1335: 5 ejecutados, 5 aprobados, 0 fallidos, 1 créditos (índices [0]); Hora y fecha 19/23 (los literales en otros idiomas quedan fuera de aceptación). Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/CLOCK1335/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 78.59 s acumulados; pico GPU 3497.56 MiB; pico RAM 1528.46 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0399 | passed | Lectura verificada y respuesta fiel; crédito con dos variantes aprobadas. | Turno ordinario: system.time de sólo lectura completada y verificada; cero confirmaciones y violaciones; pins intactos. |
| 1 | clock1335-dev-01 | passed | Lectura verificada y respuesta fiel. | Turno ordinario: system.time de sólo lectura completada y verificada; cero confirmaciones y violaciones; pins intactos. |
| 2 | clock1335-dev-02 | passed | Lectura verificada y respuesta fiel. | Turno ordinario: system.time de sólo lectura completada y verificada; cero confirmaciones y violaciones; pins intactos. |
| 3 | clock1335-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | clock1335-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 78.59 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1528.46 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
