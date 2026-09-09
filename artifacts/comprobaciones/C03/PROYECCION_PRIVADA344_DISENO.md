# 344 — contrato de hechos privados que llega al compositor

Primera pérdida demostrada en342:

- Confirmación: PrivateOperationNarration sólo entrega cause memory_enable y
  choices. Python recibe el mismo hecho insuficiente; native pregunta confirmar
  sin nombrar qué se autoriza. Falta pendingAction ya soportado por el compositor.
- Enable/save: MemoryOperationResponseProjection emite prosa española fija. El
  compositor interpreta situation como no estructurada y su payload es vacío.
  Publica Confirmado/Guardé en lugar de informar el resultado concreto.
- Recall: C# valida/redacta y entrega records[{label:name,value:emmanuel}],shown1,
  total1. _compose_situation_payload descarta esas tres propiedades. El modelo
  dice no saber el nombre porque ya no recibe el valor que devolvió el provider.

Siguiente reparación de ownership: preservar hechos seguros en un contrato
estructurado. No meter el nombre en otro prompt ni añadir detector de la frase
final. Usar el mecanismo observed/seen existente para los resultados privados;
conservar validación exacta de schema/cuentas/timestamps/redacción/export-replay
de MemoryOperationResponseProjection. Retirar la prosa fija que se sustituya,
actualizando tests para comprobar hechos en vez de las frases antiguas.

Piezas exactas:
src/Baxy.App/MemoryOperationResponseProjection.cs:106–218 configuración/mutación/
borrado/status;244enadelante export;444–482 registros ya seguros y truncados.
src/Baxy.App/PrivateOperationNarration.cs:27–60 confirmación sinpendingAction.
src/baxy_mind/llm.py:_compose_situation_payload ya transmite observed como seen;
no debe descartar registros que la proyección privada ha autorizado a mostrar.
tests/Baxy.Integration.Tests/MemoryAppFlowTests.cs comprueba schemas, redacción,
persistencia y todavía literales de la presentación antigua.

El test StrictProjectionAcceptsOnlyKnownCompletedShapes:21–89 exige explícitamente
Does.Not.StartWith("{") y acepta esa prosa como respuesta final. Esa expectativa
antigua contradice el contrato C03 de hechos para composición: sustituirla por
hechos tipados correctos y rechazo de JSON como respuesta visible. Conservar las
aserciones de ausencia de IDs/selectores privados y los rechazos de schema.
RecordsPayload/Record:1042–1087 ya generan fixtures válidas con procedencia/redacción.

Comparación prevista:340+343 como base; misma conversación342 con confirmación
sintética declarada, comprobar journal y cada mensaje intermedio/final. Además
variantes de recuerdo con valores nuevos y controles de secretos/inyección.
Las pruebas no deben llamar cumplido a un dict que el modelo no recibe.

Implementado en344, con PREREG y baseline9fail antes de editar la fuente.
Focal9pass/0skip122ms, dueñas .NET1913pass/0skip5m19s y compositor Python85pass/
0skip0,65s. La ruta Python observed→seen ya funciona: no se añadió otra capa.
Fast verde, build18,77s sin advertencias/errores. Nativo345:3/7 completos/0silencios;
confirmación explica la acción y registros llegan al modelo, que aún invierte el
sujeto y añade afirmaciones en enable/save. Las representaciones346/347 no reparan
la atribución y no se promueven. Ver sus REVIEW.md; no declarar memoria integrada.
Identidad contextual105/107 y el comportamiento ante preguntas mientras hay una
confirmación pendiente siguen pendientes independientes, no resueltos por recordar.
