# APPS1549 — adjudicación de la raíz

## APPS1549 — estado vigente 2026-09-15T05:44:30.081006+00:00

Parcial: 3 aprobados, 3 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 520/742 | 222 | 0 | >=394 | 5/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 394 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); APPS1549 añade 0. No se cuentan revalidaciones.

Siguiente acción: APPS1549: 6 ejecutados, 3 aprobados, 3 fallidos, 0 créditos (índices []); Abrir aplicaciones 45/54. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/APPS1549/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 110.24 s acumulados; pico GPU 3497.56 MiB; pico RAM 1576.01 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 6; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0249 | failed | Falló: la lectura de presencia se decidió pero su argumento no se enlazó y el turno preguntó en vez de comprobar y nombrar el nombre pedido. | Turno ordinario: cero operaciones; cero confirmaciones; cero violaciones; pins intactos; el final fue una pregunta, no la comprobación pedida. |
| 1 | apps1549-dev-01 | failed | Falló: la lectura de presencia se decidió pero su argumento no se enlazó y el turno preguntó en vez de comprobar y nombrar el nombre pedido. | Turno ordinario: cero operaciones; cero confirmaciones; cero violaciones; pins intactos; el final fue una pregunta, no la comprobación pedida. |
| 2 | apps1549-dev-02 | failed | Falló: la lectura de presencia se decidió pero su argumento no se enlazó y el turno preguntó en vez de comprobar y nombrar el nombre pedido. | Turno ordinario: cero operaciones; cero confirmaciones; cero violaciones; pins intactos; el final fue una pregunta, no la comprobación pedida. |
| 3 | apps1549-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | apps1549-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 5 | apps1549-boundary-03 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 110.24 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1576.01 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
