# Procesos 813: 39 de 50 válidos, sin adopción

La adjudicación raíz completa de la tanda continua de 50 consultas del candidato 812 registra **39 válidos y 11 fallidos**. Hay 49 respuestas publicadas y un terminal composition_failed sin respuesta publicada. Frente a 811 (40/50), se ganan tres casos y se pierden cuatro: saldo de −1. La fuente 812 no está adoptada. La categoría y C03 siguen abiertos; no se acredita cobertura nueva.

La raíz revisó este informe contra los 50 juicios guardados y sus observaciones nuevas.

| Grupo | Válidos 813 | Fallidos 813 | Válidos 811 |
|---|---:|---:|---:|
| Listas | 11 | 0 | 11 |
| Conteos | 10 | 2 | 12 |
| Memoria | 9 | 2 | 8 |
| CPU | 9 | 2 | 9 |
| Recurso no especificado | 0 | 4 | 0 |
| Memoria de aplicaciones | 0 | 1 | 0 |
| Total | 39 | 11 | 40 |

Ganancias frente a 811: process795-memory_rank-06; process795-cpu_rank-06; process795-cpu_rank-09.

Pérdidas frente a 811: H0364; process795-count-06; process795-count-07; process795-cpu_rank-08.

Las razones siguientes se conservan literalmente de ROOT_ADJUDICATION.json:

| Caso fallido | Terminal | Razón raíz exacta |
|---|---|---|
| H0169 | published_final | Muestra cuatro PIDs/valores de memoria correctos pero afirma que incluye diez filas en la lista; cardinalidad falsa. |
| H0364 | published_final | Cinco instanciasCPU y porcentajes actuales correctos, pero declara diez listadas mientras muestra cinco; diferencia del recorte explícito veraz en811. |
| H0669 | published_final | Declara memoria y conserva cuatro PIDs/valores, pero afirma diez listados cuando aparecen cuatro; cardinalidad falsa. |
| H0675 | published_final | Atribuye el working set de una instancia ChatGPT a la aplicación de mayor memoria sin membresía ni agregado observados. |
| process795-count-06 | published_final | Conteo146 y límite accesible correctos, pero publica el identificador interno observationScope literalmente en la explicación; fuga de campo interno en prosa de producto. |
| process795-count-07 | composition_failed | Sin respuesta publicada: composition_failed con internal_code/recovery/internal_code/retry_exhausted pese a146observados disponibles. |
| process795-memory_rank-07 | published_final | Máximo con PID y896,68MB correctos, pero afirma un proceso observado cuando se observaron145; uno es sólo el devuelto. |
| process795-memory_rank-10 | published_final | Muestra cuatro PIDs/valores de memoria pero afirma diez listados; cardinalidad visible falsa. |
| process795-cpu_rank-08 | published_final | Máximo CPU con PID y porcentaje correcto, pero afirma una instancia accesible observada cuando fueron 145; una es sólo la devuelta. |
| process795-unspecified_rank-01 | published_final | Declara memoria y muestra cuatro PIDs/valores correctos, pero afirma que se muestran diez; cardinalidad visible falsa. |
| process795-unspecified_rank-02 | published_final | Declara memoria y muestra cuatro PIDs/valores correctos, pero afirma haber listado diez filas; cardinalidad visible falsa. |

**CPU 06 es válido.** Razón raíz exacta: Muestra dos máximos actuales con PIDs y porcentajes correctos sin cantidad pedida. Declara estos dos como máximos y diez suministrados, hecho verdadero del payload, sin afirmar diez mostrados; 145 observados accesibles y subconjunto explícitos.

| Medición | 813 | 811 |
|---|---:|---:|
| Duración de la tanda | 262,844 s | 253,406 s |
| Mediana de latencia hasta terminal | 4,726 s | 4,512 s |
| Percentil 95 hasta terminal, rango más próximo | 7,016 s | 7,133 s |
| Máximo de latencia hasta terminal | 9,587 s | 7,278 s |
| Pico de VRAM | 3.497,55859375 MiB | 3.499,55859375 MiB |
| Pico de RAM residente | 2.449,80859375 MiB | 2.455,98828125 MiB |

La latencia es la diferencia entre el primer y último evento shell registrado por turno. La etiqueta heredada «completed finals only» se corrigió antes del cierre en ROOT_CLOSURE.json: la estadística abarca 50 terminales, 49 published_final y 1 composition_failed; los tiempos y juicios no cambiaron. Por ello se presenta como **latencia hasta terminal**, sin atribuir 50 respuestas publicadas. Se usan los perfiles completos continuos de 813 y 811, sin combinar ejecuciones interrumpidas o reanudadas. No es latencia acústica.

RAM y VRAM se contabilizan por separado. El pico de VRAM de 813 queda por debajo de 4.096 MiB. RESOURCES registra telemetría GPU disponible y cero infracciones en el árbol propio de procesos del conductor. No acredita voz ni interfaz de escritorio visible.

EXIT registra salida 0; manifiesto, fuentes, fuente 812, runner y DLL sin cambios. Su quality_adjudicated:false pertenece al recibo de ejecución; el resultado de calidad procede de ROOT_ADJUDICATION.json posterior.

| Avance formal conservado | Estado |
|---|---|
| Encuesta | 28/742 cubiertos; 714 abiertos; 0 no aplicables. |
| Cobertura nueva | 0. |
| Matriz C03 | 3/11 cumplidas; 5 contradichas; 3 pendientes. |
| Categoría de procesos | Abierta. |
| Fuente 812 | No adoptada. |

La preparación documental no ejecutó producto ni pruebas. La raíz sí había validado812: 306 pruebas aprobadas, cero omisiones, 3,34 segundos; Fast0 y Release22,94s. Full804 es antecedente, no Full812 ni cierre.

Siguiente diferencia814: retirar únicamente la obligación de recitar ambas cardinalidades en cada ranking/lista; conservar conteos solicitados, filas, datos y alcance. La primera prosa errónea sigue disponible; no se promete mejora antes de815. El veto léxico de «current context» tiene diagnóstico separado en DIAGNOSIS_INTERNAL_CODE.md y no convierte aquella prosa en factual.

La fuente y evidencia publicadas antes de esta corrida están en2bb04ef4, Goal-c03. Main intacto. Respuestas literales y payloads completos: archivo privado C03-process-batch813-private/RESPUESTAS_ADJUDICADAS.md.
