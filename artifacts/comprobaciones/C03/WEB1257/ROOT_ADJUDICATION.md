# WEB1257 — adjudicación de la raíz

## WEB1257 — estado vigente 2026-09-13T21:42:38.711028+00:00

Parcial: 5 aprobados, 7 fallidos, 0 sin ejecutar; 3 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 341/742 | 401 | 0 | >=215 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–13 septiembre: 212 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); WEB1257 añade 3 (H0185, H0565, H0389), 215 después. No se cuentan revalidaciones.

Siguiente acción: WEB1257: 12 ejecutados, 5 aprobados, 7 fallidos, 3 créditos (H0185, H0565, H0389 con dev-01/dev-02). Los destinos simbólicos («andá a youtube», «llevame a github», «Ve a ChatGPT» y sus variantes) preguntaron la URL: el lector navega directo porque el catálogo conoce esos nombres, pero el constructor de argumentos se abstiene ante el destino simbólico. Siguiente: WEB1259 con el constructor alineado con la lista pública cerrada (mente) y la composición del final contra el pedido y no contra «confirmar» (App).

Evidencia: `artifacts/comprobaciones/C03/WEB1257/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 211.70 s acumulados; pico GPU 3683.61 MiB; pico RAM 2514.06 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 12; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0185 | passed | Navegó al sitio pedido con revisión y lo dijo; crédito con dos variantes aprobadas. | Turno revisado: pregunta de confirmación y final; browser.navigate completada y verificada (URL final observada por la sesión CDP propia del producto); una confirmación aprobada por la raíz para el host esperado; cero violaciones; pins intactos. |
| 1 | H0565 | passed | Navegó al sitio pedido con revisión y lo dijo; crédito con dos variantes aprobadas. | Turno revisado: pregunta de confirmación y final; browser.navigate completada y verificada (URL final observada por la sesión CDP propia del producto); una confirmación aprobada por la raíz para el host esperado; cero violaciones; pins intactos. |
| 2 | H0389 | passed | Navegó al sitio pedido con revisión y lo dijo; crédito con dos variantes aprobadas. | Turno revisado: pregunta de confirmación y final; browser.navigate completada y verificada (URL final observada por la sesión CDP propia del producto); una confirmación aprobada por la raíz para el host esperado; cero violaciones; pins intactos. |
| 3 | H0480 | failed | Falló: preguntó la URL en vez de navegar al sitio nombrado. | Final publicado: pregunta por la URL; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | H0320 | failed | Falló: preguntó la URL en vez de navegar al sitio nombrado. | Final publicado: pregunta por la URL; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 5 | H0161 | failed | Falló: preguntó la URL en vez de navegar al sitio nombrado. | Final publicado: pregunta por la URL; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 6 | web1257-dev-01 | passed | Navegó al sitio pedido con revisión y lo dijo; variante que sostiene el crédito. | Turno revisado: pregunta de confirmación y final; browser.navigate completada y verificada (URL final observada por la sesión CDP propia del producto); una confirmación aprobada por la raíz para el host esperado; cero violaciones; pins intactos. |
| 7 | web1257-dev-02 | passed | Navegó al sitio pedido con revisión y lo dijo; variante que sostiene el crédito. | Turno revisado: pregunta de confirmación y final; browser.navigate completada y verificada (URL final observada por la sesión CDP propia del producto); una confirmación aprobada por la raíz para el host esperado; cero violaciones; pins intactos. |
| 8 | web1257-dev-03 | failed | Falló: preguntó la URL en vez de navegar al sitio nombrado. | Final publicado: pregunta por la URL; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 9 | web1257-dev-04 | failed | Falló: preguntó la URL en vez de navegar al sitio nombrado. | Final publicado: pregunta por la URL; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 10 | web1257-boundary-01 | failed | Límite fallido: no navegó pero la respuesta no fue fiel. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 11 | web1257-boundary-02 | failed | Límite fallido: explicación no fiel. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 211.70 s de segmentos; pico GPU 3683.61 MiB; pico RAM 2514.06 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
