# APPS1607 — adjudicación de la raíz

## APPS1607 — estado vigente 2026-09-15T20:34:57.741686+00:00

Parcial: 1 aprobados, 5 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 548/742 | 194 | 0 | >=422 | 6/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 422 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); APPS1607 añade 0. No se cuentan revalidaciones.

Siguiente acción: APPS1607: 6 ejecutados, 1 aprobados, 5 fallidos, 0 créditos (índices []); Abrir aplicaciones 46/54. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/APPS1607/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 114.88 s acumulados; pico GPU 3497.56 MiB; pico RAM 1662.45 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 6; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0487 | failed | Falló: Steam no se abrió o no se verificó, o el final no fue fiel. | Turno ordinario: la apertura no se verificó (la ventana pertenece a un proceso auxiliar de Steam) y el final no fue fiel; cero violaciones; pins intactos. |
| 1 | H0544 | failed | Falló: Steam no se abrió o no se verificó, o el final no fue fiel. | Turno ordinario: la apertura no se verificó (ventana del proceso auxiliar) y el final lo dijo con verdad; cero violaciones; pins intactos. |
| 2 | apps1607-dev-01 | failed | Falló: Steam no se abrió o no se verificó, o el final no fue fiel. | Turno ordinario: la apertura no se verificó y el final lo dijo con verdad; cero violaciones; pins intactos. |
| 3 | apps1607-dev-02 | failed | Falló: Steam no se abrió o no se verificó, o el final no fue fiel. | Turno ordinario: la apertura no se verificó y el final lo dijo con verdad; cero violaciones; pins intactos. |
| 4 | apps1607-boundary-01 | failed | Límite fallido: cero operaciones, pero la respuesta no fue fiel o útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 5 | apps1607-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 114.88 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1662.45 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
