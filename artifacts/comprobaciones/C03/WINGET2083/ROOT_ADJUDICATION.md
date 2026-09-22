# WINGET2083 — adjudicación de la raíz

## WINGET2083 — estado vigente 2026-09-22T16:31:45.990321+00:00

Parcial: 2 aprobados, 10 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 680/742 | 62 | 0 | >=656 | 29/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 656 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); WINGET2083 añade 0. No se cuentan revalidaciones.

Siguiente acción: WINGET2083: 12 ejecutados, 2 aprobados, 10 fallidos, 0 créditos (índices []). Siguiente: Steam (descargar, instalar, desinstalar, lanzar).

Evidencia: `artifacts/comprobaciones/C03/WINGET2083/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 249.20 s acumulados; pico GPU 3485.56 MiB; pico RAM 2459.68 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 12; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0651 | failed | Falló: no leyó winget, no instaló/desinstaló el paquete único, o el final inventó el estado. | Turno ordinario: el instalador corrió y la relectura no confirmó la instalación; el final que lo decía no se pudo publicar; pins intactos. Reparación en el commit siguiente. |
| 1 | H0217 | failed | Falló: no leyó winget, no instaló/desinstaló el paquete único, o el final inventó el estado. | Turno ordinario: winget no ofrece ese paquete; cero instalaciones y final fiel; pins intactos. |
| 2 | H0167 | failed | Falló: no leyó winget, no instaló/desinstaló el paquete único, o el final inventó el estado. | Turno ordinario: winget no ofrece ese paquete; cero instalaciones y final fiel; pins intactos. |
| 3 | H0457 | failed | Falló: no leyó winget, no instaló/desinstaló el paquete único, o el final inventó el estado. | Turno ordinario: winget no ofrece ese paquete; cero instalaciones y final fiel; pins intactos. |
| 4 | H0583 | failed | Falló: no leyó winget, no instaló/desinstaló el paquete único, o el final inventó el estado. | Turno ordinario: winget no ofrece ese paquete; cero instalaciones y final fiel; pins intactos. |
| 5 | H0574 | failed | Falló: no leyó winget, no instaló/desinstaló el paquete único, o el final inventó el estado. | Turno ordinario: el runner detuvo una operación que el panel no permitía; cero efectos; pins intactos. Defecto del panel. |
| 6 | H0089 | failed | Falló: no leyó winget, no instaló/desinstaló el paquete único, o el final inventó el estado. | Turno ordinario: el runner detuvo una operación que el panel no permitía; cero efectos; pins intactos. |
| 7 | winget2083-dev-01 | failed | Falló: no leyó winget, no instaló/desinstaló el paquete único, o el final inventó el estado. | Turno ordinario: el instalador corrió y la relectura no confirmó la instalación; el final no se pudo publicar; pins intactos. |
| 8 | winget2083-dev-02 | failed | Falló: no leyó winget, no instaló/desinstaló el paquete único, o el final inventó el estado. | Turno ordinario: el instalador corrió, la relectura no confirmó la instalación y el final lo dijo con verdad; pins intactos. |
| 9 | winget2083-rev-01 | failed | Falló: no leyó winget, no instaló/desinstaló el paquete único, o el final inventó el estado. | Turno ordinario: el runner detuvo una operación que el panel no permitía; cero efectos; pins intactos. |
| 10 | winget2083-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 11 | winget2083-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 249.20 s de segmentos; pico GPU 3485.56 MiB; pico RAM 2459.68 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
