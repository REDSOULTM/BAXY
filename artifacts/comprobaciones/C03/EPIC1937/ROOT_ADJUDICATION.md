# EPIC1937 — adjudicación de la raíz

## EPIC1937 — estado vigente 2026-09-20T07:33:48.997433+00:00

Parcial: 5 aprobados, 0 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 726/742 | 16 | 0 | >=610 | 29/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 609 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); EPIC1937 añade 1. No se cuentan revalidaciones.

Siguiente acción: EPIC1937: 5 ejecutados, 5 aprobados, 0 fallidos, 1 créditos (índices [0]); Información web actual 17/17. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/EPIC1937/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 89.47 s acumulados; pico GPU 3492.93 MiB; pico RAM 1788.63 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0578 | passed | game.entitlement.named completada y verificada sobre la biblioteca del lanzador de Epic Games (nada descargado ni comprado); el final dijo el estado leído del juego nombrado por la persona sin inventar efectos; crédito con dos variantes aprobadas del mismo grupo. | Turno ordinario: exactamente una game.entitlement.named con store=epic completada y verificada (manifiestos instalados y caché del catálogo autenticado del lanzador de Epic Games; nada descargado, comprado ni abierto); el final dijo el estado leído del juego nombrado como la persona lo nombró, sin inventar que instaló, descargó ni desinstaló nada; cero confirmaciones y violaciones; pins intactos. |
| 1 | epic1937-dev-01 | passed | game.entitlement.named completada y verificada sobre la biblioteca del lanzador de Epic Games (nada descargado ni comprado); el final dijo el estado leído del juego nombrado por la persona sin inventar efectos. | Turno ordinario: exactamente una game.entitlement.named con store=epic completada y verificada (manifiestos instalados y caché del catálogo autenticado del lanzador de Epic Games; nada descargado, comprado ni abierto); el final dijo el estado leído del juego nombrado como la persona lo nombró, sin inventar que instaló, descargó ni desinstaló nada; cero confirmaciones y violaciones; pins intactos. |
| 2 | epic1937-dev-02 | passed | game.entitlement.named completada y verificada sobre la biblioteca del lanzador de Epic Games (nada descargado ni comprado); el final dijo el estado leído del juego nombrado por la persona sin inventar efectos. | Turno ordinario: exactamente una game.entitlement.named con store=epic completada y verificada (manifiestos instalados y caché del catálogo autenticado del lanzador de Epic Games; nada descargado, comprado ni abierto); el final dijo el estado leído del juego nombrado como la persona lo nombró, sin inventar que instaló, descargó ni desinstaló nada; cero confirmaciones y violaciones; pins intactos. |
| 3 | epic1937-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | epic1937-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 89.47 s de segmentos; pico GPU 3492.93 MiB; pico RAM 1788.63 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
