# WINGET2087 — adjudicación de la raíz

## WINGET2087 — estado vigente 2026-09-22T19:28:29.292840+00:00

Parcial: 6 aprobados, 6 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 680/742 | 62 | 0 | >=656 | 29/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 656 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); WINGET2087 añade 0. No se cuentan revalidaciones.

Siguiente acción: WINGET2087: 12 ejecutados, 6 aprobados, 6 fallidos, 0 créditos (índices []). Siguiente: Steam (descargar, instalar, desinstalar, lanzar).

Evidencia: `artifacts/comprobaciones/C03/WINGET2087/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 236.38 s acumulados; pico GPU 3485.56 MiB; pico RAM 2396.79 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 12; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0651 | failed | Falló: no leyó winget, no instaló/desinstaló el paquete único, o el final inventó el estado. | Turno ordinario: el paquete ya estaba instalado porque el fixture no pudo quitarlo; el final no lo dijo así; pins intactos. |
| 1 | H0217 | passed | package.install.prepare/commit verificadas sin confirmación; el final dice el paquete y su estado real (o que no está en winget). | Turno ordinario: exactamente una package.install.prepare completada y verificada (winget leído; paquete único, ausente o varios) y, con paquete único, una package.install.commit completada y verificada que instala y observa el estado; el final nombra el paquete y su estado real; cero confirmaciones y violaciones; pins intactos. |
| 2 | H0167 | passed | package.install.prepare/commit verificadas sin confirmación; el final dice el paquete y su estado real (o que no está en winget). | Turno ordinario: exactamente una package.install.prepare completada y verificada (winget leído; paquete único, ausente o varios) y, con paquete único, una package.install.commit completada y verificada que instala y observa el estado; el final nombra el paquete y su estado real; cero confirmaciones y violaciones; pins intactos. |
| 3 | H0457 | passed | package.install.prepare/commit verificadas sin confirmación; el final dice el paquete y su estado real (o que no está en winget). | Turno ordinario: exactamente una package.install.prepare completada y verificada (winget leído; paquete único, ausente o varios) y, con paquete único, una package.install.commit completada y verificada que instala y observa el estado; el final nombra el paquete y su estado real; cero confirmaciones y violaciones; pins intactos. |
| 4 | H0583 | passed | package.install.prepare/commit verificadas sin confirmación; el final dice el paquete y su estado real (o que no está en winget). | Turno ordinario: exactamente una package.install.prepare completada y verificada (winget leído; paquete único, ausente o varios) y, con paquete único, una package.install.commit completada y verificada que instala y observa el estado; el final nombra el paquete y su estado real; cero confirmaciones y violaciones; pins intactos. |
| 5 | H0574 | failed | Falló: no leyó winget, no instaló/desinstaló el paquete único, o el final inventó el estado. | Turno ordinario: la desinstalación pidió confirmación y la raíz no llegó a aprobarla; nada se desinstaló; pins intactos. |
| 6 | H0089 | failed | Falló: no leyó winget, no instaló/desinstaló el paquete único, o el final inventó el estado. | Turno ordinario: la desinstalación pidió confirmación y la raíz no llegó a aprobarla; nada se desinstaló; pins intactos. |
| 7 | winget2087-dev-01 | failed | Falló: no leyó winget, no instaló/desinstaló el paquete único, o el final inventó el estado. | Turno ordinario: el paquete ya estaba instalado; el final no lo dijo así; pins intactos. |
| 8 | winget2087-dev-02 | failed | Falló: no leyó winget, no instaló/desinstaló el paquete único, o el final inventó el estado. | Turno ordinario: el paquete ya estaba instalado; el final no lo dijo así; pins intactos. |
| 9 | winget2087-rev-01 | failed | Falló: no leyó winget, no instaló/desinstaló el paquete único, o el final inventó el estado. | Turno ordinario: la desinstalación pidió confirmación y la raíz no llegó a aprobarla; nada se desinstaló; pins intactos. |
| 10 | winget2087-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 11 | winget2087-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 236.38 s de segmentos; pico GPU 3485.56 MiB; pico RAM 2396.79 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
