# 14 — Auditoría de 10 competidores

**Fecha**: 2026-05-11
**Insumos**: `Extras/Competidores/` (10 proyectos open-source)

Este documento absorbe lo aprendido de **competidores reales en producción**
y lo destila a patterns aplicables a Carter v5. Cada hallazgo cita la fuente
y dice exactamente qué hacer con él.

---

## Resumen ejecutivo

| Competidor | Score externo | Lección para Carter v5 |
|---|---|---|
| **Agent-S3** (Simular) | OSWorld **72.6%** (1° humano-level) | Minimal hierarchy + **Dual Agent (GUI + Code)** + procedural memory |
| **OpenHands** | SWE-bench **77.6%** | **Event/Action/Observation** stream, **Bash Session persistente con tmux**, microagents |
| **OS-Copilot** (FRIDAY) | Paper ICLR 2024 | **SelfLearner** (course design), Planner + Retriever + Executor + Learner + ToolManager |
| **goose** (AAIF) | Productivo | **MCP integration** (70+ extensions), **ACP** (Agent Communication Protocol), Rust native |
| **langgraph** | Industry standard | **State graphs**, **Durable execution**, **Human-in-the-loop interrupts**, comprehensive memory |
| **autogen** (Microsoft) | EOL, ahora MAF | Multi-agent patterns (siguen vivos en MAF), A2A protocol |
| **AutoGPT** | Legacy | Skill management original (ya superado por Agent-S/Voyager) |
| **open-interpreter** | Productivo | LLM runs **Python/JS/Shell locally** via REPL, simple loop |
| **openclaw** | Productivo | Multi-channel: WhatsApp/Telegram/Slack/Discord (out of scope para Carter) |
| **Mark-XXXIX** | Hobby project | Confirma que Carter es vertical popular; ~10 actions específicas hardcoded |

---

## 1. Agent-S3 (Simular) — LIDER OSWORLD 72.6%

### 1.1 Hallazgos clave

**Arquitectura**:
- v1 → v2 → v3: **simplificó cada versión**, removió jerarquía.
- S2 tenía Manager + Worker; **S3 tiene solo Worker** + grounding agent (UI ACI).
- Validación medible: bench más alto con MENOS capas.

**Dual Agent (GUI + Code)**:
- GUI Agent: clicks, typing, navigation, visual features.
- **Code Agent**: ejecuta Python/Bash en sandbox para "ALL spreadsheet calculations, data manipulation, bulk operations, formatting changes".
- Pattern: `agent.call_code_agent("specific subtask")` cuando la tarea es manipulación de datos. Step budget 20.
- **Interpretación de resultados**: DONE / FAIL / BUDGET_EXHAUSTED.
- **CRÍTICO**: "ALWAYS verify code agent results with GUI actions before using agent.done(); NEVER trust code agent output alone."

**Procedural memory**:
- Plantillas de prompt que se inyectan dinámicamente según task type.
- "expert in graphical user interfaces and Python code" como rol base.

### 1.2 Aplicable a Carter v5

| Pattern Agent-S3 | Aplicar a Carter v5? | Cómo |
|---|---|---|
| Minimal hierarchy (1 Worker) | ✅ **Ya está hecho** (v5 elimina los 3 routers de v4) |
| Dual Agent GUI + Code | 🟡 **Considerar v5.1** | Carter tiene `terminal_run` para shell pero no un Code Agent autónomo con step budget |
| Behavior Best-of-N (S3 → +6 pts) | ❌ **No aplicable** | Requiere correr N rollouts en paralelo, latencia 5x. Carter es interactivo |
| Reflection enabled per turn | 🟡 **Parcial** | Carter tiene loop detection v2; agregar reflection sería extender ese módulo |

**Acción concreta**:
- Documentar pattern Dual Agent en `docs/ARCHITECTURE.md` para v5.1.
- Por ahora `terminal_run` cubre el caso Code (no autónomo, pero suficiente).

---

## 2. OpenHands — SWE-bench 77.6%

### 2.1 Hallazgos clave

**Arquitectura Event-driven**:
- No es while-loop. Es **Event Stream**.
- Cada evento es **Action** (emitida por agent) o **Observation** (resultado de tool).
- **Agent Controller** maneja state + lifecycle (no el agent mismo).
- Permite: pausar, inspeccionar, modificar, replay.

