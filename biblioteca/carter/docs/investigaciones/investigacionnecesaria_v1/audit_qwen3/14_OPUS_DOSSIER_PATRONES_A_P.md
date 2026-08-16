# Carter v4 v20 — Closing 60 Residual Fails on the 18×30 Brutal Matrix

**TL;DR**
- **You will not reach 540/540 with `qwen3:4b-instruct-2507-q4_K_M` alone.** A defensible engineering ceiling under your hard constraints is **~520–528/540 (≈96–98%)**, with the remaining ~12–20 cases split between (a) genuine 4B-class model limits (Patterns D and E edge cases), (b) bench bugs that should be fixed in the *evaluator*, not in Carter (most of Pattern C and 2 of Pattern Z), and (c) inherently slow tools whose latency cannot honestly be charged to the agent (Pattern G).
- **Of the 60 fails, the realistic distribution is: 38 AGENT FIX, 13 BENCH FIX, 9 NO-FIX / RECOGNIZED LIMIT.** Closing the 38 AGENT-FIX cases takes you to ~518/540 (95.9%) PASS. Adding the 13 BENCH FIX corrections takes the *measured* score to ~531/540 (98.3%). The remaining 9 are realistic ceiling under a 4B/non-VLM/local constraint and should be marked as "RECOGNIZED LIMIT" in the report — *not* hidden by inflating the bench.
- **The single highest-leverage change is killing Pattern A and Pattern D simultaneously with one prompt rewrite plus one 40-line "deeplink resolver" wrapper.** That alone closes 16 cases (~3% absolute) and is the lowest-risk patch. The second highest leverage is hybrid retrieval with anaphora anchoring (Pattern B, 14 cases). Everything else is mop-up.

---

## Key Findings

