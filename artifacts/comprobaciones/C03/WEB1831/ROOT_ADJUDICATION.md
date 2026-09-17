# WEB1831 — adjudicación de la raíz

## WEB1831 — estado vigente 2026-09-17T07:28:13.460822+00:00

Parcial: 2 aprobados, 3 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 649/742 | 93 | 0 | >=533 | 13/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 533 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); WEB1831 añade 0. No se cuentan revalidaciones.

Siguiente acción: WEB1831: 5 ejecutados, 2 aprobados, 3 fallidos, 0 créditos (índices []); Información web actual 16/17. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/WEB1831/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 92.44 s acumulados; pico GPU 3497.56 MiB; pico RAM 1701.96 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0060 | failed | Falló: la operación no se completó o no se verificó, o el final no fue fiel. | Turno ordinario: web.search con la pregunta de la persona como consulta terminó sin resultados pertinentes (el motor público devuelve páginas ajenas a una consulta con forma de pregunta); el final dijo con verdad que no pudo investigar; sin utilidad. |
| 1 | web1831-dev-01 | failed | Falló: la operación no se completó o no se verificó, o el final no fue fiel. | Turno ordinario: web.search con la pregunta de la persona como consulta terminó sin resultados pertinentes; el final dijo con verdad que no pudo investigar; sin utilidad. |
| 2 | web1831-dev-02 | failed | Falló: la operación no se completó o no se verificó, o el final no fue fiel. | Turno ordinario: web.search con la pregunta de la persona como consulta terminó sin resultados pertinentes; el final dijo con verdad que no pudo investigar; sin utilidad. |
| 3 | web1831-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | web1831-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 92.44 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1701.96 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
