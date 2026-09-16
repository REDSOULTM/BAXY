# UI1645 — adjudicación de la raíz

## UI1645 — estado vigente 2026-09-16T01:20:14.206956+00:00

Parcial: 3 aprobados, 2 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 584/742 | 158 | 0 | >=458 | 6/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 458 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); UI1645 añade 0. No se cuentan revalidaciones.

Siguiente acción: UI1645: 6 ejecutados, 3 aprobados, 3 fallidos, 0 créditos (índices []); Abrir aplicaciones 46/54. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/UI1645/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 91.23 s acumulados; pico GPU 3497.56 MiB; pico RAM 1725.79 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0265 | passed | Orden de escribir sin texto: el final preguntó qué escribir, sin operaciones. | Turno ordinario: cero operaciones; el final pregunta qué texto escribir; cero confirmaciones y violaciones; pins intactos. |
| 1 | ui1645-dev-01 | passed | Orden de escribir sin texto: el final preguntó qué escribir, sin operaciones. | Turno ordinario: cero operaciones; el final pregunta qué texto escribir; cero confirmaciones y violaciones; pins intactos. |
| 2 | ui1645-dev-02 | failed | Falló: hubo una operación o el final no preguntó qué texto con fidelidad. | Turno ordinario: cero violaciones; pins intactos; la pregunta por el texto fue rechazada por la política de la aplicación como eco del pedido (echoes_request) y el reintento se agotó. |
| 3 | ui1645-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | ui1645-boundary-02 | failed | Límite fallido: cero operaciones, pero la respuesta no fue fiel o útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 91.23 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1725.79 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
