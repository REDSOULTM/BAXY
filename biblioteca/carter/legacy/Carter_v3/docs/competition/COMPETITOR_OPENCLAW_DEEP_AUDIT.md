# COMPETITOR_OPENCLAW_DEEP_AUDIT.md
# OpenClaw — Auditoría Profunda
# Generado por: Claude Code (claude-sonnet-4-6) — 2026-05-06
# FUENTE: Código leído directamente desde legacy/Referencia OpenClaw/openclaw-main/

---

## 1. Arquitectura general

OpenClaw es un **orquestador de agentes multi-canal** escrito en TypeScript/Node.js. Es fundamentalmente distinto a Carter: no está diseñado para controlar un PC Windows, sino para ser un asistente de mensajería multi-plataforma que puede ejecutar código y controlar browsers.

```
Canal (WhatsApp/Discord/Telegram/etc.)
  ↓
Gateway daemon (Node.js, local)
  ↓
Agent session
  ↓
pi-embedded-runner (loop de tool calls)
  ↓
Tool handlers (exec, read, write, web, browser, canvas, nodes, etc.)
  ↓
Tool results → back to LLM → next tool call o final reply
  ↓
Respuesta → canal original
```

## 2. Modelo local / cloud

- **Provider-agnostic**: 30+ providers via plugins. Default OpenAI `gpt-5.4`.
- **Local disponible**: Ollama y LM Studio como extensiones. Completamente funcional sin cloud si se usa modelo local.
- **Model failover**: Si un modelo falla, rota a otro auth profile automáticamente.
- **Sin if-model-name**: Provider adapter pattern limpio.

## 3. Requisitos de VRAM

- OpenClaw en sí no ejecuta modelos — delega al provider (Ollama, LM Studio, vLLM, etc.)
- Con Ollama local: VRAM según el modelo elegido (puede ser tan bajo como CPU-only)
- Sin VRAM mínimo requerido por el framework mismo

## 4. Tool calling

- Definición via TypeBox JSON schemas (OpenAI/Anthropic compatible)
- LLM retorna JSON tool calls → handler registrado ejecuta → result devuelto → LLM loop
- Tool policy: allowlist/denylist per-session, per-agent, per-channel
- Subagent sandboxing: Docker containers para sesiones no-main
- **No genera código Python/JS libre** — todo es tool call estructurado con schema fijo

## 5. Computer control

- **Canvas**: Web UI companion. Acciones: navigate, eval (JS injection), snapshot.
- **Browser tool**: Playwright Chromium en Docker sandbox. Full web automation.
- **Nodes tool**: iOS/Android camera, screen record, location, notifications, device status.
- **exec tool**: Bash shell commands en el host. Puede invocar cualquier programa via CLI.
- **SIN control nativo Windows**: No hay pyautogui, no hay Win32 API, no hay mouse_event, no hay UIA.

## 6. Screen observation

- Canvas snapshot: screenshot de la web UI companion (no del escritorio)
- Browser tool screenshot: de la página web en el browser Playwright
- Nodes camera_snap: foto desde cámara iOS/Android
- No hay screenshot del escritorio Windows
- No hay OCR del desktop
- No hay UIA/accessibility tree del desktop

## 7. GUI automation

- Solo via browser (Playwright) para webs
- Solo via Canvas para web UI companion
- Solo via nodes para mobile
- **Zero GUI automation nativa de Windows**

## 8. Memory / context

- Plugin-based memory backend
- Vector embeddings locales (disk)
- "Dreaming": consolidación background de memories
- Multimodal memory (image embeddings)
- Citations mode: mostra fuentes de memory en respuestas
- Memory inyectada como `memory.md` en system prompt

## 9. Planning

- `update_plan` tool: el agente puede llamar esta tool para actualizar su plan visible
- Subagent spawning: tareas complejas pueden delegarse a subagentes con su propio contexto
- Sin planner separado — el LLM es el planner nativo via tool calls

## 10. Error recovery

- Context compaction automática (summarization) cuando overflow de contexto
- Tool call errors devueltos como tool results → LLM decide qué hacer
- Model failover automático entre auth profiles
- Docker sandbox: crashes de herramientas no afectan el daemon principal

## 11. Safety

**OpenClaw tiene el sistema de seguridad más sofisticado de los competidores vistos:**

- `openclaw doctor`: audit completo de configuración de seguridad
- Docker sandboxing por sesión para agentes no-main
- Tool policy pipeline: allowlist/denylist granular
- SSRF protection (bloquea fetch a IPs privadas)
- Path policy: no reads/writes fuera del workspace
- Exec approval via push iOS notification para comandos peligrosos
- DM pairing: desconocidos reciben un código, no respuesta
- Gateway auth: Bearer token, scopes por operator
- Owner-only tools: herramientas que solo el dueño puede usar

## 12. Testing

- vitest para unit tests TypeScript
- pytest para skills tests Python
- Docker integration tests
- E2E tests
- Test coverage extenso

## 13. Extensibilidad

- Plugin SDK completo (`packages/plugin-sdk/`)
- ClawHub registry para plugins de la comunidad
- Extension API para providers, channels, tools, memory backends
- MCP (Model Context Protocol) via mcporter bridge
- ACP (Agent Control Protocol) para comunicación entre agentes

---

## Tabla comparativa OpenClaw vs Carter

