# EXPLORER2071 — adjudicación de la raíz

## EXPLORER2071 — estado vigente 2026-09-22T12:51:29.254920+00:00

Parcial: 2 aprobados, 4 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 677/742 | 65 | 0 | >=653 | 29/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 653 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); EXPLORER2071 añade 0. No se cuentan revalidaciones.

Siguiente acción: EXPLORER2071: 6 ejecutados, 2 aprobados, 4 fallidos, 0 créditos (índices []). Siguiente: las tipadas de red (modo avión, wifi de casa) y las de descarga.

Evidencia: `artifacts/comprobaciones/C03/EXPLORER2071/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 129.27 s acumulados; pico GPU 3485.56 MiB; pico RAM 2401.50 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 6; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0701 | failed | Falló: no contó, preguntó cuál carpeta, o el final dijo otra cantidad que la leída. | Turno ordinario: el conteo de la carpeta en primer plano se leyó y se verificó; el final que la nombra no se pudo publicar porque el nombre observado se leyó como código interno; pins intactos. Reparación en el commit siguiente. |
| 1 | explorer2071-dev-01 | failed | Falló: no contó, preguntó cuál carpeta, o el final dijo otra cantidad que la leída. | Turno ordinario: el conteo se verificó; el final que nombra la carpeta no se pudo publicar; pins intactos. |
| 2 | explorer2071-dev-02 | failed | Falló: no contó, preguntó cuál carpeta, o el final dijo otra cantidad que la leída. | Turno ordinario: el conteo se verificó; el final que nombra la carpeta no se pudo publicar; pins intactos. |
| 3 | explorer2071-dev-03 | failed | Falló: no contó, preguntó cuál carpeta, o el final dijo otra cantidad que la leída. | Turno ordinario: el conteo se verificó; el final que nombra la carpeta no se pudo publicar; pins intactos. |
| 4 | explorer2071-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 5 | explorer2071-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 129.27 s de segmentos; pico GPU 3485.56 MiB; pico RAM 2401.50 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
