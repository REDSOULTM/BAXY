# Estado de C03 — 11 de septiembre de 2026

**La captura ya recupera la ventana completa. Se reparó también el rechazo de una lectura OCR válida. C03 sigue abierto.** La comprobación completa terminó sin fallos, con las omisiones ambientales detalladas abajo. La primera prueba real encontró el Administrador de tareas, pero no pudo traerlo al frente; todavía no llegó a leer su memoria.

| Qué cambió y qué se comprobó | Resultado |
|---|---|
| Una ventana se recortaba por mezclar escalas de Windows. | Ahora captura2564×1320 completos;20 comprobaciones nativas aprobadas, incluida restauración del contexto de escala. |
| El kernel rechazaba OCR porque la lectura no había modificado el PC. | La prueba reprodujo el fallo; el catálogo distingue ahora lectura verificada de efecto. Mantiene privacidad y confirmación. |
| Pruebas de la última reparación | 35 de integración y161 del kernel aprobadas, sin fallos ni omisiones. Compilación aprobada. Full acumulado terminado con salida0. |

| Qué respondió sobre una tabla sintética de tres filas | Válidas | Fallos |
|---|---:|---|
| Composición actual de BAXY | 6/8 | Inventó unPID y afirmó un empate entre cifras distintas. |
| Control sin la composición de BAXY | 1/8 | Siete consultas agotaron el plazo sin respuesta recuperada. |
| Control con una instrucción de brevedad | 4/8 | Contradicción sobrePID, nombre confundido, un plazo agotado y una comparación sin resolver. |

Estos controles no mejoraron el conjunto: se cerró esa estrategia sin cambiar el compositor. Los fallos siguen abiertos. La prueba confirmó que texto, posiciones y huella de la imagen llegaban completos al modelo; no se acredita una aplicación real a partir de esta tabla.

| Recursos medidos, por separado | VRAM pico | RAM residente pico |
|---|---:|---:|
| Última tanda de50 consultas de procesos | 3497,56MiB | 2454,28MiB |
| Ocho consultas OCR con BAXY | 3495,56MiB | 755,20MiB |
| Último control de brevedad | 3495,56MiB | 756,54MiB |

La VRAM quedó bajo el techo de4GB, sin infracciones de las guardas. Las50 consultas de procesos tardaron246,829s, con mediana4,229s; las ocho consultas OCR con BAXY tardaron32,25s. Son mediciones distintas y no acreditan interfaz visible ni voz.

La tanda de procesos conserva49/50 válidas: listas11/11,conteos12/12,memoria11/11,CPU11/11,recurso no especificado4/4. El caso restante atribuía la memoria de un proceso a toda una aplicación; sigue pendiente. Se prepara una lectura contemporánea del grupo y su memoria mediante el Core real, con imágenes y recibos conservados antes de interpretar el resultado.

| Avance formal | Estado |
|---|---|
| Encuesta | 36/742 cubiertos;706 abiertos;0 no aplicables. |
| Matriz C03 | 3/11 cumplidas;5 contradichas;3 pendientes. |
| Categorías nuevas cerradas | 0;total completo aún no definido. |
| Apertura de aplicaciones | 75 casos preparados, sin ejecutar. |

El método cuenta requisitos verificados con variantes, no el porcentaje de un panel pequeño. No hay un plazo fiable de cierre. Faltan las conductas restantes, las ocho rutas de respuesta, cien turnos de aceptación, recuperación, interfaz real, voz y validación final.

El Full839 aprobó12907 pruebas Python, con3 omisiones y466 subpruebas, en653,33s; .NET aprobó4735, con1 omisión agregada y16 avisos optativos que se solapan. Cero fallos. Las omisiones no son aprobaciones. Se adopta la reparación de apoyo dentro de lo comprobado; C03 sigue abierto.

BAXY permanece cerrado para uso manual. Main, la encuesta original y los cambios del dueño se conservan. La captura corregida está publicada en Goal-c03,e7fbae65; la reparación OCR ya pasó la validación completa. También se probó una vez el atajo de Windows: aceptó las teclas, pero la ventana activa no cambió. La sesión está desbloqueada. Se corrigió que enfocar restaurara el tamaño innecesariamente:20 pruebas aprobadas ycompilación correcta. La nueva lectura encontró la ventana ya activa, por lo que no se ejecutó otro foco ni se atribuye aesa corrección. Maximizar falló; se pidió una vez ayuda para dejar la tabla completa. [Captura](OBSERVATION837/ROOT_REVIEW.md), [OCR con BAXY](OCR_COMPOSER832/REPORT.md), [último control](OCR_NATIVE838/REPORT.md), [procesos49/50](PROCESS_BATCH824/REPORT.md).

La lecturaOCR real guardó un resultado verificado, pero el Core se cerró antes de entregarlo: su mensaje tenía6532 caracteres yel transporte admitía4096. La reparación siguiente unifica ese límite conlos48000 ya admitidos por el productor yla interfaz. No llegó ninguna respuesta al modelo yno se acredita el caso de memoria de aplicaciones.
