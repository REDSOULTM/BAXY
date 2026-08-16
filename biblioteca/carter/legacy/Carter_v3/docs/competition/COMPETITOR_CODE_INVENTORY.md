# COMPETITOR_CODE_INVENTORY.md
# Inventario de Competidores Locales
# Generado por: Claude Code (claude-sonnet-4-6) — 2026-05-06

---

## Resumen de competidores encontrados localmente

| Competidor | Ruta | Lenguaje | Tamaño aprox | Componentes principales | Tiene voz | Tiene cámara | Tiene GUI | Tiene memoria | Tiene tools | Estado |
|---|---|---|---|---|---|---|---|---|---|---|
| **Mark XXXIX** | `Extras/Mark-XXXIX-main/Mark-XXXIX-main/` | Python | ~20 archivos, UI es 1500 líneas | LLM(Gemini), Planner, Executor, Memory, UI(PyQt6), Actions | SÍ (Gemini Live audio nativo) | SÍ (mss+cv2+Gemini vision) | SÍ (PyQt6 HUD 60fps) | SÍ (JSON long_term) | SÍ (18 tools + agent_task) | Proyecto activo, completo funcional |
| **OpenClaw** | `legacy/Referencia OpenClaw/openclaw-main/` | TypeScript/Node.js | Massive (700+ archivos) | Gateway, Channels(25+), Agents, Memory(vector), Browser(Playwright), Nodes(mobile), Voice, Plugins | SÍ (ElevenLabs/Deepgram/sherpa-onnx) | SÍ (mobile nodes iOS/Android) | SÍ (Canvas web UI) | SÍ (vector embeddings + dreaming) | SÍ (exec, read/write, web, browser, canvas, nodes, cron, image/video/music gen) | Proyecto open-source masivo, producción |

---

## ACTUALIZACIÓN 2026-05-06 — 8 competidores adicionales descargados

El usuario descargó los 8 competidores públicos restantes a `Extras/Competidores/`. Todos auditados ahora con código real (ver `COMPETITOR_LANDSCAPE_AUDIT.md` v2). Resumen:

| Competidor | Ruta | Lenguaje | Loop | Verifier | Policy pre-LLM | Sandbox | Memoria persistente | Local-first |
|---|---|---|---|---|---|---|---|---|
| **Agent-S (S3)** | `Extras/Competidores/Agent-S-main/` | Python 3.10+ | `Worker.generate_next_action()` Think-Act-Observe | **BBON visual** (`BehaviorNarrator`+`ComparativeJudge`) | NO (en system prompt) | NO | NO | Híbrido (LLM cloud) |
| **AutoGPT (classic)** | `Extras/Competidores/AutoGPT-master/classic/` | Python 3.12+ | `propose_action()`→`execute()` (1 step/invoc, **LLM no implementado**) | NO | `CommandPermissionManager` (allow/deny por capas, opt-in) | NO | File storage local | SÍ |
| **AutoGen** | `Extras/Competidores/autogen-main/` | Python 3.10+ | `BaseGroupChat` event loop + `AssistantAgent.on_messages()` | Parcial (ToolMessage en contexto) | NO | Docker opcional | `ListMemory` in-context | SÍ (litellm) |
| **Goose** | `Extras/Competidores/goose-main/` | **Rust** | `Agent::reply()` con `max_turns=1000` enforced | `RepetitionInspector` (no state) | **5 inspectores** (Security, Egress, Adversary LLM, Permission, Repetition) | NO | Extensión `memory` MCP + compaction 0.75 | **SÍ puramente local** |
| **LangGraph** | `Extras/Competidores/langgraph-main/` | Python 3.10+ | Pregel DAG (no imperativo) | Validación tool name | NO built-in | NO | **Store nativo + checkpointer** (SQLite/Postgres, fork/replay) | Cloud-agnostic |
| **Open Interpreter** | `Extras/Competidores/open-interpreter-main/` | Python 3.9+ | `respond()` Think→Code→subprocess | Screenshot opcional (OS mode) | `safe_mode` semgrep (off por defecto) | subprocess (sin Docker) | NO | SÍ (Ollama nativo) |
| **OpenHands** | `Extras/Competidores/OpenHands-main/` | Python 3.12+ | Event-driven, **lógica core en `openhands-agent-server` externo** | NO visible | NO visible | **Docker obligatorio** | DB SQLAlchemy | NO |
| **OS-Copilot (FRIDAY)** | `Extras/Competidores/OS-Copilot-main/` | Python 3.10 | Planner→Executor (generate→exec→judge→repair max=3)→SelfLearner | `judge_tool()` LLM sobre stdout/stderr | NO | NO | **Cursos JSON + Chroma** | NO (embeddings OpenAI) |

### Componentes destacados por competidor (citas reales)

