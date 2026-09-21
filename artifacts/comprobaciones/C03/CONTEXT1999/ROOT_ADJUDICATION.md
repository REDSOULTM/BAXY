# CONTEXT1999 — adjudicación de la raíz

## CONTEXT1999 — estado vigente 2026-09-21T05:59:48.978896+00:00

Parcial: 2 aprobados, 6 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 652/742 | 90 | 0 | >=628 | 29/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 628 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); CONTEXT1999 añade 0. No se cuentan revalidaciones.

Siguiente acción: CONTEXT1999: 8 ejecutados, 2 aprobados, 6 fallidos, 0 créditos (índices []). Siguiente: cien-89 sobre BUILD1997 y las tandas de dos turnos (alarma de la sesión, ponle texto).

Evidencia: `artifacts/comprobaciones/C03/CONTEXT1999/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 201.15 s acumulados; pico GPU 3492.93 MiB; pico RAM 1867.77 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 8; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0263 | failed | Falló: preguntó, actuó sobre otra ventana o no miró la pantalla, o el final no fue fiel. | Turno ordinario sobre ventanas propias de la raíz: una window.resolve verificada y una window.focus fallida sobre una ventana de herramienta sin título; el final dijo que no pudo cambiar; pins intactos. |
| 1 | H0528 | failed | Falló: preguntó, actuó sobre otra ventana o no miró la pantalla, o el final no fue fiel. | Turno ordinario con el diálogo de la raíz delante: captura de toda la pantalla y lectura verificadas; el final citó líneas de otra ventana; pins intactos. |
| 2 | context1999-dev-01 | failed | Falló: preguntó, actuó sobre otra ventana o no miró la pantalla, o el final no fue fiel. | Turno ordinario sobre ventanas propias de la raíz: window.resolve y window.focus verificadas, pero sobre una ventana de herramienta sin título, no la de atrás; pins intactos. |
| 3 | context1999-dev-02 | failed | Falló: preguntó, actuó sobre otra ventana o no miró la pantalla, o el final no fue fiel. | Turno ordinario sobre ventanas propias de la raíz: window.resolve y window.focus verificadas sobre una ventana de herramienta sin título; el final dijo que ya estaba en la anterior; pins intactos. |
| 4 | context1999-dev-03 | failed | Falló: preguntó, actuó sobre otra ventana o no miró la pantalla, o el final no fue fiel. | Turno ordinario con el diálogo de la raíz delante: captura de toda la pantalla y lectura verificadas; el final citó líneas de otra ventana; pins intactos. |
| 5 | context1999-dev-04 | failed | Falló: preguntó, actuó sobre otra ventana o no miró la pantalla, o el final no fue fiel. | Turno ordinario con el diálogo de la raíz delante: captura de toda la pantalla y lectura verificadas; el final citó líneas de otra ventana; pins intactos. |
| 6 | context1999-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 7 | context1999-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 201.15 s de segmentos; pico GPU 3492.93 MiB; pico RAM 1867.77 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
