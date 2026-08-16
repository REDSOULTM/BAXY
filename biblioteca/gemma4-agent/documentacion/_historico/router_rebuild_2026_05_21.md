# Router rebuild (2026-05-21) — applying the 4 deep-research reports

This documents the router overhaul that applied the consensus of four
independent deep-research investigations (1 Gemini, 1 ChatGPT, 2 Claude) on how
to build an optimal local/offline tool router for the Carter Agent.

## Result (measured on the never-seen 20% holdout)

| metric | baseline | after | delta |
|---|---|---|---|
| TOOL RECALL | 0.835 | **0.881** | +4.6 |
| NO-TOOL keep | 0.512 | **0.628** | +11.6 |
| short-query recall | 0.783 | 0.830 | +4.7 |
| continuation recall | 0.771 | 0.800 | +2.9 |
| multilingual probe (6 langs, fresh) | 0.789 | 0.895 | +10.6 |

Every dev threshold point dominates the baseline on BOTH axes. Tests: 111 router
tests + 65 subtests green. Latency unchanged (same 384-dim MiniLM size on CPU).

## What shipped (each step measured dev-tuned, holdout-verified once)

1. **Slice-aware eval** (`scripts/router_eval.py --slices`, isolated vs
   `--inherit` with-context). Anti-overfit foundation.
2. **Meta-directive intent class** — 5th centroid in `intent_router.py` for
   tool/answer-policy directives ("no uses herramientas").
3. **Calibrated abstain head** (`abstain_head.py`, `scripts/train_abstain_head.py`)
   — logistic regression over 12 cheap query-comparable features, trained on the
   DEV split only, threshold on dev-CV. Runtime is a numpy dot product (sub-ms,
   no sklearn). Weights in versioned JSON (`data/abstain_head.json`), not a
   pickle. This is the NO-TOOL lever: abstention as ONE calibrated decision.
4. **Tool2Vec** — each tool represented by the mean embedding of ~50 synthetic
   multilingual (es/en/pt/fr/de/it) voice-style example queries, blended with the
   description embedding (alpha 0.6). The recall lever for short queries.
5. **Session-state fusion** — the abstain head gates continuation-inheritance in
   `agent.py` so smalltalk no longer inherits the prior turn's tool.
6. **Encoder fine-tune** (`scripts/train_router_encoder.py`) — the base MiniLM
   fine-tuned (MultipleNegativesRankingLoss) on the synthetic queries + dev real
   rows (holdout excluded by stable hash). This was the decisive lever: the base
   encoder's short-query topical geometry was the ceiling. Improved multilingual
   robustness too (0.79->0.90), so universality survived the fine-tune.

Read/write operator head (a research recommendation) was SKIPPED after measuring:
all read/write pairs already route to the correct compound-tool family; the
read-vs-write *operation* is chosen by the LLM via the tool's `action` enum, so
a separate head would add complexity for a non-problem on this architecture.

## Reproducing the artifacts (project law: recipe, not binary)

`gemma4_agent/data/` is gitignored; the small text artifacts (abstain_head.json,
tool2vec_queries.jsonl, tool2vec_centroids.npz) are force-committed. The 466 MB
fine-tuned encoder (`data/router_encoder_ft/`) is NOT committed — it is
regenerated from versioned scripts. A fresh checkout falls back to the base
MiniLM automatically (semantic_router resolves the FT dir only if present).

To regenerate end-to-end:

```bash
# 1. synthetic multilingual example queries per tool (uses the running llama
#    server; resumable). Two passes: general + short/noisy.
python scripts/router_tool2vec_generate.py --per-tool 30
python scripts/router_tool2vec_generate.py --short --per-tool 25
# 2. fine-tune the encoder (CPU ok, ~25 min; GPU faster)
python scripts/train_router_encoder.py --epochs 3 --batch 64 --no-onnx
# 3. re-embed centroids with the FT encoder + retrain the abstain head + eval
python scripts/router_ft_pipeline.py
# 4. (optional) ONNX int8 export for faster CPU inference — research rec
#    (deferred: optimum dependency conflicts in the 3.10 runtime env).
```

The `_HOLDOUT_SALT` stable hash is identical across `router_eval.py`,
`train_abstain_head.py`, and `train_router_encoder.py`, so the holdout 20% is
NEVER seen during any training step.

### Pinned runtime versions (router/encoder path)

Verified-working on 2026-05-21: `torch 2.10.0+cpu`, `transformers 4.57.6`,
`sentence-transformers 5.5.1`, `scikit-learn 1.7.2`, `numpy 1.26.4`.

GOTCHA (cost a debugging detour): a stray `pip install optimum[onnxruntime]`
upgraded transformers and pulled a broken `tensorflow 2.20.0` (its own
`import tensorflow` failed on `tensorflow.tsl.protobuf`). transformers eagerly
imports TF, so `sentence_transformers` import broke → `semantic_router` silently
disabled → router returned EMPTY subsets → holdout recall collapsed 0.88→0.66.
Fix: uninstall the broken `tensorflow`/`tf_keras`. Also: newer transformers save
a tokenizer_config referencing `TokenizersBackend`, unloadable by older
transformers; `train_router_encoder.py` now overwrites the FT tokenizer with the
BASE model's portable files so the artifact loads cross-version. Do NOT install
`optimum` into the 3.10 runtime env; if ONNX export is wanted, use an isolated
venv.

## Unification (the 4 reports' consolidation ask)

The router is now ONE thing with ONE decision per turn, exposed through a single
public entry point `gemma4_agent/router.py`:

```python
from gemma4_agent import router
router.select_tool_names(text, plan, ...)   # the one decision
router.classify_intent(...) / router.suggest_tools_scored(...) / router.load_abstain_model()
```

The internals remain as cohesive single-responsibility modules (planner =
orchestrator + keyword layer + abstain gate; semantic_router = fine-tuned
encoder + Tool2Vec retrieval; intent_router = intent centroids; abstain_head =
calibrated reject option). Merging them into one megafile would hurt readability
and testability; the facade unifies the *interface*, which is what "one router"
means in practice.

**router_v2 was DELETED** (2026-05-21). All four reports agreed BM25+RRF is
structurally wrong for short voice queries (TF collapses to 1; RRF amplifies the
degenerate lexical ranker's noise) and a live probe caught it routing garbage.
It was already OFF, so removal left the holdout unchanged (0.881/0.628) — pure
debt cleanup. Removed with it: its 4 dedicated tests, `scripts/bootstrap_e5_small.py`
(served only v2), the agent.py shadow-routing block, and the launcher bootstrap.
