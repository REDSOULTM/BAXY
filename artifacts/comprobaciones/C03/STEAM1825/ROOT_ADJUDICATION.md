# STEAM1825 — adjudicación de la raíz

## STEAM1825 — estado vigente 2026-09-17T06:44:12.477082+00:00

Parcial: 5 aprobados, 0 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 648/742 | 94 | 0 | >=532 | 14/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 531 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); STEAM1825 añade 1. No se cuentan revalidaciones.

Siguiente acción: STEAM1825: 5 ejecutados, 5 aprobados, 0 fallidos, 1 créditos (índices [0]); Instalar y desinstalar software 29/31. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/STEAM1825/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 86.58 s acumulados; pico GPU 3497.56 MiB; pico RAM 1728.45 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0571 | passed | game.entitlement.named completada y verificada sobre la biblioteca autenticada de Steam (nada descargado ni comprado); el final dijo el estado leído del juego nombrado por la persona; crédito con dos variantes aprobadas del mismo grupo. | Turno ordinario: exactamente una game.entitlement.named completada y verificada (biblioteca autenticada de Steam; nada descargado, comprado ni abierto); el final dijo el estado leído del juego nombrado como la persona lo nombró; cero confirmaciones y violaciones; pins intactos. |
| 1 | steam1825-dev-01 | passed | game.entitlement.named completada y verificada sobre la biblioteca autenticada de Steam (nada descargado ni comprado); el final dijo el estado leído del juego nombrado por la persona. | Turno ordinario: exactamente una game.entitlement.named completada y verificada (biblioteca autenticada de Steam; nada descargado, comprado ni abierto); el final dijo el estado leído del juego nombrado como la persona lo nombró; cero confirmaciones y violaciones; pins intactos. |
| 2 | steam1825-dev-02 | passed | game.entitlement.named completada y verificada sobre la biblioteca autenticada de Steam (nada descargado ni comprado); el final dijo el estado leído del juego nombrado por la persona. | Turno ordinario: exactamente una game.entitlement.named completada y verificada (biblioteca autenticada de Steam; nada descargado, comprado ni abierto); el final dijo el estado leído del juego nombrado como la persona lo nombró; cero confirmaciones y violaciones; pins intactos. |
| 3 | steam1825-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | steam1825-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 86.58 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1728.45 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
