# COMPETITOR_LANDSCAPE_AUDIT.md
# Auditoría de Competidores — VERSIÓN 2 (con código real local)
# Generado por: GitHub Copilot (Claude) — 2026-05-06
#
# CAMBIO MAYOR vs v1: Todos los análisis de Open Interpreter, OpenHands, AutoGPT,
# AutoGen, LangGraph, Goose, OS-Copilot y Agent-S ahora se basan en LECTURA DIRECTA
# del código fuente disponible en `Extras/Competidores/`. Las marcas [inferencia]
# fueron eliminadas en favor de citas `archivo:línea`.
# Claude Computer Use y Windows Copilot siguen siendo análisis de conocimiento
# público (no hay código abierto disponible para estos dos).
# La versión anterior se conserva como `COMPETITOR_LANDSCAPE_AUDIT.v1_inferencia.md`.

---

## Tabla resumen (verificada contra código real)

| Competidor | Lenguaje | Loop principal | Verifier post-acción | Policy pre-LLM | Step budget | Sandbox | Memoria persistente | Tests | Local-first | Hardcodes |
|---|---|---|---|---|---|---|---|---|---|---|
| **Open Interpreter** | Python 3.9+ | `respond()` Think→Code→Exec | Débil (screenshot opcional, sin verify de estado real) | `safe_mode` con semgrep (off por defecto) | NO (loop_breakers por strings) | subprocess en host (sin Docker) | NO (solo `messages` lista) | 4 archivos | SÍ (Ollama nativo) | Mínimos (computer API dinámica) |
| **OpenHands** | Python 3.12+ | Event-driven, lógica core en `openhands-agent-server` (paquete externo, no auditable) | NO visible en app_server | NO visible | NO visible | **Docker obligatorio** (DockerSandboxService) | DB SQLAlchemy | 97 archivos (alto) | NO (Docker + agent-server requeridos) | Skills hardcoded a `CodeActAgent` |
| **AutoGPT (classic)** | Python 3.12+ | `propose_action()` → `execute()` por step (UN step por invocación) | NO existe | `CommandPermissionManager` (allow/deny lists, granular pero opt-in) | `cycle_budget` (cuenta pero no bloquea) | NO | File storage + ChromaDB declarado pero no usado | Smoke tests (débiles) | SÍ (file storage local) | Defaults a GPT-3.5/GPT-4; **`propose_action()` retorna stub `"I cannot solve the task!"` — LLM call NO IMPLEMENTADO en Forge** |
| **AutoGen (Microsoft)** | Python 3.10+ | `BaseGroupChat` + `GroupChatManager` event loop, `AssistantAgent.on_messages()` | Parcial (ToolMessage añadido a contexto, sin verify de estado real) | NO existe (warning textual sobre LocalCommandLineCodeExecutor) | `MaxMessageTermination`, `TokenLimitTermination`, `TimeoutTermination` (per-team-run) | Docker opcional (`DockerCommandLineCodeExecutor`) | `ListMemory` (in-context, no vector) | Cobertura buena | SÍ (litellm) | Defaults de provider, function name = `func.__name__` |
| **LangGraph** | Python 3.10+ | Pregel (DAG distribuido), no loop imperativo | Validación de tool name (`INVALID_TOOL_NAME_ERROR_TEMPLATE`), sin verify de estado | NO built-in (DIY: añadir nodo "permission_checker") | Recursion limit + `interrupt_before/after` | NO (depende del tool) | **Store nativo** (key-value persistente, scoped por namespace) + checkpointer SQLite/Postgres | Bueno (unit + integration) | Sí, cloud-agnostic (LangGraph Server opcional) | Mínimos |
| **Goose (Block)** | **Rust** | `Agent::reply()` con loop imperativo, `max_turns=1000` | NO state verifier; usa `RepetitionInspector` para detectar bucles | **Pipeline multi-inspector pre-ejecución**: Security, Egress, Adversary (LLM), Permission, Repetition | `max_turns=1000` real | NO (subprocess + extensiones MCP) | Extensión `memory` (MCP builtin) + compaction automática | Suite buena (tokio tests) | **SÍ puramente local** (Electron + goosed local) | Builtin extensions enumeradas en HashMap |
| **OS-Copilot (FRIDAY)** | Python 3.10 | `FridayAgent.run()`: Planner → Executor (generate_tool→execute→judge→repair) → SelfLearner | `judge_tool()` LLM-based sobre stdout/stderr (sin verify visual) | NO existe | `max_repair_iterations=3` (muy restrictivo) | NO | Cursos JSON persistentes + ChromaDB para tool retrieval | 5 archivos | NO (embeddings OpenAI obligatorios) | Paths a `tool_repository/`, `courses/` |
| **Agent-S (S3)** | Python 3.10+ | `AgentS3.predict()` → `Worker.generate_next_action()` (Think-Act-Observe sin planner explícito) | **`BehaviorNarrator.judge()` + `ComparativeJudge` (BBON)**: marca screenshots before/after, LLM compara visualmente | NO engine; restricciones en system prompt (`PROCEDURAL_MEMORY`) | `max_steps=15`, `max_trajectory_length=8`, code agent budget=20 | NO | NO entre sesiones (solo `worker_history` in-session) | NO (eval por OSWorld benchmark, 72.60% SOTA) | NO (LLM cloud requerido; vLLM teórico) | Mínimos (fuzzy match sobre window titles reales) |
| **Mark XXXIX** | Python | Loop Gemini Live | Limitado | Limitado | n/a | NO | NO | Limitado | NO (Gemini cloud) | Alto (ver `COMPETITOR_MARK_DEEP_AUDIT.md`) |
| **OpenClaw** | TypeScript/Node | Multi-channel | NO | NO | NO | NO | Limitado | Limitado | n/a | Alto (ver `COMPETITOR_OPENCLAW_DEEP_AUDIT.md`) |
| **Claude Computer Use** | API Anthropic (cerrada) | Screenshot→Action loop | Verbalización del modelo | Moderado | API-side | n/a | NO | n/a | NO (cloud) | n/a |
| **Windows Copilot** | Cerrado (Microsoft) | n/a | n/a | Corporativo | n/a | n/a | MSA | n/a | NO (cloud) | n/a |

