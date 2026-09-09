# Tramo108 — proyección del fallo de composición — 2026-09-07

Bloqueo demostrado en [UI107](PRUEBAS_UI107.md): fallo real de servidor,
agotamiento de composición, código interno en actividad y grafo Idle. La
recuperación sin reinicio ya funciona; no se cambia modelo, muestreo o prompts.

## Herencia y decisión

Se heredan la cola, HasCompositionError y el evento tipado composition_failed
de la App, medidos en [106](PRUEBAS_RECUPERACION106.md), y el lector state
existente de la GUI histórica (ADR-0008). Consulta de inventario de biblioteca
por recuperación/interfaz/estado: sin mecanismo más específico que sustituya
la frontera ya localizada. UI107 es evidencia física de la primera pérdida:
CurrentConversationState sólo considera voz/escucha/IsBusy; HasCompositionError
era una propiedad sin notificación y la cola no participaba de esa proyección.

Alternativa descartada: introducir una respuesta fija o volver a componer durante
un fallo total; incumple el invariante o depende del recurso averiado. Tampoco
se añade un segundo lector en el bridge. Se extiende el estado existente a
error; la propiedad del view model notifica su cambio y la cola pendiente se
proyecta como thinking, conservando la admisión de entrada que ya existía.

Contraste primario consultado2026-09-07: [W3C ARIA19](https://www.w3.org/WAI/WCAG21/Techniques/aria/ARIA19)
describe una región de error presente antes de actualizar su contenido y su
anuncio sin trasladar el foco. Se adopta role=alert persistente para la etiqueta
de estado Response error; el grafo muestra Error con nombre accesible del estado.
Estas son etiquetas de interfaz, no prosa de BAXY ni una explicación de causa.
La causa/ruta permanecen en el evento diagnóstico y deja de duplicarse el código
interno como actividad de conversación. No se añade reejecución automática.
La eficacia física con lector de pantalla no se presume a partir del atributo.

## Fuente y comprobación

MainWindowViewModel notifica HasCompositionError y cambios de cola;
FieldProductChannel los proyecta por state y por bootstrap, con error prioritario.
Nuevo turno o publicación recuperada retiran el error mediante el estado del
dueño. React usa el mismo reducer de state, añade las tablas visuales del estado
error y una región alert sin cambiar la lógica de entrada ni las dependencias.

Dos casos de prueba en FieldProductHonestTerminalTests ejercen callbacks reales
de agotamiento/publicación del view model: evento diagnosticable, error visible
por state y bootstrap, entrada habilitada, ninguna actividad fija inventada y
retirada del error por un nuevo turno o una publicación recuperada. Son pruebas
de frontera con datos técnicos, no inferencia real ni aceptación de prosa.

`pnpm build` exit0: TypeScript/Vite8.0.12,37módulos,275ms de Vite.
Source/dist regenerados deliberadamente; ADR-0008 y ORIGIN actualizados.
Sello38archivos `99FF9838C07CE32F25F329AACF830F62D8DD70C5931E26C2EC483B710B2CA657`.
Bundles index-Dh8gdcnz.js e index-B7EBy9jN.css.

Validación .NET94729 exit0:169pass/0skips,6s. Comando:
`dotnet test tests/Baxy.Integration.Tests -c Release --nologo -v:minimal --filter 'FullyQualifiedName~FieldProductHonestTerminalTests|FullyQualifiedName~FieldProductChannelParityTests|FullyQualifiedName~FieldProgressContractTests|FullyQualifiedName~MainWindowShellContractTests|FullyQualifiedName~PlannerAppBoundaryTests'`.
Salida TEMP/c03-ui108-dotnet.log.
`.\scripts\test_source_quality.ps1`77667 exit0, Fast verde, Release19,29s,
0advertencias/errores; TEMP/c03-ui108-fast.log.
UI109 completada con los tres primeros relojes de UI107: Error/Response error
visible, entrada utilizable, posterior reloj útil y error retirado con el mismo
App/servidor. Capturas, recursos y límites en PRUEBAS_UI109.md.
No Full durante reparación, promoción, reserva100 ni cierre de C03.
