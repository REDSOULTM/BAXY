# Análisis de competencia — qué robarles para ganarles (2026-05-29)

Análisis de 10 competidores en `Carter OS AI/Extras/Competidores` (lectura de su
código + el nuestro, vía 8 sub-agentes). Síntesis filtrada por nuestras
restricciones DURAS (4GB VRAM, OSS, local, voz, multilingüe, el-LLM-decide).

## El panorama: NINGUNO es nuestro rival directo

| Competidor | Qué es | Modelo/recursos |
|---|---|---|
| Agent-S | computer-use/GUI (OSWorld 72%) | GPT-4V / UI-TARS, **cloud** |
| OS-Copilot | automatización SO + self-learning | GPT, **cloud**, hardcoded chino |
| Open Interpreter | ejecuta código en lenguaje natural | Claude/LiteLLM (soporta local) |
| OpenHands | agente de software enterprise | Anthropic/OpenAI, **cloud/Docker** |
| Goose | agente local en **Rust** + MCP | 50+ providers, llama-cpp-2 nativo |
| **Mark-XXXIX** | **JARSIV de voz** (el más parecido) | **Gemini 2.5 LiveAPI, cloud/PAGO** |
| openclaw | gateway multi-canal (WhatsApp/etc) | TS, agnóstico, **infra producción** |
| AutoGen | multi-agente conversacional | framework, N modelos grandes |
| LangGraph | state-machine/DAG de agentes | framework |
| AutoGPT | loop autónomo + memoria episódica | framework |

**Conclusión:** todos son cloud / modelos grandes / frameworks de orquestación.
**NINGUNO corre en 4GB local con voz.** El único voz-personal (Mark-XXXIX) depende
de Gemini LiveAPI **paga**. → Nuestro nicho (local, 4GB, voz, privado, gratis,
multilingüe, honesto) es **único**. No tenemos que ganarles en capacidad bruta de
GPT-4; tenemos que ser el MEJOR asistente local-privado-de-voz, que ya somos.

## Nuestro MOAT (lo que YA ganamos — no regalarlo)

- **4GB local + OSS gratis** (ellos: cloud/pago/grande). Privacidad + costo + offline.
- **Voz-first multilingüe** por embeddings (OS-Copilot está hardcoded a chino; el resto es text/dev-agent o inglés-céntrico).
- **Honestidad estructural**: verify tristate por ESTADO DEL SO (no LLM-judge que alucina como OS-Copilot/Mark). "No miente".
- **Prefix-cache** (el win de esta sesión: ~1s/acción).
- **Ya tenemos** (varios agentes lo ignoraron): compaction CON summarization LLM de la mitad vieja (`agent.py` _maybe_summarize, acota el prompt ~7-12k), core_tools_pareto adaptativo, lean prompts, command_splitter, computer-use cascada UIA→OCR→visión + verify dHash, mission_checkpoint.

## Lo que VALE robar (priorizado por ROI × encaje en 4GB; escéptico)

### #1 — Recuperación por TIPO de error (replan / amend / skip)  ⭐ MAYOR ROI
**Quién:** OS-Copilot (`friday_agent.py:self_refining` → repair/replan según `judge_tool`),
Mark-XXXIX (`agent/error_handler.py` → `ErrorDecision.RETRY|SKIP|ABORT|FIX`), AutoGPT
(memoria episódica de errores inyectada al prompt).
**Qué:** hoy nuestro verify es tristate honesto (True/False/None) pero al fallar
**dropeamos** o devolvemos "no pude". Ellos CLASIFICAN el error y ACTÚAN:
missing-precondition→replan, param-mismatch→amend, transient→skip.
**Por qué encaja:** ataca DIRECTO el flakeo de app-open/tool que medí esta sesión.
Es una capa GENÉRICA (el LLM decide la recuperación), NO un macro-por-intención
(respeta `feedback_computer_use_universal`). Extra-LLM SOLO al fallar → gateado, no
infla la latencia del caso feliz.
**Cómo:** extender `safety_pkg/verify_core.py::VerifierOutcome` con `error_type`;
en `_finalize_turn`, si `confirmed==False`: replan (re-elegir tools) / amend (ajustar
args) / skip. Inyectar el error al prompt del re-intento (AutoGPT-style).
**NO adoptar:** el code-gen dinámico de OS-Copilot (prohibitivo en 4GB).

