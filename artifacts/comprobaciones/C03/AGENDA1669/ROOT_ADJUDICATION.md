# AGENDA1669 — adjudicación de la raíz

## AGENDA1669 — estado vigente 2026-09-16T04:12:17.972552+00:00

Parcial: 8 aprobados, 0 fallidos, 0 sin ejecutar; 2 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 600/742 | 142 | 0 | >=474 | 7/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 472 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); AGENDA1669 añade 2. No se cuentan revalidaciones.

Siguiente acción: AGENDA1669: 6 ejecutados, 8 aprobados, -2 fallidos, 2 créditos (índices [0, 1]); Abrir aplicaciones 48/54. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/AGENDA1669/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 187.06 s acumulados; pico GPU 3497.56 MiB; pico RAM 2523.89 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 8; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0660 | passed | Lectura notification.list completada y verificada; el final dijo lo observado sin inventar citas; crédito con dos variantes aprobadas del mismo grupo. | Turno ordinario: exactamente una notification.list de sólo lectura completada y verificada; el final dice lo observado; cero confirmaciones y violaciones; pins intactos. |
| 1 | H0666 | passed | Efecto sin operación en el catálogo: el final dijo llanamente el límite nombrando el pedido, sin operaciones; crédito con dos variantes aprobadas del mismo grupo. | Turno ordinario: cero operaciones; el final dice llanamente el límite nombrando el pedido; cero confirmaciones y violaciones; pins intactos. |
| 2 | agenda1669-dev-01 | passed | Lectura notification.list completada y verificada; el final dijo lo observado sin inventar citas. | Turno ordinario: exactamente una notification.list de sólo lectura completada y verificada; el final dice lo observado; cero confirmaciones y violaciones; pins intactos. |
| 3 | agenda1669-dev-02 | passed | Lectura notification.list completada y verificada; el final dijo lo observado sin inventar citas. | Turno ordinario: exactamente una notification.list de sólo lectura completada y verificada; el final dice lo observado; cero confirmaciones y violaciones; pins intactos. |
| 4 | agenda1669-dev-03 | passed | Efecto sin operación en el catálogo: el final dijo llanamente el límite nombrando el pedido, sin operaciones. | Turno ordinario: cero operaciones; el final dice llanamente el límite nombrando el pedido; cero confirmaciones y violaciones; pins intactos. |
| 5 | agenda1669-dev-04 | passed | Efecto sin operación en el catálogo: el final dijo llanamente el límite nombrando el pedido, sin operaciones. | Turno ordinario: cero operaciones; el final dice llanamente el límite nombrando el pedido; cero confirmaciones y violaciones; pins intactos. |
| 6 | agenda1669-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 7 | agenda1669-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 187.06 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2523.89 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
