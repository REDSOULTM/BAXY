# UI1641 — adjudicación de la raíz

## UI1641 — estado vigente 2026-09-16T00:57:14.942115+00:00

Parcial: 5 aprobados, 0 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 583/742 | 159 | 0 | >=457 | 6/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 456 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); UI1641 añade 1. No se cuentan revalidaciones.

Siguiente acción: UI1641: 6 ejecutados, 5 aprobados, 1 fallidos, 1 créditos (índices [0]); Abrir aplicaciones 47/54. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/UI1641/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 86.99 s acumulados; pico GPU 3497.56 MiB; pico RAM 1627.98 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0088 | passed | Orden de ir cortada en una preposición: el final citó la cola y preguntó cómo sigue, sin operaciones; crédito con dos variantes aprobadas. | Turno ordinario: cero operaciones; el final cita la cola cortada y pregunta cómo sigue; cero confirmaciones y violaciones; pins intactos. |
| 1 | ui1641-dev-01 | passed | Orden de ir cortada en una preposición: el final citó la cola y preguntó cómo sigue, sin operaciones. | Turno ordinario: cero operaciones; el final cita la cola cortada y pregunta cómo sigue; cero confirmaciones y violaciones; pins intactos. |
| 2 | ui1641-dev-02 | passed | Orden de ir cortada en una preposición: el final citó la cola y preguntó cómo sigue, sin operaciones. | Turno ordinario: cero operaciones; el final cita la cola cortada y pregunta cómo sigue; cero confirmaciones y violaciones; pins intactos. |
| 3 | ui1641-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | ui1641-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 86.99 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1627.98 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
