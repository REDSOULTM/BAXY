# Backlog — qué adoptar de los competidores (2026-05-29)

Derivado de `ANALISIS_COMPETENCIA.md` (10 competidores). Filtrado por restricciones
DURAS: 4GB VRAM, OSS/gratis, local, voz, multilingüe, **el LLM decide** (no
hardcodes/macros-por-intención), **no miente** (verify estructural). Cada ítem trae
gate de validación. Método: medir → implementar gateado → validar en vivo → flip.

Leyenda ROI/Esfuerzo/Riesgo: A(alto)/M(medio)/B(bajo).

## ESTADO (actualizado 2026-05-29)
- ✅ **B1** error-type recovery — GATED `GEMMA4_ERROR_RECOVERY`, 22 tests, commit `a3aef18`.
- ✅ **B2** memory-guided tool-picking — GATED `GEMMA4_MEMORY_TOOLS`, 10 tests, commit `aa7d5ae`.
- ✅ **B7** web fallback DDG→Bing — GATED `GEMMA4_WEB_FALLBACK`, 7 tests, commit `e2c248e`.
- ⏸️ **B3** (streaming voz) — BLOQUEADO: B3a (flip del streaming-info ya construido) necesita validación de voz (RED jugando, GPU ocupada); B3b ("buscando…" hablado) = respuesta enlatada por idioma → viola la regla "nada enlatado" → hacerlo como **earcon no-verbal**, que también necesita validación de voz.
- 🔎 **B8** (reminders) — HALLAZGO: el backend Task Scheduler YA EXISTE (`domain_tools/notifications.py`, `windows_scheduled_tasks`); el tool `reminder` (ops_tools) es SOLO state (no dispara). Gap = cablear `reminder`→notifications + validar disparo (tiempo/reinicio). Chunk, no quick-win.
- ⬜ **B5/B6/B4/B9** — pendientes, cada uno esfuerzo DEDICADO: B5 refactor de guards de confirmación; B6 unificar file-processor; B4 code-exec sandbox (gate de SEGURIDAD primero); B9 cliente MCP (refactor grande, medir impacto en tool-calling del 4B).

**Los 3 gated (B1/B2/B7) NO cambian nada con default-off.** Validación pendiente en
**una pasada batch en box FRESCA + sin gaming**: flipear B1/B2/B3a/B7 tras validar
en vivo (el efecto del 4B es no-determinista). Los quick-wins limpios están hechos;
B3 espera tu voz; B8/B5/B6/B4/B9 son esfuerzos dedicados (no se grindean sin validar).

---

## TIER 1 — Quick wins (fiabilidad/latencia, encajan, hacer primero)

### B1 · Recuperación por TIPO de error (replan / amend / skip)  ROI:A Esf:M Riesgo:B
- **De:** OS-Copilot (`friday_agent.py:self_refining` → repair/replan según `judge_tool`),
  Mark-XXXIX (`agent/error_handler.py:ErrorDecision.RETRY|SKIP|ABORT|FIX`), AutoGPT (memoria episódica de error).
- **Qué:** hoy al fallar una tool dropeamos o decimos "no pude". Clasificar el error y
  ACTUAR: missing-precondition→replan (re-elegir tools), param-mismatch→amend (ajustar args),
  transient/timeout→skip. Inyectar el error al prompt del re-intento.
- **Ataca:** el flakeo de tool/app-open MEDIDO esta sesión (events=0 intermitente).
- **Cómo:** extender `safety_pkg/verify_core.py::VerifierOutcome` con `error_type`; en
  `agent_core/agent.py::_finalize_turn` decidir la acción; verifiers de domain_tools devuelven `error_type`.
- **Encaje:** capa GENÉRICA (el LLM decide la recuperación), NO macro-por-intención. Extra-LLM
  SOLO al fallar → gateado (`GEMMA4_ERROR_RECOVERY`), no toca el caso feliz. Respeta "no miente".
