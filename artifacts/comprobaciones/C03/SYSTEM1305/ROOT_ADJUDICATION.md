# SYSTEM1305 — adjudicación de la raíz

## SYSTEM1305 — estado vigente 2026-09-14T02:08:05.113860+00:00

Parcial: 4 aprobados, 1 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 381/742 | 361 | 0 | >=255 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 255 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); SYSTEM1305 añade 0. No se cuentan revalidaciones.

Siguiente acción: SYSTEM1305: 5 ejecutados, 4 aprobados, 1 fallidos, 0 créditos (índices []). Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/SYSTEM1305/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 82.69 s acumulados; pico GPU 3497.56 MiB; pico RAM 1627.24 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0508 | failed | Falló: la lectura se verificó pero el final no fue fiel. | Final publicado; system.status verificada; el final afirmó una versión de Windows no observada; pins intactos. |
| 1 | system1305-dev-01 | passed | Lectura verificada y respuesta fiel. | Turno ordinario: system.status de sólo lectura completada y verificada (dos lecturas coherentes); cero confirmaciones y violaciones; pins intactos. |
| 2 | system1305-dev-02 | passed | Lectura verificada y respuesta fiel. | Turno ordinario: system.status de sólo lectura completada y verificada (dos lecturas coherentes); cero confirmaciones y violaciones; pins intactos. |
| 3 | system1305-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | system1305-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 82.69 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1627.24 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
