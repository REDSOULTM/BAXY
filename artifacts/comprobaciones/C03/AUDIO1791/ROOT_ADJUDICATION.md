# AUDIO1791 — adjudicación de la raíz

## AUDIO1791 — estado vigente 2026-09-17T03:26:08.539115+00:00

Parcial: 2 aprobados, 3 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 639/742 | 103 | 0 | >=523 | 12/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 523 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); AUDIO1791 añade 0. No se cuentan revalidaciones.

Siguiente acción: AUDIO1791: 5 ejecutados, 2 aprobados, 3 fallidos, 0 créditos (índices []); Música 37/39. Siguiente: UI1775 (Epic) sobre la misma compilación y el volumen de Spotify.

Evidencia: `artifacts/comprobaciones/C03/AUDIO1791/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 100.80 s acumulados; pico GPU 3497.56 MiB; pico RAM 1682.14 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0652 | failed | Falló: no preguntó cuánto, o el ajuste del volumen de Spotify no se verificó, o el final no dio el nivel observado, afirmó de más o no hubo final. | Caso de diálogo: pregunta sin operar; la respuesta numérica se decidió como el ajuste pero los argumentos no se completaron desde el pedido anterior y se volvió a preguntar; cero operaciones; cero violaciones; pins intactos. |
| 1 | audio1791-dev-01 | failed | Falló: no preguntó cuánto, o el ajuste del volumen de Spotify no se verificó, o el final no dio el nivel observado, afirmó de más o no hubo final. | Caso de diálogo: pregunta sin operar; la respuesta numérica se decidió como el ajuste pero los argumentos no se completaron desde el pedido anterior y se volvió a preguntar; cero operaciones; cero violaciones; pins intactos. |
| 2 | audio1791-dev-02 | failed | Falló: no preguntó cuánto, o el ajuste del volumen de Spotify no se verificó, o el final no dio el nivel observado, afirmó de más o no hubo final. | Caso de diálogo: pregunta sin operar; la respuesta numérica se decidió como el ajuste pero los argumentos no se completaron desde el pedido anterior y se volvió a preguntar; cero operaciones; cero violaciones; pins intactos. |
| 3 | audio1791-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | audio1791-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 100.80 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1682.14 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
