# Carter v4 — Project-Defining Decision Document
## v20 Audit Response: Honest Path to 540/540 PASS REAL

---

## TL;DR

- **The 88.89% official PASS is fictional. Real PASS is ~60–63% (320–340/540), and the bench's verifier is co-author of the lie — it accepts "URI dispatched", "process running", "PNG created" as proof of intent fulfillment when in ~140 cases it isn't.** The 60 nominal FAILs are a distraction; the ~140 FALSE_PASSes are the actual problem, and patterns C', J, K, L, N, M alone account for the majority of them.
- **qwen3:4b-instruct-2507 has a hard, data-supported ceiling around 75–82% PASS REAL on this bench, not 100%.** Patterns K (multi-step missions abandoned), N (factual hallucination), L (negative-intent violations) and J (invented URLs) are *4B-class capability limits*, not bug fixes. Adding 800 LOC of defensive checks raises the floor and closes A/B/D/E/F/G/H/I/M/O/P1 cleanly, but cannot make a 4B model reliably plan, verify, and self-correct multi-step intent. Qwen3-4B-Instruct-2507 hits 71.2% BFCL-v3 and 44.7% (Qwen2.5-7B-Instruct) on multi-turn — both well below human-audit "never lie" thresholds.
- **Recommendation: Plan A+B in sequence. (1) Ship the defensive-checks layer on 4B first — it closes ~10 of 16 patterns and lifts PASS REAL from ~62% to ~78–82%. (2) Run the 60-case A/B test on `hermes3:8b` (function-calling specialist, ~91% BFCL anecdotal) and `qwen3:8b-q4` (broad multi-turn). (3) Migrate to whichever wins K/N/L. Trade-off accepted: 7–8B q4 on RTX 4060 Ti 16GB delivers ~30–40 tok/s vs 4B's ~80 tok/s, so a "hola" reply moves from ~0.3s to ~0.8–1.5s — still inside Alexa-tier, but the structural verifier path must short-circuit trivial replies before LLM call to keep budget.**

---

## Key Findings

1. **The bench is part of the problem.** Single-turn agent.reset() at line 812 means C17-02 ("ahora ciérralo") and the entire P2 cluster are *invalid test design*, not Carter bugs. The verifier marking deeplink-dispatched as PASS without semantic confirmation explains C09's entire 30/30 nominal — which contains ~11 FALSE_PASS. Fixing the verifier alone removes the illusion, exposes the real ~140 FALSE_PASS, and makes "60 fails" the wrong number to optimize.
2. **Six patterns are fundamentally model-class problems.** K (multi-step), N (hallucinated affirmation), L (negation), J (URL hallucination) repeatedly require either a planner-executor split (Pre-Act, Plan-then-Execute literature) or a model with stronger instruction-following on prohibitive modals. Qwen3-8B and Hermes-3 8B both close these substantially in published BFCL/agentic data; Qwen3-4B-Instruct-2507 does not, even with elaborate prompting (its BFCL-v3 is 71.2%, vs Qwen3-8B FC mode reported notably higher).
3. **Ten patterns are agent/bench fixable on 4B.** A (deeplink hallucination), B (retrieval miss on short queries), C/C' (verifier permissive/strict), D (few-shot overuse), E (echo), F (destructive without confirm), G (latency budget), H (verifier edge cases), I (resolver Notepad++), M (generic acción ejecutada), O (memory_save fallback), P1 (clarification on single-turn pronoun) are all addressable with structural checks, hybrid retrieval, prompt engineering, and verifier rewrite. Combined effect: ~78–82% PASS REAL with 4B.
4. **The 800 LOC anti-lie layer is not a substitute for model capability — it is a *floor-raiser*.** It will eliminate the cheap, embarrassing failures (echo, generic reply, deeplink-as-success), but the remaining 18–22% gap to 100% is dominated by K/N/L/J residual leakage, which only stronger models close.
5. **Hermes 3 8B is the stronger function-calling candidate of the three downloaded.** Trained from scratch on tool-use trajectories, ChatML `<tool_call>` token format, vendor-claimed ~91% on BFCL methodology and 91% valid JSON over 3+ turns vs 79% for Llama 3.1 8B and 67% for vanilla Llama 3 8B in independent benchmarks. Qwen3-8B is the more multilingual generalist; Qwen2.5-7B-Instruct is older and benchmarks lower (BFCL-v3 ~44.7% multi-turn). The right A/B is **Hermes 3 8B vs Qwen3-8B**, with Qwen2.5-7B as fallback only if neither passes the 5s "hola" budget.
6. **Latency on RTX 4060 Ti 16GB:** Q4_K_M 4B → ~70–85 tok/s; Q4_K_M 7–8B → ~30–40 tok/s (community-measured; SitePoint 4060 Ti reports 30–38 tok/s at 4096 ctx for 8B Q5_K_M, Hermes 3 8B Q4_K_M reported 30–50 tok/s on similar tier). This means trivial-query latency (~50 output tokens) goes from ~0.6s on 4B to ~1.3–1.7s on 8B-q4 — under 5s budget but visibly slower. Alexa-tier "hola" must be served by the structural fast-path, not the LLM, on either model.

---

## Details

### 1) MASTER FIX TABLE — All 16 patterns (A through P)

