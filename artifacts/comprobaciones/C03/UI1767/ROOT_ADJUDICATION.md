# UI1767 — adjudicación de la raíz

## UI1767 — estado vigente 2026-09-16T23:27:34.367844+00:00

Parcial: 3 aprobados, 2 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 634/742 | 108 | 0 | >=518 | 12/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 518 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); UI1767 añade 0. No se cuentan revalidaciones.

Siguiente acción: UI1767: 5 ejecutados, 3 aprobados, 2 fallidos, 0 créditos (índices []); Bibliotecas y fichas de juegos 4/6. Siguiente: Discord (navegación por buscador) y diálogos de Steam (captura + clic).

Evidencia: `artifacts/comprobaciones/C03/UI1767/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 178.48 s acumulados; pico GPU 3497.56 MiB; pico RAM 2465.89 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0432 | passed | Abrió el cliente, hizo clic en la sección o canal pedido sobre su ventana (etiqueta localizada por OCR tras esperar la carga, superficie cambiada) y lo dijo. | Turno revisado: app.open del cliente completada y verificada (paso ordinario; Epic o Discord abiertos por el producto y cerrados por la raíz después) y luego input.visible.click completado y verificado (UIA sin controles útiles, OCR localiza la etiqueta tras esperar la carga, superficie cambiada) sobre la ventana del cliente; una confirmación aprobada por la raíz sólo con esa etiqueta y con el cliente en primer plano; cero violaciones; pins intactos. |
| 1 | ui1767-dev-01 | failed | Falló: la apertura o el clic no se verificaron o el final no fue fiel. | Turno revisado: app.open del launcher completada y verificada; clic aprobado por la raíz pero terminado visible_button_not_found tras la espera de carga; final que no afirma la navegación; cero violaciones; pins intactos. |
| 2 | ui1767-dev-02 | failed | Falló: la apertura o el clic no se verificaron o el final no fue fiel. | Turno revisado: app.open del launcher completada y verificada; clic aprobado por la raíz pero terminado visible_button_not_found tras la espera de carga; final que no afirma la navegación; cero violaciones; pins intactos. |
| 3 | ui1767-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | ui1767-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 178.48 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2465.89 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
