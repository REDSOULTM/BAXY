# MEME2055 — adjudicación de la raíz

## MEME2055 — estado vigente 2026-09-22T09:33:20.285268+00:00

Parcial: 1 aprobados, 5 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 675/742 | 67 | 0 | >=651 | 29/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 651 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); MEME2055 añade 0. No se cuentan revalidaciones.

Siguiente acción: MEME2055: 6 ejecutados, 1 aprobados, 5 fallidos, 0 créditos (índices []). Siguiente: la presentación (H0188) y las tipadas revisadas (winget, Steam).

Evidencia: `artifacts/comprobaciones/C03/MEME2055/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 102.44 s acumulados; pico GPU 3594.57 MiB; pico RAM 2027.65 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 6; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0069 | failed | Falló: no descargó ni abrió una imagen, preguntó, o el final no la nombró. | Turno ordinario: la imagen se descargó y se abrió con el visor (verificado); el final dice que está abierta pero no nombra el archivo; pins intactos. Reparación en el commit siguiente. |
| 1 | meme2055-dev-01 | failed | Falló: no descargó ni abrió una imagen, preguntó, o el final no la nombró. | Turno ordinario: la imagen se descargó y se abrió con el visor (verificado); el final no nombra el archivo; pins intactos. |
| 2 | meme2055-dev-02 | failed | Falló: no descargó ni abrió una imagen, preguntó, o el final no la nombró. | Turno ordinario: la imagen se descargó y se abrió con el visor (verificado); el final no nombra el archivo; pins intactos. |
| 3 | meme2055-dev-03 | failed | Falló: no descargó ni abrió una imagen, preguntó, o el final no la nombró. | Turno ordinario: la imagen se descargó y se abrió con el visor (verificado); el final no nombra el archivo; pins intactos. |
| 4 | meme2055-boundary-01 | failed | Límite fallido: cero operaciones, pero la respuesta no fue fiel o útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 5 | meme2055-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 102.44 s de segmentos; pico GPU 3594.57 MiB; pico RAM 2027.65 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
