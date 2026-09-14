# WEB1291 — adjudicación de la raíz

## WEB1291 — estado vigente 2026-09-14T01:09:49.606442+00:00

Parcial: 2 aprobados, 9 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 375/742 | 367 | 0 | >=249 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 249 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); WEB1291 añade 0. No se cuentan revalidaciones.

Siguiente acción: WEB1291: 11 ejecutados, 2 aprobados, 9 fallidos, 0 créditos (índices []). Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/WEB1291/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 220.48 s acumulados; pico GPU 3497.56 MiB; pico RAM 2452.72 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 11; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0380 | failed | Falló: la búsqueda no devolvió resultados pertinentes, la navegación no llegó o el final no fue fiel. | Final publicado; web.search sin resultados pertinentes (motor); pins intactos. |
| 1 | H0098 | failed | Falló: la búsqueda no devolvió resultados pertinentes, la navegación no llegó o el final no fue fiel. | Final publicado; web.search sin resultados pertinentes (motor); pins intactos. |
| 2 | H0618 | failed | Falló: la búsqueda no devolvió resultados pertinentes, la navegación no llegó o el final no fue fiel. | Final publicado; web.search sin resultados pertinentes (motor); pins intactos. |
| 3 | H0360 | failed | Falló: la búsqueda no devolvió resultados pertinentes, la navegación no llegó o el final no fue fiel. | Final publicado; la búsqueda no encontró la página (motor); sin navegación; pins intactos. |
| 4 | H0723 | failed | Falló: la búsqueda no devolvió resultados pertinentes, la navegación no llegó o el final no fue fiel. | Final publicado; la búsqueda no encontró la página (motor); sin navegación; pins intactos. |
| 5 | web1291-dev-01 | failed | Falló: la búsqueda no devolvió resultados pertinentes, la navegación no llegó o el final no fue fiel. | Final publicado; web.search sin resultados pertinentes (motor); pins intactos. |
| 6 | web1291-dev-02 | failed | Falló: la búsqueda no devolvió resultados pertinentes, la navegación no llegó o el final no fue fiel. | Final publicado; web.search sin resultados pertinentes (motor); pins intactos. |
| 7 | web1291-dev-03 | failed | Falló: la búsqueda no devolvió resultados pertinentes, la navegación no llegó o el final no fue fiel. | Final publicado; la búsqueda no encontró la página (motor); sin navegación; pins intactos. |
| 8 | web1291-dev-04 | passed | Respuesta fiel y útil. | Turno revisado: web.search de sólo lectura verificada y browser.navigate aprobada por la raíz (host store.steampowered.com), completada y verificada por URL en la sesión propia del producto; una confirmación; cero violaciones; pins intactos. |
| 9 | web1291-boundary-01 | failed | Límite fallido: cero operaciones, pero la respuesta no fue fiel o útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 10 | web1291-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 220.48 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2452.72 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
