# FILES1603 — adjudicación de la raíz

## FILES1603 — estado vigente 2026-09-15T19:59:50.454229+00:00

Parcial: 2 aprobados, 3 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 547/742 | 195 | 0 | >=421 | 6/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 421 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); FILES1603 añade 0. No se cuentan revalidaciones.

Siguiente acción: FILES1603: 5 ejecutados, 2 aprobados, 3 fallidos, 0 créditos (índices []); Archivos y carpetas 27/32. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/FILES1603/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 122.42 s acumulados; pico GPU 3497.56 MiB; pico RAM 2386.55 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0327 | failed | Falló: la carpeta no se movió o no se verificó, o el final no fue fiel. | Turno ordinario: la operación de papelera falló en el adaptador (movimiento entre volúmenes) y el final lo dijo con verdad; cero violaciones; pins intactos. |
| 1 | files1603-dev-01 | failed | Falló: la carpeta no se movió o no se verificó, o el final no fue fiel. | Turno ordinario: la operación de papelera falló en el adaptador y el final lo dijo con verdad; cero violaciones; pins intactos. |
| 2 | files1603-dev-02 | failed | Falló: la carpeta no se movió o no se verificó, o el final no fue fiel. | Turno ordinario: nombre ambiguo entre las carpetas conocidas; sin final; cero violaciones; pins intactos. |
| 3 | files1603-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | files1603-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 122.42 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2386.55 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
