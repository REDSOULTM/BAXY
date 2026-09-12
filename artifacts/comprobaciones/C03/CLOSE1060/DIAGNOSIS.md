# CLOSE1060 — resolución de cierre por nombre instalado

Base de fuente: cd1b08ab8c1be8d40c80498b02a5e7aabf9f6990. Se heredan el diagnóstico CLOSE1059 y la reparación de intención CLOSE1056. H0095 (run-00) y close1052-dev-01 Paint (run-04) ya conservan app.close hasta action_grounding; ambos terminan preguntando un nombre de proceso, sin propuestas, aprobaciones ni efectos de cierre. Las trazas exactas y sus SHA están en IDENTITY.json. No se atribuyen resultados a los once casos sin ejecutar.

La transición action→plan en action_grounding es deliberada y correcta: un cierre requiere identidad observada. El defecto posterior es que window.resolve no tenía selector de nombre instalado y su extractor sólo podía aportar proceso/título. No se repara desactivando el plan ni el grounding. window.application.status no emite tokens y permanece como lectura de presencia.

Esta propuesta añade applicationName a window.resolve y lo rellena con el nombre exacto del catálogo autenticado cuando el reconocedor de cierre existente resuelve un único destino. La operación continúa devolviendo sus mismos windows/windowId. La identidad procede del inventario OS existente, restringido para este uso a AUMID exacto o ejecutable absoluto del catálogo; nunca usa el fallback por título o prefijo de proceso del lector histórico.

Ocho owners propuestos: effect_intent.py conserva el nombre; __main__.py materializa el argumento; ProductCatalog.cs declara selector y contrato v3; WindowControlHandlers.cs valida exclusión y despacha; Program.cs comparte el provider instalado ya construido; WindowControlContracts.cs expone la lectura en el provider existente; WindowsInstalledApplicationOpenProvider.cs resuelve catálogo e inventario fuerte; WindowsWindowControlProvider.cs reobserva y emite sus tokens habituales. No se añade operación, provider, catálogo de apps ni herramienta externa.

Masa pendiente demostrada: H0095/H0186/H0228/H0346 y sus cuatro variantes intactas del subset. Sólo los dos primeros fallos observados descritos arriba fundamentan este diagnóstico; el parche no constituye evidencia de reparación ni crédito.

No se ejecutaron producto, imports, Core, GPU, pruebas ni build. Sólo se prepararon archivos externos y se revisó texto/flujo/identidades. No se editó fuente canónica ni registro. La raíz debe revisar la totalidad antes de adoptar y medir el subset dirigido.
