# 06 — Matriz de gaps VERIFICADA contra nuestro código

Cada hallazgo de Carter (v5 + legacy + OpenClaw) cruzado por `grep` contra
`gemma4_agent/`. Estado real, no asumido. Ordenado por valor.

Leyenda: ✅ ya lo tenemos · ⚠️ parcial · ❌ gap real · 🚫 no aplica/descartar

| # | Idea de Carter | ¿Nosotros? | Evidencia (grep nuestro código) | Veredicto |
|---|---|---|---|---|
| 1 | **Loop `no_progress`** (N tools sin cambiar evidence_key) | ⚠️ | `loop_detection.py` tiene `record_evidence`/`evidence_keys_changed` pero NO el detector explícito | **GAP barato (#1)** — ~15 LOC, aditivo |
| 2 | **Anti-unverified-claim** (reply afirma "está abierto" sin leer estado) | ❌ | `reply_validator.py` solo cubre el patrón "Listo" literal; no hay anti-echo ni anti-claim | **GAP real** — honestidad, ~40 LOC |
| 3 | **Trivial short-circuit** ("ok"/"gracias"→reply canned SIN LLM) | 🚫 | RED lo VETÓ (2026-05-23): respuesta enlatada = hardcode frágil/monolingüe. El LLM responde, siempre. Regla nueva en CLAUDE.md. | **DESCARTADO por principio** — no por técnica |
| 4 | **Error classifier** (RETRY/SKIP/REPLAN/ABORT determinista + LLM fallback) | ❌ | no existe; el loop_detector corta pero no decide estrategia | **GAP** (#2 audit previa) — alto ROI GUI |
| 5 | **normalize_tool_name** (case/segment fallback: SYSTEM_INFO→system_info) | ⚠️ | `reasoning.py::_extract_balanced_json` cubre JSON balanced+truncado, NO el nombre mal-caseado | **GAP menor** — Gemma 4 mis-casea |
| 6 | **Active-recall pre-turno** (resuelve "el proyecto X"→path antes del LLM) | ⚠️ | memoria en capas (inv 2) es PASIVA; no resuelve referencias activamente | **Evaluar** (#5 audit) — solapa ~60% |
| 7 | **CEF a11y flag** (`--force-renderer-accessibility=complete`) | ❌ | no lo seteamos al lanzar apps CEF | **GAP** — desbloquea UIA de Discord/Spotify |
| 8 | **Árbol UIA→texto con refs** (`[e42] button "Install"`) para el LLM | ⚠️ | tenemos tool `uia` (find/click) pero no el snapshot-textual-con-refs que el LLM consume | **Evaluar** — potente para GUI compleja |
| 9 | **frame_diff verifier** (pantalla PRE/POST, multi-monitor) | ❌ | solo aparece el nombre en loop_detection, no como verificador GUI | **Evaluar** — anti-fake-success en clicks |
| 10 | **Cascading GUI** (deeplink→UIA→OCR→vision con cache 15s) | ⚠️ | tenemos UIA-first + OCR fallback (mi inv 8) pero no el cascading completo con vision-locate cache | **Evaluar** |
| 11 | **App-resolver SequenceMatcher 0.75** (calculator↔calculadora) | ⚠️ | tenemos `app_discovery.py` (Get-StartApps, ya arreglado cp1252); verificar si usa fuzzy cross-lingual | **Verificar/mejorar** |
| 12 | **Allow-list deeplinks + HKCR + fallback web** | ⚠️ | `microagents.py` maneja algo de protocolos; no la allow-list+fallback completa | **GAP menor** (#4 audit) — ~60 LOC |
| 13 | **Secret detection estructural en memoria** (no guardar API keys) | ❌ | memory.py no filtra secretos al guardar | **GAP de seguridad menor** |
| 14 | **context_builder: truncar tool_result con marcador** | ✅ | `compact_tool_result` + `middle_ellipsis` + `compact_json` ya lo hacen | OK |
| 15 | **Prefijo estable / append-only history** | ⚠️ | RIESGO de layout (ver 02): verificar orden estable | **Medir** (riesgo A) |
| 16 | **Honesty: promover dato del tool si dijo "Listo"** | ⚠️ | tenemos breadcrumbs/stitch pero no la promoción auto del dato | **Evaluar** |
| 17 | **mission_goal arg-aware** (deeplink search≠open_target) | ⚠️ | tenemos mission_goal.py; verificar si distingue por args | **Verificar** |
| 18 | **Durable state atomic write** | ⚠️ | tenemos sessions.py; verificar atomic write-then-move | **Verificar** |
| 19 | **Workspace files editables (SOUL/USER/AGENTS.md)** | ❌ | no existe | **Evaluar** — personalización sin código |
| 20 | **Refactor modular (agent.py<500 LOC)** | 🚫 | nuestro agent.py ~3.3k | **NO** (Inv 0/T5: no rinde si nos estabilizamos) |
| 21 | **Multi-profile carpeta-por-tier** | 🚫 | tenemos perfiles con un agent+config | **NO** (más debt) |
| 22 | **whisper-turbo / qwen3 specifics** | 🚫 | Parakeet ya elegido; Qwen3 es otro stack | **NO** |
| 23 | **Per-app hardcodes** (Carter v4 los tenía) | ✅ | VERIFICADO: NO los tenemos (mejor que v4) | OK |

---

## Top accionables (re-priorizado tras el análisis profundo)

### Tier 1 — aditivos seguros y baratos (hacer sin eval-set)
1. **`no_progress` en loop_detection** (#1) — ~15 LOC, caza loops que los 4 patrones no ven.
2. **Trivial short-circuit** (#3) — "ok"/"gracias"/"dale" → reply canned sin LLM. Ahorra 4-7s por turno de smalltalk. Universal (lista cerrada multilingüe, como el yes/no de Jarvis que ya hicimos). **Mayor ROI de latencia percibida de toda la auditoría.**
3. **Anti-unverified-claim** (#2) en reply_validator — afirma estado sin haberlo leído → corregir. Honestidad.

### Tier 2 — alto ROI, requieren medir
4. **Error classifier** (#4) — empezar sin LLM (por error-code), medir reducción de retries inútiles.
5. **CEF a11y flag** (#7) — desbloquea control de Discord/Spotify (apps que usás).
6. **normalize_tool_name** (#5) — robustez de tool-calls de Gemma 4.

### Tier 3 — evaluar si el núcleo ya cubre
7. Active-recall (#6), árbol-UIA-textual (#8), frame_diff (#9), cascading GUI (#10) — solapan con cosas que ya tenemos; medir si aportan.

### Verificaciones rápidas (no features, auditar lo nuestro)
- #15 layout de prompt estable (riesgo A de doc 02).
- #11 app-resolver: ¿usa SequenceMatcher cross-lingual?
- #17 mission_goal: ¿es arg-aware?
- #18 sessions: ¿atomic write?

---

## Conclusión del análisis profundo

Carter (especialmente v5 + lo bueno perdido en v3/v4) es un **espejo del mismo
asistente** del que se puede extraer ingeniería concreta. Tras leer el código real:

- **Confirmado:** vamos bien en lo grande (loop, verificación, universal, foco,
  sin hardcodes — incluso MEJOR que Carter v4 en eso).
- **3 gaps baratos y claros** que recomiendo cerrar ya (Tier 1): no_progress,
  trivial short-circuit, anti-unverified-claim.
- **El resto** (GUI cascading, active-recall, error classifier) son potentes pero
  necesitan número antes de tocar — y para eso hace falta el eval-set.

La lección meta de Carter (`crece por acumulación, -13pts por cambiar 4 cosas a la
vez`) **aplica a nosotros**: cerrar los 3 de Tier 1 de a uno, con gate y medición.
Nada a ciegas.
