# Procesos 811 — 40 de 50 válidos, sin adopción

La tanda continua de 50 consultas del candidato 810 obtuvo **40 respuestas válidas y 10 fallidas** según la adjudicación completa de la raíz. Frente a 809, con 37/50, recupera diez casos y pierde siete: mejora neta de tres respuestas, insuficiente para adoptar el candidato por sus siete regresiones. C03 sigue abierto y no recibe cobertura nueva.

810 sustituye nombre y PID separados por una identidad conjunta en seis líneas de la proyección existente cuando ambos son válidos. Conserva observación canónica, nombres exactos, filas, orden, alcance, cantidades, unidades e identidades incompletas tipadas. No modifica instrucciones, verificador, modelo ni presupuesto. En 811 se conservan los PIDs de las filas efectivamente mostradas; persisten errores al relacionar cantidades con su población y al atribuir memoria de procesos a aplicaciones.

| Grupo | Válidas 811 | Fallidas 811 | Válidas 809 |
|---|---:|---:|---:|
| Listas | 11 | 0 | 9 |
| Conteos | 12 | 0 | 12 |
| Memoria | 8 | 3 | 3 |
| CPU | 9 | 2 | 9 |
| Recurso no especificado | 0 | 4 | 4 |
| Memoria de aplicaciones | 0 | 1 | 0 |
| Total | 40 | 10 | 37 |

Las diez ganancias frente a 809 son H0650; process795-list-08 y -09; process795-memory_rank-01, -02, -03, -05, -08 y -09; process795-cpu_rank-08. Las siete pérdidas son H0169, H0669; process795-memory_rank-06 y -10; process795-cpu_rank-09; process795-unspecified_rank-01 y -02. Frente a 801, con 35 válidas, hay diez ganancias y cinco pérdidas.

| Fallos restantes | Casos | Criterio incumplido |
|---|---|---|
| Alcance y población observada: 3 | process795-memory_rank-06, process795-memory_rank-07, process795-cpu_rank-09 | Declaran respectivamente tres, uno y dos procesos observados cuando se observaron 139. Esas cantidades corresponden a las filas devueltas o solicitadas. |
| Filas omitidas pero afirmadas como mostradas: 6 | H0169, H0669, process795-memory_rank-10, process795-cpu_rank-06, process795-unspecified_rank-01, process795-unspecified_rank-02 | Afirman diez listados; CPU 06 muestra uno y los otros cinco casos muestran cuatro. Identidades y valores correctos de esas filas no reparan la cardinalidad falsa. |
| Memoria de aplicación: 1 | H0675 | Atribuye el working set de un proceso python a la aplicación de mayor consumo sin membresía ni agregado observados. |

El criterio distingue procesos observados, filas devueltas y filas efectivamente mostradas. **H0364 es válido**: presenta dos máximos actuales por intervalo con PIDs y porcentajes correctos, declara dos mostrados de 145 observados y explicita el recorte a los primeros dos del ranking accesible. No se solicitó un número concreto. No corresponde imponer una cuota de diez filas a una petición CPU sin cantidad explícita. El fallo de los seis casos anteriores es afirmar una cantidad mostrada falsa.

| Medición | 811 | 809 |
|---|---:|---:|
| Duración de la tanda | 253,406 s | 243,250 s |
| Mediana general por respuesta | 4,512 s | 4,209 s |
| Percentil 95, rango más próximo | 7,133 s | 6,785 s |
| Máximo por respuesta | 7,278 s | 7,516 s |
| Pico de VRAM | 3.499,55859375 MiB | 3.497,55859375 MiB |
| Pico de RAM residente | 2.455,98828125 MiB | 2.399,80859375 MiB |

La latencia mide la diferencia entre primer y último evento shell registrado del turno con final completado. Ambas tandas son continuas y completas; no se combinan perfiles interrumpidos o reanudados. No es latencia acústica. RAM y VRAM se contabilizan por separado; el pico de VRAM queda bajo el techo de 4.096 MiB. Hubo telemetría GPU y cero infracciones en el árbol propio de procesos del conductor. No se acredita voz ni interfaz de escritorio visible.

EXIT registra salida 0 y manifiesto, fuentes, candidato 810, runner y DLL intactos. Su campo quality_adjudicated:false corresponde al recibo de ejecución; los 40 válidos y 10 fallidos proceden de ROOT_ADJUDICATION posterior.

| Validación disponible | Resultado |
|---|---|
| Siete suites dueñas de 810 | 247 aprobadas, 0 omisiones, 3,04 s; salida 0. |
| Fast 810 | Salida 0; Release 22,18 s, 0 advertencias y 0 errores; 30 pins intactos. |
| Full 804, base anterior | Python: 12.714 aprobadas, 3 omisiones y 466 subpruebas. .NET: 4.642 aprobadas y 1 omisión agregada. Las 16 omisiones optativas impresas no son disjuntas y no se suman. |

Full 804 no acredita Full 810. Las omisiones no cuentan como aprobadas; siguen pendientes la Full de adopción acumulada y la de cierre.

| Avance formal | Estado |
|---|---|
| Encuesta | 28/742 cubiertos; 714 abiertos; 0 no aplicables. |
| Matriz C03 | 3/11 cumplidas; 5 contradichas; 3 pendientes. |
| Categorías nuevas cerradas | 0; total completo no definido. |
| Ocho rutas de respuesta | Pendientes. |
| Apertura de aplicaciones | 75 casos preparados, sin ejecutar. |

El siguiente candidato, 812, propone representar cada cuenta ligada a su población dentro de la proyección existente: observados dentro del alcance y filas devueltas, sin convertir estas últimas en filas mostradas antes de producir la respuesta. Su implementación se prepara en worktree aislado, sin integración ni medición nuevas. No supone cambios de instrucciones ni del verificador. Continúan pendientes las otras conductas, cien turnos de aceptación, errores y recuperación, interfaz, voz y validación final. Última publicación verificada: f4480bf2 en Goal-c03; main permanece en 5f572ee1.
