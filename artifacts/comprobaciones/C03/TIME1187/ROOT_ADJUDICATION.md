# TIME1187 — adjudicación de la raíz

## TIME1187 — estado vigente 2026-09-13T11:58:47+00:00

Parcial: 0 aprobados, 11 fallidos, 4 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 248/742 | 494 | 0 | >=122 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–13 septiembre: 122 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS), todas dentro de la ventana de 24 h al adjudicar; TIME1187 no añade. No se cuentan revalidaciones.

Siguiente acción: TIME1187 parcial: 11 ejecutados, 0 aprobados, 11 fallidos, 4 sin ejecutar (5, 6, 11, 12: recordatorios, aparcados al comprobar en el índice 4 que reminder.create está fuera del transporte sellado), 0 créditos. Causas medidas, todas léxicas o de transporte: (a) duración compacta «2min/3min/4min» no leída por los cinco lectores temporales (TIME1138); (b) «despertame/wake me» ausente del dominio y del reconocedor de alarma; «media hora» no es duración; (c) «contá N minutos» y «start a timer» sin cabeza de temporizador; (d) extractor de recordatorio relativo limitado a «avisame/remind me … que/to»; (e) transporte sin reminder.create. Siguiente: reparación léxica compartida (patrón de duración relativa con formas compactas y «media hora»; vocabulario de despertar; cabeza contá/start; cabezas y formas del recordatorio) verificada sin GPU, e instrumento TIME1189 con reminder.create autorizado para el grupo de recordatorios.

Evidencia: `artifacts/comprobaciones/C03/TIME1187/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 178.70 s acumulados; pico GPU 3497.56 MiB; pico RAM 1638.40 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 11; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0641 | failed | Pidió confirmación en vez de crear la alarma. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 1 | H0381 | failed | Pidió la hora aunque la duración estaba escrita (forma compacta). | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 2 | H0576 | failed | Pidió la hora aunque la duración estaba escrita (forma compacta). | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 3 | H0102 | failed | Pidió cuándo y qué recordar aunque ambos estaban en el pedido. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | H0283 | failed | Recordatorio creado, pero la operación no estaba autorizada en el transporte de esta tanda. | Caso detenido por el conductor por operación fuera del transporte; efecto confinado al perfil aislado; pins intactos. |
| 7 | alarm-panel978-dev-06 | failed | Negó alcance en vez de crear la alarma. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 8 | alarm-panel978-dev-07 | failed | Pidió la hora aunque la duración estaba escrita («media hora»). | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 9 | time1118-dev-compact-es | failed | Negó alcance en vez de crear el temporizador. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 10 | time1118-dev-compact-en | failed | Negó alcance en vez de crear el temporizador. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 13 | alarm-repair983-boundary-prohibition | failed | No creó nada pero ofreció cancelar otra alarma. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 14 | alarm-repair983-boundary-missing | failed | Negó alcance en vez de pedir la duración. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 178.70 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1638.40 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