> **Carta de cobertura del código:** Los 8 primeros tienen evidencia `archivo:línea` directa abajo. Mark y OpenClaw tienen documentos dedicados (`COMPETITOR_MARK_DEEP_AUDIT.md`, `COMPETITOR_OPENCLAW_DEEP_AUDIT.md`). Los 2 últimos siguen siendo conocimiento público.

---

## 1. Open Interpreter

**Ubicación local:** `Extras/Competidores/open-interpreter-main/`

### Arquitectura real
- **Loop principal:** `respond()` en `interpreter/core/respond.py` — yields chunks (LLM thinking) y, al detectar bloque de código, lo parsea, llama `terminal.run(language, code)` que ejecuta vía `subprocess.Popen` (`interpreter/core/computer/terminal/languages/subprocess_language.py:50`).
- **Loop control:** `loop_message` y `loop_breakers` configurables (`interpreter/core/core.py:54-60`) — strings que terminan el loop. **No hay step budget numérico.**
- **LLM:** `litellm` multi-proveedor (`interpreter/core/llm/llm.py:3`).

### Verifier
- En "OS mode": tras cada acción, snippet `computer.display.view()` con delay de 2 s (`interpreter/terminal_interface/profiles/defaults/os.py:101`). Solo screenshot, no verifica que el efecto pretendido haya ocurrido.
- `truncate_output(data, max_chars=2800)` (`interpreter/core/utils/truncate_output.py:1`) — corta output, no verifica.

### Policy pre-LLM
- Modos: `safe_mode = "off" | "ask" | "auto"`, default `"off"` (`interpreter/core/core.py:50`).
- Si `safe_mode != "off"` corre `semgrep scan --config auto --quiet --error` (`interpreter/core/utils/scan_code.py:30-39`).
- **No hay lista de comandos peligrosos hardcoded.** Toda la defensa depende del registry público de semgrep.

### Hardcodes
- Mínimos: usa `computer` API dinámica que se adapta al SO. Profiles en `interpreter/terminal_interface/profiles/defaults/` (os.py, llama3.py, etc.).

### Local-first
- **SÍ.** `interpreter --local` lanza wizard para descargar Ollama (`interpreter/terminal_interface/local_setup.py:1-50`). Detecta proveedor: `if "ollama" in interpreter.llm.model` (`validate_llm_settings.py:91-95`).

### Tests
- 4 archivos: `test_interpreter.py`, `test_async_core.py`, `test_computer.py`, `test_files.py`. Cobertura débil.

### Lo mejor (real, citado)
- Simplicidad arquitectónica + offline-first + computer API dinámica.

### Lo peor (real, citado)
- **Sin sandbox real** (subprocess en el host).
- Sin verifier de estado del sistema.
- **Sin step budget**: dependencia total de los `loop_breakers` por string.
- `safe_mode` requiere `semgrep` instalado externamente.

### Qué puede aprender Carter
- El concepto de **profiles por dominio** (`profiles/defaults/os.py` etc.) es elegante. Carter podría tener perfiles de comportamiento por escenario.
- Streaming chunks tipados (`{"type": "confirmation"}` en `respond.py:289`) para distinguir mensajes UX de output de tools.

