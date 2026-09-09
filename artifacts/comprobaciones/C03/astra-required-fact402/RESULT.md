#402 — dato leído conservado en composición y aceptación

UserMessagePolicy.CollectStructuredLiterals incluye el único valor corto (≤256
caracteres), no redactado, de una lectura memory.recall/list verificada y exitosa.
Reusa RequiredLiteralFacts y ModelMessageComposer.requiredFacts; no cambia prompt,
modelo, formato de la memoria, autorización ni parser. Los datos largos, múltiples,
vacíos o redactados siguen como observaciones, sin contrato de copiar todos.

401 midió3/8→5/8 útiles sin nuevas pérdidas; sujetoES/redacción siguen abiertos.
Las nuevas pruebas pasan por la proyección privada, transporte al compositor y
aceptación de prosa: una respuesta que omite el dato falla. Los secretos no salen.

- Baseline:4fail,5pass,0skip,779ms. Cada fallo incluye tres garantías ausentes;
  además la aserción inicial usaba Is.Empty para un retorno null aceptado. Se
  corrigió esa aserción a Is.Null; no altera las tres ausencias que reproducen el defecto.
- Focal:9pass,0skip,444ms.
- `dotnet test tests/Baxy.Integration.Tests -c Release --nologo -v:minimal
  --filter 'FullyQualifiedName~MemoryAppFlowTests|FullyQualifiedName~MemoryOperationProtectionTests|FullyQualifiedName~PlannerAppBoundaryTests'`:
  186pass,0skip,3m05s.
- `scripts/test_source_quality.ps1 -Mode Fast`: verde entero, build18,15s,
  0 advertencias/errores. No Full durante reparación.

Producto402b separado. No dar por resuelto C03 ni todas las consultas de memoria.
