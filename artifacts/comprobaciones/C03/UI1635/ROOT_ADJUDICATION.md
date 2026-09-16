# UI1635 — adjudicación de la raíz

## UI1635 — estado vigente 2026-09-16T00:41:20.296827+00:00

Parcial: 3 aprobados, 2 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 580/742 | 162 | 0 | >=454 | 6/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 454 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); UI1635 añade 0. No se cuentan revalidaciones.

Siguiente acción: UI1635: 6 ejecutados, 3 aprobados, 3 fallidos, 0 créditos (índices []); Abrir aplicaciones 46/54. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/UI1635/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 90.95 s acumulados; pico GPU 3497.56 MiB; pico RAM 1716.17 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0592 | passed | Clic revisado y verificado en el botón Aceptar del diálogo propio de la raíz con una aprobación exacta; final fiel. | Turno revisado: input.visible.click con la etiqueta pedida sobre el diálogo propio de la raíz, una aprobación raíz exacta, completado y verificado (el diálogo se cerró); cero violaciones; pins intactos. |
| 1 | ui1635-dev-01 | failed | Falló: el clic no se propuso, no se aprobó, no se verificó, o el final no fue fiel. | Turno revisado: clic aprobado, completado y verificado (el diálogo propio se cerró); el final narró el control como deshabilitado leyendo el post-read del recibo; cero violaciones; pins intactos. |
| 2 | ui1635-dev-02 | failed | Falló: el clic no se propuso, no se aprobó, no se verificó, o el final no fue fiel. | Turno revisado: clic aprobado, completado y verificado; el final en inglés narró el botón como no clicable leyendo el post-read del recibo; cero violaciones; pins intactos. |
| 3 | ui1635-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | ui1635-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 90.95 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1716.17 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
