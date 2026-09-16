# MUSIC1763 — adjudicación de la raíz

## MUSIC1763 — estado vigente 2026-09-16T23:00:16.619368+00:00

Parcial: 7 aprobados, 0 fallidos, 0 sin ejecutar; 3 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 634/742 | 108 | 0 | >=518 | 12/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 515 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); MUSIC1763 añade 3. No se cuentan revalidaciones.

Siguiente acción: MUSIC1763: 7 ejecutados, 7 aprobados, 0 fallidos, 3 créditos (índices [0, 1, 2]); Música 35/39. Siguiente: «poné rock», «reproducí…», «tocá…» (lectores) y volumen de Spotify (operación por aplicación).

Evidencia: `artifacts/comprobaciones/C03/MUSIC1763/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 226.03 s acumulados; pico GPU 3497.56 MiB; pico RAM 2544.57 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 7; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0022 | passed | Preguntó qué música poner, reprodujo con revisión lo contestado en el cliente de Spotify y lo nombró por su título observado; crédito con dos variantes aprobadas. | Caso de diálogo: primer turno con pregunta sin operar, respuesta guionizada por la raíz (un artista), media.play.query propuesta con proveedor spotify y ese artista, aprobada por la raíz, completada y verificada por la postlectura de now-playing del cliente de Spotify (abierto por la raíz antes del caso, pausado y cerrado después; volumen preajustado y restaurado); dos envíos tras el primero; cero violaciones; pins intactos. |
| 1 | H0300 | passed | Preguntó qué música poner, reprodujo con revisión lo contestado en el cliente de Spotify y lo nombró por su título observado; crédito con dos variantes aprobadas. | Caso de diálogo: primer turno con pregunta sin operar, respuesta guionizada por la raíz (un artista), media.play.query propuesta con proveedor spotify y ese artista, aprobada por la raíz, completada y verificada por la postlectura de now-playing del cliente de Spotify (abierto por la raíz antes del caso, pausado y cerrado después; volumen preajustado y restaurado); dos envíos tras el primero; cero violaciones; pins intactos. |
| 2 | H0215 | passed | Preguntó qué música poner, reprodujo con revisión lo contestado en el cliente de Spotify y lo nombró por su título observado; crédito con dos variantes aprobadas. | Caso de diálogo: primer turno con pregunta sin operar, respuesta guionizada por la raíz (un artista), media.play.query propuesta con proveedor spotify y ese artista, aprobada por la raíz, completada y verificada por la postlectura de now-playing del cliente de Spotify (abierto por la raíz antes del caso, pausado y cerrado después; volumen preajustado y restaurado); dos envíos tras el primero; cero violaciones; pins intactos. |
| 3 | music1763-dev-01 | passed | Preguntó qué música poner y reprodujo con revisión lo contestado en Spotify, nombrándolo por su título observado; variante o literal sin dos pares aprobados. | Caso de diálogo: primer turno con pregunta sin operar, respuesta guionizada por la raíz (un artista), media.play.query propuesta con proveedor spotify y ese artista, aprobada por la raíz, completada y verificada por la postlectura de now-playing del cliente de Spotify (abierto por la raíz antes del caso, pausado y cerrado después; volumen preajustado y restaurado); dos envíos tras el primero; cero violaciones; pins intactos. |
| 4 | music1763-dev-02 | passed | Preguntó qué música poner y reprodujo con revisión lo contestado en Spotify, nombrándolo por su título observado; variante o literal sin dos pares aprobados. | Caso de diálogo: primer turno con pregunta sin operar, respuesta guionizada por la raíz (un artista), media.play.query propuesta con proveedor spotify y ese artista, aprobada por la raíz, completada y verificada por la postlectura de now-playing del cliente de Spotify (abierto por la raíz antes del caso, pausado y cerrado después; volumen preajustado y restaurado); dos envíos tras el primero; cero violaciones; pins intactos. |
| 5 | music1763-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 6 | music1763-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 226.03 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2544.57 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
