# C03 — contexto personal sin escritura implícita

Estado EN_CURSO. Fuente299 continúa la petición completa por la política semántica
cuando el parser identifica contexto personal sin consentimiento para persistir.
Antes, MainWindowViewModel terminaba el turno con context_not_saved aunque la
persona hubiera pedido un saludo. Ahora desaparece esa terminación prematura;
se reutiliza el recorrido existente de conversación, acción o plan.

No se cambian el parser, los argumentos privados, el consentimiento explícito,
las confirmaciones sensibles ni la persistencia. AskToSave conserva MustNotPersist.
La operación de memoria sólo se ejecuta por la ruta explícita anterior del parser.
TryExecuteMindOperationAsync rechaza memory.* propuesto por la mente; el kernel
rechaza memory.* dentro de planes. Estas son las barreras pertinentes: la protección
criptográfica por sí sola no demuestra consentimiento.

La prueba del shell utiliza el proceso real de mente con un oráculo determinista
de contrato, no el modelo local. Tres entradas de desarrollo pasan completas a
turn.decide y publican la respuesta inyectada. Una propuesta adversarial memory.save
se rechaza con memory_needs_explicit_request. En los cuatro casos no crece el
journal append-only del Core y no se crea la cola de operaciones. Ninguna afirmación
de calidad generativa se deduce de estos tests.

Baseline corregido:4 fail,0 pass,0 skips,18s, con fuente previa; tres finales de
clarificación en vez de la conversación y ninguna llamada a turn.decide.
Se preservan dos errores de construcción de los tests: lectura del journal
exclusivo y espera de un outbox que sólo se crea al ejecutar una operación.
Se corrigieron las comprobaciones a metadatos de longitud y ausencia del outbox,
sin modificar las garantías del producto. owners.log registra1845pass4fallos
del segundo error, antes de la corrección de esos tests.

Comando final:

```powershell
dotnet test tests/Baxy.Integration.Tests -c Release --nologo -v:minimal --filter 'FullyQualifiedName~MindShellEndToEndTests|FullyQualifiedName~NaturalMemoryRequestParserTests|FullyQualifiedName~PlannerAppBoundaryTests'
```

1879 pass,0 skips,0 fallos,2m25s. owners-corrected.log conserva salida exacta.
Fast299 integrado VERDE: todas las fases estáticas y build Release,0 advertencias,
0 errores,build19,33s. No Full durante reparación. Incluye fuente298 del filtro
de preguntas; sus tres suites Python habían dado1022pass0skip5,65s.

Falta contrastar el recorrido compartido con inferencia nativa300 y adjudicar cada
final. La UI293 fue preservada y detenida para compilar; se debe reabrir BAXY para
el dueño. No aceptación de UI/audio físico ni promoción de modelo en estos tests.
Los defectos de atribución de identidad y París observados293 siguen pendientes.
