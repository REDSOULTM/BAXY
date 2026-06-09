# BACKLOG MAESTRO — Baxy

**Fuente única de verdad.** Consolida los 5 backlogs históricos (ROADMAP_perfeccion,
IDEAS_research_backlog, BACKLOG_competidores, router/06_PENDIENTE, BACKLOG_research_cruzado)
en un solo lugar, con el estado de CADA ítem **verificado contra el código real** (no contra
lo que cada doc decía de sí mismo — varios estaban desactualizados).

Última verificación de la base histórica: **2026-06-02** (3 auditores cruzaron 50+ ítems
contra `gemma4_agent/`). **Estado vivo extendido al 2026-06-09** (ver §9–§16 abajo:
cacería de honestidad, idioma multilingüe, Jarvis proactivo, resolución de sitios,
voz/mic, visión residente, descomposición de archivos-dios).
Rama de trabajo: `Dev` (espejada en `main`; ambos remotos `origin` Baxy + `asistia` asistIA).

Leyenda: ✅ APLICADO (verificado en código) · 🔲 PENDIENTE-REAL · ⏸️ BLOQUEADO (con bloqueador)
· ❌ RECHAZADO (medido, no re-litigar) · 🔨 EN PROGRESO esta sesión

---

## VEREDICTO DE LA BASE: SÓLIDA

De 50+ ítems históricos verificados contra código: **la práctica totalidad de lo CRÍTICO y
de calidad/honestidad/estabilidad está APLICADO.** No hay deuda crítica oculta. Lo que queda
es: (a) tareas OPERACIONALES del usuario (no de código), (b) un frente multilingüe grande
BLOQUEADO por GPU+corpus, (c) 3-4 mejoras de ROI bajo, (d) lo medido-y-rechazado.

---

## 1. FIABILIDAD / HONESTIDAD (Críticos C1-C7, Altos H1-H9) — ✅ TODO APLICADO

| ID | Qué | Estado | Evidencia (archivo:línea) |
|----|-----|--------|---------------------------|
| C1 | WhatsApp no manda al destinatario equivocado (deeplink por phone, desempate, no GUI ciego) | ✅ | `domain_tools/whatsapp.py:130-208` |
| C2 | `is_group` estructural en metadata de contactos | ✅ | `domain_tools/contacts.py:106-136` |
| C3 | `app.open` verifica proceso real (no fire-and-hope) | ✅ | `safety_pkg/verifiers.py:114-166` |
| C4 | Tri-estado verify: `None`≠`False` (no doble-click) | ✅ | `computer_use_pkg/computer_use.py:62,319-340` |
| C5 | No "hice click" con `state_changed=False` | ✅ | `computer_use.py:386-400` |
| C6 | vram_watchdog actúa + pre-flight imagen inline (0 OOM 4GB) | ✅ | `agent.py:3515-3520,5550` |
| C7 | atexit por-instancia (no deja VRAM huérfana) | ✅ | `infra/llama_server.py:843-870` |
| H1 | `error_type` seteado por verifiers | ✅ | `safety_pkg/verify_core.py:64,195-196` |
| H2 | Budget de retry por-clase (no reintenta lo imposible) | ✅ | `verify_core.py:99-116` + `agent.py:3589` |
| H4 | Recovery exige `/health AND /slots` | ✅ | `infra/llm_client.py:297,534` |
| H6 | restart con lock + port-wait (no race en :8080) | ✅ | `llama_server.py:843,1247` |
| H8 | WhatsApp pre-check login (no `sent=True` falso con QR) | ✅ | `domain_tools/whatsapp.py:958-1064` |
| H9 | Circuit breaker OFF (medido-y-rechazado v15) | ❌ correcto OFF | `llm_client.py:253-261` |

**Extras de honestidad de esta sesión (Dev, el roadmap NO los listaba):** ✅ `honest_action_reply`
(`agent_guards.py:286`), ✅ keypress cero-señal-falsa (`computer_use.py:765 _UNAMBIGUOUS_LITERAL_KEYS`),
✅ `parse_keypress_action` (`command_splitter.py:984`), ✅ app.open gibberish honesto (`_site_resolution_relevant`).

---

## 2. ESTABILIDAD / VRAM (6 palancas CUDA #22527) — ✅ TODO APLICADO

| Palanca | Estado | Evidencia |
|---------|--------|-----------|
| flash-attn OFF (mató el crash, 37/37 turnos) | ✅ default | `llama_server.py:372` |
| ctx-checkpoints 0 + cache-ram 0 + no-cache-idle-slots | ✅ | `llama_server.py:416` |
| circuit breaker preventivo (= H9, OFF correcto) | ✅ | `llm_client.py:240-283` |
| core-rules 6 (system prompt 9.4k→5k) | ✅ | `core_tools_pareto.py:46` |
| MAX_SELECTED_TOOLS=5 (cap anti-crash) | ✅ | `planner.py:30` |

