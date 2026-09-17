# KNOW1833 — adjudicación de la raíz

## KNOW1833 — estado vigente 2026-09-17T07:34:59.793317+00:00

Parcial: 3 aprobados, 2 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 649/742 | 93 | 0 | >=533 | 13/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 533 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); KNOW1833 añade 0. No se cuentan revalidaciones.

Siguiente acción: KNOW1833: 5 ejecutados, 3 aprobados, 2 fallidos, 0 créditos (índices []); Conocimiento, razonamiento y creatividad verbal 36/37. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/KNOW1833/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 88.05 s acumulados; pico GPU 3497.56 MiB; pico RAM 1719.92 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0297 | passed | Tramo largo de habla sin pedido: cero operaciones y un final que dijo con honestidad que no encontró un pedido para BAXY y preguntó si la persona necesita algo, sin responder ni repetir lo dicho. | Turno ordinario: cero operaciones; el final dice con honestidad que en lo dicho no encuentra un pedido para BAXY y pregunta si la persona necesita algo, sin responder ni repetir lo dicho; cero confirmaciones y violaciones; pins intactos. |
| 1 | know1833-dev-01 | passed | Tramo largo de habla sin pedido: cero operaciones y un final que dijo con honestidad que no encontró un pedido para BAXY y preguntó si la persona necesita algo, sin responder ni repetir lo dicho. | Turno ordinario: cero operaciones; el final dice con honestidad que en lo dicho no encuentra un pedido para BAXY y pregunta si la persona necesita algo, sin responder ni repetir lo dicho; cero confirmaciones y violaciones; pins intactos. |
| 2 | know1833-dev-02 | failed | Falló: la operación no se completó o no se verificó, o el final no fue fiel. | Turno ordinario: cero operaciones; el final repitió la afirmación de la persona en vez de la aclaración de habla ajena. |
| 3 | know1833-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | know1833-boundary-02 | failed | Límite fallido: cero operaciones, pero la respuesta no fue fiel o útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 88.05 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1719.92 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
