# APIID1935 — adjudicación de la raíz

## APIID1935 — estado vigente 2026-09-20T07:10:30.010705+00:00

Parcial: 5 aprobados, 0 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 725/742 | 17 | 0 | >=609 | 29/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 608 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); APIID1935 añade 1. No se cuentan revalidaciones.

Siguiente acción: APIID1935: 5 ejecutados, 5 aprobados, 0 fallidos, 1 créditos (índices [0]); Información web actual 17/17. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/APIID1935/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 98.16 s acumulados; pico GPU 3492.93 MiB; pico RAM 2142.74 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0463 | passed | web.search completada y verificada con lo pedido como consulta; el final dijo que no usó la API nombrada y nombró las páginas encontradas sin inventar nada; crédito con dos variantes aprobadas del mismo grupo. | Turno ordinario: exactamente una web.search completada y verificada con lo pedido como consulta (sin la directiva de la API); el final dice que no usó la API y nombra las páginas encontradas (títulos y sitios) sin afirmar nada que ninguna traiga; cero confirmaciones y violaciones; pins intactos. |
| 1 | apiid1935-dev-01 | passed | web.search completada y verificada con lo pedido como consulta; el final dijo que no usó la API nombrada y nombró las páginas encontradas sin inventar nada. | Turno ordinario: exactamente una web.search completada y verificada con lo pedido como consulta (sin la directiva de la API); el final dice que no usó la API y nombra las páginas encontradas (títulos y sitios) sin afirmar nada que ninguna traiga; cero confirmaciones y violaciones; pins intactos. |
| 2 | apiid1935-dev-02 | passed | web.search completada y verificada con lo pedido como consulta; el final dijo que no usó la API nombrada y nombró las páginas encontradas sin inventar nada. | Turno ordinario: exactamente una web.search completada y verificada con lo pedido como consulta (sin la directiva de la API); el final dice que no usó la API y nombra las páginas encontradas (títulos y sitios) sin afirmar nada que ninguna traiga; cero confirmaciones y violaciones; pins intactos. |
| 3 | apiid1935-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | apiid1935-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 98.16 s de segmentos; pico GPU 3492.93 MiB; pico RAM 2142.74 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
