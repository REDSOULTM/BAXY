# APPS1551 — adjudicación de la raíz

## APPS1551 — estado vigente 2026-09-15T05:48:55.992636+00:00

Parcial: 6 aprobados, 0 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 521/742 | 221 | 0 | >=395 | 5/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 394 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); APPS1551 añade 1. No se cuentan revalidaciones.

Siguiente acción: APPS1551: 6 ejecutados, 6 aprobados, 0 fallidos, 1 créditos (índices [0]); Abrir aplicaciones 46/54. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/APPS1551/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 106.98 s acumulados; pico GPU 3497.56 MiB; pico RAM 1566.36 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 6; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0249 | passed | Comprobó de sólo lectura que el nombre no está entre las aplicaciones y dijo que no lo encuentra, nombrándolo, sin abrir ni buscar; crédito con dos variantes aprobadas del grupo. | Turno ordinario: una app.installed de sólo lectura completada y verificada (ausente); cero confirmaciones; cero violaciones; pins intactos. |
| 1 | apps1551-dev-01 | passed | Comprobó de sólo lectura que el nombre no está entre las aplicaciones y dijo que no lo encuentra, nombrándolo; variante o literal sin dos pares aprobados. | Turno ordinario: una app.installed de sólo lectura completada y verificada (ausente); cero confirmaciones; cero violaciones; pins intactos. |
| 2 | apps1551-dev-02 | passed | Comprobó de sólo lectura que el nombre no está entre las aplicaciones y dijo que no lo encuentra, nombrándolo; variante o literal sin dos pares aprobados. | Turno ordinario: una app.installed de sólo lectura completada y verificada (ausente); cero confirmaciones; cero violaciones; pins intactos. |
| 3 | apps1551-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | apps1551-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 5 | apps1551-boundary-03 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 106.98 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1566.36 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
