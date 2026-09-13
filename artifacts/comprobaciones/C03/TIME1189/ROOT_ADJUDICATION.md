# TIME1189 — adjudicación de la raíz

## TIME1189 — estado vigente 2026-09-13T12:16:42+00:00

Parcial: 6 aprobados, 9 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 248/742 | 494 | 0 | >=122 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–13 septiembre: 122 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS), todas dentro de la ventana de 24 h al adjudicar; TIME1189 no añade. No se cuentan revalidaciones.

Siguiente acción: TIME1189 completa: 15 ejecutados, 6 aprobados, 9 fallidos, 0 créditos. Se demuestran la duración compacta (H0381, H0576 crean y verifican la alarma con due == NextRun) y las formas de recordatorio (H0102, H0283, H0330, H0715 crean el recordatorio con el contenido pedido y plazo dentro del bracket), pero ningún literal acredita porque sus pares fallaron: el despertar pierde el anclaje del enum «alarm» (alias), la duración al inicio no entra al reconocedor, y el recordatorio inglés cae en un falso positivo del validador de palabras recortadas (remind/reminder.create). Tres reparaciones puntuales verificadas sin GPU y remedición con el mismo material (TIME1191). «contá» y «For the oven, start…» quedan documentados.

Evidencia: `artifacts/comprobaciones/C03/TIME1189/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 260.30 s acumulados; pico GPU 3497.56 MiB; pico RAM 2037.07 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 15; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0641 | failed | Pidió cuándo y qué tipo aunque el pedido era completo. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 1 | H0381 | passed | Alarma creada y verificada con la duración compacta; sin crédito por faltar pares aprobados. | Final revisado con una admisión; una operación de programación verificada; postlectura y cancelación exacta de raíz; cero confirmaciones y violaciones; pins intactos. |
| 2 | H0576 | passed | Alarma creada y verificada con la duración compacta; sin crédito por faltar pares aprobados. | Final revisado con una admisión; una operación de programación verificada; postlectura y cancelación exacta de raíz; cero confirmaciones y violaciones; pins intactos. |
| 3 | H0102 | passed | Recordatorio creado con el contenido pedido; sin crédito por faltar pares aprobados. | Final revisado con una admisión; una operación de recordatorio verificada en el perfil aislado; cero confirmaciones y violaciones; pins intactos. |
| 4 | H0283 | passed | Recordatorio creado con el contenido pedido; sin crédito por faltar pares aprobados. | Final revisado con una admisión; una operación de recordatorio verificada en el perfil aislado; cero confirmaciones y violaciones; pins intactos. |
| 5 | H0330 | passed | Recordatorio creado con el contenido pedido; sin crédito por faltar pares aprobados. | Final revisado con una admisión; una operación de recordatorio verificada en el perfil aislado; cero confirmaciones y violaciones; pins intactos. |
| 6 | H0715 | passed | Recordatorio creado con el contenido pedido; sin crédito por faltar pares aprobados. | Final revisado con una admisión; una operación de recordatorio verificada en el perfil aislado; cero confirmaciones y violaciones; pins intactos. |
| 7 | alarm-panel978-dev-06 | failed | Pidió cuándo y qué aunque el pedido era completo. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 8 | alarm-panel978-dev-07 | failed | Pidió cuándo y qué tipo aunque el pedido era completo. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 9 | time1118-dev-compact-es | failed | Negó alcance en vez de crear el temporizador. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 10 | time1118-dev-compact-en | failed | Negó alcance en vez de crear el temporizador. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 11 | time1118-dev-reminder-es | failed | Pidió confirmación en vez de crear el recordatorio. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 12 | time1118-dev-reminder-en | failed | Creó el recordatorio pero publicó un código interno en vez de la respuesta. | Final revisado con una admisión; una operación de recordatorio verificada en el perfil aislado; el texto final fue un código de diagnóstico; pins intactos. |
| 13 | alarm-repair983-boundary-prohibition | failed | No creó nada pero ofreció cancelar otra alarma. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 14 | alarm-repair983-boundary-missing | failed | Negó alcance en vez de pedir la duración. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 260.30 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2037.07 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
