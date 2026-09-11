# Procesos 809 — 37 de 50 válidos, sin adopción

La adjudicación final de la raíz da **37 respuestas válidas y 13 fallidas** en una tanda continua de 50 consultas del candidato 808. Frente a 807, también con 37 válidas, hay **siete ganancias y siete pérdidas**. No hay mejora neta y la categoría sigue sin adoptar. Este informe transcribe los juicios públicos ya cerrados; no vuelve a evaluar respuestas ni concede cobertura.

| Grupo | Válidas 809 | Fallidas 809 | Válidas 807 |
|---|---:|---:|---:|
| Listas | 9 | 2 | 7 |
| Conteos | 12 | 0 | 12 |
| CPU | 9 | 2 | 8 |
| Memoria | 3 | 8 | 7 |
| Recurso no especificado | 4 | 0 | 3 |
| Memoria de aplicaciones | 0 | 1 | 0 |
| Total | 37 | 13 | 37 |

Frente a 801, con 35 válidas, la adjudicación registra once ganancias y nueve pérdidas. El empate con 807 no acredita estabilidad: las mejoras de listas y CPU conviven con pérdidas de identidad en memoria.

| Casos fallidos | Motivo ya adjudicado, resumido |
|---|---|
| H0650; process795-memory_rank-01, -02, -03, -05, -08 y -09 | Faltan los identificadores de proceso exigidos para memoria, aunque las instancias y sus valores sean correctos. |
| process795-memory_rank-07 | Omite el identificador y confunde la fila devuelta con el número de procesos observados. |
| H0675 | Atribuye la memoria de un proceso a una aplicación sin pertenencia ni agregado verificados. |
| process795-list-08 y -09 | Confunde el recorte del listado con el alcance accesible de la observación. |
| process795-cpu_rank-06 | Muestra dos filas mientras declara diez; omite ocho. |
| process795-cpu_rank-08 | Confunde el único proceso devuelto con el total observado. |

El caso de memoria 08 sí tiene un final publicado; su fallo actual es la ausencia de identificadores. No debe confundirse con el antiguo fallo sin respuesta. Los criterios de CPU y listas no heredan automáticamente la exigencia de identificadores de memoria. Se conserva la separación entre procesos observados, filas devueltas y filas efectivamente mostradas.

| Medición | 809 | 807 |
|---|---:|---:|
| Duración de la tanda | 243,250 s | 241,093 s |
| Mediana general por respuesta | 4,209 s | 4,364 s |
| Percentil 95 general, rango más próximo | 6,785 s | 6,862 s |
| Máximo por respuesta | 7,516 s | 7,253 s |
| Mediana de listas | 6,603 s | 4,830 s |
| Mediana de conteos | 3,028 s | 2,996 s |
| Pico de VRAM | 3.497,55859375 MiB | 3.497,55859375 MiB |
| Pico de RAM residente | 2.399,80859375 MiB | 2.449,53515625 MiB |

La latencia es el intervalo entre el primer y el último evento shell registrado del turno con final completado; no es latencia acústica. Las dos comparaciones corresponden a tandas continuas completas. El pico de VRAM queda por debajo del techo de **4.096 MiB**. RAM y VRAM se contabilizan por separado. Hubo telemetría GPU disponible y cero infracciones en el árbol propio de procesos del conductor. No se acredita interfaz visible ni voz.

`EXIT.json` registra salida 0 y fuentes, candidato 808, manifiesto, runner y DLL sin cambios. Su campo `quality_adjudicated: false` pertenece al recibo de ejecución; el resultado de calidad procede de la adjudicación posterior de la raíz.

| Validación conservada | Alcance y resultado |
|---|---|
| Suites dueñas del candidato 808 | 204 aprobadas, 0 omisiones, 2,78 s. |
| Fast 808 | Salida 0; Release en 21,84 s, 0 advertencias y 0 errores. |
| Full 804 | Base anterior: Python 12.714 aprobadas, 3 omisiones y 466 subpruebas; .NET 4.642 aprobadas y 1 omisión agregada. Las 16 omisiones optativas impresas no son disjuntas y no se suman. |

**Full 804 no es Full 808.** Las omisiones no cuentan como aprobadas y falta una Full final que cubra los cambios posteriores. Los datos de las validaciones 808 y Full 804 se conservan del informe 807 y del estado existente; este trabajo documental no ejecutó pruebas.

| Avance formal, sin nuevo crédito | Estado |
|---|---|
| Encuesta | 28/742 cubiertos; 714 abiertos; 0 no aplicables. |
| Matriz C03 | 3/11 filas cumplidas; 5 contradichas; 3 pendientes. |
| Categorías nuevas cerradas | 0; el registro no define un total completo de categorías. |
| Ocho rutas de respuesta | Pendientes. |
| Apertura de aplicaciones | 75 casos preparados, sin ejecutar. |

Estos recuentos no son un porcentaje de cierre de C03. Tras 807 y 809 sin mejora neta, la raíz cambiará de estrategia; no corresponde otro retoque de instrucciones a ciegas. Continúan abiertos memoria de aplicaciones, identificadores y coherencia entre conteos, recortes y alcance, además de las demás conductas, aceptación de cien turnos, errores y recuperación, interfaz, voz y validación final.

Evidencia: ROOT_ADJUDICATION.json, VERIFICATION_STATUS.json, EXIT.json, RESOURCES.json y ROOT_CLOSURE.json en este directorio. Raíz revisó este informe; los 50 juicios permanecen intactos. El siguiente candidato810 cambia únicamente la representación de identidad en la proyección existente; no está integrado ni medido.
