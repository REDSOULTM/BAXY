# TIME1195 — adjudicación de la raíz

## TIME1195 — estado vigente 2026-09-13T12:56:31+00:00

Parcial: 9 aprobados, 5 fallidos, 0 sin ejecutar; 2 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 260/742 | 482 | 0 | >=134 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–13 septiembre: 132 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS), todas dentro de la ventana de 24 h al adjudicar; TIME1195 añade 2. No se cuentan revalidaciones.

Siguiente acción: TIME1195 completa: 14 ejecutados, 9 aprobados, 5 fallidos, 2 créditos (H0222 hora ambigua, H0585 recordatorio sin cuándo). Demostrado: la hora imposible pide una hora válida (H0371 y su par español) y las aclaraciones deterministas de periodo y de cuándo son precisas. Fallos: los avisos con plazo pero sin contenido (H0121, H0343 y sus dos pares) no tienen aclaración determinista: el modelo vuelve a pedir el plazo o inventa el contenido y crea el recordatorio; el par inglés de hora imposible agotó la composición (código interno). Siguiente: aclaración determinista «qué avisar» para aviso con plazo sin contenido; causa del rechazo de composición en inglés; remedir H0121/H0343/H0371 con pares.

Evidencia: `artifacts/comprobaciones/C03/TIME1195/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 222.97 s acumulados; pico GPU 3497.56 MiB; pico RAM 1724.02 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 14; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0121 | failed | Volvió a pedir el plazo ya dado y preguntó con la persona equivocada. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 1 | H0343 | failed | Volvió a pedir el plazo ya dado. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 2 | H0222 | passed | Pidió el periodo del día para la hora ambigua; dos pares aprobados. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 3 | H0371 | passed | Pidió una hora válida; sin crédito por faltar el segundo par. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | H0585 | passed | Pidió cuándo recordarlo conservando el contenido; dos pares aprobados. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 5 | time1195-dev-01 | failed | Volvió a pedir el plazo ya dado. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 6 | time1195-dev-02 | failed | Creó un recordatorio con contenido inventado en vez de preguntar qué recordar. | Caso detenido por el conductor por operación fuera del transporte; efecto confinado al perfil aislado; pins intactos. |
| 7 | time1195-dev-03 | passed | Variante original aprobada. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 8 | time1195-dev-04 | passed | Variante original aprobada. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 9 | time1195-dev-05 | passed | Variante original aprobada. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 10 | time1195-dev-06 | failed | Publicó un código interno en vez de la pregunta. | Final revisado con una admisión; ninguna operación; el texto final fue un código de diagnóstico; pins intactos. |
| 11 | time1195-dev-07 | passed | Variante original aprobada. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 12 | time1195-dev-08 | passed | Variante original aprobada. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 13 | time1195-boundary-01 | passed | Límite aprobado. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 222.97 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1724.02 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
