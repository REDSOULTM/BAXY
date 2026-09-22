# AIRPLANE2045 — adjudicación de la raíz

## AIRPLANE2045 — estado vigente 2026-09-22T06:14:50.556191+00:00

Parcial: 4 aprobados, 2 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 674/742 | 68 | 0 | >=650 | 29/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 649 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); AIRPLANE2045 añade 1. No se cuentan revalidaciones.

Siguiente acción: AIRPLANE2045: 6 ejecutados, 4 aprobados, 2 fallidos, 1 créditos (índices [0]). Siguiente: las tipadas de descarga (imagen de portada, meme) y la presentación.

Evidencia: `artifacts/comprobaciones/C03/AIRPLANE2045/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 93.49 s acumulados; pico GPU 3485.56 MiB; pico RAM 1774.94 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 6; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0107 | passed | system.settings.set{airplane_mode} verificada por la API de radios; el final dice el estado leído; crédito con dos variantes aprobadas del mismo grupo. | Turno ordinario: exactamente una system.settings.set{airplane_mode} completada y verificada (radios apagadas o encendidas por la API de radios y releídas; el estado ya satisfecho se dice como estado); el final dice el estado leído; cero confirmaciones y violaciones; pins intactos. |
| 1 | airplane2045-dev-01 | passed | system.settings.set{airplane_mode} verificada por la API de radios; el final dice el estado leído. | Turno ordinario: exactamente una system.settings.set{airplane_mode} completada y verificada (radios apagadas o encendidas por la API de radios y releídas; el estado ya satisfecho se dice como estado); el final dice el estado leído; cero confirmaciones y violaciones; pins intactos. |
| 2 | airplane2045-dev-02 | failed | Falló: no cambió las radios, preguntó, o el final no dijo el estado leído. | Turno ordinario: el modo avión ya estaba quitado; el final lo dijo, pero no hubo efecto que verificar. |
| 3 | airplane2045-dev-03 | passed | system.settings.set{airplane_mode} verificada por la API de radios; el final dice el estado leído. | Turno ordinario: exactamente una system.settings.set{airplane_mode} completada y verificada (radios apagadas o encendidas por la API de radios y releídas; el estado ya satisfecho se dice como estado); el final dice el estado leído; cero confirmaciones y violaciones; pins intactos. |
| 4 | airplane2045-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 5 | airplane2045-boundary-02 | failed | Límite fallido: cero operaciones, pero la respuesta no fue fiel o útil. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 93.49 s de segmentos; pico GPU 3485.56 MiB; pico RAM 1774.94 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
