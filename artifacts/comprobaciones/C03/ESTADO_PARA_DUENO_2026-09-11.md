# Estado para el dueño — 11 de septiembre

La encuesta está en **64/742 cubiertos, 678 abiertos y 0 no aplican**. Se acreditaron 36 requisitos en las últimas 24 horas. Dos actualizaciones adicionales de casos cubiertos no permiten distinguir la fecha de su primera acreditación. Hay 0/35 categorías cerradas; la matriz C03 permanece en3/11.

Audio861 acreditó18 solicitudes de volumen. La continuación de apps acreditó Spotify; otras dos respuestas útiles quedaron abiertas porque todavía faltan variantes de su misma conducta. Las causas de los demás fallos ya constan por case_id.

Web y apps empatan con46 abiertos. Web864 terminó sus52 casos sin crédito nuevo. Varias navegaciones quedaron sin el paso de confirmación y las búsquedas devolvieron fallos. Ya está publicada una corrección mínima del nombre de Configuración y una continuación para dos casos de apps que necesitan variantes. Nueve literales de Steam y juegos quedan aparcados hasta disponer de6000MiB de RAM libre, con los límites de ejecución originales. Esto responde a tres cortes por RAM; no se repiten las tandas completas.

La continuación de apps terminó24/24 en88,25s sin exceder recursos:3497,56MiB de VRAM y2490,64MiB de RAM del árbol. Spotify reutilizó una ventana existente. Explorer produjo un efecto incierto: no se atribuye éxito ni se reintenta automáticamente. El audio continúa restaurado a31%, sin silencio.

El candidato anterior860 pasó3583 pruebas dueñas, cero fallos y cero omisiones, más estática y compilación Release. El Full843 histórico aprobó4754 pruebas.NET y12907 Python, con una omisión agregada.NET y tres Python, además de466 subpruebas aprobadas. No se cuentan las omisiones como aprobaciones ni se atribuye ese Full al Python posterior. Falta el Full final.

H0675, OCR y nuevos providers siguen aparcados. El Administrador de tareas se conserva como lo dejaste. C03 sigue en curso; main y tus cambios se conservan. La [tabla de categorías del checkpoint](CHECKPOINT.md) está ordenada por abiertos.

Por tu nueva instrucción, no se lanzan suites de tests ni Full. La aclaración sobre paneles de producto está pendiente; el trabajo continúa con revisión y cambios mínimos. Ninguna prueba omitida se contará como aprobada.

La corrección de Configuración ocupa una línea. La revisión del código conserva la identidad del catálogo y el rechazo de destinos ambiguos; aún no se ha comprobado en el producto. Ya está incorporada la reparación que respeta Google cuando se pide ese buscador, evitando enviar esas palabras como parte de una búsqueda en Bing.

También se ajustó la lectura de nombres para peticiones como «una terminal», conservando la comprobación contra aplicaciones instaladas. Los cambios nuevos sólo tienen revisión de código: no se ejecutaron tests ni se sumó cobertura por ellos.
