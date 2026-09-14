# CLOCK1329 — adjudicación de la raíz

## CLOCK1329 — estado vigente 2026-09-14T03:58:16.508697+00:00

Parcial: 6 aprobados, 3 fallidos, 0 sin ejecutar; 2 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 395/742 | 347 | 0 | >=269 | 3/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 267 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); CLOCK1329 añade 2. No se cuentan revalidaciones.

Siguiente acción: CLOCK1329: 9 ejecutados, 6 aprobados, 3 fallidos, 2 créditos (índices [1, 2]); Hora y fecha 18/23 (los literales en otros idiomas quedan fuera de aceptación). Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/CLOCK1329/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 168.56 s acumulados; pico GPU 3497.56 MiB; pico RAM 2278.83 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 9; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0399 | failed | Falló: la lectura no se hizo o el final no fue fiel al reloj observado. | Turno ordinario: system.time de sólo lectura completada y verificada; ningún final publicado (borradores vetados por la comprobación del reloj); cero confirmaciones y violaciones; pins intactos. |
| 1 | H0054 | passed | Lectura verificada y respuesta fiel; crédito con dos variantes aprobadas. | Turno ordinario: system.time de sólo lectura completada y verificada; cero confirmaciones y violaciones; pins intactos. |
| 2 | H0312 | passed | Lectura verificada y respuesta fiel; crédito con dos variantes aprobadas. | Turno ordinario: system.time de sólo lectura completada y verificada; cero confirmaciones y violaciones; pins intactos. |
| 3 | clock1329-dev-01 | failed | Falló: la lectura no se hizo o el final no fue fiel al reloj observado. | Turno ordinario: system.time de sólo lectura completada y verificada; ningún final publicado (borradores vetados por la comprobación del reloj); cero confirmaciones y violaciones; pins intactos. |
| 4 | clock1329-dev-02 | failed | Falló: la lectura no se hizo o el final no fue fiel al reloj observado. | Turno ordinario: system.time de sólo lectura completada y verificada; ningún final publicado (borradores vetados por la comprobación del reloj); cero confirmaciones y violaciones; pins intactos. |
| 5 | clock1329-dev-03 | passed | Lectura verificada y respuesta fiel. | Turno ordinario: system.time de sólo lectura completada y verificada; cero confirmaciones y violaciones; pins intactos. |
| 6 | clock1329-dev-04 | passed | Lectura verificada y respuesta fiel. | Turno ordinario: system.time de sólo lectura completada y verificada; cero confirmaciones y violaciones; pins intactos. |
| 7 | clock1329-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 8 | clock1329-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 168.56 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2278.83 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
