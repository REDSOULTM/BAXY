# MUSIC1747 — adjudicación de la raíz

## MUSIC1747 — estado vigente 2026-09-16T20:57:15.433211+00:00

Parcial: 2 aprobados, 7 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 626/742 | 116 | 0 | >=510 | 12/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 510 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); MUSIC1747 añade 0. No se cuentan revalidaciones.

Siguiente acción: MUSIC1747: 9 ejecutados, 2 aprobados, 7 fallidos, 0 créditos (índices []); Música 27/39. Siguiente: «pon música en spotify» (diálogo) y «poné rock», «tocá una canción» (lectores).

Evidencia: `artifacts/comprobaciones/C03/MUSIC1747/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 372.16 s acumulados; pico GPU 3497.56 MiB; pico RAM 2529.64 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 9; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0237 | failed | Falló: la reproducción no se verificó en el cliente de Spotify, o el final citó un título no observado o afirmó de más, o no hubo final. | Turno revisado: media.play.query propuesta, aprobada por la raíz, completada y verificada por now-playing en el cliente de Spotify (abierto y cerrado por la raíz; volumen preajustado y restaurado); sin final publicado (todos los borradores vetados por el compositor); cero violaciones; pins intactos. |
| 1 | H0454 | failed | Falló: la reproducción no se verificó en el cliente de Spotify, o el final citó un título no observado o afirmó de más, o no hubo final. | Turno revisado: media.play.query propuesta, aprobada por la raíz, completada y verificada por now-playing en el cliente de Spotify (abierto y cerrado por la raíz; volumen preajustado y restaurado); sin final publicado (todos los borradores vetados por el compositor); cero violaciones; pins intactos. |
| 2 | H0548 | failed | Falló: la reproducción no se verificó en el cliente de Spotify, o el final citó un título no observado o afirmó de más, o no hubo final. | Turno revisado: media.play.query propuesta, aprobada por la raíz, completada y verificada por now-playing en el cliente de Spotify (abierto y cerrado por la raíz; volumen preajustado y restaurado); sin final publicado (todos los borradores vetados por el compositor); cero violaciones; pins intactos. |
| 3 | H0282 | failed | Falló: la reproducción no se verificó en el cliente de Spotify, o el final citó un título no observado o afirmó de más, o no hubo final. | Turno revisado: media.play.query propuesta, aprobada por la raíz, completada y verificada por now-playing en el cliente de Spotify (abierto y cerrado por la raíz; volumen preajustado y restaurado); sin final publicado (todos los borradores vetados por el compositor); cero violaciones; pins intactos. |
| 4 | H0579 | failed | Falló: la reproducción no se verificó en el cliente de Spotify, o el final citó un título no observado o afirmó de más, o no hubo final. | Turno revisado: media.play.query propuesta, aprobada por la raíz, completada y verificada por now-playing en el cliente de Spotify (abierto y cerrado por la raíz; volumen preajustado y restaurado); sin final publicado (todos los borradores vetados por el compositor); cero violaciones; pins intactos. |
| 5 | music1747-dev-01 | failed | Falló: la reproducción no se verificó en el cliente de Spotify, o el final citó un título no observado o afirmó de más, o no hubo final. | Turno revisado: media.play.query propuesta, aprobada por la raíz, completada y verificada por now-playing en el cliente de Spotify (abierto y cerrado por la raíz; volumen preajustado y restaurado); sin final publicado (todos los borradores vetados por el compositor); cero violaciones; pins intactos. |
| 6 | music1747-dev-02 | failed | Falló: la reproducción no se verificó en el cliente de Spotify, o el final citó un título no observado o afirmó de más, o no hubo final. | Turno revisado: media.play.query propuesta, aprobada por la raíz, completada y verificada por now-playing en el cliente de Spotify (abierto y cerrado por la raíz; volumen preajustado y restaurado); sin final publicado (todos los borradores vetados por el compositor); cero violaciones; pins intactos. |
| 7 | music1747-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 8 | music1747-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 372.16 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2529.64 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
