# FILES1205 — adjudicación de la raíz

## FILES1205 — estado vigente 2026-09-13T13:51:59+00:00

Parcial: 19 aprobados, 0 fallidos, 0 sin ejecutar; 12 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 280/742 | 462 | 0 | >=154 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–13 septiembre: 142 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS), todas dentro de la ventana de 24 h al adjudicar; FILES1205 añade 12. No se cuentan revalidaciones.

Siguiente acción: FILES1205 completa: 19 ejecutados, 19 aprobados, 12 créditos (8 archivos en escritorio/Documentos, 3 carpetas en el escritorio, 1 carpeta en el sandbox), cada uno con dos pares aprobados. El proveedor de carpetas conocidas (BUILD1205) y los lectores de creación se demuestran: 18 creaciones verificadas por el producto y comprobadas en disco por raíz (existencia, tipo y hash del contenido literal), ninguna preexistente, todas eliminadas tras la postlectura. Archivos queda 15/32; restan borrados (fixtures en carpetas personales), listados del escritorio, contenido dinámico («que contenga la fecha», procesos), rutas absolutas, comprimir/abrir, resumir PDF y copia a pendrive.

Evidencia: `artifacts/comprobaciones/C03/FILES1205/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 305.34 s acumulados; pico GPU 3497.56 MiB; pico RAM 1588.07 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 19; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0047 | passed | Archivo creado en el escritorio con el contenido pedido y verificado en disco; dos pares aprobados. | Final revisado con una admisión; una creación verificada; postlectura y limpieza de raíz; cero confirmaciones y violaciones; pins intactos. |
| 1 | H0203 | passed | Archivo creado y verificado en disco; dos pares aprobados. | Final revisado con una admisión; una creación verificada; postlectura y limpieza de raíz; cero confirmaciones y violaciones; pins intactos. |
| 2 | H0204 | passed | Archivo creado y verificado en disco; dos pares aprobados. | Final revisado con una admisión; una creación verificada; postlectura y limpieza de raíz; cero confirmaciones y violaciones; pins intactos. |
| 3 | H0304 | passed | Archivo creado y verificado en disco; dos pares aprobados. | Final revisado con una admisión; una creación verificada; postlectura y limpieza de raíz; cero confirmaciones y violaciones; pins intactos. |
| 4 | H0428 | passed | Archivo creado en Documentos y verificado en disco; dos pares aprobados. | Final revisado con una admisión; una creación verificada; postlectura y limpieza de raíz; cero confirmaciones y violaciones; pins intactos. |
| 5 | H0547 | passed | Archivo creado en Documentos y verificado en disco; dos pares aprobados. | Final revisado con una admisión; una creación verificada; postlectura y limpieza de raíz; cero confirmaciones y violaciones; pins intactos. |
| 6 | H0676 | passed | Archivo creado y verificado en disco; dos pares aprobados. | Final revisado con una admisión; una creación verificada; postlectura y limpieza de raíz; cero confirmaciones y violaciones; pins intactos. |
| 7 | H0722 | passed | Archivo creado y verificado en disco; dos pares aprobados. | Final revisado con una admisión; una creación verificada; postlectura y limpieza de raíz; cero confirmaciones y violaciones; pins intactos. |
| 8 | H0256 | passed | Carpeta creada en el escritorio y verificada en disco; dos pares aprobados. | Final revisado con una admisión; una creación verificada; postlectura y limpieza de raíz; cero confirmaciones y violaciones; pins intactos. |
| 9 | H0261 | passed | Carpeta creada en el escritorio y verificada en disco; dos pares aprobados. | Final revisado con una admisión; una creación verificada; postlectura y limpieza de raíz; cero confirmaciones y violaciones; pins intactos. |
| 10 | H0288 | passed | Carpeta creada en el escritorio y verificada en disco; dos pares aprobados. | Final revisado con una admisión; una creación verificada; postlectura y limpieza de raíz; cero confirmaciones y violaciones; pins intactos. |
| 11 | H0629 | passed | Carpeta creada y verificada; dos pares aprobados. | Final revisado con una admisión; una creación verificada en el sandbox del perfil; cero confirmaciones y violaciones; pins intactos. |
| 12 | files1205-dev-01 | passed | Variante original aprobada. | Final revisado con una admisión; una creación verificada; postlectura y limpieza de raíz; cero violaciones; pins intactos. |
| 13 | files1205-dev-02 | passed | Variante original aprobada. | Final revisado con una admisión; una creación verificada; postlectura y limpieza de raíz; cero violaciones; pins intactos. |
| 14 | files1205-dev-03 | passed | Variante original aprobada. | Final revisado con una admisión; una creación verificada; postlectura y limpieza de raíz; cero violaciones; pins intactos. |
| 15 | files1205-dev-04 | passed | Variante original aprobada. | Final revisado con una admisión; una creación verificada; postlectura y limpieza de raíz; cero violaciones; pins intactos. |
| 16 | files1205-dev-05 | passed | Variante original aprobada. | Final revisado con una admisión; una creación verificada en el sandbox del perfil; cero violaciones; pins intactos. |
| 17 | files1205-dev-06 | passed | Variante original aprobada. | Final revisado con una admisión; una creación verificada en el sandbox del perfil; cero violaciones; pins intactos. |
| 18 | files1205-boundary-01 | passed | Límite aprobado. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 305.34 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1588.07 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
