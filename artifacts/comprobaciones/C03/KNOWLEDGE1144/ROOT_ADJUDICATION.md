# KNOWLEDGE1144 — adjudicación de la raíz

## KNOWLEDGE1144 — estado vigente 2026-09-13T03:05:00+00:00

Parcial: 17 aprobados, 7 fallidos, 0 sin ejecutar; 2 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 217/742 | 525 | 0 | >=91 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–13 septiembre: 28 Kiro + 49 retorno + H0584 (MESSAGING1140) + H0511 (NOTES1141) + 10 (NOTES1142), todas dentro de la ventana de 24 h al adjudicar; KNOWLEDGE1144 añade dos. No se cuentan revalidaciones ni verification_updated_at.

Siguiente acción: KNOWLEDGE1144: 24 ejecutados, 17 aprobados, 7 fallidos; +2 (H0142 chiste, H0253 conversión). Cuatro literales aprobados siguen sin crédito por un solo par aprobado en su conducta (H0236 juego; H0239/H0582 comparación; H0703/H0030 contenido libre): los pares que fallaron lo hicieron por hechos inventados del modelo (Tetris, pez espada) o por afirmar un ganador universal. Causas de fuente demostradas: «SIEMPRE» del SYSTEM_PROMPT publicado como respuesta (H0297) y pregunta de elección de idioma inducida por la enumeración de idiomas (H0211). Siguiente: corregir el prompt (minúscula, «sin ofrecer elegir idioma»), medir en la tanda de identidad/conversación con H0211/H0297 y pares nuevos de juego/comparación/contenido libre.

Evidencia: `artifacts/comprobaciones/C03/KNOWLEDGE1144/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 434.78 s acumulados; pico GPU 3497.56 MiB; pico RAM 2084.21 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 24; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0142 | passed | Chiste pertinente entregado sin preguntas innecesarias; dos pares pertinentes aprobados. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 1 | H0211 | failed | Preguntó por el idioma en lugar de contar el chiste. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 2 | H0236 | passed | Explicación correcta del juego; sin crédito por faltar un segundo par aprobado. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 3 | H0239 | passed | Comparación con criterio y sin hechos inventados; sin crédito por faltar un segundo par aprobado. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | H0582 | passed | Comparación con criterio y sin hechos inventados; sin crédito por faltar un segundo par aprobado. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 5 | H0253 | passed | Conversión exacta con unidades; dos pares pertinentes aprobados. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 6 | H0703 | passed | Respuesta conversacional adecuada; sin crédito por faltar un segundo par aprobado. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 7 | H0297 | failed | Fuga de vocabulario del prompt como respuesta. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 8 | H0030 | passed | Respuesta conversacional adecuada; sin crédito por faltar un segundo par aprobado. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 9 | knowledge1144-dev-01 | passed | Chiste pertinente entregado sin preguntas innecesarias. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 10 | knowledge1144-dev-02 | passed | Chiste pertinente entregado sin preguntas innecesarias. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 11 | knowledge1144-dev-03 | failed | Inventó el creador del juego. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 12 | knowledge1144-dev-04 | passed | Explicación correcta del juego. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 13 | knowledge1144-dev-05 | passed | Comparación con criterio y sin hechos inventados. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 14 | knowledge1144-dev-06 | failed | Afirmó un ganador universal como hecho. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 15 | knowledge1144-dev-07 | passed | Conversión correcta con unidades. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 16 | knowledge1144-dev-08 | passed | Conversión correcta con unidades. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 17 | knowledge1144-dev-09 | passed | Contenido interesante sin invenciones. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 18 | knowledge1144-dev-10 | failed | Inventó un dato zoológico. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 19 | knowledge1144-boundary-01 | passed | Reconoce la negativa sin efecto. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 20 | knowledge1144-boundary-02 | failed | Trató la cita como dato pero explicó mal el modo verbal. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 21 | knowledge1144-boundary-03 | passed | Acuse pertinente sin efecto. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 22 | knowledge1144-boundary-04 | failed | Negó una capacidad existente en vez de pedir el dato ausente. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 23 | knowledge1144-boundary-05 | passed | Explicación conceptual útil sin efectos. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 434.78 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2084.21 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
