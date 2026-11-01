# Código C# muerto en `src/Baxy.App` (2026-10-15)

Análisis de solo lectura del notebook sobre la App reescrita por el líder (rama `renew-nb`, commit `18e8546a1`).
Aquí no se borró nada.

**Build.** `dotnet build src/Baxy.App -c Release` compila sin advertencias ni errores.

**Método.** Se calculó el alcance con Roslyn desde `App.Main`. Cuentan como raíces el código que genera XAML
(`IComponentConnector.Connect`, que cablea `Loaded` y `Closing`), los overrides, las implementaciones de interfaz
y los campos de las estructuras P/Invoke. Los generadores de System.Text.Json y Regex se ejecutaron dentro de la
herramienta, así que `DurableRetryJsonContext` compila sin errores. Las pruebas no cuentan, y ningún proyecto de
pruebas referencia `Baxy.App`. Ningún XAML usa `{Binding}` ni objetos COM hospedados.

Hubo una segunda pasada para lo **inerte**: código alcanzable que nunca tiene efecto. Busca campos y propiedades que
sólo escribe código muerto y parámetros opcionales que nadie pasa. La herramienta está en
`%LOCALAPPDATA%\Temp\claude\nb\deadtool2` y tiene los modos `report`, `inert`, `why` y `live`.

## Totales

| Categoría | Líneas |
|---|---|
| Ficheros enteros | 261 (2 ficheros) |
| Miembros nunca alcanzados, en ficheros vivos | 645 |
| Inerte: alcanzable pero sin efecto | ~171 |
| **Total** | **~1077 de 16 598 líneas `.cs` (52 ficheros), ~6,5 %** |

## Lo que pide la App y lo que atiende la mente hoy

`src/baxy_mind/__main__.py` anuncia y atiende 13 peticiones: `catalog.configure`, `turn.decide`, `turn.continue`,
`turn.confirm`, `turn.beat`, `turn.beat.end`, `session.new`, `voice.start`, `voice.stop`, `voice.status`,
`voice.speak`, `voice.cancel` y `shutdown`. `MindSidecarClient` envía exactamente esas, ni una más.

- La mente devuelve cuatro tipos de `turn.result` (`action`, `clarify`, `conversation` y `silence`). Son los cuatro
  que trata `MindSidecarClient.ParseStep`.
- La mente también emite `voice.transcript`, `voice.event` y `startup`, y la App los lee.

Así que **ninguna parte de la App queda inalcanzable por el protocolo de la mente**. Las 34 rutas HTTP de
`FieldProductChannel` también las llama `Baxy.FieldUi/src`.

Lo que no cuadra son las variables de entorno y un dato que nunca llega:

| Qué | Dónde | Efecto | Tipo |
|---|---|---|---|
| La App publica `BAXY_MIND_STT_DIR`, `BAXY_MIND_CPU_PROSE_ADAPTER`, `BAXY_MIND_DECIDER_ADAPTER`, `BAXY_VOICE_WAKE_MANIFEST`, `BAXY_VOICE_WAKE_CASCADE_MANIFEST` y `BAXY_VOICE_WAKE_ALLOW_UNCALIBRATED` | `MindRuntimeDiscovery.cs` 186–201, 205–208, 210–229 | La mente sólo lee `BAXY_RENEW_STT_DIR`, `_WAKE_DIR`, `_TTS_MODEL`, `_PIPER_DIR` y `_MIC`. La voz depende de que el lanzador (`scripts/run_renew.cmd`) las ponga. | inerte |
| `ContextSize()` lee `BAXY_MIND_CTX` y por defecto vale 12288 | `FieldProductChannel.cs` 1099–1107 | `/model` y `/settings` informan un contexto falso: la mente usa `BAXY_RENEW_CTX`, por defecto 49152. | alcanzable pero incorrecto; corregir, no borrar |
| `ConversationMessage.SourceUrl` no se rellena nunca (el único `new` está en `MainWindowViewModel.cs:1012`, sin ese argumento) | `FieldProductChannel.cs` 605–614 y 321–331 | `/source/open` responde siempre 404 `source_not_published`, y el enlace «fuente» nunca aparece. | alcanzable pero siempre falla |
| `BAXY_COMPOSITION_INJECTION` | `FieldProductChannel.cs` 68–107 | La clase que lo lee está muerta, así que la variable no hace nada. | inalcanzable |

## Ficheros que se pueden borrar

| Ruta | Líneas | Por qué | Confianza |
|---|---|---|---|
| `src/Baxy.App/AgentFieldGraph.cs` | 192 | Nadie lo referencia: ni el código ni el XAML, que no usa `clr-namespace:Baxy.App`. | alta |
| `src/Baxy.App/ConsultedSource.cs` | 69 | `From` y `Parse` nunca se llaman. `IsWikimediaPage` sólo se evalúa sobre `SourceUrl`, que siempre es nulo. Se borra junto con la cadena «fuente» descrita abajo. | media-alta (hay que decidir si vuelve el enlace «fuente») |