- **Gate:** medir tasa de éxito de tool-call con/sin recovery en un set de comandos que hoy fallan;
  no debe agregar runaways (cuidado con el loop — máx 1 recovery/turno, como el forced_tool_retry_done).

### B2 · Tool-picking guiado por MEMORIA (reuso de experiencia)  ROI:A Esf:M Riesgo:B
- **De:** OS-Copilot (self-learning de skills), Mark-XXXIX (`memory/memory_manager.py`), AutoGPT (EpisodicActionHistory).
- **Qué:** capturar `(intent → tool_sequence → outcome)` en éxito; reusar en intents similares →
  repeticiones más rápidas/fiables (ej. "abrí Spotify" día 2 saltea el system_check que día 1 no hizo falta).
- **Cómo:** `routing/planner.py::select_tool_names` consulta memoria de patrones antes del router;
  feedback en `_finalize_turn` (guardar patrón al verificar OK). Reusar `memory_pkg/` + `experience.py`.
- **Encaje:** lookup por EMBEDDINGS (MiniLM multilingüe que ya usamos), no keyword-lists. 0 extra-LLM si hit.
  En-memory dict, NO Chroma/LanceDB (cloud/peso).
- **Gate:** medir latencia + aciertos de tool en repeticiones; no debe degradar el primer intento.

### B3a · Prender el streaming-info TTS (YA construido, gated)  ROI:M Esf:B Riesgo:B
- **De:** Open Interpreter / openclaw (streaming), lección de Mark-XXXIX (voz percibida).
- **Qué:** ya construí y validé `GEMMA4_STREAM_TTS` (info-turns, truthful, demote-on-tool). Falta decidir flip.
- **Cómo:** `agent_core/agent.py` (ya está). Validar variantes de fraseo en vivo → flip default.
- **Gate:** ya validado (0 violaciones de veracidad); falta el OK de RED + box fresca.

### B3b · Streaming de PROGRESO de tool en voz ("buscando en web…")  ROI:M Esf:M Riesgo:B
- **De:** openclaw (eventos `tool` en vivo, `agent-loop.md`), Mark-XXXIX (silencio post-tool-lento).
- **Qué:** mientras una tool lenta (web/visión) corre, decir "buscando…" → percepción de rapidez.
- **Cómo:** en `agent_core/agent_dispatch.py` emitir eventos de progreso al runner/VOICE antes de tools lentas.
- **Encaje:** voz-first; bajo riesgo (sólo feedback). No debe hablar sobre la respuesta final.
- **Gate:** que no pise el TTS de la respuesta; medir percepción en 3-4 acciones lentas.

---

## TIER 2 — Capacidad real (más esfuerzo/riesgo)

### B4 · Tool de EJECUCIÓN DE CÓDIGO sandboxeada (pandas/numpy)  ROI:A Esf:A Riesgo:A
- **De:** Open Interpreter (`core/respond.py` loop + Jupyter stateful), OS-Copilot (genera Python), Mark-XXXIX (`dev_agent`).
- **Qué:** tool `python`/`analyze` para cómputo/datos SIN screenshots ("tabulá ese CSV" → ~0.8s vs 3s de visión).
- **Cómo:** nueva tool en `tools_pkg/`; sandbox real (RestrictedPython o subproceso aislado), timeout 20s,
  SIN red ni filesystem por defecto, whitelist de libs. Empezar read-only (cálculo), no file-ops.
- **Encaje:** 0 VRAM (CPU), local. **La SEGURIDAD es el gate** (AST-whitelist se bypassea → sandbox real).
- **Gate:** suite de inputs maliciosos (exfiltración, DoS `while True`, `__import__`, `open(/etc/passwd)`)
  → 0 escapes. Si no podemos garantizar el sandbox, NO hacer.

