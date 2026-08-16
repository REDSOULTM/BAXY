# COMPETITOR_GOOSE_DEEP_AUDIT.md
# Auditoría profunda de Goose (Block) — código real Rust
# Generado por: GitHub Copilot (Claude) — 2026-05-06
# Ubicación: `Extras/Competidores/goose-main/`

---

## ¿Por qué un deep audit de Goose?

Goose es el **único competidor con un sistema de policy pre-LLM superior al de Carter v3**. Su pipeline de 5 inspectores compositivos (Security, Egress, Adversary LLM, Permission, Repetition) y sus `ToolAnnotations` son los patrones más maduros del set. Si Carter quiere absorber UNA cosa de un competidor, este es el primer candidato.

---

## 1. Estructura

- Lenguaje: **Rust** (workspace cargo).
- Crates clave:
  - `crates/goose/` — núcleo del agente.
  - `crates/goose-mcp/` — extensiones MCP builtin.
  - `crates/goose-cli/`, `crates/goosed/` — UX (CLI + servidor local).
- App: Electron desktop frontend → habla con `goosed` local.

## 2. Loop principal

`Agent::reply()` en `crates/goose/src/agents/agent.rs:1028`.

```rust
pub async fn reply(
    &self,
    user_message: Message,
    session_config: SessionConfig,
    cancel_token: Option<CancellationToken>,
) -> Result<BoxStream<'static, Result<AgentEvent, Error>>>
```

Loop principal en `:1301`:

1. `if turns_taken > max_turns { break; }` — `max_turns = 1000` por defecto (`:1293`).
2. Prepara contexto (tools + system prompt).
3. `provider.stream(...)` (LLM completion en streaming).
4. Categoriza tool requests: frontend vs backend.
5. **Tool inspection** (ver §4).
6. Ejecuta tools aprobados vía `extension_manager.dispatch_tool_call(...)`.
7. Drena mensajes `ActionRequired` (ver §5).
8. Lógica de retry (`handle_retry_logic`, `:476`).

**Diferencia con Carter:** Carter tiene step budget configurable pero su loop es función imperativa Python; Goose enforce `max_turns` real en cada iteración del bucle.

## 3. Tool calling y extensiones

`dispatch_tool_call()` en `agent.rs:733`:

```rust
pub async fn dispatch_tool_call(
    &self,
    tool_call: CallToolRequestParams,
    request_id: String,
    cancellation_token: Option<CancellationToken>,
) -> (String, Result<ToolCallResult, ErrorData>)
```

Special tools: `PLATFORM_MANAGE_SCHEDULE_TOOL_NAME`, `FINAL_OUTPUT_TOOL_NAME`.

### Builtin extensions (MCP)

`crates/goose-mcp/src/lib.rs:55`:

```rust
pub static BUILTIN_EXTENSIONS: Lazy<HashMap<&'static str, SpawnServerFn>> = Lazy::new(|| {
    HashMap::from([
        builtin!(autovisualiser, AutoVisualiserRouter),
        builtin!(computercontroller, ComputerControllerServer),
        builtin!(memory, MemoryServer),
        builtin!(tutorial, TutorialServer),
    ])
});
```

Las extensiones son **MCP-native** (Model Context Protocol). Se cargan lazy y exponen tools dinámicamente.

## 4. **Pipeline de inspectores pre-LLM (LO MÁS IMPORTANTE)**

`agent.rs:1454`:

```rust
fn create_tool_inspection_manager(...) -> ToolInspectionManager {
    let mut tm = ToolInspectionManager::new();
    tm.add_inspector(Box::new(SecurityInspector::new()));
    tm.add_inspector(Box::new(EgressInspector::new()));
    tm.add_inspector(Box::new(AdversaryInspector::new(...)));
    tm.add_inspector(Box::new(PermissionInspector::new(...)));
    tm.add_inspector(Box::new(RepetitionInspector::new(...)));
    tm
}
```

**Orden = prioridad. Primer match decide.**

### 4.1 SecurityInspector (`security_inspector.rs`)

Pattern matching anti prompt-injection. Output: `RequireApproval` o `Allow`.

### 4.2 EgressInspector (`egress_inspector.rs:25`)

Regex sobre el contenido del tool call para extraer URLs, git SSH, S3, GCS. Mantiene allowlist/denylist. Si destino desconocido → `RequireApproval`.

### 4.3 AdversaryInspector

**Esta es la joya.** Una segunda LLM (Claude por defecto) revisa el tool call. Configurable vía `~/.config/goose/adversary.md` — el usuario describe qué quiere bloquear en lenguaje natural. Output: `RequireApproval` si la LLM detecta riesgo.

### 4.4 PermissionInspector

