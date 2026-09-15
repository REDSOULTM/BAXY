# MUSIC1573 — adjudicación de la raíz

## MUSIC1573 — estado vigente 2026-09-15T16:32:29.077702+00:00

Parcial: 10 aprobados, 2 fallidos, 0 sin ejecutar; 5 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 533/742 | 209 | 0 | >=407 | 5/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 402 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); MUSIC1573 añade 5. No se cuentan revalidaciones.

Siguiente acción: MUSIC1573: 12 ejecutados, 10 aprobados, 2 fallidos, 5 créditos (índices [0, 1, 4, 5, 6]); Música 19/39. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/MUSIC1573/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 300.39 s acumulados; pico GPU 3513.33 MiB; pico RAM 2677.96 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 12; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0066 | passed | Preguntó qué música poner, reprodujo con revisión lo contestado desde YouTube en el reproductor local y lo nombró por su título observado; crédito con dos variantes aprobadas. | Caso de diálogo: primer turno con pregunta sin operar, respuesta guionizada por la raíz, media.play.youtube propuesta con la música contestada, aprobada por la raíz, reproducción verificada en el reproductor local (mpv, detenido por la raíz; volumen preajustado y restaurado); dos envíos tras el primero; cero violaciones; pins intactos. |
| 1 | H0526 | passed | Preguntó qué música poner, reprodujo con revisión lo contestado desde YouTube en el reproductor local y lo nombró por su título observado; crédito con dos variantes aprobadas. | Caso de diálogo: primer turno con pregunta sin operar, respuesta guionizada por la raíz, media.play.youtube propuesta con la música contestada, aprobada por la raíz, reproducción verificada en el reproductor local (mpv, detenido por la raíz; volumen preajustado y restaurado); dos envíos tras el primero; cero violaciones; pins intactos. |
| 2 | H0405 | failed | Falló: no preguntó, o la reproducción de lo contestado no se verificó, o el final citó un título no observado, no lo nombró, preguntó o no hubo final. | Diálogo de dos turnos: la pregunta fue fiel, la respuesta con el nombre del artista propuso y la reproducción revisada se verificó, pero el turno no produjo final (los borradores omitieron el título o dijeron «viendo», que el veto de estado no lee como reproducción); cero violaciones; pins intactos. |
| 3 | H0009 | failed | Falló: no preguntó, o la reproducción de lo contestado no se verificó, o el final citó un título no observado, no lo nombró, preguntó o no hubo final. | Diálogo de dos turnos: la pregunta fue fiel, la reproducción revisada se verificó, pero el turno no produjo final (el reintento que escribió sólo el título en inglés fue vetado por idioma y el borrador siguiente perdió el título); cero violaciones; pins intactos. |
| 4 | H0601 | passed | Preguntó qué música poner, reprodujo con revisión lo contestado desde YouTube en el reproductor local y lo nombró por su título observado; crédito con dos variantes aprobadas. | Caso de diálogo: primer turno con pregunta sin operar, respuesta guionizada por la raíz, media.play.youtube propuesta con la música contestada, aprobada por la raíz, reproducción verificada en el reproductor local (mpv, detenido por la raíz; volumen preajustado y restaurado); dos envíos tras el primero; cero violaciones; pins intactos. |
| 5 | H0656 | passed | Preguntó qué música poner, reprodujo con revisión lo contestado desde YouTube en el reproductor local y lo nombró por su título observado; crédito con dos variantes aprobadas. | Caso de diálogo: primer turno con pregunta sin operar, respuesta guionizada por la raíz, media.play.youtube propuesta con la música contestada, aprobada por la raíz, reproducción verificada en el reproductor local (mpv, detenido por la raíz; volumen preajustado y restaurado); dos envíos tras el primero; cero violaciones; pins intactos. |
| 6 | H0740 | passed | Preguntó qué música poner, reprodujo con revisión lo contestado desde YouTube en el reproductor local y lo nombró por su título observado; crédito con dos variantes aprobadas. | Caso de diálogo: primer turno con pregunta sin operar, respuesta guionizada por la raíz, media.play.youtube propuesta con la música contestada, aprobada por la raíz, reproducción verificada en el reproductor local (mpv, detenido por la raíz; volumen preajustado y restaurado); dos envíos tras el primero; cero violaciones; pins intactos. |
| 7 | music1573-dev-01 | passed | Preguntó qué música poner y reprodujo con revisión lo contestado, nombrándolo por su título observado; variante o literal sin dos pares aprobados. | Caso de diálogo: primer turno con pregunta sin operar, respuesta guionizada por la raíz, media.play.youtube propuesta con la música contestada, aprobada por la raíz, reproducción verificada en el reproductor local (mpv, detenido por la raíz; volumen preajustado y restaurado); dos envíos tras el primero; cero violaciones; pins intactos. |
| 8 | music1573-dev-02 | passed | Preguntó qué música poner y reprodujo con revisión lo contestado, nombrándolo por su título observado; variante o literal sin dos pares aprobados. | Caso de diálogo: primer turno con pregunta sin operar, respuesta guionizada por la raíz, media.play.youtube propuesta con la música contestada, aprobada por la raíz, reproducción verificada en el reproductor local (mpv, detenido por la raíz; volumen preajustado y restaurado); dos envíos tras el primero; cero violaciones; pins intactos. |
| 9 | music1573-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 10 | music1573-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 11 | music1573-boundary-03 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 300.39 s de segmentos; pico GPU 3513.33 MiB; pico RAM 2677.96 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
