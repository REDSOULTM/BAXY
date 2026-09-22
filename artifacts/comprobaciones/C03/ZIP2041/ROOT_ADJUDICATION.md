# ZIP2041 — adjudicación de la raíz

## ZIP2041 — estado vigente 2026-09-22T05:10:47.476170+00:00

Parcial: 5 aprobados, 1 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 673/742 | 69 | 0 | >=649 | 29/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 648 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); ZIP2041 añade 1. No se cuentan revalidaciones.

Siguiente acción: ZIP2041: 6 ejecutados, 5 aprobados, 1 fallidos, 1 créditos (índices [0]). Siguiente: las tipadas de archivos restantes (ruta pegada, conteo del Explorador) y las de red.

Evidencia: `artifacts/comprobaciones/C03/ZIP2041/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 100.51 s acumulados; pico GPU 3485.93 MiB; pico RAM 2063.96 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 6; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0542 | passed | las cuatro tipadas (carpeta, txt, zip, abrir) verificadas en orden; el final nombra los tres artefactos y dice que el zip quedó abierto; crédito con dos variantes aprobadas del mismo grupo. | Turno ordinario: filesystem.create.directory, filesystem.write.text, file.compress y file.open completadas y verificadas en ese orden en la carpeta pedida (nombres por defecto de Windows); el final nombra la carpeta, el txt y el zip y dice que el zip quedó abierto; cero confirmaciones y violaciones; pins intactos. |
| 1 | zip2041-dev-01 | failed | Falló: faltó un paso, algo no se verificó, preguntó, o el final no nombró la carpeta, el txt y el zip abierto. | Turno ordinario: cero operaciones; la lectura no reconoció el pedido en inglés (corpus semántico pendiente). |
| 2 | zip2041-dev-02 | passed | las cuatro tipadas (carpeta, txt, zip, abrir) verificadas en orden; el final nombra los tres artefactos y dice que el zip quedó abierto. | Turno ordinario: filesystem.create.directory, filesystem.write.text, file.compress y file.open completadas y verificadas en ese orden en la carpeta pedida (nombres por defecto de Windows); el final nombra la carpeta, el txt y el zip y dice que el zip quedó abierto; cero confirmaciones y violaciones; pins intactos. |
| 3 | zip2041-dev-03 | passed | las cuatro tipadas (carpeta, txt, zip, abrir) verificadas en orden; el final nombra los tres artefactos y dice que el zip quedó abierto. | Turno ordinario: filesystem.create.directory, filesystem.write.text, file.compress y file.open completadas y verificadas en ese orden en la carpeta pedida (nombres por defecto de Windows); el final nombra la carpeta, el txt y el zip y dice que el zip quedó abierto; cero confirmaciones y violaciones; pins intactos. |
| 4 | zip2041-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 5 | zip2041-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 100.51 s de segmentos; pico GPU 3485.93 MiB; pico RAM 2063.96 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
