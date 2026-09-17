# DISCORD1839 — adjudicación de la raíz

## DISCORD1839 — estado vigente 2026-09-17T16:48:52.940667+00:00

Parcial: 5 aprobados, 0 fallidos, 0 sin ejecutar; 2 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 652/742 | 90 | 0 | >=536 | 13/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 534 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); DISCORD1839 añade 2. No se cuentan revalidaciones.

Siguiente acción: DISCORD1839: 5 ejecutados, 5 aprobados, 0 fallidos, 2 créditos (índices [0, 1]); Interacción dentro de aplicaciones 21/22. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/DISCORD1839/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 102.12 s acumulados; pico GPU 3497.56 MiB; pico RAM 1770.57 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0290 | passed | client.channel.locate completada y verificada (buscador rápido del cliente leído y cerrado, nada unido); el final dijo que encontró el canal y preguntó antes de unirse; crédito con dos variantes aprobadas del mismo grupo. | Turno ordinario: exactamente una client.channel.locate completada y verificada (buscador rápido del cliente leído por UI Automation y cerrado; nada unido ni abierto); el final dijo que encontró el canal con su tipo y servidor y preguntó si se une; cero confirmaciones y violaciones; pins intactos. |
| 1 | H0636 | passed | client.channel.locate completada y verificada (buscador rápido del cliente leído y cerrado, nada unido); el final dijo que encontró el canal y preguntó antes de unirse; crédito con dos variantes aprobadas del mismo grupo. | Turno ordinario: exactamente una client.channel.locate completada y verificada (buscador rápido del cliente leído por UI Automation y cerrado; nada unido ni abierto); el final dijo que encontró el canal con su tipo y servidor y preguntó si se une; cero confirmaciones y violaciones; pins intactos. |
| 2 | discord1839-dev-01 | passed | client.channel.locate completada y verificada (buscador rápido del cliente leído y cerrado, nada unido); el final dijo que encontró el canal y preguntó antes de unirse. | Turno ordinario: exactamente una client.channel.locate completada y verificada (buscador rápido del cliente leído por UI Automation y cerrado; nada unido ni abierto); el final dijo que encontró el canal con su tipo y servidor y preguntó si se une; cero confirmaciones y violaciones; pins intactos. |
| 3 | discord1839-dev-02 | passed | client.channel.locate completada y verificada (buscador rápido del cliente leído y cerrado, nada unido); el final dijo que encontró el canal y preguntó antes de unirse. | Turno ordinario: exactamente una client.channel.locate completada y verificada (buscador rápido del cliente leído por UI Automation y cerrado; nada unido ni abierto); el final dijo que encontró el canal con su tipo y servidor y preguntó si se une; cero confirmaciones y violaciones; pins intactos. |
| 4 | discord1839-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 102.12 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1770.57 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
