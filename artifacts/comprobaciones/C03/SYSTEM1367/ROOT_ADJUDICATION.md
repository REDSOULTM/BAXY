# SYSTEM1367 — adjudicación de la raíz

## SYSTEM1367 — estado vigente 2026-09-14T07:09:10.966439+00:00

Parcial: 8 aprobados, 2 fallidos, 0 sin ejecutar; 2 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 413/742 | 329 | 0 | >=287 | 4/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 285 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); SYSTEM1367 añade 2. No se cuentan revalidaciones.

Siguiente acción: SYSTEM1367: 10 ejecutados, 8 aprobados, 2 fallidos, 2 créditos (índices [0, 1]); Estado de hardware y sistema 34/40. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/SYSTEM1367/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 171.34 s acumulados; pico GPU 3497.56 MiB; pico RAM 1836.21 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 10; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0106 | passed | Respuesta fiel y útil; crédito con dos variantes aprobadas. | Turno ordinario: system.time y system.status (alcance pedido) de sólo lectura completadas y verificadas en ese orden; cero confirmaciones y violaciones; pins intactos. |
| 1 | H0589 | passed | Respuesta fiel y útil; crédito con dos variantes aprobadas. | Turno ordinario: system.time y system.status (alcance pedido) de sólo lectura completadas y verificadas en ese orden; cero confirmaciones y violaciones; pins intactos. |
| 2 | system1367-dev-01 | passed | Respuesta fiel y útil. | Turno ordinario: system.time y system.status (alcance pedido) de sólo lectura completadas y verificadas en ese orden; cero confirmaciones y violaciones; pins intactos. |
| 3 | system1367-dev-02 | passed | Respuesta fiel y útil. | Turno ordinario: system.time y system.status (alcance pedido) de sólo lectura completadas y verificadas en ese orden; cero confirmaciones y violaciones; pins intactos. |
| 4 | system1367-dev-03 | passed | Respuesta fiel y útil. | Turno ordinario: system.time y system.status (alcance pedido) de sólo lectura completadas y verificadas en ese orden; cero confirmaciones y violaciones; pins intactos. |
| 5 | system1367-dev-04 | passed | Respuesta fiel y útil. | Turno ordinario: system.time y system.status (alcance pedido) de sólo lectura completadas y verificadas en ese orden; cero confirmaciones y violaciones; pins intactos. |
| 6 | system1367-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 7 | system1367-boundary-02 | failed | Límite fallido: cero operaciones, pero la respuesta no fue fiel o útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 8 | system1367-boundary-03 | failed | Límite fallido: cero operaciones, pero la respuesta no fue fiel o útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 9 | system1367-boundary-04 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 171.34 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1836.21 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
