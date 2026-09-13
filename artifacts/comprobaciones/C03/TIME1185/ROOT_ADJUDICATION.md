# TIME1185 — adjudicación de la raíz

## TIME1185 — estado vigente 2026-09-13T11:44:22+00:00

Parcial: 7 aprobados, 1 fallidos, 0 sin ejecutar; 2 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 248/742 | 494 | 0 | >=122 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–13 septiembre: 120 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS), todas dentro de la ventana de 24 h al adjudicar; TIME1185 añade 2 (H0100, H0523). No se cuentan revalidaciones.

Siguiente acción: TIME1185 completa: 8 ejecutados, 7 aprobados, 1 fallido, 2 créditos (H0100, H0523). La decisión del dueño (segundo entero hacia arriba publicado) más la reparación de _canonical_due_utc se demuestran: seis alarmas/temporizadores con dueUtc == NextRun exacto y bracket cumplido; seis tareas canceladas por identidad exacta (911→910 cada vez), ninguna disparada. Fallo: «contá 10 minutos» negado como fuera de alcance (cabeza «contá» no leída como temporizador): causa léxica a reparar antes de remedir H0385. Agenda queda 17/38; siguiente: resto de alarmas/recordatorios relativos y de reloj explícito del material 1134 (índices 3–9 y 14–24) bajo el mismo criterio.

Evidencia: `artifacts/comprobaciones/C03/TIME1185/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 160.97 s acumulados; pico GPU 3497.56 MiB; pico RAM 1826.11 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 8; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0100 | passed | Alarma creada y verificada; hora publicada igual a la registrada; dos pares aprobados. | Final revisado con una admisión; una operación de programación verificada; postlectura y cancelación exacta de raíz; cero confirmaciones y violaciones; pins intactos. |
| 1 | H0523 | passed | Temporizador creado y verificado; hora publicada igual a la registrada; dos pares aprobados. | Final revisado con una admisión; una operación de programación verificada; postlectura y cancelación exacta de raíz; cero confirmaciones y violaciones; pins intactos. |
| 2 | H0385 | failed | Negó alcance en vez de crear el temporizador. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 3 | alarm-panel978-dev-04 | passed | Variante original aprobada. | Final revisado con una admisión; una operación de programación verificada; postlectura y cancelación exacta de raíz; cero violaciones; pins intactos. |
| 4 | alarm-panel978-dev-05 | passed | Variante original aprobada. | Final revisado con una admisión; una operación de programación verificada; postlectura y cancelación exacta de raíz; cero violaciones; pins intactos. |
| 5 | alarm-repair983-dev-relative-es | passed | Variante original aprobada. | Final revisado con una admisión; una operación de programación verificada; postlectura y cancelación exacta de raíz; cero violaciones; pins intactos. |
| 6 | alarm-repair983-dev-relative-order | passed | Variante original aprobada. | Final revisado con una admisión; una operación de programación verificada; postlectura y cancelación exacta de raíz; cero violaciones; pins intactos. |
| 7 | time1185-boundary-01 | passed | Límite aprobado. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 160.97 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1826.11 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