DESCARTADOS (causan OOM/peor, no tocar): `--no-flash-attn`, `--no-swa-full`, reducir `-c`,
`-ngl` parcial, env-vars CUDA, KV-quant con FA-off.

---

## 3. LATENCIA — ✅ mayormente cosechada; p50 medido 1.22s (sano, budget 4-5s)

| Palanca | Estado | Evidencia |
|---------|--------|-----------|
| keep-tools pass-2 (prefix-cache hit, −1s acción) | ✅ default | `agent.py:197-200` |
| LEAN_RULES (prompt −30%, p50 7.56 vs 10.55) | ✅ default ON | `agent_prompt.py:174` |
| streaming TTS (time-to-first-audio) | ✅ default ON | `agent.py:179` |
| greedy action-mode (+3-4/6 tool-call) | ✅ default ON | `llm_client.py:361-383` |
| forced-retry cap (GEMMA4_FORCED_RETRY_MAXTOK=128) | ✅ | `agent.py:3019-3024` |
| 🔨 **tracing batcheado** (~22ms/turno medido) | 🔨 EN PROGRESO | `infra/tracing.py` |
| `--reasoning-budget-message` (cierre limpio thinking) | 🔲 PENDIENTE | sin código; no medido en Gemma; ROI bajo |
| pre-ejecución eager read-only | 🔲 PENDIENTE | sin código; ROI bajo |
| tool-cache/versioning (B10) | 🔲 PENDIENTE | `schemas_for_names` reconstruye c/llamada; ROI bajo |
| FR-CoT (thinking estructurado) | ❌ RECHAZADO 3× | re-medido 2026-06-02: PEOR (rompe audio, +think). Premisa muerta. |
| prefill `<\|tool_call\|>` | ❌ RECHAZADO | thinking load-bearing 4/6→0/6 |
| KV-quant FA-off / streaming-TTS-filler | ❌ RECHAZADO | medidos ~0 ganancia |
| MTP (3× decode) | ⏸️ BLOQUEADO | no existe en llama.cpp aún (3-6 meses) |

---

## 4. CALIDAD / ROUTING — barato aplicado; multilingüe pesado bloqueado

