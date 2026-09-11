# Estado de C03 — 11 de septiembre de 2026

C03 sigue abierto. La tanda 807 dio **37 respuestas válidas y 13 fallidas** en las mismas 50 consultas consecutivas. Empata con 805, pero recupera cinco casos y pierde otros cinco. La reparación del alcance, candidato 806, **sigue sin adoptar**. `main` permanece en `5f572ee1`; la evidencia publicada en origen llega a `86197f89`.

| Qué cambió | Resultado comprobado |
|---|---|
| Se explica el límite de observación con palabras, sin copiar su código interno. | El caso de memoria 08 vuelve a responder correctamente, sin exponer ese código. |
| Se midió el candidato 806 con los 50 casos. | Frente a 805: cinco recuperados y cinco perdidos. Frente a 801, que tenía 35 válidos: siete recuperados y cinco perdidos. |
| Se comprobó la integración del candidato. | 198 pruebas específicas aprobadas, cero omisiones; Fast y compilación Release correctos en 22,36 segundos, cero advertencias. Esto no es una validación Full de 806. |

| Qué se midió en 807 | Resultado |
|---|---|
| Respuestas válidas por grupo. | Listas 7/11; conteos 12/12; CPU 8/11; memoria 7/11; recurso no especificado 3/4; memoria de aplicaciones 0/1. |
| Duración de la tanda. | 241,093 segundos. |
| Espera registrada por respuesta. | Mediana general 4,364 segundos; listas 4,830; conteos 2,996; percentil 95 general 6,862; máximo 7,253 frente a 29,626 en 805. No es latencia de voz. |
| Pico de VRAM. | 3.497,55859375 MiB, aproximadamente 3,668 GB: bajo el techo de 4 GB. |
| Pico de RAM residente. | 2.449,53515625 MiB, aproximadamente 2,569 GB: inferior a 4 GB, contabilizada por separado de la VRAM. |

No se registraron infracciones de recursos en el árbol de procesos del producto medido. La prueba no acredita interfaz visible, voz ni el ciclo completo de BAXY funcionando junto.

| Qué falló | Qué falta corregir |
|---|---|
| Listas incompletas o con instancias fusionadas. | Conservar todos los miembros y distinguir procesos repetidos. |
| Respuestas de memoria sin identificadores. | Mantener los PIDs exigidos por el criterio de memoria. |
| Recortes ambiguos y cantidades contradictorias. | Distinguir procesos observados, filas devueltas y filas efectivamente mostradas. |
| Memoria de una aplicación. | No presentar un proceso como el agregado de toda una aplicación sin evidencia de pertenencia y suma. |

Ya se integró la propuesta de filas como candidato 808: cambia un párrafo existente y su prueba específica, y conserva modelo, presupuestos y comprobador. Sus seis suites dieron **204 aprobadas, cero omisiones, en 2,78 segundos**. Los controles de integración de 808 pasaron, con compilación en 21,84 segundos y cero advertencias o errores y todavía no hay medición de producto que demuestre una mejora de respuestas. Los 75 casos de apertura de aplicaciones están preparados y no ejecutados. También faltan las demás conductas de C03, las ocho rutas de respuesta, la aceptación de cien turnos, errores y recuperación, interfaz real, voz y validación final.

La última Full verde es la base 804, anterior a 806: Python, **12.714 aprobadas, 3 omisiones y 466 subpruebas**; .NET, **4.642 aprobadas y 1 omisión agregada**. La salida también imprime 16 omisiones optativas que no son un conjunto separado y no se suman. Ninguna omisión cuenta como aprobada. Sigue pendiente una Full final que cubra los cambios posteriores.

**Avance formal:** encuesta, **28/742 cubiertos, 714 abiertos y 0 no aplicables**; matriz C03, **3/11 filas cumplidas, 5 contradichas y 3 pendientes**. Hay **0 categorías nuevas cerradas**; el registro no define un total completo de categorías. Estos recuentos no constituyen un porcentaje de cierre del goal. **Estimación:** aún no hay un plazo fiable de cierre.

BAXY permanece cerrado para uso manual. Encuesta742/revisión1248 intacta; los cambios del dueño se conservan.
