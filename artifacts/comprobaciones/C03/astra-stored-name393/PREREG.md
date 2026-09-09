# 393 — lectura explícita del nombre persistido

Hipótesis: `What name have you saved in private memory?` falla antes de la
inferencia útil porque el parser privado no reconoce la lectura del nombre
guardado. El catálogo público excluye memory.* deliberadamente y no debe abrirse
para compensar esta omisión. 376 ya rechazó esa apertura; 392 muestra que inferir
persistencia de un nombre conversacional inventa un guardado.

Reutilizar `NaturalMemoryRequestParser.NameRecallPattern` y la ruta sellada
`memory.recall`, scope exact, selector name. Añadir las construcciones de lectura
explícita en pasado/estado guardado en español e inglés, con límites de cláusula.
No cambia las consultas genéricas, la prosa, el catálogo, el modelo ni la autoridad.
No es todavía la reparación del recuerdo conversacional o de quién soy.

Herencia: parser actual, `ViewModelBindsRequestedNameAndRecallsItAfterANewSession`
y la separación de procedencia descrita en biblioteca/gemma4-agent/documentacion/
08_memoria_jarvis/research/2_memoria.md:1–75. La recomendación de tres capas de ese
documento no se adopta: esta lectura ya tiene un almacén y una ruta tipada.
La investigación vigente de herramientas/modelo de C03 se reutiliza; no hay nueva
configuración de inferencia ni dependencia que requiera otra comparación de modelos.

Antes de cambiar fuente: pruebas de lectura ES/EN y controles de negación,
traducción, terceros, futuro, otra ubicación y acciones compuestas. Ampliar el
flujo real existente que guarda un valor aleatorio y lo consulta en otra sesión:
las nuevas preguntas deben devolver lo leído del almacén, no un nombre del prompt.
Pruebas dueñas y Fast tras fuente. Producto con modelo después, sin Full durante
reparación. No presentar tests de transporte como voz/UI ni aceptación fresca.
