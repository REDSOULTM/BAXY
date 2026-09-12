# MUSIC1077 — adjudicación de la raíz

## MUSIC1077 — estado vigente 2026-09-12T18:02:53.762552+00:00

Parcial: 0 aprobados, 3 fallidos, 16 sin ejecutar; 0 créditos.

| Cubiertos | Abiertos | No aplican | Primeras altas últimas 24 h | Categorías cerradas |
|---:|---:|---:|---:|---:|
| 186/742 | 556 | 0 | >=60 | 0/35 |

Procedencia de primeras altas: Al menos60 primeras altas verificadas hoy:28 Kiro y32 retorno; no se cuentan las revalidaciones ni actualizaciones de abiertos.

Siguiente acción: Tras adjudicar, integrar hipótesis1079: ampliar postlectura del control SMTC de350ms a2s, mismo dispatch y criterios. Compilar .NET sin suites por orden del dueño. Sellar1080 con los mismos19objetos, perfiles nuevos separados por caso y preservación íntegra del perfil1077 incierto. Reejecutados en1077:3,6,7;16 no ejecutados en ese padre, con historia previa conservada. No contar borradores como terminales ni efectos no verificados como éxito. C03 activo, formal3/11.

Evidencia: `artifacts/comprobaciones/C03/MUSIC1077/ROOT_ADJUDICATION.json`. Sin pruebas por instrucción expresa del dueño.

Recursos de los segmentos: 99.84 s acumulados; pico GPU 3497.56 MiB; pico RAM 2061.00 MiB. El muestreo del árbol de procesos puede incluir descendientes ajenos a BAXY; no representa consumo exclusivo del modelo.

| Índice | Caso | Veredicto | Causa de la raíz | Observación |
|---:|---|---|---|---|
| 6 | music1037-dev-03 | failed | El control de reanudación fue emitido, pero el proveedor agotó la postlectura y devolvió efecto incierto. No acredita la variante. | Pre Aurora de cobre paused0:20; media.control632be546-778b-4699-8e58-bebf5ea30ff8 failed/smtc_postcondition_not_verified/verifiedfalse/resultnull/effectMayHaveOccurredtrue. Postlectura y UI playing0:45 no convierten ese recibo en éxito retrospectivo. Final indica resultado no verificado.1079 propone ampliar sólo la observación, sin repetir dispatch. |
| 7 | music1037-dev-04 | failed | No hubo respuesta final útil ni control nuevo; el perfil conservaba la incertidumbre de la variante anterior. La medición no aísla esta conducta. | La selección recuperó media.control y source_app dejó de bloquear. Ninguna nueva operación multimedia; Aurora permaneció pausada1:09 después de nueva precondición manual de raíz. Auditoría t0 restauró pendingRequest del caso6 y t1 compuso error de resultado no verificado. Terminal composition_failed/no_response; no demuestra regresión de interpretación ni crédito. |
| 3 | H0567 | failed | El salto se ejecutó y tuvo un borrador fiel aceptado, pero el terminal reportado fue composition_failed; no se acredita con una respuesta final no establecida. | Pre Rio de cristal playing, control6deb8cde-bad2-4c13-bb8b-00dcdf39e250 completed/verifiedtrue/replayedfalse Sendero azul playing y postlectura coincide. Composer t1 publicó un borrador completo con canción/artista/estado; t0 siguió restaurando incertidumbre anterior. case-observations declaró no_response;recovery:no_response;retry_exhausted. Se conserva discrepancia y se aislarán perfiles de casos, sin borrar la misión incierta ni atribuirle operaciones ajenas. |

Recursos: 99.84 s de segmentos; pico GPU 3497.56 MiB; pico RAM 2061.00 MiB. La muestra del árbol de procesos puede incluir descendientes ajenos a BAXY; no equivale a consumo exclusivo del modelo.

Sólo se atribuyen invocaciones nuevas de cada segmento. Los cambios espontáneos de canción o estado no acreditan efectos del producto. Los casos no ejecutados conservan sus datos y estado.
