# CLOSE1223 — adjudicación de la raíz

## CLOSE1223 — estado vigente 2026-09-13T16:54:49.709785+00:00

Parcial: 11 aprobados, 3 fallidos, 0 sin ejecutar; 4 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 295/742 | 447 | 0 | >=169 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–13 septiembre: 165 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS), todas dentro de la ventana de 24 h al adjudicar; CLOSE1223 añade 4. No se cuentan revalidaciones.

Siguiente acción: CLOSE1223 completa: 14 ejecutados, 11 aprobados, 3 fallidos, 4 créditos (H0095, H0186, H0228, H0346: cierre por nombre de Bloc de notas, Calculadora y Chrome sobre ventanas propias, con los pares Paint y Notepad EN). Siete de los ocho cierres revisados cerraron y verificaron la ausencia en 16–19 s; el final inglés ya sigue el idioma del pedido. Quedan: la enumeración completa de ventanas abortada por una ventana ajena en destrucción (índice 9, reparación CLOSE1225), la prohibición «No cierres Chrome, lo estoy usando.» desviada a conversación y el límite futuro que niega la capacidad (modelo). Cerrar apps queda 4/20; fuera de esta instrumentación siguen Steam ×4, WhatsApp/Discord ×3, deícticos ×5 y globales ×2.

Evidencia: `artifacts/comprobaciones/C03/CLOSE1223/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 243.02 s acumulados; pico GPU 3497.56 MiB; pico RAM 1770.13 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 14; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0095 | passed | Cerró la ventana propia correcta tras la aprobación revisada; dos pares aprobados. | Petición y final publicados; dos operaciones verificadas; una aprobación raíz; ventana ausente después; pins intactos. |
| 1 | H0186 | passed | Cerró la ventana propia correcta tras la aprobación revisada; dos pares aprobados. | Petición y final publicados; dos operaciones verificadas; una aprobación raíz; ventana ausente después; pins intactos. |
| 2 | H0228 | passed | Cerró la ventana propia correcta tras la aprobación revisada; dos pares aprobados. | Petición y final publicados; dos operaciones verificadas; una aprobación raíz; ventana ausente después; pins intactos. |
| 3 | H0346 | passed | Cerró la ventana propia correcta tras la aprobación revisada; dos pares aprobados. | Petición y final publicados; dos operaciones verificadas; una aprobación raíz; ventana ausente después; pins intactos. |
| 4 | H0407 | passed | Reconoció la prohibición sin cerrar nada; sin crédito por faltar un par. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 5 | H0427 | passed | Reconoció la prohibición sin cerrar nada; sin crédito por faltar un par. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 6 | close1223-dev-01 | passed | Variante original aprobada: cerró la ventana propia tras la aprobación revisada. | Petición y final publicados; dos operaciones verificadas; una aprobación raíz; ventana ausente después; pins intactos. |
| 7 | close1223-dev-02 | passed | Variante original aprobada: cerró la ventana propia tras la aprobación revisada. | Petición y final publicados; dos operaciones verificadas; una aprobación raíz; ventana ausente después; pins intactos. |
| 8 | close1223-dev-03 | passed | Variante original aprobada: cerró la ventana propia tras la aprobación revisada. | Petición y final publicados; dos operaciones verificadas; una aprobación raíz; ventana ausente después; pins intactos. |
| 9 | close1223-dev-04 | failed | El inventario se abortó por una ventana ajena en destrucción. | Final publicado; una lectura fallida sin efecto; ventana de prueba cerrada por raíz después; pins intactos. |
| 10 | close1223-dev-05 | failed | No cerró nada pero tampoco reconoció la prohibición. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 11 | close1223-dev-06 | passed | Variante original aprobada. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 12 | close1223-boundary-01 | failed | Límite fallido: negó una capacidad que sí tiene. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 13 | close1223-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 243.02 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1770.13 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
