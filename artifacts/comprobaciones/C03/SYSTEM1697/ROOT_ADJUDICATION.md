# SYSTEM1697 — adjudicación de la raíz

## SYSTEM1697 — estado vigente 2026-09-16T09:16:06.502788+00:00

Parcial: 4 aprobados, 1 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 610/742 | 132 | 0 | >=494 | 9/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 493 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); SYSTEM1697 añade 1. No se cuentan revalidaciones.

Siguiente acción: SYSTEM1697: 6 ejecutados, 4 aprobados, 2 fallidos, 1 créditos (índices [0]); Abrir aplicaciones 47/54. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/SYSTEM1697/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 91.83 s acumulados; pico GPU 3497.56 MiB; pico RAM 1655.39 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0307 | passed | software.python.status completada y verificada sobre el registro de Windows (sin ejecutar nada); el final dio las versiones de Python registradas con sus cadenas exactas; crédito con dos variantes aprobadas del mismo grupo. | Turno ordinario: exactamente una software.python.status completada y verificada (instalaciones de Python registradas en Windows, PEP 514, sin ejecutar nada); el final dio las versiones exactas; cero confirmaciones y violaciones; pins intactos. |
| 1 | system1697-dev-01 | passed | software.python.status completada y verificada sobre el registro de Windows (sin ejecutar nada); el final dio las versiones de Python registradas con sus cadenas exactas. | Turno ordinario: exactamente una software.python.status completada y verificada (instalaciones de Python registradas en Windows, PEP 514, sin ejecutar nada); el final dio las versiones exactas; cero confirmaciones y violaciones; pins intactos. |
| 2 | system1697-dev-02 | passed | software.python.status completada y verificada sobre el registro de Windows (sin ejecutar nada); el final dio las versiones de Python registradas con sus cadenas exactas. | Turno ordinario: exactamente una software.python.status completada y verificada (instalaciones de Python registradas en Windows, PEP 514, sin ejecutar nada); el final dio las versiones exactas; cero confirmaciones y violaciones; pins intactos. |
| 3 | system1697-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | system1697-boundary-02 | failed | Límite fallido: cero operaciones, pero la respuesta no fue fiel o útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 91.83 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1655.39 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
