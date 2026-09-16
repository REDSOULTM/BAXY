# UI1735 — adjudicación de la raíz

## UI1735 — estado vigente 2026-09-16T17:37:42.662991+00:00

Parcial: 2 aprobados, 7 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 624/742 | 118 | 0 | >=508 | 11/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 508 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); UI1735 añade 0. No se cuentan revalidaciones.

Siguiente acción: UI1735: 9 ejecutados, 2 aprobados, 7 fallidos, 0 créditos (índices []); Bibliotecas y fichas de juegos y Interacción dentro de aplicaciones según los créditos. Siguiente: el diálogo de encendido del wifi (H0302) y las filas de Chrome/Spotify.

Evidencia: `artifacts/comprobaciones/C03/UI1735/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 217.06 s acumulados; pico GPU 3497.56 MiB; pico RAM 2108.33 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 9; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0432 | failed | Falló: la apertura o el clic no se verificaron o el final no fue fiel. | Turno revisado: app.open del cliente verificada; el clic aprobado terminó visible_button_not_found (la etiqueta no fue localizada en la ventana capturada dentro del plazo de espera); el final dijo que no pudo verificar la navegación. |
| 1 | H0290 | failed | Falló: la apertura o el clic no se verificaron o el final no fue fiel. | Turno revisado: app.open del cliente verificada; el clic aprobado terminó visible_button_not_found (la etiqueta no fue localizada en la ventana capturada dentro del plazo de espera); el final dijo que no pudo verificar la navegación. |
| 2 | H0636 | failed | Falló: la apertura o el clic no se verificaron o el final no fue fiel. | Turno revisado: app.open del cliente verificada; el clic aprobado terminó visible_button_not_found (la etiqueta no fue localizada en la ventana capturada dentro del plazo de espera); el final dijo que no pudo verificar la navegación. |
| 3 | ui1735-dev-01 | failed | Falló: la apertura o el clic no se verificaron o el final no fue fiel. | Turno revisado: app.open del cliente verificada; el clic aprobado terminó visible_button_not_found (la etiqueta no fue localizada en la ventana capturada dentro del plazo de espera); el final dijo que no pudo verificar la navegación. |
| 4 | ui1735-dev-02 | failed | Falló: la apertura o el clic no se verificaron o el final no fue fiel. | Turno revisado: app.open del cliente verificada; el clic aprobado terminó visible_button_not_found (la etiqueta no fue localizada en la ventana capturada dentro del plazo de espera); el final dijo que no pudo verificar la navegación. |
| 5 | ui1735-dev-03 | failed | Falló: la apertura o el clic no se verificaron o el final no fue fiel. | Turno revisado: app.open del cliente verificada; el clic aprobado terminó visible_button_not_found (la etiqueta no fue localizada en la ventana capturada dentro del plazo de espera); el final dijo que no pudo verificar la navegación. |
| 6 | ui1735-dev-04 | failed | Falló: la apertura o el clic no se verificaron o el final no fue fiel. | Turno revisado: app.open del cliente verificada; el clic aprobado terminó visible_button_not_found (la etiqueta no fue localizada en la ventana capturada dentro del plazo de espera); el final dijo que no pudo verificar la navegación. |
| 7 | ui1735-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 8 | ui1735-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 217.06 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2108.33 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
