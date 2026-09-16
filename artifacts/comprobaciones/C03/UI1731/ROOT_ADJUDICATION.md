# UI1731 — adjudicación de la raíz

## UI1731 — estado vigente 2026-09-16T16:52:33.757155+00:00

Parcial: 5 aprobados, 3 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 622/742 | 120 | 0 | >=506 | 10/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 505 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); UI1731 añade 1. No se cuentan revalidaciones.

Siguiente acción: UI1731: 8 ejecutados, 5 aprobados, 3 fallidos, 1 créditos (índices [0]); Bibliotecas y fichas de juegos 4/6. Siguiente: cerrar todo salvo VS Code (H0467/H0484) y el diálogo de encendido del wifi (H0302).

Evidencia: `artifacts/comprobaciones/C03/UI1731/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 225.42 s acumulados; pico GPU 3497.56 MiB; pico RAM 2453.79 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 8; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0559 | passed | Abrió el cliente de juegos, hizo clic en «Biblioteca» sobre su ventana (localizada por OCR, superficie cambiada) y lo dijo; crédito con dos variantes aprobadas del mismo cliente. | Turno revisado: app.open del cliente completada y verificada (paso ordinario; el Steam del dueño se reutiliza y la raíz lo devuelve a su estado, Epic lo abre el producto y la raíz lo cierra) y luego input.visible.click completado y verificado (UIA sin controles, OCR localiza «Biblioteca», superficie cambiada) sobre la ventana del cliente; una confirmación aprobada por la raíz sólo con esa etiqueta y con el cliente en primer plano; cero violaciones; pins intactos. |
| 1 | H0432 | failed | Falló: la apertura o el clic no se verificaron o el final no fue fiel. | Turno revisado: app.open del Epic Games Launcher verificada; input.visible.click aprobado por la raíz terminó visible_button_not_found (la etiqueta no fue localizada en la ventana recién abierta); el final dijo que no pudo verificar la navegación. |
| 2 | ui1731-dev-01 | passed | Abrió el cliente de juegos, hizo clic en «Biblioteca» sobre su ventana (localizada por OCR, superficie cambiada) y lo dijo. | Turno revisado: app.open del cliente completada y verificada (paso ordinario; el Steam del dueño se reutiliza y la raíz lo devuelve a su estado, Epic lo abre el producto y la raíz lo cierra) y luego input.visible.click completado y verificado (UIA sin controles, OCR localiza «Biblioteca», superficie cambiada) sobre la ventana del cliente; una confirmación aprobada por la raíz sólo con esa etiqueta y con el cliente en primer plano; cero violaciones; pins intactos. |
| 3 | ui1731-dev-02 | passed | Abrió el cliente de juegos, hizo clic en «Biblioteca» sobre su ventana (localizada por OCR, superficie cambiada) y lo dijo. | Turno revisado: app.open del cliente completada y verificada (paso ordinario; el Steam del dueño se reutiliza y la raíz lo devuelve a su estado, Epic lo abre el producto y la raíz lo cierra) y luego input.visible.click completado y verificado (UIA sin controles, OCR localiza «Biblioteca», superficie cambiada) sobre la ventana del cliente; una confirmación aprobada por la raíz sólo con esa etiqueta y con el cliente en primer plano; cero violaciones; pins intactos. |
| 4 | ui1731-dev-03 | failed | Falló: la apertura o el clic no se verificaron o el final no fue fiel. | Turno revisado: app.open del Epic Games Launcher verificada; el clic aprobado terminó visible_button_not_found; el final dijo que no pudo verificar la navegación. |
| 5 | ui1731-dev-04 | failed | Falló: la apertura o el clic no se verificaron o el final no fue fiel. | Turno revisado: app.open del Epic Games Launcher verificada; el clic aprobado terminó visible_button_not_found; el final dijo que no pudo verificar la navegación. |
| 6 | ui1731-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 7 | ui1731-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 225.42 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2453.79 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
