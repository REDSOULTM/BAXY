# 418 — precedencia privada corregida; owners y Fast verdes

La solicitud privada de memoria ya reconocida por el parser sustituye la
aclaración pública pendiente. Se reutiliza la ruta/contrato privado existente;
NoRoute y AskToSave conservan el flujo mental. Sin nueva operación, persistencia
implícita, capa, frase fija ni cambio de modelo. Diagnóstico y herencia en
DIAGNOSTICO.md. Se preserva el resto del WIP en MainWindowViewModel y tests.

`dotnet test tests/Baxy.Integration.Tests -c Release --nologo -v:minimal
--filter 'FullyQualifiedName~ExplicitPrivateMemoryRequestSupersedesMindClarification|FullyQualifiedName~PrivateMissingValueReplacesPublicClarificationWithoutInventingIt'`
→ 6 pass / 0 skips, 26 s.

`dotnet test tests/Baxy.Integration.Tests -c Release --nologo -v:minimal
--filter 'FullyQualifiedName~MindShellEndToEndTests|FullyQualifiedName~MemoryAppFlowTests|FullyQualifiedName~MemoryTurnSessionTests|FullyQualifiedName~NaturalMemoryRequestParserTests|FullyQualifiedName~PlannerAppBoundaryTests'`
→ 2007 pass / 0 skips reportados, 6 min 51 s. La salida señala además la prueba
explícita OptInRealRuntimeTraversesShellMindAndCoreUsingReadOnlyOperations como
omitida; no cuenta como pass ni acredita runtime real, UI o voz física. Su
compuerta separada sigue pendiente para el candidato final. Las indicaciones
de latencia de esta suite excluyen composición LLM: no son latencia del producto.

`.\scripts\test_source_quality.ps1` → Fast verde completo, build 18,01 s,
0 warnings/errors. No Full durante reparación. Servidores de build inactivos
cerrados mediante build-server shutdown en ambos SDK, sin producto/modelo
activo ni cambio de aplicaciones del usuario. La encuesta permanece abierta.

Producto419 preparado: ocho sintéticos, misma secuencia404b con una petición
de aplicación sin nombre antes de cada lectura privada. Capturará hechos y
finales, comprobará que realmente quedó una aclaración y medirá el árbol del
diagnóstico. Corte conservador VRAM 3800 MiB/RAM disponible 768 MiB, sólo ese
árbol; no certifica el conjunto físico de voz. Falta ejecutarlo y adjudicarlo.
