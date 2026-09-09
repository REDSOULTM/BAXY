# C03 — tramo63: búsqueda de nombres y rutas absolutas

Hipótesis: el proveedor compara una ruta absoluta completa contra cada basename.
Devuelve éxito vacío aunque ese tipo de consulta no esté soportado. La misión
pierde la causa y acaba como step_data_missing. No se amplía el alcance de lectura.

Herencia: Carter_v5/skills/filesystem-workflow/SKILL.md:39–45 exige conservar el
error y no deducir inexistencia de cero resultados. Gemma4
codigo-docs/prompts/tool_rules/filesystem.lean.md:6 usaba rutas absolutas en otra
API; no prueba compatibilidad con el catálogo actual por nombres e IDs opacos.
Ambos fragmentos se leyeron desde biblioteca. Se conserva la frontera actual.

Contraste actual y medición: PRUEBAS_ARCHIVOS56_62.md y TRAMO58_62_PINS.json.
59 scope no mejora;60/61 causa de búsqueda vacía mejora parcialmente;62 cambia
hipótesis y explica búsqueda absoluta no soportada en los dos controles.62 es
contrafactual HTTP, no prueba del proveedor. Se usa Path.IsPathFullyQualified de
.NET10, sin parser propio ni confundir rooted con absoluta.

Cambio mínimo: validación en LocalFilesystemProvider.Search tras normalizar
consulta. Error tipado absolute_path_search_unsupported por el transporte ya
existente. No se sustituye la ruta por basename ni se cambia el catálogo.
Prueba roja del proveedor:1 fail/0 pass/0 skips/66ms,25397exit1; cinco rutas
(exterior existente, separadores alternos, interior absoluta, ausente, UNC)
antes se aceptaban como éxito vacío. Tras cambio:8 pass/0 skips/119ms.
Se conserva búsqueda de nombre sin distinción de mayúsculas, lectura real por ID,
búsqueda vacía válida y contenido exterior intacto. Integración:152 pass/0 skips/8s,
64922exit0, familias MvpLocalStatefulHandlerMatrixTests, PlannerAppBoundaryTests y
C03FactPreservationTests. Incluye causa exacta sin éxito y búsqueda por nombre
posterior verificada en el mismo handler. Producto pendiente.

Producto previsto: mismos cinco turnos técnicos53–58, candidato files63-absolute,
Core NativeAOT recompilado antes de ejecutar y hashes en PREREG. No reserva humana,
UI, voz ni cierre de C03. Runtime registrado sin modificación.

Producto63 terminado43558exit0:72,11s,GPU3497,56MiB,RAM5228,26MiB,
registro intacto. **2/5 útiles**, t1 causa absoluta correcta y t5 hora. T2/t3
se niegan pese a lectura disponible; t4 sólo devuelve fuera de catálogo.
No avisos. No adoptar63 como reparación completa ni presentar5 finales como5passes.
paired.json conserva los literales. Primera transformación errónea t2/t3:
selector nativo propone filesystem.search para leer; domain_grounding rechaza
la operación insuficiente. T4 selector propone conversación. No atribuir todavía
causalidad al historial: capturar HTTP con hook47 en files64-wire, misma fuente.
No se cambiará el selector antes de comparar los payloads reales.

scratchpad/c03-progress-inference64.py quedó preparado, NO ejecutado: comprobaría
otra hipótesis sobre progreso55. Se prioriza recuperación después del error63.
