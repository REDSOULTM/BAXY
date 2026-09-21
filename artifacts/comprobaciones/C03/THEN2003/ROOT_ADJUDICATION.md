# THEN2003 — adjudicación de la raíz

## THEN2003 — estado vigente 2026-09-21T08:18:24.663658+00:00

Parcial: 2 aprobados, 6 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 653/742 | 89 | 0 | >=629 | 29/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 629 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); THEN2003 añade 0. No se cuentan revalidaciones.

Siguiente acción: THEN2003: 8 ejecutados, 2 aprobados, 6 fallidos, 0 créditos (índices []). Siguiente: SEARCH2005 y las tandas de las tipadas.

Evidencia: `artifacts/comprobaciones/C03/THEN2003/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 209.11 s acumulados; pico GPU 3492.93 MiB; pico RAM 2524.80 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 8; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0097 | failed | Falló: preguntó, no completó los dos turnos, o el final no fue fiel. | Caso de dos turnos: el primero abrió el Bloc de notas y no publicó final (los borradores «Abrí el Bloc de notas» se vetaron por la regla de estado); el segundo no corrió; pins intactos. |
| 1 | then2003-dev-01 | failed | Falló: preguntó, no completó los dos turnos, o el final no fue fiel. | Caso de dos turnos: el primero abrió el Bloc de notas y no publicó final; el segundo no corrió; pins intactos. |
| 2 | then2003-dev-02 | failed | Falló: preguntó, no completó los dos turnos, o el final no fue fiel. | Caso de dos turnos: Bloc de notas abierto y texto escrito en él (verificado), pero el final sólo repitió el texto sin decir que lo escribió; pins intactos. |
| 3 | then2003-dev-03 | failed | Falló: preguntó, no completó los dos turnos, o el final no fue fiel. | Caso de dos turnos: el primero abrió el Bloc de notas y no publicó final; el segundo no corrió; pins intactos. |
| 4 | then2003-dev-04 | failed | Falló: preguntó, no completó los dos turnos, o el final no fue fiel. | Caso de dos turnos: el primero abrió el Bloc de notas y no publicó final; el segundo no corrió; pins intactos. |
| 5 | then2003-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 6 | then2003-boundary-02 | failed | Límite fallido: cero operaciones, pero la respuesta no fue fiel o útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 7 | then2003-boundary-03 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 209.11 s de segmentos; pico GPU 3492.93 MiB; pico RAM 2524.80 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
