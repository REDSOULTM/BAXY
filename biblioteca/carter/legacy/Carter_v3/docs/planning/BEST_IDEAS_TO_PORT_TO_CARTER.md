# BEST_IDEAS_TO_PORT_TO_CARTER.md
# Mejores Ideas para Portar a Carter v3
# Generado por: Claude Code (claude-sonnet-4-6) — 2026-05-06
# CRITERIO: Solo ideas compatibles con ContextoCarter.md. Ninguna viola local-first, privacy, no-hardcode, no-fake-success.

---

## Leyenda de prioridad
- **P0** — Obligatorio antes de voz/cámara. Bloquea calidad real del núcleo texto.
- **P1** — Muy recomendado. Carter se vuelve significativamente mejor.
- **P2** — Bueno para después de cerrar núcleo texto.
- **P3** — Interesante pero no para Carter en este momento o incompatible con sus valores.

---

| Prioridad | Idea | Competidor origen | Problema que resuelve | Cómo adaptarla a Carter | Riesgo | Archivos Carter afectados |
|---|---|---|---|---|---|---|
| **P0** | Fix confirmación follow-up: aceptar "Sí"/"OK"/"YES"/"SI" | Bug interno Carter / todos los competidores lo hacen bien | B2: pending_intent no se activa con afirmativos cortos en mayúsculas | En `_short_same_language_nonsecret`: si el texto normalizado pertenece a un set pequeño de afirmativos conocidos (`{"sí","si","ok","yes","yep","claro","dale","va","np"}`), permitir sin verificar mayúsculas. Este set está auditado (no es routing semántico, es simple aceptación de confirmaciones). | BAJO (el set está acotado y bien documentado) | `session_state.py` |
| **P0** | Fix fake_success_guard: detectar claims a mitad del texto | Análisis interno Carter (CLAUDE_RUNTIME_CODE_AUDIT.md) | B3: "Intenté abrir Steam, está listo ahora." pasa el guard | Cambiar de `low.startswith(anchor)` a buscar `anchor` en el texto completo con word boundary regex. Excluir contextos donde la palabra es parte de una negación ("no está listo"). | MEDIO (mayor superficie de falsos positivos) | `guards.py:fake_success_guard` |
| **P0** | Fix notify_toast: cambiar de CONFIRMED a SKIPPED | Análisis interno Carter | B4: notify_toast reporta CONFIRMED sin verificación visual real | Cambiar `verifier="synchronous_ok"` a `verifier="skipped"` en el ToolSpec de notify_toast. Actualizar response_composer para usar SKIPPED semántica. | BAJO | `tools/catalog.py`, `tools/verifier.py`, `response_composer.py` |
| **P0** | Fix system_prompt: matizar "call it now" | Análisis interno Carter | B6: LLM ejecuta tools cuando usuario solo pregunta capacidad | Cambiar la cláusula a "if the user's intent is clearly an action request (not a question about capability), and a safe listed tool clearly fits, call it now." | BAJO | `turn_support.py:build_messages` |
| **P0** | Progress reporting entre steps de misión compuesta | Mark XXXIX (estados UI) / OpenClaw (update_plan) | B5: Silencio de 30-60s en misiones compuestas viola Valor 17 | En el loop de steps de `agent.py`, emitir un mensaje de progreso al usuario antes de cada step via `heartbeat` o yield al caller: "Ejecutando paso {n}/{total}: {tool_name} {target}..." | BAJO (no cambia lógica de ejecución) | `agent.py:loop de steps`, `heartbeat.py` |
| **P0** | Validar live con LLM real (Notepad open/close, web open, terminal) | Todos los competidores tienen validación live | Sin validación live, los 490 tests no prueban el comportamiento real | No es código — es proceso: ejecutar spotcheck manual del CLAUDE_MANUAL_SPOTCHECK_SET.md con Ollama corriendo, documentar resultados | BAJO | `docs/audit/` (solo documentación) |
| **P1** | Browser automation via Playwright | Mark XXXIX / OpenClaw / OpenHands | Carter no puede automatizar browsers más allá de open URL | Agregar `browser_playwright` tool opcional. Si Playwright disponible: navigate, click, type, screenshot, get_text. Encapsulada en su propia dispatch mixin. Reuse los schemas existentes. Sin cloud. | MEDIO (dependencia nueva: playwright-python) | `tools/dispatch_web.py`, `tools/catalog.py` |
| **P1** | SSRF protection en web_fetch | OpenClaw | Carter puede hacer requests a IPs privadas desde web_open_url o web_search helper | Agregar validación en web_helpers.py: rechazar URLs que resuelvan a IPs privadas (10.x, 192.168.x, 172.16.x, 127.x) | BAJO | `tools/web_helpers.py` |
| **P1** | Context compaction cuando overflow de contexto | OpenClaw | Con conversaciones largas, Carter trunca los últimos 6 turns sin avisar | Detectar cuando el historial de turns está al 80% del context window del modelo → resumir turns viejos en un "context summary" → mantener ese summary + turns recientes | MEDIO (requiere nueva llamada LLM para summarize) | `turn_support.py:build_messages` |
| **P1** | PTY support para terminal_run_command | OpenClaw / Open Interpreter | Carter tiene `subprocess.run` básico. Comandos interactivos (vim, python REPL, ssh) no funcionan | Agregar PTY mode en dispatch_terminal.py usando `pty.openpty()` o la librería `pexpect`. Timeout configurable. Streaming de output en tiempo real. | MEDIO (complejidad en Windows, pty no nativo en Windows) | `tools/dispatch_terminal.py` |
| **P1** | apply_patch tool para edición de archivos | OpenClaw / pi-coding-agent | Carter puede leer y escribir archivos completos, pero no aplicar diffs parciales | Agregar `filesystem_apply_patch(path, diff)` tool. Aplica unified diff a un archivo existente. Verificación post-apply via SHA-256. | BAJO | `tools/dispatch_filesystem.py`, `tools/catalog.py` |
| **P1** | Error classification estructural (retry/skip/abort) | Mark XXXIX (usando LLM) | Carter solo tiene retry para app_open. Otros errores no se clasifican. | Crear `error_taxonomy.py` con clasificación estructural (sin LLM): si `VerifierStatus==FAILED` y es un error transitorio conocido (timeout, network) → retry. Si es error permanente (wrong tool, no permission) → abort. Si es parcial (process started but window not found) → next_step hint. | BAJO | `recovery.py`, nuevo `error_taxonomy.py` |
| **P1** | Degradación automática por RAM/VRAM | ContextoCarter.md Valor 22 | Carter puede intentar cargar modelos cuando el sistema está al 95% RAM | En config startup: leer RAM y VRAM disponible. Si < umbral configurable → forzar ModelSelector a perfiles más pequeños, deshabilitar VLM, deshabilitar preload. | BAJO | `models/selector.py`, `config.py` |
| **P1** | Categorías semánticas en memory store | Mark XXXIX (6 categorías) | Carter guarda todo en una sola tabla. Recall semántico requiere buscar todo. | Agregar campo `category` opcional a la tabla memory: `identity`, `preferences`, `work`, `projects`, `facts`, `other`. Recall puede filtrar por categoría. Sin cambiar el schema principal (solo campo adicional). | BAJO | `memory/store.py` |
| **P1** | Model failover entre adapters | OpenClaw | Si Ollama no está disponible, Carter falla. No hay fallback a OpenAI-compat. | En adapter selection: si el primary adapter no está `available()`, intentar el siguiente en la lista de prioridad del model registry. | BAJO | `adapters/ollama_adapter.py`, `config.py` |
| **P2** | Docker sandbox para terminal CRITICAL | OpenClaw / OpenHands | Comandos CRITICAL en terminal se ejecutan directamente en el host | Para tools con risk=CRITICAL: si Docker disponible, ejecutar en container efímero. Si no → pedir confirmación explícita. | ALTO (dependencia Docker, complejidad) | `tools/dispatch_terminal.py` |
| **P2** | Semantic memory recall via embeddings | OpenClaw | Carter hace recall exacto por key. No puede buscar por concepto relacionado. | Agregar índice de embeddings local (sentence-transformers o similar) para buscar memorias por similitud semántica. Heavy: requiere embedding model. | ALTO (dependencia nueva, VRAM) | `memory/store.py`, nuevo `memory/embeddings.py` |
| **P2** | Task persistence para misiones largas | AutoGPT / LangGraph | Misiones de Carter se pierden si el proceso se reinicia | Serializar el estado de una misión en progreso a disco. Al reiniciar, ofrecer reanudar misión pendiente. | MEDIO | `session_state.py`, nuevo `mission_store.py` |
| **P2** | Webcam snapshot | Mark XXXIX (cv2) | Carter no puede capturar foto de la cámara física | Agregar `camera_snapshot(source_index=0)` tool. Usa cv2. Guarda JPEG a temp file. Verifica que el archivo existe y tiene tamaño. Retorna path. | BAJO (cv2 dependencia) | `tools/dispatch_misc.py`, `tools/catalog.py` |
| **P2** | First-run setup wizard | Mark XXXIX (overlay de setup) | Carter no guía al usuario en la configuración inicial de Ollama/modelo | Script de primer setup: detectar si Ollama está corriendo, qué modelos hay disponibles, seleccionar uno, escribir configuración. CLI simple, no UI. | BAJO | Nuevo `cli/setup_wizard.py` |
| **P2** | Toolkit grouping para tools | Goose (Block) | `catalog.py` tiene 32 tools sin agrupación visible | Agregar campo `toolkit` a ToolSpec: `system`, `app`, `browser`, `filesystem`, `terminal`, `memory`, `vision`. Permite filtrar tools por toolkit según el contexto. | BAJO | `tools/catalog.py` |
| **P2** | Visible plan / update_plan | OpenClaw | El usuario no puede ver qué pasos planificó Carter para una misión | Después del step_materialise, emitir un resumen de los pasos a ejecutar antes de empezar. "Voy a: (1) abrir Steam, (2) buscar la biblioteca, (3) confirmar resultado." | BAJO | `agent.py` |
| **P3** | Multi-agent subagent spawning | OpenClaw / AutoGen | Para PC personal tipo Jarvis, un solo agente es suficiente por ahora | Innecesario para fase texto. Complica el debugging. Añadir después de que el núcleo texto esté 100% validado. | - | - |
| **P3** | Plugin SDK / ClawHub | OpenClaw | Gran overhead de infraestructura para un asistente single-user | Fuera de scope para fase texto. Podría considerarse si Carter crece como producto. | - | - |
| **P3** | Multi-canal (WhatsApp, Telegram, Discord) | OpenClaw | Carter es asistente de PC personal, no bot de mensajería | Diferente nicho. Añadiría complejidad sin mejorar el objetivo Jarvis-local. | - | - |
| **P3** | LLM-based error fix generation | Mark XXXIX (generate_fix) | Pedirle al LLM que genere un "script de fix" es una superficie de ataque | Anti-Carter: puede generar código malicioso. El error debe resolverse con reglas estructurales, no con código generado por el LLM. | - | - |
| **P3** | 64-entry app aliases dict | Mark XXXIX | Carter ya tiene fuzzy resolver dinámico — superior | Hardcode directo. Anti-Carter. El fuzzy resolver es mejor. | - | - |

