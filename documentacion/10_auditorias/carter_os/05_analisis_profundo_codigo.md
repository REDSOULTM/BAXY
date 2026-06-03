# 05 — Análisis profundo del código de Carter (lectura módulo por módulo)

Auditoría exhaustiva del CÓDIGO real (no solo docs) de:
- `carter_v5/` completo (22k LOC: core, mission, verify, loop, memory, safety, tools, adapters).
- `legacy/Carter_v3` y `legacy/Carter_v4` (módulos que v5 PERDIÓ en la migración).
- `legacy/Referencia OpenClaw` (origen de active-recall + workspace).

Leído con 3 agentes Explore en paralelo + verificación directa. Cada técnica con
archivo+línea. **Todo cruzado contra NUESTRO código** (ver matriz en 06).

---

## A. core/ — el agent loop de v5

### execution.py (697 líneas) — el loop
- **MAX_CHAIN_DEPTH=8 + MAX_TURN_SECONDS=120**: doble límite (profundidad + wall-clock). Nosotros tenemos max_agent_turns=8 + per-mode timeout — equivalente.
- **Honesty gate en 3 capas** (líneas 290-663):
  1. `_promote_tool_data()`: si el LLM dijo "Listo." pero el tool emitió DATOS (hora, contenido, lista), **reemplaza el reply con la síntesis de los datos** (`_reply_from_last_tool`). → Nosotros tenemos algo similar (breadcrumbs) pero NO la promoción automática del dato.
  2. `_enforce_honesty()`: si outcome≠COMPLETED pero reply="Listo." → reescribe desde el outcome.
  3. **Fake-done detection con NFKD folding** (líneas 577-600): absorbe variantes ("listo", "ya está", "hecho", "ya lo abrí") normalizando. → Nuestro reply_validator solo matchea "listo" literal regex.
- **Setup-step nudge SIN incrementar depth** (líneas 250-269): si tras `gui_deeplink`/`app_open` el LLM solo emitió texto, inyecta "la misión no terminó" como turno gratis. → Nuestro `_chaining_nudge` es parecido pero cuenta turno.

### router.py (314) — UN router pre-LLM (lección clave de v5)
- 7 arquetipos: TRIVIAL / KNOWLEDGE / DESTRUCTIVE / TOOL_SIMPLE / TOOL_VERIFY / MISSION / MISSION_LONG.
- **`_fold()` (NFKD + lowercase + strip diacríticos)** antes de cualquier match: "qué"→"que", "cerrá"→"cerra". → Nosotros usamos embeddings (más robusto multilingüe) PERO el fold es un buen pre-paso barato.
- **Short-circuit de TRIVIAL** (líneas 256-280): "ok"→"Listo.", "gracias"→"De nada." SIN LLM. Ahorra 4-7s. → **NO LO TENEMOS** — todo "ok"/"gracias" pasa por el LLM. Gap real de latencia.
- **SamplingProfile.for_archetype**: temperatura por arquetipo. → Acabamos de aplicar T4 (per-mode sampling) — equivalente.

### context_builder.py (171) — prefijo estable (anti-patrón 3.5)
- **StableContext construido UNA VEZ** (system + memory inicial), append-only después. Preserva el KV cache.
- **`_MAX_TOOL_RESULT_CHARS=4000`** con marcador `...[TRUNCATED to fit context]`: trunca resultados largos de tools (skill_load, search) para no desbordar contexto. → **Verificar si truncamos** los tool_results grandes con marcador.
- **`_HIDDEN_TOOL_RESULT_KEYS`**: filtra campos ruidosos (frame_diff_fraction, _raw_xml, _score) antes de pasar al LLM. → Buena idea aditiva.

### durable_state.py (128) — sesión persistente
- **Atomic write-then-move** (.tmp → replace): sobrevive crash mid-write.
- Cleanup de sesiones >7 días. Gate `CARTER_V5_DURABLE_OFF`.
- → Tenemos `sessions.py`; verificar si persiste con atomic write.

### workspace.py (246) — archivos editables por el usuario (port de OpenClaw)
- `~/.carter_v5/workspace/{AGENTS,SOUL,IDENTITY,USER,TOOLS,HEARTBEAT,MEMORY}.md`.
- **`build_workspace_block(subagent=True)` filtra**: subagents ven solo AGENTS+TOOLS, no la persona. → **NO LO TENEMOS** — concepto interesante para personalización sin código.

