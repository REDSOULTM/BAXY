# APPS1497 — adjudicación de la raíz

## APPS1497 — estado vigente 2026-09-15T00:30:39.777815+00:00

Parcial: 7 aprobados, 3 fallidos, 0 sin ejecutar; 2 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 491/742 | 251 | 0 | >=365 | 4/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 363 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); APPS1497 añade 2. No se cuentan revalidaciones.

Siguiente acción: APPS1497: 10 ejecutados, 7 aprobados, 3 fallidos, 2 créditos (índices [1, 2]); Abrir aplicaciones 42/54. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/APPS1497/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 162.41 s acumulados; pico GPU 3497.56 MiB; pico RAM 1690.51 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 10; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0521 | failed | Falló: cero operaciones, pero no preguntó si abrir la candidata o negó que existiera. | Turno ordinario: cero operaciones; cero violaciones; pins intactos; la pregunta no nombró las aplicaciones candidatas (validación demasiado estricta). |
| 1 | H0386 | passed | Preguntó si abrir la aplicación candidata, nombrándola, sin abrir nada; crédito con dos variantes aprobadas del grupo. | Turno ordinario: cero operaciones; cero confirmaciones; cero violaciones; pins intactos; pregunta de aplicación fiel. |
| 2 | H0522 | passed | Preguntó si abrir la aplicación candidata, nombrándola, sin abrir nada; crédito con dos variantes aprobadas del grupo. | Turno ordinario: cero operaciones; cero confirmaciones; cero violaciones; pins intactos; pregunta de aplicación fiel. |
| 3 | H0227 | failed | Falló: cero operaciones, pero no preguntó si abrir la candidata o negó que existiera. | Turno ordinario: cero operaciones; cero violaciones; pins intactos; la pregunta repitió el nombre mal escrito en vez de la candidata. |
| 4 | H0398 | failed | Falló: cero operaciones, pero no preguntó si abrir la candidata o negó que existiera. | Turno ordinario: cero operaciones; cero violaciones; pins intactos; la pregunta repitió el nombre mal escrito en vez de la candidata. |
| 5 | apps1497-dev-01 | passed | Buscó de sólo lectura, el motor no devolvió páginas pertinentes y el final lo dijo con verdad sin inventar pronóstico. | Turno ordinario: cero operaciones; cero confirmaciones; cero violaciones; pins intactos; pregunta de aplicación fiel. |
| 6 | apps1497-dev-02 | passed | Buscó de sólo lectura, el motor no devolvió páginas pertinentes y el final lo dijo con verdad sin inventar pronóstico. | Turno ordinario: cero operaciones; cero confirmaciones; cero violaciones; pins intactos; pregunta de aplicación fiel. |
| 7 | apps1497-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 8 | apps1497-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 9 | apps1497-boundary-03 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 162.41 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1690.51 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
