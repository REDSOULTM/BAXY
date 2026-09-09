# Cancelación379 — fuente validada

PrivateOperationNarration comparte MemoryAction seguro (operation/target) entre confirmación y cancelación. MemoryTurnSession usa esa proyección sólo después de retirar la invocación; conserva ramas que no pueden cancelar por incertidumbre o fallo. Python amplía la representación de remaining_steps_cancelled a memory_cancelled, conservando el outcome cancelado y la acción. No se añade prosa fija, argumentos privados, tokens o permisos.

- BaselinePython:4fail1pass96deselected0,56s por outcome completed y falta de acción.
- Baseline.NET:2fail0pass0skip25s por falta de cancelledAction.
- Python:1335pass0skip6,02s (compose/request_reading/turn_policy/transport/price_v8).
- .NET:1977pass0skip2m18s (MemoryAppFlow,MemoryTurnSession,MemoryOperationProtection,NaturalMemoryRequestParser,NaturalSystemStatusRequestParser,RequestReadingConformance).
- Fast:verde entero, build17,86s0warnings/0errors. Handle13506 recogido exit0.

V8 sólo vuelve a sellar llm.py actual, con comentario; aritmética/veredicto y seis artefactos históricos intactos. Producto380 iniciado después de verde, mismos diez casos370. No Full ni aceptación C03 por estas suites.
