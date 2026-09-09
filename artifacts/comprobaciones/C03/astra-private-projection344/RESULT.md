# 344 — proyección privada estructurada; producto por comprobar

Se sustituyó la prosa interna fija por hechos observados en
MemoryOperationResponseProjection.cs. Los resultados de configuración, mutación,
borrado, estado y exportación preservan la operación y replay; los registros
recuperados viajan como observed.records, con la redacción y límites originales.
PrivateOperationNarration.cs identifica la operación preparada en pendingAction
para confirmación inicial, reconciliación y recuperación, sin argumentos privados.
Python ya transmite observed como seen: no se modificó su fuente para esta tanda.

Las expectativas antiguas de texto fijo en MemoryAppFlowTests se sustituyeron
por aserciones sobre hechos. Permanecen los controles de esquema exacto, ausencia
de secretos/IDs/rutas/digests, persistencia, cancelación y confirmación ligada a
la invocación. La nueva prueba Python verifica el request realmente enviado al
compositor con dos nombres distintos, además de la respuesta publicada.

## Validación

- Baseline .NET focal: 9 fallos / 0 pass / 0 skips, 153 ms.
- Mismo focal tras editar: 9 pass / 0 fallos / 0 skips, 122 ms.
- `dotnet test tests/Baxy.Integration.Tests -c Release --nologo -v:minimal --filter 'FullyQualifiedName~MemoryAppFlowTests|FullyQualifiedName~MemoryTurnSessionTests|FullyQualifiedName~NaturalMemoryRequestParserTests|FullyQualifiedName~MemoryOperationProtectionTests|FullyQualifiedName~MissionInputPipelineTests|FullyQualifiedName~MindShellEndToEndTests'`: 1913 pass / 0 fallos / 0 skips, 5 m 19 s. Log owners.log.
- Runtime Python registrado, `-m pytest tests/test_compose_contract.py -q`: 85 pass / 0 fallos / 0 skips, 0,65 s. Log python-owners.log.
- `.\scripts\test_source_quality.ps1`: Fast verde; build Release18,77s, 0 advertencias/errores. Log fast.log. No Full durante reparación.

El driver scratchpad/c03-product345.py conserva los siete pedidos de342, incluyendo
los dos controles sintéticos declarados. Modelo y perfil de inferencia sin cambios;
datos en un perfil privado aislado. Resultado345:3/7 turnos completos útiles,
cero silencios. Confirmación ya explica la activación; nombre recuperado llega
al compositor, pero se atribuye al asistente. Enable/save añaden afirmaciones no
observadas. RESULT/PINS del producto conservan todos los mensajes intermedios.
346/347 no reparan la atribución; ninguna de esas variantes se promueve.
No acredita aceptación humana fresca, escritorio gráfico ni voz física.

Pendiente separado: continuidad de identidad105/107 y preguntas durante una
confirmación. El ramo Invalid de MemoryTurnSession todavía omite pendingAction;
no confundir esta mejora de la confirmación inicial con cobertura de ese ramo.
C03 completo sigue EN_CURSO.
