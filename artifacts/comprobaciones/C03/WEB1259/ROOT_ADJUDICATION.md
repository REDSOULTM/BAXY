# WEB1259 — adjudicación de la raíz

## WEB1259 — estado vigente 2026-09-13T21:57:08.997690+00:00

Parcial: 2 aprobados, 7 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 341/742 | 401 | 0 | >=215 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–13 septiembre: 215 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); WEB1259 no añade ninguna. No se cuentan revalidaciones.

Siguiente acción: WEB1259: 9 ejecutados, 2 aprobados, 7 fallidos, 0 créditos. Las dos causas de WEB1257 quedaron resueltas (los destinos simbólicos navegan; el final compone contra el pedido), pero el final de una navegación verificada promete («Voy a youtube.») porque la carga del compositor no marca outcome=completed para browser.navigate y nada rechaza la promesa. Siguiente: WEB1261 (mente: outcome completed, pista de estado y rechazo promised_effect) sobre el mismo panel.

Evidencia: `artifacts/comprobaciones/C03/WEB1259/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 181.61 s acumulados; pico GPU 3683.61 MiB; pico RAM 2460.25 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 9; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0480 | failed | Falló: navegó de verdad, pero el final lo prometió en vez de reportarlo. | Turno revisado: pregunta de confirmación y final; browser.navigate completada y verificada (URL final observada por la sesión CDP propia del producto); una confirmación aprobada por la raíz para el host esperado; cero violaciones; pins intactos. |
| 1 | H0320 | failed | Falló: navegó de verdad, pero el final lo prometió en vez de reportarlo. | Turno revisado: pregunta de confirmación y final; browser.navigate completada y verificada (URL final observada por la sesión CDP propia del producto); una confirmación aprobada por la raíz para el host esperado; cero violaciones; pins intactos. |
| 2 | H0161 | passed | Navegó al sitio pedido con revisión y lo dijo en pasado; sin crédito por faltar variantes aprobadas. | Turno revisado: pregunta de confirmación y final; browser.navigate completada y verificada (URL final observada por la sesión CDP propia del producto); una confirmación aprobada por la raíz para el host esperado; cero violaciones; pins intactos. |
| 3 | web1259-dev-01 | failed | Falló: navegó de verdad, pero el final lo prometió en vez de reportarlo. | Turno revisado: pregunta de confirmación y final; browser.navigate completada y verificada (URL final observada por la sesión CDP propia del producto); una confirmación aprobada por la raíz para el host esperado; cero violaciones; pins intactos. |
| 4 | web1259-dev-02 | failed | Falló: navegó de verdad, pero el final lo prometió en vez de reportarlo. | Turno revisado: pregunta de confirmación y final; browser.navigate completada y verificada (URL final observada por la sesión CDP propia del producto); una confirmación aprobada por la raíz para el host esperado; cero violaciones; pins intactos. |
| 5 | web1259-dev-03 | failed | Falló: navegó de verdad, pero el final lo prometió en vez de reportarlo. | Turno revisado: pregunta de confirmación y final; browser.navigate completada y verificada (URL final observada por la sesión CDP propia del producto); una confirmación aprobada por la raíz para el host esperado; cero violaciones; pins intactos. |
| 6 | web1259-dev-04 | passed | Navegó al sitio pedido con revisión y lo dijo en pasado; sin crédito por faltar variantes aprobadas. | Turno revisado: pregunta de confirmación y final; browser.navigate completada y verificada (URL final observada por la sesión CDP propia del producto); una confirmación aprobada por la raíz para el host esperado; cero violaciones; pins intactos. |
| 7 | web1259-boundary-01 | failed | Límite fallido: no navegó pero no respondió la pregunta. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 8 | web1259-boundary-02 | failed | Límite fallido: explicación no fiel. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 181.61 s de segmentos; pico GPU 3683.61 MiB; pico RAM 2460.25 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
