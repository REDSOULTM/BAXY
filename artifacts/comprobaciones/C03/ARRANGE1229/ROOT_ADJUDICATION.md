# ARRANGE1229 — adjudicación de la raíz

## ARRANGE1229 — estado vigente 2026-09-13T17:51:14.435188+00:00

Parcial: 9 aprobados, 0 fallidos, 0 sin ejecutar; 3 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 305/742 | 437 | 0 | >=179 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–13 septiembre: 176 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS), todas dentro de la ventana de 24 h al adjudicar; ARRANGE1229 añade 3. No se cuentan revalidaciones.

Siguiente acción: ARRANGE1229 completa: 9 ejecutados, 9 aprobados, 3 créditos (H0291 «maximizá la ventana», H0681 «maximiza la ventana actual», H0628 «minimizá esta ventana») con sus dos pares cada uno. Organizar ventanas queda 3/13. Quedan fuera de esta instrumentación y documentados: minimizar todo ×3 (H0238, H0529, H0658: ventanas ajenas del dueño), «traé chrome al frente» (H0525: window.focus desde otro proceso no garantiza el primer plano, efecto incierto), «Minimisa ópera.» (H0697: Opera GX del dueño), «poné chrome a la izquierda» (H0268: window.move sin geometría definida), «cambiá a la otra ventana» y «enfocá la mejor» ×2 (H0263, H0392, H0527: referente indeterminado), «cerrá todas las pestañas de chrome» (H0444: sin browser.control de pestañas). Siguiente por masa: otra categoría.

Evidencia: `artifacts/comprobaciones/C03/ARRANGE1229/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 148.20 s acumulados; pico GPU 3497.56 MiB; pico RAM 1631.00 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 9; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0291 | passed | Cambió el estado de la ventana en primer plano (propia) a maximized; dos pares aprobados. | Final publicado; dos operaciones verificadas (window.active y la mutación); cero confirmaciones y violaciones; estado de la ventana propia comprobado por raíz después; pins intactos. |
| 1 | H0681 | passed | Cambió el estado de la ventana en primer plano (propia) a maximized; dos pares aprobados. | Final publicado; dos operaciones verificadas (window.active y la mutación); cero confirmaciones y violaciones; estado de la ventana propia comprobado por raíz después; pins intactos. |
| 2 | H0628 | passed | Cambió el estado de la ventana en primer plano (propia) a minimized; dos pares aprobados. | Final publicado; dos operaciones verificadas (window.active y la mutación); cero confirmaciones y violaciones; estado de la ventana propia comprobado por raíz después; pins intactos. |
| 3 | arrange1229-dev-01 | passed | Variante original aprobada: la ventana en primer plano (propia) quedó maximized. | Final publicado; dos operaciones verificadas (window.active y la mutación); cero confirmaciones y violaciones; estado de la ventana propia comprobado por raíz después; pins intactos. |
| 4 | arrange1229-dev-02 | passed | Variante original aprobada: la ventana en primer plano (propia) quedó maximized. | Final publicado; dos operaciones verificadas (window.active y la mutación); cero confirmaciones y violaciones; estado de la ventana propia comprobado por raíz después; pins intactos. |
| 5 | arrange1229-dev-03 | passed | Variante original aprobada: la ventana en primer plano (propia) quedó minimized. | Final publicado; dos operaciones verificadas (window.active y la mutación); cero confirmaciones y violaciones; estado de la ventana propia comprobado por raíz después; pins intactos. |
| 6 | arrange1229-dev-04 | passed | Variante original aprobada: la ventana en primer plano (propia) quedó minimized. | Final publicado; dos operaciones verificadas (window.active y la mutación); cero confirmaciones y violaciones; estado de la ventana propia comprobado por raíz después; pins intactos. |
| 7 | arrange1229-boundary-01 | passed | Límite aprobado: respuesta informativa sin efecto. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 8 | arrange1229-boundary-02 | passed | Límite aprobado: reconoció la prohibición sin efecto. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 148.20 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1631.00 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
