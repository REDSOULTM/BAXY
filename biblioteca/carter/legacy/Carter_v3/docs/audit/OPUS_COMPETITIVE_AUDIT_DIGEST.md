# OPUS_COMPETITIVE_AUDIT_DIGEST.md
# Resumen de auditoría competitiva — Sesión Claude Code (claude-sonnet-4-6)
# Fecha: 2026-05-06
# Fuente: Código real de 12 competidores + Carter v3 fuente

---

## VEREDICTO CONSOLIDADO

**`CARTER_ARCHITECTURE_GOOD_RUNTIME_WEAK`**

Carter v3 tiene la mejor arquitectura combinada de 12 competidores para el nicho
de asistente personal local en Windows. Cada competidor gana en UNA dimensión;
ninguno gana en TODAS las dimensiones que importan para Carter.

Fuente canónica del veredicto: `docs/competition/CLAUDE_COMPETITIVE_AUDIT_VERDICT.md`

---

## 1. Ventajas de Carter sobre TODOS los competidores

Estas ventajas son verificadas con código real, no inferidas:

| Ventaja | Evidencia | Competidores que no tienen esto |
|---|---|---|
| **Verifier system** (CONFIRMED/PARTIAL/UNVERIFIED/FAILED con causal baseline) | `tools/verifier.py`, 14 verifiers distintos | Mark, OpenClaw, AutoGPT, AutoGen, OS-Copilot, Open Interpreter, Goose, LangGraph |
| **Policy pre-LLM** (20+ patterns peligrosos bloqueados ANTES del LLM) | `security/policy.py` | Mark, la mayoría de competidores |
| **Zero hardcodes verificado por AST** (`hardcode_guard`) | `audit/hardcode_guard.py`, 58 archivos CLEAN | Todos los competidores (ninguno tiene AST scanner de hardcodes) |
| **Fuzzy resolver sin aliases** (resuelve "stean"→Steam sin tabla) | `fuzzy_resolver.py` | Mark (64 aliases), la mayoría |
| **Fake success guards** (8 guards estructurales post-reply) | `guards.py` | Todos los competidores |
| **Windows native CEF control** (AttachThreadInput + mouse_event para Steam/Discord/Spotify) | `tools/dispatch_app.py` | Todos los competidores |
| **Secret filter en memoria** (detecta contraseñas/tokens antes de guardar) | `memory/store.py:contains_secret` | Mark, la mayoría |
| **507 tests con ScriptedAdapter** | `Carter_v3/tests/` | Mark (0 tests), casi todos |
| **Local-first puro** (100% offline con Ollama) | `adapters/ollama_adapter.py` | Mark (cloud obligatorio), muchos |

---

## 2. Lo que Carter NO tiene vs competidores

| Gap | Competidor con la capacidad | Prioridad de cierre |
|---|---|---|
| **Browser automation** (Playwright, clicks en formularios, múltiples tabs) | Mark, OpenClaw, OpenHands | P1 |
| **Pipeline de inspectores pre-LLM componibles** | Goose (5 inspectores en Rust) | P1 |
| **Progress reporting durante misiones** | Mark (UI), OpenClaw (update_plan) | P0 (B5) |
| **Follow-up confirmaciones** ("Sí"/"OK" activa pending_intent) | Todos lo hacen bien | P0 (B2) |
| **SSRF protection en web_fetch** | OpenClaw | P1 |
| **Model failover automático** | OpenClaw | P1 |
| **Degradación automática por VRAM/RAM** | (falta en todos, pero ContextoCarter Valor 22 lo requiere) | P1 |
| **ToolAnnotations** (read_only/destructive/idempotent) | Goose | P1 |
| **ActionRequired bidireccional** (LLM pide datos tipados al usuario, no solo yes/no) | Goose | P1 |
| **Verificación visual (BBON)** (before/after screenshot comparison) | Agent-S (SOTA OSWorld 72.60%) | P1 (requiere VLM) |
| **Checkpointing/replay/fork** de sesión | LangGraph | P2 |
| **TerminationCondition componibles** | AutoGen | P1 |
| **Semantic memory search** (embeddings) | OpenClaw | P2 |

---

## 3. Audit de cada competidor — Puntos clave

### Mark XXXIX
- 100% Gemini cloud. Sin internet → inútil.
- 64 aliases hardcodeados en `_APP_ALIASES`. Anti-patrón directo.
- Sin verifier. "Done." es el resultado sin verificación.
- Sin test suite. Cero.
- Trademark "JARVIS" (Marvel/Disney) — problema legal.
- Sí tiene: voz, cámara cv2, Playwright browser, HUD PyQt6, progress visual.
- **Ratio calidad/riesgo: BAJO** (riesgo legal + sin tests + cloud obligatorio).

### OpenClaw
- TypeScript/Node.js, 30+ LLM providers.
- Docker sandbox por sesión (overhead inaceptable para single-user).
- Playwright browser nativo — la capacidad de browser más madura vista.
- Vector embeddings + "dreaming" para memoria — ingeniosa pero pesada.
- PTY support en terminal — interactividad real.
- Sin verifier de acciones.
- Sin Windows native app control.
- **Ratio calidad/riesgo: MEDIO-ALTO** (bueno para nicho multi-canal, no para PC personal).

### Goose (Block, Rust)
- Pipeline de 5 inspectores componibles — **el sistema pre-LLM más maduro del set**.
- ToolAnnotations struct con read_only/destructive/idempotent por tool.
- ActionRequired bidireccional — LLM puede pedir datos estructurados al usuario.
- SmartApprove mode — salta verificación cuando read_only=true.
- Compaction automática de contexto (threshold 0.75).
- Rust = barrera de contribución.
- Sin verifier de estado de OS (solo RepetitionInspector contra loops).
- Sin Windows native app control.
- **Ratio calidad/riesgo: ALTO** — las ideas más portables a Carter (ver P1 tabla).

