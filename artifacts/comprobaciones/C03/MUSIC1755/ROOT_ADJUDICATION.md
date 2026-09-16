# MUSIC1755 — adjudicación de la raíz

## MUSIC1755 — estado vigente 2026-09-16T22:06:23.447497+00:00

Parcial: 4 aprobados, 3 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 631/742 | 111 | 0 | >=515 | 12/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 515 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); MUSIC1755 añade 0. No se cuentan revalidaciones.

Siguiente acción: MUSIC1755: 7 ejecutados, 4 aprobados, 3 fallidos, 0 créditos (índices []); Música 32/39. Siguiente: «poné rock», «reproducí…», «tocá…» (lectores) y volumen de Spotify (operación por aplicación).

Evidencia: `artifacts/comprobaciones/C03/MUSIC1755/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 238.19 s acumulados; pico GPU 3497.56 MiB; pico RAM 2547.16 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 7; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0022 | failed | Falló: no preguntó qué poner, o la reproducción de lo contestado no se verificó en Spotify, o el final citó un título no observado, afirmó de más o no hubo final. | Caso de diálogo: pregunta en el primer turno, respuesta guionizada por la raíz, media.play.query aprobada por la raíz pero no verificada en el cliente de Spotify (reproducir pulsado sin que empezara a sonar a tiempo); final de fallo sin causa; cero violaciones; pins intactos. |
| 1 | H0300 | passed | Preguntó qué música poner y reprodujo con revisión lo contestado en Spotify, nombrándolo por su título observado; variante o literal sin dos pares aprobados. | Caso de diálogo: primer turno con pregunta sin operar, respuesta guionizada por la raíz (un artista), media.play.query propuesta con proveedor spotify y ese artista, aprobada por la raíz, completada y verificada por la postlectura de now-playing del cliente de Spotify (abierto por la raíz antes del caso, pausado y cerrado después; volumen preajustado y restaurado); dos envíos tras el primero; cero violaciones; pins intactos. |
| 2 | H0215 | failed | Falló: no preguntó qué poner, o la reproducción de lo contestado no se verificó en Spotify, o el final citó un título no observado, afirmó de más o no hubo final. | Caso de diálogo: pregunta en el primer turno, respuesta guionizada, media.play.query aprobada por la raíz pero fallida en el cliente de Spotify (ningún resultado a tiempo); final de fallo sin causa; cero violaciones; pins intactos. |
| 3 | music1755-dev-01 | passed | Preguntó qué música poner y reprodujo con revisión lo contestado en Spotify, nombrándolo por su título observado; variante o literal sin dos pares aprobados. | Caso de diálogo: primer turno con pregunta sin operar, respuesta guionizada por la raíz (un artista), media.play.query propuesta con proveedor spotify y ese artista, aprobada por la raíz, completada y verificada por la postlectura de now-playing del cliente de Spotify (abierto por la raíz antes del caso, pausado y cerrado después; volumen preajustado y restaurado); dos envíos tras el primero; cero violaciones; pins intactos. |
| 4 | music1755-dev-02 | failed | Falló: no preguntó qué poner, o la reproducción de lo contestado no se verificó en Spotify, o el final citó un título no observado, afirmó de más o no hubo final. | Caso de diálogo: pregunta en inglés, respuesta guionizada, media.play.query aprobada, completada y verificada en el cliente de Spotify; final en español con una opinión añadida; cero violaciones; pins intactos. |
| 5 | music1755-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 6 | music1755-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 238.19 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2547.16 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
