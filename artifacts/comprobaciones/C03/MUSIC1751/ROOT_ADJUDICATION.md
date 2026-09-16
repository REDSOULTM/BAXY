# MUSIC1751 — adjudicación de la raíz

## MUSIC1751 — estado vigente 2026-09-16T21:27:03.908084+00:00

Parcial: 8 aprobados, 0 fallidos, 0 sin ejecutar; 4 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 631/742 | 111 | 0 | >=515 | 12/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 511 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); MUSIC1751 añade 4. No se cuentan revalidaciones.

Siguiente acción: MUSIC1751: 8 ejecutados, 8 aprobados, 0 fallidos, 4 créditos (índices [0, 1, 2, 3]); Música 32/39. Siguiente: «pon música en spotify» (diálogo) y «poné rock», «tocá una canción» (lectores).

Evidencia: `artifacts/comprobaciones/C03/MUSIC1751/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 264.23 s acumulados; pico GPU 3497.56 MiB; pico RAM 2517.82 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 8; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0237 | passed | Reprodujo lo pedido en Spotify con revisión de la raíz y nombró lo que suena por su título observado; crédito con dos variantes aprobadas. | Turno revisado: media.play.query propuesta con proveedor spotify y la consulta pedida, aprobada por la raíz, completada y verificada por la postlectura de now-playing del cliente de Spotify (abierto por la raíz antes del caso, pausado y cerrado después; volumen preajustado y restaurado); una confirmación; cero violaciones; pins intactos. |
| 1 | H0548 | passed | Reprodujo lo pedido en Spotify con revisión de la raíz y nombró lo que suena por su título observado; crédito con dos variantes aprobadas. | Turno revisado: media.play.query propuesta con proveedor spotify y la consulta pedida, aprobada por la raíz, completada y verificada por la postlectura de now-playing del cliente de Spotify (abierto por la raíz antes del caso, pausado y cerrado después; volumen preajustado y restaurado); una confirmación; cero violaciones; pins intactos. |
| 2 | H0282 | passed | Reprodujo lo pedido en Spotify con revisión de la raíz y nombró lo que suena por su título observado; crédito con dos variantes aprobadas. | Turno revisado: media.play.query propuesta con proveedor spotify y la consulta pedida, aprobada por la raíz, completada y verificada por la postlectura de now-playing del cliente de Spotify (abierto por la raíz antes del caso, pausado y cerrado después; volumen preajustado y restaurado); una confirmación; cero violaciones; pins intactos. |
| 3 | H0579 | passed | Reprodujo lo pedido en Spotify con revisión de la raíz y nombró lo que suena por su título observado; crédito con dos variantes aprobadas. | Turno revisado: media.play.query propuesta con proveedor spotify y la consulta pedida, aprobada por la raíz, completada y verificada por la postlectura de now-playing del cliente de Spotify (abierto por la raíz antes del caso, pausado y cerrado después; volumen preajustado y restaurado); una confirmación; cero violaciones; pins intactos. |
| 4 | music1751-dev-01 | passed | Reprodujo lo pedido en Spotify con revisión de la raíz y nombró lo que suena por su título observado; variante o literal sin dos pares aprobados. | Turno revisado: media.play.query propuesta con proveedor spotify y la consulta pedida, aprobada por la raíz, completada y verificada por la postlectura de now-playing del cliente de Spotify (abierto por la raíz antes del caso, pausado y cerrado después; volumen preajustado y restaurado); una confirmación; cero violaciones; pins intactos. |
| 5 | music1751-dev-02 | passed | Reprodujo lo pedido en Spotify con revisión de la raíz y nombró lo que suena por su título observado; variante o literal sin dos pares aprobados. | Turno revisado: media.play.query propuesta con proveedor spotify y la consulta pedida, aprobada por la raíz, completada y verificada por la postlectura de now-playing del cliente de Spotify (abierto por la raíz antes del caso, pausado y cerrado después; volumen preajustado y restaurado); una confirmación; cero violaciones; pins intactos. |
| 6 | music1751-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 7 | music1751-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 264.23 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2517.82 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
