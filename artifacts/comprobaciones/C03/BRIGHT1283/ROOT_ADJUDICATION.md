# BRIGHT1283 — adjudicación de la raíz

## BRIGHT1283 — estado vigente 2026-09-14T00:14:16.505660+00:00

Parcial: 4 aprobados, 12 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 362/742 | 380 | 0 | >=236 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–13 septiembre: 236 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); BRIGHT1283 añade 0. No se cuentan revalidaciones.

Siguiente acción: BRIGHT1283: 16 ejecutados, 4 aprobados, 12 fallidos, 0 créditos (índices []). Siguiente: reparación causal medida (lectores deterministas de brillo que reflejan la gramática del volumen) en la tanda siguiente.

Evidencia: `artifacts/comprobaciones/C03/BRIGHT1283/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 276.20 s acumulados; pico GPU 3497.56 MiB; pico RAM 1668.87 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 16; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0171 | failed | Falló: no leyó el brillo, no preguntó la cantidad conservando la dirección, o negó/aclaró de más. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 1 | H0662 | failed | Falló: no leyó el brillo, no preguntó la cantidad conservando la dirección, o negó/aclaró de más. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 2 | H0242 | failed | Falló: no leyó el brillo, no preguntó la cantidad conservando la dirección, o negó/aclaró de más. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 3 | H0606 | failed | Falló: no leyó el brillo, no preguntó la cantidad conservando la dirección, o negó/aclaró de más. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | H0446 | failed | Falló: no leyó el brillo, no preguntó la cantidad conservando la dirección, o negó/aclaró de más. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 5 | H0494 | failed | Falló: no leyó el brillo, no preguntó la cantidad conservando la dirección, o negó/aclaró de más. | EXIT15, system.settings.status iniciada y completada (no permitida en el grupo relativo), violación unexpected_operation_started; sin final publicado |
| 6 | H0031 | failed | Falló: no leyó el brillo, no preguntó la cantidad conservando la dirección, o negó/aclaró de más. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 7 | H0496 | passed | Respuesta fiel y útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 8 | bright1283-dev-01 | passed | Respuesta fiel y útil. | Turno ordinario: system.settings.status (brightness) de sólo lectura completada y verificada (dos lecturas WMI coherentes); cero confirmaciones y violaciones; pins intactos. |
| 9 | bright1283-dev-02 | failed | Falló: no leyó el brillo, no preguntó la cantidad conservando la dirección, o negó/aclaró de más. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 10 | bright1283-dev-03 | failed | Falló: no leyó el brillo, no preguntó la cantidad conservando la dirección, o negó/aclaró de más. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 11 | bright1283-dev-04 | failed | Falló: no leyó el brillo, no preguntó la cantidad conservando la dirección, o negó/aclaró de más. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 12 | bright1283-dev-05 | failed | Falló: no leyó el brillo, no preguntó la cantidad conservando la dirección, o negó/aclaró de más. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 13 | bright1283-dev-06 | passed | Respuesta fiel y útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 14 | bright1283-boundary-01 | failed | Límite fallido: cero operaciones, pero la respuesta no fue fiel o útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 15 | bright1283-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 276.20 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1668.87 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
