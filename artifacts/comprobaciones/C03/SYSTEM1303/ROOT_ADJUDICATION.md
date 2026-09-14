# SYSTEM1303 — adjudicación de la raíz

## SYSTEM1303 — estado vigente 2026-09-14T02:03:53.862692+00:00

Parcial: 9 aprobados, 2 fallidos, 0 sin ejecutar; 2 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 381/742 | 361 | 0 | >=255 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 253 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); SYSTEM1303 añade 2. No se cuentan revalidaciones.

Siguiente acción: SYSTEM1303: 11 ejecutados, 9 aprobados, 2 fallidos, 2 créditos (índices [0, 1]). Siguiente: etiqueta «instalada» sobre el total (compositor) y categoría por masa abierta.

Evidencia: `artifacts/comprobaciones/C03/SYSTEM1303/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 177.00 s acumulados; pico GPU 3497.56 MiB; pico RAM 1633.38 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 11; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0219 | passed | Lectura verificada y respuesta fiel; crédito con dos variantes aprobadas. | Turno ordinario: system.status de sólo lectura completada y verificada (dos lecturas coherentes); cero confirmaciones y violaciones; pins intactos. |
| 1 | H0532 | passed | Lectura verificada y respuesta fiel; crédito con dos variantes aprobadas. | Turno ordinario: system.status de sólo lectura completada y verificada (dos lecturas coherentes); cero confirmaciones y violaciones; pins intactos. |
| 2 | H0508 | failed | Falló: la lectura se verificó pero el final etiquetó mal un valor observado. | Final publicado; system.status verificada; la etiqueta de la RAM no corresponde al valor observado; pins intactos. |
| 3 | system1303-dev-01 | passed | Lectura verificada y respuesta fiel. | Turno ordinario: system.status de sólo lectura completada y verificada (dos lecturas coherentes); cero confirmaciones y violaciones; pins intactos. |
| 4 | system1303-dev-02 | passed | Lectura verificada y respuesta fiel. | Turno ordinario: system.status de sólo lectura completada y verificada (dos lecturas coherentes); cero confirmaciones y violaciones; pins intactos. |
| 5 | system1303-dev-03 | passed | Lectura verificada y respuesta fiel. | Turno ordinario: system.status de sólo lectura completada y verificada (dos lecturas coherentes); cero confirmaciones y violaciones; pins intactos. |
| 6 | system1303-dev-04 | passed | Lectura verificada y respuesta fiel. | Turno ordinario: system.status de sólo lectura completada y verificada (dos lecturas coherentes); cero confirmaciones y violaciones; pins intactos. |
| 7 | system1303-dev-05 | passed | Lectura verificada y respuesta fiel. | Turno ordinario: system.status de sólo lectura completada y verificada (dos lecturas coherentes); cero confirmaciones y violaciones; pins intactos. |
| 8 | system1303-dev-06 | failed | Falló: la lectura se verificó pero el final etiquetó mal un valor observado. | Final publicado; system.status verificada; la etiqueta de la RAM no corresponde al valor observado; pins intactos. |
| 9 | system1303-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 10 | system1303-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 177.00 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1633.38 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
