# MUSIC1773 — adjudicación de la raíz

## MUSIC1773 — estado vigente 2026-09-17T01:06:43.826848+00:00

Parcial: 4 aprobados, 1 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 636/742 | 106 | 0 | >=520 | 12/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 520 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); MUSIC1773 añade 0. No se cuentan revalidaciones.

Siguiente acción: MUSIC1773: 5 ejecutados, 4 aprobados, 1 fallidos, 0 créditos (índices []); Música 37/39. Siguiente: UI1775 (Epic) sobre la misma compilación y el volumen de Spotify.

Evidencia: `artifacts/comprobaciones/C03/MUSIC1773/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 168.06 s acumulados; pico GPU 3497.56 MiB; pico RAM 2502.79 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0163 | failed | Falló: la reproducción no se verificó en el cliente de Spotify, o el final citó un título no observado, no lo nombró, afirmó de más o no hubo final. | Turno revisado: media.play.query aprobada por la raíz, completada y verificada por now-playing en el cliente de Spotify (título observado íntegro, con signos y comillas); sin final publicado (borradores vetados por parafrasear el pedido en vez de citar el título observado); cero violaciones; pins intactos. Primera invocación rechazada por la comprobación de RAM del runner y reejecutada por la raíz. |
| 1 | music1773-dev-01 | passed | Reprodujo la obra pedida en Spotify con revisión de la raíz, nombrando lo que suena por su título observado; variante o literal sin dos pares aprobados. | Turno revisado: media.play.query propuesta con proveedor spotify y la consulta pedida, aprobada por la raíz, completada y verificada por la postlectura de now-playing del cliente de Spotify (abierto por la raíz antes del caso, pausado y cerrado después; volumen preajustado y restaurado); una confirmación; cero violaciones; pins intactos. |
| 2 | music1773-dev-02 | passed | Reprodujo la obra pedida en Spotify con revisión de la raíz, nombrando lo que suena por su título observado; variante o literal sin dos pares aprobados. | Turno revisado: media.play.query propuesta con proveedor spotify y la consulta pedida, aprobada por la raíz, completada y verificada por la postlectura de now-playing del cliente de Spotify (abierto por la raíz antes del caso, pausado y cerrado después; volumen preajustado y restaurado); una confirmación; cero violaciones; pins intactos. |
| 3 | music1773-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | music1773-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 168.06 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2502.79 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
