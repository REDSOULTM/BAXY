# BRIGHT1285 — adjudicación de la raíz

## BRIGHT1285 — estado vigente 2026-09-14T00:24:31.353185+00:00

Parcial: 14 aprobados, 2 fallidos, 0 sin ejecutar; 7 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 369/742 | 373 | 0 | >=243 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–13 septiembre: 236 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); BRIGHT1285 añade 7. No se cuentan revalidaciones.

Siguiente acción: BRIGHT1285: 16 ejecutados, 14 aprobados, 2 fallidos, 7 créditos (índices [0, 1, 2, 3, 4, 5, 6]). Siguiente: niveles absolutos del brillo como turno revisado (system.settings.set, confirmación); luego categoría por masa abierta.

Evidencia: `artifacts/comprobaciones/C03/BRIGHT1285/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 252.02 s acumulados; pico GPU 3497.56 MiB; pico RAM 1638.95 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 16; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0171 | passed | Respuesta fiel y útil; crédito con dos variantes aprobadas. | Turno ordinario: system.settings.status (brightness) de sólo lectura completada y verificada (dos lecturas WMI coherentes); cero confirmaciones y violaciones; pins intactos. |
| 1 | H0662 | passed | Respuesta fiel y útil; crédito con dos variantes aprobadas. | Turno ordinario: system.settings.status (brightness) de sólo lectura completada y verificada (dos lecturas WMI coherentes); cero confirmaciones y violaciones; pins intactos. |
| 2 | H0242 | passed | Respuesta fiel y útil; crédito con dos variantes aprobadas. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 3 | H0606 | passed | Respuesta fiel y útil; crédito con dos variantes aprobadas. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | H0446 | passed | Respuesta fiel y útil; crédito con dos variantes aprobadas. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 5 | H0494 | passed | Respuesta fiel y útil; crédito con dos variantes aprobadas. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 6 | H0031 | passed | Respuesta fiel y útil; crédito con dos variantes aprobadas. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 7 | H0496 | passed | Respuesta fiel y útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 8 | bright1285-dev-01 | passed | Respuesta fiel y útil. | Turno ordinario: system.settings.status (brightness) de sólo lectura completada y verificada (dos lecturas WMI coherentes); cero confirmaciones y violaciones; pins intactos. |
| 9 | bright1285-dev-02 | passed | Respuesta fiel y útil. | Turno ordinario: system.settings.status (brightness) de sólo lectura completada y verificada (dos lecturas WMI coherentes); cero confirmaciones y violaciones; pins intactos. |
| 10 | bright1285-dev-03 | passed | Respuesta fiel y útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 11 | bright1285-dev-04 | passed | Respuesta fiel y útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 12 | bright1285-dev-05 | failed | Falló: no leyó el brillo, no preguntó la cantidad conservando la dirección, o negó/aclaró de más. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 13 | bright1285-dev-06 | passed | Respuesta fiel y útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 14 | bright1285-boundary-01 | failed | Límite fallido: cero operaciones, pero la respuesta no fue fiel o útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 15 | bright1285-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 252.02 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1638.95 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
