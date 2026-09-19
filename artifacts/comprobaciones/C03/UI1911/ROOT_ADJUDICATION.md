# UI1911 — adjudicación de la raíz

## UI1911 — estado vigente 2026-09-19T19:18:34.686046+00:00

Parcial: 6 aprobados, 0 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 705/742 | 37 | 0 | >=589 | 13/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 588 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); UI1911 añade 1. No se cuentan revalidaciones.

Siguiente acción: UI1911: 6 ejecutados, 6 aprobados, 0 fallidos, 1 créditos (índices [0]). Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/UI1911/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 129.89 s acumulados; pico GPU 3492.93 MiB; pico RAM 1967.01 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 6; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0101 | passed | lee lo que hay en el diálogo abierto y pulsa el botón que el pedido nombra, diciendo cuál pulsó; crédito con dos variantes aprobadas del mismo grupo. | Turno revisado sobre el diálogo de descarga que la raíz dejó abierto en Steam con el disco E: elegido: una lectura de los controles visibles completada y verificada —30 líneas del diálogo— y un solo clic aprobado por la raíz contra una ventana de Steam, completado y verificado porque la superficie cambió; cero violaciones; pins intactos. |
| 1 | ui1911-dev-01 | passed | lee lo que hay en el diálogo abierto y pulsa el botón que el pedido nombra, diciendo cuál pulsó. | Turno revisado sobre el diálogo de descarga que la raíz dejó abierto en Steam con el disco E: elegido: una lectura de los controles visibles completada y verificada —30 líneas del diálogo— y un solo clic aprobado por la raíz contra una ventana de Steam, completado y verificado porque la superficie cambió; cero violaciones; pins intactos. |
| 2 | ui1911-dev-02 | passed | lee lo que hay en el diálogo abierto y pulsa el botón que el pedido nombra, diciendo cuál pulsó. | Turno revisado sobre el diálogo de descarga que la raíz dejó abierto en Steam con el disco E: elegido: una lectura de los controles visibles completada y verificada —30 líneas del diálogo— y un solo clic aprobado por la raíz contra una ventana de Steam, completado y verificado porque la superficie cambió; cero violaciones; pins intactos. |
| 3 | ui1911-dev-03 | passed | lee lo que hay en el diálogo abierto y pulsa el botón que el pedido nombra, diciendo cuál pulsó. | Turno revisado sobre el diálogo de descarga que la raíz dejó abierto en Steam con el disco E: elegido: una lectura de los controles visibles completada y verificada —30 líneas del diálogo— y un solo clic aprobado por la raíz contra una ventana de Steam, completado y verificado porque la superficie cambió; cero violaciones; pins intactos. |
| 4 | ui1911-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 5 | ui1911-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 129.89 s de segmentos; pico GPU 3492.93 MiB; pico RAM 1967.01 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
