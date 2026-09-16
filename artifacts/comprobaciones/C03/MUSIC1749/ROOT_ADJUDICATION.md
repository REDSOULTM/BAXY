# MUSIC1749 — adjudicación de la raíz

## MUSIC1749 — estado vigente 2026-09-16T21:12:35.327335+00:00

Parcial: 5 aprobados, 4 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 627/742 | 115 | 0 | >=511 | 12/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 510 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); MUSIC1749 añade 1. No se cuentan revalidaciones.

Siguiente acción: MUSIC1749: 9 ejecutados, 5 aprobados, 4 fallidos, 1 créditos (índices [1]); Música 28/39. Siguiente: «pon música en spotify» (diálogo) y «poné rock», «tocá una canción» (lectores).

Evidencia: `artifacts/comprobaciones/C03/MUSIC1749/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 334.11 s acumulados; pico GPU 3497.56 MiB; pico RAM 2524.56 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 9; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0237 | failed | Falló: la reproducción no se verificó en el cliente de Spotify, o el final citó un título no observado o afirmó de más, o no hubo final. | Turno revisado: media.play.query propuesta, aprobada por la raíz, completada y verificada por now-playing en el cliente de Spotify (abierto y cerrado por la raíz; volumen preajustado y restaurado); sin final publicado (borradores vetados por el compositor); cero violaciones; pins intactos. |
| 1 | H0454 | passed | Reprodujo lo pedido en Spotify con revisión de la raíz y nombró lo que suena por su título observado; crédito con dos variantes aprobadas. | Turno revisado: media.play.query propuesta con proveedor spotify y la consulta pedida, aprobada por la raíz, completada y verificada por la postlectura de now-playing del cliente de Spotify (abierto por la raíz antes del caso, pausado y cerrado después; volumen preajustado y restaurado); una confirmación; cero violaciones; pins intactos. |
| 2 | H0548 | failed | Falló: la reproducción no se verificó en el cliente de Spotify, o el final citó un título no observado o afirmó de más, o no hubo final. | Turno revisado: media.play.query propuesta, aprobada por la raíz, completada y verificada por now-playing en el cliente de Spotify (abierto y cerrado por la raíz; volumen preajustado y restaurado); sin final publicado (borradores vetados por el compositor); cero violaciones; pins intactos. |
| 3 | H0282 | failed | Falló: la reproducción no se verificó en el cliente de Spotify, o el final citó un título no observado o afirmó de más, o no hubo final. | Turno revisado: media.play.query propuesta, aprobada por la raíz, completada y verificada por now-playing en el cliente de Spotify (abierto y cerrado por la raíz; volumen preajustado y restaurado); sin final publicado (borradores vetados por el compositor); cero violaciones; pins intactos. |
| 4 | H0579 | failed | Falló: la reproducción no se verificó en el cliente de Spotify, o el final citó un título no observado o afirmó de más, o no hubo final. | Turno revisado: media.play.query propuesta, aprobada por la raíz, completada y verificada por now-playing en el cliente de Spotify (abierto y cerrado por la raíz; volumen preajustado y restaurado); sin final publicado (borradores vetados por el compositor); cero violaciones; pins intactos. |
| 5 | music1749-dev-01 | passed | Reprodujo lo pedido en Spotify con revisión de la raíz y nombró lo que suena por su título observado; variante o literal sin dos pares aprobados. | Turno revisado: media.play.query propuesta con proveedor spotify y la consulta pedida, aprobada por la raíz, completada y verificada por la postlectura de now-playing del cliente de Spotify (abierto por la raíz antes del caso, pausado y cerrado después; volumen preajustado y restaurado); una confirmación; cero violaciones; pins intactos. |
| 6 | music1749-dev-02 | passed | Reprodujo lo pedido en Spotify con revisión de la raíz y nombró lo que suena por su título observado; variante o literal sin dos pares aprobados. | Turno revisado: media.play.query propuesta con proveedor spotify y la consulta pedida, aprobada por la raíz, completada y verificada por la postlectura de now-playing del cliente de Spotify (abierto por la raíz antes del caso, pausado y cerrado después; volumen preajustado y restaurado); una confirmación; cero violaciones; pins intactos. |
| 7 | music1749-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 8 | music1749-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 334.11 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2524.56 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
