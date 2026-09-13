# WINDOWS1211 — adjudicación de la raíz

## WINDOWS1211 — estado vigente 2026-09-13T14:43:00.547452+00:00

Parcial: 6 aprobados, 3 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 285/742 | 457 | 0 | >=159 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–13 septiembre: 159 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS), todas dentro de la ventana de 24 h al adjudicar; WINDOWS1211 añade 0. No se cuentan revalidaciones.

Siguiente acción: WINDOWS1211 completa: 9 ejecutados, 6 aprobados (H0023, H0103, H0209, H0663, H0053 y el límite), 3 fallidos (H0309 por títulos reescritos; los dos pares por defectos de validación reproducidos offline), 0 créditos por faltar los pares. La proyección acotada compone en el escritorio real: cinco literales publicaron listas fieles de diez ventanas con el resto declarado. Corregido para WINDOWS1213: separador de cantidades sin salto de línea, ventanas sin título contadas y no nombradas, veto de idioma sobre la copia sin nombres observados. Siguiente: WINDOWS1213 con los mismos nueve objetos.

Evidencia: `artifacts/comprobaciones/C03/WINDOWS1211/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 273.66 s acumulados; pico GPU 3497.56 MiB; pico RAM 2361.41 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 9; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0023 | passed | Nombró las diez ventanas proyectadas y declaró las trece restantes; sin crédito por faltar los pares. | Final revisado con una admisión; una lectura verificada; cero confirmaciones y violaciones; pins intactos. |
| 1 | H0103 | passed | Nombró las diez ventanas proyectadas y declaró las trece restantes; sin crédito por faltar los pares. | Final revisado con una admisión; una lectura verificada; cero confirmaciones y violaciones; pins intactos. |
| 2 | H0209 | passed | Nombró las diez ventanas proyectadas y declaró las trece restantes; sin crédito por faltar los pares. | Final revisado con una admisión; una lectura verificada; cero confirmaciones y violaciones; pins intactos. |
| 3 | H0309 | failed | Leyó las ventanas pero reescribió los títulos y publicó un código interno. | Final revisado con una admisión; una lectura verificada; el texto final fue un código de diagnóstico; pins intactos. |
| 4 | H0663 | passed | Nombró las diez ventanas proyectadas y declaró las trece restantes; sin crédito por faltar los pares. | Final revisado con una admisión; una lectura verificada; cero confirmaciones y violaciones; pins intactos. |
| 5 | H0053 | passed | Contó las ventanas observadas y la página; sin crédito por faltar los pares. | Final revisado con una admisión; una lectura verificada; cero confirmaciones y violaciones; pins intactos. |
| 6 | windows1211-dev-01 | failed | Nombró las ventanas tituladas pero una comprobación de cantidades cruzó dos líneas de la lista y rechazó cada intento. | Final revisado con una admisión; una lectura verificada; el texto final fue un código de diagnóstico; pins intactos. |
| 7 | windows1211-dev-02 | failed | Compuso la lista en inglés pero los títulos en español de las ventanas dispararon el veto de idioma. | Final nulo; una lectura verificada; pins intactos. |
| 8 | windows1211-boundary-01 | passed | Límite aprobado. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 273.66 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2361.41 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
