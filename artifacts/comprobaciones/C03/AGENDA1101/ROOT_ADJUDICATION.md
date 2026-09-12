# AGENDA1101 — adjudicación de la raíz

## AGENDA1101 — estado vigente 2026-09-12T21:53:11.2194319Z

Parcial: 1 aprobados, 6 fallidos, 8 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 197/742 | 545 | 0 | >=71 | 0/35 |

Procedencia de primeras altas: Al menos 71 primeras altas verificadas: 28 del relevo Kiro y 43 del retorno hasta DIALOGUE1093. No se cuentan revalidaciones ni verification_updated_at.

Siguiente acción: Integrar AGENDA1103: recolocar la llamada existente de aclaración temporal antes de la guarda que impedía alcanzarla; sin nuevas reglas ni efectos. Medir WEB1102 según masa y disponibilidad mientras se prepara AGENDA1104 con nuevo candidato y pares antes de seis literales. Los fallos de composición siguen separados. Sin tests por instrucción del dueño.

Evidencia: `artifacts/comprobaciones/C03/AGENDA1101/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 184.63 s acumulados; pico GPU 3497.56 MiB; pico RAM 1694.97 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

Segmentos iniciados: 7; abortados antes de admisión: 0. Los abortos anteriores a la admisión no son fallos de producto ni literales ejecutados.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 6 | agenda1097-dev-01 | failed | Volvió a pedir una hora ya indicada. | La reparación no mejoró esta variante; sin operaciones adicionales. |
| 8 | agenda1097-dev-07 | failed | Promesa de recordatorio no creado y ausencia de aclaración. | La reparación no mejoró esta variante; sin operaciones adicionales. |
| 10 | agenda1097-boundary-01 | failed | Respuesta inconexa ante prohibición explícita. | Sin programación, pero la respuesta no es útil. |
| 11 | agenda1097-boundary-02 | failed | Añadió un período temporal ausente en la cita. | Explicación no fiel aunque no hubo programación. |
| 12 | agenda1097-boundary-03 | failed | Trató una hipótesis como solicitud fuera de alcance. | Respuesta no pertinente; sin programación. |
| 13 | agenda1097-boundary-04 | failed | Trató el relato de un hecho pasado como pedido fuera de alcance. | No respondió a la intención narrativa; sin operaciones adicionales. |
| 14 | agenda1097-boundary-05 | passed | Explicó la diferencia conceptual pedida. | Respuesta útil sin consultar ni modificar agenda. |

Recursos: 184.63 s de segmentos; pico GPU 3497.56 MiB; pico RAM 1694.97 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. El aislamiento de contexto o la ausencia de operaciones no acredita por sí sola una respuesta útil. Los casos no ejecutados conservan sus datos y estado.
