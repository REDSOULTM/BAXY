# ARRANGE1781 — adjudicación de la raíz

## ARRANGE1781 — estado vigente 2026-09-17T02:08:15.486828+00:00

Parcial: 2 aprobados, 3 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 638/742 | 104 | 0 | >=522 | 12/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 522 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); ARRANGE1781 añade 0. No se cuentan revalidaciones.

Siguiente acción: ARRANGE1781: 6 ejecutados, 2 aprobados, 4 fallidos, 0 créditos (índices []); Abrir aplicaciones 46/54. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/ARRANGE1781/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 98.06 s acumulados; pico GPU 3497.56 MiB; pico RAM 1688.82 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0268 | failed | Falló: la operación no se completó o no se verificó, o el final no fue fiel. | Turno ordinario: window.resolve completada y verificada sobre la ventana de Chrome abierta por la raíz; window.snap no invocada (los argumentos del paso no se completaron); final honesto; cero violaciones; pins intactos. |
| 1 | arrange1781-dev-01 | failed | Falló: la operación no se completó o no se verificó, o el final no fue fiel. | Turno ordinario: window.resolve completada y verificada sobre la ventana de Chrome abierta por la raíz; window.snap no invocada (los argumentos del paso no se completaron); final honesto; cero violaciones; pins intactos. |
| 2 | arrange1781-dev-02 | passed | window.resolve y window.snap completadas y verificadas sobre la ventana de Chrome abierta por la raíz en un perfil aislado, ninguna cerrada; el final dijo en qué lado la puso; Chrome cerrado por la raíz. | Turno ordinario: exactamente una window.resolve (Google Chrome) y una window.snap completadas y verificadas sobre la ventana de Chrome que la raíz abrió en un perfil aislado, ninguna cerrada; la raíz cierrauró la ventana; cero confirmaciones y violaciones; pins intactos. |
| 3 | arrange1781-boundary-01 | failed | Límite fallido: cero operaciones, pero la respuesta no fue fiel o útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | arrange1781-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 98.06 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1688.82 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
