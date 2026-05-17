# Fase 3 — UML de clases por subsistema

> Un documento por subsistema (no por archivo). 10 archivos UML siguiendo
> la taxonomía de Fase 2.

## Convenciones de los diagramas

- **Mermaid `classDiagram`** como formato primario.
- Atributos privados con `_` (sin marca `-` que Mermaid no soporta bien).
- Métodos públicos primero, métodos privados después.
- **Marcas explícitas:**
  - `(N L)` después del nombre: LOC de la clase.
  - `(M)` después del nombre del método: LOC del método si >50.
  - `[GOD]`: clase >300 LOC o >15 métodos públicos.
  - `[1-USER]`: clase usada en un solo lugar (candidata a colapsar a función).
  - `[DUP]`: clase/método con duplicado en otro lugar.
- Notas (`note for X`) marcan hallazgos.

## Índice

| # | Doc | Container | Clases cubiertas |
|--:|---|---|---|
| 1 | [observability.md](observability.md) | Observability | `EventBus`, `LogRecorder`, `TraceLogger`, `TelemetryStore` |
| 2 | [voice_loop.md](voice_loop.md) | Voice Loop | `AudioCapture`, `WakeDetector`, `StreamingSTT`, `_SileroVAD`, `StreamingTTS`, `VoiceController`, `VoiceRunner` |
| 3 | [llm_lifecycle.md](llm_lifecycle.md) | LLM Lifecycle | `LlamaServerManager`, `LLMClient`, `LlamaLogTail`, `ModelInfo` (TypedDict) |
| 4 | [mission_verification.md](mission_verification.md) | Mission + Verification | `MissionGoal`, `ExpectedOutcome`, `MissionOutcome`, `OutcomeStatus` enum, `VerifierOutcome`, `_ToolCallRecord` |
| 5 | [routing.md](routing.md) | Routing + Validation | `MissionPlan`, `MissionStep`, `CapabilityVerdict`, `_NLIService`, `_State` (router), `IntentTag`, `ValidationResult`, `GroundingVerdict` |
| 6 | [memory.md](memory.md) | Memory | `MemoryStore`, `ExperienceMemory`, `KnowledgeStore`, `SkillMeta`, `Microagent`, `Persona` |
| 7 | [tools.md](tools.md) | Tools | `ToolRegistry` (god), `AppResolver` (god), `AppCandidate`, `_SSRFGuardRedirectHandler` |
| 8 | [agent_core.md](agent_core.md) | Agent Core | `Gemma4Agent` (god), `ToolEvent`, `AgentReply` |
| 9 | [surfaces.md](surfaces.md) | Surfaces | `AgentWorker` (PyQt), `AgentRunner` (FastAPI), `EventBusBridge`, `VoiceBridge`, `ServerBootWorker`, `MainWindow`, `SettingsDialog`, `ProgressDisplay` (chat.py) |
| 10 | [state_config.md](state_config.md) | State + Config | `AgentState`, `Session`, `SessionTurn`, `SessionStore`, `AgentConfig`, `Profile`, `ProfileWatcher`, `WatcherConfig`, `_Sample` |

## Cómo cosechar hallazgos de estos diagramas

Al final de cada doc hay una tabla con las clases marcadas por:
- LOC, # métodos, # atributos
- `[GOD]` / `[1-USER]` / `[DUP]` flags
- Veredicto de Fase 3 (mantener / split / colapsar a función / unificar con otra)

Los veredictos van a `_findings_seed.md` con su severidad para ser cosechados
en Fase 8.