### Agent-S
- SOTA OSWorld 72.60% en GUI automation.
- BehaviorNarrator + ComparativeJudge: before/after screenshot + LLM visual verification.
- VLM obligatorio (VRAM) — incompatible con hardware limitado.
- ActionSpace jerárquico (SubProcess → Action).
- Sin verifier de estado lógico (solo visual).
- **Ratio calidad/riesgo: MEDIO** — las ideas visuales son portables como verifier opcional.

### AutoGPT (classic Forge)
- `forge_agent.py:195`: stub literal `'I cannot solve the task!'`. No implementa el loop LLM.
- Anti-patrón de anti-patrones. Útil como "qué NO hacer".
- Sin step budget real. Loop infinito potencial.
- **Ratio calidad/riesgo: MUY BAJO** — anti-patrón documentado.

### AutoGen
- Framework multi-agent (diferente nicho).
- TerminationCondition componibles (max_messages + token_budget + timeout + handoff).
- Round-robin groupchat — útil para orquestación, no para PC personal.
- **Ideas portables a Carter:** TerminationCondition = P1.

### LangGraph
- Framework de grafo de estado (diferente nicho).
- Checkpointing SQLite/Postgres por turno con source = {input, loop, update, fork}.
- KV Store separado del state para hechos persistentes.
- Sin agente específico para PC.
- **Ideas portables a Carter:** Checkpointing P2, KV store P2.

### Open Interpreter
- Loop de código Python + exec local. Sin verifier. Sin guards.
- Execution sandbox limitado. exec() en producción.
- Sin policy pre-LLM.
- **Ratio calidad/riesgo: BAJO** (exec sin sandbox = superficie de ataque).

### OpenHands
- Agent loop oculto en paquete externo no auditable.
- Sandbox Docker obligatorio.
- Good browser automation + CodeAct paradigm.
- **Ideas portables a Carter:** Ninguna prioritaria. Sandbox Docker es P2 opcional.

### OS-Copilot / FRIDAY
- Planner topológico con dependencias entre subtareas.
- Más investigación académica que producto.
- **Ideas portables a Carter:** topological planning P2.

### Claude Computer Use (Anthropic)
- VLM nativo de Anthropic. Gana en GUI visual.
- Carter gana en privacidad, offline, memory, policy.
- **Ideas portables a Carter:** Nada nuevo — Carter ya tiene Perception ladder con VLM como último recurso.

### Windows Copilot (Microsoft)
- Integración nativa del OS (Start, Search, System settings).
- Cloud obligatorio. Sin privacidad real. Sin extensibilidad open.
- **Ideas portables a Carter:** Ninguna (cloud, closed).

---

## 4. Top prioridades para implementación (post P0 blockers)

### P0 (bloqueadores activos antes de cualquier P1):
1. Fix B2 — confirmaciones "Sí"/"OK"/"YES" → pending_intent
2. Fix B3 — fake_success_guard cubre texto completo, no solo inicio
3. Fix B4 — notify_toast → SKIPPED (no CONFIRMED falso)
4. Fix B6 — system prompt no ejecuta al preguntar capacidad
5. Fix B5 — progress reporting en misiones compuestas
6. Validación live con LLM real (proceso, no código)

### P1 (enriquecimiento arquitectónico post P0):
1. Pipeline de inspectores pre-LLM componibles (de Goose)
2. ToolAnnotations en ToolSpec (de Goose)
3. ActionRequired bidireccional / PendingDataRequest (de Goose)
4. SSRF protection en web_fetch
5. Browser Playwright básico
6. TerminationCondition componibles (de AutoGen)
7. Error taxonomy estructural (retry/skip/abort)
8. VRAM/RAM degradation automática
9. Model failover entre adapters
10. Context compaction cuando 80% del context window

---

## 5. Lo que NO copiar (con justificación)

Ver tabla completa en `docs/competition/WHAT_NOT_TO_COPY_FROM_COMPETITORS.md`.

Top 5 más importantes:
1. **Cloud LLM obligatorio** (Mark) — rompe Valor 1 (local-first)
2. **Sin verifier = fake success** (Mark, AutoGPT, mayoría) — rompe confianza
3. **64-entry app aliases** (Mark) — viola Valor 6 y 7 (no hardcodes)
4. **exec() sin sandbox** (Open Interpreter) — superficie de ataque directa
5. **Identidad de marca ajena** (Mark "JARVIS") — problema legal

---

## 6. Fuentes de este digest

- `docs/competition/CLAUDE_COMPETITIVE_AUDIT_VERDICT.md` — veredicto base + adendum
- `docs/competition/COMPETITOR_GOOSE_DEEP_AUDIT.md` — audit Rust real Goose
- `docs/competition/COMPETITOR_AGENTS_DEEP_AUDIT.md` — audit 8 agentes
- `docs/competition/COMPETITOR_MARK_DEEP_AUDIT.md` — audit Mark XXXIX
- `docs/competition/COMPETITOR_OPENCLAW_DEEP_AUDIT.md` — audit OpenClaw
- `docs/planning/BEST_IDEAS_TO_PORT_TO_CARTER.md` — tabla P0/P1/P2/P3 completa
- `docs/competition/WHAT_NOT_TO_COPY_FROM_COMPETITORS.md` — anti-patrones
- Código fuente local en `Extras/Competidores/` — todos los repositorios descargados

---

*Generado por Claude Code (claude-sonnet-4-6) — Auditoría de código real, sin ejecución — 2026-05-06*
