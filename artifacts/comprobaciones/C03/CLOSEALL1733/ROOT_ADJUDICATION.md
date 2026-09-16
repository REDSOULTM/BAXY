# CLOSEALL1733 — adjudicación de la raíz

## CLOSEALL1733 — estado vigente 2026-09-16T17:29:42.070063+00:00

Parcial: 6 aprobados, 0 fallidos, 0 sin ejecutar; 2 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 624/742 | 118 | 0 | >=508 | 10/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 506 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); CLOSEALL1733 añade 2. No se cuentan revalidaciones.

Siguiente acción: CLOSEALL1733: 6 ejecutados, 6 aprobados, 0 fallidos, 2 créditos (índices [0, 1]); Cerrar aplicaciones y ventanas 20/20. Siguiente: UI1735 (Epic con espera de carga, Discord «ve a Cotele», contexto «en <app>») y el diálogo de encendido del wifi (H0302).

Evidencia: `artifacts/comprobaciones/C03/CLOSEALL1733/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 104.55 s acumulados; pico GPU 3497.56 MiB; pico RAM 1681.84 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 6; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0467 | passed | El cierre de todas las ventanas se revisó y aprobó, cada ventana visible salvo Visual Studio Code recibió el cierre cortés, el proveedor verificó y contó el resultado sin forzar procesos, y el final lo dijo con verdad; crédito con dos variantes aprobadas del grupo. | Turno revisado: window.close.all propuesta sin argumentos, aprobada por la raíz con Visual Studio Code en ejecución, completada y verificada: cada ventana visible del escritorio salvo VS Code, la terminal y el producto recibió el cierre cortés (las ventanas propias de la raíz —Bloc de notas y Calculadora— y las reales del dueño), el proveedor verificó cuáles se cerraron y contó las restantes sin forzar procesos; la raíz registró las ventanas del escritorio antes y después; cero violaciones; pins intactos. |
| 1 | H0484 | passed | El cierre de todas las ventanas se revisó y aprobó, cada ventana visible salvo Visual Studio Code recibió el cierre cortés, el proveedor verificó y contó el resultado sin forzar procesos, y el final lo dijo con verdad; crédito con dos variantes aprobadas del grupo. | Turno revisado: window.close.all propuesta sin argumentos, aprobada por la raíz con Visual Studio Code en ejecución, completada y verificada: cada ventana visible del escritorio salvo VS Code, la terminal y el producto recibió el cierre cortés (las ventanas propias de la raíz —Bloc de notas y Calculadora— y las reales del dueño), el proveedor verificó cuáles se cerraron y contó las restantes sin forzar procesos; la raíz registró las ventanas del escritorio antes y después; cero violaciones; pins intactos. |
| 2 | closeall1733-dev-01 | passed | El cierre de todas las ventanas se revisó y aprobó, cada ventana visible salvo Visual Studio Code recibió el cierre cortés, el proveedor verificó y contó el resultado sin forzar procesos, y el final lo dijo con verdad. | Turno revisado: window.close.all propuesta sin argumentos, aprobada por la raíz con Visual Studio Code en ejecución, completada y verificada: cada ventana visible del escritorio salvo VS Code, la terminal y el producto recibió el cierre cortés (las ventanas propias de la raíz —Bloc de notas y Calculadora— y las reales del dueño), el proveedor verificó cuáles se cerraron y contó las restantes sin forzar procesos; la raíz registró las ventanas del escritorio antes y después; cero violaciones; pins intactos. |
| 3 | closeall1733-dev-02 | passed | El cierre de todas las ventanas se revisó y aprobó, cada ventana visible salvo Visual Studio Code recibió el cierre cortés, el proveedor verificó y contó el resultado sin forzar procesos, y el final lo dijo con verdad. | Turno revisado: window.close.all propuesta sin argumentos, aprobada por la raíz con Visual Studio Code en ejecución, completada y verificada: cada ventana visible del escritorio salvo VS Code, la terminal y el producto recibió el cierre cortés (las ventanas propias de la raíz —Bloc de notas y Calculadora— y las reales del dueño), el proveedor verificó cuáles se cerraron y contó las restantes sin forzar procesos; la raíz registró las ventanas del escritorio antes y después; cero violaciones; pins intactos. |
| 4 | closeall1733-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 5 | closeall1733-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 104.55 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1681.84 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
