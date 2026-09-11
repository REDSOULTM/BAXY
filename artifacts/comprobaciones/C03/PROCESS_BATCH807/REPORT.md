# Procesos807 — 37 de50 válidos, sin adopción

La adjudicación del agente raíz se conserva sin recalificar: **37/50 válidos, 13 fallidos**, candidato 806 sin adoptar. Tanda continua de 50; cinco ganancias y cinco pérdidas frente a 805 (37 válidos), siete ganancias y cinco pérdidas frente a 801 (35 válidos). La raíz conserva los50juicios y sus evidencias sin nuevo crédito.

Fuentes públicas: [adjudicación 807](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/PROCESS_BATCH807/ROOT_ADJUDICATION.json>), [recursos](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/PROCESS_BATCH807/RESOURCES.json>), [salida](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/PROCESS_BATCH807/EXIT.json>), [candidato 806](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/PROCESS_SCOPE806/CANDIDATE.json>) y [validación 806](<D:/Perfil/Escritorio/ETC/Programacion/BAXY DEFINITIVO/artifacts/comprobaciones/C03/PROCESS_SCOPE806/VALIDATION_EXIT.json>). Respuestas privadas para la revisión del agente raíz: [RESPUESTAS_ADJUDICADAS.md](<C:/Users/usuario/AppData/Local/BAXY/C03-process-batch807-private/RESPUESTAS_ADJUDICADAS.md>); contienen los50finales, payloads y juicios ya leídos por la raíz.

| Grupo | Válidos | Fallidos |
|---|---:|---:|
| Listas | 7 | 4 |
| Conteos | 12 | 0 |
| CPU | 8 | 3 |
| Memoria | 7 | 4 |
| Recurso no especificado | 3 | 1 |
| Memoria de aplicaciones | 0 | 1 |

Se mantienen los criterios del raíz: fidelidad a la observación fresca; miembros e instancias correctos; cantidades y alcance coherentes; orden y unidades fieles; PIDs exigidos en memoria. El criterio CPU no hereda automáticamente la exigencia de PID de memoria; la lista de nombres tampoco. Los recortes ambiguos no se excusan por tener valores correctos. La memoria de una aplicación requiere pertenencia y agregado, no sólo el working set de un proceso.

| Caso fallido | Motivo ya adjudicado, resumido |
|---|---|
| H0133 | Anuncia diez instancias, pero fusiona nombres repetidos y no las enumera todas. |
| H0158 | Multiplicidad de un proceso repetido incorrecta; lista incompleta. |
| H0169 | Muestra cuatro de diez filas sin identificar el recorte visible. |
| H0364 | Muestra cuatro de diez filas CPU y omite seis. |
| H0650 | Valores e instancias correctos, sin los PIDs exigidos en memoria. |
| H0675 | Presenta memoria de un proceso como memoria de una aplicación sin pertenencia ni agregado. |
| process795-list-02 | Nueve filas aunque anuncia diez; falta una instancia. |
| process795-list-04 | Nueve identificadores aunque afirma haber mostrado diez. |
| process795-memory_rank-02 | Máximo y valor correctos, falta el PID exigido. |
| process795-memory_rank-05 | Nombres y valores correctos, faltan los PIDs exigidos. |
| process795-memory_rank-07 | Confunde un proceso devuelto con el total observado y se contradice. |
| process795-cpu_rank-05 | Siete filas mientras afirma diez; omite tres filas de cero por ciento. |
| process795-cpu_rank-06 | Reduce diez filas a tres mientras anuncia diez en la lista. |

`process795-memory_rank-08` se recuperó, sin código interno ni veto. La corrección 806 cambia seis líneas de proyección para explicar el límite accesible; la propuesta de filas quedó aislada, sin integrar ni medir en 806. Actualización del raíz: fuente 808 ya integrada como candidato mediante el párrafo existente de `llm.py` y su test dueño. Se generaliza la regla de memoria al valor y unidad del recurso observado, con cobertura CPU; seis suites dieron 204 aprobadas, cero omisiones, en 2,78 s. Fast808 recogido0:Release21,84s/0advertencias/errores;29pins intactos; no hay medición de producto 808 ni adopción acreditada. Modelo, presupuestos y checker sin cambios.

Duración 241,093 s; mediana general 4,364 s, listas 4,830 s y conteos 2,996 s; p95 por rango más próximo 6,862 s; máximo 7,253 s frente a 29,626 s en 805. La latencia mide el intervalo entre primer y último evento shell del turno con final completado; no es acústica. Pico VRAM 3.497,55859375 MiB y RAM residente 2.449,53515625 MiB, separados; telemetría GPU disponible y cero infracciones. Alcance: árbol propio de procesos del conductor del producto, sin crédito de interfaz ni voz.

`EXIT.json` confirma salida 0 e integridad de fuentes, manifiesto, runner y DLL. Su `quality_adjudicated: false` describe el recibo de ejecución, no sustituye la adjudicación posterior del raíz. Validación 806: seis suites específicas, 198 aprobadas y cero omisiones; Fast/Release 22,36 s y cero advertencias según el relevo del raíz. Full 804 es sólo base previa Python 802 + C# 804: 12.714 Python aprobadas, 3 omisiones, 466 subpruebas; 4.642 .NET aprobadas, 1 omisión agregada, 16 omisiones optativas impresas no disjuntas. No se atribuye esa Full a 806.

Publicación verificada por raíz: HEAD y origen `86197f89`; `main` permanece en `5f572ee1`. Encuesta 28/714/0; matriz 3 cumplidas, 5 contradichas, 3 pendientes; cero categorías nuevas cerradas, denominador total de categorías indefinido. Aplicaciones: 75 casos preparados, sin ejecutar. Sin crédito de UI/voz ni cierre de C03.
