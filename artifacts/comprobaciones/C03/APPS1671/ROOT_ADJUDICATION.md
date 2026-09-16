# APPS1671 — adjudicación de la raíz

## APPS1671 — estado vigente 2026-09-16T04:23:47.833777+00:00

Parcial: 3 aprobados, 2 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 600/742 | 142 | 0 | >=474 | 8/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 474 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); APPS1671 añade 0. No se cuentan revalidaciones.

Siguiente acción: APPS1671: 6 ejecutados, 3 aprobados, 3 fallidos, 0 créditos (índices []); Abrir aplicaciones 46/54. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/APPS1671/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 107.92 s acumulados; pico GPU 3497.56 MiB; pico RAM 2284.19 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0322 | failed | Falló: la lectura no se completó o hubo una operación indebida, o el final no fue fiel. | Turno ordinario: cero violaciones; pins intactos; la lectura de presencia terminó ausente pero el narrador vetó sus tres borradores como afirmación de fallo y no hubo respuesta. |
| 1 | apps1671-dev-01 | passed | Lectura app.installed completada y verificada (ausente); el final dijo que el programa no está instalado sin abrir nada. | Turno ordinario: exactamente una app.installed de sólo lectura completada y verificada (ausente), ninguna apertura; el final dice que no está instalado; cero confirmaciones y violaciones; pins intactos. |
| 2 | apps1671-dev-02 | failed | Falló: la lectura no se completó o hubo una operación indebida, o el final no fue fiel. | Turno ordinario: cero violaciones; pins intactos; la lectura terminó ausente pero la aplicación rechazó la frase «cannot be opened» como resultado invertido y no hubo respuesta útil. |
| 3 | apps1671-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | apps1671-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 107.92 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2284.19 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
