# PIP1817 — adjudicación de la raíz

## PIP1817 — estado vigente 2026-09-17T06:13:39.917773+00:00

Parcial: 3 aprobados, 2 fallidos, 0 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 645/742 | 97 | 0 | >=529 | 14/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–14 septiembre: 529 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS); PIP1817 añade 0. No se cuentan revalidaciones.

Siguiente acción: PIP1817: 5 ejecutados, 3 aprobados, 2 fallidos, 0 créditos (índices []); Abrir aplicaciones 50/54. Siguiente: categoría por masa abierta según CONDICIONES.

Evidencia: `artifacts/comprobaciones/C03/PIP1817/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 100.11 s acumulados; pico GPU 3497.56 MiB; pico RAM 1824.19 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0052 | passed | software.python.package.status completada y verificada (pip show en cada Python registrado, nada instalado); el final dijo si el paquete ya está instalado y en qué versiones de Python con sus cadenas exactas. | Turno ordinario: exactamente una software.python.package.status completada y verificada (pip show en cada Python registrado en Windows, nada instalado); el final dijo si el paquete está instalado y en qué versiones de Python con sus cadenas exactas; cero confirmaciones y violaciones; pins intactos. |
| 1 | pip1817-dev-01 | failed | Falló: la operación no se completó o no se verificó, o el final no fue fiel. | Turno ordinario: software.python.package.status completada y verificada; el final negó una instalación que el recibo muestra. |
| 2 | pip1817-dev-02 | failed | Falló: la operación no se completó o no se verificó, o el final no fue fiel. | Turno ordinario: software.python.package.status completada y verificada; el final se contradijo y atribuyó el paquete a un Python que no lo tiene. |
| 3 | pip1817-boundary-01 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |
| 4 | pip1817-boundary-02 | passed | Límite aprobado. | Final publicado; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 100.11 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1824.19 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
