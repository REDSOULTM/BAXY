# Deep-Research Prompt — Make the Carter Agent tool router PERFECT
### (version for ChatGPT / Gemini — same ZIP, decisions pre-answered, fixed output format)

Attached is a ZIP (`gemma4_router_audit.zip`) with the COMPLETE tool router of a
**local, offline, low-latency Windows voice assistant** ("Carter Agent"): the
source of all routing layers, the eval harness, a 1733-query hand-labeled
corpus, prior research docs, and tests. Read every file, then return a concrete,
evidence-backed plan to push routing accuracy toward ~100% WITHOUT breaking the
hard constraints. Use the FIXED OUTPUT FORMAT at the end so your answer can be
compared side-by-side with two other models doing the same investigation.

## What the router does
Each user turn, the router picks a SUBSET of ~10 tools (out of 65 "compound"
tools) to offer the local LLM (Gemma 4, served by llama.cpp). The LLM then
decides which tool to actually call. Routing = "which tools does the model get
to see this turn". Wrong subset -> the model can't act, or acts wrong. The 65
tools are in `core/tool_schemas.py`; enriched descriptions in
`core/tool_descriptions.yaml`.

## HARD CONSTRAINTS (non-negotiable — the operator's law)
1. **Universal & multilingual.** Must work in ANY language and ANY phrasing —
   not just Spanish, not a fixed vocabulary. Multi-user / multi-accent. NO
   solution that only works for "word X".
2. **NO regex/keyword/hardcode as the DECISION mechanism.** A keyword matching
   one phrasing is forbidden as the primary signal. Decisions must come from
   MEANING. (A pragmatic keyword layer exists today; the goal is to shrink it,
   not grow it.)
3. **Local & offline.** No paid APIs, no cloud at runtime. Embedding models
   must run on CPU on a modest laptop (6 GB VRAM is fully consumed by the LLM).
   Today: `paraphrase-multilingual-MiniLM-L12-v2` + `intfloat/multilingual-e5-small`
   int8 ONNX.
4. **Tier-Alexa latency.** Per-turn budget 4-5 s total; the router runs BEFORE
   the LLM, so its own cost must be tiny (tens of ms). Do NOT re-introduce big
   per-turn cost.
5. **Measure, don't assume.** Every recommendation must be testable against the
   corpus (`scripts/router_eval.py`) with a defined metric and an anti-overfit
   holdout. No "this should help" without a measurement plan.

## TWO architectural decisions — ALREADY MADE (do not re-ask; design AROUND these)
1. **Offline-heavy preprocessing IS in scope.** Techniques whose *runtime* stays
   ≤50 ms CPU but whose *build* costs hours-to-days offline are welcome: LoRA-
   fine-tuning a small encoder on synthetic queries; using a heavyweight cross-
   encoder offline to label the logs and distilling into a tiny student
   classifier; auto-bootstrapping example-queries per tool from the corpus.
   (Dev machine has an RTX 4060 Ti 16 GB and a precedent of multi-hour GPU
   training.) TWO requirements on anything offline-trained: (a) **reproducible**
   — must regenerate from a versioned script, never a binary artifact; (b)
   **universality must survive distillation** — synthetic data must be
   multilingual / multi-phrasing and the student validated on a held-out
   multilingual slice, NOT overfit to Spanish or one user.
2. **Runtime session state should be folded INTO the router.** The new router
   should consume richer state — the prior turn's *executed* tool name(s), the
   pending-intent slot, open windows/processes, the last tool result — and
   collapse today's separate "inherit-tools" continuation rescue into the
   routing decision. (Today that logic is fragmented across `agent.py` and
   `planner.py` and caused real bugs, e.g. an infinite "need disney profile"
   loop.) BUT keep the isolated-query path as the well-defined core the harness
   scores by default, with context as a separately-measurable input — we want
   to see BOTH numbers (pure-query recall = the honest hard number; with-context
   recall = the production number) so context-fusion can't hide a weak base.
   Treat NO-TOOL abstention and read-vs-write as EASIER with state (e.g.
   "ciérralo" is unambiguous given the prior executed tool).

## Current architecture (FOUR things coexist — this is the tech debt to resolve)
- **v1 = `core/planner.py` (AUTHORITATIVE today).** Cascade: keyword regex
  UNION semantic suggestions UNION intent classifier, capped to 10. Plus
  abbreviation expansion, current-facts rule (weather/release-dates->web),
  pending-intent injection, continuation inherit. All recent fixes live here.
- **`core/intent_router.py`** — 4-class semantic classifier (info/action/
  chitchat/self-reference) via anchor centroids over MiniLM. A UNION signal.
- **`core/semantic_router.py`** — embeds query vs the 65 tool descriptions
  (cosine), top-k. A UNION signal.