- **Agent-S BBON**: `gui_agents/s3/bbon/behavior_narrator.py:25-75,130-170`, `comparative_judge.py:100-145`. SOTA OSWorld 72.60%.
- **AutoGPT permissions**: `classic/forge/forge/permissions.py:66-72`. Stub LLM en `forge_agent.py:195`.
- **AutoGen termination**: `autogen-agentchat/.../conditions/_terminations.py` (Max/Token/Timeout/Handoff).
- **Goose inspectors**: `crates/goose/src/agents/agent.rs:1454`. Builtin extensions `crates/goose-mcp/src/lib.rs:55`. ActionRequired bidireccional.
- **LangGraph Store + checkpointer**: `libs/checkpoint/langgraph/checkpoint/base/__init__.py:50` (`source` ∈ input/loop/update/**fork**).
- **Open Interpreter safe_mode**: `interpreter/core/utils/scan_code.py:30-39` (semgrep externo).
- **OpenHands DockerSandbox**: `openhands/app_server/sandbox/docker_sandbox_service.py:82`. Skills hardcoded a `CodeActAgent`.
- **OS-Copilot tool generation**: `oscopilot/modules/executor/friday_executor.py:175-240` (`judge_tool` con `Succeed|Amend|Replan`).

---

## Mark XXXIX — Análisis arquitectónico básico

### Entrypoint
`main.py` — clase `JarvisLive`. Loop principal: conexión persistente WebSocket a Gemini Live API (nativa, streaming de audio). Async loop via `asyncio`.

### Cómo llama al modelo
`google-genai` SDK, `client.aio.live.connect()`. Streaming real-time. Audio input y output nativo del modelo. Múltiples modelos Gemini para distintos roles (planificación, ejecución, visión, búsqueda, corrección).

### Cómo ejecuta tools
`if/elif` chain de 18 tools en `_execute_tool()`. Cada tool se ejecuta en thread pool (`run_in_executor`). Resultado devuelto al modelo como tool response en la sesión Live.

### Cómo maneja errores
3 niveles: per-tool exception, LLM-based error analysis (classify error → retry/skip/replan/abort), session reconnect automático (3s backoff).

### Cómo maneja GUI
`actions/computer_control.py` — usa `pyautogui` para mouse/teclado. `actions/desktop.py` — gestión de ventanas. NO usa AttachThreadInput ni accesibilidad UIA para CEF apps (Steam, Discord).

### Cómo maneja memoria
JSON categorizado (`long_term.json`). LLM llama `save_memory` tool. Inyectado como texto al sistema prompt al conectar.

### Cómo maneja seguridad
Ningún sistema de policy pre-LLM. Ningún guard post-reply. 100% dependiente de que Gemini rechace solicitudes peligrosas.

### Cómo maneja voz/cámara
Voz: `sounddevice` → Gemini Live audio nativo. Cámara: `mss`+`cv2` → Gemini vision. Completamente cloud.

### Cómo mide estado/progreso
Estados de UI: LISTENING/THINKING/PROCESSING/SPEAKING/MUTED. UI muestra waveform. Log con typewriter effect.

### Cómo responde al usuario
Audio TTS via Gemini (voz "Charon" hardcoded). También texto en el log de la UI.

### Cómo testea
No hay tests visibles. Sin test suite, sin CI visible.

---

## OpenClaw — Análisis arquitectónico básico

### Entrypoint
`src/entry.ts` → compiled a `openclaw.mjs`. Gateway daemon local que corre en macOS/Linux/Windows.

### Cómo llama al modelo
Via plugin de provider. Default: OpenAI `gpt-5.4`. Soporta 30+ providers incluyendo Ollama (local). Streaming transport. Model fallover automático entre auth profiles.

### Cómo ejecuta tools
Herramientas definidas como TypeBox JSON schemas. LLM retorna JSON tool calls. Gateway ejecuta handler registrado. Loop de tool calls hasta respuesta final de texto. Sandboxed via Docker para sesiones no-main.

### Cómo maneja errores
Context compaction automática si overflow. Tool call errors capturados y devueltos como tool results. Lifecycle hooks pre/post tool call.

### Cómo maneja GUI
Canvas tool (web UI companion, solo macOS). Browser tool (Playwright en Docker). Nodes tool (mobile iOS/Android). NO hay control de apps Windows nativas.

### Cómo maneja memoria
Plugin-based. Vector embeddings locales. "Dreaming" (consolidación background). Memory inyectada como `memory.md` en system prompt.

### Cómo maneja seguridad
Sistema de auditoría completo (`openclaw doctor`). Docker sandbox por sesión. Tool policy pipeline (allowlist/denylist). SSRF protection. Exec approval via iOS push notification. Path policy.

### Cómo maneja voz/cámara
TTS: ElevenLabs (cloud), sherpa-onnx (local). STT: Deepgram (cloud). Wake word en macOS/iOS. Cámara: mobile nodes solamente.

### Cómo mide estado/progreso
update_plan tool que el agente puede llamar para actualizar su plan visible. Sessions con history visible. Status via gateway API.

### Cómo responde al usuario
Multi-channel: WhatsApp, Telegram, Discord, Slack, etc. Responde en el canal donde llegó el mensaje.

### Cómo testea
Test suite con vitest. QA con pytest sobre skills. Docker-based integration tests. E2E tests. Extensive test coverage.

---

## Nota sobre competidores públicos (sin código local)

Sin código abierto disponible:

- Claude Computer Use pattern (Anthropic, API cerrada)
- Windows Copilot patterns (Microsoft, cerrado)

El resto (Open Interpreter, OpenHands, AutoGPT, AutoGen, LangGraph, Goose, OS-Copilot, Agent-S) ya tiene código local en `Extras/Competidores/` y se auditó arriba con citas reales.
