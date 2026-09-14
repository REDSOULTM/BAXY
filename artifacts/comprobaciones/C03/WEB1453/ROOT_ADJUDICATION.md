# WEB1453 — adjudicación de la raíz

## WEB1453 — estado vigente 2026-09-14T19:13:03.411425+00:00

Parcial: 4 aprobados, 5 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 452/742 | 290 | 0 | >=326 | 4/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 325 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); WEB1453 añade 1. No se cuentan revalidaciones.

Siguiente acción: WEB1453: 9 ejecutados, 4 aprobados, 5 fallidos, 1 créditos (índices [0]); Información web actual 8/17. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/WEB1453/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 160.03 s acumulados; pico GPU 3497.56 MiB; pico RAM 1718.83 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 9; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0451 | passed | Buscó de sólo lectura y respondió con fidelidad a los resultados devueltos; crédito con dos variantes aprobadas del grupo. | Turno ordinario: a lo sumo una web.search de sólo lectura; cero confirmaciones; cero violaciones; pins intactos. |
| 1 | H0266 | failed | No acreditable en este transporte: la respuesta dijo con verdad que no halló resultados, pero la regla sellada de caso aprobado exige la búsqueda permitida completada y verificada, y la búsqueda falló por resultados no pertinentes. | Turno ordinario: una web.search de sólo lectura que falló por resultados no pertinentes; cero confirmaciones; cero violaciones; pins intactos; final veraz. |
| 2 | web1453-dev-01 | passed | Buscó de sólo lectura y respondió con fidelidad a los resultados devueltos. | Turno ordinario: a lo sumo una web.search de sólo lectura; cero confirmaciones; cero violaciones; pins intactos. |
| 3 | web1453-dev-02 | passed | Buscó de sólo lectura y respondió con fidelidad a los resultados devueltos. | Turno ordinario: a lo sumo una web.search de sólo lectura; cero confirmaciones; cero violaciones; pins intactos. |
| 4 | web1453-dev-03 | failed | No acreditable en este transporte: la respuesta dijo con verdad que no halló resultados, pero la regla sellada de caso aprobado exige la búsqueda permitida completada y verificada, y la búsqueda falló por resultados no pertinentes. | Turno ordinario: una web.search de sólo lectura que falló por resultados no pertinentes; cero confirmaciones; cero violaciones; pins intactos; final veraz. |
| 5 | web1453-dev-04 | failed | No acreditable en este transporte: la respuesta dijo con verdad que no halló resultados, pero la regla sellada de caso aprobado exige la búsqueda permitida completada y verificada, y la búsqueda falló por resultados no pertinentes. | Turno ordinario: una web.search de sólo lectura que falló por resultados no pertinentes; cero confirmaciones; cero violaciones; pins intactos; final veraz. |
| 6 | web1453-boundary-01 | failed | Límite fallido: la pregunta de definición se leyó como consulta de clima y una búsqueda no permitida arrancó; el runner detuvo el caso. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 7 | web1453-boundary-02 | failed | Límite fallido: la prohibición se reconoció, pero las respuestas añadieron una segunda oración y el contrato de una oración las rechazó; se publicó una pregunta de aclaración. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 8 | web1453-boundary-03 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 160.03 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1718.83 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