---

## 2. OpenHands (antes OpenDevin)

**Ubicación local:** `Extras/Competidores/OpenHands-main/`

### Arquitectura real
- App-server FastAPI: `openhands/app_server/app.py`.
- **La lógica del agente está en un paquete externo: `openhands-agent-server==1.20.1`** (`pyproject.toml`). El loop, el verifier y la policy NO son auditables desde este repo.
- Sandbox: `DockerSandboxService` (`openhands/app_server/sandbox/docker_sandbox_service.py:82`) — **Docker obligatorio**.
- Eventos vía `/api/v1/conversation/{id}/events`.
- LLM: `litellm!=1.64.4,!=1.67.*,>=1.83.14` (`pyproject.toml`).
- Browser: Playwright + browsergym 0.13.3.

### Verifier
- **No visible en este repo.** Probablemente en `agent-server` (no auditable).

### Policy pre-LLM
- **No visible en este repo.** Defensa primaria = aislamiento Docker.

### Step budget
- **No visible en este repo.**

### Hardcodes
- Skills en `skills/*.md` declaran `agent: CodeActAgent` (cada skill amarrada al mismo tipo de agente).

### Tests
- **97 archivos** en `tests/unit/` (LLM utils, analytics, settings, storage, integrations). NO hay tests de la lógica del agente (vive en agent-server externo).

### Local-first
- **NO.** Requiere Docker (local o remoto). Soporte de kubernetes (`pyproject.toml: kubernetes>=33.1`). No hay soporte explícito a Ollama en el código visible.

### Lo mejor
- Aislamiento Docker real, arquitectura event-driven escalable, hub modular de skills, lista para Kubernetes, cobertura de tests amplia.

### Lo peor
- **Lógica principal oculta** (agent-server externo) — auditoría limitada.
- No es local-first.
- Complejidad: FastAPI + app-server + agent-server.

### Qué puede aprender Carter
- **Event stream tipado por categoría** (`ACTION`, `USER_ACTION`, `STEP`) — mucho mejor que prints. Carter podría tipar todos sus eventos así.
- Patrón de "skills" en Markdown estructurado para enseñar al agente capacidades nuevas.

---

## 3. AutoGPT (classic)

**Ubicación local:** `Extras/Competidores/AutoGPT-master/classic/`

### Arquitectura real
- `ForgeAgent.execute_step(task_id, step_request)`: 1 step = 1 invocación externa.
- `propose_action()` (`classic/forge/forge/agent/forge_agent.py:168-195`):
  - Reúne directives + commands + messages.
  - **HALLAZGO CRÍTICO:** la llamada al LLM **NO está implementada**. La función retorna un stub:
    ```python
    proposal = ActionProposal(
        thoughts="I cannot solve the task!",
        use_tool=AssistantFunctionCall(name="finish",
                                       arguments={"reason": "Unimplemented logic"}),
        ...)
    ```
    Comentario explícito en `:195`: *"THIS NEEDS TO BE REPLACED WITH YOUR LLM CALL/LOGIC"*. La referencia a `original_autogpt/agents/agent.py` apunta a un archivo que **no existe** en `classic/`.
- `execute(proposal)` (`forge_agent.py:211-243`): busca el comando en `self.commands` por nombre y lo invoca directamente con `**tool.arguments`.

### Tool calling
- Decorador `@command(...)` (`classic/forge/forge/command/decorator.py`).
- `Command(Generic[P, CO])` (`classic/forge/forge/command/command.py:16-83`).
- **Sin validación de argumentos pre-LLM**: si el LLM envía args mal, falla en runtime.

### Memoria
- `BaseAgentSettings.save_state()` a file storage (`classic/forge/forge/components/file_manager/file_manager.py:102-116`). Backends: local / S3 / GCS.
- `chromadb = "^1.4.0"` declarado en `pyproject.toml:38` pero **no usado en Forge**.

### Verifier
- **No existe.** No hay re-verificación post-ejecución.

### Policy pre-LLM
- `CommandPermissionManager` con orden de chequeo: agent_deny → workspace_deny → agent_allow → workspace_allow → prompt_fn (`classic/forge/forge/permissions.py:66-72`).
- **Granular y bien diseñado**, pero **opt-in**: en `execute()` no es obligatorio.

### Step budget
- `cycle_budget: Optional[int] = 1` (`classic/forge/forge/agent/base.py:68-77`).
- `cycle_count` se incrementa en `propose_action()` (`forge_agent.py:247`) **pero no bloquea ejecución**.

