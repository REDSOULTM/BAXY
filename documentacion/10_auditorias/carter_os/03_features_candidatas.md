# 03 — Features que Carter v5 tiene y nosotros NO (candidatos priorizados)

Sólo cosas que (a) verifiqué que NO tenemos, (b) encajan en vram4, (c) son
universales (no hardcode por idioma/app). Cada una con ROI/riesgo/esfuerzo y un
veredicto honesto. **Ninguna se aplica a ciegas: medir en nuestro stack.**

---

## ⭐ CANDIDATO 1 — Active memory recall (recall pre-turno) — `memory/active_recall.py`

**Qué es:** ANTES de la llamada principal al LLM, una side-call corta a memoria
que recupera hechos relevantes al mensaje actual y los inyecta como contexto.
Portado de OpenClaw (`extensions/active-memory`).

**Ejemplo que resuelve (del propio módulo):**
> User: "abre el proyecto del laboratorio"
> Sin active-recall: el LLM no sabe qué es → pregunta o abre algo mal.
> Con active-recall: recall encuentra `{proyecto_lab: C:\projects\lab_v2}` y lo
> inyecta → el LLM emite `filesystem(open, path)`.

**Por qué nos sirve:** es el complemento ACTIVO de nuestra memoria en capas (inv 2).
La nuestra es pasiva (mete hechos relevantes al prompt por similitud). Active-recall
va un paso más: resuelve referencias del usuario a entidades guardadas ANTES de que
el LLM decida. Tiene circuit-breaker (si recall falla N veces, se desactiva por
cooldown — no quema latencia).

**Diferencia con lo que ya hicimos:** nuestra `memory_retrieval.build_memory_section`
ya hace recall semántico por turno. Active-recall sería elevar eso a "resolver el
slot e inyectarlo como hecho explícito redactado". Solapamiento ~60% — habría que
ver si aporta sobre lo que ya tenemos o es redundante.

- **ROI:** Medio-Alto (mejora comandos con referencias a cosas guardadas).
- **Riesgo:** Bajo (circuit-breaker, best-effort).
- **vram4:** Sí (reusa el encoder).
- **Veredicto:** Evaluar SI nuestra memoria en capas no cubre ya el caso. Medir
  con 10 comandos tipo "abre el proyecto X" donde X está en memoria.

---

## CANDIDATO 2 — Error classifier explícito (Mark-XXXIX / `04_dossier` §6)

**Qué es:** clasificador del error en `{RETRYABLE, SKIPPABLE, REPLAN_NEEDED, ABORT}`
en el error-path. Hoy, cuando un GUI click falla, ReAct reintenta IGUAL (no sabe
que ya falló). Con classifier: `gui_click_failed(target_not_found)` → REPLAN con
estrategia distinta (ej. buscar por screenshot+OCR).

**Por qué nos sirve:** Inv 3 ya lo identificó y yo dije "parcialmente cubierto por
el loop_detector". Carter es más fuerte: el loop_detector CORTA el loop, pero no
DECIDE una estrategia alternativa. El classifier enruta a replan/skip/ask con
presupuesto por CLASE de error (no contador global).

- **ROI:** Alto para fallos de GUI (un patrón real tuyo: "manda al canal equivocado").
- **Riesgo:** Bajo (idempotente, no se clasifica a sí mismo; cae a heurística por error-code).
- **vram4:** Sí (es código determinista; el dossier sugiere mini-LLM 350ms SOLO en error-path, opcional).
- **Veredicto:** Buen candidato. Empezar SIN LLM (clasificación por error-code/string), medir reducción de retries inútiles.

---

## CANDIDATO 3 — `loop/detection.py` 5º patrón `no_progress`

**Qué es:** N tool-calls consecutivos sin que cambie NINGÚN `evidence_key`
registrado → loop semántico aunque args difieran.

**Estado nuestro:** tenemos `record_evidence` + `evidence_keys_changed` y el
warning_count se resetea con evidencia. PERO no hay un detector explícito
"global_count subió N y evidence_keys no creció → stuck".

- **ROI:** Medio (caza loops que los 4 patrones actuales no ven).
- **Riesgo:** Muy bajo (es una condición extra en `detect_stuck`).
- **vram4:** Sí (puro conteo).
- **Veredicto:** Barato y aditivo. Portar la condición de Carter a nuestro
  `loop_detection.py::detect_stuck`. ~15 líneas.

---

## CANDIDATO 4 — GUI cascading + Chromium accessibility flag (dossier 05)

