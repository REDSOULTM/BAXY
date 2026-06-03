# Gemma 4 Router Audit — Architecture, Diagnosis, and Migration Plan

> **Critical disclosure up front.** The task asked me to unzip `/mnt/user-data/uploads/gemma4_router_audit.zip` and cite specific functions and line ranges from the code. **This execution environment does not expose filesystem, shell, or unzip tools** — only web search/fetch, Google Drive (which does not contain the file), one subagent, and the enrich/complete tools. I confirmed this by searching Drive for the archive and finding nothing. I therefore could not read `core/planner.py`, `core/router_v2.py`, `core/agent.py`, or the corpus directly. **Every code-level claim below is derived from the prompt's own description of the codebase** (the cascade structure, baseline 0.835 / 0.51, 1733 queries / 27% no-tool, the "Dune" v2 failure, the four routers, the inherit-tools rescue location) **plus published literature**, not from reading the files. Where I refer to a path/function I name it as "the prompt describes" or "the cascade in `core/planner.py` (per the project description)". A second-pass audit by an agent with filesystem access should re-anchor every recommendation to actual line ranges before any code is changed. With that caveat stated, the substantive design conclusions below are independently defensible and the user can stress-test them against the real code.

---

## A. DIAGNOSIS — why short, multilingual, noisy voice queries defeat the current approaches

The current system is a **four-router pile** (v1 cascade `core/planner.py`, the 4-class `core/intent_router.py`, the cosine `core/semantic_router.py`, and the deprecated `core/router_v2.py`) plus a runtime continuation rescue in `core/agent.py`. The reported baseline is **recall 0.835 and no-tool keep 0.51** on the holdout. The asymmetry between those two numbers is the single most important diagnostic signal: recall is "good enough" because the cascade can ensemble multiple weak signals into a 10-tool subset, but no-tool keep is barely better than a coin flip because **none of the four components was trained to emit a calibrated abstain decision** — abstention is a residual category that survives only when every other layer happens to miss. Below is the mechanical chain.

**A1. The query distribution is hostile to every cheap retrieval primitive.** Median 5 words, 27% no-tool, and Spanish/English code-switching. Short queries are the worst case for BM25 (the lexical engine inside v2): with k1≈1.2 and only 2–3 query tokens, the saturation curve is essentially flat, IDF dominates, and any rare token in a *wrong* tool description outranks the right tool. As one practitioner survey puts it: *"Single word queries like 'pizza' match everything containing that word with no way to distinguish intent ... BM25 cannot find 'physicians' when query says 'doctors'. No shared words means no match. This is THE fundamental limitation of term-based retrieval, affecting perhaps 15 to 20 percent of queries where users and content creators use different vocabulary"* (systemoverflow.com). For the Gemma-4-Agent corpus, "que notas tengo" and "anota X" share zero meaningful tokens with the English tool descriptions in `core/tool_descriptions.yaml`, so BM25 over those descriptions is essentially noise.

**A2. Dense cosine over English tool descriptions (`core/semantic_router.py`) is *near*-multilingual, not multilingual, unless the encoder was actually trained for it.** If the current semantic router uses a generic English MiniLM-class encoder, Spanish queries land in roughly the right neighborhood but the margin between the correct tool and a thematic neighbor (`reminder` vs `note`, `routine` vs `timer`) collapses below the noise floor for 3–5 word inputs. multilingual-E5-small is the right baseline here (Wang et al., arXiv:2402.05672) because it was explicitly trained with weakly-supervised contrastive pre-training on multilingual pairs and supervised fine-tuning. Per Grebennikov's Nixiesearch ONNX quantization study, dynamic int8 quantization brings e5-base-v2 down to ~15 ms on CPU for long documents (a 3.5× improvement); e5-small at 118M params is faster still, comfortably inside the 50 ms budget. A vanilla English MiniLM is not multilingually competent at this query length.

**A3. The 4-class intent router cannot carry the abstention load.** A 4-class classifier (likely something like `tool / question / chat / unknown`) is structurally too coarse. The published ceiling for the right framing — open-set intent detection with explicit OOS — is much higher: DROID (arXiv:2510.14110) reports a mean of **93.65% F1 on Known and 95.8% on Unknown intents on CLINC-150**, exceeding strong boundary-based methods such as DA-ADB and ADB. DETER (arXiv:2405.19967) achieves up to 13% F1 improvement on known and 5% on unknown intents on CLINC-150 over prior baselines with only 1.5M trainable parameters and a threshold-based re-classification head. The implication for this codebase: the 0.51 no-tool keep number is not a law of physics — it is the cost of using a router that wasn't trained for calibrated abstention. The original CLINC-150 BERT baseline F1 was **0.735 for OOS detection** (Larson et al., "An Evaluation Dataset for Intent Classification and Out-of-Scope Prediction", EMNLP 2019, ACL Anthology D19-1131), so even a competent off-the-shelf encoder + threshold should reach the high 0.7s on this corpus.

