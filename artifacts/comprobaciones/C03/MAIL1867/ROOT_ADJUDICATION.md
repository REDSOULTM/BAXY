# MAIL1867 — adjudicación de la raíz

## MAIL1867 — estado vigente 2026-09-19T02:41:37.510864+00:00

Parcial: 5 aprobados, 0 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 676/742 | 66 | 0 | >=560 | 13/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 559 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); MAIL1867 añade 1. No se cuentan revalidaciones.

Siguiente acción: MAIL1867: 5 ejecutados, 5 aprobados, 0 fallidos, 1 créditos (índices [0]); Mensajería 10/31. Siguiente: panel grande de mensajería (Musica y Valeria) sobre el mismo mecanismo.

Evidencia: `artifacts/comprobaciones/C03/MAIL1867/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 116.84 s acumulados; pico GPU 3492.93 MiB; pico RAM 2598.36 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0018 | passed | Envió el mensaje de la persona al canal de prueba del dueño (destino forzado), con revisión de la raíz, y lo dijo con verdad; crédito con dos variantes aprobadas. | Turno revisado: message.send.test propuesta con el canal, el destinatario pedido y el texto de la persona, aprobada por la raíz, completada y verificada (destino forzado al canal de prueba del dueño, texto enviado y entrega leída por OCR, sent true); una confirmación; cero violaciones; pins intactos. |
| 1 | mail1867-dev-01 | passed | Envió el mensaje de la persona al canal de prueba del dueño (destino forzado), con revisión de la raíz, y lo dijo con verdad; variante o literal sin dos pares aprobados. | Turno revisado: message.send.test propuesta con el canal, el destinatario pedido y el texto de la persona, aprobada por la raíz, completada y verificada (destino forzado al canal de prueba del dueño, texto enviado y entrega leída por OCR, sent true); una confirmación; cero violaciones; pins intactos. |
| 2 | mail1867-dev-02 | passed | Envió el mensaje de la persona al canal de prueba del dueño (destino forzado), con revisión de la raíz, y lo dijo con verdad; variante o literal sin dos pares aprobados. | Turno revisado: message.send.test propuesta con el canal, el destinatario pedido y el texto de la persona, aprobada por la raíz, completada y verificada (destino forzado al canal de prueba del dueño, texto enviado y entrega leída por OCR, sent true); una confirmación; cero violaciones; pins intactos. |
| 3 | mail1867-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | mail1867-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 116.84 s de segmentos; pico GPU 3492.93 MiB; pico RAM 2598.36 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