Lee grants en `~/.config/goose/permissions`. Permite que el usuario haya pre-aprobado tools específicas con scope (`AlwaysAllow`, `AllowOnce`, etc.).

### 4.5 RepetitionInspector

Detecta tool calls repetidas en bucle (mismo tool + mismos args N veces). Output: `RequireApproval` para romper loops.

### 4.6 Mode SmartApprove + ToolAnnotations

`agent.rs:1444`:

```rust
if goose_mode == GooseMode::SmartApprove {
    self.tool_inspection_manager.apply_tool_annotations(&tools);
}
```

Cada tool puede declarar `ToolAnnotations { read_only: bool, destructive: bool, idempotent: bool }`. Si `read_only=true`, SmartApprove salta la aprobación heavy.

## 5. ActionRequired bidireccional

`MessageContent::ActionRequired(ActionRequiredData)` en `conversation/message.rs`:

```rust
pub struct ActionRequiredData {
    pub id: String,
    pub action: String,
    pub user_data: Option<serde_json::Value>,
}
```

Permission types (`permission_confirmation.rs:5`):

```rust
pub enum Permission {
    AlwaysAllow,
    AllowOnce,
    Cancel,
    DenyOnce,
    AlwaysDeny,
}
```

`ToolConfirmationRouter` (oneshot channel): el frontend bloquea esperando `deliver()`. **El LLM puede pedir DATOS al usuario** (no solo "yes/no") usando `user_data` con un schema arbitrario JSON.

**Carter actualmente** modela follow-ups como pregunta libre + `pending_intent`. Adoptar `ActionRequired` tipado permite UI/CLI presentar input estructurado y ahorrar turnos.

## 6. Memoria y contexto

- Per-session: `Conversation` lista de `Message` (variantes `User`, `Assistant`, `ToolRequest`, `ToolResponse`, `ActionRequired`, `Thinking`).
- Compaction automática (`context_mgmt/mod.rs`): `check_if_compaction_needed()` antes de cada LLM call. Threshold default 0.75 del context window.
- Persistente: extensión `memory` (MCP builtin) con `memory_put`, `memory_get`, `memory_search`.

## 7. Tests

- `agent.rs`, `mcp_integration_test.rs`, `tool_inspection_manager_tests.rs`, `repetition_inspector_tests.rs`, `adversary_inspector_tests.rs`, `acp_*.rs`, `session_*.rs`, `compaction.rs`.
- Buena cobertura, especialmente del pipeline de inspectores.

## 8. Local-first

**Sí, puramente local** para decisión y dispatch. La inferencia LLM puede ser cloud (Anthropic, OpenAI) o local (Ollama). Soporte ACP (Auth Control Proxy) para OIDC opcional.

## 9. Lo mejor (real, citado)

1. Pipeline de inspectores composable y ordenado.
2. AdversaryInspector con LLM second-opinion configurable por archivo de texto.
3. ActionRequired bidireccional (LLM pide datos, no solo confirmación).
4. SmartApprove + ToolAnnotations para no hartar al usuario con tools read-only.
5. Compaction automática de contexto.
6. MCP-native desde el inicio.

## 10. Lo peor (real, citado)

1. Rust = barrera de entrada para contribuir.
2. Sin checkpointing/replay tipo LangGraph (conversación lineal).
3. Sin GUI automation propia (depende de extensiones).
4. Sin verifier de estado del sistema (solo RepetitionInspector contra bucles).

## 11. Qué portar a Carter (priorizado)

| # | Patrón Goose | Adaptación Carter | Prioridad |
|---|---|---|---|
| 1 | Pipeline de inspectores ordenados | Refactor de `security/policy.py` a lista componible | **P1** |
| 2 | `ToolAnnotations` (`read_only`, `destructive`, `idempotent`) | Añadir 3 booleans a `ToolSpec` en `catalog.py` | **P1** |
| 3 | `ActionRequired` bidireccional con schema | Nueva clase `PendingDataRequest` en `session_state.py` | **P1** |
| 4 | `AdversaryInspector` opcional | Plugin con segundo Ollama local solo para `risk≥HIGH` | **P2** |
| 5 | Compaction automática | Detectar 80% del context window y resumir turns viejos | **P1** (ya en BEST_IDEAS) |
| 6 | `SmartApprove` mode | Modo de Carter que salta verificación cuando `tool.read_only` | **P2** |
| 7 | MCP-native extensiones | Workbench MCP opcional (compartido con AutoGen idea) | **P2** |

## 12. Lo que NO portar

- Reescribir Carter en Rust. La elección de Python es correcta para un asistente extensible.
- Multi-thread / múltiples conversaciones simultáneas: Carter es single-user.
- Electron frontend: Carter prioriza CLI/servicio local.
