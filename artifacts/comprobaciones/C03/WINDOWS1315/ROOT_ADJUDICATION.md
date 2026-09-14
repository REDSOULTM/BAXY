# WINDOWS1315 — adjudicación de la raíz

## WINDOWS1315 — estado vigente 2026-09-14T02:43:58.229233+00:00

Parcial: 2 aprobados, 3 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 386/742 | 356 | 0 | >=260 | 1/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 260 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); WINDOWS1315 añade 0. No se cuentan revalidaciones.

Siguiente acción: WINDOWS1315: 5 ejecutados, 2 aprobados, 3 fallidos, 0 créditos (índices []); categoría Estado de ventanas y aplicaciones 13/14. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/WINDOWS1315/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 126.11 s acumulados; pico GPU 3497.56 MiB; pico RAM 2373.95 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0419 | failed | Falló: la lectura no se hizo o el final no fue fiel a las ventanas observadas. | Turno ordinario: window.resolve de inventario completada y verificada; ningún final publicado (borradores vetados por la guardia de página parcial); cero confirmaciones y violaciones; pins intactos. |
| 1 | windows1315-dev-01 | failed | Falló: la lectura no se hizo o el final no fue fiel a las ventanas observadas. | Turno ordinario: window.resolve de inventario completada y verificada; ningún final publicado (borradores vetados por la guardia de página parcial); cero confirmaciones y violaciones; pins intactos. |
| 2 | windows1315-dev-02 | failed | Falló: la lectura no se hizo o el final no fue fiel a las ventanas observadas. | Turno ordinario: window.resolve de inventario completada y verificada; ningún final publicado (borradores vetados por la guardia de página parcial); cero confirmaciones y violaciones; pins intactos. |
| 3 | windows1315-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | windows1315-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 126.11 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2373.95 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