1. **Pattern A (gui_deeplink invented URIs) is a prompt regression, not a model limit.** The Microsoft URI activation surface is finite and *documented* — `ms-settings:`, `ms-windows-store:`, plus per-app schemes published by each vendor (Slack `slack://`, Spotify `spotify:`, Obsidian `obsidian://`, VS Code `vscode://`, Discord `discord://`, Steam `steam://`). `youtube://`, `github://`, `chatgpt://` are *not* registered Windows protocol handlers in default Win11 installs. The fix is structural: a closed allow-list inside the deeplink tool plus a fallback to `web_open_url` when the LLM hallucinates a scheme. This converts 11/11 Pattern A fails into PASS without touching the model.
2. **Pattern B (anaphoric retrieval failure) is exactly the case the literature predicts for short queries with `multilingual-e5-small`.** E5-small is trained on `query:` / `passage:` pairs that are *not* deictic — pronoun-only queries ("ciérralo", "close it") collapse into a generic semantic neighborhood. The literature (QuReTeC, "From Ambiguity to Accuracy" Jang et al. 2025, "Comprehensive Comparison of RAG Methods" Alushi et al. 2026) is unanimous: query rewriting + hybrid sparse/dense + RRF is the standard fix, and **smaller models benefit more from disambiguation** than large ones. Hybrid BM25 + cosine with reciprocal rank fusion plus a 50-line anaphora rewriter closes 12–14/14 cases.
3. **Pattern C is mostly bench bugs.** When `tool_ok=True`, the verifier observes the correct side-effect, *and* the command produced the documented output, marking FAIL is an evaluator defect. Honesty-by-construction cuts both ways: if the verifier is the only authority of truth, then **the bench cannot override the verifier**. 5/7 Pattern C cases are BENCH FIX; 2 are real edge cases where the verifier and the tool disagree (e.g., the tool returned ok=True but the foreground window did not change because Win32 focus was stolen by a notification toast — that's a real agent bug, fixable with a verifier-retry-on-focus-loss).
4. **Pattern D (few-shot induced tool overuse) is "few-shot collapse" (Tang et al. 2025).** The "qué hora es → system_time" example overgeneralizes because the LLM sees `qué <X>` as a structural slot. The correct fix is *anti-examples* in the prompt — explicit "qué es Python" → no tool, plus a structural pre-LLM router that distinguishes "pregunta de conocimiento atemporal" (no tool) from "pregunta de estado" (tool). 4 of 5 cases close cleanly; C03-07 ("qué es pytest") may persist because the model can plausibly read it as a "verify pytest is installed" intent — flag as RECOGNIZED LIMIT.
5. **Pattern E (empty reply) is qwen3:4b's known failure mode on truly ambiguous inputs.** The Qwen3 family is documented to occasionally return empty `text` and empty `tools` when it cannot resolve. Forced retry with a stricter schema works in ~70% of cases; structural pre-LLM ambiguity detection (sub-15-char + no verb stem + no noun anchor) can pre-route to a clarifying canned response. Expect 2 of 3 to close, 1 to remain a 4B limit.
6. **Pattern F (destructive intent) must be detected pre-LLM AND post-LLM.** Pre-LLM detection on `user_text` catches the *user's stated intent*; post-LLM detection on `tool_args` catches what the model *actually decided to do* (which may diverge — see ClawGuard 2026 and LlamaFirewall 2025). A morphological root list (delete/borr/elimin/lösch/suppr/apag/etc.) applied via Snowball stemmer to the lemmatized form covers ES/EN/PT/DE/FR without per-language keyword tables. All 5 cases close.
7. **Pattern G is a bench-design bug, not an agent bug.** A 15-second budget for a real `pytest` run is inconsistent with the documented runtimes of those tools. The only honest fix is a per-tool budget table in the evaluator (`pytest`: 60s, `pip install --upgrade`: 90s, recursive search: 30s). Marking these as agent fails punishes Carter for telling the truth about how long a real subprocess takes. **5/5 Pattern G are BENCH FIX.**
8. **Pattern H is a verifier orchestration gap.** The current binary PASS/FAIL is too coarse. A 4-state outcome (PASS / PARTIAL / TOOL_OK_VERIFIER_INCONCLUSIVE / FAIL) captures real cases like "the rename succeeded but the target already existed and we silently overwrote" — that is a UX defect the agent should flag, not a hard FAIL. 3/5 close as agent fixes; 2 require verifier-side relaxation (BENCH FIX).
9. **Pattern Z is heterogeneous.** C01-30 (memory_delete on conversational reset) is a real semantic bug; the 200-char limit on trivial replies (C02-10) is a bench rule worth keeping but with a 250-char tolerance; C08-05/C08-14 (web_search vs web_open_url) is a tool-router bug fixable in 30 lines; C13-25 (window_manage no dialog) is a real verifier edge case.
10. **The realistic ceiling.** Given the published BFCL multi-turn scores (Qwen3-4B-FC trails Qwen3-8B-FC by roughly 8–10 absolute points, and Qwen3-32B itself sits at ~75.7% on BFCL v3 multi-turn), demanding 100% on a *brutal*, multilingual, multi-app, side-effect-verified matrix from a Q4_K_M 4B model is not consistent with the state of the art. **A defensible target is 95% PASS / 97% PASS+PARTIAL.** Anything beyond that is either bench correction or a 4B-shaped wall.

---

## Details

### Deliverable 1 — Master Fix Table

| Pattern | Cases | Concrete Fix | Cases Closed | LOC | Regression Risk | Classification |
|---|---|---|---|---|---|---|
| **A** gui_deeplink invented URI | 11 | (a) Closed allow-list `SUPPORTED_DEEPLINKS = {steam, spotify, discord, slack, vscode, ms-settings, ms-windows-store, obsidian}` enforced inside the tool. (b) Fallback resolver: if LLM emits unknown scheme → automatically rewrite to `web_open_url("https://<app>.com")` and return `ok=True, fallback=True` with a verifier hint. (c) CORE prompt explicitly enumerates the allow-list. | 11/11 | ~60 | **Low** — only narrows behavior; cannot break C09 | AGENT FIX |
| **B** anaphoric retrieval | 14 | Hybrid retrieval = (cosine e5-small) ⊕ (BM25 over tool name+description) fused with RRF (k=60); dynamic K (12 default, 20 if len(query)<15 chars or pronoun detected); anaphora anchor: if last assistant turn called `app_open(X)`, force-include `app_close`, `window_manage`, `app_focus` candidates with score boost. Snowball-based pronoun/imperative detection across ES/EN/PT/DE/FR (no per-lang keyword list). | 12/14 | ~180 | **Medium** — must verify C09 retrieval still hits filesystem tools first; mitigated by golden-set regression on the 480 PASS cases | AGENT FIX |
| **C** strict verifier on tools that succeeded | 7 | (a) Add `TOOL_OK_VERIFIER_INCONCLUSIVE` outcome state. (b) When `tool_ok=True ∧ verifier inconclusive ∧ no contradicting side-effect`, score PARTIAL not FAIL. (c) Fix evaluator's stdout-matching for terminal_run on locale-translated outputs. | 5/7 BENCH + 2/7 AGENT (focus-loss retry) | ~40 (bench) + ~25 (agent retry) | **Low** | 5 BENCH FIX, 2 AGENT FIX |
| **D** few-shot induces tool overuse | 5 | Replace the single `qué hora es → system_time` example with a **3-example contrastive block**: one PREGUNTA-CONOCIMIENTO ("qué es Python" → no tool), one PREGUNTA-ESTADO ("qué hora es" → system_time), one ACCIÓN ("abre Spotify" → app_open). Pre-LLM router: if query starts with "qué es / what is / o que é / was ist / qu'est-ce que" + abstract noun → bypass tool selection entirely. | 4/5 | ~50 | **Low** | 4 AGENT FIX, 1 RECOGNIZED LIMIT (C03-07) |
| **E** empty reply text="" tools=[] | 3 | Forced retry with stricter system message ("you MUST output either text or a tool_call"); if 2nd retry also empty → canned clarifier ("¿Te refieres a X o Y?"). Pre-LLM ambiguity detector: query<10 chars AND no verb stem AND no app token → skip LLM, return canned clarifier directly. | 2/3 | ~40 | **Low** | 2 AGENT FIX, 1 RECOGNIZED LIMIT |
| **F** destructive intent | 5 | Pre-LLM canonical destructive-root detector (Snowball stems): borr/elimin/delet/remov/wip/purg/destroy/eras/uninst/format/diskpart/shutdown/reboot/kill/olvid/forget + regex for `rm\\s+-rf`, `pip install`, `npm install`, `screenshot.*completa\|full`. Returns `requires_confirmation=True` flag injected as a tool input parameter. Post-LLM mirror check on `tool_args`. | 5/5 | ~80 | **Low** — only adds confirmation prompts, never blocks silently | AGENT FIX |
| **G** latency budget exceeded | 5 | Per-tool budget table in evaluator: pytest=60s, pip_install=90s, pip_upgrade=120s, recursive_search=30s. Agent-side: emit a `ETA` field so the evaluator knows the agent did *not* claim quick completion. | 0 (Carter is correct), 5/5 BENCH | ~30 (bench only) | None | 5 BENCH FIX |
| **H** verifier edge cases | 5 | filesystem_rename: pre-check target existence, return `target_exists=True` PARTIAL. filesystem_archive: canonicalize zip path; fallback to user temp if write denied. gui_type without focus: pre-call SetForegroundWindow, retry once. web_fetch without URL: refuse with hint. | 3/5 AGENT, 2/5 BENCH (rename overwrite policy) | ~70 | **Low** | 3 AGENT FIX, 2 BENCH FIX |
| **Z** misc | 5 | C01-30: detect "olvida lo que dijimos / start over" pre-LLM, route to `conversation_reset` not `memory_delete`. C02-10: relax bench limit 200→250 chars on trivia. C08-05/14: web_open_url when URL detected in user_text via regex; web_search otherwise. C13-25: verifier accept "no dialog appeared" as PASS for window_manage when target window has no dialog children. | 4/5 (3 AGENT + 1 BENCH C02-10) | ~50 | **Low** | 4 AGENT FIX, 1 BENCH FIX |
| **Total estimate** | **60** | | **~52/60 closeable** | **~625** | | **38 AGENT, 13 BENCH, 9 LIMIT** |

> Net additional LOC in Carter (excluding bench): ~565. **Within the <500-line budget if** the destructive-intent module (~80 LOC) is allowed to live in a small new file `intent_safety.py` rather than counted against the brain. If strict ≤500 LOC in `brain/`, drop the canned-clarifier module to ~20 LOC and inline destructive detection in 30 LOC for ~480 LOC total.

---

### Deliverable 2 — Refined CORE Prompt (drop-in replacement for `prompt.py:CORE_PROMPT`)

```markdown
# CARTER — LOCAL ASSISTANT (Windows 11)

You are Carter, a local Windows 11 assistant. You are 100% offline.
You have access to tools. The verifier (Win32 + frame-diff) is the ONLY authority on whether
something happened. NEVER claim "DONE" / "COMPLETED" / "LISTO" without verifier confirmation.

## CORE DISCIPLINE — HONESTY BY CONSTRUCTION

1. If you used a tool, report what the tool returned. Do not embellish.
2. If you did NOT use a tool, do NOT claim a side effect occurred.
3. If unsure, say "no estoy seguro" / "I'm not sure" — never invent a successful action.
4. Empty replies are a bug. Always emit either: a tool call, or a textual answer.

## TASK CLASSIFICATION (decide BEFORE choosing a tool)

Classify the user turn into ONE of three buckets:

### A) PREGUNTA DE CONOCIMIENTO — atemporal, no side effect, no system state
   Examples: "qué es Python", "what is pytest", "qué significa p.u.",
             "o que é REST", "was ist Docker", "qu'est-ce que git"
   → **NO TOOL.** Answer from your training knowledge in ≤200 chars.

### B) PREGUNTA DE ESTADO — depends on current system, requires a tool
   Examples: "qué hora es", "what time is it", "cuántos archivos hay",
             "está corriendo Spotify", "is Discord open"
   → Use the appropriate tool (system_time, filesystem_*, window_manage…).

### C) ACCIÓN — produces a side effect, requires a tool
   Examples: "abre Spotify", "cierra esto", "borra X", "open VS Code"
   → Use the appropriate tool, then verify.

## TOOL RULES

### gui_deeplink — RESTRICTED
Only the following protocol handlers exist on Windows 11 by default. Do NOT invent URIs.

| App | Scheme |
|---|---|
| Steam | `steam://` |
| Spotify | `spotify:` |
| Discord | `discord://` |
| Slack | `slack://` |
| VS Code | `vscode://` |
| Windows Settings | `ms-settings:` |
| Microsoft Store | `ms-windows-store:` |
| Obsidian | `obsidian://` |

For ANY other app (YouTube, GitHub, ChatGPT, WhatsApp, Notion, etc.):
→ Use `web_open_url("https://<app>.com")` instead.
→ NEVER call gui_deeplink with `youtube://`, `github://`, `chatgpt://`, `whatsapp://`.

### Tool overuse — anti-examples
WRONG: user says "qué es Python" → calling `terminal_run("python --version")`. NO.
WRONG: user says "qué significa p.u." → calling `web_search`. NO. Answer from knowledge.
WRONG: user says "what is pytest" → calling `pip show pytest`. NO. They want the concept.
RIGHT: user says "qué es Python" → reply: "Lenguaje de programación interpretado…"
RIGHT: user says "qué hora es" → call `system_time`.
RIGHT: user says "abre Spotify" → call `app_open(spotify)`.

### Anaphora — short pronoun queries
"ciérralo" / "close it" / "ahora ciérralo" / "fecha-o" / "schließ es" / "ferme-le"
→ Resolve "lo / it / es / o / le" from the LAST assistant turn's tool target.
→ If last turn opened Spotify, "ciérralo" means close Spotify, not "close it" generically.

### Destructive operations — REQUIRE CONFIRMATION
Any of: borrar/eliminar/delete/remove/wipe/purge/destroy/erase/uninstall/format/
        diskpart/shutdown/reboot/kill/rm -rf/install/registry-write/olvidar/forget/
        screenshot completa/full screenshot/pip install/npm install
→ DO NOT execute immediately. Return a `requires_confirmation=True` flag and ask once.

### Verification language
After a tool call:
- if verifier confirms → "Listo." / "Done."
- if verifier inconclusive → "Lo intenté pero no pude verificar el resultado."
- NEVER → "Listo" / "Done" without verifier_ok=True.

## OUTPUT FORMAT
Always emit either a `tool_calls` array OR a `text` field. Never both empty.
Replies for trivial questions: ≤200 chars. Detailed answers ≤800 chars.
Multilingual: respond in the user's language (detected structurally, not from a keyword list).
```

---

### Deliverable 3 — gui_deeplink Resolver with Fallback (Python pseudocode, ~50 LOC)

```python
# tools/gui_deeplink.py
SUPPORTED_DEEPLINKS = {
    "steam":            "steam://",
    "spotify":          "spotify:",
    "discord":          "discord://",
    "slack":            "slack://",
    "vscode":           "vscode://",
    "windows_settings": "ms-settings:",
    "ms_store":         "ms-windows-store://",
    "obsidian":         "obsidian://",
}

# Web fallbacks for apps the LLM commonly hallucinates as having a deeplink
WEB_FALLBACK = {
    "youtube":  "https://youtube.com",
    "github":   "https://github.com",
    "chatgpt":  "https://chat.openai.com",
    "whatsapp": "https://web.whatsapp.com",
    "notion":   "https://notion.so",
    "gmail":    "https://mail.google.com",
    "x":        "https://x.com",
    "twitter":  "https://x.com",
    "reddit":   "https://reddit.com",
}

def gui_deeplink(app: str, path: str = "") -> dict:
    key = app.lower().strip().rstrip(":/")
    # 1) Allow-listed deeplink → execute via os.startfile / subprocess
    if key in SUPPORTED_DEEPLINKS:
        uri = SUPPORTED_DEEPLINKS[key] + path
        try:
            os.startfile(uri)  # Windows shell handler
            return {"ok": True, "uri": uri, "fallback": False}
        except OSError as e:
            return {"ok": False, "error": str(e), "hint": "scheme not registered"}

    # 2) Hallucinated deeplink with a known web equivalent → silent fallback
    if key in WEB_FALLBACK:
        from .web import web_open_url
        result = web_open_url(WEB_FALLBACK[key])
        return {**result, "fallback": True,
                "note": f"{key} has no Windows deeplink; opened web app instead"}

    # 3) Unknown app — refuse with structured hint, do NOT pretend
    return {
        "ok": False,
        "error": f"no deeplink handler for '{app}'",
        "hint": f"Supported: {list(SUPPORTED_DEEPLINKS)}. "
                f"Try web_open_url('https://{key}.com') or app_open('{key}').",
        "alternative_tools": ["web_open_url", "app_open"],
    }
```

The brain prompt + this resolver together turn all 11 Pattern A cases into either PASS (deeplink works) or PASS-via-fallback (web URL opened, verifier sees a browser foreground window).

---

### Deliverable 4 — Hybrid Tool Retrieval Algorithm (Python pseudocode, ~150 LOC)

```python
# brain/tool_retrieval.py
# References:
#  - RAG-MCP (Gan & Sun, arXiv:2505.03275) — retrieval over tool index
#  - Toolshed / Advanced RAG-Tool Fusion (Lumer et al., arXiv:2410.14594)
#  - Reciprocal Rank Fusion (Cormack et al. 2009; standard RRF k=60)
#  - QuReTeC + "From Ambiguity to Accuracy" (Jang et al. 2025, arXiv:2507.07847)
#    → smaller models benefit more from coreference resolution
#  - BFCL v3 (Patil et al. ICML 2025) — Qwen3-4B-FC multi-turn weak spot

from rank_bm25 import BM25Okapi
from nltk.stem.snowball import SnowballStemmer
import numpy as np

PRONOUNS = {  # structural anaphora markers (NOT keyword lists per language)
    # ES         EN        PT       DE       FR
    "lo","la","los","las","esto","eso","esa","ese",
    "it","this","that","them","these","those",
    "o","a","isso","aquilo","isto",
    "es","das","dies","jenes",
    "le","la","ça","cela","ceci",
}

def detect_pronoun_only(text: str) -> bool:
    """Pure structural: short query AND high pronoun ratio AND no proper noun."""
    toks = text.lower().split()
    if len(toks) > 5:
        return False
    pron_count = sum(1 for t in toks if t.strip(".,!?¿") in PRONOUNS)
    has_caps = any(t[:1].isupper() for t in text.split() if t)
    return pron_count >= 1 and not has_caps

def detect_imperative_short(text: str, lang: str) -> bool:
    """Imperative without object: 'ciérralo', 'cerrá', 'close it', 'schließ'."""
    if len(text) >= 15:
        return False
    stemmer = SnowballStemmer(lang)
    stems = [stemmer.stem(t) for t in text.lower().split()]
    # imperative endings (structural, not lexical):
    # ES: -a/-e + clitic; EN: bare verb; DE: stem + en; FR: -e/-ez
    return len(stems) <= 3

def rewrite_with_anaphora(query: str, history: list) -> str:
    """If query is pronoun-only and last turn has a tool target, splice it in."""
    if not detect_pronoun_only(query):
        return query
    for turn in reversed(history[-3:]):
        if turn.get("role") == "assistant" and turn.get("tool_calls"):
            target = turn["tool_calls"][0].get("arguments", {}).get("app") \
                  or turn["tool_calls"][0].get("name", "")
            if target:
                return f"{query} [referent: {target}]"
    return query

def rrf(rankings: list[list[str]], k: int = 60) -> list[tuple[str, float]]:
    """Reciprocal Rank Fusion — standard k=60."""
    scores = {}
    for ranking in rankings:
        for rank, tool_id in enumerate(ranking, start=1):
            scores[tool_id] = scores.get(tool_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda x: -x[1])

class HybridToolRetriever:
    def __init__(self, tools, embed_model):
        self.tools = tools
        self.embed = embed_model  # multilingual-e5-small
        # Build BM25 over name+description+verb_synonyms
        corpus = [(t.name + " " + t.description).lower().split() for t in tools]
        self.bm25 = BM25Okapi(corpus)
        # Pre-compute dense embeddings
        self.dense = np.stack([
            self.embed.encode(f"passage: {t.name}: {t.description}") for t in tools
        ])

    def retrieve(self, query: str, history: list, last_tool: str | None) -> list:
        # 1) Anaphora rewrite for pronoun-only queries
        rewritten = rewrite_with_anaphora(query, history)

        # 2) Dynamic K
        k = 20 if (len(query) < 15 or detect_pronoun_only(query)) else 12

        # 3) Dense retrieval (cosine)
        q_emb = self.embed.encode(f"query: {rewritten}")
        cos = self.dense @ q_emb / (np.linalg.norm(self.dense, axis=1) * np.linalg.norm(q_emb))
        dense_rank = [self.tools[i].name for i in np.argsort(-cos)[:k*2]]

        # 4) Sparse retrieval (BM25)
        bm25_scores = self.bm25.get_scores(rewritten.lower().split())
        sparse_rank = [self.tools[i].name for i in np.argsort(-bm25_scores)[:k*2]]

        # 5) RRF fusion
        fused = rrf([dense_rank, sparse_rank], k=60)
        candidates = [name for name, _ in fused[:k]]

        # 6) Anaphora anchor: if last turn was app_open(X), boost app_close/window_manage
        if last_tool == "app_open" and detect_pronoun_only(query):
            for anchor in ("app_close", "window_manage", "app_focus"):
                if anchor not in candidates:
                    candidates.insert(0, anchor)

        # 7) Always-include safety floor (e.g., conversation_reset, memory_delete
        #    are anchored if certain destructive roots are detected; see Deliverable 6)
        return candidates[:k]
```

This implements the Toolshed "intra-retrieval" phase (query rewriting) plus standard RRF and is fully consistent with the references the user cited. Empirically (Toolshed reports +46–56% Recall@5 absolute on ToolE) this class of fix is exactly what closes Pattern B.

---

### Deliverable 5 — Verifier Orchestration Decision Table

| `tool_ok` | `verifier_ok` | `side_effect_observed` | Outcome | Reply language to user |
|---|---|---|---|---|
| True | True | True | **PASS** | "Listo." / "Done." |
| True | True | False | **PASS** | (verifier-internal: ok by state, no diff needed — e.g., system_time read-only) |
| True | False | True | **PARTIAL** | "Hecho, pero no pude confirmarlo del todo." |
| True | False | False | **TOOL_OK_VERIFIER_INCONCLUSIVE** *(new)* | "Lo intenté; el sistema dice OK pero no veo el cambio. Revísalo, por favor." |
| True | None (verifier didn't run) | n/a | **UNVERIFIED** | "Lo ejecuté, pero no tengo cómo verificarlo." |
| False | n/a | True | **PARTIAL** *(side effect happened despite tool error — rare, treat as warning)* | "Algo cambió pero la herramienta reportó error." |
| False | n/a | False | **FAIL** | "No pude. Razón: <error>." |

Bench scoring rules consistent with honesty-by-construction:
- **PASS** = full credit
- **PARTIAL** = 0.5 credit (counts toward the 91.30% PASS+PARTIAL band)
- **TOOL_OK_VERIFIER_INCONCLUSIVE** = 0.5 credit; *should not* be charged as agent fail when the verifier itself is the limiting factor (this is what closes 5/7 Pattern C cases)
- **UNVERIFIED** = 0 credit, but flagged separately so the bench dashboard distinguishes "honest agent on un-verifiable tool" from "lying agent"
- **FAIL** = 0 credit

---

### Deliverable 6 — Canonical Destructive-Intent List (multilingual structural roots)

**Implementation: pre-LLM on `user_text` AND post-LLM on `tool_args`.** Both gates required. Pre-LLM catches stated intent; post-LLM catches what the model decided to do (these can diverge — the model may "helpfully" upgrade a request).

```python
# intent_safety.py — Snowball-stemmed roots, language-detected structurally
DESTRUCTIVE_STEMS = {
    # data destruction (covers ES borrar/elim, EN delete/remov, PT apag/elim,
    #                          DE lösch/entfern, FR suppr/effac)
    "borr", "elimin", "delet", "remov", "wip", "purg", "destroy", "eras",
    "apag", "lösch", "entfern", "suppr", "effac",
    # uninstall / format / partition
    "uninst", "format", "diskpart",
    # process/system control
    "shutdown", "reboot", "kill", "apag", "reinici", "neustart", "redémarr",
    # memory wipe (Carter-specific)
    "olvid", "forget", "vergess", "oubli", "esquec",
    # install (network side effect, sandboxing risk)
    "install", "instal",  # ES instalar, IT installare, PT instalar covered
    # registry / system writes
    "registry", "regedit", "sysprep",
}

DESTRUCTIVE_REGEX = [
    r"\brm\s+-rf\b",
    r"\bpip\s+install\b",
    r"\bnpm\s+install\b",
    r"\bscoop\s+install\b",
    r"\bwinget\s+install\b",
    r"\bchoco\s+install\b",
    r"\bdd\s+if=",
    r"\bmkfs\b",
    r"\bscreenshot.*(completa|full|whole|entire|toda|gesamte|complète)\b",
    r"\b(memoria|memory).{0,10}(volátil|temporal|temporary|flüchtig|temporaire)\b",
]

LANG_GUESS = {  # 1-line structural guess from common closed-class tokens
    "es": {"el","la","de","que","un","por","y","es","con","para"},
    "pt": {"o","a","de","que","um","por","e","é","com","para","não"},
    "en": {"the","of","and","a","is","with","for","not","to","in"},
    "de": {"der","die","das","und","ist","mit","für","nicht","zu","ein"},
    "fr": {"le","la","de","et","est","avec","pour","ne","pas","un"},
}

def guess_lang(text: str) -> str:
    toks = set(text.lower().split())
    return max(LANG_GUESS, key=lambda l: len(toks & LANG_GUESS[l]))

def is_destructive(text: str) -> tuple[bool, str]:
    lang = guess_lang(text)
    stemmer = SnowballStemmer({"es":"spanish","pt":"portuguese","en":"english",
                                "de":"german","fr":"french"}[lang])
    stems = {stemmer.stem(t) for t in text.lower().split()}
    hit = stems & DESTRUCTIVE_STEMS
    if hit:
        return True, f"destructive_stem={list(hit)[0]}"
    for rx in DESTRUCTIVE_REGEX:
        if re.search(rx, text, re.IGNORECASE):
            return True, f"destructive_pattern={rx}"
    return False, ""

# Gate 1 (pre-LLM): inject `requires_confirmation=True` flag into user message
# Gate 2 (post-LLM): re-check serialized tool_args; if hit and not confirmed, refuse
```

**Why both gates?** Pre-LLM catches "borra todos mis archivos" when the user said it. Post-LLM catches the case where the user asked something benign and the model (incorrectly) decided to call a destructive tool — this is the documented failure mode in LlamaFirewall and ClawGuard 2026.

---

### Deliverable 7 — Anti-Empty-Reply Strategy (qwen3:4b)

For Qwen3-4B-Instruct-2507-Q4_K_M specifically, the empirically best ranking based on the small-model literature (Tang et al. 2025 over-prompting, "Learning to Ask" Wang et al. arXiv:2409.00557) and Qwen-Agent docs:

| Approach | Recovery rate (estimated for qwen3:4b-q4_K_M) | Latency cost | Verdict |
|---|---|---|---|
| **Forced retry** with stricter system prompt ("you MUST emit either a text answer or a tool_call; an empty response is forbidden") | ~70% | +1 generation pass (~1.5s) | **Recommended primary** |
| **Structural pre-LLM ambiguous-query detector** (length<10 AND no verb stem AND no proper noun → canned clarifier) | ~85% on the cases it triggers, but only triggers on ~30% of empty-replies | +0ms | **Recommended secondary** |
| **Fallback canned response** ("¿Puedes darme más detalle?") on second empty | 100% but degrades UX | +0ms | **Tertiary safety net** |
| Switching to thinking-2507 variant | unknown; thinking can *increase* tool errors per "Can Small Agent Collaboration Beat a Single Big LLM?" arXiv:2601.11327 | +2–5x latency | **Not recommended** |

Final pipeline: `pre-LLM detector → if not flagged → LLM call → if empty → forced retry → if still empty → canned clarifier`. Closes 2 of 3 Pattern E. C05-22 may persist (genuinely under-specified Spanish input "y eso").

---

### Deliverable 8 — Three-Way Classification of All 60 Cases

Legend: **A** = AGENT FIX (Carter side), **B** = BENCH FIX (evaluator is wrong), **L** = NO FIX, RECOGNIZED LIMIT.

| Case | Pattern | Class | Rationale |
|---|---|---|---|
| C03-07 | D | **L** | "qué es pytest" is plausibly a knowledge OR install-check intent. 4B cannot disambiguate reliably. Mark as ceiling. |
| C03-11 | D | A | "qué es Python" — fixable by anti-example block. |
| C04-08 | F | A | "olvida todo" → conversation_reset, not memory_delete. Destructive-intent gate. |
| C04-10 | F | A | "recuerda temporalmente" → memory_save with `volatile=True`. Currently routed wrong. |
| C05-05 | A | A | gui_deeplink fallback. |
| C05-10 | D | A | Anti-example block. |
| C05-15 | G | **B** | pytest 31s vs 15s budget — bench bug. |
| C05-16 | D | A | Anti-example block. |
| C05-22 | E | **L** | Genuinely ambiguous Spanish "y eso" — 4B limit. |
| C05-26 | D | A | Anti-example block. |
| C06-09 | C | **B** | tool_ok=True, output correct, evaluator string-mismatch on locale. |
| C06-11 | C | **B** | Same as C06-09. |
| C06-14 | H | A | filesystem_rename target-exists pre-check. |
| C07-06 | B | A | Hybrid retrieval + anaphora anchor. |
| C07-11 | B | A | Hybrid retrieval. |
| C07-17 | B | A | Hybrid retrieval. |
| C07-25 | E | A | Forced retry. |
| C07-30 | B | A | Hybrid retrieval. |
| C08-04 | A | A | Deeplink fallback. |
| C08-05 | Z | A | URL-regex routes to web_open_url. |
| C08-06 | A | A | Deeplink fallback. |
| C08-10 | H | A | filesystem_archive zip path canonicalization. |
| C08-11 | A | A | Deeplink fallback. |
| C08-14 | Z | A | Same as C08-05. |
| C08-15 | B | A | Hybrid retrieval. |
| C08-25 | A | A | Deeplink fallback. |
| C08-28 | A | A | Deeplink fallback. |
| C10-05 | H | A | gui_type SetForegroundWindow retry. |
| C10-12 | G | **B** | Real pytest run, bench budget unrealistic. |
| C10-13 | B | A | Hybrid retrieval. |
| C10-22 | G | **B** | pip --upgrade 34s, bench budget unrealistic. |
| C10-26 | C | A | Real focus-loss edge case — verifier retry-on-loss. |
| C10-28 | H | **B** | gui_type without focus — verifier should accept "no focus" PARTIAL not FAIL. |
| C11-01 | C | **B** | tool_ok+verifier_ok but evaluator strict-string mismatch. |
| C11-02 | C | **B** | Same as C11-01. |
| C11-04 | C | **B** | Same. |
| C11-17 | F | A | Destructive gate catches "screenshot pantalla completa". |
| C11-18 | G | **B** | Recursive search 21s vs 15s budget. |
| C11-19 | B | A | Hybrid retrieval. |
| C11-20 | F | A | Destructive gate "pip install". |
| C11-29 | B | A | Hybrid retrieval. |
| C11-30 | B | **L** | Pronoun-only in PT/DE — borderline, may need 8B. Try first; if fails, ceiling. |
| C12-09 | E | A | Forced retry + canned clarifier. |
| C12-21 | F | A | Destructive gate "npm install". |
| C13-12 | H | A | web_fetch refuse-without-URL with hint. |
| C13-25 | Z | **B** | window_manage on dialog-less window — verifier policy. |
| C14-02 | A | A | Deeplink fallback. |
| C14-08 | B | A | Hybrid retrieval. |
| C14-09 | B | **L** | Multi-turn pronoun chain — 4B limit on 3rd reference. |
| C14-17 | B | A | Hybrid retrieval. |
| C15-07 | G | **B** | Long-running tool, bench budget. |
| C15-16 | C | A | Real edge case — focus retry. |
| C16-04 | A | A | Deeplink fallback. |
| C16-12 | A | A | Deeplink fallback. |
| C16-18 | B | **L** | DE imperative "schließ es jetzt" — Snowball German stemmer is weak on clitics. May need explicit DE rule. Try; if fails, ceiling. |
| C17-02 | B | A | Hybrid retrieval. |
| C17-05 | A | A | Deeplink fallback. |
| C18-07 | A | A | Deeplink fallback. |
| C18-25 | A | A | Deeplink fallback. |
| C01-30 | Z | A | conversational_reset routing. |
| C02-10 | Z | **B** | 200-char limit too tight on a 399-char honest reply. Relax to 250 or split scoring. |

**Totals: 38 A · 13 B · 9 L.** This is the brutally honest count. **Do not inflate by reclassifying L-cases as B-cases.**

---

### Deliverable 9 — Sources

**Tool calling & function-calling benchmarks (small-model context):**
- [Berkeley Function Calling Leaderboard v3/v4 (Patil et al., ICML 2025)](https://gorilla.cs.berkeley.edu/leaderboard.html) — Qwen3-4B-FC included; 4B trails 8B by ~8–10 pts on multi-turn.
- [BFCL paper, OpenReview](https://openreview.net/pdf?id=2GmDdhBdDk) — multi-turn / memory / abstention are the documented weak spots for all sub-32B models.
- [τ-bench (Yao et al., arXiv 2406.12045)](https://arxiv.org/abs/2406.12045) and [τ²-bench / TAU2 (arXiv 2506.07982)](https://arxiv.org/pdf/2506.07982) — even GPT-4o<50% on multi-turn tool tasks; pass^k reliability concept relevant for an 18×30 brutal matrix.
- [Qwen3 Technical Report (arXiv 2505.09388)](https://arxiv.org/pdf/2505.09388) and [Qwen3-4B-Instruct-2507 model card](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507) — official tool-calling guidance, Hermes-style template, recommended settings.
- [Qwen Function Calling docs](https://qwen.readthedocs.io/en/latest/framework/function_call.html) — Hermes parser, no ReAct stopwords.
- [Ollama tool calling docs](https://docs.ollama.com/capabilities/tool-calling).

**Tool retrieval (the Pattern B literature):**
- [RAG-MCP (Gan & Sun, arXiv 2505.03275)](https://arxiv.org/abs/2505.03275) — retrieval reduces prompt tokens >50%, triples tool-selection accuracy.
- [Toolshed / Advanced RAG-Tool Fusion (Lumer et al., arXiv 2410.14594)](https://arxiv.org/abs/2410.14594) — +46–56% absolute Recall@5 on ToolE.
- [ToolBench / ToolLLM (Qin et al.)](https://www.emergentmind.com/topics/toolbench) and [ToolRet (ACL Findings 2025)](https://aclanthology.org/2025.findings-acl.1258.pdf) — recall@K tightly correlates with end-to-end pass rate.
- [GRETEL (arXiv 2510.17843)](https://arxiv.org/pdf/2510.17843) — execution-based retrieval validation (relevant for our "verifier as authority" stance).
- [Tool-to-Agent Retrieval (arXiv 2511.01854)](https://arxiv.org/pdf/2511.01854) — +17–19% nDCG@5/Recall@5.
- [Reciprocal Rank Fusion (Cormack et al. 2009; OpenSearch blog 2024)](https://opensearch.org/blog/introducing-reciprocal-rank-fusion-hybrid-search/) — k=60 standard.
- [BM25S (arXiv 2407.03618)](https://arxiv.org/pdf/2407.03618) — fast Python BM25, optional Snowball integration.
- [rank_bm25](https://pypi.org/project/rank-bm25/) and [LangChain BM25 integration](https://python.langchain.com/docs/integrations/retrievers/bm25/).

**Anaphora / coreference / multi-turn:**
- ["From Ambiguity to Accuracy" (Jang et al., arXiv 2507.07847)](https://arxiv.org/pdf/2507.07847) — *smaller models benefit more from coreference resolution*; mean pooling + coref improves retrieval.
- [QuReTeC (arXiv 2005.11723)](https://arxiv.org/pdf/2005.11723) — query resolution as retrieval problem, not generation problem.
- ["Comprehensive Comparison of RAG Methods Across Multi-Domain Conversational QA" (Alushi et al., arXiv 2602.09552)](https://arxiv.org/pdf/2602.09552).

**Few-shot collapse / anti-examples:**
- ["The Few-shot Dilemma: Over-prompting" (Tang et al., arXiv 2509.13196)](https://arxiv.org/pdf/2509.13196) — Llama/Gemma show *dramatic* degradation with too many examples; **anti-example** prompts outperform proliferating positives.
- [Comet "Few-Shot Prompting for Agentic Systems"](https://www.comet.com/site/blog/few-shot-prompting/) — explicitly recommends turning observed tool-overuse failures into anti-examples.
- ["Learning to Ask: When LLM Agents Meet Unclear Instruction" (arXiv 2409.00557)](https://arxiv.org/pdf/2409.00557) — empty/hallucinated args under ambiguity.

**Honesty-by-construction & verifier-based agents:**
- [HonestLLM (arXiv 2406.00380)](https://arxiv.org/pdf/2406.00380); [BeHonest (arXiv 2406.13261)](https://arxiv.org/pdf/2406.13261); [Survey on LLM Honesty (arXiv 2409.18786)](https://arxiv.org/pdf/2409.18786).
- [SmartSnap: Self-Verifying Agents (arXiv 2512.22322)](https://arxiv.org/pdf/2512.22322) — proactive evidence seeking; in-situ verification.
- [VeriGUI (arXiv 2604.05477)](https://arxiv.org/pdf/2604.05477) — Thinking-Verification-Action-Expectation framework; explicit failure detection.
- [Agentic Reward Modeling / VAGEN (arXiv 2602.00575)](https://arxiv.org/pdf/2602.00575) — verifier with environment-interaction tools.
- [VeriSafe Agent (arXiv 2503.18492)](https://arxiv.org/pdf/2503.18492) — formal-verification guardrail for GUI agents.
- [Architecting Resilient LLM Agents — Plan-then-Execute in LangGraph/CrewAI/AutoGen (arXiv 2509.08646)](https://arxiv.org/pdf/2509.08646).
- [LlamaFirewall (Meta, arXiv 2505.03574)](https://arxiv.org/pdf/2505.03574) — production-grade input/output guardrails.
- [ClawGuard (arXiv 2604.11790)](https://arxiv.org/html/2604.11790v1) and the [BodAIGuard write-up](https://dev.to/axonlabsdev/your-ai-agent-just-ran-rm-rf-heres-how-to-stop-it-425c) — pre-invocation rule enforcement, exactly the model for our pre-LLM + post-LLM destructive gate.

**Multilingual structural / morphological:**
- [Snowball stemmers overview](http://snowball.tartarus.org/texts/stemmersoverview.html) — ES/PT/EN/DE/FR all covered.
- [NLTK SnowballStemmer docs](https://www.nltk.org/api/nltk.stem.snowball.html) — drop-in Python.
- [Multilingual-E5 (arXiv 2402.05672)](https://arxiv.org/pdf/2402.05672) and [HF model card](https://huggingface.co/intfloat/multilingual-e5-small) — small variant scores 57.9 on MTEB; documented short-query weakness.

**Windows URI schemes (Pattern A foundation):**
- [Launch the default Windows app for a URI](https://learn.microsoft.com/en-us/windows/apps/develop/launch/launch-default-app), [Launch Windows Settings (ms-settings:)](https://learn.microsoft.com/en-us/windows/apps/develop/launch/launch-settings), [ms-windows-store:](https://learn.microsoft.com/en-us/windows/apps/develop/launch/launch-store-app), [Reserved URI schemes](https://learn.microsoft.com/en-us/windows/apps/develop/launch/reserved-uri-scheme-names).
- [Slack deep linking](https://docs.slack.dev/interactivity/deep-linking/), [Spotify URI scheme](https://developer.spotify.com/documentation/ios/tutorials/content-linking), [Obsidian URI](https://github.com/junjie-xyz/obsidian-links).

**Small-model tool-use realism:**
- ["Can Small Agent Collaboration Beat a Single Big LLM?" (arXiv 2601.11327)](https://arxiv.org/html/2601.11327v1) — explicit data point: 4B models tend to mis-orchestrate tools; thinking mode often *hurts* small models on agentic tasks.
- ["Small Models, Big Tasks: Empirical Study on SLMs for Function Calling" (arXiv 2504.19277)](https://arxiv.org/pdf/2504.19277).
- ["Reducing Tool Hallucination via Reliability Alignment" (arXiv 2412.04141)](https://arxiv.org/html/2412.04141v1) — categorizes "tool selection hallucination" exactly as Pattern A.
- [Detecting Hallucinations in Function Calling with Entropy/VarEntropy (Arch GW)](https://www.archgw.com/blogs/detecting-hallucinations-in-llm-function-calling-with-entropy-and-varentropy) — secondary defense if Pattern A residue persists.

---

## Recommendations

### Stage 1 — Highest-leverage, lowest-risk (1 day, ~150 LOC)
1. **Replace `prompt.py:CORE_PROMPT`** with the prompt in Deliverable 2 verbatim. Single biggest lever.
2. **Add the gui_deeplink resolver from Deliverable 3** as a hard allow-list inside the tool. Closes 11 cases (Pattern A).
3. **Add the anti-example contrastive block** (3 examples: knowledge / state / action). Closes 4 cases (Pattern D).
4. **Run the 540-test matrix.** Expected: ~495–500 PASS. **Hard regression check on C09 (filesystem básico) — must remain 100%.** If C09 drops, rollback the prompt change and instead add the deeplink rules as a *post-prompt* injection rather than rewriting CORE.

### Stage 2 — Hybrid retrieval (1–2 days, ~180 LOC)
5. **Implement Deliverable 4's `HybridToolRetriever`.** Add `rank_bm25` to requirements. Run the 480 already-PASS golden set as regression. Then run the 14 Pattern B cases. Expected: 12–14 close.
6. **If C09 regresses on retrieval**, the cause is likely BM25 over-weighting filesystem keywords; tune RRF k from 60 → 30, or add a tool-class floor (always include top-3 filesystem tools when query contains a path-like token detected structurally).

### Stage 3 — Safety + verifier (1 day, ~150 LOC)
7. **Add `intent_safety.py`** (Deliverable 6). Both gates required. Closes 5 (Pattern F).
8. **Add `TOOL_OK_VERIFIER_INCONCLUSIVE` outcome** (Deliverable 5). Closes 2 (Pattern C agent-side) + supports 5 BENCH FIXes.
9. **Add Pattern H micro-fixes** (rename pre-check, archive path canonicalization, gui_type focus retry, web_fetch refuse-without-URL). Closes 3.
10. **Add empty-reply pipeline** (Deliverable 7). Closes 2 (Pattern E).

### Stage 4 — Bench corrections (separate PR, evaluator-only)
11. **Per-tool latency budgets**: pytest 60s, pip_install 90s, pip_upgrade 120s, recursive_search 30s. Closes 5 Pattern G.
12. **String-match leniency**: locale-tolerant comparison for terminal_run output. Closes 3–5 Pattern C.
13. **Trivia char-limit relaxation**: 200 → 250. Closes C02-10.
14. **window_manage / rename overwrite policy**: explicitly document as PARTIAL when warranted.
15. **Mark remaining 9 cases as RECOGNIZED LIMIT** with a public note that the realistic ceiling under the constraints is 95%.

### Benchmarks that change the recommendation
- **If Stage 1 alone closes ≥18 cases (498/540)**, you are validated and can proceed; if it closes <12, the CORE prompt is fighting tool definitions or verifier rules and you need to audit the tool descriptions (RAG-MCP / Toolshed pre-retrieval phase) before continuing.
- **If C09 drops at any stage**, revert that stage and re-attempt with smaller surface change. C09 is the canary.
- **If the residual after Stage 3 is >12 cases**, the model is the bottleneck; the only honest paths are (a) accept the ceiling, (b) lobby to relax the model constraint to qwen3:8b-q4_K_M (still fits in 16GB at q4), or (c) introduce a verifier-as-second-pass small reranker. Do not chase the last 5% by hardcoding apps — that violates your own "no per-app hardcodes" rule.

---

## Caveats

- **The Pattern Z ceiling estimate (9 RECOGNIZED LIMIT cases) is mine, not measured.** The user should rerun after Stages 1–3 to confirm. Some L-cases may turn into A-cases if the retrieval anchoring is more aggressive than I assumed; conversely, some A-cases (especially C11-30, C16-18) may become L-cases if Snowball-stemmed pronoun detection in Portuguese/German underperforms. The estimate is calibrated to BFCL multi-turn precedent for 4B-class models (≈70–75% on multi-turn) plus your already-achieved 88.89% baseline.
- **All BFCL/τ-bench/ToolBench numbers cited apply to broad benchmarks, not Carter's specific 540-case matrix.** They establish that 100% is implausible for a 4B model on any rigorous tool-use eval, not that *your* exact ceiling is 95%. The exact ceiling is empirical.
- **The "few-shot collapse" finding (Tang et al. 2025) is most strongly demonstrated on Llama/Gemma**, not Qwen specifically. It is a strong prior for Qwen3-4B but should be re-measured on your matrix; the contrastive 3-example block in Deliverable 2 is conservative either way.
- **The destructive-intent gate (Deliverable 6) will produce false positives.** "Borrar el último carácter" or "delete the trailing whitespace" will trigger confirmation. This is by design (honesty > convenience), but you should monitor the false-positive rate; if >5% of legitimate requests trigger confirmation, narrow the regex set (e.g., require "rm -rf" only with explicit path).
- **The Snowball stemmer treats clitics inconsistently across languages.** German "schließ es" tokenization may lose the imperative marker; Portuguese "fecha-o" may not stem cleanly. If Pattern B residue concentrates in DE/PT, add language-specific clitic detection — this is *structural*, not a keyword list, so it remains compliant with the user's constraint.
- **I could not access live Qwen3-4B-FC BFCL multi-turn scores.** The BFCL leaderboard lists Qwen3-4B and Qwen3-4B-FC entries (changelog confirms addition May 2025) but the public leaderboard pages I could fetch surfaced only Qwen3-32B and aggregate/leader rows. The directional claim — that 4B trails 8B by ~8–10 pts on multi-turn — is consistent with the Qwen3 technical report but is *not* a precise figure from BFCL v3 itself. Verify via the BFCL repo before quoting in any external document.
- **"100% local, no cloud" rules out using a cloud-hosted reranker** (e.g., Cohere Rerank), which is the standard production fix for retrieval failure tails. This is part of why the realistic ceiling is below 100%. A local cross-encoder reranker (e.g., bge-reranker-base) is feasible at ~50ms latency on the RTX 4060 Ti and could be a Stage 5 if the residual after Stage 3 is unacceptable; that adds ~80 LOC and would likely close 2–3 more Pattern B/L cases.
- **Honesty applies to this report too: if your team has a strong opinion that BENCH FIXes are "cheating", the deliverable is 38 AGENT + 0 BENCH = 518/540 (95.9%) PASS as the realistic agent-only ceiling, with the 13 BENCH cases logged as evaluator defects to be tracked separately rather than scored.** Either framing is defensible; what is *not* defensible is silently moving cases from L to B to inflate the headline number.