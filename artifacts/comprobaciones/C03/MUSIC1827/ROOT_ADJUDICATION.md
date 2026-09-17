# MUSIC1827 — adjudicación de la raíz

## MUSIC1827 — estado vigente 2026-09-17T07:11:26.282520+00:00

Parcial: 2 aprobados, 3 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 648/742 | 94 | 0 | >=532 | 13/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 532 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); MUSIC1827 añade 0. No se cuentan revalidaciones.

Siguiente acción: MUSIC1827: 5 ejecutados, 2 aprobados, 3 fallidos, 0 créditos (índices []); Música 38/39. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/MUSIC1827/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 107.55 s acumulados; pico GPU 3497.56 MiB; pico RAM 2573.22 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0352 | failed | Falló: no preguntó qué música, o la navegación al navegador nombrado no se aprobó o no se verificó, o el final afirmó de más o no hubo final. | Diálogo revisado: pregunta, respuesta guionizada, browser.navigate.named aprobada por la raíz, completada y verificada; la lista sellada de operaciones permitidas incluyó una operación nominal de la aclaración que nunca se ejecutó y el adjudicador sellado no admite el caso como aprobado; se repite con la lista corregida. |
| 1 | music1827-dev-01 | failed | Falló: no preguntó qué música, o la navegación al navegador nombrado no se aprobó o no se verificó, o el final afirmó de más o no hubo final. | Diálogo revisado: pregunta, respuesta guionizada, browser.navigate.named aprobada por la raíz, completada y verificada; la lista sellada de operaciones permitidas incluyó una operación nominal de la aclaración que nunca se ejecutó y el adjudicador sellado no admite el caso como aprobado; se repite con la lista corregida. |
| 2 | music1827-dev-02 | failed | Falló: no preguntó qué música, o la navegación al navegador nombrado no se aprobó o no se verificó, o el final afirmó de más o no hubo final. | Diálogo revisado: pregunta, respuesta guionizada, browser.navigate.named aprobada por la raíz, completada y verificada; la lista sellada de operaciones permitidas incluyó una operación nominal de la aclaración que nunca se ejecutó y el adjudicador sellado no admite el caso como aprobado; se repite con la lista corregida. |
| 3 | music1827-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | music1827-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 107.55 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2573.22 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
