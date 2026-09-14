# WEB1449 — adjudicación de la raíz

## WEB1449 — estado vigente 2026-09-14T17:43:10.722943+00:00

Parcial: 9 aprobados, 1 fallidos, 0 sin ejecutar; 3 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 449/742 | 293 | 0 | >=323 | 4/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 320 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); WEB1449 añade 3. No se cuentan revalidaciones.

Siguiente acción: WEB1449: 10 ejecutados, 9 aprobados, 1 fallidos, 3 créditos (índices [0, 1, 2]); Información web actual 5/17. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/WEB1449/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 201.06 s acumulados; pico GPU 3497.56 MiB; pico RAM 2381.68 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 10; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0339 | passed | Buscó el clima local de sólo lectura y respondió con fidelidad a los resultados devueltos; crédito con dos variantes aprobadas. | Turno ordinario: web.search de sólo lectura sobre el clima, completada y verificada con resultados pertinentes; cero confirmaciones; cero violaciones; pins intactos. |
| 1 | H0689 | passed | Buscó el clima local de sólo lectura y respondió con fidelidad a los resultados devueltos; crédito con dos variantes aprobadas. | Turno ordinario: web.search de sólo lectura sobre el clima, completada y verificada con resultados pertinentes; cero confirmaciones; cero violaciones; pins intactos. |
| 2 | H0617 | passed | Buscó el clima local de sólo lectura y respondió con fidelidad a los resultados devueltos; crédito con dos variantes aprobadas. | Turno ordinario: web.search de sólo lectura sobre el clima, completada y verificada con resultados pertinentes; cero confirmaciones; cero violaciones; pins intactos. |
| 3 | web1449-dev-01 | failed | Falló: la búsqueda verificó páginas de pronóstico, pero la composición se cortó por el presupuesto de tokens y la App rechazó el borrador; ningún final visible. | Turno ordinario: una web.search de sólo lectura completada y verificada; cero confirmaciones; cero violaciones; pins intactos; ningún final visible (composición rechazada por la App). |
| 4 | web1449-dev-02 | passed | Buscó el clima local de sólo lectura y respondió con fidelidad a los resultados devueltos. | Turno ordinario: web.search de sólo lectura sobre el clima, completada y verificada con resultados pertinentes; cero confirmaciones; cero violaciones; pins intactos. |
| 5 | web1449-dev-03 | passed | Buscó el clima local de sólo lectura y respondió con fidelidad a los resultados devueltos. | Turno ordinario: web.search de sólo lectura sobre el clima, completada y verificada con resultados pertinentes; cero confirmaciones; cero violaciones; pins intactos. |
| 6 | web1449-dev-04 | passed | Buscó el clima local de sólo lectura y respondió con fidelidad a los resultados devueltos. | Turno ordinario: web.search de sólo lectura sobre el clima, completada y verificada con resultados pertinentes; cero confirmaciones; cero violaciones; pins intactos. |
| 7 | web1449-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 8 | web1449-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 9 | web1449-boundary-03 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 201.06 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2381.68 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
