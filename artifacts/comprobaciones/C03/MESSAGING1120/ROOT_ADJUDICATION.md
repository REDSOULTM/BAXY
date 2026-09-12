# MESSAGING1120 — adjudicación de la raíz

## MESSAGING1120 — estado vigente 2026-09-12T23:43:42.7182609Z

Parcial: 1 aprobados, 1 fallidos, 6 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 202/742 | 540 | 0 | >=76 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas del12septiembre:28Kiro+48retorno incluidas4AGENDA1110. No sumar revalidaciones.

Siguiente acción: AGENDA1121 residual con candidato1119; después DIALOGUE1122/1123. MESSAGING1120 variante1 falla interlocutor y falta canal: diagnosticar ruta antes de nueva tanda; H0584 no ejecutado. Cinco límites preservados; condicional6 fallido1095 sin hipótesis no repetido. Observación1 rechazó cliente reaparecido, sin producto: receipt archivado, root cerró proceso exacto en segundo plano y reobservó ausencia antes de la única ejecución1. Goalactivo; sin tests.

Evidencia: `artifacts/comprobaciones/C03/MESSAGING1120/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 58.99 s acumulados; pico GPU 3495.56 MiB; pico RAM 1563.80 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 2; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | messaging1062-dev-01 | passed | Aclaración útil sobre canal faltante; conserva intención y destinatario. | Una admisión y final revisado; cero efectos, confirmaciones y violaciones; pins intactos. |
| 1 | messaging1062-dev-02 | failed | Confunde al tercero con el interlocutor y no pide el canal faltante. | Una admisión y final revisado; cero efectos, confirmaciones y violaciones. Contexto rechazado previo sin ejecución preservado y nueva ausencia verificada. |

Recursos: 58.99 s de segmentos; pico GPU 3495.56 MiB; pico RAM 1563.80 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
