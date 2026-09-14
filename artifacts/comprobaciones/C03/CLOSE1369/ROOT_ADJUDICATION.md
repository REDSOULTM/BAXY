# CLOSE1369 — adjudicación de la raíz

## CLOSE1369 — estado vigente 2026-09-14T07:15:11.035190+00:00

Parcial: 2 aprobados, 8 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 413/742 | 329 | 0 | >=287 | 4/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 287 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); CLOSE1369 añade 0. No se cuentan revalidaciones.

Siguiente acción: CLOSE1369: 10 ejecutados, 2 aprobados, 8 fallidos, 0 créditos (índices []); Cerrar aplicaciones y ventanas 11/20. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/CLOSE1369/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 201.50 s acumulados; pico GPU 3497.56 MiB; pico RAM 1947.93 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 10; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0117 | failed | Falló: no se publicó respuesta o el final no fue veraz sobre el estado de Steam. | Turno ordinario: ninguna app.close; como mucho una window.resolve de sólo lectura sobre Steam sin ventanas; cero confirmaciones y violaciones; pins intactos; Steam sin ejecutar antes y después (verificado por la raíz). |
| 1 | H0556 | failed | Falló: no se publicó respuesta o el final no fue veraz sobre el estado de Steam. | Turno ordinario: ninguna app.close; como mucho una window.resolve de sólo lectura sobre Steam sin ventanas; cero confirmaciones y violaciones; pins intactos; Steam sin ejecutar antes y después (verificado por la raíz). |
| 2 | H0677 | failed | Falló: no se publicó respuesta o el final no fue veraz sobre el estado de Steam. | Turno ordinario: ninguna app.close; como mucho una window.resolve de sólo lectura sobre Steam sin ventanas; cero confirmaciones y violaciones; pins intactos; Steam sin ejecutar antes y después (verificado por la raíz). |
| 3 | H0679 | failed | Falló: no se publicó respuesta o el final no fue veraz sobre el estado de Steam. | Turno ordinario: ninguna app.close; como mucho una window.resolve de sólo lectura sobre Steam sin ventanas; cero confirmaciones y violaciones; pins intactos; Steam sin ejecutar antes y después (verificado por la raíz). |
| 4 | close1369-dev-01 | failed | Falló: no se publicó respuesta o el final no fue veraz sobre el estado de Steam. | Turno ordinario: ninguna app.close; como mucho una window.resolve de sólo lectura sobre Steam sin ventanas; cero confirmaciones y violaciones; pins intactos; Steam sin ejecutar antes y después (verificado por la raíz). |
| 5 | close1369-dev-02 | failed | Falló: no se publicó respuesta o el final no fue veraz sobre el estado de Steam. | Turno ordinario: ninguna app.close; como mucho una window.resolve de sólo lectura sobre Steam sin ventanas; cero confirmaciones y violaciones; pins intactos; Steam sin ejecutar antes y después (verificado por la raíz). |
| 6 | close1369-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 7 | close1369-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 8 | close1369-boundary-03 | failed | Límite fallido: cero operaciones, pero la respuesta no fue fiel o útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 9 | close1369-boundary-04 | failed | Límite fallido: cero operaciones, pero la respuesta no fue fiel o útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 201.50 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1947.93 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
