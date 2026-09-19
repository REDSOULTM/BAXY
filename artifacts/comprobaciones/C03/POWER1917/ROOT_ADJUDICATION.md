# POWER1917 — adjudicación de la raíz

## POWER1917 — estado vigente 2026-09-19T20:34:30.179233+00:00

Parcial: 6 aprobados, 0 fallidos, 0 sin ejecutar; 2 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 709/742 | 33 | 0 | >=593 | 13/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 591 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); POWER1917 añade 2. No se cuentan revalidaciones.

Siguiente acción: POWER1917: 6 ejecutados, 6 aprobados, 0 fallidos, 2 créditos (índices [0, 1]). Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/POWER1917/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 127.74 s acumulados; pico GPU 3492.93 MiB; pico RAM 2162.84 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 6; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0401 | passed | llama de verdad a la transición pedida y, al rechazarla Windows, dice que el equipo sigue encendido; crédito con dos variantes aprobadas del mismo grupo. | Turno ordinario: exactamente una system.power con la acción pedida, llamada de verdad, que termina en power_transition_not_accepted porque Windows no inicia la transición; nada del equipo cambia; cero confirmaciones y violaciones; pins intactos. |
| 1 | H0714 | passed | llama de verdad a la transición pedida y, al rechazarla Windows, dice que el equipo sigue encendido; crédito con dos variantes aprobadas del mismo grupo. | Turno ordinario: exactamente una system.power con la acción pedida, llamada de verdad, que termina en power_transition_not_accepted porque Windows no inicia la transición; nada del equipo cambia; cero confirmaciones y violaciones; pins intactos. |
| 2 | power1917-dev-01 | passed | llama de verdad a la transición pedida y, al rechazarla Windows, dice que el equipo sigue encendido. | Turno ordinario: exactamente una system.power con la acción pedida, llamada de verdad, que termina en power_transition_not_accepted porque Windows no inicia la transición; nada del equipo cambia; cero confirmaciones y violaciones; pins intactos. |
| 3 | power1917-dev-02 | passed | llama de verdad a la transición pedida y, al rechazarla Windows, dice que el equipo sigue encendido. | Turno ordinario: exactamente una system.power con la acción pedida, llamada de verdad, que termina en power_transition_not_accepted porque Windows no inicia la transición; nada del equipo cambia; cero confirmaciones y violaciones; pins intactos. |
| 4 | power1917-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 5 | power1917-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 127.74 s de segmentos; pico GPU 3492.93 MiB; pico RAM 2162.84 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
