# UI1637 — adjudicación de la raíz

## UI1637 — estado vigente 2026-09-16T00:45:04.744829+00:00

Parcial: 5 aprobados, 0 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 581/742 | 161 | 0 | >=455 | 6/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 454 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); UI1637 añade 1. No se cuentan revalidaciones.

Siguiente acción: UI1637: 6 ejecutados, 5 aprobados, 1 fallidos, 1 créditos (índices [0]); Abrir aplicaciones 47/54. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/UI1637/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 88.34 s acumulados; pico GPU 3497.56 MiB; pico RAM 1690.80 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0592 | passed | Clic revisado y verificado en el botón Aceptar del diálogo propio de la raíz con una aprobación exacta; final fiel; crédito con dos variantes aprobadas. | Turno revisado: input.visible.click con la etiqueta pedida sobre el diálogo propio de la raíz, una aprobación raíz exacta, completado y verificado (el diálogo se cerró); cero violaciones; pins intactos. |
| 1 | ui1637-dev-01 | passed | Clic revisado y verificado en el botón Aceptar del diálogo propio de la raíz con una aprobación exacta; final fiel. | Turno revisado: input.visible.click con la etiqueta pedida sobre el diálogo propio de la raíz, una aprobación raíz exacta, completado y verificado (el diálogo se cerró); cero violaciones; pins intactos. |
| 2 | ui1637-dev-02 | passed | Clic revisado y verificado en el botón Aceptar del diálogo propio de la raíz con una aprobación exacta; final fiel. | Turno revisado: input.visible.click con la etiqueta pedida sobre el diálogo propio de la raíz, una aprobación raíz exacta, completado y verificado (el diálogo se cerró); cero violaciones; pins intactos. |
| 3 | ui1637-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | ui1637-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 88.34 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1690.80 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
