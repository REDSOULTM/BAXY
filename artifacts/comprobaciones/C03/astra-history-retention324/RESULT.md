# 324 — historial conservado; validación de contrato

El primer conjunto terminó con 155 pass, 1 fail, 0 skips (2 m 36 s).
La nueva aserción de historia pasó, pero la simulación de mente omitía
`preserveObjective:false` para la pregunta independiente de recuerdo. La App
interpretaba el valor por defecto como continuación de «Haz eso». El sidecar real
ya emite false para conocimiento independiente e identidad (__main__.py:6527).
Se corrigió sólo esa respuesta de la fixture; no se cambió el contrato productivo.

El siguiente conjunto focal terminó con 3 pass, 1 fail, 0 skips (22 s). Ya pasó
la respuesta con el nonce. Falló porque AssertOutboxEmpty exige que exista un
archivo: una conversación sin operaciones nunca lo crea. La nueva prueba exige
ahora ausencia del archivo y ausencia de llamadas arguments/plan. No se retira
ninguna aserción de utilidad, historial ni ausencia de efectos.

Validación final:
`dotnet test tests/Baxy.Integration.Tests -c Release --nologo -v:minimal --filter 'FullyQualifiedName~MindShellEndToEndTests|FullyQualifiedName~PlannerAppBoundaryTests|FullyQualifiedName~Goal06VisibleVoiceTests'`
→ **156 pass, 0 fail, 0 skips, 2 m 33 s**, owners-final.log.
Incluye recuerdo tras aclaración, pregunta independiente y fragmento que retoma
el objetivo exacto. Los dos resultados rojos se conservan, no son pases.

Fast324 verde: `.\scripts\test_source_quality.ps1 -Mode Fast`, build Release
20,76 s, 0 advertencias y 0 errores; fast324.log. Producto325 en curso.
Esto acredita la frontera y el
contrato, no la calidad del modelo en los seis turnos humanos.
