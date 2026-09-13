# CLOSE1221 — adjudicación de la raíz

## CLOSE1221 — estado vigente 2026-09-13T16:41:19.562318+00:00

Parcial: 6 aprobados, 8 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 291/742 | 451 | 0 | >=165 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–13 septiembre: 165 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS), todas dentro de la ventana de 24 h al adjudicar; CLOSE1221 no añade ninguna. No se cuentan revalidaciones.

Siguiente acción: CLOSE1221 completa: 14 ejecutados, 6 aprobados, 8 fallidos, 0 créditos. Progreso: la Calculadora alojada por ApplicationFrameHost ya se resuelve (índice 1 llegó a la propuesta; la revisión raíz la rechazó por un criterio propio corregido en la sesión); Chrome tiene identidad ejecutable pero el inventario fuerte clásico se aborta al leer MainModule de un proceso elevado ajeno (reproducido con la sonda invprobe); la Calculadora EN falló por el mismo aborto en la vía empaquetada; el idioma del final inglés sigue en español porque las respuestas de plan de la mente no llevan responseLanguage. Siguiente: CLOSE1223 (BUILD1223: procesos no candidatos ignorados en el inventario fuerte; mente: idioma en respuestas de plan) con los mismos 14 objetos.

Evidencia: `artifacts/comprobaciones/C03/CLOSE1221/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 379.05 s acumulados; pico GPU 3497.56 MiB; pico RAM 2347.84 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 14; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0095 | passed | Cerró la ventana propia correcta tras la aprobación revisada; sin crédito por faltar el segundo par. | Petición y final publicados; dos operaciones verificadas; una aprobación raíz; ventana ausente después; pins intactos. |
| 1 | H0186 | failed | El producto identificó la ventana y pidió confirmación; la revisión raíz la rechazó por un criterio propio ya corregido. | Petición publicada; una lectura verificada; sin aprobación ni cierre; ventana de prueba cerrada por raíz después; pins intactos. |
| 2 | H0228 | failed | El inventario fuerte se abortó al no poder leer un proceso elevado ajeno. | Final publicado; una lectura fallida sin efecto; ventana de prueba cerrada por raíz después; pins intactos. |
| 3 | H0346 | failed | El inventario fuerte se abortó al no poder leer un proceso elevado ajeno. | Final publicado; una lectura fallida sin efecto; ventana de prueba cerrada por raíz después; pins intactos. |
| 4 | H0407 | passed | Reconoció la prohibición sin cerrar nada; sin crédito por faltar un par. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 5 | H0427 | passed | Reconoció la prohibición sin cerrar nada; sin crédito por faltar un par. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 6 | close1221-dev-01 | passed | Variante original aprobada: cerró la ventana propia tras la aprobación revisada. | Petición y final publicados; dos operaciones verificadas; una aprobación raíz; ventana ausente después; pins intactos. |
| 7 | close1221-dev-02 | failed | Cerró la ventana correcta pero respondió en español a un pedido en inglés. | Petición y final publicados; dos operaciones verificadas; una aprobación raíz; ventana ausente después; pins intactos. |
| 8 | close1221-dev-03 | failed | El inventario fuerte se abortó al no poder leer un proceso elevado ajeno. | Final publicado; una lectura fallida sin efecto; ventana de prueba cerrada por raíz después; pins intactos. |
| 9 | close1221-dev-04 | failed | El inventario fuerte se abortó por un proceso ajeno no legible. | Final publicado; una lectura fallida sin efecto; ventana de prueba cerrada por raíz después; pins intactos. |
| 10 | close1221-dev-05 | failed | No cerró nada pero tampoco reconoció la prohibición. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 11 | close1221-dev-06 | passed | Variante original aprobada. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 12 | close1221-boundary-01 | failed | Límite fallido: negó una capacidad que sí tiene. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 13 | close1221-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 379.05 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2347.84 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