**A4. The cascade leaks state to `core/agent.py`.** Continuation utterances like "subelo un poco mas", "cierralo", and "Mi perfil es Ema" are routed empty when handled in isolation — they have no lexical anchor to any specific tool. The codebase compensates with an "inherit-tools rescue" inside the agent that pulls the previous turn's tool set forward. This is a textbook violation of single-responsibility: the router emits an answer that is *known wrong* and another layer patches it. Every dialog-state-tracking paper since TripPy (Heck et al., arXiv:2005.02877) has argued the opposite — slot/state copy mechanisms belong inside the unit making the prediction, not as downstream rescue.

**A5. Specific analysis of why `router_v2`'s BM25+RRF actively regressed.** The "de que trata Dune" → `[backup_sync, reminder, routine, ...]` failure is the canonical signature of **uncalibrated rank fusion on heterogeneous signal quality**. The mechanics:

1. **BM25 over tool descriptions has near-zero signal on the Spanish short query** — "de", "que", "trata" are stopwords or near-stopwords; "Dune" hits *nothing* in `core/tool_descriptions.yaml` (web_search's description almost certainly says "search the web", not "movies" or "Dune"). So the BM25 list is effectively random above noise.
2. **RRF is rank-only by design.** As the WRRF paper (uregina.ca) documents: *"RRF is agnostic to the confidence of the retriever, which could otherwise provide useful signals for weighting documents retrieved with higher certainty"*. When one of your retrievers produces a meaningless ranking, RRF gives that ranking equal voting weight as the meaningful one. A random BM25 list with `web_search` at rank 30 and `backup_sync` at rank 3 contributes `1/(60+3) = 0.0159` to backup_sync — enough to swamp a dense retriever that put web_search at rank 5 with `1/65 = 0.0154` if the dense list was also noisy (and on a 3-word Spanish query against English tool descriptions, it is).
3. **No abstention output.** RRF produces a fused ranking but cannot say "none of these is good enough"; it always returns *something* in the top-k. A cascade with a keyword tripwire for "de que trata X" or a calibrated dense-score floor would have routed to web_search; v2 had neither.
4. **65 candidate descriptions are too few for RRF to recover from noise.** RRF was characterized on TREC-scale collections with thousands of candidates and a long tail; with 65 items the rank distribution is too compressed for the `1/(k+r)` decay to differentiate signal from noise. Berkeley's BFCL work (Patil et al., ICML 2025) corroborates the broader scaling problem: tool-calling accuracy on calendar scheduling collapses from 43% to 2% as tools expand from 4 to 51 across multiple domains. ToolRet (ACL 2025 Findings) reports that *"all retrievers in our experiments achieve less than 35% in Completeness@10 and under 52% in recall@10"* on tool retrieval — meaning the published ceiling for short-query tool retrieval is well below what v2's design implicitly assumed.

So v2 lost because the team replaced a *pragmatic asymmetric* system (the v1 cascade has different layers for different failure modes) with a *symmetric* system (RRF treats every retriever's vote as equally valid) at the exact corpus size and query length where RRF's robustness properties break down. This is the lesson to internalize: **rank-only fusion only outperforms calibrated cascades when each constituent retriever is independently competent and the candidate set is large enough to spread.** Neither holds here.

**A6. Tool-calling coupling.** The router cannot be evaluated independently of Gemma 4's tool-calling reliability. Per multiple GitHub issues — `ggml-org/llama.cpp#21316` ("Gemma 4 tool calling leaves unexpected tokens in tool calls"), `#21384` (array parameters serialized as JSON string when string values contain `{` or `}`), `unslothai/unsloth#4999` (raw `<|tool_call>call:...<tool_call|>` surfaces as plain text in OpenAI clients), and `ollama/ollama#15241` (parser crash in Ollama v0.20.0) — **Gemma 4's `<|tool_call>...<tool_call|>` token format is fragile across the local inference stack as of April 2026**. Even with a perfect router subset, a non-trivial fraction of turns leak the call as text or drop it. That means the router design has to anticipate retries and keep the offered subset *narrow* (≤8 tools), because a fat subset materially increases the chance Gemma declines or leaks (the BFCL 43% → 2% scaling curve). Notably, Google itself ships **FunctionGemma 270M** as a separate function-calling-specialized model, which is itself indirect evidence that the base Gemma 4 family is not reliably good at native tool calling out of the box.

---

## B. RECOMMENDED ARCHITECTURE (ONE pick)

**Pick: a single distilled-and-calibrated `multilingual-e5-small` bi-encoder, fine-tuned with LoRA on teacher-labeled silver data, exporting an ONNX-int8 runtime artifact, with a learned router head that emits per-tool logits AND a calibrated abstain probability, and that consumes a 4-slot runtime state vector (last_tool, pending_intent, open_windows, last_result_kind) as part of its input.**

Concretely:

- **Encoder:** `intfloat/multilingual-e5-small` (118M, 384-dim), CPU-friendly under 20 ms per query when ONNX-int8 quantized (per Grebennikov's Nixiesearch benchmark for e5-base-v2 at ~15 ms; e5-small is faster).
- **Head:** a 2-layer MLP on top of `[query_embedding ; state_vector_embedding]` producing 65 sigmoid tool logits + 1 explicit `no_tool` logit. Multi-label (sigmoid), not softmax, so multi-tool turns work natively.
- **Threshold:** per-tool calibrated thresholds learned on the train slice, plus a global temperature for the no_tool logit, validated by Brier/ECE on the holdout (the DETER recipe).
- **Fallback:** if the no_tool logit is high AND the top-tool logit is below its calibrated threshold, route to the empty set + LLM-only path. If the top tool is `web_search` with margin > τ, send only that one tool (narrow subsets help Gemma 4 actually call it).
- **State integration:** the 4-slot vector is concatenated to the query embedding; no separate "rescue" layer in agent.py. Continuation utterances are learned, not patched.
- **Keyword tripwires:** kept, but demoted to a *prior bias* layer that biases logits before the threshold check, not a hard override. This shrinks the keyword surface area over time (matches the user's "shrink not grow" constraint).

**The single reason it wins:** every other architecture either re-imports v2's failure mode (uncalibrated fusion of heterogeneous signals) or trades latency for marginal recall. A single calibrated bi-encoder with a router head is the only design where **abstention is a first-class output**, where the **multilingual representation is intrinsic to the encoder** rather than retrofitted, where the **runtime cost is one forward pass plus one MLP** (well under 50 ms), and where the **training signal is unified** — one model, one loss, one corpus, one set of metrics. The user has already paid the "ambition tax" once (v2). The lesson is not "stop being ambitious"; it is "be ambitious about *one* component, not about *combining* components."

---

## C. TRADE-OFF TABLE

| Axis | (a) v1 cascade + targeted patches *(baseline)* | (b) Cross-encoder reranker over BM25+dense candidates | (c) int4 instruction-tuned classifier-LLM (e.g. Qwen3-0.6B at int4) | **(P) Picked: fine-tuned mE5-small bi-encoder + router head + state vector** |
|---|---|---|---|---|
| **Multilingual robustness** | Medium — depends on whether semantic_router uses a multilingual encoder; Spanish short queries weak | High at inference, but only if base encoder is multilingual; reranker amplifies, doesn't create, multilingual signal | High in principle but uneven for short colloquial Spanish; depends on instruction tuning quality | **Highest** — mE5 is intrinsically multilingual and we add held-out Spanish/EN/PT/FR slices to the validation set |
| **Latency (CPU)** | ~30 ms today (per project description, cascade with cosine layer) | **Bad** — cross-encoder over even 20 candidates costs 200–500 ms CPU; blows the 50 ms budget | 100–300 ms typical for 0.6B int4 even with llama.cpp on CPU; tight against 50 ms | ~25–35 ms (under 20 ms encoder + ~3 ms MLP + overhead), inside budget |
| **Offline / CPU fit** | Already fits | Cross-encoders are notoriously CPU-hostile; would need aggressive distillation | Fits but consumes RAM (~500 MB) competing with Gemma 4's footprint | Fits cleanly; ONNX-int8 artifact is ~50 MB |
| **No-tool / abstention quality** | **Weak (0.51)** — abstention is residual, not learned | Medium — reranker can be trained for it but adds a stage | High if instruction-tuned for it, but expensive | **Highest** — calibrated abstain logit + threshold; DROID-class architecture achieves 95.8% OOS F1 on CLINC-150 |
| **Read-vs-write handling** | Patched case-by-case in `core/planner.py` keyword layer | Same problem just on candidates — reranker doesn't know Spanish imperative vs interrogative without training | Strong if LLM is trained on it; brittle without | Strong — synthetic data generation explicitly produces matched read/write pairs per tool |
| **Implementation risk** | Lowest | High — new stage, new failure modes, latency cliff | High — model swap risk, contention with Gemma | **Medium** — single model, single artifact, reproducible from a versioned script |

**Reading the table:** if (a) gets us from 0.51 → 0.65 on no-tool keep with targeted patches alone, ambition over (a) is **not justified** and we should stop. If (a)'s patches cap below 0.65 (which is the literature expectation for hand-rules without a learned abstain head), then (P) is justified. (b) and (c) are both worse than (P) on the binding constraint (latency) and don't beat it on quality. **The migration plan below sequences (a) before (P) precisely so we can falsify the more ambitious step if the cheap one already wins.**

---

## D. MIGRATION PLAN

Each step has: change, expected metric move, holdout validation slice, ship threshold. The plan is ordered cheap-safe-high-value first so that v2's mistake — committing to ambition before the cheap fixes were exhausted — cannot repeat.

**Step 1 — Wire the existing `core/semantic_router.py` to multilingual-E5-small if it isn't already, ONNX-int8.** (1–2 days.)
- *Change:* swap encoder; rebuild tool-description embeddings with "query:" / "passage:" prefixes (required by E5 family — Pinecone's E5 guide is explicit about this); export ONNX with HuggingFace `optimum`, dynamic int8 (avx2 or avx512_vnni config per the user's CPU, via `export_dynamic_quantized_onnx_model`).
- *Expected move:* recall +0.01 to +0.03; no-tool keep ≤ +0.02 (semantic_router doesn't drive abstention).
- *Validate on:* multilingual slice (any non-English query); short-query slice (≤4 words).
- *Ship if:* no recall regression on holdout and CPU p95 latency stays under 30 ms.

**Step 2 — Add a learned abstain head as a stub on top of the *existing* semantic_router scores.** (2–3 days.)
- *Change:* logistic regression on `[max_cosine, top-3_cosine_gap, query_length, has_imperative_marker, has_interrogative_marker]` → P(no_tool). Train on the 1733-corpus train split. Threshold calibrated on a held-out 10% of train.
- *Expected move:* no-tool keep 0.51 → ~0.62–0.68; recall ±0.01.
- *Validate on:* no-tool slice of holdout (27% × 0.2 ≈ 94 examples). Slice-wise: short-no-tool, chat-no-tool, ambiguous-no-tool.
- *Ship if:* no-tool keep ≥ 0.62 AND tool-bearing recall does not drop below 0.825.

**Step 3 — Fold runtime state into the router input.** (3–5 days.)
- *Change:* expose `last_tool, pending_intent, open_windows, last_result_kind` from agent.py to the router as a small dict; encode as a 16-dim learned embedding concatenated to the query embedding inside `core/semantic_router.py` (or new `core/router.py`). The "inherit-tools rescue" in `core/agent.py` is now disabled but kept behind a feature flag for 2 weeks.
- *Expected move:* continuation slice accuracy +0.10–0.20; pure-query recall unchanged. **Crucially, report both pure-query and with-context numbers** per the user's requirement.
- *Validate on:* continuation slice (utterances tagged as follow-ups in the corpus — likely identifiable by the same dialog id appearing twice in the prior turn). Specifically: "subelo un poco mas", "cierralo", "Mi perfil es Ema".
- *Ship if:* with-context recall ≥ pure-query recall + 0.05 on the continuation slice, AND no regression on pure-query.

**Step 4 — Targeted patches to `core/app_resolver.py` for the Teams↔Steam / COD↔God-of-War class.** (1–2 days.)
- *Change:* phonetic blocking (Double Metaphone) **before** Levenshtein, never as a fallback after it; an explicit "ambiguous-app" branch that asks the user "did you mean Teams or Steam?" rather than silently picking; a hard regex for Chrome-PWA mismatch.
- *Expected move:* app-resolution accuracy slice +0.10–0.15; no general recall move.
- *Validate on:* the corpus subset where the labeled tool depends on a correctly resolved app name.
- *Ship if:* zero new false-positive resolutions (precision must not drop) AND ambiguous-ask rate <5% of total app-bearing turns.

**Step 5 — Distill the cascade into a single LoRA-fine-tuned mE5-small + router head (the "P" architecture).** This is the ambitious step. Run Step 5 *only* if Steps 1–4 have not closed the gap to ~0.70 no-tool keep / ~0.88 recall. See Section G for the exact recipe.
- *Expected move:* recall 0.835 → ~0.90; no-tool keep ~0.65 → ~0.80.
- *Validate on:* all four slices (no-tool, continuation, short ≤4 words, multilingual non-English) reported separately, plus the held-out multilingual slice that is **not** part of training (Section H).
- *Ship if:* every slice improves or stays flat vs Step 4, with no slice regressing by >0.02. If a slice regresses, ship the cheap baseline and treat Step 5 as a research result.

**Step 6 — Retire the dead routers (Section E).** Only after Step 5 is shipped or definitively abandoned.

---

## E. WHAT TO DELETE

The four routers exist because each was built to compensate for the failures of the previous one. After Steps 1–5 succeed, three of them have no reason to live.

- **Delete `core/router_v2.py` entirely.** It is the BM25+RRF redesign that the user has already proved actively harmful. The "Dune" probe and the `docs/research_router_v2_arch.md` post-mortem are sufficient evidence. The safety argument: it is not on the runtime path today (per the project description), so removal is a no-op for live behavior. **Tests to update:** any unit test that imports `router_v2` should be deleted or moved to a `tests/_archive/` directory; the `scripts/router_diag.py` per-stage attribution should drop the v2 column.
- **Delete `core/intent_router.py` (the 4-class classifier).** Its responsibility — telling apart tool vs no-tool — is subsumed by the calibrated abstain logit in the new architecture. The safety argument: keep its current behavior pinned in a *characterization test* that runs against the new router on the exact same 1733 corpus; assert the new router's no-tool keep is strictly ≥ the old router's on every slice before deletion.
- **Delete the "inherit-tools rescue" inside `core/agent.py`.** The continuation behavior is now learned by the state vector in Step 3. Safety argument: feature-flag for two weeks (Step 3 already builds this in); compare with-context recall before and after; only remove the dead branch after the flag has been off for 14 days with no regression in the continuation slice.
- **Keep `core/planner.py` as the *integration* layer**, but strip its tool-selection logic down to a thin wrapper that calls the new router and applies the keyword tripwire (which becomes a *prior bias*, not a hard override). The cascade structure as a *router* is what dies; the cascade as a *budget-enforced pipeline* is what survives, slimmer.
- **Keep `core/semantic_router.py`** — it becomes the home of the new bi-encoder + head. Rename to `core/router.py` once `router_v2.py` is gone.

**Behaviors the replacement MUST preserve** (capture in pinned tests before any deletion):
1. The `web_search` route for general-knowledge questions ("de que trata Dune", weather, release dates).
2. Multi-tool turns that hit ≥2 labels in the corpus must still surface ≥2 tools (this is why the head is sigmoid not softmax).
3. The keyword tripwires for the explicit safety/destructive cases (anything that today bypasses the cascade entirely — likely volume mute, anything destructive on file system — these stay as hard rules until proven safe to remove).

---

## F. STRUCTURAL FIXES for recurring patterns

**F1. Read-vs-write phrasings ("que notas tengo" vs "anota X"; "esta instalado discord" vs "instala discord").** The structural fix is *training-data generation* (Section G), not runtime logic. Synthetic generation produces *matched pairs* for every tool: for every write-side template, generate the corresponding read-side template in 6 languages and the corresponding existence-check template. The router learns from data that these are different tools, instead of relying on Spanish-specific imperative-vs-interrogative regexes. Concretely: for `notes`, generate (write: "anota X", "écrivez X", "write down X", "annotare X"; read: "que notas tengo", "quelles notes ai-je", "show my notes", "mostra le mie note"; existence: not applicable). This eliminates the read/write confusion as a *category* rather than as case-by-case patches.

**F2. App-name resolution (Teams↔Steam, Chrome-PWA, COD↔God-of-War).** The structural fix is a **two-stage resolver with explicit uncertainty**:
- Stage 1 — phonetic blocking: Double Metaphone. The ML6 voice-AI study ("Why Voice AI Fails at Name Matching and How We Achieved 96% Accuracy", ml6.eu) reports *"96% overall accuracy, 97.3% precision, and 94.8% recall, adding ~150ms of latency"* using a cascading Exact → Phonetic → Fuzzy approach. The 150 ms is for a full identity-verification pipeline; the actual algorithmic execution they report is 0.2–0.5 ms.
- Stage 2 — edit distance only within a phonetic bucket. This catches "Teams" vs "Steam" as phonetically *different* (TMS vs STM in Metaphone) instead of edit-distance-close (Levenshtein = 1).
- Stage 3 — if the top-2 candidates are within 5% similarity AND from different phonetic buckets, **emit an `ambiguous-app` signal** that the router treats as "ask the user". Today's resolver silently picks. The structural insight is that **silent disambiguation is the bug**; uncertainty must be a first-class output.
- For Chrome-PWA, maintain an explicit alias table (PWA name → underlying browser process) versioned in `core/tool_descriptions.yaml` rather than inferred at runtime.

**F3. Continuations ("subelo un poco mas", "cierralo", "Mi perfil es Ema").** The structural fix is the 4-slot state vector from Step 3. "Mi perfil es Ema" in isolation embeds near nothing actionable; concatenated with `(last_tool=profile_set, pending_intent=set_username, open_windows=[settings])` it becomes a near-zero-distance match to the `profile_set` tool. This is the TripPy lesson (Heck et al., arXiv:2005.02877): slot copy mechanisms belong inside the unit making the prediction, not as downstream rescues. Reporting both pure-query and with-context numbers prevents context from masking a weak base — the pure-query number tells you whether the encoder is fundamentally any good; the with-context number tells you whether state integration is buying real continuation accuracy.

**F4. LLM tool-calling coupling — Gemma 4 declines / leaks.** This is the most under-discussed coupling in the system. Per the GitHub issues catalogued in Section A6, **Gemma 4's tool-calling stack in llama.cpp is unreliable as of mid-2026**: `<|tool_call>call:name(args)<tool_call|>` leaks as plain text when the chat template/parser combination is wrong (`unslothai/unsloth#4999`); array arguments serialize as JSON strings when values contain `{` or `}` (`ggml-org/llama.cpp#21384`); Ollama 0.20.0 drops tool calls into the reasoning field with empty content (`ollama/ollama#15241`). The router cannot fix Gemma, but it can structurally reduce the failure rate:
- **Narrow subsets.** Offer ≤8 tools per turn, not 10. Berkeley BFCL data shows tool-calling accuracy drops sharply as tool count rises (43% → 2% from 4 → 51 in calendar scheduling).
- **High-confidence single-tool path.** When the router's top-tool margin exceeds τ (~0.4 logit gap), offer ONLY that tool to Gemma. Single-tool offerings dramatically reduce both refusal and leak rates in the local tool-calling literature.
- **Detect leaked tool calls.** Add a post-hoc regex in `core/agent.py` for `<|tool_call>call:(\w+)\s*\{(.*?)\}<tool_call|>` in the assistant's text content; if matched, parse it and execute as if it were a structured tool_call. This is the parser-side fix from `ggml-org/llama.cpp#21316`; do it client-side until llama.cpp ships the fix.
- **Re-ask with a smaller subset on refusal.** If Gemma replies with text only and the router was confident (top logit > τ), retry the turn with the top-1 tool only and an explicit system note "use this tool".

The principle: routing and Gemma's tool-calling failures **compound**. A 0.9 router × 0.9 tool-call success = 0.81 user-visible correctness. Both numbers must move together.

---

## G. OFFLINE TRAINING RECIPE

Two scales, same recipe. RTX 4060 Ti 16 GB, LLM unloaded so all 16 GB free. Both must be reproducible from one versioned script (e.g. `scripts/train_router.py`) with config flags for the two scales.

### G1. Common scaffolding (both scales)

- **Student:** `intfloat/multilingual-e5-small` (118M, 12 layers, 384 dim). Full fine-tune fits comfortably in 16 GB; LoRA is also fine. Pure FT is preferred at small scale because it converges faster. Note: BGE-M3 (568M) full fine-tune fits on a single 24 GB consumer GPU per arXiv:2412.17364 (trained on 3090); on 16 GB it requires LoRA. The Johal.in case study reports BGE-M3 full FT on A10G (24 GB) at 12k pairs / 2.1 h / lr 2e-5 / batch 32 / 3 epochs — a useful comparable.
- **Teacher (silver labeler):** `bge-reranker-v2-m3` as a cross-encoder reranker over candidate tools, *plus* a 7–8B instruction-tuned LLM (Qwen2.5-7B-Instruct or Gemma-2-9B) for binary "is this query a tool-bearing query? if yes, which tool?" label generation. The teacher does **not** need to be local — synthetic data is generated **offline** and then frozen. Per the RGD paper (arXiv:2601.09692), *"weak generators struggle to answer their own queries"* — so use the strongest teacher available, validated by GPT-4-class spot checks on a 200-sample audit.
- **Runtime artifact:** ONNX dynamic-int8 (avx2 config for current CPUs; avx512_vnni if available) per Hugging Face `optimum` and the sbert.net efficiency docs (`export_dynamic_quantized_onnx_model`). Versioned by git hash + training-config hash baked into the filename.
- **Synthetic data languages:** English, Spanish, Portuguese, French, Italian, German. Six languages forces the model not to overfit to Spanish (the user's biggest production language). Validation uses a held-out language slice — see Section H.
- **Multilingual data generation pattern.** For each tool t in the 65, prompt the teacher LLM with: *"Generate 200 user utterances that should invoke tool t, evenly across 6 languages, varying read-vs-write framing, with 30% being short (≤4 words) and 20% being continuation-style (assume prior turn already set context). Generate 50 negative utterances per tool — semantically near but should NOT invoke t."* This produces ~17k labeled queries per tool; 65 tools × 17k = ~1.1M, but heavily downsampled to ~100k after dedup and a teacher cross-encoder consistency check.

### G2. "12-hour overnight" lower-risk variant

- **Data:** 30k synthetic queries (≈460 per tool) + the 1733 real corpus (train split only, 1386). Generated by a single teacher LLM (Qwen2.5-7B-Instruct via llama.cpp on the same 4060 Ti the night before, or via free-tier API).
- **Model:** mE5-small, full fine-tune (no LoRA), contrastive loss (InfoNCE) on (query, correct_tool_description) pairs with in-batch negatives + 3 hard negatives mined by the teacher cross-encoder.
- **Training:** 3 epochs, batch size 64, lr 2e-5, fp16, AdamW with paged optimizer. The Johal.in BGE-M3 case study reports 12k pairs in 2.1 h on A10G (24 GB) at similar hyperparameters; extrapolating: 30k pairs × 3 epochs ≈ 5–7 h on A10G; on a 4060 Ti 16 GB it's ~8–10 h for the encoder backbone (note: no direct 4060 Ti benchmark for mE5-small is published; the closest reference is arXiv:2509.12229 which profiles LoRA on RTX 4060 8 GB for a 1.5B-param model at 628 tok/s with paged optimizer — mE5-small is ~13× smaller so encoder throughput should be substantially higher). The router head trains in ~30 min on top.
- **Validation:** held-out 20% (347 queries) with slice-wise reporting. Pass criteria: no-tool keep ≥ 0.62, recall ≥ 0.86, and the multilingual non-Spanish slice (PT/FR/IT/DE) within 0.05 of the Spanish slice.
- **Distillation pass:** *None* in the overnight variant — full FT on contrastive loss is already a form of supervised distillation when the teacher labels are used to construct the positive/negative sets.

### G3. "2–5 day" full version

- **Data:** ~100k–150k synthetic queries after dedup and teacher consistency filtering (start with ~400k generated, drop everything where the teacher LLM and the teacher cross-encoder disagree on the correct tool — this is the "consensus filter" from the RGD paper). Plus the 1733 real corpus train split. Include adversarial pairs: matched read/write/existence triples per tool, code-switched queries ("anota X please" mixing ES+EN), and noisy ASR-style queries (random insertion/deletion to simulate STT errors).
- **Model:** mE5-small base + LoRA (rank 16, alpha 32, on all attention and FFN projections). LoRA over full FT here because we'll train *long* and want to easily revert.
- **Cross-encoder teacher distillation:** explicit KL-divergence loss against `bge-reranker-v2-m3`'s scores on (query, candidate_tool_description) pairs for the top-20 candidates, temperature 2.0, mixed with InfoNCE (50/50). This is the standard cross-encoder→bi-encoder distillation recipe (towardsdatascience.com "Advanced RAG: Cross-Encoders & Reranking" and Amazon Science's DISKCO). The published evidence for this recipe: ResearchGate's "Distilling Cross-Encoder Signals into Bi-Encoders" reports 19.66% Recall@3 improvement on SQuAD over the BGE baseline.
- **Training:** 5 epochs, batch size 128 (with gradient accumulation as needed), lr 1e-4 for LoRA, cosine schedule with warmup. On a 4060 Ti 16 GB at fp16, expect 12–24 hours for the contrastive portion, plus 8–16 hours for the distillation portion, plus head training and ablations. Total wall-clock 2.5–4 days with margin for re-runs (no published 4060 Ti number for mE5-small; this is an extrapolation from the 4060 8 GB LoRA profiling and the A10G BGE-M3 anchor).
- **Router head:** trained on top of frozen encoder embeddings, 2-layer MLP (384 → 256 → 66 logits — 65 tools + no_tool), focal loss to handle the 27% no_tool class skew, per-tool threshold calibration via isotonic regression on a held-out 10% of train.
- **Validation:** same as G2 but with all four slices reported separately AND a held-out multilingual slice (see Section H). Pass criteria: no-tool keep ≥ 0.78, recall ≥ 0.90, no slice regressing by >0.02 against the v1 baseline, p95 latency ≤ 35 ms on the target CPU.
- **Runtime artifact:** merge LoRA into the base weights, export to ONNX, dynamic int8 quantize via `optimum`. Single file. Reproducible by re-running `scripts/train_router.py --config configs/full.yaml`. Config is versioned, weights are reproducible from config + seed.

**Universality validation that survives distillation.** The held-out multilingual slice is the gate: hold out *all* PT and *all* IT examples from training (zero contamination), and require that on these languages the model's recall is within 0.05 of the Spanish recall and within 0.07 of the English recall. If PT/IT drops by more than that, the distillation has overfit to ES/EN — fail the run and re-balance the training language mix. This is the bare minimum to claim universality.

---

## H. ANTI-OVERFIT NOTE

The 1733-query corpus is small and precious. Use it as a **test set with discipline**, not as training data that happens to be evaluated on itself.

**H1. Contamination boundary.** The 80/20 hash split already in place is good. Two additional guardrails:
- Hash on a *normalized* form of the query (lowercase, strip punctuation, collapse whitespace, NFKC) so that "Anota X" and "anota X" end up in the same split.
- Hash on the *tool label* too as a tiebreaker on duplicates, so a near-duplicate that should logically be in test cannot leak into train via a paraphrase.
- Synthetic data generation MUST use only the train side of the hash split as exemplars, and must dedup against the *full* 1733 by normalized cosine (e.g. >0.95 similarity to any holdout query → drop).

**H2. Slice-based reporting.** Report each of these on every run, never just an aggregate:
- `no_tool` (≈468 queries) — measures abstain quality.
- `continuation` (queries identifiable as follow-ups by dialog id or by syntactic markers like "lo", "subelo", "cierralo", "más", short pronoun-only Spanish utterances) — measures state integration.
- `short` (≤4 words) — measures BM25-killer cases.
- `multilingual non-EN` — measures cross-lingual.
- `held-out language` (PT + IT, never in training) — measures universality.
- `read-vs-write paired` (utterances where the tool depends on read vs write framing) — measures the F1 structural fix.

Reporting only an aggregate hides which slice is doing the work; a model that hits 0.90 aggregate by being 0.99 on the easy slice and 0.40 on the hard slice is worse than one that hits 0.88 by being 0.85/0.91 across the board.

**H3. The ceiling.** Perfect routing is *not* achievable under the hard constraints. Honest ceiling estimate:
- **Aggregate recall realistic ceiling: ~0.92.** Why not higher: (a) the corpus has irreducible labeling ambiguity — multi-tool queries that one annotator labels with 2 tools and another with 3; (b) some genuinely ambiguous turns ("ponlo en azul" with no prior context) cannot be deterministically routed; (c) STT-noisy queries in the corpus. The published ceiling on tool retrieval more broadly is low — ToolRet (ACL 2025) reports under 52% Recall@10 across SOTA retrievers — but that's on much harder multi-step tool selection; on a 65-tool single-call corpus with hand-labeled ground truth, 0.92 is the right ballpark.
- **No-tool keep realistic ceiling: ~0.80–0.85.** Why: DROID hits 95.8% Unknown F1 on CLINC-150, but CLINC-150 is a clean, English-only, single-turn intent classification dataset; this corpus is voice-noisy, multilingual, and the no_tool class includes "small talk", "ambiguous", and "needs clarification" mixed together. ~0.80 is the realistic asymptote for a 50ms CPU router; getting above it would require either a bigger model (busts latency) or rewriting the no_tool class label structure. Even MetaTool's binary "should I use a tool?" benchmark sees only GPT-3.5 exceed 70% F1 zero-shot (smaller models lower), which puts the absolute frontier in perspective.
- **Tool-call success rate (router × Gemma): ceiling ~0.85 user-visible** given Gemma 4's current llama.cpp issues. The router can hit 0.92, but if 10% of high-confidence single-tool offerings still leak as text, the user sees 0.83. Section F4's mitigations bring this back to ~0.88.

The right framing for the user: **the goal is not 100%. The goal is 0.90 recall / 0.78 no-tool keep / 0.85 user-visible success, slice-balanced, at ≤50 ms.** Anything above that is a stretch goal contingent on the offline training recipe converging on synthetic data, and on llama.cpp fixing the Gemma 4 tool-call parser. Set expectations there.

**H4. Falsifiability of every step.** Each step in Section D has a numeric ship threshold and a slice. If a step misses, do not ship it. If the cheap steps (1–4) already get to 0.70 no-tool keep, **do not run Step 5** — the ambition tax was already paid once. This is the v2 lesson written as a process rule.

---

*End of audit. Re-anchoring every code-level claim to actual line ranges in `core/planner.py`, `core/router_v2.py`, `core/agent.py`, and `scripts/router_eval.py` is the necessary next step before any deletions in Section E; the ZIP could not be opened in this environment.*