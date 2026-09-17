# MUSIC1769 — adjudicación de la raíz

## MUSIC1769 — estado vigente 2026-09-17T00:02:01.832320+00:00

Parcial: 8 aprobados, 1 fallidos, 0 sin ejecutar; 2 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 636/742 | 106 | 0 | >=520 | 12/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 518 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); MUSIC1769 añade 2. No se cuentan revalidaciones.

Siguiente acción: MUSIC1769: 9 ejecutados, 8 aprobados, 1 fallidos, 2 créditos (índices [0, 2]); Música 37/39. Siguiente: volumen de Spotify (operación por aplicación) y las filas de Steam con diálogo abierto.

Evidencia: `artifacts/comprobaciones/C03/MUSIC1769/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 329.51 s acumulados; pico GPU 3497.56 MiB; pico RAM 2507.80 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 9; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0178 | passed | Preguntó qué poner y reprodujo con revisión lo contestado en Spotify, nombrando lo que suena por su título observado; crédito con dos variantes aprobadas del grupo. | Caso de diálogo: primer turno con pregunta sin operar, respuesta guionizada por la raíz (un artista), media.play.query propuesta con proveedor spotify y ese artista, aprobada por la raíz, completada y verificada por la postlectura de now-playing del cliente de Spotify (abierto por la raíz antes del caso, pausado y cerrado después; volumen preajustado y restaurado); dos envíos tras el primero; cero violaciones; pins intactos. |
| 1 | H0163 | failed | Falló: la reproducción no se verificó en el cliente de Spotify, o el final citó un título no observado, afirmó de más, o el pedido sin nombrar no preguntó qué poner, o no hubo final. | Turno revisado: media.play.query aprobada por la raíz, completada y verificada por now-playing en el cliente de Spotify (primer resultado de la búsqueda); sin final publicado (borradores vetados por el compositor ante un título observado largo); cero violaciones; pins intactos. |
| 2 | H0552 | passed | Reprodujo lo pedido en Spotify con revisión de la raíz, nombrando lo que suena por su título observado; crédito con dos variantes aprobadas del grupo. | Turno revisado: media.play.query propuesta con proveedor spotify y la consulta pedida, aprobada por la raíz, completada y verificada por la postlectura de now-playing del cliente de Spotify (abierto por la raíz antes del caso, pausado y cerrado después; volumen preajustado y restaurado); una confirmación; cero violaciones; pins intactos. |
| 3 | music1769-dev-01 | passed | Preguntó qué poner y reprodujo con revisión lo contestado en Spotify, nombrando lo que suena por su título observado; variante o literal sin dos pares aprobados. | Caso de diálogo: primer turno con pregunta sin operar, respuesta guionizada por la raíz (un artista), media.play.query propuesta con proveedor spotify y ese artista, aprobada por la raíz, completada y verificada por la postlectura de now-playing del cliente de Spotify (abierto por la raíz antes del caso, pausado y cerrado después; volumen preajustado y restaurado); dos envíos tras el primero; cero violaciones; pins intactos. |
| 4 | music1769-dev-02 | passed | Preguntó qué poner y reprodujo con revisión lo contestado en Spotify, nombrando lo que suena por su título observado; variante o literal sin dos pares aprobados. | Caso de diálogo: primer turno con pregunta sin operar, respuesta guionizada por la raíz (un artista), media.play.query propuesta con proveedor spotify y ese artista, aprobada por la raíz, completada y verificada por la postlectura de now-playing del cliente de Spotify (abierto por la raíz antes del caso, pausado y cerrado después; volumen preajustado y restaurado); dos envíos tras el primero; cero violaciones; pins intactos. |
| 5 | music1769-dev-03 | passed | Reprodujo lo pedido en Spotify con revisión de la raíz, nombrando lo que suena por su título observado; variante o literal sin dos pares aprobados. | Turno revisado: media.play.query propuesta con proveedor spotify y la consulta pedida, aprobada por la raíz, completada y verificada por la postlectura de now-playing del cliente de Spotify (abierto por la raíz antes del caso, pausado y cerrado después; volumen preajustado y restaurado); una confirmación; cero violaciones; pins intactos. |
| 6 | music1769-dev-04 | passed | Reprodujo lo pedido en Spotify con revisión de la raíz, nombrando lo que suena por su título observado; variante o literal sin dos pares aprobados. | Turno revisado: media.play.query propuesta con proveedor spotify y la consulta pedida, aprobada por la raíz, completada y verificada por la postlectura de now-playing del cliente de Spotify (abierto por la raíz antes del caso, pausado y cerrado después; volumen preajustado y restaurado); una confirmación; cero violaciones; pins intactos. |
| 7 | music1769-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 8 | music1769-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 329.51 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2507.80 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