**Qué es (2 partes):**
1. **`--force-renderer-accessibility=complete`** al lanzar Steam/Discord/Spotify/
   Slack: desde Chrome 138 (jun-2025) Chromium expone UIA nativa; sin el flag, el
   árbol de esas apps CEF está vacío para UIA.
2. **Cascading deeplink→UIA→OCR** + usar `click_input` (mouse físico) en vez de
   `Invoke()` pattern (que falla en CEF custom-render).

**Por qué nos sirve:** complementa mi Inv 8 (UIA-first). Hoy si intentás controlar
Discord/Spotify por UIA probablemente falle (árbol vacío). El flag lo desbloquea.

- **ROI:** Alto para control fino de apps Electron/CEF (Discord, Spotify, Slack, VSCode).
- **Riesgo:** Bajo (un wrapper de lanzamiento; reversible).
- **vram4:** Sí (no toca el LLM).
- **Veredicto:** Buen candidato cuando ataquemos GUI de apps CEF. Verificar primero
  si tus apps target son CEF (Discord/Spotify sí lo son).

---

## CANDIDATO 5 — Allow-list de deeplinks + fallback web (patterns §A)

**Qué es:** lista cerrada `{steam, spotify, discord, slack, vscode, ms-settings,
obsidian}` validada contra HKCR; si el LLM inventa un esquema no registrado
(`youtube://`, `github://` no existen en Win11) → fallback automático a
`web_open_url("https://<app>.com")` con `ok=True, fallback=True`.

**Por qué nos sirve:** evita que el modelo alucine URIs rotas (Pattern A de Carter,
11 casos). Barato (~60 líneas) y casi sin riesgo.

- **ROI:** Medio. **Riesgo:** Muy bajo. **vram4:** Sí.
- **Veredicto:** Aditivo y seguro. Verificar primero si ya resolvemos esto en
  `microagents.py` (tenemos algo de protocol handling).

---

## CANDIDATO 6 — Outcome multi-estado PARTIAL (verifier orchestrator)

**Qué es:** en vez de PASS/FAIL binario, estados `{COMPLETED, PARTIAL,
TOOL_OK_VERIFIER_INCONCLUSIVE, FAILED, NEEDS_USER}`. PARTIAL es honesto cuando ≥1
paso verifica pero no todos.

**Estado nuestro:** tenemos `completion_status` con varios valores
(needs_confirmation, attempted, etc.) y mission_goal. Solapamiento alto.

- **ROI:** Bajo-Medio (más honestidad en misiones multi-paso).
- **Riesgo:** Bajo. **Veredicto:** Probablemente ya cubierto por mission_goal +
  completion_status. Revisar si falta el estado PARTIAL explícito.

---

## Lo que NO recomiendo traer

- **Refactor a estructura modular tipo v5** (agent.py < 500 LOC): Inv 0/T5 ya lo
  evaluó — ROI bajo si el sistema se estabiliza, riesgo de regresión alto. Carter
  lo hizo porque arrastraba debt de 4 generaciones; nosotros no.
- **Multi-profile con carpeta por tier** (`profiles/tier_Ngb/agent.py`): nosotros
  ya tenemos perfiles por VRAM con un solo agent + config. La duplicación de
  agent.py por tier es MÁS debt, no menos.
- **faster-whisper-large-v3-turbo**: ya decidimos Parakeet-TDT-v3 (más rápido en
  CPU). Carter usa whisper-turbo; no es upgrade para nosotros.
- **El bench 540 de Carter**: es su matriz. El nuestro es smoke_e2e + cacería en vivo.

## Priorización final (por ROI/riesgo, para decidir con RED)

| Prioridad | Candidato | Esfuerzo | Acción previa obligatoria |
|---|---|---|---|
| **1** | `no_progress` en loop_detection (#3) | ~15 LOC | ninguna, es aditivo y barato |
| **2** | Error classifier sin LLM (#2) | ~80 LOC | medir % retries inútiles hoy |
| **3** | Chromium a11y flag para CEF (#4) | wrapper | confirmar apps target son CEF |
| **4** | Allow-list deeplinks + fallback (#5) | ~60 LOC | grep si microagents ya lo hace |
| **5** | Active-recall (#1) | ~120 LOC | medir si memoria en capas ya cubre |
| —  | PARTIAL outcome (#6) | — | revisar si mission_goal ya lo da |

**Nada de esto antes de un eval-set** que mida el estado actual, salvo #1 y #5
que son aditivos seguros. El resto: número primero (CLAUDE.md: medí, no celebres).
