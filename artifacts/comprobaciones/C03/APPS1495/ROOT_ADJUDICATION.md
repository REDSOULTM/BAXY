# APPS1495 — adjudicación de la raíz

## APPS1495 — estado vigente 2026-09-15T00:21:57.394491+00:00

Parcial: 3 aprobados, 7 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 489/742 | 253 | 0 | >=363 | 4/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 363 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); APPS1495 añade 0. No se cuentan revalidaciones.

Siguiente acción: APPS1495: 10 ejecutados, 3 aprobados, 7 fallidos, 0 créditos (índices []); Abrir aplicaciones 40/54. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/APPS1495/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 168.39 s acumulados; pico GPU 3497.56 MiB; pico RAM 1672.50 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 10; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0521 | failed | Falló: cero operaciones, pero no preguntó si abrir la candidata o negó que existiera. | Turno ordinario: cero operaciones; cero violaciones; pins intactos; la pregunta no nombró la aplicación candidata (fallo interno de la mente recuperado con una pregunta genérica). |
| 1 | H0386 | failed | Falló: cero operaciones, pero no preguntó si abrir la candidata o negó que existiera. | Turno ordinario: cero operaciones; cero violaciones; pins intactos; la pregunta no nombró la aplicación candidata. |
| 2 | H0522 | failed | Falló: cero operaciones, pero no preguntó si abrir la candidata o negó que existiera. | Turno ordinario: cero operaciones; cero violaciones; pins intactos; la pregunta no nombró la aplicación candidata. |
| 3 | H0227 | failed | Falló: cero operaciones, pero no preguntó si abrir la candidata o negó que existiera. | Turno ordinario: cero operaciones; cero violaciones; pins intactos; la pregunta no nombró la aplicación candidata. |
| 4 | H0398 | failed | Falló: cero operaciones, pero no preguntó si abrir la candidata o negó que existiera. | Turno ordinario: cero operaciones; cero violaciones; pins intactos; la pregunta no nombró la aplicación candidata. |
| 5 | apps1495-dev-01 | failed | Falló: cero operaciones, pero no preguntó si abrir la candidata o negó que existiera. | Turno ordinario: cero operaciones; cero violaciones; pins intactos; pregunta genérica de recuperación. |
| 6 | apps1495-dev-02 | failed | Falló: cero operaciones, pero no preguntó si abrir la candidata o negó que existiera. | Turno ordinario: cero operaciones; cero violaciones; pins intactos; la pregunta no nombró la aplicación candidata. |
| 7 | apps1495-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 8 | apps1495-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 9 | apps1495-boundary-03 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 168.39 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1672.50 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