| Ítem | Estado | Evidencia / bloqueador |
|------|--------|------------------------|
| Encoder FT + abstain head + per-tool heads + clustering (holdout ES 0.9964) | ✅ | `routing/` + `data/*.json` |
| MCP-prefer en router (`_MCP_PEAK_KEEP=0.40`, collapse-a-1) | ✅ | `planner.py:67,436-439` |
| Deícticos ring-buffer multilingüe | ✅ default ON | `routing/deictic_detector.py` |
| greedy action-mode | ✅ | `llm_client.py:361` |
| accent en is_question_lexical (PT/IT/FR sin tilde) | ✅ | `intent_router.py:46,114` — `_fold` (NFKD acento-agnóstico) pliega ANTES de matchear; wh-words y verbos en forma plegada. Verificado en vivo 9/9 (perchè/quê/quanto/cosa/chi/dove). |
| **B2 corpus multilingüe de eval** (hoy ~98% ES) | 🔲 PENDIENTE-REAL | prerrequisito de todo lo multilingüe; sin bloqueador técnico, es construir datos |
| **B1 encoder FT alemán/multilingüe** (GAP-2) | ⏸️ BLOQUEADO | ~12h GPU 4060Ti + depende de B2 |
| **B4 calibración abstain por idioma** (GAP-4) | ⏸️ BLOQUEADO | infra lista (`thresholds_by_lang`) pero artefacto vacío; depende de B1+B2 |
| SPRINT5 anti-primacy ordering | ✅ | `b812841` — estaba mergeado pero INERTE: `schemas_for_names` (tools.py:1495) descartaba el orden del router (filtraba por `set`). Fix: ordena por posición en `names` + cache keyed por tuple. Validado E2E (browser antes que media llega al LLM), 27/27 verde. |
| SPRINT5 few-shot turn-specific | ❌ DESCARTADO | research: baseline ya 6/6; prefill mal hecho ROMPE el tool-call; complejidad+riesgo sin ganancia medible. |
| cap=5→8 (GAP-5; FA-off ya mató el crash) | ❌ NO tocar | crash CUDA ya muerto, pero el norte del user es precisión>recall (MENOS tools). Va en contra. |
| **ruido router: wants_web_store falso-positivo** (ALTO, MEDIDO) | 🔲 PENDIENTE-vivo | `planner.py:835-846` — wants_web_store sobre-dispara en menciones de entretenimiento/celebridad ("quien es batman", "pon stranger things") → inyecta browser+browser_real de ruido en 189 tool-turns. A/B con OFF: ruido 1.519→1.453, recall SUBE 0.9929→0.9953. Fix: exigir verbo de compra/nav-a-sitio, o no insertar el par browser cuando wants_knowledge. NO aplicado: toca clasificador semántico, exige validación EN VIVO (regla #3.5). |
| **ruido router: web→source_manager + head débil** (los 3 canarios, MEDIDO) | 🔲 PENDIENTE-vivo | `planner.py:1503` + head firing :637-660 — "que dia es hoy"/"what time is it"→web (forbidden, es fecha local); "que es pytest"→web+knowledge+source_manager (debería ser EMPTY). Causa: per-tool head dispara web con margen débil (0.05-0.10) evadiendo la guarda `_LOCAL_FACT` que SÍ funciona en `_suggest_tools`; + `_related_tools('web')` arrastra source_manager. Fix: aplicar la guarda local-fact/wants-knowledge también al head, y source_manager solo con intent explícito. NO aplicado: router, exige validación EN VIVO. |

---

## 5. COMPETIDORES (B1-B10) — ✅ aplicados (varios gated opt-in)

| ID | Qué | Estado | Flag/evidencia |
|----|-----|--------|----------------|
| B1 | Error-type recovery | ✅ default ON | `GEMMA4_ERROR_RECOVERY` (`agent.py:215`) |
| B2 | Memory-guided tool-picking | ✅ default ON | `GEMMA4_MEMORY_TOOLS` (`agent.py:231`) |
| B3a | Streaming-info TTS | ✅ default ON | `GEMMA4_STREAM_TTS` |
| B3b | Earcon progreso | ✅ opt-in OFF | `GEMMA4_PROGRESS_EARCON` (`voice/earcon.py:37`) |
| B4 | Code-exec datos (sandbox genérico descartado a propósito) | ✅ | `data_analysis.py`, `database.py` read-only |
| B5 | Política confirmación (confirm_risky) | ✅ default | `safety_pkg/confirmation_policy.py:76` |
| B6 | File-processor unificado | ✅ gated OFF | `GEMMA4_FILE_PROCESSOR` |
| B7 | Web fallback DDG→Bing | ✅ default ON | `GEMMA4_WEB_FALLBACK` (`tools.py:1314`) |
| B8 | Reminders Task Scheduler | ✅ default ON | `GEMMA4_REMINDER_SCHEDULE` (`ops_tools.py:725`) |
| B9 | Cliente MCP | ✅ construido, gated OFF | `GEMMA4_MCP` (`mcp_client.py:47`) — falta validar+flip, NO construir |
| B10 | Tool cache/versioning | 🔲 PENDIENTE | ROI bajo |

---

## 6. OTROS IDEAS aplicados — ✅

✅ #5 SetWinEventHook 3ª señal verify (gated `GEMMA4_GUI_VERIFY_WINEVENT` OFF) ·
✅ #8 slot-extraction deíctico (= deícticos) · ✅ #9 preconditions declarativas (default ON;
**OJO docstring stale dice "off"**) · ⏸️ #7 mmproj-Q8 (código listo, artefacto upstream no existe).

---

## 7. PENDIENTE OPERACIONAL (del usuario — NO es código)

1. **Bundlear binario CPU/Vulkan de llama.cpp** + apuntar `GEMMA4_LLAMA_SERVER_EXE`. El software
   auto-detecta perfil `cpu` (-ngl 0) sin NVIDIA, pero falta el binario. **Único bloqueador de mercado real.**
2. **Declarar servidores MCP** en `~/.gemma4/mcp_servers.json` + validar que el 4B no degrada con
   catálogo grande → recién ahí flip `GEMMA4_MCP=1`.
