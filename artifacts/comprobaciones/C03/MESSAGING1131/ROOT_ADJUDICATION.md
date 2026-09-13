# MESSAGING1131 — adjudicación de la raíz

## MESSAGING1131 — estado vigente 2026-09-13T00:45:38.642261+00:00

Parcial: 2 aprobados, 1 fallidos, 5 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 203/742 | 539 | 0 | >=77 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas12septiembre28Kiro+49retorno hastaAGENDA1121. Sin nuevas altas en1131; no contar variantes ni revalidaciones.

Siguiente acción: Adoptar TIME1133 y medir TIME1134 instrumento v6 tras revisión completa; v5 rechazado estáticamente por perfil1130 en observer, sin ejecución. MESSAGING1131 dos variantes pasadas, literalH0584fallido por primera persona ajena; conservar causa, no acreditar ni repetir hasta hipótesis pertinente. Cinco límites preservados;6sin causa nueva excluido. Primera observación0concliente fue archivada antes de cierreexactoPID4104; luego única ejecución0 con ausencia observada. Goalactivo sin tests.

Evidencia: `artifacts/comprobaciones/C03/MESSAGING1131/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 75.81 s acumulados; pico GPU 3495.56 MiB; pico RAM 1576.23 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 3; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | messaging1062-dev-01 | passed | Pregunta el canal ausente conservando intención y destinatario. | Final revisado con una admisión; cero efectos, confirmaciones y violaciones; pins intactos. |
| 1 | messaging1062-dev-02 | passed | Pregunta el canal ausente conservando intención y destinatario. | Final revisado con una admisión; cero efectos, confirmaciones y violaciones; pins intactos. |
| 2 | H0584 | failed | Pide canal pero adopta como propia la relación y la intención del usuario. | Final revisado con una admisión; cero efectos, confirmaciones y violaciones; pins intactos. |

Recursos: 75.81 s de segmentos; pico GPU 3495.56 MiB; pico RAM 1576.23 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