### Hardcodes
- `fast_llm = OpenAIModelName.GPT3_16k`, `smart_llm = OpenAIModelName.GPT4` (`base.py:60-62`).
- `DEFAULT_TRIGGERING_PROMPT = "Determine exactly one command..."` (`base.py:45`).
- `openai = "^1.50.0"` (`pyproject.toml:27`).

### Tests
- ~50 archivos de "smoke tests" sin assertions reales.

### Local-first
- **SÍ:** `FILE_STORAGE_BACKEND=local` por defecto (S3/GCS opcionales).

### Lo mejor
- `CommandPermissionManager` con `(agent|workspace) × (allow|deny)` es el modelo de permisos más granular del set.

### Lo peor
- **Forge no implementa la llamada LLM.** Para usarlo de verdad hay que escribir esa pieza desde cero.
- Permission manager opt-in (no enforced en el path de ejecución).
- Tests débiles (smoke sin assertions).

### Qué puede aprender Carter
- **Modelo de permisos por capas (agent vs workspace, allow vs deny)** es excelente. Carter actualmente tiene policy pre-LLM monolítica; podría dividirla en capas.

---

## 4. Microsoft AutoGen

**Ubicación local:** `Extras/Competidores/autogen-main/`

### Estructura
- `autogen-core/` (runtime base), `autogen-agentchat/` (multi-agent), `autogen-ext/` (extensiones), `autogen-magentic-one/`, `autogen-studio/`, `pyautogen/` (compat v0.2).
- Estado: **maintenance mode** (`README.md:16`).

### Arquitectura real
- `BaseGroupChat.run() / run_stream()`: levanta runtime, suscribe agentes a topics, crea `GroupChatManager`.
- `AssistantAgent.on_messages_stream()` (`autogen-agentchat/.../agents/_assistant_agent.py:960+`):
  1. Añade mensajes al `model_context`.
  2. `_update_model_context_with_memory(memory, model_context)` — emite eventos.
  3. `_call_llm(...)` — streaming vía `litellm`.
  4. `_process_model_result(...)` — ejecuta tools y eventualmente reflexiona.
  5. `yield Response(chat_message=..., inner_messages=...)`.

### Tool calling
- Function tools auto-envueltos en `FunctionTool`; nombre = `func.__name__`, descripción = docstring.
- `_execute_tool_calls()` (`_assistant_agent.py:1196+`): **paralelo por defecto** (`asyncio.gather`); desactivable vía `parallel_tool_calls=False` del provider.
- `max_tool_iterations: int = 1` (`_assistant_agent.py:139-146`): controla cuántos ciclos LLM→tool→LLM por `on_messages()`.
- **Workbench (MCP) soportado**: `McpWorkbench(server_params=StdioServerParams(...))`.

### Memoria
- Protocol `Memory` (`autogen-core/.../memory/_base_memory.py`): `add()`, `query()`, `update_context()`.
- `ListMemory` (`autogen-core/.../memory/_list_memory.py`): in-context, cronológico, **sin vector search**. Inyecta como `SystemMessage` con prefijo "Relevant memory content (in chronological order):".

### Verifier
- Parcial: el resultado del tool entra como `ToolExecutionResultMessage` y, si `reflect_on_tool_use=True`, hay otra inferencia. **No verifica estado del sistema.**

### Policy pre-LLM
- **Inexistente.** Único defensor: warning textual en `LocalCommandLineCodeExecutor` recomendando usar `DockerCommandLineCodeExecutor`.

### Step budget
- `MaxMessageTerminationCondition`, `TokenLimitTerminationCondition`, `HandoffTerminationCondition`, `TimeoutTerminationCondition` (`autogen-agentchat/.../conditions/_terminations.py`). **Por team run, no por agente.**

### Human-in-the-loop
- `HumanProxyAgent` emite `UserInputRequestedEvent` y suspende el equipo hasta que llega input.

### Code execution
- `LocalCommandLineCodeExecutor` (`autogen-ext/.../code_executors/local/__init__.py:45-300`) con warning de seguridad.
- Alternativa: `DockerCommandLineCodeExecutor`.

### Tests
- Cobertura buena.

### Local-first
- **SÍ** (litellm acepta endpoints locales).

### Lo mejor
- API de tools por convención (`func.__name__` + docstring) elimina boilerplate.
- `TerminationCondition` componible (token, mensajes, timeout, handoff).
- **Workbench MCP**: tools descubribles en runtime.

### Lo peor
- **Cero policy pre-LLM**: la seguridad se delega al sandbox.
- `max_tool_iterations=1` por defecto puede hacer al agente "dormirse" tras una sola tool.
- Maintenance mode oficial.

