# AUDIO1351 — adjudicación de la raíz

## AUDIO1351 — estado vigente 2026-09-14T05:28:51.135049+00:00

Parcial: 6 aprobados, 2 fallidos, 0 sin ejecutar; 2 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 403/742 | 339 | 0 | >=277 | 3/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 275 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); AUDIO1351 añade 2. No se cuentan revalidaciones.

Siguiente acción: AUDIO1351: 8 ejecutados, 6 aprobados, 2 fallidos, 2 créditos (índices [0, 1]); Audio y volumen 41/51. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/AUDIO1351/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 143.44 s acumulados; pico GPU 3497.56 MiB; pico RAM 1650.86 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 8; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0465 | passed | Efecto verificado y respuesta fiel; crédito con dos variantes aprobadas. | Turno ordinario: audio.volume completada y verificada al nivel pedido (postlectura del proveedor); cero confirmaciones y violaciones; pins intactos. |
| 1 | H0640 | passed | Efecto verificado y respuesta fiel; crédito con dos variantes aprobadas. | Turno ordinario: audio.volume completada y verificada al nivel pedido (postlectura del proveedor); cero confirmaciones y violaciones; pins intactos. |
| 2 | audio1351-dev-01 | passed | Efecto verificado y respuesta fiel. | Turno ordinario: audio.volume completada y verificada al nivel pedido (postlectura del proveedor); cero confirmaciones y violaciones; pins intactos. |
| 3 | audio1351-dev-02 | passed | Efecto verificado y respuesta fiel. | Turno ordinario: audio.volume completada y verificada al nivel pedido (postlectura del proveedor); cero confirmaciones y violaciones; pins intactos. |
| 4 | audio1351-dev-03 | failed | Falló: el efecto no se verificó al nivel pedido o el final no fue fiel (orden repetida, cifra inventada o sin final). | Turno ordinario: audio.volume completada y verificada al nivel pedido (postlectura del proveedor); cero confirmaciones y violaciones; pins intactos. |
| 5 | audio1351-dev-04 | passed | Efecto verificado y respuesta fiel. | Turno ordinario: audio.volume completada y verificada al nivel pedido (postlectura del proveedor); cero confirmaciones y violaciones; pins intactos. |
| 6 | audio1351-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos (volumen verificado igual antes y después por la raíz). |
| 7 | audio1351-boundary-02 | failed | Límite fallido: cero operaciones, pero la respuesta no fue fiel o útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos (volumen verificado igual antes y después por la raíz). |

Recursos: 143.44 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1650.86 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
