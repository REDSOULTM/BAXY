# Revisión de flujo y límites de la propuesta

## Entrada, catálogo y argumentos

El helper nuevo devuelve únicamente un nombre cuyo key coincide con el target que ya autenticó CLOSE1056; reutiliza su gramática y sus barreras de negación, cita, diferimiento y otro dispositivo. Si la equivalencia del catálogo produce más de un nombre, se abstiene. No hay nombres/IDs de encuesta, traducción de variantes ni una respuesta visible fija.

El plan continúa expandiendo app.close→window.resolve→app.close con after_dependencies. El ciclo plan de __main__ (expected_operations, _ground_explicit_arguments) pasa application_names al extractor por propósito conservado. La lectura directa de argumentos también usa ese extractor. El nombre canónico valida con el esquema publicado; no se exige que sus mayúsculas/acento sean bytes del literal, porque la autoridad es el catálogo autenticado. El guard de esquemas anteriores rechaza applicationName si no existe allí.

El esquema de OperationArgumentsSchema es plano: no soporta alternativas/XOR. Para evitar ampliar ese motor compartido, ambos selectores están tipados como opcionales y la exclusión se impone en WindowResolveHandler antes de cualquier lectura OS. Se rechazan cero selectores, ambos selectores, byTitle (incluso false) u offset (incluso 0) acompañando applicationName. La descripción del catálogo declara exactamente esa semántica y el contrato cambia a window.resolve.identity.inventory.v3. La forma process previa conserva su comportamiento, incluyendo byTitle y paginación. Un {} que antes fallaba validación de campos ahora falla en el handler como invalid_selector; no obtiene identidad ni efecto. Ésta es una diferencia deliberada y acotada del esquema plano, visible a revisión.

## Asociación fuerte y sus límites

El mismo provider instalado que produce el hello de Core se inyecta en el provider de ventanas, conservando su caché de catálogo existente. ResolveWindowIdentitiesAsync reutiliza el resolver pero exige igualdad normalizada completa entre solicitud y entrada: ningún resultado de ranking aproximado se acepta. Ambigüedad/no instalado fallan antes de inventariar.

Paquetes: AUMID observado coincide exactamente con AppUserModelId y se vuelve a leer después de enumerar. No se usa nombre de proceso ni título. Win32: sólo TargetPath o AppUserModelId que sean rutas absolutas .exe suministradas por Shell; se compara MainModule.FileName normalizado contra esa ruta. No se interpretan accesos directos, comandos, prefijos ni rutas inferidas del display name. Si no existe ruta fuerte, application_window_identity_unavailable. El catálogo actual suele obtener TargetPath sólo para nombres duplicados: por tanto este parche puede abstenerse en muchas apps Win32. No se expande la consulta Shell para ocultar ese límite.

La rama fuerte usa el enumerador existente de ventanas de nivel superior por PID y no depende de MainWindowHandle para descubrir ventanas secundarias. Falla si no puede obtener geometría de una ventana visible del proceso; errores de observación no se convierten en un subconjunto exitoso. Conserva el criterio existente de ventanas visibles con área positiva, no procesos sin ventanas ni superficies ocultas. El inventario no es una instantánea atómica entre procesos: la reobservación del token protege la instancia seleccionada, sin afirmar que el escritorio queda congelado. Cada proceso y HWND puede desaparecer durante la lectura; eso causa abstención.

El inventario fuerte es una vía dentro del provider/plataforma ya existentes. El lector legacy de apertura/status continúa llamando Inventory sin modo fuerte y mantiene el fallback histórico; no se usa ese resultado legacy para cerrar. Se conserva también su semántica de errores y el valor por defecto de ProcessName en sus observaciones. Implementaciones que no ofrecen la nueva lectura fuerte fallan mediante la implementación predeterminada del contrato, sin degradarse al lector débil.

## Token, completitud y cancelación

window.resolve/applicationName exige 1–50 de límite y publica todos sus candidatos observados o falla antes de emitir ninguno si exceden el límite; no acepta páginas/offset. Cero candidatos termina window_not_found. No se publica una primera página que parezca la única ventana. El resultado usa el WindowInventoryPage existente con offset0, observedCount igual a candidatos, complete=true dentro del alcance descrito y nextOffset nulo.

Cada observación incluye HWND, PID, inicio de proceso, nombre real del proceso y ruta ejecutable observada. WindowsWindowControlProvider construye WindowIdentity y llama Observe antes de Issue, después verifica de nuevo. Para tokens de esta vía, Observe compara además la ruta ejecutable; los tokens antiguos tienen ese campo null y conservan su semántica previa. Issue, caducidad, consumo, confirmación de app.close y verificación de ausencia posterior no cambian. Si falla un candidato posterior o se cancela, finally revoca todos los tokens emitidos de esta selección; sólo se conservan tras publicar el conjunto exitoso.

## Binder y revisión humana

El productor sigue siendo window.resolve: no hay cambios en prerequisites Python/kernel, PlanObservationProjector ni el binder. windows y windowId ya están proyectados. Sólo un valor único permite el binding determinista; más de uno mantiene la selección pendiente. No se inserta un HWND, PID, target fixture ni appName directamente en app.close. La aprobación manual conserva la invocación y argumentos exactos del windowId propuesto. ProductConductorHost conserva su windowObservations del productor sin exigir process en los argumentos.

## Revisión realizada y pendiente

Se revisaron las ocho unidades, sus firmas y consumidores, los valores opcionales que preservan constructores previos, la ordenación del esquema, la ruta de materialización por propósito, los dos caminos de inventario, cancelación/revocación y observación pre/post del token. Todas las fuentes base siguen byte a byte iguales a los archivos canónicos al preparar IDENTITY.json; el DIFF corresponde únicamente a las copias proposed. No se importó, compiló ni ejecutó código y esto no es un resultado de pruebas.

Pendiente para raíz tras su revisión: integración del conjunto completo y evidencia real del subset existente con ventanas propias vacías. Son relevantes el navegador titulado Paint, app sin identidad fuerte, ausencia, varias ventanas, límite insuficiente e identidad expirada/cambiada; no se ejecutó ni preparó un panel nuevo para ellos aquí. No se promete que la ruta Win32 sea elegible cuando Shell no aporte el ejecutable. Ninguna reparación/coverage se acredita con esta revisión estática.
