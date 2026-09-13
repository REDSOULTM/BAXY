# WEB1263 — adjudicación de la raíz

## WEB1263 — estado vigente 2026-09-13T22:11:43.352520+00:00

Parcial: 7 aprobados, 2 fallidos, 0 sin ejecutar; 3 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 344/742 | 398 | 0 | >=218 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–13 septiembre: 215 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); WEB1263 añade 3. No se cuentan revalidaciones.

Siguiente acción: WEB1263: 9 ejecutados, 7 aprobados, 2 fallidos, 3 créditos (índices [0, 1, 2]). Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/WEB1263/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 182.38 s acumulados; pico GPU 3497.56 MiB; pico RAM 2651.43 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 9; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0480 | passed | Navegó al sitio pedido con revisión y lo reportó; crédito con dos variantes aprobadas. | Turno revisado: pregunta de confirmación y final; browser.navigate completada y verificada (URL final observada por la sesión CDP propia del producto); una confirmación aprobada por la raíz para el host esperado; cero violaciones; pins intactos. |
| 1 | H0320 | passed | Navegó al sitio pedido con revisión y lo reportó; crédito con dos variantes aprobadas. | Turno revisado: pregunta de confirmación y final; browser.navigate completada y verificada (URL final observada por la sesión CDP propia del producto); una confirmación aprobada por la raíz para el host esperado; cero violaciones; pins intactos. |
| 2 | H0161 | passed | Navegó al sitio pedido con revisión y lo reportó; crédito con dos variantes aprobadas. | Turno revisado: pregunta de confirmación y final; browser.navigate completada y verificada (URL final observada por la sesión CDP propia del producto); una confirmación aprobada por la raíz para el host esperado; cero violaciones; pins intactos. |
| 3 | web1263-dev-01 | passed | Navegó al sitio pedido con revisión y lo reportó. | Turno revisado: pregunta de confirmación y final; browser.navigate completada y verificada (URL final observada por la sesión CDP propia del producto); una confirmación aprobada por la raíz para el host esperado; cero violaciones; pins intactos. |
| 4 | web1263-dev-02 | passed | Navegó al sitio pedido con revisión y lo reportó. | Turno revisado: pregunta de confirmación y final; browser.navigate completada y verificada (URL final observada por la sesión CDP propia del producto); una confirmación aprobada por la raíz para el host esperado; cero violaciones; pins intactos. |
| 5 | web1263-dev-03 | passed | Navegó al sitio pedido con revisión y lo reportó. | Turno revisado: pregunta de confirmación y final; browser.navigate completada y verificada (URL final observada por la sesión CDP propia del producto); una confirmación aprobada por la raíz para el host esperado; cero violaciones; pins intactos. |
| 6 | web1263-dev-04 | passed | Navegó al sitio pedido con revisión y lo reportó. | Turno revisado: pregunta de confirmación y final; browser.navigate completada y verificada (URL final observada por la sesión CDP propia del producto); una confirmación aprobada por la raíz para el host esperado; cero violaciones; pins intactos. |
| 7 | web1263-boundary-01 | failed | Límite fallido: no navegó pero la respuesta no fue fiel o útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 8 | web1263-boundary-02 | failed | Límite fallido: no navegó pero la respuesta no fue fiel o útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 182.38 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2651.43 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
