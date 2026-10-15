# Código C# muerto en `src/Baxy.App` (análisis para el arnés nuevo, 2026-10-15)

Análisis de solo lectura del notebook. La App es del líder: aquí no se borró nada.

**Método.** Alcance con Roslyn desde `App.Main`, contando el código que genera XAML y los overrides, sin las
pruebas. Para el código inalcanzable (c) se repitió quitando las ramas que nunca se toman. XAML no tiene
`{Binding}`, no hay objetos COM hospedados y la serialización usa contextos generados, así que nada de eso mantiene
vivo código.

## Totales

| | Líneas |
|---|---|
| Nunca referenciado, (a) tipos y (b) miembros | 1083 (918 fuera de los ficheros del líder) |
| Inalcanzable con la mente de hoy (c) | ~16 100 |
| Total | ~17 200 de 51 149 (~16 500 fuera de `MainWindowViewModel` y `MindSidecarClient`) |

## Por qué (c) es inalcanzable, y no sólo «sin soporte»

- **`plan`.** `TryExecuteMindOperationAsync` (cerca de la línea 2853) crea siempre una ejecución de un paso.
  `MayReplan` (`PlannerExecutionSupport.cs:580`) exige más de uno, y los planes restaurados de disco se descartan
  sin correr (`TryRestore`). Por eso `TryReplanAsync` → `PlanAsync` nunca se alcanza. `IsPlannerAvailable` no se lee.
- **`turn.result` de tipo `plan`.** La mente sólo devuelve `action`, `clarify` o `conversation`.
- **`computer.use.step`.** Sólo se alcanza con la operación `mission.computer.use`, que `mind.py:143` quita del
  catálogo que ve el modelo. Todo el motor queda inalcanzable, igual que lo que cuelga de él: la rama de misión de
  `HandlePendingAsync`, `OperationFloor.ComputerUse` y `ComputerUseMission.WarmAsync`.
- **`after_dependencies`** sólo vale para pasos de un plan; los pasos nuevos son siempre `literal`.
- **`plan.ground`.** `GroundPlanStepAsync` no tiene quien la llame.
- **`narrate` y `message.send`.** La App no los envía.

## Ficheros que se pueden borrar

| Ruta | Líneas | Por qué | Confianza |
|---|---|---|---|
| `AgentFieldGraph.cs` | 192 | nadie lo referencia | alta |
| `ComputerUseMission*.cs` (13) | ~6580 | (c); antes, mover 3 miembros (ver abajo) | alta |
| `ComputerUseSuccessCheck*.cs` (11) | ~5110 | (c) | alta |
| `ComputerUseMissionWindow.cs`, `ComputerUseDestination.cs`, `ComputerUseLabelTranslations.cs`, `ComputerUseTypedLedger.cs` | 1589 | (c) | alta |
| `OpenWindowOperations.cs` | 74 | (c), sólo sirve a planes de varios pasos | alta |

## Miembros que se pueden borrar en ficheros vivos

**Vivos sólo por las ramas muertas (c):**

- `OperationFloor.cs` 326–1899: la redacción de computer use, unas 1480 líneas, mezcladas con código vivo
  (confianza media).
- `PlannerExecutionSupport.cs`: 48–53, 148–233, 572–783, 807–872, 954–978 y 1104–1619 (877 líneas).
- `MindPlanSession.cs`, unas 255 líneas:
  - ramas 151–155, 157–173, 182–214, 237–249, 252–289, 384–464, 473–479, 489–491, 542–545, 555–558 y 562–577;
  - miembros 37–38 y 749–779.
- `MissionNarration.cs`: 13–47 y 209–263.

**Nunca llamados:**

