# CLOSE1371 — adjudicación de la raíz

## CLOSE1371 — estado vigente 2026-09-14T07:34:07.290239+00:00

Parcial: 8 aprobados, 2 fallidos, 0 sin ejecutar; 4 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 417/742 | 325 | 0 | >=291 | 4/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 287 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); CLOSE1371 añade 4. No se cuentan revalidaciones.

Siguiente acción: CLOSE1371: 10 ejecutados, 8 aprobados, 2 fallidos, 4 créditos (índices [0, 1, 2, 3]); Cerrar aplicaciones y ventanas 15/20. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/CLOSE1371/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 208.74 s acumulados; pico GPU 3497.56 MiB; pico RAM 1867.22 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 10; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0117 | passed | Respuesta fiel y útil; crédito con dos variantes aprobadas. | Turno ordinario: ninguna app.close; exactamente una window.resolve sobre Steam terminada window_not_found (observación de ausencia); cero confirmaciones y violaciones; pins intactos; Steam sin ejecutar antes y después (verificado por la raíz). |
| 1 | H0556 | passed | Respuesta fiel y útil; crédito con dos variantes aprobadas. | Turno ordinario: ninguna app.close; exactamente una window.resolve sobre Steam terminada window_not_found (observación de ausencia); cero confirmaciones y violaciones; pins intactos; Steam sin ejecutar antes y después (verificado por la raíz). |
| 2 | H0677 | passed | Respuesta fiel y útil; crédito con dos variantes aprobadas. | Turno ordinario: ninguna app.close; exactamente una window.resolve sobre Steam terminada window_not_found (observación de ausencia); cero confirmaciones y violaciones; pins intactos; Steam sin ejecutar antes y después (verificado por la raíz). |
| 3 | H0679 | passed | Respuesta fiel y útil; crédito con dos variantes aprobadas. | Turno ordinario: ninguna app.close; exactamente una window.resolve sobre Steam terminada window_not_found (observación de ausencia); cero confirmaciones y violaciones; pins intactos; Steam sin ejecutar antes y después (verificado por la raíz). |
| 4 | close1371-dev-01 | passed | Respuesta fiel y útil. | Turno ordinario: ninguna app.close; exactamente una window.resolve sobre Steam terminada window_not_found (observación de ausencia); cero confirmaciones y violaciones; pins intactos; Steam sin ejecutar antes y después (verificado por la raíz). |
| 5 | close1371-dev-02 | passed | Respuesta fiel y útil. | Turno ordinario: ninguna app.close; exactamente una window.resolve sobre Steam terminada window_not_found (observación de ausencia); cero confirmaciones y violaciones; pins intactos; Steam sin ejecutar antes y después (verificado por la raíz). |
| 6 | close1371-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 7 | close1371-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 8 | close1371-boundary-03 | failed | Límite fallido: cero operaciones, pero la respuesta no fue fiel o útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 9 | close1371-boundary-04 | failed | Límite fallido: cero operaciones, pero la respuesta no fue fiel o útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 208.74 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1867.22 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
