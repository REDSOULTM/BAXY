# FILES1709 — adjudicación de la raíz

## FILES1709 — estado vigente 2026-09-16T10:35:47.848261+00:00

Parcial: 2 aprobados, 3 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 611/742 | 131 | 0 | >=495 | 10/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 495 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); FILES1709 añade 0. No se cuentan revalidaciones.

Siguiente acción: FILES1709: 6 ejecutados, 2 aprobados, 4 fallidos, 0 créditos (índices []); Abrir aplicaciones 46/54. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/FILES1709/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 153.17 s acumulados; pico GPU 3497.56 MiB; pico RAM 2392.94 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0334 | failed | Falló: la operación no se completó o no se verificó, o el final no fue fiel. | Turno ordinario: las dos operaciones se completaron y verificaron y el archivo quedó escrito; ningún final fue publicado (borradores fieles vetados por la forma de código del nombre del archivo). |
| 1 | files1709-dev-01 | failed | Falló: la operación no se completó o no se verificó, o el final no fue fiel. | Turno ordinario: la lectura se completó y verificó; la escritura no se pudo groundear y el final lo dijo honestamente. |
| 2 | files1709-dev-02 | failed | Falló: la operación no se completó o no se verificó, o el final no fue fiel. | Turno ordinario: las dos operaciones se completaron y verificaron y el archivo quedó escrito; ningún final fue publicado. |
| 3 | files1709-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | files1709-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 153.17 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2392.94 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
