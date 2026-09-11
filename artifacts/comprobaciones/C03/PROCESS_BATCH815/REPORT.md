# Procesos 815: 39 de 50 válidos, sin adopción

Revisado e integrado por la raíz contra ROOT_ADJUDICATION.json y ROOT_CLOSURE.json. Conserva los 50 juicios sellados; no añade crédito.

La tanda continua de 50 consultas del candidato 814 registra **39 válidos y 11 fallidos**, con 48 respuestas publicadas y dos terminales composition_failed. Frente a 813, también 39/50, hay diez ganancias y diez pérdidas. La fuente 814 sigue sin adoptar. La categoría de procesos y C03 permanecen abiertos.

| Grupo | Válidos 815 | Fallidos 815 | Válidos 813 |
|---|---:|---:|---:|
| Listas | 3 | 8 | 11 |
| Conteos | 12 | 0 | 10 |
| Memoria | 9 | 2 | 9 |
| CPU | 11 | 0 | 9 |
| Recurso no especificado | 4 | 0 | 0 |
| Memoria de aplicaciones | 0 | 1 | 0 |
| Total | 39 | 11 | 39 |

Ganancias frente a 813: H0169; H0364; H0669; process795-count-06; process795-count-07; process795-memory_rank-07; process795-memory_rank-10; process795-cpu_rank-08; process795-unspecified_rank-01; process795-unspecified_rank-02.

Pérdidas frente a 813: H0158; process795-list-02; process795-list-03; process795-list-04; process795-list-05; process795-list-06; process795-list-07; process795-list-08; process795-memory_rank-03; process795-memory_rank-05.

| Fallo adjudicado | Casos | Alcance |
|---|---:|---|
| Lista publicada sin conteo observado | 7 | H0158 y list-02, 03, 04, 05, 07, 08. Algunas también omiten el alcance o la identificación del recorte. |
| Lista agotada sin respuesta | 1 | list-06: seis vetos invented; el primer borrador también omite el conteo observado. |
| Ranking de memoria agotado | 1 | memory_rank-03, t31: sin borrador de resultado; no se juzgan hechos no vistos. |
| Ranking de memoria sin magnitudes | 1 | memory_rank-05: los dos máximos y sus PIDs son correctos, pero faltan cantidades y unidad de memoria residente. |
| Memoria de proceso atribuida a aplicación | 1 | H0675: falta membresía y agregado observados de la aplicación. |

CPU 06 es válido: identifica el máximo actual con PID y 5,59 % correctos. No se pidió una cantidad concreta y no afirma mostrar más filas. Se conserva el criterio sellado, sin introducir una cuota nueva.

La raíz decidió detener los ajustes de redacción después de dos variantes sin mejora y corregir los falsos vetos ya identificados, además del deadline de la consulta de cinco filas. El diagnóstico del falso veto sobre complete/completeness está publicado en DIAGNOSIS_LEXICAL.md, junto a esta tanda. Corregir ese veto no resuelve por sí solo la omisión factual de list-06.

Para t31, la captura registra seis composiciones shell con límite exterior de 5 segundos e interior de 4 segundos, sin borrador de resultado. Esto no prueba cuánto tardó la operación nativa ni demuestra que ella agotara el plazo. La causa debe conservarse separada de la calidad de hechos que no llegaron a mostrarse.

| Medición | 815 | 813 |
|---|---:|---:|
| Duración de la tanda | 414,11 s | 262,844 s |
| Mediana hasta terminal | 5,262 s | 4,726 s |
| Percentil 95 hasta terminal, rango más próximo | 11,051 s | 7,016 s |
| Máximo hasta terminal | 60,002 s | 9,587 s |
| Pico de VRAM | 3.497,55859375 MiB | 3.497,55859375 MiB |
| Pico de RAM residente | 2.429,734375 MiB | 2.449,80859375 MiB |

La latencia es la diferencia entre el primer y último evento shell registrado por turno e incluye los 50 terminales, también los fallidos. Cada tanda usa su perfil continuo completo. No mide latencia acústica ni duración nativa aislada. El Administrador de tareas de 814 estaba vivo durante 815 y ausente durante 813, según la raíz: es un confusor de entorno y no permite atribuir el aumento exclusivamente al prompt.

RESOURCES registra telemetría GPU disponible y cero infracciones en el árbol propio del conductor. RAM y VRAM se contabilizan por separado. La VRAM queda bajo 4.096 MiB y bajo la guarda de 3.800 MiB. Esto no acredita voz ni interfaz de escritorio visible.

EXIT registra salida 0 y manifiesto, fuentes, fuente 814, runner y DLL sin cambios. quality_adjudicated:false es el recibo de ejecución; los 39/50 proceden de la adjudicación raíz posterior.

| Validación y avance conservados | Estado |
|---|---|
| Fuente 814 | 306 pruebas aprobadas, cero omisiones, 3,62 s; Fast correcto; Release 25,34 s, sin advertencias ni errores. Valida fuente, no sustituye Full. |
| Full 804 anterior a los candidatos | Python: 12.714 aprobadas, 3 omisiones y 466 subpruebas. .NET: 4.642 aprobadas y 1 omisión agregada, con 16 optativas impresas que se solapan. Ninguna omisión cuenta como aprobada. |
| Validación pendiente | Full acumulado de adopción y Full final. |
| Encuesta | 28/742 cubiertos; 714 abiertos; 0 no aplicables. |
| Matriz C03 | 3/11 cumplidas; 5 contradichas; 3 pendientes. |
| Cobertura nueva y categorías nuevas cerradas | 0. |
| Interfaz y voz nuevas; aceptación de cien turnos | Sin acreditar. |
| Última publicación comunicada | b997816d en Goal-c03; main 5f572ee1 intacto. |

La adjudicación íntegra y sus respuestas literales permanecen en el directorio privado C03-process-batch815-private. Los recibos públicos conservan las huellas y resultados sin publicar los datos del equipo.
