# SCREEN1399 — adjudicación de la raíz

## SCREEN1399 — estado vigente 2026-09-14T12:35:50.311473+00:00

Parcial: 6 aprobados, 4 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 423/742 | 319 | 0 | >=297 | 4/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 297 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); SCREEN1399 añade 0. No se cuentan revalidaciones.

Siguiente acción: SCREEN1399: 10 ejecutados, 6 aprobados, 4 fallidos, 0 créditos (índices []); Pantalla, captura e interpretación visual 0/19. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/SCREEN1399/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 212.17 s acumulados; pico GPU 3497.56 MiB; pico RAM 2448.42 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 10; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0093 | failed | Falló: la captura no se verificó o el final no fue fiel. | Turno revisado: capture.screenshot propuesta sin argumentos, aprobada por la raíz, completada y verificada (BMP privado; identidad, dimensiones y hash); una confirmación; cero violaciones; pins intactos; la captura queda en el directorio privado del perfil y no se publica. El final publicado repitió la orden en imperativo en vez de informar la captura. |
| 1 | screen1399-dev-01 | passed | Sacó la captura de pantalla revisada y lo dijo. | Turno revisado: capture.screenshot propuesta por la App sin argumentos, aprobada por la raíz, completada y verificada por el proveedor (BMP privado con identidad, dimensiones y hash); una confirmación; cero violaciones; pins intactos; la captura queda en el directorio privado del perfil y no se publica. |
| 2 | screen1399-dev-02 | failed | Falló: la captura no se verificó o el final no fue fiel. | Turno revisado: capture.screenshot propuesta sin argumentos, aprobada por la raíz, completada y verificada (BMP privado; identidad, dimensiones y hash); una confirmación; cero violaciones; pins intactos; la captura queda en el directorio privado del perfil y no se publica. Sin final publicado: los borradores narraron el identificador interno de la captura y fueron vetados. |
| 3 | screen1399-dev-03 | failed | Falló: la captura no se verificó o el final no fue fiel. | Turno revisado: capture.screenshot propuesta sin argumentos, aprobada por la raíz, completada y verificada (BMP privado; identidad, dimensiones y hash); una confirmación; cero violaciones; pins intactos; la captura queda en el directorio privado del perfil y no se publica. Sin final publicado: los borradores narraron el identificador interno de la captura y fueron vetados. |
| 4 | screen1399-dev-04 | passed | Sacó la captura de pantalla revisada y lo dijo. | Turno revisado: capture.screenshot propuesta por la App sin argumentos, aprobada por la raíz, completada y verificada por el proveedor (BMP privado con identidad, dimensiones y hash); una confirmación; cero violaciones; pins intactos; la captura queda en el directorio privado del perfil y no se publica. |
| 5 | screen1399-dev-05 | passed | Sacó la captura de pantalla revisada y lo dijo. | Turno revisado: capture.screenshot propuesta por la App sin argumentos, aprobada por la raíz, completada y verificada por el proveedor (BMP privado con identidad, dimensiones y hash); una confirmación; cero violaciones; pins intactos; la captura queda en el directorio privado del perfil y no se publica. |
| 6 | screen1399-dev-06 | failed | Falló: la captura no se verificó o el final no fue fiel. | Turno revisado: capture.screenshot propuesta sin argumentos, aprobada por la raíz, completada y verificada (BMP privado; identidad, dimensiones y hash); una confirmación; cero violaciones; pins intactos; la captura queda en el directorio privado del perfil y no se publica. Sin final publicado: los borradores narraron el identificador interno de la captura y fueron vetados. |
| 7 | screen1399-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 8 | screen1399-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 9 | screen1399-boundary-03 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 212.17 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2448.42 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