### B5 · Política de confirmación estructurada (ConfirmRisky/Always/Never)  ROI:M Esf:B Riesgo:B
- **De:** OpenHands (`ConfirmationPolicy`: ConfirmRisky/AlwaysConfirm/NeverConfirm + LLMSecurityAnalyzer),
  openclaw (ACP / `before_tool_call`).
- **Qué:** formalizar el guard de acciones irreversibles (enviar WhatsApp/email, borrar, comprar) como
  política (hoy es ad-hoc en guards). Confianza por tool (auto-aprobar tools seguras frecuentes).
- **Cómo:** enum en `agent_core/agent_guards.py`; clasificar destructive vs safe; opt-in auto-approve.
- **Encaje:** refina lo que ya tenemos (user-activity guard, password handoff). Refactor, 0 cloud.
- **Gate:** que NUNCA auto-apruebe lo irreversible sin confirmación; mantener el handoff de password.

### B6 · Tool file-processor versátil (PDF/CSV/imagen/audio/código)  ROI:M Esf:M Riesgo:B
- **De:** Mark-XXXIX (`actions/file_processor.py`, drag-drop + análisis inmediato).
- **Qué:** una tool/UX para "analizá este archivo" (10+ tipos) → vision/parse + respuesta. UX fuerte.
- **Cómo:** unificar/extender `filesystem`/`office`/vision en una entrada coherente; drag-drop en la UI.
- **Encaje:** local; visión gateada para imágenes (ya la tenemos). Revisar qué ya cubre office/filesystem.
- **Gate:** que no rompa el budget de visión (≤2 calls) ni la VRAM en 4GB.

