# WEB1543 — adjudicación de la raíz

## WEB1543 — estado vigente 2026-09-15T04:54:06.412155+00:00

Parcial: 7 aprobados, 0 fallidos, 0 sin ejecutar; 2 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 519/742 | 223 | 0 | >=393 | 4/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 391 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); WEB1543 añade 2. No se cuentan revalidaciones.

Siguiente acción: WEB1543: 7 ejecutados, 7 aprobados, 0 fallidos, 2 créditos (índices [0, 1]); Leer y resumir páginas web 2/2. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/WEB1543/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 121.08 s acumulados; pico GPU 3497.56 MiB; pico RAM 1696.43 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 7; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0561 | passed | Leyó con revisión la página abierta en el navegador y la nombró citando su comienzo tal cual; crédito con dos variantes aprobadas. | Turno revisado: browser.page.read propuesta sin argumentos de destino, aprobada por la raíz sobre su propio fixture (Edge y página del raíz), completada y verificada; una confirmación; cero violaciones; pins intactos. |
| 1 | H0738 | passed | Leyó con revisión la página abierta en el navegador y la nombró citando su comienzo tal cual; crédito con dos variantes aprobadas. | Turno revisado: browser.page.read propuesta sin argumentos de destino, aprobada por la raíz sobre su propio fixture (Edge y página del raíz), completada y verificada; una confirmación; cero violaciones; pins intactos. |
| 2 | web1543-dev-01 | passed | Leyó con revisión la página abierta y la nombró citando su comienzo tal cual; variante o literal sin dos pares aprobados. | Turno revisado: browser.page.read propuesta sin argumentos de destino, aprobada por la raíz sobre su propio fixture (Edge y página del raíz), completada y verificada; una confirmación; cero violaciones; pins intactos. |
| 3 | web1543-dev-02 | passed | Leyó con revisión la página abierta y la nombró citando su comienzo tal cual; variante o literal sin dos pares aprobados. | Turno revisado: browser.page.read propuesta sin argumentos de destino, aprobada por la raíz sobre su propio fixture (Edge y página del raíz), completada y verificada; una confirmación; cero violaciones; pins intactos. |
| 4 | web1543-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 5 | web1543-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 6 | web1543-boundary-03 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 121.08 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1696.43 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