### #2 — Tool-picking guiado por MEMORIA (reuso de experiencia)  ⭐ ALTO ROI
**Quién:** OS-Copilot (self-learning de skills en vector DB), Mark-XXXIX (memory_manager),
AutoGPT (EpisodicActionHistory).
**Qué:** capturar `(intent → tool_sequence → outcome)` en éxito y REUSARLO en
intents similares → repeticiones más rápidas y fiables. Ya tenemos `memory_pkg/` +
`experience.py`; falta cablearlo al `planner`.
**Por qué encaja:** lookup por embeddings (ya usamos MiniLM multilingüe), 0 extra-LLM
si hay hit. Debe ser por EMBEDDINGS, no keyword-lists (CLAUDE.md). Es guía, no hardcode.
**Cómo:** en `routing/planner.py::select_tool_names`, consultar memoria de patrones
exitosos antes del router; feedback loop en `_finalize_turn` (guardar el patrón al verificar OK).
**NO adoptar:** Chroma/LanceDB/OpenAI-embeddings (cloud/peso). En-memory dict + MiniLM.

### #3 — Tool de EJECUCIÓN DE CÓDIGO controlada (capacidad universal)  ⭐ ALTO, con gate de seguridad
**Quién:** Open Interpreter (`core/respond.py` loop + Jupyter stateful), OS-Copilot
(genera Python/shell), Mark-XXXIX (`dev_agent`).
**Qué:** una tool `python`/`analyze` sandboxeada (pandas/numpy, SIN red ni filesystem
por defecto) da capacidad universal de datos/cómputo SIN screenshots de GUI. "tabulá
ese CSV" → ejecuta en ~0.8s en vez de 3s de visión.
**Por qué encaja:** 0 VRAM (corre en CPU), local, feedback directo al LLM. Pero la
**SEGURIDAD es el gate**: AST-whitelist se bypassea fácil → usar RestrictedPython o
sandbox real + timeout 20s + sin red. Empezar read-only (cálculo/datos), no file-ops.
**Riesgo:** alto si se hace mal (exfiltración, DoS). Diseñar con cuidado o no hacer.

### #4 — Cliente MCP (extensibilidad + ecosistema)  — estratégico, esfuerzo alto
**Quién:** Goose (`rmcp`, 70+ servidores), openclaw (plugin-SDK), OS-Copilot.
**Qué:** adoptar MCP como CLIENTE nos abre 70+ servidores existentes (filesystem, git,
APIs, etc.) sin escribir cada tool. Futuro-proof + interoperable.
**Por qué con cautela:** más tools = tool-calling más difícil para el 4B (nuestro
cuello de botella medido). Mitigado porque el router ya manda un SUBSET por turno.
Refactor grande (`domain_tools/`→extensiones). Estratégico, no inmediato.
**NO confundir:** NO somos un gateway multi-canal (openclaw) ni multi-agente (AutoGen);
eso no entra en 4GB ni es nuestro producto.

### #5 — UX de voz: streaming de progreso de tool + mejor TTS  — ROI medio (voz)
**Quién:** openclaw (eventos `tool` en vivo), Mark-XXXIX (Gemini LiveAPI ~100ms +
voz Charon natural; silencio post-tool-lento), Open Interpreter (streaming).
**Qué:** (a) avisar "buscando en web…" mientras una tool lenta corre → percepción de
rapidez. (b) Mark nos gana en latencia de voz (~100ms) y naturalidad (Charon) — pero
es **Gemini cloud PAGO, no adoptable**. La lección: mejorar voz local (mejor modelo
Piper/VITS) + el **streaming token→TTS que YA construí** (gated, esta sesión).
**Por qué encaja:** el streaming-info ya está listo (opt-in); el progreso-de-tool es
plomería en el runner.

## Lo que NO robar (viola restricciones)
- Multi-agente con N modelos grandes (AutoGen) — no entra en 4GB.
- Cloud APIs: Gemini LiveAPI, GPT-4V, Chroma+OpenAI-emb, LanceDB remoto.
- Code-gen dinámico full por turno (OS-Copilot) — demasiados LLM-calls.
- Arquitectura microservicios/async-total (OpenHands thin-proxy) — overkill local.
- Reescribir en Rust (Goose) — perdemos velocidad de dev; llama-server ya nos sirve.

## Roadmap priorizado (cuando se decida)
1. **#1 Error-type recovery** — el quick-win de fiabilidad (ataca el flakeo medido). Gateado.
2. **#2 Memory-guided tool-picking** — latencia + fiabilidad en repeticiones. Reusa MiniLM.
3. **#5b** prender el **streaming-info TTS** (ya construido) + progreso-de-tool en voz.
4. **#3 code-exec sandbox** — gran capacidad, PERO diseñar la seguridad primero.
5. **#4 MCP** — estratégico, sprint dedicado, medir impacto en tool-calling del 4B.

## Veredicto
No perdemos contra nadie en NUESTRO terreno (local/4GB/voz/privado/gratis/honesto) —
somos los únicos ahí. Las mejores IDEAS de arquitectura (recuperación de errores,
memoria-experiencia, code-exec, MCP) son adoptables DENTRO del moat para cerrar la
brecha de capacidad sin romper las restricciones. El camino a "ganarles a todos" no
es out-GPT-4 en la nube; es ser el mejor asistente que corre en la máquina del usuario.
