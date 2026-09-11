# Estado para el dueño — 11 de septiembre

La encuesta está en **64/742 cubiertos, 678 abiertos y 0 no aplican**. Se acreditaron 36 requisitos en las últimas 24 horas. Dos actualizaciones adicionales de casos cubiertos no permiten distinguir la fecha de su primera acreditación. Hay 0/35 categorías cerradas; la matriz C03 permanece en3/11.

Audio861 acreditó18 solicitudes de volumen. La continuación de apps acreditó Spotify; otras dos respuestas útiles quedaron abiertas porque todavía faltan variantes de su misma conducta. Las causas de los demás fallos ya constan por case_id.

Web y apps empatan con46 abiertos. Web864 terminó sus52 casos sin crédito nuevo. Varias navegaciones quedaron sin el paso de confirmación y las búsquedas devolvieron fallos. Ya está publicada una corrección mínima del nombre de Configuración y una continuación para dos casos de apps que necesitan variantes. Nueve literales de Steam y juegos quedan aparcados hasta disponer de6000MiB de RAM libre, con los límites de ejecución originales. Esto responde a tres cortes por RAM; no se repiten las tandas completas.

La continuación de apps terminó24/24 en88,25s sin exceder recursos:3497,56MiB de VRAM y2490,64MiB de RAM del árbol. Spotify reutilizó una ventana existente. Explorer produjo un efecto incierto: no se atribuye éxito ni se reintenta automáticamente. El audio continúa restaurado a31%, sin silencio.

El candidato anterior860 pasó3583 pruebas dueñas, cero fallos y cero omisiones, más estática y compilación Release. El Full843 histórico aprobó4754 pruebas.NET y12907 Python, con una omisión agregada.NET y tres Python, además de466 subpruebas aprobadas. No se cuentan las omisiones como aprobaciones ni se atribuye ese Full al Python posterior. El Full final se omite por decisión posterior del dueño.

H0675, OCR y nuevos providers siguen aparcados. El Administrador de tareas se conserva como lo dejaste. C03 sigue en curso; main y tus cambios se conservan. La [tabla de categorías del checkpoint](CHECKPOINT.md) está ordenada por abiertos.

Por tu nueva instrucción, no se lanzan suites de tests ni Full. El dueño aprobó mantener los paneles reales para acreditar encuesta. Ninguna prueba omitida se contará como aprobada.

La corrección de Configuración ocupa una línea. La revisión del código conserva la identidad del catálogo y el rechazo de destinos ambiguos; aún no se ha comprobado en el producto. Ya está incorporada la reparación que respeta Google cuando se pide ese buscador, evitando enviar esas palabras como parte de una búsqueda en Bing.

También se ajustó la lectura de nombres para peticiones como «una terminal», conservando la comprobación contra aplicaciones instaladas. Los cambios nuevos sólo tienen revisión de código: no se ejecutaron tests ni se sumó cobertura por ellos.

Las órdenes directas y los pedidos «quiero que abras…» comparten ahora la extracción del nombre. Esto permite usar los artículos y alias que BAXY ya conoce sin duplicar esa gramática. La verificación en el producto sigue pendiente. Se prepara una continuación para dos literales de apps que aún no se habían ejecutado en los recibos consultados.

También se ajustó «no, mejor abrí…» para conservar la nueva orden sin borrar las negaciones o correcciones que contenga. Los dos literales pendientes ya están sellados con cuatro variantes y tres límites. No se ejecutaron: la cobertura sigue en64/742. Las ejecuciones reales de encuesta están autorizadas; las suites y el Full se omiten por decisión del dueño.

Cuatro fallos de apps compartían una pregunta redundante sobre si abrirlas. Ahora, cuando lo que falta es resolver una identidad única, se usa la pregunta de argumentos faltantes que ya tenía BAXY. Esto conserva la ejecución detenida y evita afirmar que la app no existe. Sólo se revisó el código. Se descartó una tanda que habría medido esa aclaración sin acreditar aperturas: esos cuatro requisitos siguen abiertos.

Reanudación autorizada: el dueño aceptó omitir suites automáticas, Fast y Full y mantener los paneles reales de encuesta. La duda de alcance queda resuelta. Próximo paso869/881 sobre candidato actual; se prepara885 para877 en paralelo. RAM libre observada2855MiB frente a4000MiB de arranque: se solicitó liberar aplicaciones, sin cerrar ninguna del dueño. Cobertura64/742,678abiertos,0NA;0/35categorías; último cómputo24h36altas confirmadas a15:42UTC. Ninguna suite omitida se declara aprobada.



881: ocho casos ejecutados, seis respuestas válidas y dos variantes fallidas; los dos literales útiles siguen abiertos por falta de generalización. Cobertura64/742,678abiertos,0NA;0/35categorías;36altas confirmadas24h al último recuento. VRAM3497,56MiB y RAM2429,65MiB frente a4096MiB;41,875s. No suites/Fast/Full.885 no admitió casos por una ruta de perfil incorrecta del runner; se corrigió sólo esa ruta y su continuación está en marcha. Causas escritas por case_id; no se repite881 completa.


885 continuación terminó9/9 en66,922s:1pass8fail,0créditos; VRAM3497,56MiB/RAM2398,76MiB, sin violaciones. H0165/H0183 causas escritas49dc01, registro84c452c4391988bc504a11fa9dd8af029554752433b2c44bda9f8a2eda3a166f. H0183 app.open3cb73ca5-77ab-4802-8f56-8fe73b526ba8 con efecto incierto: no reintentar. Paint de la variante fue abierto/verificado, pero composición falló; cierre normal autorizado solicitado por raíz aed8fa, PID33076/HWND4983644/creation2026-09-11T16:22:45.8377761Z. No repetir885entero.888+889 integrados con revisión manual, sin suites, para consulta de presencia y premisa explícita ficticia; panel890 dirigido en preparación.64/742,678abiertos,0NA;36altas confirmadas24h,0/35categorías;matriz3/11.887Google sóloPLAN: confirmación segura pendiente, alcance3, ninguna infraestructura nueva ni sello ejecutable.
