# Backlog de ideas del research (revisión 2026-05-28, Opus 4.8)

Revisión a fondo de `gemma4_agent/docs/research/` con 3 subagentes que **verificaron
cada idea contra el código real** (descartando las ya aplicadas). Todas las de abajo
son NUEVAS, encajan en las restricciones (Gemma 4 / 4GB / OSS / sin-hardcodes /
LLM-responde) y **requieren validación EN VIVO** (los mocks no bastan, el E2B es
no-determinista — regla #3.5). Ordenadas por impacto × factibilidad.

## TOP PICKS

### 1. Streaming token→TTS en el pase-2 (time-to-first-audio) — LATENCIA, alto ROI
El runner hoy espera la respuesta COMPLETA antes de mandar a Piper (`agent_runner.py`
~650-685). `LLMClient.chat_stream` YA existe pero no se usa. Empujar a TTS por oración
a medida que llegan tokens baja el time-to-first-audio del pase-2 de ~1.9-2.5s a
~0.3-0.6s. Permitido explícitamente (el LLM genera cada palabra). Fuente:
`latency_research_prompt.md` §6, `latency_golden_eras.md` §4. Riesgo: el grounding-gate
corre sobre el reply completo — decidir si gatea el primer chunk o se acepta el
trade-off. Plomería en el runner.

### 2. Prefill del token `<|tool_call|>` en turno de acción — LATENCIA + TOOL-CALLING
Añadir un assistant-prefix parcial `<|tool_call|>` en modo acción sesga el primer token
al trigger, reemplazando el rol del thinking → permite **bajar thinking_budget de 32 a
0** en quick_action (hoy capado a 32 por el crash #22527). −0.3 a −1s pase-1 + menos
presión sobre el KV del crash. Fuente: `1_toolcalling.md` §3.2 (arXiv 2505.15323,
"first-token misalignment"). Token estructural del protocolo Gemma (no hardcode).
Riesgo: NO prefillear en charla; el parser `peg-gemma4` tiene bugs con args — abortar si
rompe. Sinergia con FR-CoT (ya escrito dormant).

### 3. WhatsApp grounded por contact_id/teléfono, NO por fuzzy-search en GUI — CALIDAD
`_whatsapp_send_via_gui_search` teclea el nombre en Ctrl+N y toma el primer match → el
bug "mamá → grupo Música" (destinatario equivocado, daño alto/irreversible). Cura de
raíz: resolver a teléfono estable ANTES (ya existe `_contacts_resolve_recipient`) y abrir
por `wa.me/<phone>`/deeplink por número, sin re-buscar en la UI; distinguir `is_group`.
Fuente: `2_memoria.md` §2 (P0). Caveat: si el contacto no tiene teléfono guardado, cae al
flujo actual (degradación honesta). El envío real queda para el usuario; abrir-el-chat
correcto (auto_send=False) sí se valida en vivo por el header.

### 4. Taxonomía de errores + presupuesto de retry POR CLASE — RECOVERY
Hoy el retry es ad-hoc (failure_log genérico, _forced_tool_retry global). Clasificar
`(result, verifier) -> {TRANSIENT, PRECONDITION_MISSING, ARG_INVALID, VERIFIER_FAILED,
TOOL_NOT_FOUND}` con budget distinto: TOOL_NOT_FOUND→0 retries, TRANSIENT→backoff,
ARG_INVALID/VERIFIER_FAILED→1 replan. Fuente: `3_verificacion.md` §2 ("466 de 513
retries fueron desperdiciados en errores que ningún retry arregla"). Pura lógica Python,
0 VRAM, clasifica por status/excepción estructural (no keywords).

### 5. 3ª señal de verify: `SetWinEventHook` async (fusión 2-de-3) — COMPUTER-USE
`gui_verify.py` usa solo 2 señales (dHash ROI + foreground); su docstring admite que falta
la de eventos. Sumar un hook `SetWinEventHook(EVENT_OBJECT_INVOKED/VALUECHANGE/
STATECHANGE)` correlacionado por `event_thread_id == GetWindowThreadProcessId(hwnd)` (filtra
ruido de Teams/Outlook). 2-de-3 = confirmed. Ataca el 14.3% falso-PASS medido ("click
ciego"). Fuente: `11_plan_computer_use_windows_4b.md` P2. Win32 puro, 0 VRAM. Riesgo:
necesita message-pump + CoInitialize en su thread; gatear `GEMMA4_GUI_VERIFY_WINEVENT`.

### 6. `--reasoning-budget-message` (cierre limpio del thinking al cortar) — CALIDAD
El budget de thinking (32 tok) se corta ABRUPTO sin mensaje de transición. llama.cpp
puede inyectar `"\n</thought>\nFinal answer:"` al cortar → recupera calidad de la
respuesta final (Qwen3-9B HumanEval 78%→89% con budget+mensaje vs corte abrupto). Flag de
server, reversible, Gemma4-nativo, 0 VRAM. Fuente: `0_arquitectura_general.md` Key Finding
#4. El número es de Qwen → medir en vivo en Gemma.

### 7. mmproj Q8_0 (560MB) en vez de BF16 (992MB) + descargable entre turnos — VRAM/4GB
~430MB menos de VRAM al activar visión (crítico en 4GB — el repo ya tiene `mmproj-...-Q8_0.gguf`),
y marcar el projector como descargable tras la llamada VLM para no empujar al OOM en el
turno siguiente. Fuente: `11_plan...md`, `8_gui.md` Fase-3 #9. Verificar sha256 + que la
visión gateada siga pasando su gate con Q8_0 (puede degradar levemente la descripción).

### 8. Slot-extraction de identificadores + fusión deíctica — CONTEXTO/CALIDAD
Extraer locators del tool_result (path/url/id) a un slot `state.last_useful_result` e
inyectarlo LITERAL en el turno deíctico ("ábrelo [ref: C:/.../informe.docx]"). El 4B sufre
"lost in the middle" → el referente debe ir al final junto al pronombre. Sube el éxito de
"ábrelo/súbelo eso" Y permite mandar MENOS historial. Fuente: `4_contexto.md` §3-4 (Liu
2023). Regex estructural sobre el JSON (no idioma). Reusa el DEICTIC existente.

### 9. Catálogo declarativo de precondiciones (`preconditions.py`) — RECOVERY
`tool -> [Precondition(check, repair)]` evaluado ANTES de actuar: app.open (¿instalada? via
which/registry), whatsapp (¿proceso vivo? psutil; ¿logueado? UIA Chats-vs-QR → needs_user).
repair() idempotente; si no puede → needs_user (encaja con pending_intent). Lo pide el
mandamiento #5 ("el código garantiza sus precondiciones"). Fuente: `3_verificacion.md` §4
(InferAct arXiv:2407.11843). psutil/win32 = estado del SO. Solo en tools de acción real.

### 10. Pre-ejecución eager de tools READ-ONLY durante el pase-1 — LATENCIA
Para intenciones idempotentes (clima, hora, estado de ventana, brillo/volumen actual),
disparar la tool read-only en paralelo al pase-1, basándose en el intent del router barato;
cuando el LLM la pide, el resultado ya está. Fuente: `reducir_latencia_thinking_gemma4.md`
P3(b) (Stream.io). DISCIPLINA DURA: allowlist ESTRUCTURAL de idempotencia (marcar read-only
en el schema, no por keyword) — jamás pre-ejecutar un write (regla #6).

## Otras (menor ROI / más nicho)
- Cadena de samplers mínima `--samplers "top_k;temperature"` en acción (trivial, +1-3% decode, riesgo ~0).
- Router adaptativo de thinking por complejidad (Ares, −52.7% tokens) — depende de #2 como red.
- UIA-subtree-delta con RuntimeId cacheado como señal de verify (re-bind 5ms vs re-scan 80ms) — complementa #5.
- Política proactiva de presión de contexto en bandas 70/85/95% (vs compaction reactiva) — ROI bajo en voz (sesiones cortas); medir distribución primero.
- Microcopy "unknown" calibrado por risk-tier — SOLO como guía al LLM (no tabla de strings, sino reforzar el system-note gateado por verify_policy), o viola "sin hardcodes".
- Sentinel de regresión voseo rioplatense/chileno (anti-overfit del NLU español no-EU; google-deepmind/gemma #460). Metodología, no runtime.

## DESCARTADAS (no re-proponer — ya aplicadas o violan restricción)
- Sampling greedy/dual, two-track filler, router por embeddings, KV q8_0 (gated), VRAM-watchdog-gate, circuit-breaker, tool isolation, mission_checkpoint, command_splitter, UIA→OCR→visión cascade, password handoff, --swa-full, context_router, memoria en capas, experience RAG, Jarvis proactivo (5_jarvis ya 100% implementado): **YA APLICADAS**.
- FR-CoT estructurado: ya escrito (dormant); MEDIDO que regresiona media por defecto → solo opt-in.
- Camino C prefijo estable / cache-reuse: MEDIDO ~2x peor E2E / dispara el crash #22527 → rechazado por el entorno.
- Speculative/draft decoding (E2B→E4B), ngram-cache, drafter gemma-3-270m: no entran en 4GB / negativos en benchmarks / contaminación Gemma 3.
- Migrar a vLLM/SGLang/xLAM/Fara/UI-TARS/voice-to-voice: no-Gemma-4 o no entra en 4GB.
- GBNF/TOOLDEC enum cerrado de tool-names: el repo lo evaluó y RECHAZÓ (pelea con la grammar de --jinja).
- QLoRA fine-tune: necesita 16GB para entrenar + mantenimiento; no primera línea.

## Orden recomendado (cuando se valide en vivo)
1. **#1 streaming TTS** (mayor win de latencia percibida, infra existe).
2. **#2 prefill tool_call + thinking→0** (ataca el costo dominante de acción; sinergia con FR-CoT dormant).
3. **#3 WhatsApp por número** (bug real de destinatario, daño alto).
4. **#6 reasoning-budget-message** (trivial, reversible, calidad).
5. **#5 WinEvent verify** + **#7 mmproj Q8_0** (computer-use robustez + VRAM 4GB).
Luego #4, #8, #9, #10 según prioridad del usuario. Todas: gate medido + prueba en vivo de
varios fraseos antes de default-on.