- **v2 = `core/router_v2.py` (OPT-IN, currently OFF).** A semantic-first
  redesign (e5-small ONNX + BM25 + RRF k=60 + smalltalk centroid gate +
  confidence-gated fallback + adaptive cap). **Turned OFF as authoritative**
  because a live probe found it routing GARBAGE in production (overrode v1's
  good subset with noise, e.g. "de que trata Dune" -> [backup_sync, reminder,
  routine...] no web). See `docs/research_router_v2_arch.md` and
  `docs/research_rrf_confidence.md`.

**The operator wants to collapse these into ONE clean router. You may recommend
keeping v1 as the base, reviving a fixed v2, or a NEW unified design — but pick
ONE and justify it. Tearing it all down is allowed if the evidence supports it.**

## Current measured baseline (`python scripts/router_eval.py --split both`)
Corpus: `data/router_eval_corpus.curated.jsonl` — 1733 real queries (median 5
words, 27% no-tool, 32/65 tools actually labeled), mined from production logs +
the Carter-540 bench, hand-labeled. 80/20 dev/holdout by stable hash.
- **TOOL RECALL (holdout): 0.835** — needed tool is in the subset.
- **NO-TOOL keep (holdout): 0.51** — correctly offers NO tool on smalltalk/
  knowledge questions. THE WEAK SPOT.
- `--inherit` simulates runtime continuation rescue (~+2 pts). `scripts/router_diag.py`
  attributes misses by stage.

## Recurring real-bug PATTERNS your design should make impossible BY CONSTRUCTION
1. **read-vs-write phrasings**: "que notas tengo" (read) vs "anota X" (write);
   "esta instalado discord" (read) vs "instala discord" (write); calendar read;
   weather/release-dates needing web. Semantic layer weak on short queries.
2. **App-name resolution** (`app_resolver.py`): near-anagrams ("Teams"->"Steam"),
   PWA shortcuts ("Chrome"->a YouTube PWA), stopword overlap ("Call of Duty"->
   "God of War"). Fuzzy matching is fragile.
3. **Continuations/context**: "subelo un poco mas", "cierralo", "Mi perfil es
   Ema" routed empty in isolation; rescued at runtime — delicate.
4. **The local LLM is the OTHER half**: even with the right subset, Gemma 4
   INTERMITTENTLY declines to call the offered tool or leaks the call as text
   (a rescue parser handles several leak forms). Routing and model tool-calling
   are COUPLED — analyze together.
5. **router_v2 was actively harmful** — a sophisticated hybrid (BM25+RRF)
   UNDERPERFORMED a pragmatic cascade on short, noisy, multilingual voice
   queries. Understand why; don't repeat it.

## How to read the ZIP
`core/` = the router (4 layers + descriptions + schemas + app resolver).
`scripts/` = eval harness, corpus build/curate/label, diagnostics, e5 bootstrap.
`tests/` = pin current behavior. `data/` = the 1733-query labeled corpus + raw.
`docs/` = prior research on v2's hybrid + a night logbook of one optimization
marathon (numbers, 8 attempts, honest ceiling). Start with `scripts/router_eval.py`
(the metric), then `data/*.curated.jsonl`, then `core/planner.py`, then docs.

## FIXED OUTPUT FORMAT (use these exact section headers, in this order)
**A. DIAGNOSIS** — why short, multilingual, noisy voice queries defeat the
current approaches. Cite literature where it materially supports a claim.

**B. RECOMMENDED ARCHITECTURE (pick ONE)** — one paragraph stating the design
you recommend and the single reason it wins.

**C. TRADE-OFF TABLE** — your pick vs the 2-3 strongest alternatives, scored on:
multilingual robustness, latency, offline/CPU fit, no-tool/abstention quality,
read-vs-write handling, implementation risk. Use a real table.

**D. MIGRATION PLAN** — numbered steps from today's v1 cascade. For EACH step:
the change, the expected metric move (recall / no-tool), and the holdout
validation method. Order by value/risk.

**E. WHAT TO DELETE** — which of the 4 current routers / which code you would
remove, and why it is safe.

**F. STRUCTURAL FIXES for the recurring patterns** — how your design makes
read-vs-write, app-name resolution, and continuations structurally robust rather
than patched case-by-case. Include the model-tool-calling coupling.

**G. OFFLINE TRAINING RECIPE (if any)** — exact, reproducible steps: data
generation (multilingual), model, training, distillation, runtime artifact, and
how you validate universality on a held-out multilingual slice.

**H. ANTI-OVERFIT NOTE** — how to use the corpus as a TEST set without
memorizing it.

Be concrete and honest. If ~100% is not achievable under the constraints, say so
and state the realistic ceiling with the reason.
