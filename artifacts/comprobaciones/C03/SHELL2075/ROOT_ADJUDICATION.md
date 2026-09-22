# SHELL2075 — adjudicación de la raíz

## SHELL2075 — estado vigente 2026-09-22T13:59:29.509486+00:00

Parcial: 5 aprobados, 3 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 679/742 | 63 | 0 | >=655 | 29/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 654 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); SHELL2075 añade 1. No se cuentan revalidaciones.

Siguiente acción: SHELL2075: 8 ejecutados, 5 aprobados, 3 fallidos, 1 créditos (índices [0]). Siguiente: energía del sistema y las de winget/Steam.

Evidencia: `artifacts/comprobaciones/C03/SHELL2075/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 136.28 s acumulados; pico GPU 3485.56 MiB; pico RAM 2422.63 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 8; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0048 | passed | shell.command.run verificada en carpeta propia o conocida; el final cita la salida real; crédito con dos variantes aprobadas del mismo grupo. | Turno ordinario: exactamente una shell.command.run completada y verificada (comando corrido en la carpeta propia del producto o en la carpeta conocida nombrada, salida y código observados); el final cita el resultado real; cero confirmaciones y violaciones; pins intactos. |
| 1 | H0245 | failed | Falló: no corrió el comando, corrió en otra carpeta, o el final inventó la salida. | Turno ordinario: el comando corrió y se verificó (sin salida); el final que lo decía no se pudo publicar; pins intactos. Reparación en el commit siguiente. |
| 2 | shell2075-dev-01 | failed | Falló: no corrió el comando, corrió en otra carpeta, o el final inventó la salida. | Turno ordinario: cero operaciones; la orden se leyó como pregunta; pins intactos. Corpus de la Fase 3.5. |
| 3 | shell2075-dev-02 | passed | shell.command.run verificada en carpeta propia o conocida; el final cita la salida real. | Turno ordinario: exactamente una shell.command.run completada y verificada (comando corrido en la carpeta propia del producto o en la carpeta conocida nombrada, salida y código observados); el final cita el resultado real; cero confirmaciones y violaciones; pins intactos. |
| 4 | shell2075-dev-03 | failed | Falló: no corrió el comando, corrió en otra carpeta, o el final inventó la salida. | Turno ordinario: el comando corrió y se verificó en la carpeta nombrada; el final no dice lo que salió; pins intactos. |
| 5 | shell2075-dev-04 | passed | shell.command.run verificada en carpeta propia o conocida; el final cita la salida real. | Turno ordinario: exactamente una shell.command.run completada y verificada (comando corrido en la carpeta propia del producto o en la carpeta conocida nombrada, salida y código observados); el final cita el resultado real; cero confirmaciones y violaciones; pins intactos. |
| 6 | shell2075-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 7 | shell2075-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 136.28 s de segmentos; pico GPU 3485.56 MiB; pico RAM 2422.63 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
