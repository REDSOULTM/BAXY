# CLIPBOARD1359 — adjudicación de la raíz

## CLIPBOARD1359 — estado vigente 2026-09-14T06:28:59.920367+00:00

Parcial: 7 aprobados, 3 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 406/742 | 336 | 0 | >=280 | 3/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 279 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); CLIPBOARD1359 añade 1. No se cuentan revalidaciones.

Siguiente acción: CLIPBOARD1359: 10 ejecutados, 7 aprobados, 3 fallidos, 1 créditos (índices [2]); Portapapeles 1/3. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/CLIPBOARD1359/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 163.19 s acumulados; pico GPU 3497.56 MiB; pico RAM 1647.16 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 10; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0199 | failed | Falló: la operación no se propuso, no se aprobó o el final no fue fiel al texto observado. | Turno revisado: clipboard.write.text {text: literal pedido} propuesta, aprobada por la raíz por texto exacto, completada y verificada por postlectura; una confirmación; cero violaciones; pins intactos. |
| 1 | H0356 | failed | Falló: la operación no se propuso, no se aprobó o el final no fue fiel al texto observado. | Turno revisado: clipboard.write.text {text: literal pedido} propuesta, aprobada por la raíz por texto exacto, completada y verificada por postlectura; una confirmación; cero violaciones; pins intactos. |
| 2 | H0518 | passed | Respuesta fiel y útil; crédito con dos variantes aprobadas. | Turno revisado: clipboard.read.text propuesta, aprobada por la raíz sin argumentos ajenos, completada y verificada por doble lectura; una confirmación; cero violaciones; pins intactos. |
| 3 | clipboard1359-dev-01 | failed | Falló: la operación no se propuso, no se aprobó o el final no fue fiel al texto observado. | Turno revisado: clipboard.write.text {text: literal pedido} propuesta, aprobada por la raíz por texto exacto, completada y verificada por postlectura; una confirmación; cero violaciones; pins intactos. |
| 4 | clipboard1359-dev-02 | passed | Respuesta fiel y útil. | Turno revisado: clipboard.write.text {text: literal pedido} propuesta, aprobada por la raíz por texto exacto, completada y verificada por postlectura; una confirmación; cero violaciones; pins intactos. |
| 5 | clipboard1359-dev-03 | passed | Respuesta fiel y útil. | Turno revisado: clipboard.read.text propuesta, aprobada por la raíz sin argumentos ajenos, completada y verificada por doble lectura; una confirmación; cero violaciones; pins intactos. |
| 6 | clipboard1359-dev-04 | passed | Respuesta fiel y útil. | Turno revisado: clipboard.read.text propuesta, aprobada por la raíz sin argumentos ajenos, completada y verificada por doble lectura; una confirmación; cero violaciones; pins intactos. |
| 7 | clipboard1359-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos (portapapeles verificado igual antes y después por la raíz). |
| 8 | clipboard1359-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos (portapapeles verificado igual antes y después por la raíz). |
| 9 | clipboard1359-boundary-03 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos (portapapeles verificado igual antes y después por la raíz). |

Recursos: 163.19 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1647.16 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
