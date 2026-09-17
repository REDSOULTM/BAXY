# ARRANGE1785 — adjudicación de la raíz

## ARRANGE1785 — estado vigente 2026-09-17T02:19:50.351585+00:00

Parcial: 4 aprobados, 1 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 639/742 | 103 | 0 | >=523 | 12/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 522 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); ARRANGE1785 añade 1. No se cuentan revalidaciones.

Siguiente acción: ARRANGE1785: 6 ejecutados, 4 aprobados, 2 fallidos, 1 créditos (índices [0]); Abrir aplicaciones 47/54. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/ARRANGE1785/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 88.22 s acumulados; pico GPU 3497.56 MiB; pico RAM 1688.52 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0268 | passed | window.resolve y window.snap completadas y verificadas sobre la ventana de Chrome abierta por la raíz en un perfil aislado, ninguna cerrada; el final dijo en qué lado la puso; Chrome cerrado por la raíz; crédito con dos variantes aprobadas del mismo grupo. | Turno ordinario: exactamente una window.resolve (Google Chrome) y una window.snap completadas y verificadas sobre la ventana de Chrome que la raíz abrió en un perfil aislado, ninguna cerrada; la raíz cierrauró la ventana; cero confirmaciones y violaciones; pins intactos. |
| 1 | arrange1785-dev-01 | passed | window.resolve y window.snap completadas y verificadas sobre la ventana de Chrome abierta por la raíz en un perfil aislado, ninguna cerrada; el final dijo en qué lado la puso; Chrome cerrado por la raíz. | Turno ordinario: exactamente una window.resolve (Google Chrome) y una window.snap completadas y verificadas sobre la ventana de Chrome que la raíz abrió en un perfil aislado, ninguna cerrada; la raíz cierrauró la ventana; cero confirmaciones y violaciones; pins intactos. |
| 2 | arrange1785-dev-02 | passed | window.resolve y window.snap completadas y verificadas sobre la ventana de Chrome abierta por la raíz en un perfil aislado, ninguna cerrada; el final dijo en qué lado la puso; Chrome cerrado por la raíz. | Turno ordinario: exactamente una window.resolve (Google Chrome) y una window.snap completadas y verificadas sobre la ventana de Chrome que la raíz abrió en un perfil aislado, ninguna cerrada; la raíz cierrauró la ventana; cero confirmaciones y violaciones; pins intactos. |
| 3 | arrange1785-boundary-01 | failed | Límite fallido: cero operaciones, pero la respuesta no fue fiel o útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | arrange1785-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 88.22 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1688.52 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
