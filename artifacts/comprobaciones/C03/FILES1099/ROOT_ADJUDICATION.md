# FILES1099 — adjudicación de la raíz

## FILES1099 — estado vigente 2026-09-12T21:35:32.1366154Z

Parcial: 1 aprobados, 5 fallidos, 3 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 197/742 | 545 | 0 | >=71 | 0/35 |

Procedencia de primeras altas: Al menos 71 primeras altas verificadas: 28 del relevo Kiro y 43 del retorno hasta DIALOGUE1093. No se cuentan revalidaciones ni verification_updated_at.

Siguiente acción: Integrar tras revisión la reparación AGENDA1100 de aclaración temporal y medir AGENDA1101 con pares antes de sus seis literales. FILES1099: tres objetos sin ejecutar tras el fallo de variante2; diagnóstico local conserva la clasificación complete incorrecta. Sin tests por instrucción del dueño; sin crédito por propuestas.

Evidencia: `artifacts/comprobaciones/C03/FILES1099/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 173.22 s acumulados; pico GPU 3497.56 MiB; pico RAM 2082.44 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 6; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 2 | files1099-dev-01 | failed | Negativa genérica ante contenido incompleto. | No pidió el dato faltante; sin operaciones adicionales. |
| 4 | files1099-boundary-01 | failed | Respuesta inconexa a una prohibición explícita. | La ausencia de efectos no basta para aprobar la respuesta. |
| 5 | files1099-boundary-02 | failed | Explicación parcialmente correcta con una carencia inventada. | No ejecutó la cita; añadió un motivo incorrecto a la explicación. |
| 6 | files1099-boundary-03 | failed | Confundió un planteamiento futuro con una solicitud fuera de alcance. | Negativa global no pertinente; sin operaciones adicionales. |
| 7 | files1099-boundary-04 | passed | Distinguió nombre y contenido de forma correcta. | Explicación útil sin inspeccionar archivos. |
| 8 | files1099-boundary-05 | failed | Confundió una pregunta conceptual con una creación fallida. | No explicó la diferencia entre ubicaciones; sin operaciones adicionales. |

Recursos: 173.22 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2082.44 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
