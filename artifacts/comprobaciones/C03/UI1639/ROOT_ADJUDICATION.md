# UI1639 — adjudicación de la raíz

## UI1639 — estado vigente 2026-09-16T00:50:39.857750+00:00

Parcial: 5 aprobados, 0 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 582/742 | 160 | 0 | >=456 | 6/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 455 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); UI1639 añade 1. No se cuentan revalidaciones.

Siguiente acción: UI1639: 6 ejecutados, 5 aprobados, 1 fallidos, 1 créditos (índices [0]); Abrir aplicaciones 47/54. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/UI1639/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 81.59 s acumulados; pico GPU 3497.56 MiB; pico RAM 1564.38 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0344 | passed | Un color no identifica un control: el final preguntó el texto del botón sin operaciones; crédito con dos variantes aprobadas. | Turno ordinario: cero operaciones; el final pregunta el texto del botón; cero confirmaciones y violaciones; pins intactos. |
| 1 | ui1639-dev-01 | passed | Un color no identifica un control: el final preguntó el texto del botón sin operaciones. | Turno ordinario: cero operaciones; el final pregunta el texto del botón; cero confirmaciones y violaciones; pins intactos. |
| 2 | ui1639-dev-02 | passed | Un color no identifica un control: el final preguntó el texto del botón sin operaciones. | Turno ordinario: cero operaciones; el final pregunta el texto del botón; cero confirmaciones y violaciones; pins intactos. |
| 3 | ui1639-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | ui1639-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 81.59 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1564.38 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
