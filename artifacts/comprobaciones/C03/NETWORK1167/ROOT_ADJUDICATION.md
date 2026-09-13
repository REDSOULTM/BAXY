# NETWORK1167 — adjudicación de la raíz

## NETWORK1167 — estado vigente 2026-09-13T06:50:31+00:00

Parcial: 5 aprobados, 0 fallidos, 0 sin ejecutar; 2 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 242/742 | 500 | 0 | >=116 | 0/35 |

Procedencia de primeras altas: Primeras altas documentadas 12–13 septiembre: 114 antes de esta tanda (ver CURRENT_CATEGORY_COUNTS), todas dentro de la ventana de 24 h al adjudicar; NETWORK1167 añade 2. No se cuentan revalidaciones.

Siguiente acción: NETWORK1167 completa: 5 ejecutados, 5 aprobados, 2 créditos (H0127, H0433). El validador de conectividad se demuestra: el par inglés ya no añade «offline». Red queda 6/21 (abiertos: H0230 «decime si…», H0302 redes disponibles, H0455/H0568/H0481 IP PrivacySensitive, efectos de bluetooth/wifi y 4 elipsis/sin marca). Siguiente: cierre de apps propias (20 abiertos) con autorización explícita del dueño por app, o conocimiento residual sólo con causa nueva.

Evidencia: `artifacts/comprobaciones/C03/NETWORK1167/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 81.87 s acumulados; pico GPU 3497.56 MiB; pico RAM 1596.00 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 5; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 0 | H0127 | passed | Informó fielmente que no hay conexión wifi; dos variantes aprobadas. | Final revisado con una admisión; una lectura wifi verificada; cero confirmaciones y violaciones; pins intactos. |
| 1 | H0433 | passed | Informó fielmente que no hay conexión wifi; dos variantes aprobadas. | Final revisado con una admisión; una lectura wifi verificada; cero confirmaciones y violaciones; pins intactos. |
| 2 | network1167-dev-01 | passed | Variante original aprobada: estado wifi leído sin inventar. | Final revisado con una admisión; una lectura wifi verificada; cero confirmaciones y violaciones; pins intactos. |
| 3 | network1167-dev-02 | passed | Variante original aprobada: estado wifi leído sin inventar. | Final revisado con una admisión; una lectura wifi verificada; cero confirmaciones y violaciones; pins intactos. |
| 4 | network1167-boundary-01 | passed | Límite aprobado. | Final revisado con una admisión; ninguna operación; cero confirmaciones y violaciones; pins intactos. |

Recursos: 81.87 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1596.00 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
