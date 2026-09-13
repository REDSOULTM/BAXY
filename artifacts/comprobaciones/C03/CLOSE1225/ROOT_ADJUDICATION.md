# CLOSE1225 — adjudicación de la raíz

## CLOSE1225 — estado vigente 2026-09-13T17:19:57.817066+00:00

Parcial: 9 aprobados, 4 fallidos, 0 sin ejecutar; 3 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 298/742 | 444 | 0 | >=172 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–13 septiembre: 169 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS), todas dentro de la ventana de 24 h al adjudicar; CLOSE1225 añade 3. No se cuentan revalidaciones.

Siguiente acción: CLOSE1225 completa: 13 ejecutados, 9 aprobados, 4 fallidos, 3 créditos (H0400 «cierra esta ventana», H0316 «cerrá esto», H0495 «cerrala»: cierre deíctico de la ventana en primer plano con los dos pares). H0148 y H0335 llegaron a la propuesta y la revisión raíz las rechazó por un criterio propio (sólo aceptaba window.resolve), corregido antes del índice 2: se remiden en la siguiente tanda. Prohibición con justificación: ya cerrada como conversación pero el compositor no reconoce la prohibición (constraint_ack sólo cubre aperturas). Límite futuro: el modelo sigue negando la capacidad. Cerrar apps queda 7/20.

Evidencia: `artifacts/comprobaciones/C03/CLOSE1225/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 447.64 s acumulados; pico GPU 3497.56 MiB; pico RAM 2359.96 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 13; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0148 | failed | El producto identificó la ventana y pidió confirmación; la revisión raíz la rechazó por un criterio propio ya corregido. | Petición publicada; una lectura verificada; sin aprobación ni cierre; ventana de prueba cerrada por raíz después; pins intactos. |
| 1 | H0335 | failed | El producto identificó la ventana y pidió confirmación; la revisión raíz la rechazó por un criterio propio ya corregido. | Petición publicada; una lectura verificada; sin aprobación ni cierre; ventana de prueba cerrada por raíz después; pins intactos. |
| 2 | H0400 | passed | Cerró la ventana en primer plano (propia) tras la aprobación revisada; dos pares aprobados. | Petición y final publicados; dos operaciones verificadas; una aprobación raíz; ventana ausente después; pins intactos. |
| 3 | H0316 | passed | Cerró la ventana en primer plano (propia) tras la aprobación revisada; dos pares aprobados. | Petición y final publicados; dos operaciones verificadas; una aprobación raíz; ventana ausente después; pins intactos. |
| 4 | H0495 | passed | Cerró la ventana en primer plano (propia) tras la aprobación revisada; dos pares aprobados. | Petición y final publicados; dos operaciones verificadas; una aprobación raíz; ventana ausente después; pins intactos. |
| 5 | H0407 | passed | Reconoció la prohibición sin cerrar nada; sin crédito por faltar un par. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 6 | H0427 | passed | Reconoció la prohibición sin cerrar nada; sin crédito por faltar un par. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 7 | close1225-dev-01 | passed | Variante original aprobada: cerró la ventana en primer plano tras la aprobación revisada. | Petición y final publicados; dos operaciones verificadas; una aprobación raíz; ventana ausente después; pins intactos. |
| 8 | close1225-dev-02 | passed | Variante original aprobada: cerró la ventana en primer plano tras la aprobación revisada. | Petición y final publicados; dos operaciones verificadas; una aprobación raíz; ventana ausente después; pins intactos. |
| 9 | close1225-dev-03 | failed | No cerró nada pero tampoco reconoció la prohibición. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 10 | close1225-dev-04 | passed | Variante original aprobada. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 11 | close1225-boundary-01 | failed | Límite fallido: negó una capacidad que sí tiene. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 12 | close1225-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 447.64 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2359.96 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
