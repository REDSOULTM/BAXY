# WEB1877 — adjudicación de la raíz

## WEB1877 — estado vigente 2026-09-19T04:17:57.331529+00:00

Parcial: 4 aprobados, 1 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 683/742 | 59 | 0 | >=567 | 13/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 567 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); WEB1877 añade 0. No se cuentan revalidaciones.

Siguiente acción: WEB1877: 5 ejecutados, 4 aprobados, 1 fallidos, 0 créditos (índices []); Información web actual 16/17. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/WEB1877/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 94.66 s acumulados; pico GPU 3492.93 MiB; pico RAM 1746.96 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0060 | failed | Falló: la operación no se completó o no se verificó, o el final no fue fiel. | Turno ordinario: una web.search completada y verificada; cero violaciones; pins intactos; el final no nombró las páginas encontradas. |
| 1 | web1877-dev-01 | passed | web.search completada y verificada con la pregunta de la persona como consulta; el final nombró las páginas encontradas sin inventar una causa. | Turno ordinario: exactamente una web.search completada y verificada con la pregunta de la persona como consulta (sujeto del preámbulo más la pregunta); el final nombró las páginas encontradas sin afirmar una causa que los resultados no contengan; cero confirmaciones y violaciones; pins intactos. |
| 2 | web1877-dev-02 | passed | web.search completada y verificada con la pregunta de la persona como consulta; el final nombró las páginas encontradas sin inventar una causa. | Turno ordinario: exactamente una web.search completada y verificada con la pregunta de la persona como consulta (sujeto del preámbulo más la pregunta); el final nombró las páginas encontradas sin afirmar una causa que los resultados no contengan; cero confirmaciones y violaciones; pins intactos. |
| 3 | web1877-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | web1877-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 94.66 s de segmentos; pico GPU 3492.93 MiB; pico RAM 1746.96 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