---

## B. mission/ + verify/ + loop/ — verificación

### mission/goal.py (364) — verifier por-misión (Voyager)
- **Verb patterns multilingües con `\w*`** para conjugaciones (abr\w*|open\w*|ouvr\w*).
- **Arg-aware kinds** (líneas 159-230): `gui_deeplink(intent="search")` → solo `navigate` (NO open_target, porque buscar abre la página de búsqueda, no el target). `intent="install"` → open_target + destructive_install. → **Sutileza valiosa** que nosotros probablemente no distinguimos.
- **Nosotros YA tenemos `mission_goal.py`** — comparar si captura el arg-aware.

### loop/detection.py (239) — 5 patrones
- Mismos 4 que nosotros + **5º patrón `no_progress`**: N tool-calls sin que cambie ningún `evidence_key`. → **Candidato #1 de la auditoría anterior** (confirmado aquí: nuestro loop_detection tiene `record_evidence` pero NO el detector explícito no_progress).
- Mismos umbrales (REPEAT_WARNING=3, CRITICAL=5, PING_PONG=6, GLOBAL=30) — coinciden con los nuestros.

### verify/core.py (423) + verify/runtime.py (244)
- Verificadores estructurales por-tool (pycaw para volumen, EnumWindows para foco, frame_diff para GUI). Estado `confirmed: True | False | None` (None = no verificable, honesto). → Tenemos verify_core.py con la misma filosofía.
- **frame_diff verifier** (gui_universal/gui): captura pantalla PRE+POST, threshold >16/canal, multi-monitor via `mss.monitors[0]`. Estado None si ok=True pero sin cambio visual. → **NO tenemos frame_diff** como verificador de GUI. Útil si atacamos GUI por clicks.

---

## C. memory/ — memoria

### memory/store.py (278) — SQLite + e5-small
- **Detección ESTRUCTURAL de secretos** (no keyword-list): patterns (`sk-...`, `AKIA...`, `xox[bp]-`) + high-entropy (≥32 chars con mezcla de casos). NO flaggea paths de Windows. → **Buena idea**: no guardar API keys en memoria. No lo tenemos.
- **e5-small con prefijos `passage:`/`query:`** (protocolo del modelo). Nosotros usamos MiniLM-L12 (sin prefijos). Ambos multilingües.
- **Hybrid ranking**: top semántico + recientes sin embedding.

### memory/active_recall.py (171) — recall pre-turno (port OpenClaw)
- **Circuit breaker de 3 estados** (max_failures=3, window=60s, cooldown=120s, half-open auto-reset).
- **timeout_seconds=1.5**, early-exit si `len(user_text)<8`.
- Inyecta `## Relevant memory\n- key: value`. → **Candidato #5**. Nuestra memoria en capas (inv 2) es PASIVA (mete hechos al prompt); active-recall RESUELVE referencias antes del LLM. Solapamiento ~60%.

### memory/wiki.py (298) — export a markdown Obsidian
- Categoriza hechos estructuralmente (pref→preferences, paths→entities). → Nicho, baja prioridad.

---

## D. safety/ — seguridad

### safety/policy.py (177) — destructivo universal
- **Evalúa tool_name+args, NO el lenguaje del usuario**: `ConditionalRule(process_kill, force=True)` → destructivo. Patterns de terminal (rm -rf, format, taskkill /f), sensitive paths (system32\config). → Nuestro `safety.classify_tool_call` es equivalente (lo extendimos con email.send).
- **GOD_MODE env** que bypasea todo (solo sesión interactiva del dueño). → Nosotros tenemos `enable_safety` config.
- **Lookup dinámico del registry de tools** (`spec.is_destructive`) en vez de lista paralela. → Mejor que mantener dos listas; verificar nuestro approach.

---

## E. adapters/ — el puente a llama.cpp

