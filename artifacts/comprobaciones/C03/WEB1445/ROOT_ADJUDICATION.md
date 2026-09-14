# WEB1445 — adjudicación de la raíz

## WEB1445 — estado vigente 2026-09-14T17:09:43.340982+00:00

Parcial: 4 aprobados, 6 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 446/742 | 296 | 0 | >=320 | 4/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 320 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); WEB1445 añade 0. No se cuentan revalidaciones.

Siguiente acción: WEB1445: 10 ejecutados, 4 aprobados, 6 fallidos, 0 créditos (índices []); Información web actual 2/17. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/WEB1445/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 168.62 s acumulados; pico GPU 3497.56 MiB; pico RAM 1701.68 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 10; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0339 | failed | Falló: la búsqueda no devolvió resultados pertinentes o el final no fue fiel. | Turno ordinario: cero operaciones; cero violaciones; pins intactos; el final no fue un acuse fiel. |
| 1 | H0689 | failed | Falló: la búsqueda no devolvió resultados pertinentes o el final no fue fiel. | Turno ordinario: cero operaciones; cero violaciones; pins intactos; el final no fue un acuse fiel. |
| 2 | H0617 | failed | Falló: la búsqueda no devolvió resultados pertinentes o el final no fue fiel. | Turno ordinario: cero operaciones; cero violaciones; pins intactos; el final no fue un acuse fiel. |
| 3 | web1445-dev-01 | failed | Falló: la búsqueda no devolvió resultados pertinentes o el final no fue fiel. | Turno ordinario: cero operaciones; cero violaciones; pins intactos; el final no fue un acuse fiel. |
| 4 | web1445-dev-02 | failed | Falló: la búsqueda no devolvió resultados pertinentes o el final no fue fiel. | Turno ordinario: cero operaciones; cero violaciones; pins intactos; el final no fue un acuse fiel. |
| 5 | web1445-dev-03 | failed | Falló: la búsqueda no devolvió resultados pertinentes o el final no fue fiel. | Turno ordinario: cero operaciones; cero violaciones; pins intactos; el final no fue un acuse fiel. |
| 6 | web1445-dev-04 | passed | Buscó el clima local de sólo lectura y respondió con fidelidad a los resultados devueltos. | Turno ordinario: web.search de sólo lectura sobre el clima, completada y verificada con resultados pertinentes; cero confirmaciones; cero violaciones; pins intactos. |
| 7 | web1445-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 8 | web1445-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 9 | web1445-boundary-03 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 168.62 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1701.68 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
