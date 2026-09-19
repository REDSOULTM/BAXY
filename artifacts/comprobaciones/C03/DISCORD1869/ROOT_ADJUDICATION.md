# DISCORD1869 — adjudicación de la raíz

## DISCORD1869 — estado vigente 2026-09-19T03:20:50.563742+00:00

Parcial: 6 aprobados, 1 fallidos, 0 sin ejecutar; 2 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 678/742 | 64 | 0 | >=562 | 13/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 560 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); DISCORD1869 añade 2. No se cuentan revalidaciones.

Siguiente acción: DISCORD1869: 7 ejecutados, 6 aprobados, 1 fallidos, 2 créditos (índices [0, 1]); Mensajería 28/31. Siguiente: panel grande de mensajería (Musica y Valeria) sobre el mismo mecanismo.

Evidencia: `artifacts/comprobaciones/C03/DISCORD1869/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 156.17 s acumulados; pico GPU 3492.93 MiB; pico RAM 2496.50 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 7; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0318 | passed | Envió el mensaje de la persona al usuario de pruebas del dueño (Valeria) (destino forzado), con revisión de la raíz, y lo dijo con verdad; crédito con dos variantes aprobadas. | Turno revisado: message.send.test propuesta con el canal, el destinatario pedido y el texto de la persona, aprobada por la raíz, completada y verificada (destino forzado al usuario de pruebas del dueño (Valeria), texto enviado y entrega leída por OCR, sent true); una confirmación; cero violaciones; pins intactos. |
| 1 | H0340 | passed | Envió el mensaje de la persona al usuario de pruebas del dueño (Valeria) (destino forzado), con revisión de la raíz, y lo dijo con verdad; crédito con dos variantes aprobadas. | Turno revisado: message.send.test propuesta con el canal, el destinatario pedido y el texto de la persona, aprobada por la raíz, completada y verificada (destino forzado al usuario de pruebas del dueño (Valeria), texto enviado y entrega leída por OCR, sent true); una confirmación; cero violaciones; pins intactos. |
| 2 | H0394 | failed | Falló: el envío no se verificó en el canal de prueba, o el final afirmó que fue al destinatario pedido u otra cosa, o no hubo final. | Turno ordinario: cero operaciones; cero violaciones; pins intactos; el final no fue un acuse fiel. |
| 3 | discord1869-dev-01 | passed | Envió el mensaje de la persona al usuario de pruebas del dueño (Valeria) (destino forzado), con revisión de la raíz, y lo dijo con verdad; variante o literal sin dos pares aprobados. | Turno revisado: message.send.test propuesta con el canal, el destinatario pedido y el texto de la persona, aprobada por la raíz, completada y verificada (destino forzado al usuario de pruebas del dueño (Valeria), texto enviado y entrega leída por OCR, sent true); una confirmación; cero violaciones; pins intactos. |
| 4 | discord1869-dev-02 | passed | Envió el mensaje de la persona al usuario de pruebas del dueño (Valeria) (destino forzado), con revisión de la raíz, y lo dijo con verdad; variante o literal sin dos pares aprobados. | Turno revisado: message.send.test propuesta con el canal, el destinatario pedido y el texto de la persona, aprobada por la raíz, completada y verificada (destino forzado al usuario de pruebas del dueño (Valeria), texto enviado y entrega leída por OCR, sent true); una confirmación; cero violaciones; pins intactos. |
| 5 | discord1869-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 6 | discord1869-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 156.17 s de segmentos; pico GPU 3492.93 MiB; pico RAM 2496.50 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
