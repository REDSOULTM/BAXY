# WEB1467 — adjudicación de la raíz

## WEB1467 — estado vigente 2026-09-14T21:22:50.096920+00:00

Parcial: 10 aprobados, 2 fallidos, 0 sin ejecutar; 2 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 474/742 | 268 | 0 | >=348 | 4/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 346 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); WEB1467 añade 2. No se cuentan revalidaciones.

Siguiente acción: WEB1467: 12 ejecutados, 10 aprobados, 2 fallidos, 2 créditos (índices [0, 1]); Navegación y búsqueda web 31/46. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/WEB1467/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 230.25 s acumulados; pico GPU 3497.56 MiB; pico RAM 2310.75 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 12; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0098 | passed | Buscó de sólo lectura, el motor no devolvió páginas pertinentes y el final lo dijo con verdad sin inventar pronóstico; crédito con dos variantes aprobadas del grupo (fallo honesto sellado). | Turno ordinario: una web.search de sólo lectura que terminó fallida por resultados no pertinentes (fallo honesto sellado); cero confirmaciones; cero violaciones; pins intactos; final veraz. |
| 1 | H0380 | passed | Buscó de sólo lectura, el motor no devolvió páginas pertinentes y el final lo dijo con verdad sin inventar pronóstico; crédito con dos variantes aprobadas del grupo (fallo honesto sellado). | Turno ordinario: una web.search de sólo lectura que terminó fallida por resultados no pertinentes (fallo honesto sellado); cero confirmaciones; cero violaciones; pins intactos; final veraz. |
| 2 | H0618 | failed | Falló: la búsqueda no devolvió resultados pertinentes y el final lo dijo, pero sin nombrar el tema pedido. | Turno ordinario: cero operaciones; cero violaciones; pins intactos; el final no fue un acuse fiel. |
| 3 | H0360 | passed | Buscó de sólo lectura, el motor no devolvió páginas pertinentes y el final lo dijo con verdad sin inventar pronóstico. | Turno ordinario: una web.search de sólo lectura que terminó fallida por resultados no pertinentes (fallo honesto sellado); cero confirmaciones; cero violaciones; pins intactos; final veraz. |
| 4 | H0723 | passed | Buscó de sólo lectura, el motor no devolvió páginas pertinentes y el final lo dijo con verdad sin inventar pronóstico. | Turno ordinario: una web.search de sólo lectura que terminó fallida por resultados no pertinentes (fallo honesto sellado); cero confirmaciones; cero violaciones; pins intactos; final veraz. |
| 5 | web1467-dev-01 | passed | Buscó de sólo lectura, el motor no devolvió páginas pertinentes y el final lo dijo con verdad sin inventar pronóstico. | Turno ordinario: una web.search de sólo lectura que terminó fallida por resultados no pertinentes (fallo honesto sellado); cero confirmaciones; cero violaciones; pins intactos; final veraz. |
| 6 | web1467-dev-02 | passed | Buscó de sólo lectura, el motor no devolvió páginas pertinentes y el final lo dijo con verdad sin inventar pronóstico. | Turno ordinario: una web.search de sólo lectura que terminó fallida por resultados no pertinentes (fallo honesto sellado); cero confirmaciones; cero violaciones; pins intactos; final veraz. |
| 7 | web1467-dev-03 | failed | Falló en este transporte: el motor devolvió la página pedida y el producto pidió confirmar la navegación, que un turno ordinario no admite. | Turno ordinario: web.search verificada con la página pedida y pregunta de confirmación de navegación que el transporte no admite; cero confirmaciones; pins intactos. |
| 8 | web1467-dev-04 | passed | Buscó de sólo lectura, el motor no devolvió páginas pertinentes y el final lo dijo con verdad sin inventar pronóstico. | Turno ordinario: una web.search de sólo lectura que terminó fallida por resultados no pertinentes (fallo honesto sellado); cero confirmaciones; cero violaciones; pins intactos; final veraz. |
| 9 | web1467-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 10 | web1467-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 11 | web1467-boundary-03 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 230.25 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2310.75 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
