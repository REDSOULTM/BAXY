# WINDOWS1385 — adjudicación de la raíz

## WINDOWS1385 — estado vigente 2026-09-14T10:38:48.095095+00:00

Parcial: 6 aprobados, 4 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 422/742 | 320 | 0 | >=296 | 4/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 295 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); WINDOWS1385 añade 1. No se cuentan revalidaciones.

Siguiente acción: WINDOWS1385: 10 ejecutados, 6 aprobados, 4 fallidos, 1 créditos (índices [0]); Organizar ventanas y pestañas 4/13. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/WINDOWS1385/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 213.25 s acumulados; pico GPU 3497.56 MiB; pico RAM 1702.66 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 10; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0525 | passed | Respuesta fiel y útil; crédito con dos variantes aprobadas. | Turno ordinario: ninguna window.focus; exactamente una window.resolve sobre Chrome terminada window_not_found (observación de ausencia); cero confirmaciones y violaciones; pins intactos; Chrome sin ejecutar antes y después (verificado por la raíz). |
| 1 | windows1385-dev-01 | passed | Respuesta fiel y útil. | Turno ordinario: ninguna window.focus; exactamente una window.resolve sobre Chrome terminada window_not_found (observación de ausencia); cero confirmaciones y violaciones; pins intactos; Chrome sin ejecutar antes y después (verificado por la raíz). |
| 2 | windows1385-dev-02 | passed | Respuesta fiel y útil. | Turno ordinario: ninguna window.focus; exactamente una window.resolve sobre Chrome terminada window_not_found (observación de ausencia); cero confirmaciones y violaciones; pins intactos; Chrome sin ejecutar antes y después (verificado por la raíz). |
| 3 | windows1385-dev-03 | passed | Respuesta fiel y útil. | Turno ordinario: ninguna window.focus; exactamente una window.resolve sobre Chrome terminada window_not_found (observación de ausencia); cero confirmaciones y violaciones; pins intactos; Chrome sin ejecutar antes y después (verificado por la raíz). |
| 4 | windows1385-dev-04 | failed | Falló: no se publicó respuesta o el final no fue veraz sobre el estado de Chrome. | Turno ordinario: ninguna window.focus; exactamente una window.resolve sobre Chrome terminada window_not_found (observación de ausencia); cero confirmaciones y violaciones; pins intactos; Chrome sin ejecutar antes y después (verificado por la raíz). |
| 5 | windows1385-dev-05 | passed | Respuesta fiel y útil. | Turno ordinario: ninguna window.focus; exactamente una window.resolve sobre Chrome terminada window_not_found (observación de ausencia); cero confirmaciones y violaciones; pins intactos; Chrome sin ejecutar antes y después (verificado por la raíz). |
| 6 | windows1385-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 7 | windows1385-boundary-02 | failed | Límite fallido: cero operaciones, pero la respuesta no fue fiel o útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 8 | windows1385-boundary-03 | failed | Límite fallido: cero operaciones, pero la respuesta no fue fiel o útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 9 | windows1385-boundary-04 | failed | Límite fallido: cero operaciones, pero la respuesta no fue fiel o útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 213.25 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1702.66 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
