# Bloqueo de inventario de ventanas

BAXY no tiene hoy una vía tipada para listar todas las ventanas visibles sin conocer antes un proceso o título. `window.resolve` exige `process`; `window.active` sólo lee la ventana en primer plano. Un comodín no está definido: el provider busca el nombre literal del proceso. El selector vacío se rechaza.

Esto corrige el diagnóstico de H0023: la propuesta del modelo pertenece al dominio de ventanas, pero **no basta para ejecutar la enumeración total**. El filtro de dominio interviene antes, pero retirarlo o restituir autoridad no crea la capacidad que falta. Tampoco debe forzarse al verificador estricto a aceptar un contrato insuficiente.

La sonda707 mide reconocimiento de dominio con60textos sintéticos; no demuestra que las40peticiones positivas sean compatibles con una única operación actual. Sus15ganancias/1pérdida son cambios del predicado, no éxitos nuevos del producto.

Primero hay que habilitar una lectura real de inventario, conservando descubrimiento, filtros concretos y verificación de identidad. Debe declarar cuándo limita resultados: el tope50 actual no permite afirmar que se mostraron todas si hay más. Después se mide el modelo y la integración con nombres, estados, cantidades, orden, referencias e idiomas. La fuente705 permanece congelada hasta que Full4 termine; no se ha añadido una operación ni modificado código productivo en este diagnóstico.

Evidencia: ProductCatalog.cs1601–1612; WindowControlHandlers.cs8–39; WindowsWindowControlProvider.cs71–123,462–477,616–650; WindowsWindowControlProviderTests.cs187–198. Rutas completas y hashes en RESULT.json. No inferencia ni cobertura nueva.

La herencia sí incluía `window.list` para ventanas OS y `desktop_layout.list_windows` para snapshots con EnumWindows. Los documentos de reglas de ambas herramientas no especifican paginación, límite ni truncamiento. Son precedentes de la capacidad, no un contrato completo para copiar. Véanse las dos rutas de biblioteca en RESULT.json.

## Precisión necesaria para la implementación

El esquema actual sólo admite propiedades planas y requisitos globales (`ProductOperationSchema.cs:204–328`, `OperationArgumentValidator:495–597`, `ContractValidator.cs:421–476`). No expresa `process XOR all`: hacer opcional `process` y añadir `all` no basta para validar las combinaciones. La forma final del contrato no está decidida ni implementada.

La documentación de Microsoft confirma que `EnumWindows` recorre ventanas de nivel superior y se detiene cuando el callback devuelve false; el retorno cero también puede indicar un fallo de la API. El provider actual ignora ese retorno (`WindowsWindowControlProvider.cs:648`). El inventario debe distinguir fin normal, límite alcanzado y error antes de declarar que está completo. [EnumWindows](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-enumwindows).

`IsWindowVisible` comprueba el estilo de visibilidad, no que una ventana esté descubierta en pantalla. El alcance de la lectura debe conservar esta distinción y no inventar que todo lo enumerado se ve sin obstáculos. No se han añadido filtros de Alt-Tab ni cambios al provider. [IsWindowVisible](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-iswindowvisible).