### Qué puede aprender Carter
- **`TerminationCondition` componible** es un patrón excelente. Carter actualmente mezcla "step budget" en una variable; podría modelarlo como condiciones combinables.
- **Workbench MCP** para registrar tools externas en caliente sin tocar `catalog.py`.

---

## 5. LangGraph

**Ubicación local:** `Extras/Competidores/langgraph-main/`

### Arquitectura real
- **Pregel** (`libs/langgraph/langgraph/pregel/_loop.py`): grafo dirigido distribuido. Nodos = funciones de transformación de estado; arcos = dependencias; estado tipado (`TypedDict` o `BaseModel`) con reducers (`add_messages`, etc.) y canales (`LastValue`, `BinaryOperatorAggregate`, `DeltaChannel`).
- `StateGraph.compile()` → `CompiledStateGraph`.
- Ejecución paralela donde es posible.

### Tool calling
- `ToolNode(tools)` (`libs/prebuilt/langgraph/prebuilt/tool_node.py:200+`): valida nombre contra `tools_by_name`, ejecuta **TODAS las tool calls en paralelo** (`asyncio.gather`).
- `ToolCallRequest(tool_call, tool, state, runtime)` (`tool_node.py:133`): los tools reciben el `state` completo del grafo (no solo args).
- `create_react_agent()` (`libs/prebuilt/langgraph/prebuilt/chat_agent_executor.py:278`): wrapper que arma `StateGraph` con nodos "assistant" y "tools" + routing `tools_condition()`.

### Checkpointing y replay
- `Checkpoint(values, channel_versions, timestamp, metadata, source)` (`libs/checkpoint/langgraph/checkpoint/base/__init__.py:50`).
- `source` ∈ `{"input","loop","update","fork"}` (`:42-48`) — incluye **fork**.
- Backends: SQLite, Postgres, custom (`BaseCheckpointSaver`).
- **Replay** desde cualquier `checkpoint_id`; **fork** vía `update_state()` antes de continuar.
- `Durability ∈ {"sync","async","exit"}` (`types.py:120`).

### Interrupts
- `Interrupt(value, resumable=True)` (`types.py:730+`).
- `interrupt_after` / `interrupt_before` por nodo (`_loop.py:172-173`).
- `HumanInterrupt(action_request, config, description)` (`prebuilt/interrupt.py`).
- Resume = re-invocar `graph.stream(None, config={"checkpoint_id": ...})`.

### Memoria
- **Store nativo** key-value persistente, scoped `(namespace, key)`, inyectable en tools vía `InjectedStore`. Implementaciones in-memory, SQLite, async.
- Mensajes de conversación viven en el state (`add_messages` reducer).

### Policy pre-LLM
- **No built-in.** Solo validación de tool name (`INVALID_TOOL_NAME_ERROR_TEMPLATE`). DIY: insertar nodo "permission_checker" en el grafo.

### Tests
- Buena cobertura unit + integration.

### Local-first
- Cloud-agnostic. LangGraph Server opcional. Checkpointer/Store pueden ser cloud.

### Lo mejor
- **Time travel**: replay y fork desde cualquier checkpoint.
- **Store separado del state**: hechos persistentes ≠ mensajes transitorios.
- **State injection en tools**: el tool ve el contexto completo del grafo.
- **`interrupt_before/after` por nodo**: human-in-the-loop limpio.

### Lo peor
- Sin policy pre-LLM built-in (DIY).
- Multi-thread/cloud durability es overkill para un asistente single-user.
- Curva de aprendizaje (hay que pensar en grafos, no en imperativo).

### Qué puede aprender Carter
- **Checkpointing por turno** (snapshot del session_state) → permite replay/debug y futuro "deshacer".
- **Store separado** para hechos persistentes (preferencias del usuario, apps recientes, "remembered facts"), distinto de la conversación.
- **State injection en tools**: pasar el `SessionState` al tool, no solo argumentos.

---

## 6. Goose (Block) — **Rust**

**Ubicación local:** `Extras/Competidores/goose-main/`

### Arquitectura real
- `Agent::reply()` (`crates/goose/src/agents/agent.rs:1028`) retorna `BoxStream<AgentEvent>`.
- Loop principal (`:1301`):
  1. Si `turns_taken > max_turns` → break.
  2. Prepara contexto (tools, system prompt).
  3. `provider.stream(...)` → LLM completion.
  4. Categoriza tool requests (frontend vs backend).
  5. **Tool inspection** (security, permisos).
  6. Ejecuta tools aprobados vía `extension_manager`.
  7. Drena mensajes `ActionRequired`.
  8. Lógica de retry si necesario.