---

## Top 10 ideas de mayor impacto para cerrar el núcleo texto

1. **Fix B2** (confirmaciones Sí/OK/YES) — desbloquea C17
2. **Fix B3** (fake_success mid-text) — aumenta honestidad real
3. **Fix B4** (notify_toast→SKIPPED) — elimina CONFIRMED falso
4. **Fix B6** (system_prompt call-it-now) — elimina ejecuciones no pedidas
5. **Progress reporting en misiones** — desbloquea experiencia de misión compuesta real
6. **SSRF protection en web_fetch** — seguridad que falta
7. **Error classification estructural** — recovery más robusta sin LLM
8. **Browser Playwright básico** — la brecha más grande vs competidores
9. **Degradación automática por VRAM/RAM** — cumple Valor 22 de ContextoCarter
10. **Model failover entre adapters** — elimina punto de fallo único (Ollama down)

---

## Adendum 2026-05-06 — Ideas verificadas con código real de los 8 competidores

Tras descargar y auditar el código real de Agent-S, AutoGPT, AutoGen, Goose, LangGraph, Open Interpreter, OpenHands y OS-Copilot, se añaden estas ideas (todas compatibles con `ContextoCarter.md`):

| Prioridad | Idea | Origen (cita) | Adaptación a Carter | Riesgo |
|---|---|---|---|---|
| **P1** | **Pipeline de inspectores pre-LLM** (Security → Egress → Adversary → Permission → Repetition) en lugar de un único `policy.analyze()` monolítico | Goose `crates/goose/src/agents/agent.rs:1454` | Refactor de `security/policy.py` a una lista ordenada de `Inspector.inspect(call) -> Decision` componibles. Mantiene compatibilidad con la API actual. | BAJO |
| **P1** | **Tool annotations** (`read_only`, `destructive`, `idempotent`) en `ToolSpec` para que la policy decida más fina y `SmartApprove` funcione | Goose `ToolAnnotations` (`agent.rs:1444`) | Añadir 3 campos booleanos a cada `ToolSpec`. Policy lee anotaciones y salta verificación heavy en `read_only=True`. | BAJO |
| **P1** | **`ActionRequired` bidireccional** — el LLM puede pedir DATOS al usuario (no solo "yes/no") como un tipo de mensaje estructurado | Goose `MessageContent::ActionRequired(...)` | Modelar como nueva clase `PendingDataRequest{prompt, schema, request_id}` en `session_state.py`. UI/CLI presenta input tipado, devuelve via `submit_response`. | MEDIO |
| **P1** | **`TerminationCondition` componibles** (max_messages + token_budget + timeout + handoff) en lugar de una sola variable | AutoGen `_terminations.py` | Crear `runtime/termination.py` con clases componibles. `agent.py` evalúa `any(c.is_met() for c in conditions)`. | BAJO |
| **P1** | **State injection en tools** — los tools reciben el `SessionState` (no solo args) | LangGraph `ToolCallRequest{tool_call, tool, state, runtime}` (`tool_node.py:133`) | Pasar un `ToolContext` opaco al `dispatch_*` con campos read-only del state. Permite a tools leer historial y memoria sin romper aislamiento. | BAJO |
| **P1** | **Visual `BehaviorNarrator` opcional** para misiones GUI: capturar before/after, marcar la acción, pedir confirmación visual al LLM | Agent-S `bbon/behavior_narrator.py:25-75,130-170` | Verifier opcional `visual_diff` para tools con `verifier=async_visual`. Solo se activa si hay VLM disponible. | MEDIO (necesita VLM) |
| **P2** | **Best-of-N para acciones críticas** — generar 2-3 rollouts, elegir el mejor visualmente | Agent-S `comparative_judge.py:100-145` | Para tools `risk=CRITICAL`, ejecutar el plan 2 veces en paralelo (cuando es seguro idempotente) y comparar. Solo aplicable a tools idempotentes. | ALTO |
| **P2** | **Reflection agent** post-acción: revisar el historial antes de proponer la siguiente acción | Agent-S `agents/worker.py:115-160` | Inyectar prompt opcional "antes de actuar, revisa qué falló en la acción anterior y por qué" cuando el verifier de la última fue UNVERIFIED/FAILED. | BAJO |
| **P2** | **Checkpointing por turno** (snapshot del SessionState a SQLite) con `source ∈ {input,loop,update,fork}` | LangGraph `checkpoint/base/__init__.py:50` | Tras cada turno exitoso, persistir `SessionState` serializado. Comando CLI `carter rewind <n>` para volver a un punto. | MEDIO |
| **P2** | **Store separado del state** para hechos persistentes (preferencias, apps recientes, "remembered facts") distinto de la conversación | LangGraph `langgraph/store/base.py` | Nueva tabla `kv_store(namespace, key, value, updated_at)` en SQLite. API `store.put(ns, key, val)`, `store.query(ns, prefix)`. | BAJO |
| **P2** | **Topological planning** para misiones multi-paso con dependencias entre subtareas | OS-Copilot `friday_planner.py:45-90` | En `step_materialise`, retornar grafo de dependencias y ejecutar en orden topológico (permite paralelismo seguro). | MEDIO |
| **P2** | **`AdversaryInspector` (LLM second opinion)** opcional — un segundo modelo Ollama local revisa tool calls de alto riesgo | Goose `AdversaryInspector` con `~/.config/goose/adversary.md` | Plugin opcional: para `risk≥HIGH`, segunda llamada a un modelo distinto (más pequeño, rápido) que solo decide allow/deny + razón. | MEDIO |
| **P2** | **Workbench MCP** para registrar tools externas en caliente sin tocar `catalog.py` | AutoGen `McpWorkbench(StdioServerParams(...))` | Dispatch que delega a un servidor MCP local. Permite añadir tools de terceros sin modificar Carter. | MEDIO |
| **P2** | **Function tool por convención** (nombre + docstring auto-extraídos) para reducir boilerplate del catálogo | AutoGen function tools auto-wrapped | Decorador `@carter_tool` que genera `ToolSpec` desde la firma + docstring + type hints. Coexiste con specs explícitos. | BAJO |
| **P3** | Persistent learning courses (JSON por dominio) | OS-Copilot `self_learning.py:40-80` | Carter ya tiene memoria + request_patterns; añadir "courses" sería duplicación. Reevaluar si aparece un dominio recurrente. | n/a |
| **P3** | Pregel DAG (estado distribuido por canales) | LangGraph `pregel/_loop.py` | Sobre-ingeniería para single-user. La iteración imperativa actual es más simple y testeable. | n/a |
| **ANTI-PATRÓN documentado** | LLM call no implementado en framework "completo" | AutoGPT `forge_agent.py:195` (`"I cannot solve the task!"`) | Añadir test que verifique que `agent.respond()` siempre invoca al adapter (no stub). Carter ya lo hace; documentarlo en `WHAT_NOT_TO_COPY_FROM_COMPETITORS.md`. | n/a |
