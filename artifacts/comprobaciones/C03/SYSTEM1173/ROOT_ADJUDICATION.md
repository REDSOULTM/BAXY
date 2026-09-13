# SYSTEM1173 — adjudicación de la raíz

## SYSTEM1173 — estado vigente 2026-09-13T07:17:00+00:00

Parcial: 5 aprobados, 2 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 244/742 | 498 | 0 | >=118 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–13 septiembre: 117 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS), todas dentro de la ventana de 24 h al adjudicar; SYSTEM1173 añade 1. No se cuentan revalidaciones.

Siguiente acción: SYSTEM1173 completa: 7 ejecutados, 5 aprobados, 2 fallidos, 1 crédito (H0114). Las palabras inglesas de uso de GPU se demuestran («in use» → gpu_usage). La línea de prompt sobre claves de memoria no cambia la conducta: el modelo sigue llamando «disponible/available» a total_usable (2 de 3). Reparación siguiente: renombrar las claves proyectadas de memoria/disco (measurement_prose_projection: p. ej. total y free) — cambia un contrato con tests pinneados (tests no ejecutables por orden del dueño): declararlo antes. Estado de hardware queda 27/40.

Evidencia: `artifacts/comprobaciones/C03/SYSTEM1173/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 117.16 s acumulados; pico GPU 3497.56 MiB; pico RAM 1626.41 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 7; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0114 | passed | Leyó la GPU y dio el uso de VRAM observado; dos variantes aprobadas. | Final revisado con una admisión; una lectura de estado verificada; cero confirmaciones y violaciones; pins intactos. |
| 1 | H0508 | failed | Versión correcta; sigue llamando «disponible» a la RAM total. | Final revisado con una admisión; una lectura de estado verificada; cero confirmaciones y violaciones; pins intactos. |
| 2 | system1173-dev-01 | passed | Variante original aprobada: GPU leída con sus números. | Final revisado con una admisión; una lectura de estado verificada; cero confirmaciones y violaciones; pins intactos. |
| 3 | system1173-dev-02 | passed | Variante original aprobada: GPU leída en inglés. | Final revisado con una admisión; una lectura de estado verificada; cero confirmaciones y violaciones; pins intactos. |
| 4 | system1173-dev-03 | passed | Variante original aprobada: RAM total bien etiquetada. | Final revisado con una admisión; una lectura de estado verificada; cero confirmaciones y violaciones; pins intactos. |
| 5 | system1173-dev-04 | failed | Llamó «available» a la RAM total. | Final revisado con una admisión; una lectura de estado verificada; cero confirmaciones y violaciones; pins intactos. |
| 6 | system1173-boundary-01 | passed | Límite aprobado. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 117.16 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1626.41 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