- `max_turns` = 1000 por defecto (`:1293`) — **enforcement real**.

### Tool calling
- `dispatch_tool_call()` (`agent.rs:733`) → `extension_manager.dispatch_tool_call()`.
- Special tools: `PLATFORM_MANAGE_SCHEDULE_TOOL_NAME`, `FINAL_OUTPUT_TOOL_NAME`.
- Extensiones MCP-native, lazy-loaded.
- **Builtin extensions** (`crates/goose-mcp/src/lib.rs:55`): `autovisualiser`, `computercontroller`, `memory`, `tutorial`.

### Verifier
- No hay state verifier, pero **`RepetitionInspector`** detecta tool calls repetidas en bucle.

### Policy pre-LLM (la joya de Goose)
Pipeline de inspectores en orden de prioridad (`agent.rs:1454`):
1. **`SecurityInspector`** — pattern matching anti prompt-injection.
2. **`EgressInspector`** (`egress_inspector.rs:25`) — regex sobre URLs, git SSH, S3, GCS contra allow/deny lists.
3. **`AdversaryInspector`** — **second-opinion LLM (Claude)** que revisa el tool call, configurable vía `~/.config/goose/adversary.md`.
4. **`PermissionInspector`** — grants en archivo `~/.config/goose/permissions`.
5. **`RepetitionInspector`** — bucle detection.

Mode `SmartApprove` (`agent.rs:1444`) lee `ToolAnnotations` (read_only, destructive, idempotent) y salta aprobación para tools seguras.

### ActionRequired bidireccional
- `MessageContent::ActionRequired(ActionRequiredData{id, action, user_data})` — el LLM puede pedir DATOS al usuario (no solo "yes/no").
- Frontend resume con `handler.submit_response(id, user_data)`.
- `ToolConfirmationRouter` (oneshot channel) bloquea hasta `deliver()`.

### Permission types
- `AlwaysAllow | AllowOnce | Cancel | DenyOnce | AlwaysDeny` (`permission_confirmation.rs:5`).

### Memoria
- Per-session: `Conversation` lista de `Message` (`User|Assistant|ToolRequest|ToolResponse|ActionRequired|Thinking`).
- Compaction automática (`context_mgmt/mod.rs`, threshold 0.75).
- Persistente: extensión `memory` (MCP builtin) con `memory_put`, `memory_get`, `memory_search`.

### Tests
- `agent.rs`, `mcp_integration_test.rs`, `tool_inspection_manager_tests.rs`, `repetition_inspector_tests.rs`, `adversary_inspector_tests.rs`, `acp_*.rs`, `session_*.rs`, `compaction.rs`. Buena cobertura.

### Local-first
- **SÍ, puramente local**: app Electron + servidor `goosed` local. Soporta Ollama. ACP (Auth Control Proxy) opcional para OIDC.

### Lo mejor
- **Pipeline de inspectores compositiva pre-ejecución** — el modelo más maduro del set.
- **`AdversaryInspector` (LLM second opinion)** — defensa contra prompt injection con un segundo modelo.
- **`ActionRequired` bidireccional** — el LLM puede solicitar datos al usuario, no solo confirmación.
- **Mode `SmartApprove`** con `ToolAnnotations` (`read_only`, `destructive`, `idempotent`).
- Persistente local + MCP nativo.

### Lo peor
- Rust = barrera de entrada alta para contribuir.
- Sin checkpointing/replay tipo LangGraph (conversación lineal).
- Sin GUI automation propia (depende de extensiones).

### Qué puede aprender Carter (alto valor)
- **Convertir `policy.py` en pipeline de inspectores ordenados** (Security → Egress → Adversary → Permission → Repetition) en lugar de un solo `analyze()`.
- **Anotaciones por tool** (`read_only`, `destructive`, `idempotent`) en `catalog.py` para que la policy pueda decidir más fina.
- **`ActionRequired` bidireccional**: cuando el LLM necesita un dato del usuario (¿qué carpeta?, ¿qué archivo?), modelarlo como una clase de mensaje en lugar de pregunta libre.
- **`AdversaryInspector` opcional** con un segundo modelo Ollama local revisando tool calls de alto riesgo.

---

## 7. OS-Copilot (FRIDAY Agent)

**Ubicación local:** `Extras/Competidores/OS-Copilot-main/`

### Arquitectura real
- `FridayAgent.run(task)` (`oscopilot/agents/friday_agent.py:43-68`):
  1. `planner.decompose_task()` → subtasks con dependencias (orden topológico, `friday_planner.py:45-90`).
  2. Para cada sub_task: `executor.generate_tool()` → `executor.execute_tool()` → `executor.judge_tool()` → si falla, `repair_tool()` (max 3).
  3. `self_refining()` para replan si necesario.
  4. `self_learner.design_course()` para aprender.

