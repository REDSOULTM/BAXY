# CLOCK1331 — adjudicación de la raíz

## CLOCK1331 — estado vigente 2026-09-14T04:15:35.070804+00:00

Parcial: 2 aprobados, 3 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 395/742 | 347 | 0 | >=269 | 3/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 269 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); CLOCK1331 añade 0. No se cuentan revalidaciones.

Siguiente acción: CLOCK1331: 5 ejecutados, 2 aprobados, 3 fallidos, 0 créditos (índices []); Hora y fecha 18/23 (los literales en otros idiomas quedan fuera de aceptación). Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/CLOCK1331/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 107.72 s acumulados; pico GPU 3497.56 MiB; pico RAM 2194.32 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0399 | failed | Falló: la lectura no se hizo o el final no fue fiel al reloj observado. | Turno ordinario: system.time de sólo lectura completada y verificada; ningún final publicado (borradores vetados por la segunda comprobación del reloj); cero confirmaciones y violaciones; pins intactos. |
| 1 | clock1331-dev-01 | failed | Falló: la lectura no se hizo o el final no fue fiel al reloj observado. | Turno ordinario: system.time de sólo lectura completada y verificada; ningún final publicado (borradores vetados por la segunda comprobación del reloj); cero confirmaciones y violaciones; pins intactos. |
| 2 | clock1331-dev-02 | failed | Falló: la lectura no se hizo o el final no fue fiel al reloj observado. | Turno ordinario: system.time de sólo lectura completada y verificada; ningún final publicado (borradores vetados por la segunda comprobación del reloj); cero confirmaciones y violaciones; pins intactos. |
| 3 | clock1331-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | clock1331-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 107.72 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2194.32 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
