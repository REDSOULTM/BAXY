# TIME1197 — adjudicación de la raíz

## TIME1197 — estado vigente 2026-09-13T13:04:08+00:00

Parcial: 8 aprobados, 0 fallidos, 0 sin ejecutar; 3 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 263/742 | 479 | 0 | >=137 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–13 septiembre: 134 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS), todas dentro de la ventana de 24 h al adjudicar; TIME1197 añade 3. No se cuentan revalidaciones.

Siguiente acción: TIME1197 completa: 8 ejecutados, 8 aprobados, 3 créditos (H0121, H0343, H0371). La aclaración determinista «qué avisar» se demuestra (cuatro avisos sin contenido preguntan qué, conservan el plazo y no crean nada) y la hora imposible pide una hora válida en ambos idiomas. Defecto de redacción documentado sin reparación: el modelo invierte la persona en la pregunta española («me debes avisar»). Agenda queda 32/38; restan cancelación y listado de alarmas/temporizadores, tarea y reunión, «contá», «qué tengo agendado».

Evidencia: `artifacts/comprobaciones/C03/TIME1197/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 126.58 s acumulados; pico GPU 3497.56 MiB; pico RAM 1650.66 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 8; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0121 | passed | Pidió qué avisar conservando el plazo; dos pares aprobados. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 1 | H0343 | passed | Pidió qué avisar conservando el plazo; dos pares aprobados. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 2 | H0371 | passed | Pidió una hora válida; dos pares aprobados. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 3 | time1197-dev-01 | passed | Variante original aprobada. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | time1197-dev-02 | passed | Variante original aprobada. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 5 | time1197-dev-03 | passed | Variante original aprobada. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 6 | time1197-dev-04 | passed | Variante original aprobada. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 7 | time1197-boundary-01 | passed | Límite aprobado. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 126.58 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1650.66 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