### Tool generation dinámica (lo distintivo)
- LLM genera función Python/Shell/AppleScript completa + `<invoke>name(args)</invoke>` (`oscopilot/prompts/friday_pt.py`).
- `extract_json_from_string()`, `extract_code()`, regex de invocación (`oscopilot/agents/base_agent.py:46-70`).
- Ejecuta vía `self.environment.step(node_type, code)` que retorna `{result, error, pwd, ls}`.

### Verifier
- `judge_tool()` (`oscopilot/modules/executor/friday_executor.py:175-240`): LLM analiza `state.result`, `state.error`, `state.pwd`, `state.ls` → `{reasoning, status: 'Succeed'|'Amend'|'Replan', score}`.
- **Sin verificación visual**: solo stdout/stderr.

### Policy pre-LLM
- **NO existe.** Confía en el LLM para no generar código peligroso.

### Step budget
- `max_repair_iterations = 3` (`oscopilot/utils/config.py:61`) por subtarea — **muy restrictivo**.

### Memoria persistente (impresionante)
- `self_learning.py:40-80`: cursos JSON guardados en `courses/{software}_{package}.json`, leídos al inicio.
- Vector DB Chroma para retrieval de tools similares (`oscopilot/tool_repository/manager/tool_manager.py:73-80`).

### Hardcodes
- Paths: `oscopilot/tool_repository/generated_tools`, `courses/`.
- `EMBED_MODEL_TYPE == "OpenAI"` requiere `OPENAI_API_KEY` (`tool_manager.py:69-73`).

### Tests
- 5 archivos: `test_executor.py`, `test_planner.py`, `test_self_learning.py`, `test_basic_planner.py`, `test_data_loader.py`.

### Local-first
- **NO**: embeddings OpenAI obligatorios para Chroma.

### Lo mejor
- **Dynamic tool generation**: LLM crea código para tareas nunca vistas.
- **Topological planning** con dependencias entre subtareas.
- **Persistent learning courses** entre sesiones.

### Lo peor
- Cloud-dependent embeddings.
- `max_iter=3` muy restrictivo.
- Sin verifier visual ni de estado de sistema (solo stdout).
- Sin policy.

### Qué puede aprender Carter
- **Topological planning** para misiones multi-paso con dependencias entre subtareas.
- **Persistent learning** ligero (JSON por dominio) para reducir prompt boilerplate en escenarios repetidos.

---

## 8. Agent-S (S3 — SOTA en OSWorld)

**Ubicación local:** `Extras/Competidores/Agent-S-main/`

### Arquitectura real
- `AgentS3.predict()` (`gui_agents/s3/agent_s.py:84-90`) → `Worker.generate_next_action()`:
  1. Reflection agent (opcional, en turn≥1).
  2. Generator agent (LLM) → genera código `pyautogui`.
  3. **`BehaviorNarrator.judge()`** post-acción.
- Sin manager/planner explícito (el Worker es ejecutor directo).
- Loop control (`osworld_setup/s3/run_local.py`): `max_steps=15`, `max_trajectory_length=8`. Code agent budget=20 (`memory/procedural_memory.py:51`).

### LLMs soportados
- OpenAI, Anthropic (incluido Claude 3.7 Sonnet **thinking mode**, budget 4096 tokens, `core/engine.py:109-115`), Gemini, HuggingFace, vLLM, OpenRouter, Azure OpenAI.
- `split_thinking_response()` para extraer `<thoughts>` y `<answer>` (`utils/common_utils.py:158`).

### Acciones
- `pyautogui.click(x,y)`, `moveTo`, `dragTo`, `write('text')`, `press('key')` (coordenadas absolutas).
- "Code agent" alternativo para tareas no GUI.
- LibreOffice Calc: usa **UNO bridge directo** (`grounding.py:79-200`) en lugar de simular GUI.

### Verifier — la fortaleza
- **`BehaviorNarrator`** (`bbon/behavior_narrator.py:25-75, 130-170`):
  - Anota la imagen *before* con la acción.
  - LLM compara *before* anotada vs *after* y emite `fact_thoughts` + `fact_answer`.
- **`ComparativeJudge`** (`bbon/comparative_judge.py:100-145`): compara N rollouts, elige el mejor visualmente — Best-of-N.
- → No se puede declarar DONE sin evidencia visual.

### Policy pre-LLM
- No engine. Restricciones en `PROCEDURAL_MEMORY` (system prompt, `memory/procedural_memory.py:25-70`).