3. **mmproj-Q8_0**: desbloquea cuando exista el GGUF upstream (llama.cpp#18881 abierto).

---

## 8. DISCREPANCIAS doc↔código a corregir (comentarios stale)

1. `documentacion/BACKLOG_competidores.md` lista B9 (MCP) como "único gap pendiente" → FALSO, está
   construido y cableado; lo pendiente es validar+flip.
2. `safety_pkg/preconditions.py:19` docstring dice "default off" → el código está ON (flippeado 2026-05-29).

---

## NOTA DE CONSOLIDACIÓN

Este archivo REEMPLAZA como fuente de verdad a: `ROADMAP_perfeccion.md`, `IDEAS_research_backlog.md`,
`BACKLOG_competidores.md`, `router/06_PENDIENTE_Y_NO_FORZADO.md`, `BACKLOG_research_cruzado_2026-06-01.md`.
Esos quedan como histórico/detalle; este es el índice maestro con estado verificado. Se actualiza
con cada avance (sección de ESTADO VIVO abajo).

### ESTADO VIVO (fixes — rama Dev) — TODOS ✅ VALIDADOS EN VIVO 2026-06-02
| Fix | Estado | Commit |
|-----|--------|--------|
| Tracing batcheado (~22ms/turno) | ✅ mergeado + tests (infra, no req. vivo) | `404e0cc` |
| brightness honesto (re-leer post-set) | ✅ mergeado + VALIDADO VIVO (3 casos: confirma/no-aplicó/sin-DDC honestos) | `2c997a3` |
| accent multilingüe (is_question_lexical) | ✅ mergeado + VALIDADO VIVO (3 preguntas sin tilde→web OK) | `a28851b` |

### ESTADO VIVO — CIERRE 2026-06-02 (tarde) — sin commitear aún en working-tree
| Fix | Estado | Notas |
|-----|--------|-------|
| **Modelo E2B-FT v2 desplegado** | ✅ in-place (`models/E2B/...gguf` = el FT; backup `.BASE-BACKUP`) | VRAM 2.07GB, entra en 4GB. 0% tools inventadas en prod. |
| **smart_home ELIMINADO de verdad** | ✅ schema+handler+dataset+router-data + keyword rule planner + 5 refs código | la validación EN VIVO destapó que el router AÚN lo ofrecía por un keyword rule hardcoded |
| **BUG honestidad: "bajé el termostato"** | ✅ defensa-en-profundidad | source_manager (read-only ok=True/verified=None) sustentaba un claim de efecto físico FALSO. Fix: guard_unverified_final no exime si no cambió el mundo + reply afirma efecto; + anchors domótica en reply_validator. EN VIVO 5/5 honestos. |
| **BUG router: desalineación tool_head** | ✅ | quitar smart_home dejó tools(61) vs weights/biases/thr(62) → 13 tools leían el threshold del vecino → "que es pytest" ofrecía whatsapp. Fix: quitar del mismo índice en los 4 arrays. |
| **READY-GATE: casilla esperaba al router** | ✅ VALIDADO VIVO (boot real: ready a 14.1s con router listo) | la casilla se desbloqueaba antes que el router (thread bg sin join). Fix: latch `is_router_ready()` + join timeout 45s degradado + los 2 PULL de server.py al AND. |
| **7 fallos de tests** (audit_metrics, r4_smoke, skills FP, silent_except, god_object) | ✅ | incluidos los preexistentes (pedido del usuario). Suite final 2740 passed, 0 failed. |
| **tool_schemas PHASE-2** | ❌ MEDIDO-Y-RECHAZADO | vram4 ya usa modo `compact` (74-85% ahorro); el renderer no emite param.description. No aplica. |

**Pendiente de cierre:** estos cambios están en working-tree SIN commitear. Falta: `git add` + commits temáticos + (opcional) merge a Dev.

Regresión áreas tocadas (3 juntos): 295 passed, 0 failed. Tracing tool-directo confirmó
verified=True cuando GET=pedido. Accent: "que es X"/"cuando salio Y" sin tilde → web (info), no app.

Detalle tracing: handle persistente + lock + atexit, cierra antes de rotar. Ahorro MEDIDO
25.6→3.6ms/turno (86%). Fail-safe y rotación preservados. 18 tests verdes. `infra/tracing.py`.
Detalle accent: el bug real era enumeración manual de acentos en _WH_RE (solo cubría agudo) →
fold NFKD del input antes del match → grave/circunflejo/garble ASR ahora matchean. Gate 13/16→16/16.
`intent_router.py:34-122`. Límite: solo acento dentro de palabras ya listadas, no agrega idiomas.

Detalle brightness: re-read post-set + tri-estado (confirmado ±5% / no-cambió→verified=False
honesto / monitor sin DDC→fallo-SO honesto / no-medible→dispatched). 24 tests verdes. Patrón
copiado de audio_set_volume. `tools.py:3797-3837`. VALIDADO VIVO ✅.

---

### TANDA "4 mejoras chicas ROI-bajo" (decisión usuario 2026-06-02: "4 chicas suman no-despreciable") — ✅ COMPLETA
Los 4 MERGEADOS a Dev (HEAD `b99fc4f`). Regresión áreas tocadas: 462 passed, 0 failed.
Validación viva ✅: #1 (acciones razonadas → reply LIMPIO, sin leak) + #4 ("abre navegador y
reproduce música" ejecuta ambas, "subí volumen" intacto) + #3 output idéntico.
#2 EAGER: validado EXHAUSTIVO (pedido del usuario "todas las validaciones") → adversarial 32/32
escrituras nunca eager + args-efecto bloqueados; vivo 9/9 escrituras→0 eager; AFINADO por
embeddings (dispara solo la read relevante, "qué hora es"→[time], "subí volumen"→[]) commit
`15b6a46`; FLIPPEADO a default ON commit `16678a2` (27+136 tests verdes).
DEFAULTS FINALES: #1 ON, #3 ON (sin flag), #4 ON, **#2 ON** (kill-switch GEMMA4_EAGER_READONLY=0).
TODOS los 4 ROI-bajo ACTIVOS y validados. Tanda CERRADA. HEAD Dev `16678a2`.

| # | Fix | Estado | Notas para retomar |
|---|-----|--------|--------------------|
| 1 | `--reasoning-budget-message` | ✅ MERGEADO a Dev `a70cb0e` (falta validación viva) | Flag agregado en `llama_server.py:410-450`. Tag de cierre de Gemma 4 = **`<channel|>`** (NO `</think>`=deepseek), verificado x2 (chat_template del GGUF real + fuente llama.cpp `common_chat_params_init_gemma4`). Mensaje: "\nTime to answer. Stop reasoning and give the final answer or tool call now." Flag `GEMMA4_REASONING_BUDGET_MSG` default ON (custom-msg via env). 6 tests + 57 gate. Impacto chico (honesto). VIVO: forzar corte en quick_action (budget 32). |
| 2 | Pre-ejecución eager read-only | ✅ MERGEADO a Dev `0d4bba8`, default OFF | Módulo `agent_core/eager_readonly.py` + 3 spots en agent.py (+56 LOC). Solo 4 pares `system.{time,cpu_ram_gpu,disk,battery}` (acción-level, no tool-level). 3 BARRERAS independientes (tabla + verbo-lectura estructural + classifier). HALLAZGO: el agente midió que el safety classifier deja pasar set_volume/play → cambió barrera #2 a check estructural de verbo. Tests anti-escritura (NoWriteEver ~30 writes + PoisonedTable) VERIFICADOS independientemente por el orquestador (9/9). fail-safe (eager falla→turno idéntico). Gate `GEMMA4_EAGER_READONLY` default OFF. VIVO pendiente antes de flip ON. |
| 3 | Tool-cache en `schemas_for_names` | ✅ MERGEADO a Dev `6dc603d` | `tools.py:1501-1543` cache por (frozenset(names), lean_on). Ahorro MEDIDO 0.013ms/turno (despreciable pero real — decisión usuario: features suman). Invalidación bien resuelta: LEAN en la clave; subsets con MCP BYPASEAN el cache (imposible stale). Equivalencia byte-a-byte (0 mismatches). 10 tests + 128 gate. No requiere validación viva (output idéntico al LLM). |
| 4 | Anti-primacy ordering | ✅ MERGEADO a Dev `8a537bb` (falta validación viva) | `_antiprimacy_order` en `planner.py:181-244`, wiring `:900-919`. Reordena dominio por score (reusó `_collapse_scored`, no threadeó), pending_intent primero, `_INFRA_TAIL_TOOLS` al final. Gate set(antes)==set(después) ✅. 14 tests; 5 fallos del barrido = pre-existentes (0 nuevos). Flag `GEMMA4_ANTIPRIMACY`. RIESGO anotado: en multi-paso el score puede reordenar peor que orden-de-mención → flag revierte. VIVO: "abre el navegador y reproduce música" (browser debe ir antes que media). |

PENDIENTES MÁS GRANDES (5-8, dejados a propósito para después):
- **#5 Bundlear binario CPU/Vulkan de llama-server** — OPERACIONAL (usuario). El SW ya cae a perfil `cpu`
  (-ngl 0) sin NVIDIA, pero `tools/llama-cuda/` es solo-CUDA. Descargar/compilar build CPU o Vulkan
  (cubre iGPU Intel/AMD) + apuntar `GEMMA4_LLAMA_SERVER_EXE`. **Único pendiente que expande el mercado**
  de "PC con NVIDIA 4GB" a "cualquier laptop". Bloqueador de mercado real.
- **#6 Declarar servidores MCP** — OPERACIONAL. Cliente ya construido+cableado (gated `GEMMA4_MCP=0`).
  Declarar servers en `~/.gemma4/mcp_servers.json` + validar en vivo que el catálogo no degrade el
  tool-calling del 4B → recién flip ON.
- **#7 Router multilingüe** — BLOQUEADO en cadena: corpus eval multilingüe (B2, construir datos) →
  reentrenar encoder ~12h GPU 4060Ti (B1) → calibración por idioma (B4). Infra lista (thresholds_by_lang
  vacío). Frente grande conocido, no deuda oculta.
- **#8 mmproj-Q8** — BLOQUEADO upstream. Ahorraría ~430MB VRAM, pero el GGUF no existe y llama-quantize
  falla "unsupported architecture: clip" (llama.cpp#18881 abierto). Código ya listo para usarlo si aparece.

NOTA: el usuario tiene un "feature gigante" para pedir DESPUÉS de estos 4. Priorizar terminar los 4
ROI-bajo (1,3,4 listos; 2 con cautela) cuando resetee la cuota, luego el feature grande.

---

# ESTADO VIVO EXTENDIDO (2026-06-03 → 2026-06-09)

Todo lo de aquí abajo es POSTERIOR a la verificación base del 2026-06-02 y está
**commiteado en `main` + `Dev` (ambos remotos)**, salvo donde se diga lo contrario.
Verificado contra el código real.

## 9. CACERÍA DE HONESTIDAD (dataset 6162 casos, tandas 1–6) — ✅ CERRADA

El usuario pidió correr los 6162 ejemplos del dataset de fine-tuning contra el LLM
real, juzgar cada caso (juez LLM Opus), hallar la causa raíz y arreglar TODOS. Se
corrió en 6 tandas. Resultado: una familia de **guardas de honestidad ESTRUCTURALES**
(miden la FORMA del reply/turno, no el contenido — no hay listas por idioma) en
`safety_pkg/reply_validator.py` + detectores de routing en `routing/planner.py`.

| Guard / fix | Qué bloquea | Evidencia |
|-------------|-------------|-----------|
| media-fabricado (INLINE-REPAIR + A/B/C) | "Stranger Things en Netflix" inventado sin tool real | `reply_validator.py` (`13ef80f`, `03822b1`) |
| destructive-claim endurecido (8× menos FP) | afirmar que borró/destruyó algo sin la acción | capas en `reply_validator.py` (`8fbff58`, `0e74913`, `a374b6c`) |
| how-to ≠ acción | "cómo elimino una carpeta" ya no BORRA la carpeta | planner `_is_howto` (`bdcceda`) |
| anti prompt-injection en acción destructiva | instrucción embebida no dispara borrado | planner `_is_prompt_injection` (`340280d`) |
| click-claim multilingüe | "cliqueé X" sin tool que clickee | `reply_validator.py` (`cc36214`) |
| tests-passed | "los tests pasaron" sin el conteo real | `reply_validator.py` (`4405211`) |
| footer del verifier en prosa | "[N no confirmada(s)]" crudo → prosa | `c8ac105` |
| loop 'actual'/'la ventana actual' (30s→3s) | batch degenerado de 140 tool_calls (Gemma 4 #1756) | `b000ff7`, `c84551e` (dedup_degenerate_batch + cap research 2048→768) |
| ruido número/medición no se ejecuta | "B3" — input de bajo señal abstiene | planner `_is_low_signal_noise` (`a65dd4e`) |
| intent↔domain cruzado (default ON) | guard cruzado de intención vs dominio | `18ca9b5`, `3c8fe15` |
| "cuando diga X haz Y" crea rutina, no ejecuta | B2 — trigger declaration | `51345ea` |
| perfil Jarvis no se vuelca como comando | A5 — charla emocional/identidad/system-query | `14c314d`, `3ad96dc`, `510ec04` |

Toggles `GEMMA4_*_GUARD` (default-ON). Re-run final 6162/6162 medido en 4 corridas.
**Aprendizaje clave (memoria):** una guarda nueva DEBE pasar auditoría adversarial
sobre data CRUDA (el guard destructivo inicial tenía 8/9 FP). Harness:
`scripts/_diag/_diag_hunt_tanda.py`. DESCARTADOS por medición=artefacto-del-mock:
cifras/whatsapp/gate-ya-existente (el mock `execute→ok:True` inventa cifras que el
tool REAL devuelve bien — NO son bugs de prod).

## 10. IDIOMA MULTILINGÜE — ✅ APLICADO (selector + reparación)

| Fix | Qué | Evidencia |
|-----|-----|-----------|
| **Selector de idioma en settings** | fija el idioma de todo el stack; "" = Automático | `GEMMA4_VOICE_LANG`, GUI VoiceTab `<Select>`, `agent._reply_lang` |
| reply post-tool multilingüe 0/5→5/5 | el reply post-tool salía en ES aunque el user escribiera en otro idioma ("language confusion", contexto ES arrastra) | contexto LIMPIO para el summary (`_llm_action_reply`) + `reply_repair.py` |
| francés con selector en Automático | drift de py3langid | `bf146d2` |
| bloque "Reply language for this turn" en el prompt | el idioma detectado no llegaba al prompt normal | `reply_repair.turn_language_instruction` |
| guarda universal de mismatch de idioma | reescribe preservando significado, sin enlatado | `reply_repair.repair_reply_language_if_needed` |

Research de respaldo (deep-research, REFUTÓ folklore): es "language confusion"
(Cohere EMNLP 2024), no "el system prompt gana". Doc:
`GEMMA4_modelo_finetune_idioma_2026-06-06.md`.

## 11. JARVIS PROACTIVO — ✅ IMPLEMENTADO (toast ON, TTS/chat-offer opt-in)

Jarvis que usa la PC normal (sin chatear) y de repente sugiere automatizar una
rutina detectada, con REVERSIBILIDAD total. `proactive_notifier.py` (toast
windows-toasts + anti-molestia: no avisa en zoom/teams/discord/fullscreen) +
`jarvis_proactive.py` (orquestador en cada transición de app). `GEMMA4_JARVIS_PROACTIVE`
ON por default (toast no-invasivo); `_TTS` y `_CHAT_OFFER` opt-in. Apagar todo con
`GEMMA4_JARVIS_PROACTIVE=0`. Auditoría adversarial (42 agentes, 33 hallazgos, 7
arreglados): CRIT corruption-recovery no cerraba handle→DB brickeada (fix); HIGH
forget() borra TODO (privacidad=ley). commits `ad2443d`, `8d4e4c7`, `f6222d2`,
`832c4d5`. Ver `DISENO_jarvis_proactivo_2026-06-07.md` + `_JARVIS_auditoria_2026-06-07.md`.

## 12. RESOLUCIÓN DE SITIOS ("ve a X") — ✅ ESTRUCTURAL + POPULARIDAD + DNS

Evolución completa del resolvedor `tools_pkg/site_resolver.py` (extraído del
archivo-dios). NO adivina el TLD — lookup real por búsqueda web.

| Etapa | Qué | Evidencia |
|-------|-----|-----------|
| dominio REAL por búsqueda, no el adivinado por el 4B | "ve a pivigames" → pivigames.blog (no .com) | `f732e68`, `2a675d6` (procedencia) |
| metasearch ddgs (Google/Brave) | trae el sitio que el user ve en su navegador | `f0b15c1` |
| homónimos por país del SO (ccTLD) | UNIEJ existe CL/PE/CO/SV → gana el del user | `7e8f98f` (GetUserGeoID, no idioma) |
| **señal estructural anti-agregador** (reemplaza lista hardcoded `_NON_SITE_HOSTS`) | el nombre debe ser LABEL COMPLETO del dominio, no substring (insta⊄instagram); descarta perfiles de tercero sin lista — universal (cubre VK/Weibo/Naver) | `47e6c14` |
| **popularidad** | un PREFIJO de label en resultado TOP del buscador gana al lookalike nicho enterrado ('insta'→instagram.com, no insta.com.br). SLD canónica gana siempre | `3bcfdc4` |
| **DNS** | no devuelve dominios que no existen (getaddrinfo, fail-open ante timeout); si ninguno resuelve → None | `3bcfdc4` |

Medido en `scripts/_diag/_diag_non_site_hosts.py`. La lista hardcoded se ELIMINÓ
(`non_site_hosts` queda como param deprecado sin efecto). +test_site_resolver_structural_aggregator.

## 13. VOZ / MIC — ✅ WASAPI + calibración de ruido + anti-falso-wake

"Oye voces donde no hay". RAÍZ: gate fijo (350) no-universal + `device=None` usaba
MME que NO soporta 16 kHz y DEVUELVE CEROS. Fix: WASAPI (default real, 48k nativo)
+ resample a 16k (`audio_io.py`, kill-switch `GEMMA4_VOICE_WASAPI`); auto-calibración
RELATIVA del umbral (`noise_calibration.py`: ruido×1.6, sin piso absoluto);
detección de mic muteado (pycaw + CoInitialize). Verificado en vivo: voz 1050 vs
ruido 4. commit `25de1c2`. Wake-word: añadidos `maxi/paxi/vaxi/...` (Whisper oye
"Baxy"→"Maxi"); strip fonético en `pipeline.py`. Vocalizaciones no-léxicas
("mmh/mhhh") → NO_SPEECH (no disparan cancel_turn). commit voz de la tanda Codex.

## 14. VISIÓN — ✅ 3 bugs de click/describe + mmproj SIEMPRE RESIDENTE

**(a) 3 bugs (2026-06-07):** "apretá el primer título que veas" describía/alucinaba.
#1 routing (keyword "pantalla"→vision aunque sea acción) → quitar vision del keyword
+ force-include por score + reentrenar encoder (32 ej. 6 idiomas, gate 0.99/0.98
intacto). #2 visión (monitor=all 3840×2160 alucina) → monitor="active"
(GetForegroundWindow) + ancla OCR (Tesseract). #3 STT ("Baxy"→"Maxi"). commit `6e6bf90`.

**(b) Steam click dead-end + OCR-echo (2026-06-08):** "apretá el icono de Mortal
Kombat" (visible en Steam) → `steam(click)` enum inválido → reintentaba launch_game
→ callejón. Fix: `visual_click_redirect.py` redirige el verbo de click visual no-válido
a `gui(click_text)` (OCR localiza y clickea); `uia/browser(click)` válidos NO se
secuestran. La descripción de visión volcaba el OCR crudo (`<<<...>>>`) al reply →
`_strip_ocr_echo` en `vision_describe.py`. commit `808df2a`.

**(c) mmproj SIEMPRE RESIDENTE (2026-06-09):** `GEMMA4_VISION_ALWAYS` **default ON**
→ el proyector de visión queda cargado, una imagen NO paga la carga on-demand (~2-5s
del router-mode lazy). MEDIDO (build llama.cpp 9090, flags de prod): el mmproj
residente NO penaliza el cache de texto (issue ggml-org/llama.cpp #21133 ya fixeado;
turno warm re-evaluó 10 tok/21 ms). `vision_always_enabled()` desactiva el router-mode
(mutuamente excluyentes). Toggle GUI "modo visión siempre activo". Apagar →
router-mode lazy. commit `b848d82`. Harness `scripts/_diag/_measure_mmproj_text_cache.py`.
**Esto SUPERA la nota histórica "router mode lazy vision"**: el lazy ya no tiene
ventaja en builds nuevos de llama.cpp, solo la desventaja de la latencia de carga.

## 15. WEB: buscaba pero no respondía — ✅ resume + guard

"háblame de Mortal Kombat" → web.search (snippets buenos) + web.open de un tab
fallido en vez de RESUMIR. Fix: schema de web reescrito (tras search RESPONDÉ con
snippets; open solo si el user quiere VER) + guard en `t_web`/`t_browser`: open sin
que el user dicte el dominio → redirige a web.read (contenido para responder), no tab;
web.read con query → research. `site_resolver.user_requested_open`. Calidad de fuentes:
`web_source_quality.py` clasifica foro/discusión vs estándar por FORMA (no allowlist
de dominios). Media: resume del VIDEO/MEDIA ACTUAL sin inventar query de YouTube
(`media_current.py`). commit `808df2a` (tanda Codex, revisada y validada).

## 16. DESCOMPOSICIÓN DE ARCHIVOS-DIOS (ratchet) — ✅ 7 módulos hermanos nuevos

El ratchet anti-archivos-dios (`test_god_object_size_ceiling.py`) fuerza extraer a
módulos hermanos en vez de crecer el techo. Extracciones de estas sesiones:

| Módulo nuevo | Extraído de | Qué |
|--------------|-------------|-----|
| `agent_core/agent_helpers.py` | `agent.py` | helpers libres (`e2b7c79`) |
| `tools_pkg/site_resolver.py` | `tools.py` | resolución de sitios (`1cae3b1`) |
| `tools_pkg/vision_describe.py` | `tools.py` | describe_screen con ancla OCR |
| `tools_pkg/web_search.py` | `tools.py` | scrapers DDG/Bing + selector de proveedor |
| `tools_pkg/web_source_quality.py` | `tools.py` | calidad de fuentes (foro vs estándar) |
| `tools_pkg/visual_click_redirect.py` | `tools.py` | redirección click-visual → gui |
| `agent_core/reply_repair.py` | `agent.py` | reparación de idioma + info-followup + observación de media |
| `domain_tools/media_current.py` | `domain_tools/__init__.py` | resume del video/media actual |

Caveat honesto: `agent.py` subió su techo +296 (deuda registrada en el comentario
de `CEILINGS`) por un bloque INLINE irreducible (info-followup prefetch ~94 LOC que
muta los locales del loop del turno); el resto se extrajo. Mapa:
`documentacion/01_arquitectura/` (MAPA_descomposicion_archivos_dios).

---

### Datos de estado actualizados (2026-06-09)
- **Suite de tests:** ~2917 passed, 0 failed (creció con los tests de las tandas).
- **Visión:** mmproj RESIDENTE por default (`GEMMA4_VISION_ALWAYS=1`); router-mode lazy
  disponible como fallback (apagar el toggle).
- **Idioma:** selector en settings (`GEMMA4_VOICE_LANG`); "" = Automático.
- **Resolución de sitios:** señal estructural + popularidad (posición del buscador) +
  validación DNS; sin lista hardcoded de dominios.
- **Honestidad:** familia de guardas estructurales default-ON (cacería 6162 cerrada).
