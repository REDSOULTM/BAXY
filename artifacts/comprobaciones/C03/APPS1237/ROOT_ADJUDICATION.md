# APPS1237 — adjudicación de la raíz

## APPS1237 — estado vigente 2026-09-13T18:44:36.087650+00:00

Parcial: 11 aprobados, 0 fallidos, 0 sin ejecutar; 5 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 315/742 | 427 | 0 | >=189 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–13 septiembre: 184 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS), todas dentro de la ventana de 24 h al adjudicar; APPS1237 añade 5. No se cuentan revalidaciones.

Siguiente acción: APPS1237 completa: 11 ejecutados, 11 aprobados, 5 créditos (H0151 «abrí el explorador de archivos», H0147 «open the file explorer», H0289 «abrime el photoshop», H0558 «abri photoshop», H0691 «no, mejor abrí firefox») con sus dos pares. Abrir aplicaciones queda 39/54. Quedan con causa: compuesto H0183 (final omite la apertura; composición), Steam ×3 y erratas ×4 (cliente del dueño / aclaración con contexto), Mortal Kombat ×2 (juego ausente), H0249 (indeterminado), H0461 (límite sin marca), idiomas ×3 (sin marca). Intentos previos preservados: APPS1233 (7 casos, criterio sin ventana previa) y APPS1235 (2 casos del Explorador sobre BUILD1233, identidad por prefijo de título). Siguiente por masa: otra categoría.

Evidencia: `artifacts/comprobaciones/C03/APPS1237/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 171.20 s acumulados; pico GPU 3497.56 MiB; pico RAM 1580.63 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 11; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0151 | passed | Trajo al frente el Explorador ya abierto, verificado y dicho; dos pares aprobados. | Final publicado; app.open completada y verificada (alreadyRunning true: la ventana del Explorador del dueño, minimizada, restaurada y al frente); cero confirmaciones y violaciones; raíz devolvió esa ventana a minimizada, sin cerrarla; pins intactos. |
| 1 | H0147 | passed | Trajo al frente el Explorador ya abierto, verificado y dicho; dos pares aprobados. | Final publicado; app.open completada y verificada (alreadyRunning true: la ventana del Explorador del dueño, minimizada, restaurada y al frente); cero confirmaciones y violaciones; raíz devolvió esa ventana a minimizada, sin cerrarla; pins intactos. |
| 2 | H0289 | passed | Comprobó el catálogo y dijo que no está instalado; dos pares aprobados. | Final publicado; una lectura app.installed completada y verificada con installed=false; ninguna apertura; cero confirmaciones y violaciones; pins intactos. |
| 3 | H0558 | passed | Comprobó el catálogo y dijo que no está instalado; dos pares aprobados. | Final publicado; una lectura app.installed completada y verificada con installed=false; ninguna apertura; cero confirmaciones y violaciones; pins intactos. |
| 4 | H0691 | passed | Comprobó el catálogo y dijo que no está instalado; dos pares aprobados. | Final publicado; una lectura app.installed completada y verificada con installed=false; ninguna apertura; cero confirmaciones y violaciones; pins intactos. |
| 5 | apps1237-dev-01 | passed | Variante original aprobada: Explorador ya abierto traído al frente, verificado y dicho. | Final publicado; app.open completada y verificada (alreadyRunning true: la ventana del Explorador del dueño, minimizada, restaurada y al frente); cero confirmaciones y violaciones; raíz devolvió esa ventana a minimizada, sin cerrarla; pins intactos. |
| 6 | apps1237-dev-02 | passed | Variante original aprobada: Explorador ya abierto traído al frente, verificado y dicho. | Final publicado; app.open completada y verificada (alreadyRunning true: la ventana del Explorador del dueño, minimizada, restaurada y al frente); cero confirmaciones y violaciones; raíz devolvió esa ventana a minimizada, sin cerrarla; pins intactos. |
| 7 | apps1237-dev-03 | passed | Variante original aprobada: comprobó el catálogo y dijo que no está instalado. | Final publicado; una lectura app.installed completada y verificada con installed=false; ninguna apertura; cero confirmaciones y violaciones; pins intactos. |
| 8 | apps1237-dev-04 | passed | Variante original aprobada: comprobó el catálogo y dijo que no está instalado. | Final publicado; una lectura app.installed completada y verificada con installed=false; ninguna apertura; cero confirmaciones y violaciones; pins intactos. |
| 9 | apps1237-boundary-01 | passed | Límite aprobado: respuesta informativa sin efecto. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 10 | apps1237-boundary-02 | passed | Límite aprobado: reconoció la prohibición sin efecto. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 171.20 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1580.63 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
