# TIME1199 — adjudicación de la raíz

## TIME1199 — estado vigente 2026-09-13T13:15:39+00:00

Parcial: 9 aprobados, 1 fallidos, 0 sin ejecutar; 2 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 265/742 | 477 | 0 | >=139 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–13 septiembre: 137 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS), todas dentro de la ventana de 24 h al adjudicar; TIME1199 añade 2. No se cuentan revalidaciones.

Siguiente acción: TIME1199 completa: 10 ejecutados, 9 aprobados, 1 fallido, 2 créditos (H0385 «contá 10 minutos» con dos pares de temporizador; H0119 reunión sin fin con dos pares de aclaración). La cabeza de cuenta se demuestra (tres temporizadores con dueUtc == NextRun, cancelados). H0043 «crea una tarea para el viernes» falló: el modelo rellenó un título inventado y el producto intentó task.create (fallida) en vez de preguntar; sus pares sí preguntaron. Agenda queda 34/38: restan H0043, «cancelá la alarma», «listá los timers», «qué tengo agendado para hoy» (necesitan estado previo o lecturas de cuenta).

Evidencia: `artifacts/comprobaciones/C03/TIME1199/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 165.58 s acumulados; pico GPU 3497.56 MiB; pico RAM 1750.42 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 10; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0385 | passed | Temporizador creado y verificado con la duración contada; dos pares aprobados. | Final revisado con una admisión; una operación de programación verificada; postlectura y cancelación exacta de raíz; cero confirmaciones y violaciones; pins intactos. |
| 1 | H0119 | passed | Pidió el fin o la duración de la reunión conservando los datos; dos pares aprobados. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 2 | H0043 | failed | Intentó crear la tarea con un título inventado en vez de preguntar cuál es. | Caso detenido por el conductor por operación fuera del transporte; la operación falló sin efecto verificado; pins intactos. |
| 3 | time1199-dev-01 | passed | Variante original aprobada. | Final revisado con una admisión; una operación de programación verificada; postlectura y cancelación exacta de raíz; cero violaciones; pins intactos. |
| 4 | time1199-dev-02 | passed | Variante original aprobada. | Final revisado con una admisión; una operación de programación verificada; postlectura y cancelación exacta de raíz; cero violaciones; pins intactos. |
| 5 | time1199-dev-03 | passed | Variante original aprobada. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 6 | time1199-dev-04 | passed | Variante original aprobada. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 7 | time1199-dev-05 | passed | Variante original aprobada. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 8 | time1199-dev-06 | passed | Variante original aprobada. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 9 | time1199-boundary-01 | passed | Límite aprobado. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 165.58 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1750.42 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