## Miembros que se pueden borrar en ficheros vivos

Rangos `fichero:líneas` dentro de `src/Baxy.App/`, con los comentarios de documentación incluidos.

**Nunca alcanzados (645 líneas).**

| Fichero | Rangos | Líneas | Qué es | Confianza |
|---|---|---|---|---|
| `PreparedOperation.cs` | 76–96, 114–127, 201–213, 245–257, 299–354, 393–411 | 132 | `CreateFollowUp`, `Matches`, dos constructores de `RetryableOperationRegistry`, `GetOrAdd`, `Replace` ×3, `SnapshotPendingOperations` y `RestorePlanOperation` (restos del planificador) | alta |
| `PresenceIdleSampler.cs` | 11–13, 34–40, 95–205 | 116 | constantes y la sobrecarga de `Capture`; las comprobaciones de VRAM, de procesos sin atribuir, de crecimiento del working set y de handles y de giro de CPU; `WorkingSetByProcess` | alta |
| `ShellTrace.cs` | 41–42, 44–46, 52–58, 74, 93–134, 142, 429–454 | 80 | etapas sin uso, `ShellTraceStages.All`, `ShellTraceScopes.Recovery` y `ShellTraceSink.Use` con `OverrideScope` | alta |
| `FieldBridgeContract.cs` | 40–46, 51, 53–55, 75–78, 129–139, 285–301, 335–373 | 77 | constantes de revisión y lector, `MilestoneDue`, `ProgressStages`, `FirstHitoDueAt`, `FirstPulseAfterSilenceBudget`, `StampEnvelope`, `CanDeliver` y `ReadReaderRevision` | media (documentan el contrato del puente JS) |
| `FieldProductChannel.cs` | 22–45, 65, 68–107, 170–176 | 68 | `CollectingFieldEventSink`, `FieldPublicationInjection.Reset`, `FieldCompositionInjection` y su enum; las propiedades `ViewModel`, `SessionId`, `SessionLabel` y `AdmissionCount` | alta |
| `MemoryPanel.cs` | 134–199 | 62 | `KeysAsync`, `Candidates`, `Names`, `Words` y `Fold` | alta |
| `MainWindowViewModel.cs` | 322–340, 833–835 | 22 | el `SubmitAsync(CancellationToken)` público, que envía el borrador, y `MindUnavailableCause` | alta |
| `MemoryOperationProtection.cs` | 91–101, 200–208, 486–487 | 21 | `AuthenticateForOutbox`, `Authenticates`, `ResolveWireOperationName` y `HasProof` | alta |
| `Presentation/AppSurfaceNavigator.cs` | 27, 69–82 | 15 | `CurrentId` y `ReturnToFieldAsync` | alta |
| `PresenceTrayIcon.cs` | 54–60, 119–120, 383–384, 410–411 | 13 | `TryFind`, `Post` y los P/Invoke `FindWindow` y `PostMessage`, que no se usan | alta |
| `CoreProcessClient.cs` | 50–55 | 6 | el constructor con ruta (sin él, `_executableOverride` y `_argumentsOverride` quedan nulos; ver «inerte») | alta |
| `FieldUiBridge.cs` | 82, 256–262 | 6 | `ProductChannel`, `CurrentProgress`, `NormalizeActivitySource` y `ResolveModelIdentity` (envoltorios) | alta |
| `MindSidecarClient.cs` | 124, 436–439 | 5 | `GpuLayersEnvironmentVariable` y la sobrecarga de `VoiceStartAsync` sin modo | alta |
| `MainWindow.xaml.cs` | 27–30 | 4 | el constructor sin parámetros (`App` usa `new MainWindow(_presence)` y no hay `StartupUri`) | media (sólo lo usaría el diseñador de XAML) |
| `MindRuntimeDiscovery.cs` | 88–92 | 4 | las dos sobrecargas de `TryConfigureCurrentProcess` | alta |
| `LocalJsonlSidecarProcess.cs` | 88–91 | 3 | `StandardErrorBytesObserved` e `IsStandardErrorPumpCompleted` | alta |
| `PresenceStatusStore.cs` | 35–39 | 3 | las propiedades `StatusPath`, `SamplesPath` y `SamplesArchivePath` | alta |
| `ConversationLog.cs` | 42, 44 | 2 | `FilePath` y `ArchivePath` | alta |
| `ConversationMessage.cs` | 13, 15 | 2 | `TimeLabel` y `AccessibleText` (no hay bindings, la interfaz es WebView2) | alta |
| `PresenceHost.cs` | 58, 60 | 2 | `StatusPath` e `IdleSamples` | alta |
| `PresenceContracts.cs` | 9 | 1 | `PresenceLimits.VramCeilingBytes` (sólo lo usaba el muestreador muerto) | alta |
| `Presentation/AppSurfaceCatalog.cs` | 80 | 1 | `Ids` | alta |

**Inerte: alcanzable pero nunca tiene efecto (~171 líneas).**

