# KNOWLEDGE1507 — adjudicación de la raíz

## KNOWLEDGE1507 — estado vigente 2026-09-15T01:29:24.013058+00:00

Parcial: 9 aprobados, 2 fallidos, 0 sin ejecutar; 3 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 498/742 | 244 | 0 | >=372 | 4/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 369 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); KNOWLEDGE1507 añade 3. No se cuentan revalidaciones.

Siguiente acción: KNOWLEDGE1507: 11 ejecutados, 9 aprobados, 2 fallidos, 3 créditos (índices [0, 1, 3]); Conocimiento, razonamiento y creatividad verbal 30/37. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/KNOWLEDGE1507/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 220.05 s acumulados; pico GPU 3497.56 MiB; pico RAM 2381.93 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 11; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0003 | passed | Respuesta fiel: buscó de sólo lectura un tema elegido y contó lo que un fragmento afirma nombrando la página (o dijo con verdad que no encontró páginas sobre el tema); crédito con dos variantes aprobadas del grupo. | Turno ordinario: una web.search de sólo lectura completada y verificada (o fallida por resultados no pertinentes, fallo honesto sellado) sobre un tema elegido por el producto; cero confirmaciones; cero violaciones; pins intactos. |
| 1 | H0476 | passed | Respuesta fiel: buscó de sólo lectura un tema elegido y contó lo que un fragmento afirma nombrando la página (o dijo con verdad que no encontró páginas sobre el tema); crédito con dos variantes aprobadas del grupo. | Turno ordinario: una web.search de sólo lectura completada y verificada (o fallida por resultados no pertinentes, fallo honesto sellado) sobre un tema elegido por el producto; cero confirmaciones; cero violaciones; pins intactos. |
| 2 | H0520 | failed | Falló: la búsqueda se completó y los borradores repetían el fragmento nombrando la página, pero el veto de palabra cortada del compositor tomó el singular «curiosidad» por un corte del plural «curiosidades» de un título y no se publicó final. | Turno ordinario: una web.search de sólo lectura completada y verificada sobre un tema elegido por el producto; cero confirmaciones; cero violaciones; pins intactos; sin final publicado. |
| 3 | H0703 | passed | Respuesta fiel: buscó de sólo lectura un tema elegido y contó lo que un fragmento afirma nombrando la página (o dijo con verdad que no encontró páginas sobre el tema); crédito con dos variantes aprobadas del grupo. | Turno ordinario: una web.search de sólo lectura completada y verificada (o fallida por resultados no pertinentes, fallo honesto sellado) sobre un tema elegido por el producto; cero confirmaciones; cero violaciones; pins intactos. |
| 4 | knowledge1507-dev-01 | passed | Buscó de sólo lectura, el motor no devolvió páginas pertinentes y el final lo dijo con verdad sin inventar pronóstico. | Turno ordinario: una web.search de sólo lectura completada y verificada (o fallida por resultados no pertinentes, fallo honesto sellado) sobre un tema elegido por el producto; cero confirmaciones; cero violaciones; pins intactos. |
| 5 | knowledge1507-dev-02 | passed | Buscó de sólo lectura, el motor no devolvió páginas pertinentes y el final lo dijo con verdad sin inventar pronóstico. | Turno ordinario: una web.search de sólo lectura completada y verificada (o fallida por resultados no pertinentes, fallo honesto sellado) sobre un tema elegido por el producto; cero confirmaciones; cero violaciones; pins intactos. |
| 6 | knowledge1507-dev-03 | passed | Buscó de sólo lectura, el motor no devolvió páginas pertinentes y el final lo dijo con verdad sin inventar pronóstico. | Turno ordinario: una web.search de sólo lectura completada y verificada (o fallida por resultados no pertinentes, fallo honesto sellado) sobre un tema elegido por el producto; cero confirmaciones; cero violaciones; pins intactos. |
| 7 | knowledge1507-dev-04 | failed | Falló: la búsqueda se completó y los borradores repetían el fragmento nombrando la página, pero el veto de palabra cortada del compositor tomó el singular «curiosidad» por un corte del plural «curiosidades» de un título y no se publicó final. | Turno ordinario: una web.search de sólo lectura completada y verificada sobre un tema elegido por el producto; cero confirmaciones; cero violaciones; pins intactos; sin final publicado. |
| 8 | knowledge1507-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 9 | knowledge1507-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 10 | knowledge1507-boundary-03 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 220.05 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2381.93 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
