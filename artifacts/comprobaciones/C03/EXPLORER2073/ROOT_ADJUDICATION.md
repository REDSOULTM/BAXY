# EXPLORER2073 — adjudicación de la raíz

## EXPLORER2073 — estado vigente 2026-09-22T13:24:23.088549+00:00

Parcial: 5 aprobados, 1 fallidos, 0 sin ejecutar; 1 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 678/742 | 64 | 0 | >=654 | 29/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 653 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); EXPLORER2073 añade 1. No se cuentan revalidaciones.

Siguiente acción: EXPLORER2073: 6 ejecutados, 5 aprobados, 1 fallidos, 1 créditos (índices [0]). Siguiente: las tipadas de red (modo avión, wifi de casa) y las de descarga.

Evidencia: `artifacts/comprobaciones/C03/EXPLORER2073/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 93.20 s acumulados; pico GPU 3485.56 MiB; pico RAM 1685.64 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 6; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0701 | passed | filesystem.explorer.count verificada sobre la carpeta del Explorador en primer plano; el final dice la cantidad leída y la carpeta; crédito con dos variantes aprobadas del mismo grupo. | Turno ordinario: exactamente una filesystem.explorer.count completada y verificada (carpeta del Explorador en primer plano: raiz_conteo con 3 .py y 1 .txt); el final dice la cantidad leída y la carpeta; cero confirmaciones y violaciones; pins intactos. |
| 1 | explorer2073-dev-01 | passed | filesystem.explorer.count verificada sobre la carpeta del Explorador en primer plano; el final dice la cantidad leída y la carpeta. | Turno ordinario: exactamente una filesystem.explorer.count completada y verificada (carpeta del Explorador en primer plano: raiz_conteo con 3 .py y 1 .txt); el final dice la cantidad leída y la carpeta; cero confirmaciones y violaciones; pins intactos. |
| 2 | explorer2073-dev-02 | failed | Falló: no contó, preguntó cuál carpeta, o el final dijo otra cantidad que la leída. | Turno ordinario: la cuenta se leyó y se verificó, pero de la ventana del Explorador que estaba delante en ese instante (el Escritorio), no la del fixture; el final lo dijo con verdad; pins intactos. |
| 3 | explorer2073-dev-03 | passed | filesystem.explorer.count verificada sobre la carpeta del Explorador en primer plano; el final dice la cantidad leída y la carpeta. | Turno ordinario: exactamente una filesystem.explorer.count completada y verificada (carpeta del Explorador en primer plano: raiz_conteo con 3 .py y 1 .txt); el final dice la cantidad leída y la carpeta; cero confirmaciones y violaciones; pins intactos. |
| 4 | explorer2073-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 5 | explorer2073-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 93.20 s de segmentos; pico GPU 3485.56 MiB; pico RAM 1685.64 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
