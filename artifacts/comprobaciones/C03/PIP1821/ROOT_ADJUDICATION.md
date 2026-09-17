# PIP1821 — adjudicación de la raíz

## PIP1821 — estado vigente 2026-09-17T06:23:51.007797+00:00

Parcial: 5 aprobados, 0 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 646/742 | 96 | 0 | >=530 | 14/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 529 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); PIP1821 añade 1. No se cuentan revalidaciones.

Siguiente acción: PIP1821: 5 ejecutados, 5 aprobados, 0 fallidos, 1 créditos (índices [0]); Abrir aplicaciones 51/54. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/PIP1821/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 94.83 s acumulados; pico GPU 3497.56 MiB; pico RAM 1749.42 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0052 | passed | software.python.package.status completada y verificada (pip show en cada Python registrado, nada instalado); el final dijo si el paquete ya está instalado y en qué versiones de Python con sus cadenas exactas; crédito con dos variantes aprobadas del mismo grupo. | Turno ordinario: exactamente una software.python.package.status completada y verificada (pip show en cada Python registrado en Windows, nada instalado); el final dijo si el paquete está instalado y en qué versiones de Python con sus cadenas exactas; cero confirmaciones y violaciones; pins intactos. |
| 1 | pip1821-dev-01 | passed | software.python.package.status completada y verificada (pip show en cada Python registrado, nada instalado); el final dijo si el paquete ya está instalado y en qué versiones de Python con sus cadenas exactas. | Turno ordinario: exactamente una software.python.package.status completada y verificada (pip show en cada Python registrado en Windows, nada instalado); el final dijo si el paquete está instalado y en qué versiones de Python con sus cadenas exactas; cero confirmaciones y violaciones; pins intactos. |
| 2 | pip1821-dev-02 | passed | software.python.package.status completada y verificada (pip show en cada Python registrado, nada instalado); el final dijo si el paquete ya está instalado y en qué versiones de Python con sus cadenas exactas. | Turno ordinario: exactamente una software.python.package.status completada y verificada (pip show en cada Python registrado en Windows, nada instalado); el final dijo si el paquete está instalado y en qué versiones de Python con sus cadenas exactas; cero confirmaciones y violaciones; pins intactos. |
| 3 | pip1821-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | pip1821-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 94.83 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1749.42 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