| Área | OpenClaw | Carter v3 | Ganador | Qué tomar | Qué evitar |
|---|---|---|---|---|---|
| Local-first | SÍ (con Ollama) | SÍ | **Empate** | Plugin pattern para providers | Requerir Docker por defecto |
| Privacidad | Buena, pero canal-based (datos van a plataformas) | Excelente (local solo) | **Carter** | Nada | Canales de mensajería que envían datos |
| Tool calling | Schemas estáticos, seguro, sandboxed | 32 tools declarativas con risk levels | **OpenClaw (seguridad de sandbox)** | Docker sandbox para herramientas peligrosas | Schemas TypeBox (ecosistema ajeno para Python) |
| Seguridad/policy | openclaw doctor, SSRF, path policy, exec approval | PolicyEngine + 8 guards + secret filter | **OpenClaw (más completo)** | SSRF protection idea, exec approval para HIGH risk, path policy | Docker dependency (no necesario para single-user) |
| Verifier/no fake success | Sin verifier explícito por tool | 14 verifiers con causal baseline | **Carter** | Nada | Sin verifier |
| Memoria | Vector embeddings, dreaming, multimodal | SQLite, secret filter, dedup | **OpenClaw (más sofisticado)** | Vector embeddings para recall semántico, dreaming concept | Dependencia de infraestructura pesada |
| App control Windows | No existe | AttachThreadInput + UIA + fuzzy resolver | **Carter** | Nada | Nada de OpenClaw |
| Browser/web | Playwright (Docker), excelente | Sin browser automation real | **OpenClaw** | Playwright integration, SSRF protection | Docker mandatory |
| Filesystem | Read/write/edit/apply_patch | 5 filesystem tools con ownership guard | **Empate** (diferentes fortalezas) | apply_patch concept (diff-based edits) | Nada |
| Terminal | exec con PTY, process management | terminal_run_command básico | **OpenClaw** | PTY support, long-running process management | exec sin policy (Carter tiene mejor policy) |
| Multi-step planning | subagents, update_plan tool, depth limits | step_budget=6, fallback chains | **OpenClaw (multi-agent)** | depth limits para subagentes, update_plan visible | Multi-agent complejidad para single-user app |
| Progress reporting | update_plan visible, session history | Sin progress en loop de steps | **OpenClaw** | update_plan pattern (Carter análogo) | Overhead de multi-session para turns simples |
| Recovery | Context compaction, model failover | 1 retry para app_open | **OpenClaw** | Model failover, context compaction | Docker dependency |
| Latencia | Depende del provider, no optimizado para local | Diseñado para Ollama local | **Carter (en hardware limitado)** | Nada | Asumir cloud de baja latencia |
| Model flexibility | 30+ providers via plugins | 4 adapters (ollama, openai-compat, openai-api, scripted) | **OpenClaw** | Plugin pattern para más adapters | Complejidad innecesaria para single-user |
| Hardware adaptation | Sin VRAM management propio | ModelSelector con VRAM 85% rule | **Carter** | Nada | |
| Test coverage | vitest + pytest + E2E + Docker | 490 tests (scripted only) | **OpenClaw** | E2E tests con LLM real | Docker dependency para CI |
| UX | Multi-canal, TUI, web app | CLI solo | **OpenClaw (más canales)** | TUI concept | 25+ canal overhead para PC assistant |
| Code simplicity | Masivo (700+ archivos) | Compacto | **Carter** | Nada | Complejidad de gateway daemon |
| Extensibility | Plugin SDK, ClawHub, ACP | No hay plugin system | **OpenClaw** | Plugin slots concept | Full plugin marketplace |
| Offline use | SÍ con Ollama | SÍ con Ollama | **Empate** | | |
| Readiness for Jarvis-like | No orientado a desktop personal | Diseñado exactamente para esto | **Carter** | Nada | Multi-canal no es Jarvis |

---

## Respuestas a preguntas clave

- ¿OpenClaw puede usar modelo local? **SÍ** — Ollama extension disponible.
- ¿Qué modelos soporta? **30+ providers** via plugins. Cualquier modelo que Ollama soporte localmente.
- ¿Cuánta VRAM necesita? **La que requiera el modelo elegido.** El framework mismo no consume GPU.
- ¿Tiene mejor GUI control que Carter? **NO** — OpenClaw no puede controlar apps de escritorio Windows.
- ¿Tiene mejor planner? **Diferente** — multi-agent con subagentes vs step_budget. Para PC personal, Carter es más directo.
- ¿Tiene mejor observation loop? **NO para desktop** — SÍ para web (Playwright) y mobile (nodes).
- ¿Tiene mejor recovery? **SÍ** — model failover y context compaction son superiores.
- ¿Es más seguro o menos seguro? **Más completo en seguridad de red/canal** — SSRF, sandbox Docker, exec approval. Pero sin verifier por tool como Carter.
- ¿Depende de cloud? **No necesariamente** — Ollama local es primera opción posible.
- ¿Qué ideas convienen para Carter?
  1. SSRF protection en web_fetch
  2. Path policy (Carter ya tiene algo similar con OwnedPath)
  3. Exec approval via notificación para comandos HIGH risk
  4. Context compaction cuando el contexto overflow
  5. PTY support para terminal_run_command
  6. apply_patch tool para edición de archivos
  7. Model failover automático entre adapters disponibles
  8. Plugin slots para memory backend y LLM provider
