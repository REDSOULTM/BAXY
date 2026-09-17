# MUSIC1829 — adjudicación de la raíz

## MUSIC1829 — estado vigente 2026-09-17T07:17:08.710957+00:00

Parcial: 5 aprobados, 0 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 649/742 | 93 | 0 | >=533 | 13/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 532 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); MUSIC1829 añade 1. No se cuentan revalidaciones.

Siguiente acción: MUSIC1829: 5 ejecutados, 5 aprobados, 0 fallidos, 1 créditos (índices [0]); Música 39/39. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/MUSIC1829/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 100.83 s acumulados; pico GPU 3497.56 MiB; pico RAM 2522.39 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0352 | passed | Preguntó qué música y abrió en el navegador nombrado la búsqueda de YouTube de lo contestado, aprobada por la raíz y verificada por la postlectura de la URL; crédito con dos variantes aprobadas. | Caso de diálogo: primer turno con pregunta sin operar, respuesta guionizada por la raíz (una música), browser.navigate.named propuesta al navegador nombrado con la URL de resultados de YouTube, aprobada por la raíz, completada y verificada por la postlectura CDP; un envío y una revisión; cero violaciones; pins intactos; el perfil del navegador del producto se cierra al terminar. |
| 1 | music1829-dev-01 | passed | Preguntó qué música y abrió en el navegador nombrado la búsqueda de YouTube de lo contestado, aprobada por la raíz y verificada por la postlectura de la URL; variante o literal sin dos pares aprobados. | Caso de diálogo: primer turno con pregunta sin operar, respuesta guionizada por la raíz (una música), browser.navigate.named propuesta al navegador nombrado con la URL de resultados de YouTube, aprobada por la raíz, completada y verificada por la postlectura CDP; un envío y una revisión; cero violaciones; pins intactos; el perfil del navegador del producto se cierra al terminar. |
| 2 | music1829-dev-02 | passed | Preguntó qué música y abrió en el navegador nombrado la búsqueda de YouTube de lo contestado, aprobada por la raíz y verificada por la postlectura de la URL; variante o literal sin dos pares aprobados. | Caso de diálogo: primer turno con pregunta sin operar, respuesta guionizada por la raíz (una música), browser.navigate.named propuesta al navegador nombrado con la URL de resultados de YouTube, aprobada por la raíz, completada y verificada por la postlectura CDP; un envío y una revisión; cero violaciones; pins intactos; el perfil del navegador del producto se cierra al terminar. |
| 3 | music1829-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | music1829-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 100.83 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2522.39 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
