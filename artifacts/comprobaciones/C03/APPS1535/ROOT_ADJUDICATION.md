# APPS1535 — adjudicación de la raíz

## APPS1535 — estado vigente 2026-09-15T03:28:40.183089+00:00

Parcial: 3 aprobados, 3 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 515/742 | 227 | 0 | >=389 | 4/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 389 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); APPS1535 añade 0. No se cuentan revalidaciones.

Siguiente acción: APPS1535: 6 ejecutados, 3 aprobados, 3 fallidos, 0 créditos (índices []); Abrir aplicaciones 45/54. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/APPS1535/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 100.39 s acumulados; pico GPU 3497.56 MiB; pico RAM 1653.64 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 6; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0249 | failed | Falló: el final no dijo que no encuentra ni puede abrir ese nombre nombrándolo (el literal recibió la respuesta genérica de fuera de ámbito; las variantes preguntaron si abrir un nombre que no existe). | Turno ordinario: cero operaciones; cero violaciones; pins intactos; el final no dijo que no encuentra ese nombre. |
| 1 | apps1535-dev-01 | failed | Falló: el final no dijo que no encuentra ni puede abrir ese nombre nombrándolo (el literal recibió la respuesta genérica de fuera de ámbito; las variantes preguntaron si abrir un nombre que no existe). | Turno ordinario: cero operaciones; cero violaciones; pins intactos; el final no dijo que no encuentra ese nombre. |
| 2 | apps1535-dev-02 | failed | Falló: el final no dijo que no encuentra ni puede abrir ese nombre nombrándolo (el literal recibió la respuesta genérica de fuera de ámbito; las variantes preguntaron si abrir un nombre que no existe). | Turno ordinario: cero operaciones; cero violaciones; pins intactos; el final no dijo que no encuentra ese nombre. |
| 3 | apps1535-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | apps1535-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 5 | apps1535-boundary-03 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 100.39 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1653.64 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