### adapters/tool_call_repair.py (344) — reparación de tool-calls malformados de Gemma 4
Tres casos que Gemma 4 produce y rompen el parser:
1. **Trailing garbage**: `{"action":"open"}```json...` → `extract_balanced_json_prefix` (tracking de depth + escape state).
2. **Truncated JSON** (max_tokens cliff): `{"a":"hel` → `repair_truncated_json` cierra con defaults; `{"a":1,"b":` → dropea la key parcial.
3. **Tool name mal**: "SYSTEM_INFO"→"system_info", "Functions.GUI.click"→"gui" (segment fallback), "gui()"→"gui".
- → **Parcialmente cubierto**: nuestro `reasoning.py::_extract_balanced_json` ya maneja balanced+truncated. Pero **`normalize_tool_name` (case/segment/underscore fallback) NO lo tenemos** — y Gemma 4 sí mis-casea nombres. Gap menor real.

---

## F. tools/ — automatización Windows (la joya para GUI)

Resumen de técnicas con umbrales (de uia_snapshot, gui_universal, gui, apps, cef, deeplinks):

- **Árbol UIA → TEXTO** para el LLM (no VLM): `[e42] button "Install"`. max_elements=400, max_chars=8000, depth_cap=8, refs reasignables vía RuntimeId.
- **Foco Windows "golden"**: AllowSetForegroundWindow(ASFW_ANY) + ALT-press sintético + AttachThreadInput fallback + IsIconic→SW_RESTORE. → Es nuestro `win_focus.py`; coincide.
- **Off-screen pero con children**: en CEF (Steam/Discord) el contenedor está offscreen pero los botones no → NO skipear si tiene children.
- **Cascading GUI**: deeplink → UIA-fuzzy(rapidfuzz, boost a Button) → OCR(PaddleOCR, conf≥65) → Gemma4-vision(enable_thinking=false, conf 0.6). Con vision-locate **cache turn-scoped 15s**.
- **frame_diff verifier** multi-monitor: `mss.monitors[0]` (virtual screen, no primary), threshold >16/canal.
- **CEF a11y flag**: `--force-renderer-accessibility=complete --enable-features=UiaProvider`, relanzar DETACHED. Detección CEF por DLLs (libcef.dll, chrome_elf.dll).
- **Resolución universal de apps**: procesos vivos → Get-StartApps (nombres en idioma del user) → Start Menu .lnk → PATH. Scoring con `difflib SequenceMatcher ≥0.75` cross-lingual (calculator↔calculadora). Normaliza ®™© + acentos.
- **Steam library enum** desde registry + libraryfolders.vdf + appmanifest_*.acf. Cache 5min.
- **Allow-list deeplinks + HKCR** (`is_protocol_registered`) + fallback web si el esquema no está registrado.

→ Varias coinciden con lo nuestro (foco, deeplinks parciales). Las **nuevas para nosotros**: árbol-UIA-a-texto con refs, cascading completo, frame_diff verifier, CEF flag, app-resolver con SequenceMatcher.

---

## G. Lo que las versiones VIEJAS tenían y v5 PERDIÓ (rescatables)

`11_lecciones` dice "Carter crece por acumulación"; al migrar a v5 (limpieza) se
perdieron módulos que estaban BIEN. Los rescatables para nosotros:

| Módulo perdido | Versión | Qué hacía | ¿Nos sirve? |
|---|---|---|---|
| **reply_checks.py** | v4 | anti-echo (Jaccard>0.7), anti-generic, **anti-unverified-claim** (afirma "está abierto" sin haber leído estado) | **SÍ** — nuestro reply_validator solo cubre el caso "Listo". Anti-unverified-claim es valioso para honestidad. |
| **context_compaction.py** | v3 | compactación al 80% ctx + **tool-pair batching** (10+ tools → "Used: X,Y,Z") + agent_invisible | Parcial — tenemos agent_compaction.py; verificar si hace tool-pair batching. |
| **error_taxonomy.py / error_classifier.py** | v3/v4 | clasificador determinista de errores (RETRY/SKIP/REPLAN/ABORT) con shortcut por tipo + LLM fallback | **SÍ** — candidato #2. v4 hybrid (determinista + LLM solo si hace falta). |

> Lección meta: NO repetir el patrón de Carter (acumular sin medir). Cada rescate
> con gate + medición. Lo perdido en v5 NO siempre era malo — a veces era buena
> ingeniería borrada en una limpieza demasiado agresiva.
