# AUDIO1375 — adjudicación de la raíz

## AUDIO1375 — estado vigente 2026-09-14T08:04:21.991475+00:00

Parcial: 3 aprobados, 7 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 417/742 | 325 | 0 | >=291 | 4/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 291 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); AUDIO1375 añade 0. No se cuentan revalidaciones.

Siguiente acción: AUDIO1375: 10 ejecutados, 3 aprobados, 7 fallidos, 0 créditos (índices []); Audio y volumen 41/51. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/AUDIO1375/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 177.36 s acumulados; pico GPU 3497.56 MiB; pico RAM 1659.15 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 10; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0439 | failed | Falló: cero operaciones, pero no preguntó qué poner a ese nivel o adivinó el ajuste. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos; volumen y brillo intactos (verificados por la raíz). |
| 1 | H0713 | failed | Falló: cero operaciones, pero no preguntó qué poner a ese nivel o adivinó el ajuste. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos; volumen y brillo intactos (verificados por la raíz). |
| 2 | audio1375-dev-01 | failed | Falló: cero operaciones, pero no preguntó qué poner a ese nivel o adivinó el ajuste. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos; volumen y brillo intactos (verificados por la raíz). |
| 3 | audio1375-dev-02 | passed | Pregunta qué poner a ese nivel sin adivinarlo. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos; volumen y brillo intactos (verificados por la raíz). |
| 4 | audio1375-dev-03 | passed | Pregunta qué poner a ese nivel sin adivinarlo. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos; volumen y brillo intactos (verificados por la raíz). |
| 5 | audio1375-dev-04 | failed | Falló: cero operaciones, pero no preguntó qué poner a ese nivel o adivinó el ajuste. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos; volumen y brillo intactos (verificados por la raíz). |
| 6 | audio1375-boundary-01 | failed | Límite fallido: cero operaciones, pero la respuesta no fue fiel o útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos; volumen y brillo intactos (verificados por la raíz). |
| 7 | audio1375-boundary-02 | failed | Límite fallido: cero operaciones, pero la respuesta no fue fiel o útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos; volumen y brillo intactos (verificados por la raíz). |
| 8 | audio1375-boundary-03 | failed | Límite fallido: cero operaciones, pero la respuesta no fue fiel o útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos; volumen y brillo intactos (verificados por la raíz). |
| 9 | audio1375-boundary-04 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos; volumen y brillo intactos (verificados por la raíz). |

Recursos: 177.36 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1659.15 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
