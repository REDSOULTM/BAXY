# Mapa de la App antes del arnés nuevo (2026-10-15, subagente Explore del PC)

Rutas bajo `src/Baxy.App/` salvo otro proyecto.

## Lo que se conserva
- **Core:** `CoreProcessClient` (`StartAsync`, `SendOperationAsync(prepared, timeout, ct, confirmationToken)`),
  `LocalJsonlSidecarProcess`; recuperación en `MainWindowViewModel` ~3192-3263.
- **Operaciones:** `PreparedOperation` (refusa `memory.*`), `RetryableOperationRegistry` (outbox durable,
  `DurableRetryStore`; depende de `MemoryOperationProtector` y de `RoutedOperation`, declarado en
  `NaturalNoteRequestParser.cs:7`). `OperationResponse` en `Baxy.Contracts/ProtocolContracts.cs`.
- **Confirmación:** el kernel (`InMemoryConfirmationAuthority`) responde `Status=pending`,
  `ErrorCode=confirmation_required`, `Result={version, token, expiresAtUtc, reconciliationRequired}`;
  `ConfirmationChallengeParser` lo valida (token base64url de 43, ≤ 300 s). Se responde reenviando **la misma**
  `PreparedOperation` con `confirmationToken`. Envoltorios: `PendingOperationConfirmation`
  (`PlannerExecutionSupport.cs` 93-146), `PendingMemoryConfirmation`.
- **Journal:** lo escribe **Core** (`Baxy.Core/Program.cs` 186-229 → `FileInvocationJournal` del Kernel). La App sólo
  escribe `ConversationLog`, `ShellTrace`, el outbox y `DurablePlanStore` (legado).
- **Enmascarado:** Kernel `OperationVisibleFacts.Sanitize`, `ProtectedPrivateResult`; App `MemoryOperationProtector`
  (DPAPI) y, sobre el texto del usuario, `NaturalMemoryRequestParser.ContainsSensitiveMaterial` (extraer antes de
  borrar el parser, con `JudgeValueToKeep`, `MemoryRoutedOperation`, `ResolveDataRoot`).
- **UI:** `Messages` + `MessageAdded` vía `AddMessageCore` (también ConversationLog y `VoiceSpeakAsync`);
  `FieldProductChannel` manda `{"type":"activity","entry":{id,src,msg,ts,route?,source?}}`. No hay botones Sí/No: la
  confirmación hoy es texto; las entradas ya llevan `route:"confirmation"`.
- **Voz:** `MindSidecarClient` 1886-1910 (`voice.transcript` → `TranscriptReceived`), `DispatchTranscriptAsync`.
- **Conductor:** `ProductConductorHost` crea `MainWindowViewModel` y usa su ciclo de vida, estado del turno,
  `MessageAdded`, `SubmitAsync(MissionInput)` y capturas de confirmación; un turno termina cuando no está ocupado, no
  hay redacción pendiente y apareció una entrada nueva de BAXY.
- **Bandeja y arranque:** `App.xaml.cs`, `MainWindow.xaml.cs`, `Presence*`, `WindowsAutostartRegistration`,
  `ShellStartupSequence`, `FieldUiBridge`, `MindRuntimeDiscovery`.

## Lo que el bucle nativo reemplaza
`UserMessagePolicy` (4787, salvo los tipos de 8-92), `UserMessagePhrases`, `ModelMessageComposer` +
`PendingModelMessageQueue` (segunda llamada que reescribe cada línea no escrita por el modelo), `OperationFloor`
(frases fijas), `ObservedResponseLiterals`, `TurnVisibleFacts`, `MissionNarration`, `PrivateOperationNarration`,
`MindPlanSession`, `PlannerExecutionSupport` (salvo `PendingOperationConfirmation`), `DurablePlanStore`,
`AttemptedArguments`, `OpenWindowOperations`, ComputerUse* (13 311 líneas en 30 ficheros), `NaturalMemoryRequestParser`
(regex sobre cada entrada), parsers de nota/audio/app/estado, `NoteDisambiguation`, flujos pendientes de audio,
`MemoryTurnSession` (salvo su ruta de envío), `VoiceListenCommand`, `TurnBudget`, `MindArgumentNormalization`.

## Texto fijo, listas y vetos entre el modelo y la persona (a retirar)
`ConfirmationReplyParser` (lista `assent_words.v1.json`), «continuar/continue» literales en `MindPlanSession`,
arrays de elección en `TurnVisibleFacts`, líneas fijas en `MainWindowViewModel` (máscara, elección de nota, fallo de
arranque, `⚠ (...)` + OperationFloor), `MissionInput` 61-63, `ForbiddenTerms`/`IsSafeConversationReply` de
`UserMessagePolicy`, `ShouldComposeAsConversationNotError`, `FirstSignal.FormulateProgress` del Kernel.

## Resultado que vuelve al modelo hoy
`OperationResponseProjection.Create`: `HonestyCorrection` o `response.Message` (hechos del kernel
`OperationVisibleFacts`: kind, operation, polarity, verified, succeeded, error, cause, pending, effectUncertain,
observed) u `OperationVisibleFacts.FromStatus`. Cada paso costaba dos llamadas (decidir y luego `arguments`).

## Pruebas
Sólo `tests/Baxy.Integration.Tests` referencia la App: 131 de 203 ficheros usan tipos del legado; ~39 sólo tipos que
se quedan; ~33 ninguno.
