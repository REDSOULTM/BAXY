# WINDOWS1695 — adjudicación de la raíz

## WINDOWS1695 — estado vigente 2026-09-16T08:49:33.129947+00:00

Parcial: 5 aprobados, 0 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 609/742 | 133 | 0 | >=493 | 9/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 492 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); WINDOWS1695 añade 1. No se cuentan revalidaciones.

Siguiente acción: WINDOWS1695: 6 ejecutados, 5 aprobados, 1 fallidos, 1 créditos (índices [0]); Abrir aplicaciones 47/54. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/WINDOWS1695/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 92.62 s acumulados; pico GPU 3497.56 MiB; pico RAM 1654.02 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0697 | passed | window.resolve y window.minimize completadas y verificadas sobre la ventana de Opera del dueño, ninguna cerrada; el final dijo que la minimizó; ventana restaurada por la raíz; crédito con dos variantes aprobadas del mismo grupo. | Turno ordinario: exactamente una window.resolve (Navegador Opera GX) y una window.minimize completadas y verificadas sobre la ventana del dueño, ninguna cerrada; la raíz restauró la ventana; cero confirmaciones y violaciones; pins intactos. |
| 1 | windows1695-dev-01 | passed | window.resolve y window.minimize completadas y verificadas sobre la ventana de Opera del dueño, ninguna cerrada; el final dijo que la minimizó; ventana restaurada por la raíz. | Turno ordinario: exactamente una window.resolve (Navegador Opera GX) y una window.minimize completadas y verificadas sobre la ventana del dueño, ninguna cerrada; la raíz restauró la ventana; cero confirmaciones y violaciones; pins intactos. |
| 2 | windows1695-dev-02 | passed | window.resolve y window.minimize completadas y verificadas sobre la ventana de Opera del dueño, ninguna cerrada; el final dijo que la minimizó; ventana restaurada por la raíz. | Turno ordinario: exactamente una window.resolve (Navegador Opera GX) y una window.minimize completadas y verificadas sobre la ventana del dueño, ninguna cerrada; la raíz restauró la ventana; cero confirmaciones y violaciones; pins intactos. |
| 3 | windows1695-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | windows1695-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 92.62 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1654.02 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