### B7 · Web search con fallback dual (robustez)  ROI:M Esf:B Riesgo:B
- **De:** Mark-XXXIX (`actions/web_search.py`: motor primario + DuckDuckGo fallback).
- **Qué:** si el buscador primario falla/timeout → fallback (DDG) en vez de quedar en blanco.
- **Cómo:** en la tool `web` actual, agregar fallback. (Ojo: relacionado con el "webea preguntas de
  conocimiento" que medí — separado: ESTO es robustez del search, no cuándo usarlo.)
- **Encaje:** OSS, sin API paga. Bajo riesgo.
- **Gate:** simular fallo del primario → DDG responde; medir latencia del fallback.

### B8 · Reminders cross-OS confiables  ROI:M Esf:B Riesgo:B
- **De:** Mark-XXXIX (`actions/reminder.py`: Windows Task Scheduler XML / launchd / systemd).
- **Qué:** recordatorios que sobreviven reinicios vía el scheduler del SO. **Verificar si ya lo cubrimos**
  (tenemos reminder en ops_tools) — si es in-process, migrar a Task Scheduler.
- **Cómo:** revisar `ops_tools`/reminder; usar `schtasks`/Task Scheduler XML en Windows.
- **Gate:** el recordatorio dispara tras reiniciar la app/PC.

---

## TIER 3 — Estratégico / arquitectura (sprint dedicado)

### B9 · Cliente MCP (Model Context Protocol)  ROI:A(estratégico) Esf:A Riesgo:M
- **De:** Goose (`rmcp`, 70+ servidores), openclaw (plugin-SDK), OS-Copilot.
- **Qué:** adoptar MCP como CLIENTE → 70+ servidores existentes (filesystem, git, APIs) sin escribir cada tool.
  Futuro-proof + interoperable con el ecosistema.
- **Cómo:** `pymcp` (oficial) o wrapper thin; `domain_tools/` coexiste con extensiones MCP cargadas lazy.
- **Encaje/Riesgo:** más tools = tool-calling más DURO para el 4B (cuello de botella medido); mitiga el
  router (manda subset). Refactor grande. **NO** convertirnos en gateway multi-canal/multi-agente.
- **Gate:** medir que el tool-calling del 4B no se degrade con el catálogo MCP (subset estable).

### B10 · Tool cache + versioning  ROI:B Esf:B Riesgo:B
- **De:** Goose (`ExtensionManager.tools_cache` + invalidación atómica).
- **Qué:** cachear el armado de schemas de tools entre turnos (hoy se rearma). Micro-latencia + hot-reload.
- **Cómo:** cache en `tools_pkg/tools.py::schemas_for_names` con invalidación por versión.
- **Gate:** que la invalidación no sirva schemas stale; medir ahorro real (probablemente chico).

### B11 · Skills registry con merge (public/user/project) + trigger-based  ROI:M Esf:M Riesgo:B
- **De:** OpenHands (`skill_loader.py`, 4 fuentes mergeadas; YAML frontmatter + triggers).
- **Qué:** microagents/skills cargados de múltiples fuentes (sistema/usuario/proyecto), dedup por nombre,
  activados por trigger semántico. Más reuso que nuestro `microagents/` local.
- **Cómo:** `skills_registry.py`; cargar 1 vez al boot; activar por keywords/embedding del turno.
- **Encaje:** local, sin cloud. Revisar qué ya hace nuestro microagents.
- **Gate:** que cargar más skills no infle el system prompt (piso de tokens) ni el tool-calling.

### B12 · Checkpointing / durabilidad de turno (resume post-crash)  ROI:B Esf:M Riesgo:B
- **De:** LangGraph (checkpoints por step), AutoGPT (estado), OpenHands (task progress).
- **Qué:** snapshot del estado del turno (SQLite/JSON) para reanudar si crashea a mitad de una cadena.
- **Cómo:** extender `mission_checkpoint` a checkpoint por-fase. ROI bajo: los turnos de voz son cortos.
- **Gate:** que el overhead (<20ms/turno) no toque la latencia tier-Alexa.

---

## TIER 4 — UX de voz (pulido)

### B13 · Mejor voz TTS (menos robótica)  ROI:M Esf:M Riesgo:B
- **De:** Mark-XXXIX (Gemini LiveAPI voz Charon, natural — pero es CLOUD PAGO, no adoptable).
- **Qué:** la lección: la naturalidad de la voz importa. Mejorar el modelo Piper/VITS local (voz más
  natural) sin salir de OSS/local.
- **Cómo:** evaluar modelos VITS/Piper de mayor calidad que entren en CPU; A/B de naturalidad.
- **Gate:** que no suba la latencia de synth ni la VRAM; OSS.

---

## RECHAZADOS (NO re-proponer — violan restricciones)
- Multi-agente con N modelos grandes (AutoGen) — no entra en 4GB.
- Cloud APIs: Gemini LiveAPI, GPT-4V, Chroma/OpenAI-emb, LanceDB remoto.
- Code-gen dinámico FULL por turno (OS-Copilot) — demasiados LLM-calls para 4GB.
- Reescribir en Rust (Goose) — perdemos velocidad de dev; llama-server ya sirve.
- Gateway multi-canal (WhatsApp/Slack/Discord como openclaw) — no es nuestro producto.
- Arquitectura microservicios/async-total (OpenHands) — overkill para local.

## Secuencia recomendada
1. **B1** (error-recovery) — quick-win de fiabilidad, ataca el flakeo medido.
2. **B2** (memory-tools) — latencia + fiabilidad en repeticiones.
3. **B3a** (flip streaming-info, ya hecho) + **B3b** (progreso de tool en voz).
4. **B5** (confirmation policy) + **B7** (web fallback) + **B8** (reminders) — bajo costo, robustez/UX.
5. **B6** (file-processor) — capacidad/UX.
6. **B4** (code-exec sandbox) — gran capacidad, DISEÑAR seguridad primero.
7. **B9** (MCP) — sprint estratégico, medir impacto en tool-calling.
8. B10/B11/B12/B13 — oportunistas.

> Nota de método (CLAUDE.md + lección de esta sesión): cada ítem se MIDE en box FRESCA
> (no >25 turnos seguidos), se implementa GATEADO (env flag default-off), se valida EN
> VIVO con variantes de fraseo, y recién se flippea. Nada se shippea contra ruido.
