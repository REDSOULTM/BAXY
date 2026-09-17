# USB1823 — adjudicación de la raíz

## USB1823 — estado vigente 2026-09-17T06:33:31.472429+00:00

Parcial: 5 aprobados, 0 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 647/742 | 95 | 0 | >=531 | 14/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 530 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); USB1823 añade 1. No se cuentan revalidaciones.

Siguiente acción: USB1823: 5 ejecutados, 5 aprobados, 0 fallidos, 1 créditos (índices [0]); Archivos y carpetas 31/32. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/USB1823/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 87.78 s acumulados; pico GPU 3497.56 MiB; pico RAM 1685.36 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0733 | passed | storage.removable.list completada y verificada (unidades extraíbles conectadas, nada copiado); el final dijo con verdad que no hay ningún pendrive conectado y que no se copió nada; crédito con dos variantes aprobadas del mismo grupo. | Turno ordinario: exactamente una storage.removable.list completada y verificada (unidades extraíbles conectadas, DriveInfo, nada copiado); el final dijo que no hay ningún pendrive conectado, que no se copió nada y que puede pedirlo de nuevo con uno conectado; cero confirmaciones y violaciones; pins intactos. |
| 1 | usb1823-dev-01 | passed | storage.removable.list completada y verificada (unidades extraíbles conectadas, nada copiado); el final dijo con verdad que no hay ningún pendrive conectado y que no se copió nada. | Turno ordinario: exactamente una storage.removable.list completada y verificada (unidades extraíbles conectadas, DriveInfo, nada copiado); el final dijo que no hay ningún pendrive conectado, que no se copió nada y que puede pedirlo de nuevo con uno conectado; cero confirmaciones y violaciones; pins intactos. |
| 2 | usb1823-dev-02 | passed | storage.removable.list completada y verificada (unidades extraíbles conectadas, nada copiado); el final dijo con verdad que no hay ningún pendrive conectado y que no se copió nada. | Turno ordinario: exactamente una storage.removable.list completada y verificada (unidades extraíbles conectadas, DriveInfo, nada copiado); el final dijo que no hay ningún pendrive conectado, que no se copió nada y que puede pedirlo de nuevo con uno conectado; cero confirmaciones y violaciones; pins intactos. |
| 3 | usb1823-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | usb1823-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 87.78 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1685.36 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