### Step budget
- `max_steps=15`, `max_trajectory_length=8`, code agent=20. Configurables.
- Estrategia de flush: mantiene últimas K imágenes; en modelos no-long-context dropea turns enteros (`agents/worker.py:90-110`).

### Memoria
- **NO entre sesiones.** Solo `worker_history`, `reflections`, `screenshot_inputs` in-session.

### Hardcodes
- Mínimos. Detección de apps usa `difflib.get_close_matches('APP_NAME', window_titles, n=1, cutoff=0.1)` (`grounding.py:38`) — **fuzzy contra titulos reales**.
- `skipped_actions` por plataforma (`worker.py:68-72`).

### Tests
- **NO tiene test suite.** Eval: OSWorld benchmark — **Agent-S3 = 72.60% (SOTA, supera a humanos)**.

### Local-first
- Híbrido: ejecución local; LLM cloud (con vLLM/Ollama posible en teoría).

### Lo mejor
- **BBON con `BehaviorNarrator` + `ComparativeJudge`** = anti-fake-success por evidencia visual. **Patrón que Carter debería absorber.**
- **`LMMEngine*`** — abstracción multi-proveedor limpia con thinking mode.
- **Reflection agent** post-acción (no solo "act and pray").
- 72.60% en OSWorld habla por sí solo.

### Lo peor
- Sin persistencia entre sesiones.
- Hard requirement en imágenes/VLM (lento sin GPU).
- BBON elige "el menos malo" si todos los rollouts fallan.

### Qué puede aprender Carter (alto valor)
- **Visual `BehaviorNarrator` opcional** para misiones GUI: capturar before/after, marcar la acción, pedir al LLM que confirme el cambio. Carter ya tiene verifiers de estado lógico; añadir una capa visual lo lleva al nivel de Agent-S.
- **Best-of-N para acciones críticas**: generar 2-3 rollouts en paralelo y elegir el mejor.
- **Reflection agent** que revise el historial antes de proponer acción.
- **Thinking mode** cuando se use Claude (Carter actualmente solo Ollama).

---

## 9. Claude Computer Use (Anthropic) — análisis público

(Sin código abierto. Mantengo la sección como referencia conceptual.)

- 100% cloud, screenshots + acciones (click/type/scroll).
- Fortalezas: VLM nativo de calidad, descripción de pantalla rica, verbalización honesta.
- Debilidades: cloud, caro por token, lento, sin privacidad.
- Aprendizaje para Carter: **describe-then-act-then-verify** ya está en la filosofía; lo que falta es la calidad VLM (Carter no la necesita si verifica por estado).

---

## 10. Windows Copilot (Microsoft) — análisis público

(Sin código.)

- 100% cloud Microsoft, integración profunda Windows.
- Fortalezas: shell/PowerShell/WMI, MSA memory.
- Debilidades: cloud, sin privacidad, sin control del usuario.
- Aprendizaje: integración nativa con `Get-StartApps`, WMI, `Win32_Process` — Carter ya hace esto vía psutil/win32api.

---

## Cambios respecto a la versión 1

| Competidor | Cambio principal vs v1 |
|---|---|
| Open Interpreter | Confirmado: sin step budget, sin sandbox, `safe_mode` opt-in con semgrep externo. v1 era correcta en lo esencial. |
| OpenHands | **Hallazgo importante**: la lógica del agente vive en `openhands-agent-server` externo (no auditable). Lo que SÍ está aquí es FastAPI + DockerSandbox + skills. |
| AutoGPT | **Hallazgo crítico**: Forge **NO implementa la llamada al LLM** (stub `"I cannot solve the task!"`). El `CommandPermissionManager` por capas es excelente. |
| AutoGen | Confirmado en maintenance mode. `TerminationCondition` componibles + `ListMemory` + workbench MCP son los aprendizajes. |
| LangGraph | **Hallazgo de alto valor**: Store nativo, checkpointing con fork/replay, `interrupt_before/after`, state injection en tools. |
| Goose | **Hallazgo de alto valor**: pipeline de 5 inspectores pre-LLM (incluye Adversary LLM second-opinion), `ActionRequired` bidireccional, `ToolAnnotations`. Es Rust. |
| OS-Copilot | Topological planner + dynamic tool generation + cursos JSON persistentes. Cloud-dependent (embeddings OpenAI). |
| Agent-S | **Hallazgo de alto valor**: `BehaviorNarrator` + `ComparativeJudge` (BBON) — verificación visual real. SOTA en OSWorld 72.60%. |

> Esta v2 sustituye la `[inferencia]` de v1 con citas verificadas. La v1 queda en `COMPETITOR_LANDSCAPE_AUDIT.v1_inferencia.md` como referencia histórica.