**CodeAct Agent**:
- Paper [arxiv 2407.16741](https://arxiv.org/abs/2407.16741).
- Acción primaria = **editar y ejecutar código**, no clickear.
- Mostrado en SWE-bench como pattern dominante.

**Bash Session con tmux**:
- Sesión bash **persistente** entre turns.
- State preservado (variables, cd, env vars).
- Carter v5 hoy: cada `terminal_run` es proceso nuevo → pierde state.

**Microagents**:
- Markdown files en `.openhands/microagents/glossary.md`, `documentation.md`.
- Inyectados al contexto cuando matchea trigger.
- Equivalente a "Skills" pero más simple.

**Agent Hub + Agent Delegation**:
- Registry central de agent types.
- Un agent puede delegar tasks a otro especializado.

### 2.2 Aplicable a Carter v5

| Pattern OpenHands | Aplicar a Carter v5? | Cómo |
|---|---|---|
| Event/Action/Observation stream | 🟡 **v5.1+** | Refactor arquitectónico grande. Por ahora `core/execution.py` while-loop |
| Agent Controller separado | ❌ **Innecesario** | Carter es single-agent local. OpenHands lo tiene por multi-agent |
| Bash Session persistente (tmux) | 🟢 **HACERLO en v5** | `terminal_run` debe mantener sesión entre calls. Windows = ConPTY o similar |
| CodeAct pattern | 🟡 **v5.1** | Para tareas complejas, Carter podría emitir `code_execute(language, script)` |
| Microagents (markdown injection) | 🟢 **HACERLO en v5** | Cada tier puede tener `microagents/*.md` que se inyectan según triggers |
| Agent Hub / Delegation | ❌ **Out of scope** | Carter es single-agent |

**Acción concreta v5.0**:
- Agregar `core/bash_session.py` con sesión Windows ConPTY persistente.
- Agregar `microagents/` directory por tier con triggers contextuales.

---

## 3. OS-Copilot (FRIDAY) — Paper ICLR 2024

### 3.1 Hallazgos clave

**Arquitectura modular clásica**:
- `Planner` (basic_planner.py, friday_planner.py)
- `Retriever` (vector_retriever.py)
- `Executor` (friday_executor.py)
- `Learner` (self_learner.py) — **único de los competidores**
- `ToolManager` — registry + lifecycle

**SelfLearner — curriculum learning**:
- `design_course(software_name, package_name, demo_file_path)` → genera "curso" con LLM.
- `continuous_learning(...)` ejecuta el curso, aprende tools nuevas, las agrega al ToolManager.
- **Voyager pattern Component 1** (automatic curriculum) implementado.

**Vector retriever**:
- 153 LOC. Embeddings sobre tools learned.
- top-K para seleccionar tool en cada turn.

### 3.2 Aplicable a Carter v5

| Pattern OS-Copilot | Aplicar a Carter v5? | Cómo |
|---|---|---|
| Planner + Retriever + Executor + ToolManager | 🟢 **Ya parcialmente** | Carter v5 tiene router (planner-light) + tool_retriever + execution + tools/__init__ |
| **SelfLearner (curriculum)** | 🔴 **Out of scope v5.0** | Requiere LLM grande para diseñar cursos. Gemma 4B no alcanza |
| Retriever per turn (con embeddings) | ⚠️ **EVITAR** | Lección v4: invalida prompt cache. v5 usa retrieval una vez por sesión |

**Acción concreta**: ninguna nueva — Carter v5 ya cubre 3/4 del stack OS-Copilot. SelfLearner queda para futuro.

---

## 4. goose (Block / Linux Foundation AAIF)

### 4.1 Hallazgos clave

**MCP (Model Context Protocol)**:
- 70+ extensions via [modelcontextprotocol.io](https://modelcontextprotocol.io/).
- Permite que goose **consuma tools de terceros** (filesystem, GitHub, web search, etc.) y **exponga sus propias tools** a otros agentes (Cursor, Claude Desktop).
- Standard de facto en 2026.

**ACP (Agent Communication Protocol)**:
- Permite usar suscripciones existentes (Claude/ChatGPT/Gemini) en lugar de API keys.
- Out of scope para Carter (es 100% local).

**Rust native**:
- Performance + portabilidad.
- Goose es desktop app, CLI, y API (embeddable).

**Multi-provider**:
- 15+ providers (Anthropic, OpenAI, Google, Ollama, OpenRouter, Azure, Bedrock).
- Carter v5: solo llama-server (Gemma 4) + Ollama fallback. Es **suficiente para uso local**, pero limitante si querés Anthropic API en algún momento.

### 4.2 Aplicable a Carter v5

| Pattern goose | Aplicar a Carter v5? | Cómo |
|---|---|---|
| **MCP server** (exponer tools) | 🟢 **HACERLO en v5.0 o v5.1** | Wrap el `tools/composite_dispatcher.py` como MCP server → Carter exposed a Cursor/Claude Desktop |
| **MCP client** (consumir tools) | 🟡 **v5.1** | Carter podría consumir GitHub MCP, Filesystem MCP, etc. Aumenta capacidades sin escribir tool |
| Multi-provider adapter | 🟡 **Parcial** | Carter v5 ya tiene `adapters/` con llama-server + ollama. Agregar Anthropic/OpenAI API es trivial pero rompe "100% local" |
| Rust performance | ❌ **No aplicable** | Python adecuado para Carter |

**Acción concreta v5.0**:
- Agregar `mcp_server.py` opcional que expone los 16 composite tools como MCP server.
- Esto hace que **otros agentes puedan usar Carter como backend de herramientas Windows**.

---

## 5. langgraph (LangChain)

### 5.1 Hallazgos clave

**State Graphs**:
- En lugar de while-loop, define **nodos** y **edges**.
- Cada nodo es una función pura `state → state'`.
- Edges pueden ser condicionales.
- Permite: branching, subgraphs, parallel execution.

**Durable execution**:
- Agents persisten estado en disco.
- Resume después de crash/restart desde donde quedó.
- Útil para tareas long-running (>1h).

**Human-in-the-loop interrupts**:
- Agent puede pausar en cualquier nodo.
- Usuario inspecciona/modifica state, agent continúa.
- Carter v5 tiene `pending_confirmation` que es una versión simple de esto.

**Comprehensive memory**:
- Short-term working memory (conversación actual).
- Long-term persistent memory (cross-session, semántica).

### 5.2 Aplicable a Carter v5

| Pattern langgraph | Aplicar a Carter v5? | Cómo |
|---|---|---|
| State Graphs | 🟡 **v5.1+** | Carter v5 usa while-loop. State graph es refactor grande, no urgente |
| **Durable execution** (persist state) | 🟢 **v5.0 — agregar** | Save TurnContext + MissionGoal a disk between turns. Resume si crash |
| Human-in-the-loop interrupts | 🟢 **Ya parcial** | `pending_confirmation` cubre destructive. Extender a misiones largas |
| Long-term persistent memory | 🟢 **Ya hecho** | `memory/store.py` SQLite + embedder |

**Acción concreta v5.0**:
- Agregar `core/durable_state.py` que persiste `TurnContext.messages` + `MissionGoal` a `~/.carter_v5/sessions/<session_id>.json` cada N segundos.
- Si Carter crashea, próximo boot puede recuperar la sesión.

---

## 6. Microsoft Agent Framework (sucesor de autogen)

**autogen está EOL**. El sucesor es **Microsoft Agent Framework (MAF)**.

Patterns de MAF (extrapolados):
- **A2A** (Agent-to-Agent protocol) — interop entre agents.
- **MCP** native.
- Multi-agent orchestration enterprise.

### Aplicable a Carter v5

Carter es single-agent local. **MAF patterns son out of scope** salvo MCP (cubierto en goose §4).

---

## 7. AutoGPT, open-interpreter, openclaw, Mark-XXXIX

### AutoGPT
- Legacy. Cloud platform.
- Patterns superados por Agent-S/Voyager.
- **Nada nuevo aplicable**.

### open-interpreter
- LLM runs Python/JS/Shell locally via REPL.
- Pattern simple: `interpreter.chat(message)` → ejecuta código.
- **Aplicable**: validar que `terminal_run` de Carter es robusto. No agregar nada nuevo.

### openclaw
- Multi-channel assistant (WhatsApp, Telegram, etc.).
- **Out of scope** para Carter (que es asistente local del usuario).

### Mark-XXXIX
- Confirma que el espacio "Jarvis local" tiene demanda real.
- ~10 actions hardcodeadas (browser_control, computer_control, file_controller, etc.).
- Patterns similares a Carter v4 — nada nuevo.

---

## 8. Síntesis: patterns a aplicar en Carter v5.0

### 🟢 P0 — agregar AHORA (antes de validar v5)

1. **Microagents directory** (de OpenHands).
   - `carter_v5/microagents/glossary.md`, `tools_cheat_sheet.md`, etc.
   - Inyectados al system_prompt cuando hay trigger.
   - Bajo costo (10 archivos markdown).

2. **Bash Session persistente** (de OpenHands).
   - `carter_v5/tools/terminal.py` debe mantener una sesión ConPTY persistente en Windows.
   - State preservado entre calls.

3. **MCP server** (de goose).
   - `carter_v5/mcp_server.py` expone los 16 composite tools como MCP.
   - Carter visible desde Cursor, Claude Desktop, otros clientes MCP.

4. **Durable session state** (de langgraph).
   - Persistir TurnContext + MissionGoal a `~/.carter_v5/sessions/<id>.json`.
   - Recovery on restart.

### 🟡 P1 — v5.1 (después de validar v5.0)

5. **Dual Agent: GUI + Code** (de Agent-S3).
   - Tool `code_execute(language, script, max_steps=20)` separado.
   - Verificación obligatoria con GUI antes de declarar DONE.

6. **CodeAct pattern** (de OpenHands).
   - Para tareas dev, primary action = edit+execute code.
   - Requiere prompt tier-specific.

7. **MCP client** (de goose).
   - Carter consume GitHub MCP, Filesystem MCP, etc.

### 🔴 P2 — v6 (cambio arquitectónico grande)

8. **Event/Action/Observation stream** (de OpenHands).
   - Decisión 2026-05-11: **esperar v5.1**. Razonamiento:
     - Carter v5.0 es single-user local interactivo — el while-loop cubre el caso.
     - Beneficios reales (replay, h-i-t-l rico, time-travel debug) son útiles
       pero NO crítico para validar la arquitectura básica.
     - Costo: 600-1000 LOC, refactor de 4-5 módulos centrales sin datos que
       lo justifiquen aún.
     - Plan: medir v5.0 con bench + uso real. Si aparecen casos donde el
       while-loop limita (debug post-mortem, intervención mid-execution),
       refactor a event stream en v5.1.
     - Reversible: el `core/execution.py` actual puede convertirse a publisher
       sin romper contratos externos. Decisión NO-bloqueante.
9. **State Graphs** (de langgraph).
10. **SelfLearner curriculum** (de OS-Copilot, Voyager Component 1).

### ⛔ NO aplicar

- Behavior Best-of-N (Agent-S3): latencia 5x, Carter es interactivo.
- ACP suscripciones (goose): rompe "100% local" de Carter (V1).
- Multi-channel (openclaw): out of scope.

---

## 9. Plan de aplicación a v5

Aplico los **4 P0** ahora, en este orden:

1. **microagents/** — crear directorio + 4 markdown files iniciales.
2. **Bash Session persistente** — refactor `tools/terminal.py` con ConPTY/winpty.
3. **MCP server** — `mcp_server.py` wrap el composite dispatcher.
4. **Durable state** — `core/durable_state.py` persiste session.

Luego de aplicar, **Carter v5.0 está completo** y listo para validación.

---

## 10. Referencias

### Papers
- Agent-S1 (ICLR 2025): <https://arxiv.org/abs/2410.08164>
- Agent-S2 (COLM 2025): <https://arxiv.org/abs/2504.00906>
- **Agent-S3 (2025, 72.6% OSWorld)**: <https://arxiv.org/abs/2510.02250>
- OS-Copilot FRIDAY (ICLR 2024): <https://arxiv.org/abs/2402.07456>
- CodeAct: <https://arxiv.org/abs/2407.16741>
- OpenHands tech report (2025): <https://arxiv.org/abs/2511.03690>

### Repos consultados
- `Extras/Competidores/Agent-S-main/gui_agents/s3/`
- `Extras/Competidores/OpenHands-main/openhands/`
- `Extras/Competidores/OS-Copilot-main/oscopilot/`
- `Extras/Competidores/goose-main/`
- `Extras/Competidores/langgraph-main/`
- `Extras/Competidores/Mark-XXXIX-main/Mark-XXXIX-main/`
- `Extras/Competidores/open-interpreter-main/`
- `Extras/Competidores/openclaw-main/`
- `Extras/Competidores/autogen-main/`
- `Extras/Competidores/AutoGPT-master/`

### Standards / Protocols
- MCP: <https://modelcontextprotocol.io/>
- A2A protocol: Microsoft Agent Framework docs.
