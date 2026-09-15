# WEB1541 — adjudicación de la raíz

## WEB1541 — estado vigente 2026-09-15T04:27:27.034336+00:00

Parcial: 3 aprobados, 4 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 517/742 | 225 | 0 | >=391 | 4/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 391 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); WEB1541 añade 0. No se cuentan revalidaciones.

Siguiente acción: WEB1541: 7 ejecutados, 3 aprobados, 4 fallidos, 0 créditos (índices []); Leer y resumir páginas web 0/2. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/WEB1541/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 115.64 s acumulados; pico GPU 3497.56 MiB; pico RAM 1682.99 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 7; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0561 | failed | Falló: la lectura no se verificó o el final citó lo que la página no dice, no la nombró o no hubo final. | Turno revisado: browser.page.read propuesta y aprobada por la raíz sobre su propio fixture, ejecutada y dada por fallida por el contrato de efecto observado del núcleo; una confirmación; cero violaciones; pins intactos. |
| 1 | H0738 | failed | Falló: la lectura no se verificó o el final citó lo que la página no dice, no la nombró o no hubo final. | Turno revisado: browser.page.read propuesta y aprobada por la raíz sobre su propio fixture, ejecutada y dada por fallida por el contrato de efecto observado del núcleo; una confirmación; cero violaciones; pins intactos. |
| 2 | web1541-dev-01 | failed | Falló: la lectura no se verificó o el final citó lo que la página no dice, no la nombró o no hubo final. | Turno revisado: browser.page.read propuesta y aprobada por la raíz sobre su propio fixture, ejecutada y dada por fallida por el contrato de efecto observado del núcleo; una confirmación; cero violaciones; pins intactos. |
| 3 | web1541-dev-02 | failed | Falló: la lectura no se verificó o el final citó lo que la página no dice, no la nombró o no hubo final. | Turno revisado: browser.page.read propuesta y aprobada por la raíz sobre su propio fixture, ejecutada y dada por fallida por el contrato de efecto observado del núcleo; una confirmación; cero violaciones; pins intactos. |
| 4 | web1541-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 5 | web1541-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 6 | web1541-boundary-03 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 115.64 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1682.99 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