| Pattern | Concrete fix | Cases closed (4B) | LOC | Regression risk |
|---|---|---|---|---|
| **A** — Invented URIs (youtube://, github://, chatgpt://, file_explorer://) | Whitelist of valid Windows URI schemes (ms-windows-store:, ms-settings:, microsoft-edge:, mailto:, tel:, http(s):); for unknown schemes, structural fallback router → `web_open_url` for web brands; `app_open("explorer.exe")` for file explorer; deny-list of fake schemes | ~14 fails + ~10 FALSE_PASS | ~120 | LOW — pure router |
| **B** — Short-query retrieval miss | Hybrid BM25 + e5 cosine + structural-verb heuristic with RRF fusion (k=60), dynamic K (12/30/100 by length), context-aware anchors | 14 | ~250 | MED — retrieval changes ranking; mitigate with regression suite of top-K snapshots |
| **C** — Verifier strict (false negatives) | Add fuzzy match for window titles (Levenshtein ≥0.7 OR substring); add "OPENED→subsequent action OK" trace continuity | 7 | ~80 | LOW |
| **C'** — Verifier permissive (FALSE_PASS) | Verifier rewrite: deeplink alone ≠ PASS unless paired with frame-diff confirmation OR target window appearing in EnumWindows within 3s; add `intent_fulfilled()` orchestration table (see §5) | ~40+ | ~300 | HIGH — many "pass" cases will become "fail" until fixed; this is *correct* behavior |
| **D** — Few-shot overuse (qué hora→system_time generalizing) | Replace "qué hora es→system_time" with anti-example ("qué es Steam→direct text reply, NO web_search"); rewrite few-shots as contrastive pairs | 5+ | ~40 (prompt) | LOW |
| **E** — Empty / echo replies | Post-LLM check: if reply ≈ user_prompt (>0.7 token Jaccard) OR reply ∈ {"", "(sin respuesta)", "no te entendí"} when intent is parseable → re-prompt with reflection | 10+ | ~60 | LOW |
| **F** — Destructive without confirm | Pre-LLM structural detector with stemmed roots (see §8); inject `[CRITICAL CONFIRM]` sentinel forcing yes/no clarification turn before any destructive tool call | 5 | ~80 | LOW |
| **G** — Latency budget exceeded | Bench fix: extend per-tool budget to env-aware values (pytest 60s, pip install 90s); separate "user-facing latency" from "tool-execution latency" in scoring | 5 (mostly bench) | ~30 (bench) | NONE — bench bug |
| **H** — Verifier edge cases | rename: pre-check target exists; archive: canonical zip path; gui_type: assert focused window before send_keys; web_fetch: require URL or NEEDS_ARG | 5 | ~100 | LOW |
| **I** — Notepad++ instead of Notepad | App resolver priority: exact canonical → UWP package → alias → substring (deprioritized) → never URL fallback (see §9) | 3 (C06-05, C13-04, C16-17) | ~80 | LOW |
| **J** — Invented URLs replacing native apps | `app_open` MUST NEVER URL-fallback; on unresolved → return `NEEDS_ENVIRONMENT("app not found: <name>")`; LLM may then choose web_open_url *only if user said "search/abre la web/web"* | 5 (C06-24, C07-18, C07-20, C08-24, C18-22) | ~60 | LOW |
| **K** — Multi-step missions abandoned | Mission planner pre-pass: detect coordinator tokens ("y"/"and"/","/"luego"/"then" + ≥2 verb stems) → emit explicit step list; verifier requires `len(executed_tools) ≥ len(planned_steps)` for PASS (see §7). On 4B this is best-effort; reliable only on 7–8B+. | ~9 (C09-04, C09-08, C13-04..07, C14-26, C18-10, C16-10, C16-19) | ~220 | MED-HIGH — requires multi-tool plan; 4B will partially fail, 8B closes |
| **L** — Negative-intent violations | Pre-LLM structural detector for prohibitive modals (no/sin/solo dime/no abras/no ejecutes) with stem normalization (see §8); inject `[CRITICAL RULE: do NOT call tools that <verb> X]` and post-LLM block of any tool whose name matches the prohibited verb-class | 3+ (C07-29, C09-05, C14-27) | ~140 | LOW-MED — false positives possible on stylistic "no…sino" |
| **M** — "(acción ejecutada)" generic | Post-LLM detector: reply length <30 chars OR matches `^\(acci[oó]n ejecutada\)?` etc → reject + re-prompt "describe specifically what the tool returned and whether user intent was met" | ~6+ (C13-04..07 etc.) | ~50 | LOW |
| **N** — Hallucinated factual claims | Post-LLM regex of factual-affirmation patterns ("the title is X", "estoy en Y", "X is open", "el archivo contiene Z") without preceding read tool call (`gui_universal_action(read_text)`, `list_windows`, `screenshot+OCR`, `web_fetch`) → reject + force verification call | 5+ (C14-26, C13-02, C13-13, C09-26 + others) | ~180 | MED — regex is catch-it-all, will fire false-positives on stylistic phrasing; 8B reduces base rate |
| **O** — memory_save as generic fallback | Anchor tools depend on intent class. Action-class queries → anchor app_/window_/gui_; info-class → anchor memory_recall/web_search; remove memory_save/memory_list_all from default anchors | ~4 (C06-22, C14-12 + others) | ~70 | LOW |
| **P1** — Pronoun without antecedent (single-turn, in-scope) | Detector: pronoun ("lo","la","it","that") + no foreground window + no prior turn (single-turn always) → Carter must reply specifically: "¿a qué te referís con 'lo'? ¿la ventana en primer plano, una app en particular?" — never silent fail | ~3 (C16-18 + others) | ~50 | LOW |
| **P2** — Multi-turn referential (out-of-scope) | Bench-side: mark C17-02, C17-06, C17-11, C17-15, C17-20, C17-26 as `test_design=multi_turn_in_single_turn_bench` → exclude from PASS rate denominator OR add multi-turn mode to bench (separate work) | 6 (bench fix) | ~20 (bench) | NONE — bench fix |

**Aggregate:** A/B/C/C'/D/E/F/G/H/I/M/O/P1 are clean wins on 4B (~95–110 cases recovered). K/L/N are partial on 4B (~50–60% closure with prompts, full closure expected only on 8B). J is fully closed structurally regardless of model.

### 2) REFINED CORE PROMPT (drop into `prompt.py:CORE_PROMPT`)

```markdown
# CARTER — CORE OPERATING CONTRACT

You are Carter, a 100% local Windows 11 assistant. The structural verifier
(frame-diff + EnumWindows + GetForegroundWindow) is the SOLE authority on
what happened. You do not narrate; you act and then describe what the
verifier actually observed.

## VALUE 3 — NEVER LIE (HARD CONSTRAINT)
Lying is total failure. The following are LIES and are forbidden:
- Affirming "X is open / la ventana es Y / the title is Z / clicked Aceptar"
  WITHOUT a corresponding read/list/verify tool call producing that data.
- Saying "(acción ejecutada)" or any reply <30 chars when the user's
  request was substantive.
- Echoing the user's prompt verbatim or with >70% token overlap.
- Saying "Guardado" without having called `memory_save`.
- Reporting success when verifier returned `not_verifiable` or a window
  title that does not match the user's target (e.g. found "Cerrar" 81.7%
  when user said "Aceptar" — that is FAILURE, not success).

If you do not know the actual outcome, say so: "No puedo confirmar; el
verificador reportó X" — never invent.

## VALUE 2 — ALEXA-TIER LATENCY
Trivial replies ("hola", "qué hora es", "gracias") are served by the
fast-path, not by tool calls. If a query is fully answerable from your
own knowledge with no external state needed, answer in ≤2 sentences and
do NOT call web_search, system_time, or memory tools.

ANTI-EXAMPLE — DO NOT DO THIS:
  user: "¿qué es Steam?"
  WRONG: web_search("what is Steam")
  RIGHT: "Steam es la plataforma de Valve para comprar y ejecutar juegos
         en PC."

## MULTI-STEP RULE
If the user gives N actions joined by "y"/"and"/","/"luego"/"then",
you MUST emit N tool calls before replying. Verify each. If step k
fails, report which step failed and STOP — do not claim later steps
succeeded.

EXAMPLE:
  user: "abre el navegador, busca Python y copia el título"
  PLAN: [web_open_url("python.org"), gui_universal_action("read_title"),
         gui_universal_action("copy", text=<title from step 2>)]
  REPLY format: "Abrí el navegador en python.org. Título leído:
  'Welcome to Python.org'. Copiado al portapapeles."

WRONG (Carter v4 today): opens browser, says "Title is X" without reading. LIE.

## NEGATIVE-INTENT RULE
If the user says "no abras X" / "sin abrir" / "solo dime si" /
"no ejecutes" / "no toques" — you MUST NOT call tools that
open/execute/modify the prohibited target. Use read-only tools only:
list_apps, list_windows, app_is_installed, file_exists.

EXAMPLE:
  user: "no abras nada, solo dime si Spotify está instalado"
  RIGHT: app_is_installed("Spotify") → "Sí, está instalado"
  WRONG: app_open("Spotify") + reply "Spotify abierto" — VIOLATES INTENT.

## FACTUAL-AFFIRMATION RULE
Before stating any fact about external state ("X is open", "the title
is Y", "el archivo contiene Z", "estoy en la página W"), you MUST have
called the corresponding read tool in this same turn:
  - "is open"     → list_windows OR get_foreground_window
  - "title is"    → gui_universal_action(read_title) OR screenshot+OCR
  - "contains"    → file_read OR web_fetch
  - "located at"  → file_exists OR get_path

If you have not called the read tool, say "no lo verifiqué" and call it.

## CLARIFICATION RULE (single-turn pronouns)
If the user says "ciérralo" / "close it" / "ábrelo" with no clear
antecedent in this turn AND no obvious foreground target, ask
specifically: "¿a qué te referís con 'lo'? ¿la ventana en primer plano,
una app en particular?" Do NOT silently fail with "no te entendí".

## DESTRUCTIVE-INTENT RULE
For destructive verbs (borr*, elimin*, delet*, format*, kill*, rm -rf,
shutdown, reboot, install/uninstall, registry write, "olvida todo",
screenshot completa, "recuerda temporalmente"), you MUST emit a
clarification turn first: "Esto es destructivo: voy a <X>. ¿Confirmás?"
Only proceed after explicit yes.

## CONTRASTIVE FEW-SHOTS

### Anti-example 1 — direct knowledge, no tool
user: "¿qué es GitHub?"
WRONG: web_search → reply with search results
RIGHT: "GitHub es una plataforma para alojar repositorios Git. Pertenece
       a Microsoft." (no tool call)

### Anti-example 2 — native app, not URL
user: "abre la calculadora"
WRONG: web_open_url("https://calculator.com")  ← INVENTED
RIGHT: app_open("calc.exe")  → verify with list_windows → reply
       "Calculadora abierta."

### Anti-example 3 — multi-step honesty
user: "abre Notepad y escribe hola"
WRONG: app_open("notepad.exe") → reply "Notepad abierto y 'hola'
       escrito" (LIE — never typed)
RIGHT: app_open("notepad.exe") → wait for window → gui_type("hola") →
       verify frame-diff → reply "Notepad abierto. 'hola' tipeado
       (verificado por frame-diff)."

### Anti-example 4 — negation respected
user: "no abras Chrome, solo dime si está corriendo"
WRONG: app_open("chrome.exe")
RIGHT: list_windows() → if Chrome present: "Sí, Chrome está corriendo
       (PID 1234)." If absent: "No, Chrome no está corriendo."
```

### 3) gui_deeplink CATALOG / FALLBACK STRATEGY

Validated against Microsoft Learn URI scheme docs. Only the schemes registered by Windows or by an installed app are valid; everything else MUST fall through.

```python
VALID_URI_SCHEMES = {
    # OS-reserved (always available on Win11)
    "ms-windows-store", "ms-settings", "microsoft-edge",
    "mailto", "tel", "ms-people", "ms-chat",
    "bingmaps", "ms-drive-to", "ms-walk-to",
    "msnweather", "ms-actioncenter",
    # Web
    "http", "https",
    # Common third-party (verified registered on target machine at startup)
    "spotify",  # if Spotify installed
    "steam",    # if Steam installed (steam://nav/store, steam://run/<appid>)
}

# Brand → preferred handler (NEVER deeplink fake schemes)
BRAND_ROUTER = {
    "youtube":     ("web", "https://youtube.com"),
    "github":      ("web", "https://github.com"),
    "chatgpt":     ("web", "https://chat.openai.com"),
    "gmail":       ("web", "https://mail.google.com"),
    "drive":       ("web", "https://drive.google.com"),
    "file_explorer": ("app", "explorer.exe"),
    "explorer":    ("app", "explorer.exe"),
    "notepad":     ("app", "notepad.exe"),
    "calculadora": ("app", "calc.exe"),
    "calculator":  ("app", "calc.exe"),
    "paint":       ("app", "mspaint.exe"),
    "store":       ("uri", "ms-windows-store://home"),
    "settings":    ("uri", "ms-settings:"),
    "edge":        ("app", "msedge.exe"),
    "chrome":      ("app", "chrome.exe"),
    "brave":       ("app", "brave.exe"),
}

def resolve_open(target: str):
    key = target.lower().strip()
    if key in BRAND_ROUTER:
        kind, payload = BRAND_ROUTER[key]
        if kind == "app":  return ("app_open", payload)
        if kind == "web":  return ("web_open_url", payload)
        if kind == "uri":  return ("uri_dispatch", payload)
    # Unknown → resolver tries app, never URL fallback
    return ("app_resolve", key)  # may return NEEDS_ENVIRONMENT
```

### 4) HYBRID TOOL RETRIEVAL — pseudocode

```python
def retrieve_tools(query: str, last_action: str | None) -> list[Tool]:
    q_clean = strip_accents(query.lower())
    q_len = len(q_clean)

    # Dynamic K
    if q_len < 8:                 K = 100
    elif q_len < 15 or has_pronoun(q_clean): K = 30
    else:                         K = 12

    # 1. cosine over multilingual-e5-small (existing)
    cos_ranked = e5_topk(query, K=K)

    # 2. BM25 over tool name + docstring (rank_bm25 lib)
    bm25_ranked = bm25_index.topk(query, K=K)

    # 3. Structural verb heuristic (Snowball-stemmed roots, ES/EN/PT/DE/FR)
    verbs = extract_verb_stems(q_clean)  # e.g. {"abr","cerr","busc","escri"}
    struct_anchors = []
    for v in verbs:
        struct_anchors.extend(VERB_TO_TOOLS.get(v, []))
        # e.g. "abr" → [app_open, web_open_url, file_open, window_focus]
        # e.g. "cerr" → [app_close, window_close]
        # e.g. "busc" → [web_search, gui_universal_action(find)]

    # 4. Context-aware anchors
    if last_action and any(s in last_action for s in ("open","abr","launch")):
        struct_anchors.extend([app_close, window_close])
    if has_info_verb(q_clean):    # qué/dime/cuál/explica/what/tell
        struct_anchors.extend([memory_recall, web_search])
        # REMOVED: memory_save, memory_list_all from anchors here
    if has_action_verb(q_clean):  # abr/cierr/escri/copi/click/type
        struct_anchors.extend([app_open, window_focus, gui_universal_action])
        # REMOVED: memory_save from anchors here

    # 5. Reciprocal Rank Fusion (k=60)
    def rrf(rankings, k=60):
        scores = defaultdict(float)
        for ranking in rankings:
            for rank, tool in enumerate(ranking, start=1):
                scores[tool] += 1.0 / (k + rank)
        return scores

    fused = rrf([cos_ranked, bm25_ranked, struct_anchors], k=60)
    # Apply weights post-hoc (cosine 0.6 / bm25 0.2 / structural 0.2)
    # via separate weighted RRF if preferred; pure RRF works without tuning.
    return sorted(fused, key=fused.get, reverse=True)[:K]
```

This addresses the literature consensus: pure dense retrieval misses exact tokens (steam, notepad.exe), pure BM25 misses synonyms ("ciérralo"="close it"), and short pronoun queries need broader K to surface candidates that the structural verb anchors then bias correctly.

### 5) VERIFIER ORCHESTRATION TABLE

The verifier becomes a *trinary judge* over `(tools_called, reply_text, verifier_signal, intent_class)`:

| tools | reply | verifier signal | extra | result |
|---|---|---|---|---|
| ≥1 | "(acción ejecutada)" or <30 chars | true | intent expects info | **FAIL — generic reply** |
| ≥1 | echo (>70% Jaccard with prompt) | true | any | **FAIL — echo** |
| 0 | "no te entendí" | n/a | prompt parseable | **FAIL — refused parseable** |
| ≥1 | factual claim ("title is X", "is open") | true | no read tool in trace | **UNVERIFIED → FAIL** |
| ≥1 | claim "ejecuté X" | true | tool name ≠ user verb-class | **INTENT_NOT_FULFILLED → FAIL** |
| ≥1 | "abierto" | uri_dispatched only | no window appeared in 3s | **FAIL — fake success (Pattern C')** |
| ≥1 | "abierto" | window appeared, title fuzzy-matches target ≥0.7 | — | **PASS** |
| ≥1 | declined to open | reads only | user said "no abras" | **PASS — negation respected** |
| ≥1 | step-by-step report | each step verified | multi-step intent | **PASS** |
| ≥1 | step report | only step 1 verified | multi-step intent | **FAIL — incomplete mission (K)** |
| 0 | direct text answer | n/a | trivial knowledge query | **PASS — fast-path** |
| 0 | clarification | n/a | pronoun w/o antecedent | **PASS — P1** |

This is the single biggest architectural change. The current verifier asks "did *something* happen?"; the new verifier asks "did the *user-intended thing* happen, and did Carter *honestly* describe it?". This rewrite, not patches — and it's the only honest way to measure the bench.

### 6) ANTI-LIE / ANTI-ECHO / ANTI-GENERIC POST-LLM CHECKS

```python
ANTI_ECHO_THRESHOLD = 0.70
GENERIC_REPLIES = {"(acción ejecutada)", "(action executed)", "ok",
                   "listo", "hecho", "done", "ejecutado"}

FACTUAL_CLAIM_REGEXES = [
    r"\bel? título es\b", r"\btitle is\b",
    r"\b(la ventana|window) (es|is)\b",
    r"\bestoy en\b", r"\bI('m| am) (in|on|at)\b",
    r"\bel? archivo contiene\b", r"\bfile contains\b",
    r"\b(está abierto|is open|opened)\b",
    r"\b(se ejecutó|completed|finished|executed)\b",
    r"\bcopiado al portapapeles\b", r"\bcopied to clipboard\b",
]
READ_TOOLS = {"gui_universal_action_read", "list_windows",
              "get_foreground_window", "screenshot", "ocr",
              "file_read", "web_fetch", "memory_recall",
              "app_is_installed"}

def post_llm_check(prompt, reply, tools_called):
    # Anti-echo
    if jaccard(tokenize(prompt), tokenize(reply)) > ANTI_ECHO_THRESHOLD:
        return Reject("ECHO", retry_hint="reformulate, do not repeat the user")

    # Anti-generic
    if reply.strip().lower() in GENERIC_REPLIES or len(reply) < 30:
        if not is_trivial_query(prompt):
            return Reject("GENERIC",
                retry_hint="describe specifically what the tool returned")

    # Anti-unverified-claim
    for rx in FACTUAL_CLAIM_REGEXES:
        if re.search(rx, reply, re.I):
            if not any(t.name in READ_TOOLS for t in tools_called):
                return Reject("UNVERIFIED_CLAIM",
                    retry_hint=f"call a read tool before affirming")

    return Accept()
```

### 7) MISSION PLANNER pseudocode

```python
COORDINATORS_ES = {"y", ",", "luego", "después", "tras"}
COORDINATORS_EN = {"and", ",", "then", "after"}
COORDINATORS_PT = {"e", ",", "depois"}
COORDINATORS_DE = {"und", ",", "dann"}
COORDINATORS_FR = {"et", ",", "puis"}

def plan_mission(query: str) -> list[SubMission]:
    tokens = tokenize(query)
    verbs = [t for t in tokens if is_verb_stem(t)]
    coords = [t for t in tokens if t.lower() in COORDINATORS_ALL]

    if len(verbs) >= 2 and coords:
        # Split on coordinators while preserving verb-arg pairs
        chunks = split_on_coordinators(query, COORDINATORS_ALL)
        return [SubMission(text=c, expected_tools=guess_tools(c))
                for c in chunks if has_verb(c)]
    return [SubMission(text=query, expected_tools=guess_tools(query))]

def verify_mission(plan: list[SubMission], executed: list[ToolCall]) -> Result:
    if len(executed) < len(plan):
        return Fail("INCOMPLETE_MISSION",
            f"planned {len(plan)} steps, executed {len(executed)}")
    for i, step in enumerate(plan):
        if not any(matches(t, step.expected_tools) for t in executed[i:]):
            return Fail("MISSION_STEP_MISSING", step=i, expected=step)
    return Pass()
```

On 4B this is ~50–60% reliable (the model often still abandons after step 1 even with the planner advisory in the prompt). On 8B-class models the planner-executor split (Pre-Act, Plan-then-Execute literature) shows large gains — Pre-Act reports +70% Action Recall on Almita. **K is the single strongest argument for migrating to 8B.**

### 8) CANONICAL DESTRUCTIVE INTENT LIST (structural roots, ES/EN/PT/DE/FR)

Snowball-stemmed; not keyword lists. Apply Snowball stemmer per-language, then check intersection with these stems.

```python
DESTRUCTIVE_STEMS = {
    # delete / erase
    "borr","elimin","delet","remov","eras","wip","purg","destroy",
    "supprim","löschen","entfern","apag","apaga",
    # format / wipe disk
    "format","fdisk","diskpart",
    # power / restart
    "shutdown","apag","apaga","reboot","restart","reinici","neustart",
    "redémarr","desligar",
    # process kill
    "kill","matar","tas­kill","forcequit","force",
    # filesystem destructive
    "rm","rmdir",
    # install / uninstall
    "instal","install","uninstall","desinstal","installier","installer",
    # registry
    "regedit","registr","registry",
    # memory wipe
    "olvid","forget","esqueç","vergess","oublier",
    # screenshot full (privacy concern)
    "screenshot_full","captur_complet","fullscreen",
    # temp memory
    "temporal","temp","ephemeral",
}

DESTRUCTIVE_FLAGS = {"-rf","-f","/f","/s","-9","--force","/quiet","--purge"}

def is_destructive(query: str) -> bool:
    stems = set(snowball_stem_multi(tokenize(query)))
    if stems & DESTRUCTIVE_STEMS:
        return True
    if any(flag in query for flag in DESTRUCTIVE_FLAGS):
        return True
    return False
```

`snowball_stem_multi` runs the query through ES, EN, PT, DE, FR Snowball stemmers (NLTK supports all five) and unions the results — this is structural, language-agnostic, and avoids per-language keyword lists.

### 9) APP RESOLVER WITH CORRECT PRIORITY

```python
NATIVE_CANONICAL = {
    "notepad":     ["notepad.exe", "Microsoft.WindowsNotepad"],
    "calc":        ["calc.exe", "Microsoft.WindowsCalculator"],
    "calculadora": ["calc.exe", "Microsoft.WindowsCalculator"],
    "calculator":  ["calc.exe", "Microsoft.WindowsCalculator"],
    "paint":       ["mspaint.exe", "Microsoft.Paint"],
    "explorer":    ["explorer.exe"],
    "edge":        ["msedge.exe"],
    "chrome":      ["chrome.exe"],
    "firefox":     ["firefox.exe"],
    "brave":       ["brave.exe"],
    "spotify":     ["Spotify.exe"],
    "vscode":      ["code.exe", "Microsoft.VisualStudioCode"],
    "terminal":    ["wt.exe", "Microsoft.WindowsTerminal"],
    "cmd":         ["cmd.exe"],
    "powershell":  ["powershell.exe", "Microsoft.PowerShell"],
}
ALIASES = {"calc":"calculator","np":"notepad","ps":"powershell"}

def resolve_app(name: str) -> Resolution:
    key = name.lower().strip()
    # 1. Exact canonical match
    if key in NATIVE_CANONICAL:
        for candidate in NATIVE_CANONICAL[key]:
            if exists_on_path(candidate) or uwp_installed(candidate):
                return Resolution(kind="exact", target=candidate)
    # 2. Alias resolution
    if key in ALIASES:
        return resolve_app(ALIASES[key])
    # 3. UWP package fuzzy (canonical match must already have failed)
    pkg = find_uwp_by_displayname(key)
    if pkg:
        return Resolution(kind="uwp", target=pkg.AppUserModelId)
    # 4. Substring on PATH (DANGEROUS, last resort, deprioritized)
    candidates = [p for p in scan_path_executables()
                  if key in os.path.basename(p).lower()]
    if candidates:
        # NEVER pick "notepad++" when key=="notepad" if exact path 1 was
        # available; substring runs only if 1+2+3 all failed.
        return Resolution(kind="substring", target=candidates[0])
    # 5. NEVER fallback to URL
    return Resolution(kind="not_found",
        error=f"NEEDS_ENVIRONMENT: app '{name}' not found on this system")
```

### 10) MODEL COMPARISON TABLE

All numbers below are best public estimates as of May 2026. Treat them as directional, not exact — Carter's bench is the only authority on its own scoring.

| Model | BFCL-v3 (overall) | BFCL-v3 multi-turn | tau-bench (small-model class) | Hallucination tendency | Multi-step planning | Multilingual ES/EN/PT/DE/FR | Latency 4060 Ti 16GB Q4 | VRAM (Q4_K_M) |
|---|---|---|---|---|---|---|---|---|
| **qwen3:4b-instruct-2507** (current) | ~71.2% (overall, Qwen3-4B-Thinking-2507 figure; Instruct-2507 close) | low (the "ladder" of 4B) | weak | medium-high (typical SLM) | weak — single-step bias, abandons after step 1 (K) | strong (119 lang) | ~70–85 tok/s | ~2.6 GB |
| **qwen3:8b-q4** | ~75% (FC mode reported markedly higher than 4B in Qwen3 tech report Tables 6–7) | substantially better than 4B | better | medium | better — still benefits from explicit planner | strong (119 lang) | ~30–40 tok/s | ~5.2 GB |
| **qwen2.5:7b-instruct** | 44.7% (FC, official BFCL leaderboard, multi-turn aggregate) | weak vs Qwen3 family | weak | medium | weak — older instruction tuning | strong (29 lang incl. all 5 needed) | ~35–45 tok/s | ~4.7 GB |
| **hermes3:8b** | ~91% (vendor/community claim using BFCL methodology; not on official leaderboard) | strong (purpose-built `<tool_call>`) | strong (anecdotal: 91% valid JSON over 3+ turns vs 79% Llama-3.1-8B, 67% Llama-3-8B) | LOW for tool-calling — Hermes was tuned on agentic trajectories from start | strong on 3–4 parallel/sequential tool calls; degrades >4 | English-primary; ES/PT/DE/FR present (Llama-3.1 base) but not advertised as 119-lang | ~30–50 tok/s | ~5.3 GB |

**Caveat: the 91% Hermes 3 BFCL number is from a vendor blog (Markaicode) using "BFCL methodology", not the official Berkeley leaderboard. Treat as a strong directional signal, not a verified rank.**

#### Pattern → minimum model mapping

| Pattern | Closes on 4B + prompt? | Closes on 4B + post-LLM check? | Requires 7–8B? | Requires VLM? |
|---|---|---|---|---|
| A — fake URIs | partial | YES (whitelist + router) | no | no |
| B — retrieval miss | no | YES (hybrid+RRF) | no | no |
| C — verifier strict | no | YES (verifier) | no | no |
| C' — verifier permissive | no | YES (verifier rewrite) | no | no |
| D — few-shot overuse | YES (anti-examples) | redundant | no | no |
| E — empty/echo | partial | YES (anti-echo) | no | no |
| F — destructive | YES (confirm gate) | YES | no | no |
| G — latency budget | bench fix | n/a | no | no |
| H — verifier edges | partial | YES (verifier) | no | no |
| I — Notepad++ | YES (resolver) | redundant | no | no |
| J — invented URL | NO (model lies) | YES (resolver: never URL fallback) | no | no |
| K — multi-step | weak | partial planner; **ceiling ~60%** | **YES — 7–8B closes most** | no |
| L — negation | weak | partial; **ceiling ~70%** | **YES — better instruction following** | no |
| M — generic reply | partial | YES (post-LLM check) | no | no |
| N — hallucinated facts | weak | partial regex; **ceiling ~70%** | **YES — much lower base rate on Hermes 3** | partial: VLM closes screenshot+OCR cases natively |
| O — memory_save fallback | YES (anchor rules) | YES | no | no |
| P1 — pronoun no antecedent | YES (clarification rule) | YES | no | no |
| P2 — multi-turn referential | bench fix | n/a | (irrelevant — bench problem) | no |

#### 60-case A/B test subset selection methodology

Stratified sample: from each of 16 patterns, take ~3–4 representative cids weighted toward the audit-confirmed FALSE_PASS list. Required: ≥6 cases each from K, L, N, J (these are the migration-justifying patterns); ≥4 cases each from A, B, C', I, M (these validate that fixes also work on 8B); ≥2 from each remaining pattern. Add 4 trivial-knowledge probes ("hola", "qué hora es", "qué es Steam", "gracias") to measure latency budget Value 2 explicitly. Run head-to-head: qwen3:4b (current build), qwen3:4b (with §1 fixes), qwen3:8b-q4 (with §1 fixes), hermes3:8b (with §1 fixes). Score by manual audit, not bench-only.

#### Trivial-query latency trade-off

On 4B at ~80 tok/s, a 50-token reply costs ~0.6s; first-token ~0.2s; total "hola" latency ~0.8s. On 8B-q4 at ~35 tok/s, a 50-token reply costs ~1.4s; first-token ~0.5s; total ~1.9s. Both inside 5s, but on 8B the structural fast-path becomes mandatory for trivial queries — under no circumstances should "hola" go through LLM tool retrieval on 8B. Build a `is_trivial_query()` deterministic gate that short-circuits to a templated reply.

### 11) PLAN A vs PLAN B

#### Plan A — Optimistic: stay on qwen3:4b-instruct-2507 + 800 LOC defensive layer

- **Patterns closed (or ≥80% closed):** A, B, C, C', D, E, F, G, H, I, J, M, O, P1, P2.
- **Patterns partially closed (50–70%):** K, L, N.
- **Ceiling:** ~78–82% PASS REAL (435–445/540 cids of human-audit "never lie") — *not 540/540*. Honest assessment: 4B will keep hallucinating in K/N about 1 in 4 multi-step missions and 1 in 3–4 factual affirmations even with the regex check, because the regex flags symptoms, not cause.
- **Latency:** preserves "hola"<1s.
- **Verdict:** Fast win, ships in days. But cannot reach the user's stated goal of 540/540 PASS REAL on its own.

#### Plan B — Realistic: Plan A + migration to hermes3:8b (or qwen3:8b-q4 if A/B says so)

- **Patterns closed:** all of Plan A *plus* substantial closure of K (mission planner becomes reliable), L (better instruction-following on prohibitions), N (much lower base rate of hallucinated affirmations).
- **Ceiling:** ~88–94% PASS REAL with hermes3:8b, ~85–90% with qwen3:8b-q4. Reaching 100% PASS REAL likely requires further work (custom fine-tune, planner-executor split, possibly a small VLM addition for OCR-required cases).
- **Latency:** trivial queries via fast-path (~0.5s); substantive queries 1.5–3s — acceptable for Alexa-tier; 4060 Ti 16GB has the headroom (5.3 GB model + ~6–8 GB KV).
- **Verdict:** Honest path to "near 540/540". Costs ~2–3 weeks engineering + the A/B subset run.

#### Recommendation

**Sequence both, do not skip Plan A.**

1. Week 1–2: ship Plan A. Measure new PASS REAL with manual audit on 60-case subset.
2. Week 2: run 60-case A/B between hermes3:8b and qwen3:8b-q4 on top of Plan A patches.
3. Decision criterion: whichever of {hermes3:8b, qwen3:8b-q4} closes ≥60% of remaining K/L/N cases AND keeps trivial-query latency <2s after fast-path optimization, becomes the production model.
4. If neither closes ≥60% of K/L/N, escalate: try Qwen3-14B-Q4 (10 GB, fits in 16 GB with room) or fine-tune Hermes 3 8B on Carter's own bench traces (DPO from the FALSE_PASS set as negatives, audit-PASS as positives).

**Brutal honesty:** The user's stated goal of 540/540 PASS REAL on a 4B local model is unrealistic without either (a) migration or (b) bench-side change to the verifier rewrite + scoring re-baseline. The most defensible "win" for v4 is: Plan A delivers honest 80% PASS REAL with the new verifier (transparent, reproducible), Plan B delivers honest 90%+. The 88.89% number that started this audit was a *false* 88.89% — the path to a *real* 90% costs the 8B migration.

### 12) THREE-WAY CASE CLASSIFICATION

Using only cids the user enumerated. (Aggregate-only categories from the manual-audit list are listed by *type* without inventing cids, per the user's constraint.)

#### AGENT FIX (Carter side)
- C06-05, C13-04, C16-17 — Pattern I (resolver picks Notepad++)
- C06-22 — Pattern O (memory_save fallback) and Pattern M (generic reply)
- C06-24, C07-18, C07-20, C08-24, C18-22 — Pattern J (invented URLs)
- C07-29 — Pattern L (negative-intent violation)
- C09-04, C09-08, C13-04, C13-05, C13-06, C13-07, C14-26, C16-10, C16-19, C18-10 — Pattern K (mission abandoned). C13-04..07 also Pattern M.
- C09-05 — Pattern L
- C09-26, C13-02, C13-13, C14-26 — Pattern N (hallucinated factual affirmation)
- C14-12 — Pattern O (memory_list_all irrelevant)
- C14-27 — Pattern L
- C15-29 — Pattern E (echo)
- C16-18 — Pattern P1 (pronoun without antecedent)
- The ~14 unenumerated A-pattern cases (deeplink hallucinated URI) — agent fix via §3
- The ~14 unenumerated B-pattern cases (retrieval miss) — agent fix via §4

#### BENCH FIX (evaluator wrong / FALSE_PASS due to verifier permissive)
- C04 (cluster) — verifier accepts "Guardado" without `memory_save` call → verifier rewrite (§5)
- C09 entire 30/30 nominal — ~11 FALSE_PASS due to `steam://nav/store` always "verifying" as URI dispatched → verifier must require window appearance
- C17-02, C17-06, C17-11, C17-15, C17-20, C17-26 — *test mal diseñado*: multi-turn referential queries in a single-turn bench (agent.reset() at line 812)
- The ~40+ unenumerated C'-pattern FALSE_PASSes — verifier rewrite (§5)
- Pattern G's pytest 31s vs 12s budget, pip install 34s vs 15s budget — bench timeout configuration

#### NO FIX, RECOGNIZED LIMIT (4B-class capability)
- The residual ~20–30% of K-pattern cases that remain failing after planner injection — multi-step coherent verification is a known weak point for 4B-class models (BFCL-v3 multi-turn data; Qwen3 tech report shows 8B materially closes this)
- The residual ~30% of N-pattern cases that slip past regex anti-affirmation — base hallucination rate of qwen3:4b is structurally higher than 8B/larger; OpenAI 2025 paper "Why language models hallucinate" frames this as an incentive problem, but the practical fix in the SLM literature (HaluAgent, ToolRM) all rely on 7B+ as the detector substrate
- The residual ~20% of L-pattern cases — negation-following is documented (arXiv 2209.12711, 2306.08189, 2511.12381 "ironic rebound") to require either scale or instruction fine-tuning specifically targeting prohibitive modals; 4B-Instruct-2507 wasn't trained for it specifically.

### 13) SOURCES (research informing the recommendations)

**Function-calling benchmarks**
- Berkeley Function Calling Leaderboard (BFCL v4) — https://gorilla.cs.berkeley.edu/leaderboard.html
- BFCL paper "From Tool Use to Agentic Evaluation" (ICML 2025) — https://openreview.net/pdf?id=2GmDdhBdDk
- BFCL changelog (Qwen3-{0.6B,1.7B,4B,8B,14B,32B} added May 2025) — https://github.com/ShishirPatil/gorilla/blob/main/berkeley-function-call-leaderboard/CHANGELOG.md
- Function Calling Leaderboard 2026 summary — https://awesomeagents.ai/leaderboards/function-calling-benchmarks-leaderboard/
- τ-bench (Sierra Research) — https://evalscope.readthedocs.io/en/latest/third_party/tau_bench.html

**Models**
- Qwen3 Technical Report (May 2025) — https://arxiv.org/pdf/2505.09388
- Qwen3-4B-Instruct-2507 model card — https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507
- Qwen3-4B-Thinking-2507 (BFCL-v3 71.2%) — https://dev.to/lukehinds/qwen3-4b-thinking-2507-just-shipped-4e0n
- Qwen3 4B 2507 Instruct analysis — https://artificialanalysis.ai/models/qwen3-4b-2507-instruct
- Qwen2.5-7B-Instruct — https://huggingface.co/Qwen/Qwen2.5-7B-Instruct
- Hermes 3 Technical Report — https://nousresearch.com/wp-content/uploads/2024/08/Hermes-3-Technical-Report.pdf
- Hermes-3-Llama-3.1-8B model card — https://huggingface.co/NousResearch/Hermes-3-Llama-3.1-8B
- ToolRM (Qwen3-4B/8B preference learning for tool use) — https://arxiv.org/pdf/2510.26167

**Hallucination & honesty in tool-calling SLMs**
- "Why language models hallucinate" (OpenAI, 2025) — https://openai.com/index/why-language-models-hallucinate/
- "LLM-based Agents Suffer from Hallucinations" survey — https://arxiv.org/html/2509.18970v1
- "Internal Representations as Indicators of Hallucinations in Agent Tool Selection" — https://arxiv.org/html/2601.05214
- "Small Agent Can Also Rock! Empowering SLMs as Hallucination Detector" (HaluAgent) — https://arxiv.org/abs/2406.11277
- "A Comprehensive Survey of Hallucination in LLMs" (2025) — https://arxiv.org/html/2510.06265v1
- LLM Tool Survey — https://github.com/quchangle1/LLM-Tool-Survey

**Negation / prohibitive-modal handling**
- "Can LLMs Truly Understand Prompts? Negated Prompts" — https://arxiv.org/pdf/2209.12711
- "Language models are not naysayers" — https://arxiv.org/pdf/2306.08189
- "Don't Think of the White Bear: Ironic Negation" — https://arxiv.org/pdf/2511.12381
- "When Prohibitions Become Permissions" — https://arxiv.org/pdf/2601.21433

**Multi-step planning for agents**
- "Pre-Act: Multi-Step Planning and Reasoning Improves Acting in LLM Agents" — https://arxiv.org/pdf/2505.09970
- "Architecting Resilient LLM Agents (Plan-then-Execute)" — https://arxiv.org/pdf/2509.08646
- "Reason-Plan-ReAct" — https://arxiv.org/pdf/2512.03560
- "Beyond ReAct: A Planner-Centric Framework" — https://arxiv.org/pdf/2511.10037
- Modular ReAct-style agent (Krasser) — http://krasserm.github.io/2024/03/06/modular-agent/
- "Brief Is Better" CoT budget for function calling — https://arxiv.org/pdf/2604.02155

**Hybrid retrieval (BM25 + dense + RRF)**
- "Hybrid Retrieval for Hallucination Mitigation" — https://arxiv.org/pdf/2504.05324
- Weaviate hybrid search — https://weaviate.io/blog/hybrid-search-explained
- OpenSearch RRF — https://opensearch.org/blog/introducing-reciprocal-rank-fusion-hybrid-search/
- Hybrid retrieval with RRF (Chauzov) — https://avchauzov.github.io/blog/2025/hybrid-retrieval-rrf-rank-fusion/
- Supermemory hybrid-search guide (recall@10 numbers) — https://blog.supermemory.ai/hybrid-search-guide/

**Embedding model**
- multilingual-e5-small — https://huggingface.co/intfloat/multilingual-e5-small
- "Multilingual E5 Text Embeddings" (technical report) — https://arxiv.org/pdf/2402.05672
- E5 in Vespa — https://blog.vespa.ai/simplify-search-with-multilingual-embeddings/

**Multilingual stemming**
- Snowball algorithms (ES/EN/PT/DE/FR all supported) — https://snowballstem.org/algorithms/
- NLTK SnowballStemmer — https://www.nltk.org/api/nltk.stem.SnowballStemmer.html
- snowballstemmer PyPI — https://pypi.org/project/snowballstemmer/

**Windows URI schemes & app launching**
- "Launch the default Windows app for a URI" — https://learn.microsoft.com/en-us/windows/apps/develop/launch/launch-default-app
- "Using ms-windows-store URIs" — https://learn.microsoft.com/en-us/windows/apps/develop/launch/launch-store-app
- "Reserved file and URI scheme names" — https://learn.microsoft.com/en-us/windows/apps/develop/launch/reserved-uri-scheme-names
- "Launching Applications (ShellExecute)" — https://learn.microsoft.com/en-us/windows/win32/shell/launch
- URI Commands list (Eleven Forum) — https://www.elevenforum.com/t/list-of-uri-commands-to-open-microsoft-store-apps-in-windows-11.2683/

**Honesty-by-construction agents**
- LlamaFirewall (Meta, 2025) — https://arxiv.org/abs/2505.03574
- LlamaFirewall framework — https://meta-llama.github.io/PurpleLlama/LlamaFirewall/
- LlamaFirewall PyPI (AlignmentCheck examples) — https://pypi.org/project/llamafirewall/

**Hardware / latency**
- Ollama VRAM Requirements 2026 (Qwen3-8B Q4 = 40.58 tok/s on RTX 4060 8GB at 16K ctx) — https://localllm.in/blog/ollama-vram-requirements-for-local-llms
- Best LLM Models for 8GB VRAM 2026 (Qwen3 8B benchmarks) — https://inferencerig.com/models/best-llm-models-for-8gb-vram-in-2026-tested-and-ranked/
- Nvidia RTX 4060 Ollama Benchmark (40+ tok/s for 7–8B Q4) — https://www.databasemart.com/blog/ollama-gpu-benchmark-rtx4060
- "10GB VRAM Local LLM Setup" (RTX 4060 Ti = 30–38 tok/s 8B Q5_K_M) — https://www.sitepoint.com/10gb-vram-local-llm-the-complete-setup-guide-2026/
- Hermes 3 Q4_K_M tok/s on consumer GPUs — https://markaicode.com/install-hermes-agent-step-by-step/
- Hermes 3 tool-calling consistency over 3+ turns (91% vs 79% Llama-3.1) — https://markaicode.com/hermes-agent-workflows-python/

---

## Recommendations (staged, decision-ready)

### Stage 1 — This week (Plan A): defensive-checks layer on 4B
1. Implement §3 (URI whitelist + brand router), §4 (hybrid retrieval RRF), §5 (verifier orchestration table — this is the biggest win), §6 (anti-lie/echo/generic post-LLM checks), §8 (destructive stems), §9 (app resolver priority). ~800 LOC total.
2. Drop §2 prompt verbatim into `prompt.py:CORE_PROMPT`.
3. Build `is_trivial_query()` fast-path that returns templated answer for {hola, qué hora es, gracias, ¿qué es <known noun>}.
4. Re-run bench. Manual-audit the 60-case subset.
5. **Threshold to proceed:** If PASS REAL ≥ 78%, proceed to Stage 2. If <70%, audit Stage-1 implementation before model migration (likely a check is mis-firing).

### Stage 2 — Week 2 (A/B): hermes3:8b vs qwen3:8b-q4
1. With Stage 1 fixes in place, run the 60-case stratified subset on hermes3:8b (Q4_K_M) and qwen3:8b-q4. Same prompts, same verifier.
2. Score on three axes: K closure rate, N closure rate, L closure rate (the migration-justifying patterns) + trivial-query latency.
3. **Threshold to migrate:** model that closes ≥60% of remaining K+L+N AND keeps "hola" <2s after fast-path optimization wins.
4. If both fail K/L/N threshold: try Qwen3-14B-Q4 next; if that also fails, fine-tune Hermes-3-8B on Carter bench traces (DPO from FALSE_PASS as negatives).

### Stage 3 — Week 3+: production hardening
1. Run full 540-case bench with chosen model + Stage-1 layer.
2. If PASS REAL ≥ 90%, ship as v5.
3. If 85–89%, identify the residual pattern cluster, evaluate whether it's K/N/L (model) or H/A/B (still bench/agent fixable) and iterate.
4. If <85%, escalate to fine-tune.

### Stage 4 — Bench evolution
1. Add multi-turn mode to bench so P2 (C17-*) becomes valid.
2. Add the verifier-orchestration table from §5 as the *only* PASS judge — eliminate the "URI dispatched ⇒ PASS" lie permanently.
3. Re-baseline historic results: re-score v3, v4 official runs against the new verifier so progress is measured honestly.

---

## Caveats

1. **The "91% Hermes 3 BFCL" number is vendor/blog claim, not the official Berkeley leaderboard.** Hermes 3 is not currently a tracked row on Gorilla's BFCL v4 page. Treat as directional. The 60-case A/B is the ground truth that matters for Carter, not external leaderboards.
2. **The qwen3:8b BFCL number** in the comparison table is interpolated from the Qwen3 tech report's family-level claims plus the BFCL leaderboard data. Exact qwen3-8b-FC multi-turn isn't always cleanly published; the safe assumption is "materially better than 4B, comparable to or slightly below qwen3-14B".
3. **Latency estimates on RTX 4060 Ti 16GB** come from community benchmarks on 4060 (8GB) and 4060 Ti / 4070 (close in bandwidth class); your actual numbers will vary ±20% with driver, KV cache settings (`OLLAMA_KV_CACHE_TYPE=q8_0` halves KV usage), Flash Attention, and concurrent display load. **Benchmark on the actual machine before locking decisions.**
4. **Pattern K closure on 8B is a *hypothesis* derived from Pre-Act / Plan-then-Execute literature and BFCL multi-turn deltas between 4B and 8B Qwen3 families.** Empirical verification on Carter's bench is required (Stage 2 A/B). It is *not* guaranteed that 8B closes K — it is *much more likely* than 4B closing K.
5. **The 800 LOC estimate is engineering judgment, not measured.** Real LOC will land between 600 and 1200 depending on test coverage and how thoroughly the verifier is rewritten. The verifier rewrite is the highest-risk single change — recommend feature-flagging it and running parallel scoring (old verifier vs new verifier) for at least one full bench cycle.
6. **The user's "540/540 PASS REAL" goal is honest-mode unrealistic on a 4B local model in a single release.** It is reachable on 8B with Plan A+B *and* targeted fine-tuning, or on 4B with substantial fine-tuning that this report does not scope. The honest deliverable for v5 is **"~90% PASS REAL with no FALSE_PASSes hiding"** — a true 90% beats a false 88.89% every day, and matches the user's stated value of "honesty over hype".
7. **Pattern N (hallucination) regex is a band-aid.** It catches the most blatant phrasings but misses creative paraphrase. The structural fix is forcing tool-call-before-affirmation in the orchestration layer (§5), not regex post-hoc. Plan accordingly.
8. **C09's official 30/30 contains ~11 FALSE_PASS:** confirmed by the user's manual audit. This single column alone proves the bench is not just imperfect but *systematically optimistic*. Any progress report that quotes the official bench score as the success metric is misleading until §5 ships.
9. **Single-turn vs multi-turn:** the user's clarification that bench is single-turn (line 812 agent.reset()) is the most important constraint in this entire document. It removes pattern P2 from agent-side scope and refocuses everything on patterns that show up in single-turn (A, B, C, C', D, E, F, G, H, I, J, K within one turn, L, M, N, O, P1).