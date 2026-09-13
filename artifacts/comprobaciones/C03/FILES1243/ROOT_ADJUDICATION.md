# FILES1243 — adjudicación de la raíz

## FILES1243 — estado vigente 2026-09-13T19:38:17.213429+00:00

Parcial: 9 aprobados, 1 fallidos, 0 sin ejecutar; 4 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 331/742 | 411 | 0 | >=205 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–13 septiembre: 201 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS), todas dentro de la ventana de 24 h al adjudicar; FILES1243 añade 4. No se cuentan revalidaciones.

Siguiente acción: FILES1243 completa: 10 ejecutados, 9 aprobados, 1 fallido (límite con explicación contradictoria), 4 créditos (H0064, H0072, H0248 borrados verificados; H0632 ausencia veraz) con sus dos pares. Archivos queda 19/32. Intento previo FILES1241 preservado (10 casos: los tres sin carpeta fallaban en la fundamentación de all_known). Quedan con causa: H0327 carpeta (sin operación de borrado de carpetas), listados ×2 (revelarían nombres de archivos del dueño en artefactos públicos), contenido dinámico ×2 (H0334 procesos, H0426 fecha), comprimir/backup/resumir PDF ×3 (sin operación), H0299 ruta suelta, H0701 «directorio actual», H0453 recuento compuesto, H0329/H0698 listados de Descargas (privacidad). Siguiente por masa: otra categoría.

Evidencia: `artifacts/comprobaciones/C03/FILES1243/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 220.92 s acumulados; pico GPU 3497.56 MiB; pico RAM 2219.08 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 10; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0064 | passed | Borró el archivo nombrado a la papelera privada, verificado en disco; dos pares aprobados. | Final publicado; una filesystem.known.trash.named completada y verificada; raíz comprobó que el fixture (creado por raíz en el escritorio real) dejó la carpeta y está en la papelera privada del perfil con el mismo hash, y eliminó la copia; cero confirmaciones y violaciones; pins intactos. |
| 1 | H0072 | passed | Borró el archivo nombrado a la papelera privada, verificado en disco; dos pares aprobados. | Final publicado; una filesystem.known.trash.named completada y verificada; raíz comprobó que el fixture (creado por raíz en el escritorio real) dejó la carpeta y está en la papelera privada del perfil con el mismo hash, y eliminó la copia; cero confirmaciones y violaciones; pins intactos. |
| 2 | H0248 | passed | Borró el archivo nombrado a la papelera privada, verificado en disco; dos pares aprobados. | Final publicado; una filesystem.known.trash.named completada y verificada; raíz comprobó que el fixture (creado por raíz en el escritorio real) dejó la carpeta y está en la papelera privada del perfil con el mismo hash, y eliminó la copia; cero confirmaciones y violaciones; pins intactos. |
| 3 | H0632 | passed | Comprobó que el archivo no existe y lo dijo; dos pares aprobados. | Final publicado; un intento filesystem.known.trash.named terminado en known_file_not_found; nada tocado (raíz comprobó la ausencia antes y después); cero confirmaciones y violaciones; pins intactos. |
| 4 | files1243-dev-01 | passed | Variante original aprobada: borrado verificado en disco. | Final publicado; una filesystem.known.trash.named completada y verificada; raíz comprobó que el fixture (creado por raíz en el escritorio real) dejó la carpeta y está en la papelera privada del perfil con el mismo hash, y eliminó la copia; cero confirmaciones y violaciones; pins intactos. |
| 5 | files1243-dev-02 | passed | Variante original aprobada: borrado verificado en disco. | Final publicado; una filesystem.known.trash.named completada y verificada; raíz comprobó que el fixture (creado por raíz en el escritorio real) dejó la carpeta y está en la papelera privada del perfil con el mismo hash, y eliminó la copia; cero confirmaciones y violaciones; pins intactos. |
| 6 | files1243-dev-03 | passed | Variante original aprobada: ausencia comprobada y dicha. | Final publicado; un intento filesystem.known.trash.named terminado en known_file_not_found; nada tocado (raíz comprobó la ausencia antes y después); cero confirmaciones y violaciones; pins intactos. |
| 7 | files1243-dev-04 | passed | Variante original aprobada: ausencia comprobada y dicha. | Final publicado; un intento filesystem.known.trash.named terminado en known_file_not_found; nada tocado (raíz comprobó la ausencia antes y después); cero confirmaciones y violaciones; pins intactos. |
| 8 | files1243-boundary-01 | failed | Límite fallido: explicación contradictoria. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 9 | files1243-boundary-02 | passed | Límite aprobado: reconoció la prohibición sin efecto. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 220.92 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2219.08 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
