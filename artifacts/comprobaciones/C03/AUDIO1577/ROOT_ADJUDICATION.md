# AUDIO1577 — adjudicación de la raíz

## AUDIO1577 — estado vigente 2026-09-15T17:13:47.620595+00:00

Parcial: 1 aprobados, 4 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 534/742 | 208 | 0 | >=408 | 5/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 408 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); AUDIO1577 añade 0. No se cuentan revalidaciones.

Siguiente acción: AUDIO1577: 5 ejecutados, 1 aprobados, 4 fallidos, 0 créditos (índices []); Audio y volumen 45/51. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/AUDIO1577/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 107.81 s acumulados; pico GPU 3497.56 MiB; pico RAM 1589.91 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0067 | failed | Falló: la lectura no se hizo, el final no dio el dato observado, no terminó con la pregunta por la cantidad o afirmó un cambio de volumen. | Turno ordinario: lectura verificada; la mente compuso el dato y la pregunta por la cantidad, la App rechazó el final por nombrar el volumen sin nivel observado; cero violaciones; pins intactos. |
| 1 | audio1577-dev-01 | failed | Falló: la lectura no se hizo, el final no dio el dato observado, no terminó con la pregunta por la cantidad o afirmó un cambio de volumen. | Turno ordinario: lectura verificada; la mente compuso el dato y la pregunta por la cantidad, la App rechazó el final por nombrar el volumen sin nivel observado; cero violaciones; pins intactos. |
| 2 | audio1577-dev-02 | failed | Falló: la lectura no se hizo, el final no dio el dato observado, no terminó con la pregunta por la cantidad o afirmó un cambio de volumen. | Turno ordinario: lectura verificada; la mente compuso el dato y la pregunta por la cantidad, la App rechazó el final por nombrar el volumen sin nivel observado; cero violaciones; pins intactos. |
| 3 | audio1577-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | audio1577-boundary-02 | failed | Límite fallido: cero operaciones, pero la respuesta no fue fiel o útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 107.81 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1589.91 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
