# Frontera Codex ↔ Fable V2: mente, planner y tools

## Contrato

1. La mente selecciona una operación canónica y entrega argumentos JSON tipados. No ejecuta efectos.
2. El planner actual concatena hasta 16 primitivas usando resultados estructurados (`applicationId`, `windowId`, `processId`, `fileId`, `resourceUri`, `sessionId`, `deviceId`, `jobId`). Propone estructura y argumentos; no obtiene autoridad.
3. Ninguna tool interpreta la frase original, decide el siguiente paso ni llama subtools ocultamente para completar una misión.
4. El core valida schema cerrado, identidad, precondiciones, riesgo y confirmación en cada paso antes de autorizar al provider.
5. El provider queda confinado a una operación; el verifier observa el estado por una vía separada.
6. Cada paso conserva timeout/cancelación, journal sanitizado, replay e idempotencia proporcional.
7. Un handler puede informar que emitió un efecto, pero solo hay éxito si el verifier aporta evidencia positiva. Estado desconocido, dependencia ausente o verificación inconclusa nunca se proyectan como éxito.
8. Un resultado de un paso puede alimentar argumentos de otro únicamente por campos estructurados y sujetos al schema siguiente. Los handles de autoridad son opacos, acotados y revalidados.
9. Propuesta y revisión deben coincidir en las operaciones. Un string literal o enum aportado por el modelo requiere evidencia en el objetivo confiable o en una observación verificada.
10. Si el planner disponible falla, la misión se detiene: no se ejecuta una versión parcial mediante el router de una sola operación.
11. El plan se persiste cifrado antes de cada posible efecto y sólo se replantea cuando el core prueba que el efecto no pudo ocurrir.

## Aplicación al corte de ventanas

`window.resolve` transforma un selector determinista de proceso en uno o más `windowId`. Cada ID liga HWND, PID, tiempo de creación y nombre de proceso dentro del provider, expira y se consume una sola vez. Las cuatro mutaciones aceptan solo ese ID, revalidan la identidad antes del efecto, verifican foco/estado después y devuelven un ID renovado. No reciben lenguaje natural, no seleccionan entre candidatos y no planifican.

## Aplicación al planner

El sidecar recupera una shortlist por cláusulas con el mismo e5-small del router,
propone un DAG cerrado y lo audita en una segunda pasada. .NET vuelve a validar
catálogo, IDs, dependencias y schemas. Cada paso se prepara y ejecuta por el
mismo `MissionEngine` que una operación individual. Los checkpoints cifrados
permiten continuar tras reinicio sin inventar otra identidad de invocación.

## Exclusiones

`memory.*` sigue en el parser y envelope privado y jamás se muestra al planner
general. No se añadió shell, código arbitrario, loop autónomo abierto,
paralelismo, compensación general ni autoridad desde OCR/web/documentos. Los
workflows históricos se conservan como oráculos y evidencia arquitectónica, no
como un segundo runtime de ejecución.
