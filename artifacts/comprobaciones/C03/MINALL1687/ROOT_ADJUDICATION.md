# MINALL1687 — adjudicación de la raíz

## MINALL1687 — estado vigente 2026-09-16T07:31:03.108272+00:00

Parcial: 6 aprobados, 1 fallidos, 0 sin ejecutar; 2 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 606/742 | 136 | 0 | >=490 | 9/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 488 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); MINALL1687 añade 2. No se cuentan revalidaciones.

Siguiente acción: MINALL1687: 6 ejecutados, 6 aprobados, 0 fallidos, 2 créditos (índices [0, 1]); Abrir aplicaciones 48/54. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/MINALL1687/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 142.58 s acumulados; pico GPU 3497.56 MiB; pico RAM 2084.32 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 7; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0238 | passed | window.minimize.all completada y verificada sobre las ventanas del escritorio, ninguna cerrada; el final dijo que minimizó todas las ventanas; ventanas restauradas por la raíz; crédito con dos variantes aprobadas del mismo grupo. | Turno ordinario: exactamente una window.minimize.all completada y verificada (todas las ventanas visibles del escritorio minimizadas y releídas), ninguna cerrada; la raíz restauró las ventanas del dueño; cero confirmaciones y violaciones; pins intactos. |
| 1 | H0529 | passed | window.minimize.all completada y verificada sobre las ventanas del escritorio, ninguna cerrada; el final dijo que minimizó todas las ventanas; ventanas restauradas por la raíz; crédito con dos variantes aprobadas del mismo grupo. | Turno ordinario: exactamente una window.minimize.all completada y verificada (todas las ventanas visibles del escritorio minimizadas y releídas), ninguna cerrada; la raíz restauró las ventanas del dueño; cero confirmaciones y violaciones; pins intactos. |
| 2 | H0658 | failed | Falló: la operación no se completó o no se verificó, o el final no fue fiel. | Turno ordinario: la operación se completó y verificó, cero violaciones, pins intactos; ningún final fue publicado (los borradores usaron una palabra inventada y el veto los rechazó). |
| 3 | minall1687-dev-01 | passed | window.minimize.all completada y verificada sobre las ventanas del escritorio, ninguna cerrada; el final dijo que minimizó todas las ventanas; ventanas restauradas por la raíz. | Turno ordinario: exactamente una window.minimize.all completada y verificada (todas las ventanas visibles del escritorio minimizadas y releídas), ninguna cerrada; la raíz restauró las ventanas del dueño; cero confirmaciones y violaciones; pins intactos. |
| 4 | minall1687-dev-02 | passed | window.minimize.all completada y verificada sobre las ventanas del escritorio, ninguna cerrada; el final dijo que minimizó todas las ventanas; ventanas restauradas por la raíz. | Turno ordinario: exactamente una window.minimize.all completada y verificada (todas las ventanas visibles del escritorio minimizadas y releídas), ninguna cerrada; la raíz restauró las ventanas del dueño; cero confirmaciones y violaciones; pins intactos. |
| 5 | minall1687-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 6 | minall1687-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 142.58 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2084.32 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
