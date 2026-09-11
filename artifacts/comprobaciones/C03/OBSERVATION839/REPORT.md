# Candidato839 — OCR verificado y Full acumulado

El OCR local válido conserva ahora su resultado al pasar por el handler del Core. Antes, la clasificación de privacidad exigía indebidamente que una lectura hubiera modificado el PC. La propiedad `RequiresObservedEffect` pertenece al catálogo existente; sólo OCR desactiva esa exigencia. Se mantienen la privacidad, la confirmación exacta y las comprobaciones de operación, verificación, resultado y error.

| Validación | Resultado |
|---|---|
| Reproducción del rechazo | 1 fallo antes de reparar; recibo verificado de lectura descartado. |
| Dueñas de raíz | 35 integración y161 kernel aprobadas, cero fallos y cero omisiones. |
| Fast | Salida0; build Release9,33s. |
| Full839 | Salida0, sesión43122 recogida en75af48. |
| .NET completo | 4735 aprobadas, cero fallos, una omisión agregada.16 avisos optativos no disjuntos, conservados aparte. |
| Python completo | 12907 aprobadas, cero fallos,3 omisiones;466 subpruebas aprobadas;653,33s. |
| Integridad | 50/50 archivos sellados sin cambios durante Full ni al recogerlo. |

Comando: `scripts/test_source_quality.ps1 -Mode Full -QualityPython C:/Users/usuario/AppData/Local/BAXYQuality/source-quality-v1/Scripts/python.exe`. [Resultado](FULL_RESULT.json), [recibo](FULL_EXIT.json), [revisión y dueñas](ROOT_REVIEW.json), [adopción acotada](ADOPTION.json).

Se adopta la fuente de apoyo acumulada829/837/839. La captura nativa837 ya verificó20 condiciones con imagen completa2564×1320 y restauración de escala. El Full contiene esas reparaciones. Las omisiones ambientales no son aprobaciones; esto no cierra la entrega C03.

La primera prueba834 por el Core real encontró el Administrador de tareas pero `window.focus` devolvió `action_failed`, antes de capturar o ejecutar OCR. [Resultado834](../REAL_OBSERVATION834/INITIAL_RESULT.json). No se reintentó el efecto ni se atribuyó a elevación sin medir. Sus recibos privados y los62 pins de fuente/binarios están conservados.

H0675 «qué app usa más memoria» sigue abierto. El compositor conserva6/8 sobre la tabla sintética, con PID inventado y empate falso; los controles836/838 no mejoraron el conjunto y están cerrados. Encuesta36 cubiertos/706 abiertos/0 no aplicables; matriz3/11; C03 EN_CURSO. No se infiere crédito de interfaz, voz, aceptación ni memoria de aplicaciones a partir de estas pruebas.
