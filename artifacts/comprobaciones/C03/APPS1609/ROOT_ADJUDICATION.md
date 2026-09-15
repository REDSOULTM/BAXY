# APPS1609 — adjudicación de la raíz

## APPS1609 — estado vigente 2026-09-15T21:02:59.266088+00:00

Parcial: 2 aprobados, 4 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 548/742 | 194 | 0 | >=422 | 6/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 422 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); APPS1609 añade 0. No se cuentan revalidaciones.

Siguiente acción: APPS1609: 6 ejecutados, 2 aprobados, 4 fallidos, 0 créditos (índices []); Abrir aplicaciones 46/54. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/APPS1609/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 115.51 s acumulados; pico GPU 3497.56 MiB; pico RAM 1731.87 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 6; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0487 | failed | Falló: Steam no se abrió o no se verificó, o el final no fue fiel. | Turno ordinario: app.open de Steam devolvió verification_failed a los 3,6 s; el cliente arrancó y su ventana apareció después (medida raíz: 4,6 s); el final preguntó de vuelta y negó la capacidad; cero violaciones; pins intactos. |
| 1 | H0544 | failed | Falló: Steam no se abrió o no se verificó, o el final no fue fiel. | Turno ordinario: app.open de Steam devolvió verification_failed a los 3,6 s (presupuesto de verificación de ≈3 s del proveedor de catálogo; la primera ventana de Steam aparece a los 4,6 s); el final dijo con verdad que no pudo confirmar la apertura; cero violaciones; pins intactos. |
| 2 | apps1609-dev-01 | failed | Falló: Steam no se abrió o no se verificó, o el final no fue fiel. | Turno ordinario: app.open de Steam devolvió verification_failed antes de que apareciera la ventana; el final lo dijo con verdad; cero violaciones; pins intactos. |
| 3 | apps1609-dev-02 | failed | Falló: Steam no se abrió o no se verificó, o el final no fue fiel. | Turno ordinario: app.open de Steam devolvió verification_failed antes de que apareciera la ventana; el final lo dijo con verdad (en inglés, como la variante); cero violaciones; pins intactos. |
| 4 | apps1609-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 5 | apps1609-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 115.51 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1731.87 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
