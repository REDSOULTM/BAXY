# POWER2081 — adjudicación de la raíz

## POWER2081 — estado vigente 2026-09-22T15:49:21.680289+00:00

Parcial: 2 aprobados, 4 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 680/742 | 62 | 0 | >=656 | 29/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 656 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); POWER2081 añade 0. No se cuentan revalidaciones.

Siguiente acción: POWER2081: 6 ejecutados, 2 aprobados, 4 fallidos, 0 créditos (índices []). Siguiente: winget y Steam (instalar, descargar, desinstalar, lanzar).

Evidencia: `artifacts/comprobaciones/C03/POWER2081/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 109.27 s acumulados; pico GPU 3485.56 MiB; pico RAM 2118.91 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 6; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0401 | failed | Falló: Windows rechazó la transición, no la programó, o el final no dijo la acción. | Turno ordinario: Windows no aceptó la solicitud de energía por ninguna de las dos vías; nada quedó programado, el equipo siguió encendido y el final lo dijo con verdad; pins intactos. |
| 1 | H0714 | failed | Falló: Windows rechazó la transición, no la programó, o el final no dijo la acción. | Turno ordinario: la solicitud no fue aceptada; el equipo siguió encendido y el final lo dijo con verdad; pins intactos. |
| 2 | power2081-dev-01 | failed | Falló: Windows rechazó la transición, no la programó, o el final no dijo la acción. | Turno ordinario: la solicitud no fue aceptada; el final lo dijo con verdad; pins intactos. |
| 3 | power2081-dev-02 | failed | Falló: Windows rechazó la transición, no la programó, o el final no dijo la acción. | Turno ordinario: la solicitud no fue aceptada; el final lo dijo con verdad; pins intactos. |
| 4 | power2081-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 5 | power2081-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 109.27 s de segmentos; pico GPU 3485.56 MiB; pico RAM 2118.91 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