- `PresenceIdleSampler.cs` 11–13, 34–40, 95–205
- `UserMessagePolicy.cs` 94–130, 167, 198, 251–254, 1056–1070, 2739–2790
- `ShellTrace.cs` 42, 45–46, 74, 93–134, 142, 429–454
- `MemoryPanel.cs` 134–199
- `ProductConductor.cs` 64, 68, 465–507
- `OperationFloor.cs` 210–228, 1815–1828
- `FieldBridgeContract.cs` 40–55, 129–139, 285–301, 335–373 (confianza media)
- `PreparedOperation.cs` 198–210
- `NaturalApplicationRequestParser.cs` 49–63
- `NaturalMemoryRequestParser.cs` 257–264, 504–515
- `PrivateOperationNarration.cs` 12–25
- `MissionNarration.cs` 84–102
- `AppSurfaceNavigator.cs` 27, 69–82
- `MindRuntimeDiscovery.cs` 88–92
- `CoreProcessClient.cs` 50–55
- `MainWindow.xaml.cs` 27–30
- `MindPlanSession.cs` 51–54
- `PresenceTrayIcon.cs` 54–60, 117–118, 365–366, 392–393
- Restos pequeños:
  - `FieldUiBridge.cs` 82, 256–262
  - `FieldProductChannel.cs` 65, 87–90, 177–183
  - `ConversationMessage.cs` 13, 15
  - `ConversationLog.cs` 42, 44
  - `PresenceHost.cs` 57, 59
  - `PresenceStatusStore.cs` 35–39
  - `MemoryTurnSession.cs` 73–78

## En los dos ficheros que reescribe el líder

- **`MainWindowViewModel.cs`:**
  - nunca llamados: 339–340, 424–436, 687–706 (el `SubmitAsync` público), 1672–1701, 2761–2771, 2865–2874 y
    2895–2900;
  - (c): la línea 1999 (`WarmAsync`) y `"plan"` en `SanitizedTurnKind`;
  - sólo para pruebas, porque `_testTurnResolver` es siempre nulo fuera de ellas: 577 y 1178–1199.
- **`MindSidecarClient.cs`:**
  - nunca llamados: 319, 321, 486–525, 1352–1380 y 1607–1610;
  - (c), unas 490 líneas: 130–137, 151–202, 1081–1350 (`PlanAsync` y sus ayudantes), 1382–1471, 1525–1605 y el
    indicador `_plannerAvailable`.

## Parece muerto, pero se queda

- **Campos de estructuras P/Invoke** (`LocalJsonlSidecarProcess.cs` 450–480, `OwnedProcessReader.cs` 356–365,
  `PresenceTrayIcon.cs` 325–351): definen la memoria nativa.
- **`ComputerUseMission.OperationName`, `Primitives` y `Prepares`** (`ComputerUseMission.cs` 28, 86–105): los usa
  `MainWindowViewModel.cs:574` para limpiar misiones viejas de la cola de reintentos. Hay que moverlos antes de
  borrar el resto.
- **Restaurar planes:** `DurablePlanStore` con `ValidateAndConvert`, `PendingMindPlanExecution.ComputerUse` y
  `MindPlanResult` leen planes guardados por versiones anteriores.
- **`FieldUiProbe` y `ProductConductorHost`:** son entradas reales, por `--ui-probe` y `--conductor`.
- **`VoiceSpeakAsync` y `VoiceCancelAsync`:** vivos otra vez, porque la mente atiende `voice.speak`.

## JSON de `src/baxy_mind/data` que lee la App

Todos van incrustados por el csproj; la mente ya no lee ninguno.

| Fichero | Lo lee | ¿Vivo? |
|---|---|---|
| `operation_floor.v1.json` | `OperationFloor` | sí; su sección `computerUse` sólo la usa (c) |
| `assent_words.v1.json` | `ConfirmationReplyParser` (`MemoryOperationProtection.cs:578`) | sí, y es la lista de palabras que el dueño mandó quitar |
| `memory_subjects.v1.json` | `MemoryPanel.Subjects` | sí |
| `open_window_operations.v1.json` | `OpenWindowOperations` | inalcanzable (c) |
| `answer_evidence_words.v1.json` | `ComputerUseMission.Question.cs:140` | inalcanzable (c) |

Las entradas `EmbeddedResource` del csproj no tienen condición, así que se borran en el mismo cambio que su código.
