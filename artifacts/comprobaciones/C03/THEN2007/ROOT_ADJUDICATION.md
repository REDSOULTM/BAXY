# THEN2007 — adjudicación de la raíz

## THEN2007 — estado vigente 2026-09-21T08:57:16.400208+00:00

Parcial: 6 aprobados, 2 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 654/742 | 88 | 0 | >=630 | 29/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 629 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); THEN2007 añade 1. No se cuentan revalidaciones.

Siguiente acción: THEN2007: 8 ejecutados, 6 aprobados, 2 fallidos, 1 créditos (índices [0]). Siguiente: SEARCH2005 y las tandas de las tipadas.

Evidencia: `artifacts/comprobaciones/C03/THEN2007/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 197.50 s acumulados; pico GPU 3492.93 MiB; pico RAM 2412.73 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 8; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0097 | passed | Bloc de notas abierto y luego el texto escrito en él sin preguntar dónde; el final dice que lo escribió; crédito con dos variantes aprobadas del mismo grupo. | Caso ordinario de dos turnos (turn.playback-then): el primero abre el Bloc de notas (app.open completada y verificada) y el literal escribe el texto pedido en él (input.text.type completada y verificada) sin preguntar dónde; el final dice que lo escribió; cero confirmaciones compuestas y violaciones; pins intactos. |
| 1 | then2007-dev-01 | failed | Falló: preguntó, no completó los dos turnos, o el final no fue fiel. | Caso de dos turnos: el primero abrió el Bloc de notas y no publicó final (el nombre en inglés no se aceptó); el segundo no corrió; pins intactos. |
| 2 | then2007-dev-02 | passed | Bloc de notas abierto y luego el texto escrito en él sin preguntar dónde; el final dice que lo escribió. | Caso ordinario de dos turnos (turn.playback-then): el primero abre el Bloc de notas (app.open completada y verificada) y el literal escribe el texto pedido en él (input.text.type completada y verificada) sin preguntar dónde; el final dice que lo escribió; cero confirmaciones compuestas y violaciones; pins intactos. |
| 3 | then2007-dev-03 | failed | Falló: preguntó, no completó los dos turnos, o el final no fue fiel. | Caso de dos turnos: el primero abrió el Bloc de notas y no publicó final (el nombre en inglés no se aceptó); el segundo no corrió; pins intactos. |
| 4 | then2007-dev-04 | passed | Bloc de notas abierto y luego el texto escrito en él sin preguntar dónde; el final dice que lo escribió. | Caso ordinario de dos turnos (turn.playback-then): el primero abre el Bloc de notas (app.open completada y verificada) y el literal escribe el texto pedido en él (input.text.type completada y verificada) sin preguntar dónde; el final dice que lo escribió; cero confirmaciones compuestas y violaciones; pins intactos. |
| 5 | then2007-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 6 | then2007-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 7 | then2007-boundary-03 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 197.50 s de segmentos; pico GPU 3492.93 MiB; pico RAM 2412.73 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
