# WINDOWS1207 — adjudicación de la raíz

## WINDOWS1207 — estado vigente 2026-09-13T14:09:40+00:00

Parcial: 9 aprobados, 6 fallidos, 1 sin ejecutar; 5 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 285/742 | 457 | 0 | >=159 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–13 septiembre: 154 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS), todas dentro de la ventana de 24 h al adjudicar; WINDOWS1207 añade 5. No se cuentan revalidaciones.

Siguiente acción: WINDOWS1207 parcial: 15 ejecutados, 8 aprobados, 7 fallidos, 1 sin ejecutar (índice 11, abortado antes de la admisión), 5 créditos (H0143, H0281, H0314, H0403, H0631: presencia de aplicaciones). Las formas coloquiales se demuestran en el reconocedor (los seis literales antes inalcanzables llegan a su lectura), pero el inventario de ventanas no compone con 22 ventanas en el escritorio real: el validador exige conservar las 20 entradas de la página y el modelo (512 tokens) omite títulos → missing_fact → código interno; en inglés, borradores en español → sin final. Siguiente: proyección acotada del inventario (contar y nombrar un subconjunto declarado) o validación por página parcial antes de remedir H0023/H0103/H0209/H0309/H0663/H0053. Estado de ventanas queda 7/14.

Evidencia: `artifacts/comprobaciones/C03/WINDOWS1207/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 498.62 s acumulados; pico GPU 3497.56 MiB; pico RAM 2363.17 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 15; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0023 | failed | Leyó las ventanas pero publicó un código interno en vez de la lista. | Final revisado con una admisión; una lectura verificada; el texto final fue un código de diagnóstico; pins intactos. |
| 1 | H0103 | failed | Leyó las ventanas pero publicó un código interno en vez de la lista. | Final revisado con una admisión; una lectura verificada; el texto final fue un código de diagnóstico; pins intactos. |
| 2 | H0209 | failed | Leyó las ventanas pero publicó un código interno en vez de la lista. | Final revisado con una admisión; una lectura verificada; el texto final fue un código de diagnóstico; pins intactos. |
| 3 | H0309 | failed | Leyó las ventanas pero publicó un código interno en vez de la lista. | Final revisado con una admisión; una lectura verificada; el texto final fue un código de diagnóstico; pins intactos. |
| 4 | H0663 | failed | Leyó las ventanas pero publicó un código interno en vez de la lista. | Final revisado con una admisión; una lectura verificada; el texto final fue un código de diagnóstico; pins intactos. |
| 5 | H0053 | passed | Contó las ventanas observadas; sin crédito por faltar los pares. | Final revisado con una admisión; una lectura verificada; cero confirmaciones y violaciones; pins intactos. |
| 6 | H0143 | passed | Leyó la presencia de la aplicación y respondió lo observado; dos pares aprobados. | Final revisado con una admisión; una lectura verificada; cero confirmaciones y violaciones; pins intactos. |
| 7 | H0281 | passed | Leyó la presencia de la aplicación y respondió lo observado; dos pares aprobados. | Final revisado con una admisión; una lectura verificada; cero confirmaciones y violaciones; pins intactos. |
| 8 | H0314 | passed | Leyó la presencia de la aplicación y respondió lo observado; dos pares aprobados. | Final revisado con una admisión; una lectura verificada; cero confirmaciones y violaciones; pins intactos. |
| 9 | H0403 | passed | Leyó la presencia de la aplicación y respondió lo observado; dos pares aprobados. | Final revisado con una admisión; una lectura verificada; cero confirmaciones y violaciones; pins intactos. |
| 10 | H0631 | passed | Leyó la presencia de la aplicación y respondió lo observado; dos pares aprobados. | Final revisado con una admisión; una lectura verificada; cero confirmaciones y violaciones; pins intactos. |
| 12 | windows1207-dev-02 | failed | Leyó las ventanas pero no publicó respuesta (idioma incorrecto en los borradores). | Final nulo; una lectura verificada; pins intactos. |
| 13 | windows1207-dev-03 | passed | Variante original aprobada. | Final revisado con una admisión; una lectura verificada; cero confirmaciones y violaciones; pins intactos. |
| 14 | windows1207-dev-04 | passed | Variante original aprobada. | Final revisado con una admisión; una lectura verificada; cero confirmaciones y violaciones; pins intactos. |
| 15 | windows1207-boundary-01 | passed | Límite aprobado. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 498.62 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2363.17 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
