# UI1657 — adjudicación de la raíz

## UI1657 — estado vigente 2026-09-16T02:59:51.004564+00:00

Parcial: 7 aprobados, 1 fallidos, 0 sin ejecutar; 4 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 592/742 | 150 | 0 | >=466 | 6/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 462 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); UI1657 añade 4. No se cuentan revalidaciones.

Siguiente acción: UI1657: 6 ejecutados, 7 aprobados, -1 fallidos, 4 créditos (índices [0, 1, 2, 3]); Abrir aplicaciones 50/54. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/UI1657/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 129.95 s acumulados; pico GPU 3497.56 MiB; pico RAM 1705.89 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 8; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0232 | passed | Silencio pedido dentro de un cliente de voz: el final preguntó si silencia el micrófono del sistema, sin operaciones; crédito con dos variantes aprobadas. | Turno ordinario: cero operaciones; el final pregunta si silencia el micrófono del sistema; cero confirmaciones y violaciones; pins intactos. |
| 1 | H0325 | passed | Silencio pedido dentro de un cliente de voz: el final preguntó si silencia el micrófono del sistema, sin operaciones; crédito con dos variantes aprobadas. | Turno ordinario: cero operaciones; el final pregunta si silencia el micrófono del sistema; cero confirmaciones y violaciones; pins intactos. |
| 2 | H0368 | passed | Silencio pedido dentro de un cliente de voz: el final preguntó si silencia el micrófono del sistema, sin operaciones; crédito con dos variantes aprobadas. | Turno ordinario: cero operaciones; el final pregunta si silencia el micrófono del sistema; cero confirmaciones y violaciones; pins intactos. |
| 3 | H0128 | passed | Silencio pedido dentro de un cliente de voz: el final preguntó si silencia el micrófono del sistema, sin operaciones; crédito con dos variantes aprobadas. | Turno ordinario: cero operaciones; el final pregunta si silencia el micrófono del sistema; cero confirmaciones y violaciones; pins intactos. |
| 4 | ui1657-dev-01 | passed | Silencio pedido dentro de un cliente de voz: el final preguntó si silencia el micrófono del sistema, sin operaciones. | Turno ordinario: cero operaciones; el final pregunta si silencia el micrófono del sistema; cero confirmaciones y violaciones; pins intactos. |
| 5 | ui1657-dev-02 | passed | Silencio pedido dentro de un cliente de voz: el final preguntó si silencia el micrófono del sistema, sin operaciones. | Turno ordinario: cero operaciones; el final pregunta si silencia el micrófono del sistema; cero confirmaciones y violaciones; pins intactos. |
| 6 | ui1657-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 7 | ui1657-boundary-02 | failed | Límite fallido: cero operaciones, pero la respuesta no fue fiel o útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 129.95 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1705.89 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
