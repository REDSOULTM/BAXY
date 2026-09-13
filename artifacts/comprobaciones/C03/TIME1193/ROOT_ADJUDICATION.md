# TIME1193 — adjudicación de la raíz

## TIME1193 — estado vigente 2026-09-13T12:44:41+00:00

Parcial: 8 aprobados, 0 fallidos, 0 sin ejecutar; 3 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 258/742 | 484 | 0 | >=132 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–13 septiembre: 129 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS), todas dentro de la ventana de 24 h al adjudicar; TIME1193 añade 3. No se cuentan revalidaciones.

Siguiente acción: TIME1193 completa: 8 ejecutados, 8 aprobados, 0 fallidos, 3 créditos (H0273, H0514, H0259). Las reparaciones de hora explícita (lectura sobre texto plegado, periodo sobre 24 h, extractor de recordatorio con hora) se demuestran: cuatro alarmas con dueUtc == NextRun a la hora local pedida (canceladas por identidad exacta) y tres recordatorios a la hora local pedida. Agenda queda 27/38; restan «avisame en 30 minutos / en una hora» (sin contenido), «a las 5» (hora ambigua), «a las 99», cancelaciones y listados, tarea y reunión, «contá», «recuérdame comprar pilas» (sin hora), «qué tengo agendado».

Evidencia: `artifacts/comprobaciones/C03/TIME1193/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 143.86 s acumulados; pico GPU 3497.56 MiB; pico RAM 1759.67 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 8; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0273 | passed | Alarma creada y verificada a la hora local pedida; dos pares aprobados. | Final revisado con una admisión; una operación de programación verificada; postlectura y cancelación exacta de raíz; cero confirmaciones y violaciones; pins intactos. |
| 1 | H0514 | passed | Alarma creada y verificada a la hora local pedida; dos pares aprobados. | Final revisado con una admisión; una operación de programación verificada; postlectura y cancelación exacta de raíz; cero confirmaciones y violaciones; pins intactos. |
| 2 | H0259 | passed | Recordatorio creado con el contenido a la hora local pedida; dos pares aprobados. | Final revisado con una admisión; una operación de recordatorio verificada en el perfil aislado; cero confirmaciones y violaciones; pins intactos. |
| 3 | time1193-dev-01 | passed | Variante original aprobada. | Final revisado con una admisión; una operación de programación verificada; postlectura y cancelación exacta de raíz; cero violaciones; pins intactos. |
| 4 | time1193-dev-02 | passed | Variante original aprobada. | Final revisado con una admisión; una operación de programación verificada; postlectura y cancelación exacta de raíz; cero violaciones; pins intactos. |
| 5 | time1193-dev-03 | passed | Variante original aprobada. | Final revisado con una admisión; una operación de recordatorio verificada en el perfil aislado; cero violaciones; pins intactos. |
| 6 | time1193-dev-04 | passed | Variante original aprobada. | Final revisado con una admisión; una operación de recordatorio verificada en el perfil aislado; cero violaciones; pins intactos. |
| 7 | time1193-boundary-01 | passed | Límite aprobado. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 143.86 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1759.67 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
