# TIME1191 — adjudicación de la raíz

## TIME1191 — estado vigente 2026-09-13T12:31:04+00:00

Parcial: 11 aprobados, 4 fallidos, 0 sin ejecutar; 7 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 255/742 | 487 | 0 | >=129 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–13 septiembre: 122 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS), todas dentro de la ventana de 24 h al adjudicar; TIME1191 añade 7. No se cuentan revalidaciones.

Siguiente acción: TIME1191 completa: 15 ejecutados, 11 aprobados, 4 fallidos, 7 créditos (H0641, H0381, H0576, H0102, H0283, H0330, H0715). Las tres reparaciones de TIME1189 se demuestran: el despertar crea la alarma (alias del enum), el recordatorio con duración al inicio se crea con el contenido íntegro, y el recordatorio inglés publica su respuesta. Cinco alarmas nuevas con dueUtc == NextRun y bracket cumplido, cinco tareas canceladas por identidad exacta (911→910 cada vez); seis recordatorios en el almacén del perfil aislado con plazo dentro del bracket. Abiertos documentados: «contá N minutos» (cabeza ambigua), «For the oven, start a timer…» (cabeza «for»), y los dos límites (sustituto de cancelación; negación falsa con cláusula «pero»). Agenda queda 24/38; siguiente: reloj explícito y recurrentes del material de agenda restante.

Evidencia: `artifacts/comprobaciones/C03/TIME1191/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 265.34 s acumulados; pico GPU 3497.56 MiB; pico RAM 1732.40 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 15; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0641 | passed | Alarma de despertar creada y verificada; hora publicada igual a la registrada; dos pares aprobados. | Final revisado con una admisión; una operación de programación verificada; postlectura y cancelación exacta de raíz; cero confirmaciones y violaciones; pins intactos. |
| 1 | H0381 | passed | Alarma creada y verificada con la duración compacta; dos pares aprobados. | Final revisado con una admisión; una operación de programación verificada; postlectura y cancelación exacta de raíz; cero confirmaciones y violaciones; pins intactos. |
| 2 | H0576 | passed | Alarma creada y verificada con la duración compacta; dos pares aprobados. | Final revisado con una admisión; una operación de programación verificada; postlectura y cancelación exacta de raíz; cero confirmaciones y violaciones; pins intactos. |
| 3 | H0102 | passed | Recordatorio creado con el contenido y el plazo pedidos; dos pares aprobados. | Final revisado con una admisión; una operación de recordatorio verificada en el perfil aislado; cero confirmaciones y violaciones; pins intactos. |
| 4 | H0283 | passed | Recordatorio creado con el contenido y el plazo pedidos; dos pares aprobados. | Final revisado con una admisión; una operación de recordatorio verificada en el perfil aislado; cero confirmaciones y violaciones; pins intactos. |
| 5 | H0330 | passed | Recordatorio creado con el contenido y el plazo pedidos; dos pares aprobados. | Final revisado con una admisión; una operación de recordatorio verificada en el perfil aislado; cero confirmaciones y violaciones; pins intactos. |
| 6 | H0715 | passed | Recordatorio creado con el contenido y el plazo pedidos; dos pares aprobados. | Final revisado con una admisión; una operación de recordatorio verificada en el perfil aislado; cero confirmaciones y violaciones; pins intactos. |
| 7 | alarm-panel978-dev-06 | passed | Variante original aprobada. | Final revisado con una admisión; una operación de programación verificada; postlectura y cancelación exacta de raíz; cero violaciones; pins intactos. |
| 8 | alarm-panel978-dev-07 | passed | Variante original aprobada (hora publicada igual a la registrada; nombra la alarma como recordatorio). | Final revisado con una admisión; una operación de programación verificada; postlectura y cancelación exacta de raíz; cero violaciones; pins intactos. |
| 9 | time1118-dev-compact-es | failed | Negó alcance en vez de crear el temporizador. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 10 | time1118-dev-compact-en | failed | Negó alcance en vez de crear el temporizador. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 11 | time1118-dev-reminder-es | passed | Variante original aprobada: recordatorio con duración al inicio. | Final revisado con una admisión; una operación de recordatorio verificada en el perfil aislado; cero violaciones; pins intactos. |
| 12 | time1118-dev-reminder-en | passed | Variante original aprobada: recordatorio publicado con su respuesta. | Final revisado con una admisión; una operación de recordatorio verificada en el perfil aislado; cero violaciones; pins intactos. |
| 13 | alarm-repair983-boundary-prohibition | failed | No creó nada pero ofreció cancelar otra alarma. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 14 | alarm-repair983-boundary-missing | failed | Negó alcance en vez de pedir la duración. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 265.34 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1732.40 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
