# UI1661 — adjudicación de la raíz

## UI1661 — estado vigente 2026-09-16T03:35:15.586787+00:00

Parcial: 5 aprobados, 1 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 592/742 | 150 | 0 | >=466 | 6/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 466 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); UI1661 añade 0. No se cuentan revalidaciones.

Siguiente acción: UI1661: 6 ejecutados, 5 aprobados, 1 fallidos, 0 créditos (índices []); Abrir aplicaciones 46/54. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/UI1661/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 107.72 s acumulados; pico GPU 3497.56 MiB; pico RAM 1689.31 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 6; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0290 | passed | Navegación dentro de un cliente de mensajería: el final dijo llanamente el límite nombrando el pedido, sin operaciones. | Turno ordinario: cero operaciones; el final dice llanamente que no puede moverse por los canales de la aplicación; cero confirmaciones y violaciones; pins intactos. |
| 1 | H0636 | passed | Navegación dentro de un cliente de mensajería: el final dijo llanamente el límite nombrando el pedido, sin operaciones. | Turno ordinario: cero operaciones; el final dice llanamente que no puede moverse por los canales de la aplicación; cero confirmaciones y violaciones; pins intactos. |
| 2 | ui1661-dev-01 | failed | Falló: hubo una operación o el final no dijo el límite con fidelidad. | Turno ordinario: cero violaciones; pins intactos; el final preguntó en vez de decir el límite (borrador con doble inhabilidad rechazado; reintento acotado vacío bajo la gramática JSON). |
| 3 | ui1661-dev-02 | passed | Navegación dentro de un cliente de mensajería: el final dijo llanamente el límite nombrando el pedido, sin operaciones. | Turno ordinario: cero operaciones; el final dice llanamente que no puede moverse por los canales de la aplicación; cero confirmaciones y violaciones; pins intactos. |
| 4 | ui1661-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 5 | ui1661-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 107.72 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1689.31 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
