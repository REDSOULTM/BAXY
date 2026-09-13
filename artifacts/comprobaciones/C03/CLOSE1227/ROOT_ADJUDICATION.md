# CLOSE1227 — adjudicación de la raíz

## CLOSE1227 — estado vigente 2026-09-13T17:27:36.587834+00:00

Parcial: 9 aprobados, 1 fallidos, 0 sin ejecutar; 4 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 302/742 | 440 | 0 | >=176 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–13 septiembre: 172 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS), todas dentro de la ventana de 24 h al adjudicar; CLOSE1227 añade 4. No se cuentan revalidaciones.

Siguiente acción: CLOSE1227 completa: 10 ejecutados, 9 aprobados, 1 fallido (límite futuro, modelo), 4 créditos (H0148 «cerrá la ventana actual», H0335 «cerrá esta ventana», H0407 «nunca cierres spotify», H0427 «no cierres spotify») con sus dos pares cada uno. Cerrar apps queda 11/20. Quedan fuera de esta instrumentación y documentados: Steam ×4 (H0117, H0677, H0679, H0556: cerrar Steam puede cancelar descargas ajenas; sin ventana propia posible), WhatsApp ×2 y Discord ×1 (H0546, H0112, H0693: el instrumento exige clientes de mensajería ausentes y sus ventanas son sesiones del dueño), globales ×2 (H0467 «cerrame todo», H0484 «cerrá todas las ventanas»: cierre múltiple de ventanas ajenas, sin alcance seguro). Siguiente por masa: otra categoría.

Evidencia: `artifacts/comprobaciones/C03/CLOSE1227/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 164.86 s acumulados; pico GPU 3497.56 MiB; pico RAM 1877.21 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 10; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0148 | passed | Cerró la ventana en primer plano (propia) tras la aprobación revisada; dos pares aprobados. | Petición y final publicados; dos operaciones verificadas; una aprobación raíz; ventana ausente después; pins intactos. |
| 1 | H0335 | passed | Cerró la ventana en primer plano (propia) tras la aprobación revisada; dos pares aprobados. | Petición y final publicados; dos operaciones verificadas; una aprobación raíz; ventana ausente después; pins intactos. |
| 2 | H0407 | passed | Reconoció la prohibición sin cerrar nada; dos pares aprobados. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 3 | H0427 | passed | Reconoció la prohibición sin cerrar nada; dos pares aprobados. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | close1227-dev-01 | passed | Variante original aprobada: cerró la ventana en primer plano tras la aprobación revisada. | Petición y final publicados; dos operaciones verificadas; una aprobación raíz; ventana ausente después; pins intactos. |
| 5 | close1227-dev-02 | passed | Variante original aprobada: cerró la ventana en primer plano tras la aprobación revisada. | Petición y final publicados; dos operaciones verificadas; una aprobación raíz; ventana ausente después; pins intactos. |
| 6 | close1227-dev-03 | passed | Variante original aprobada. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 7 | close1227-dev-04 | passed | Variante original aprobada. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 8 | close1227-boundary-01 | failed | Límite fallido: negó una capacidad que sí tiene. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 9 | close1227-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 164.86 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1877.21 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
