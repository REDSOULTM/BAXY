# Estado de C03 — 11 de septiembre de 2026

**Se corrigió el cierre que impedía entregar una lectura OCR real. La validación completa pasó y BAXY recuperó íntegro el resultado guardado. C03 sigue abierto.** Aún no se ha verificado la respuesta sobre qué aplicación usa más memoria.

| Qué cambió | Qué se midió | Resultado |
|---|---|---|
| La captura mezclaba escalas de Windows y cortaba la imagen. | Una ventana de 2564 × 1320 píxeles y 20 comprobaciones nativas. | Captura completa; escala restaurada después. |
| Una lectura válida se rechazaba porque no había modificado el PC. | Prueba que reproducía el rechazo y comprobación real posterior. | El OCR real terminó verificado y conservó texto y posiciones. |
| El resultado se guardaba, pero era demasiado largo para entregarlo. | Reproducción del límite, transporte, reapertura del diario y conservación de datos. | 118 pruebas específicas aprobadas, sin fallos ni omisiones. Validación completa terminada con salida 0; recuperación real y conservación del contenido comprobadas. |
| Enfocar una ventana alteraba innecesariamente su tamaño. | 20 pruebas específicas y compilación. | Corrección aprobada. El intento posterior encontró la ventana ya activa; no se le atribuye esa activación. |

La tabla capturada del Administrador de tareas corta nombres y unidades dentro de su propia ventana. Windows rechazó maximizarla; se pidió una vez ayuda para mostrarla completa. La recuperación real entregó el resultado íntegro sin repetir la lectura ni modificar el diario; la proyección de la interfaz conservó texto y posiciones. No se ha enviado esa lectura real al modelo.

| Comparación sobre una tabla sintética | Respuestas válidas | Qué falló |
|---|---:|---|
| Composición actual de BAXY | 6/8 | Inventó un PID y afirmó un empate entre cifras distintas. |
| Control sin la composición de BAXY | 1/8 | Siete consultas agotaron el plazo sin respuesta. |
| Control con una instrucción de brevedad | 4/8 | Identificador contradictorio, nombre confundido, un plazo agotado y una comparación sin resolver. |

Los controles no mejoraron el conjunto y esa estrategia se cerró. En estas pruebas sintéticas, texto y posiciones llegaron completos al modelo. Sus resultados no acreditan la lectura de una aplicación real.

| Recursos medidos, por separado | VRAM pico | RAM residente pico |
|---|---:|---:|
| Última tanda de 50 consultas de procesos | 3497,56 MiB | 2454,28 MiB |
| Ocho consultas OCR con BAXY | 3495,56 MiB | 755,20 MiB |
| Último control de brevedad | 3495,56 MiB | 756,54 MiB |

La VRAM quedó bajo el techo de 4 GB. No hubo infracciones de las guardas. Las 50 consultas de procesos tardaron 246,829 s, con mediana de 4,229 s; las ocho consultas OCR con BAXY tardaron 32,25 s. Esta validación no ejecutó el modelo y no aporta otra medición de VRAM.

La tanda de procesos conserva 49/50 respuestas válidas: listas 11/11, conteos 12/12, memoria 11/11, CPU 11/11 y recurso no especificado 4/4. El caso restante atribuía la memoria de un proceso a toda una aplicación; sigue abierto.

| Avance formal | Estado |
|---|---|
| Encuesta | 36/742 cubiertos; 706 abiertos; 0 no aplicables. |
| Matriz C03 | 3/11 cumplidas; 5 contradichas; 3 pendientes. |
| Categorías nuevas cerradas | 0; total completo aún no definido. |
| Apertura de aplicaciones | 75 casos preparados, sin ejecutar. |

El método cuenta requisitos verificados con variantes, no el porcentaje de un panel pequeño. No hay una estimación fiable de cierre. Faltan la comparación real de aplicaciones, las conductas restantes, las ocho rutas de respuesta, cien turnos de aceptación, recuperación, interfaz real, voz y validación final.

La validación completa de esta corrección aprobó 4754 pruebas .NET y 12907 Python, con cero fallos. Se registraron una omisión agregada .NET, 16 avisos optativos que se solapan y tres omisiones Python; además, 466 subpruebas Python aprobadas. Las omisiones no cuentan como aprobaciones. Python terminó en 658,25 s. Esta evidencia no cierra los casos omitidos ni la comparación de memoria de aplicaciones.

BAXY permanece cerrado para uso manual. Main, la encuesta original y los cambios del dueño se conservan. [Procesos](PROCESS_BATCH824/REPORT.md), [OCR sintético](OCR_COMPOSER832/REPORT.md), [reparación actual](PROTOCOL843/CANDIDATE.json).
