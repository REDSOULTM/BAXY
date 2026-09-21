# THEN2001 — adjudicación de la raíz

## THEN2001 — estado vigente 2026-09-21T07:45:21.312659+00:00

Parcial: 5 aprobados, 3 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 653/742 | 89 | 0 | >=629 | 29/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 628 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); THEN2001 añade 1. No se cuentan revalidaciones.

Siguiente acción: THEN2001: 8 ejecutados, 5 aprobados, 3 fallidos, 1 créditos (índices [0]). Siguiente: la re-medición de «ponle hola» tras reparar el nombre de las apps de la Tienda en los finales de app.open, y SEARCH2003.

Evidencia: `artifacts/comprobaciones/C03/THEN2001/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 199.75 s acumulados; pico GPU 3492.93 MiB; pico RAM 2395.56 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 8; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0011 | passed | alarma puesta y luego cancelada por la orden sin preguntar cuál; el final dice que la canceló; crédito con dos variantes aprobadas del mismo grupo. | Caso ordinario de dos turnos (turn.playback-then): el primero pone una alarma (notification.schedule completada y verificada) y el literal la cancela (notification.cancel.latest completada y verificada) sin preguntar cuál; el final dice que la canceló; cero confirmaciones compuestas y violaciones; pins intactos. |
| 1 | H0097 | failed | Falló: preguntó, no completó los dos turnos, o el final no fue fiel. | Caso de dos turnos: el primero abrió el Bloc de notas y no publicó final (los borradores se vetaron por un nombre de catálogo); el segundo no corrió; pins intactos. |
| 2 | then2001-dev-01 | passed | alarma puesta y luego cancelada por la orden sin preguntar cuál; el final dice que la canceló. | Caso ordinario de dos turnos (turn.playback-then): el primero pone una alarma (notification.schedule completada y verificada) y el literal la cancela (notification.cancel.latest completada y verificada) sin preguntar cuál; el final dice que la canceló; cero confirmaciones compuestas y violaciones; pins intactos. |
| 3 | then2001-dev-02 | passed | alarma puesta y luego cancelada por la orden sin preguntar cuál; el final dice que la canceló. | Caso ordinario de dos turnos (turn.playback-then): el primero pone una alarma (notification.schedule completada y verificada) y el literal la cancela (notification.cancel.latest completada y verificada) sin preguntar cuál; el final dice que la canceló; cero confirmaciones compuestas y violaciones; pins intactos. |
| 4 | then2001-dev-03 | failed | Falló: preguntó, no completó los dos turnos, o el final no fue fiel. | Caso de dos turnos: el primero abrió el Bloc de notas y no publicó final; el segundo no corrió; pins intactos. |
| 5 | then2001-dev-04 | failed | Falló: preguntó, no completó los dos turnos, o el final no fue fiel. | Caso de dos turnos: el primero abrió el Bloc de notas y no publicó final; el segundo no corrió; pins intactos. |
| 6 | then2001-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 7 | then2001-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 199.75 s de segmentos; pico GPU 3492.93 MiB; pico RAM 2395.56 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
