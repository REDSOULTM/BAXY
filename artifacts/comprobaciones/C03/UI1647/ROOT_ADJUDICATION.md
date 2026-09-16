# UI1647 — adjudicación de la raíz

## UI1647 — estado vigente 2026-09-16T01:41:53.072484+00:00

Parcial: 3 aprobados, 2 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 585/742 | 157 | 0 | >=459 | 6/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 458 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); UI1647 añade 1. No se cuentan revalidaciones.

Siguiente acción: UI1647: 6 ejecutados, 3 aprobados, 3 fallidos, 1 créditos (índices [0]); Abrir aplicaciones 47/54. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/UI1647/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 83.59 s acumulados; pico GPU 3497.56 MiB; pico RAM 1597.24 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0265 | passed | Orden de escribir sin texto: el final preguntó qué escribir, sin operaciones; crédito con dos variantes aprobadas. | Turno ordinario: cero operaciones; el final pregunta qué texto escribir; cero confirmaciones y violaciones; pins intactos. |
| 1 | ui1647-dev-01 | passed | Orden de escribir sin texto: el final preguntó qué escribir, sin operaciones. | Turno ordinario: cero operaciones; el final pregunta qué texto escribir; cero confirmaciones y violaciones; pins intactos. |
| 2 | ui1647-dev-02 | passed | Orden de escribir sin texto: el final preguntó qué escribir, sin operaciones. | Turno ordinario: cero operaciones; el final pregunta qué texto escribir; cero confirmaciones y violaciones; pins intactos. |
| 3 | ui1647-boundary-01 | failed | Límite fallido: cero operaciones, pero la respuesta no fue fiel o útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | ui1647-boundary-02 | failed | Límite fallido: cero operaciones, pero la respuesta no fue fiel o útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 83.59 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1597.24 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