| Fichero | Rangos | Líneas | Por qué | Confianza |
|---|---|---|---|---|
| `FieldProductChannel.cs` | 47–66 (sin la 65), 738–753, 778–782, 785–803, 876–880 | ~64 | `FieldPublicationInjection.Mode` sólo lo escribe `Reset`, que está muerto, así que siempre vale `None` y nunca se entra en las ramas Silence, Filter y SuppressFinal | alta |
| `FieldProductChannel.cs` + `ConversationMessage.cs` | FPC 133–134, 143, 321–332, 605–615, 1141–1155; CM 3–4, 11 | ~44 | la cadena «fuente»: `SourceUrl` siempre es nulo, `_publishedSources` siempre está vacío y `SourceOpener`/`OpenInDefaultBrowser` nunca se ejecutan | media-alta |
| `MindRuntimeDiscovery.cs` | 186–201, 205–208, 210–229 | ~40 | publica variables que la mente renew no lee (ver la tabla de arriba); sus campos en `MindRuntimeConfiguration` y en la huella del entorno (664–674, 690–730) caen con ellas | media (falta decidir si se renombran a `BAXY_RENEW_*`) |
| `MainWindowViewModel.cs` | 52, 129–139, 161, 174, 187 | 15 | `Draft`/`_draft` sólo los escribe el `SubmitAsync` muerto; `CanSend` siempre es falso y no lo lee nadie vivo | alta |
| `ShellTrace.cs` | 378, 398–402 | 6 | `_override` sólo lo escribe `Use`, que está muerto | alta |
| `CoreProcessClient.cs` | 43–44 (y los `??` de 80 y 85) | 2 | los overrides sólo los escribe el constructor muerto | alta |

## Parece muerto, pero se queda

| Qué | Dónde | Por qué |
|---|---|---|
| Campos de estructuras P/Invoke (55 líneas) | `HeartbeatMoment.cs` 312–345, `LocalJsonlSidecarProcess.cs` 450–480, `OwnedProcessReader.cs` 356–365, `PresenceTrayIcon.cs` 343–369 | Definen la memoria nativa, aunque C# no los lea. |
| `DurableRetryJsonContext` y las propiedades de `DurableRetryDocument` | `DurableRetryStore.cs` 581–582 | Los usa el código que genera System.Text.Json. |
| Tipos que se serializan por reflexión | `PresenceStatusDocument`, `StoreDocument` (`RuntimeFileHashCache`), el objeto anónimo de `MindRuntimeDiscovery.cs:465` | `JsonSerializer` lee sus propiedades. |
| `FieldUiProbe` (1094 líneas) y `ProductConductorHost` | — | Son entradas reales, por `--ui-probe` (`scripts/run_baxy.ps1`) y `--conductor` (`scripts/run_baxy_conductor.ps1`, `scripts/renew/bench_e2e.py`). |
| Todo el cliente de la mente, voz incluida (`VoiceSpeakAsync`, `VoiceCancelAsync`, `voice.transcript`, `voice.event`) | `MindSidecarClient.cs` | La mente atiende las 13 peticiones. |
| `BAXY_VOICE_WAKE_ON_START` | `MindRuntimeDiscovery.cs:233` | Lo lee la propia App (`MainWindowViewModel.cs:726`). |
| Costuras de prueba: parámetros opcionales que nadie pasa y setters sin uso | constructores de `PresenceHost`, `PresenceIdleSampler`, `WindowsAutostartRegistration`, `OwnedProcessReader`, `RuntimeFileHashCache`, `PresenceStatusStore` y `ConversationLog`; `FieldProductChannel.SourceOpener { set; }` | Se pueden simplificar, pero no son código muerto: cuestan cero líneas y dejan inyectar dependencias. No se cuentan. |

## JSON de `src/baxy_mind/data`

La App sólo incrusta uno (`Baxy.App.csproj`, `EmbeddedResource`).

| Fichero | ¿Lo incrusta la App? | Lector | ¿Vivo? |
|---|---|---|---|
| `memory_subjects.v1.json` (27 líneas) | sí, como `Baxy.App.MemorySubjects.json` | `MemoryPanel.Subjects` (`MemoryPanel.cs:262`), por `Label` ← `ListAsync` ← la ruta `/memory` | sí |
| `decider_catalog.es.v1.json`, `tool_descriptions.en.v1.json` | no | `baxy_mind/mind.py` | sí (la mente) |
| `app_places`, `world_acts` | no | Kernel | sí |
| `client_cold_start`, `documentless_applications`, `keypad_keys`, `query_function_words`, `render_surface_classes`, `screen_state_lines`, `search_addresses` | no | Providers.Windows (y `documentless` también Core) | sí |
| `operation_floor.v1.json` (741), `assent_words.v1.json` (15), `open_window_operations.v1.json` (17), `answer_evidence_words.v1.json` (81) | no | **ninguno** (eran de la App vieja) | **huérfanos**: 854 líneas que se pueden borrar |
