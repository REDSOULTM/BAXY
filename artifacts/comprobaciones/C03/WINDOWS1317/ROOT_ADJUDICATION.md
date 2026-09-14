# WINDOWS1317 — adjudicación de la raíz

## WINDOWS1317 — estado vigente 2026-09-14T02:48:48.402441+00:00

Parcial: 4 aprobados, 1 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 387/742 | 355 | 0 | >=261 | 2/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 260 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); WINDOWS1317 añade 1. No se cuentan revalidaciones.

Siguiente acción: WINDOWS1317: 5 ejecutados, 4 aprobados, 1 fallidos, 1 créditos (índices [0]); categoría Estado de ventanas y aplicaciones cerrada 14/14. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/WINDOWS1317/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 84.06 s acumulados; pico GPU 3497.56 MiB; pico RAM 1595.11 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0419 | passed | Lectura verificada y respuesta fiel; crédito con dos variantes aprobadas. | Turno ordinario: window.resolve (inventario de todas las ventanas) de sólo lectura completada y verificada; cero confirmaciones y violaciones; pins intactos. |
| 1 | windows1317-dev-01 | passed | Lectura verificada y respuesta fiel. | Turno ordinario: window.resolve (inventario de todas las ventanas) de sólo lectura completada y verificada; cero confirmaciones y violaciones; pins intactos. |
| 2 | windows1317-dev-02 | passed | Lectura verificada y respuesta fiel. | Turno ordinario: window.resolve (inventario de todas las ventanas) de sólo lectura completada y verificada; cero confirmaciones y violaciones; pins intactos. |
| 3 | windows1317-boundary-01 | failed | Límite fallido: cero operaciones, pero la respuesta no fue fiel o útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | windows1317-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 84.06 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1595.11 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
