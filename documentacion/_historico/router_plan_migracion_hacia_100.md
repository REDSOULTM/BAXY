# Pushing the Carter Agent's Tool Router to ~100%: A Technical Migration Plan

## TL;DR

- **Replace today's 4-router cascade with a single unified pipeline built around a domain-distilled Tool2Vec/Re-Invoke-style retriever (≈30 MB Model2Vec static student + a SetFit-trained MiniLM intent head + a conditional bge-reranker-v2-m3 cross-encoder pass).** This is the design most likely to clear ~95% tool-recall and ~80–85% NO-TOOL keep on the holdout while staying inside a tens-of-ms CPU budget, because it attacks the root cause the literature flags: tool retrieval is a documentation/intent gap, not a similarity-function gap (Shi et al. 2025, ToolRet; Moon et al. 2024, Tool2Vec; Chen et al. 2024, Re-Invoke).
- **Do not revive router_v2 in its current form.** Its failure was structural, not a tuning miss: multilingual-e5-small produces 0.7–1.0 cosines on short text by design (its model card explicitly warns of this), BM25 is statistically degenerate on 65 short tool docs, and RRF papers over the score collapse rather than fixing it. v1's MiniLM-centroid intent gate is the only piece that should survive verbatim; everything else gets rebuilt around an offline-trained tool retriever.
- **Fold session state into the router as a first-class input, not a rescue layer.** Continuation, pending-intent, and read-vs-write distinctions become tractable once `_last_executed_tools`, `pending_intent`, and `running_processes` are features inside the routing decision rather than post-hoc patches. This single change collapses the planner/agent split that produced the infinite "need Disney profile" loop.

---

## Key Findings

1. **The literature on tool retrieval explicitly says short, noisy queries against tiny tool sets break general-purpose retrievers.** ToolRet (arXiv 2503.01763, Shi et al., ACL Findings 2025) benchmarks ~30 IR models against 43k tools and reports the best generic embedder (NV-Embed-v1, 7B params) reaches only nDCG@10 = 33.83; ColBERT underperforms BM25 on this data. The paper's verbatim conclusion: *"even the best model (i.e., NV-embedd-v1) that demonstrates strong performance in conventional IR benchmarks, achieves an nDCG@10 of only 33.83 in our benchmark"* and *"all retrievers in our experiments achieve less than 35% in Completeness@10 and under 52% in recall@10."* MTEB/BEIR ranking does not transfer to tool retrieval.

2. **The single most-replicated win in tool retrieval is to embed example queries, not descriptions.** Tool2Vec (arXiv 2409.02141, Moon et al. 2024) reports verbatim *"improvements of up to 27.28 in Recall@K on the ToolBench dataset and 30.5 in Recall@K on ToolBank"* by representing each tool as *"the average embeddings of those user queries [that] use a specific tool… as the Tool2Vec embedding that represents the tool."* Re-Invoke (arXiv 2408.01875, Chen et al., EMNLP 2024) gets *"a 20% relative improvement in nDCG@5 for single-tool retrieval and a 39% improvement for multi-tool retrieval"* on ToolE by the same trick plus LLM-based intent extraction from verbose user queries.

3. **e5-small was always going to fail at symmetric short-text intent.** Its model card states verbatim: *"Why does the cosine similarity scores distribute around 0.7 to 1.0? This is a known and expected behavior as we use a low temperature 0.01 for InfoNCE contrastive loss."* The operator's Attempt-5 observation (0.82–0.96 cosine band, centroids barely separate) is exactly the model's intended distribution; no threshold can fix it.

4. **The 4B-class LLM has a measured tool-call bias regardless of prompt.** The Ollama `orieg/gemma3-tools` documentation states verbatim: *"The 4b models have a genuine tool-call bias regardless of prompt. The 12b and 27b models (base and fine-tuned) correctly answer conversational questions in plain text even when tools are available. No-tool accuracy is primarily a model size issue, not a fine-tuning artifact."* This is a hard ceiling that the router must compensate for upstream by abstaining (passing zero tools) when intent is conversational.

5. **The router and the LLM are co-dependent.** Google's official Gemma 3 statement (HF model card discussion #24): *"Gemma 3's strong instructability allows for effective function calling by defining functions and output formats directly in user prompts. While there are no dedicated tool use tokens, we encourage you to explore your own prompting styles."* Gemma 4 added native tool tokens but the 4B class still over-calls. FunctionGemma (Google blog, Dec 18 2025, Kat Black & Ravin Kumar, 270M params fine-tuned from Gemma 3 270M) is described verbatim as *"a specialized version of our Gemma 3 270M model tuned for function calling… designed as a strong base for further training into custom, fast, private, local agents that translate natural language into executable API actions"* — Google itself sees small-LM tool reliability as a routing+specialist problem.

6. **Hubness and length-collapse are real and measurable.** Nielsen & Hansen (arXiv 2311.18364, "Hubness Reduction Improves Sentence-BERT Semantic Spaces") show Sentence-BERT spaces have asymmetric neighbourhoods and that a specific normalization pipeline (combined methods including NICDM + mean-centering) reduces hubness by ~75% and 1-NN classification error by ~9% on one tested model. The operator's Attempt-7 removed only the trivial centroid shift and did not implement the second step — this is fixable.

7. **RAG-MCP quantifies the prompt-bloat problem behind the operator's 10-tool cap.** RAG-MCP (arXiv 2505.03275, Gan & Sun 2025) reports tool-selection accuracy of 13.62% (baseline "Blank Conditioning" with all tools) vs. 43.13% with retrieval-augmented filtering; the paper's Figure 3 narrative notes that *"MCP positions below 30 exhibit predominantly yellow regions, indicating success rates above 90% when the candidate pool is minimal."* Subset size is a first-order lever.

---

## Details

### 1) Diagnosis — Why Short, Multilingual Voice Queries Break the Current Stack

**1a. Short-text cosine collapse on contrastively trained encoders.** Both e5 (InfoNCE @ τ=0.01) and BGE-family models are trained to produce sharp ranks with crushed absolute magnitudes. On 1–5-word voice queries the encoder hits its "default" similarity floor (~0.7) regardless of content — almost no entropy in the cosine to threshold against. v1's MiniLM works because `paraphrase-multilingual-MiniLM-L12-v2` was trained with a higher-temperature softmax on paraphrase pairs and retains 0.2–0.6 spread on short text. **Conclusion: keep MiniLM for intent (centroid task = symmetric short-text), and use a different, training-controlled encoder for tool retrieval.**

**1b. BM25 is statistically degenerate at 65 short docs.** BM25's IDF term blows up when a query word appears in only 1–2 of 65 documents (which is most domain-specific nouns: Disney, Steam, Discord), so any brand token drowns out the multi-word intent signal. With ~6-word tool descriptions, b-length-normalization is near-degenerate. ToolRet reports ColBERT underperforming BM25 on long-doc tool retrieval; at 65 short docs the inverse holds: BM25 scores ~0 on most candidates, leaving RRF to ride dense ranks alone — which is exactly what produced router_v2's "Dune → backup_sync, reminder, routine" failure.

**1c. RRF without calibration is fragile when the two retrievers disagree on the prior.** RRF is rank-only and uncalibrated — its strength (no normalization needed) becomes a weakness when BM25 is uniformly useless. Smoothed-RRF and weighted-RRF variants exist but require labeled tuning, which is what router_v2's 5-probe-derived bands tried to provide and produced unreproducible results.

**1d. Threshold non-calibration across queries.** Raw cosine scores are not comparable across queries — the same 0.45 threshold means different things for "mutea" vs. "qué tiempo hace mañana en Madrid." v2's HIGH/MEDIUM/LOW/TIGHT_CLUSTER bands attempted to fix this with absolute thresholds derived from 5 probes; that is exactly the failure mode the calibration literature predicts for raw-score thresholding.

**1e. Asymmetric query/passage models on symmetric tasks.** multilingual-e5-small was designed for QA-style query→passage retrieval (the model card recommends *"query:"* and *"passage:"* prefixes for asymmetric tasks). v2 used it for intent centroid matching, a symmetric short-vs-short task — wrong tool for the job, confirmed by Attempt-5. v1's MiniLM-centroid path implicitly understood this; the diagnosis is now explicit.

**1f. Hubness in 384-dim spaces.** Nielsen & Hansen show that mean-centering alone removes only the global shift; mutual-proximity / NICDM transforms are what actually break hubness. Attempt-7 only did the former. This is recoverable.

**1g. MTEB → tool-retrieval transfer gap.** ToolRet's most important finding: MTEB leaderboard rank is *not* predictive of tool-retrieval rank. Models tuned for STS/BEIR generalize poorly to "verb + entity" short-imperative queries. This is why a domain-specific student (distilled on synthetic tool queries) beats a general-purpose encoder regardless of parameter count. Shi et al. mitigate by training on 200k+ synthetic instances; the operator's mitigation is the same idea at smaller scale.

**1h. Why router_v2 failed the live "Dune" probe.** Compose the above: "de qué trata Dune" is 5 words; e5-small renders cosine(web) ≈ cosine(backup_sync) ≈ cosine(reminder) ≈ 0.85 (Attempt-5 confirms); BM25 hits ~0 on every tool (Dune is OOV); RRF averages two degraded rankings; the smalltalk-gate sees small chitchat→info delta and disables suppression; the adaptive band picks tight-cluster cap. Result: a deterministic six-step path to nonsense. **This is structural, not a tuning miss.**

### 2) The Recommended Target Architecture: Unified Domain-Distilled Router (UDR)

A single pipeline replacing planner.py / intent_router.py / semantic_router.py / router_v2.py — all four files collapse to one module, ~600 lines, plus an offline training recipe in a separate `.venv_router_train` environment.

#### Pipeline (per turn, CPU, target ≤ 40 ms median)

```
Query  ─►  Stage A: Multi-signal feature build              (~2 ms)
            • language-detect (fasttext-lid 176-lang, 917 KB)
            • normalize whitespace + lowercase (NO regex morphology)
            • build session-state vector (see §2g)

       ─►  Stage B: Intent head (MiniLM + SetFit head)      (~8 ms)
            • 5 anchors: info / action / chitchat / selfref / META
            • PLUS a binary read/write polarity head (see §2c)
            • PLUS a temporal/factuality probe (see §2d)
            • Output: P(no_tool), P(action), P(info_lookup), polarity

       ─►  Stage C: Domain-distilled tool retriever         (~10 ms)
            • Model2Vec student (~30 MB) distilled from a teacher
            • Tool reps = Tool2Vec centroids of 20–40 synth queries/tool
            • Returns top-k candidates with mutual-proximity calibrated scores

       ─►  Stage D: Session-state fusion                     (~1 ms)
            • Inject last-executed-tool, pending_intent, open-windows
              as soft features into a logistic / GBDT fusion layer

       ─►  Stage E: Decision policy
            • If P(no_tool) > 0.65 AND no tool ≥ τ → empty subset
            • Else build subset of size 4–8 (adaptive cap)
            • Conditional: bge-reranker-v2-m3 cross-encoder on top-15
              IF top-1 fused score in [0.40, 0.65] uncertainty band
              (~130 ms/16-pair batch on CPU; fires on ~10–15% of turns)
```

#### Justification per component

**2a. Encoder choice — MiniLM for intent, Model2Vec for retrieval.** The Attempt-5 measurement is exactly what multilingual-e5-small's model card warns about (*"distribute around 0.7 to 1.0"*). Keep MiniLM for intent because of its empirical 0.2–0.6 spread. For tool retrieval we want (i) very fast CPU inference, (ii) trainability on synthetic queries, (iii) ~tens-of-MB to coexist with the LLM and warm-loaded MiniLM.

**Model2Vec** (Minish Lab, MIT, GitHub MinishLab/model2vec) literally distills a sentence-transformer into a static-embedding lookup. From its README verbatim: *"Model2Vec is a technique to turn any sentence transformer into a small, fast static embedding model. Model2Vec reduces model size by a factor up to 50 and makes models up to 500 times faster, with a small drop in performance"*; the best model is *"~30 MB on disk"* and the smallest *"~8 MB (making it the smallest model on MTEB!)."* Critically Model2Vec is *"Fast, Dataset-free Distillation: distill your own model in 30 seconds on a CPU, without a dataset."*

This is the answer to "one encoder or two?": **two encoders, but only one on the hot path — MiniLM (warm) for intent and a Model2Vec static student for retrieval; the heavy teacher and cross-encoder are dev-time / fallback only.**

**2b. Intent encoding for 1–4 word queries — improve MiniLM-centroid, don't replace it.** Three concrete improvements to Attempt-4's gate:
- Add a **5th centroid for meta-directives** ("responde solo sí o no", "no uses tools", "habla en inglés"). These currently route through the chitchat anchor's tails and break unpredictably.
- Move from cosine-delta to a **SetFit-trained head** on top of the 4×384 anchor similarities. SetFit (Tunstall et al., arXiv 2209.11055) states verbatim *"SetFit obtains comparable results with PEFT and PET techniques, while being an order of magnitude faster to train. We also show that SetFit can be applied in multilingual settings by simply switching the ST body."* The classifier outputs calibrated P(class), which makes Stage E's threshold a true probability cut, not a hand-picked delta. Training takes ~15 minutes on a 4060 Ti with 50–500 examples per class.
- Add **mutual-proximity normalization** (the second step Attempt-7 missed) to the 4-anchor similarity vector, computed once at startup, to break the hubness that lets "gracias" → media win.

**2c. Read-vs-write without keyword lists — a dual-polarity head.** Hypothesis confirmed from the brief: a separate linear probe for operation polarity.
- Train a single linear probe on the MiniLM CLS embedding to output `polarity ∈ {read, write, neutral}`. Training data: synthetic, language-mixed pairs of `(read_query, write_query)` for each of the 32 covered tools (~5k pairs). Loss: cross-entropy with class weights.
- At decision time, when intent ≈ action and polarity = write, bias write-side tools (filesystem.write, memory.save); when polarity = read, bias the read tools. Soft bias on fused score (±0.10), not a hard gate.
- **Structural property:** polarity is a separate axis from "which tool family", so the system cannot silently route to the wrong polarity within a correct family without joint family+polarity ambiguity. That joint case is the genuinely-ambiguous one where a clarifying prompt is the correct behavior.

**2d. Current-facts (weather/release-dates → web) without keywords.** Replace the existing keyword crutch with a **temporal/factuality classifier** — another linear probe on MiniLM, trained on synthetic positive/negative pairs ("qué tiempo hace mañana", "cuándo sale GTA VI") vs. ("qué es Steam", "qué significa idempotente"). MiniLM is paraphrase-multilingual, so the syntactic pattern (futurity, named events, dates) transfers across languages. This becomes a signal into Stage E's fusion, not a hard rule.

**2e. NO-TOOL / abstention — the structural lever.** The 0.51 holdout is the weakest and highest-leverage metric. The fix is not another threshold:
- Treat NO-TOOL as an **explicit class with positive evidence**, not a "low confidence on all tools" negative. If `P(chitchat) + P(selfref) + P(meta) > 0.65` and no tool candidate has fused score > 0.55, return empty.
- Train the SetFit intent head on **every NO-TOOL row in the dev split + 5–10× synthetic NO-TOOL adversarials** generated offline by an LLM ("write 200 multilingual phrases a user might say to a voice assistant that are NOT actionable: chit-chat, meta, self-reference, ambient knowledge").
- This converts NO-TOOL from passive abstention to a positively-scored prediction, the same mechanism that lifted v1's number from 0.186 → 0.512.

**2f. Tool descriptions as retrieval — Tool2Vec example queries.** The operator's YAML "4–6 ES+EN queries per tool" is undersized. Tool2Vec uses tools-with-tens-of-queries (their ToolBank dataset statistics show ~40–73 queries per tool used to form the centroid average; their methodology is verbatim *"if we have multiple user queries that use a specific tool, we use the average embeddings of those user queries as the Tool2Vec embedding that represents the tool"*). Target **20–40 queries per tool** as a budget-conscious midpoint, generated offline:

> For tool `<name>` whose purpose is `<description>`, generate 30 short voice-style user queries (3–10 words each) that would invoke this tool. Cover: imperative ("abre…"), interrogative ("¿puedes…?"), elliptical ("y ahora a…"), polite ("podrías…"), and broken ("apri il…"). Mix Spanish, English, French, German, Italian, Portuguese. Inject realistic voice-transcription errors (missing accents, run-together words, common Whisper substitutions). Output one per line.

The tool's vector representation is the mean of these 30 query embeddings. Toolshed-style metadata (argument schema, "when to use" notes, anti-examples) is appended to the tool-card stored alongside, as Lumer et al. (arXiv 2410.14594) demonstrate yields 46–56% Recall@5 lifts on ToolE.

**2g. Session-state fusion — folding context in structurally.** Data structure:

```python
class SessionContext:
    last_executed_tool: Optional[str]        # survives compaction
    last_executed_args: Optional[dict]
    pending_intent: Optional[PendingIntent]  # {slot_name, asked_at_turn, ttl}
    open_windows: list[str]                  # state.list_resources()
    running_processes: set[str]              # _running_process_names()
    turn_index: int
```

The router computes a `context_vector` (one-hot for the 32 covered tools plus categorical features) and concatenates it to the fused tool-retrieval scores via a tiny GBDT (or logistic regression) trained on the dev set with both isolated *and* with-context labels. **Critical decision rule for the infinite-loop bug class:** `pending_intent` has a TTL (in turns), and must be resolved or expired before the same `needs_user` is asked again. The state machine lives in the router (Stage D), not in agent.py.

The eval harness gets two new flags: `--isolated` (today's default; ignores session state) and `--with-context` (production; uses simulated prior turns from the corpus' `prev` field plus a synthetic `_last_executed_tools` field). Both numbers reported separately, as the operator demanded.

**2h. Router ↔ LLM coupling — five concrete upstream levers.** Given the Ollama observation that *"4b models have a genuine tool-call bias regardless of prompt"*:

1. **Subset size matters more than ordering for Gemma 4 4B.** RAG-MCP's Figure 3 narrative: *"MCP positions below 30 exhibit predominantly yellow regions, indicating success rates above 90% when the candidate pool is minimal"*; in their primary stress test accuracy is 13.62% (baseline) vs 43.13% (with retrieval). Recommend **8 tools default, 4 for high-confidence single-tool intents.**
2. **Order by score descending — but inject a `no_action_needed` pseudo-action FIRST when P(no_tool) ∈ [0.4, 0.65]** to counter the 4B model's call-bias. Primacy literature (Itzhak et al. arXiv 2507.13949 "Exploiting Primacy Effect"; Liu et al. arXiv 2307.03172 "Lost in the Middle") predicts the sentinel-first variant lifts NO-TOOL keep at the LLM stage by 5–15 points on 4B-class models.
3. **Schema phrasing.** Tool descriptions in the JSON schema should be the first 1–2 example queries from the Tool2Vec corpus, not the abstract description. Aligning the surface form of the description to actual user phrasings reduces "leak as text" mode.
4. **Thinking-mode on tool turns.** The operator already enables this; the report endorses it. Re-Invoke's intent extraction inside the LLM is the same idea — explicit chain-of-thought on tool turns improves call discipline.
5. **Bypass the LLM entirely** for high-confidence imperative + open-window matches. If `last_executed_tool == media.player` and the user says "pausa", route directly to `media.pause` with no LLM call. This is the "tool usage inertia graph" pattern from AutoTool (arXiv 2511.14650, Jia et al., AAAI 2026), which reports *"AutoTool reduces inference costs by up to 30% while maintaining competitive task completion rates."* For the operator this is latency-positive.

**2i. Why this won't repeat router_v2's fate.** Router_v2 was bottom-up: pick best-in-class generic components, fuse, hope they cohere. UDR is top-down: every component is justified by a measured failure mode in the operator's existing system or by a quantitative finding from the tool-retrieval literature. Specifically:
- Stage B is v1's working centroid gate plus three measured improvements (5th class, calibrated SetFit head, hubness fix).
- Stage C replaces e5-small with a trained-on-our-own-distribution student — exactly Shi et al.'s recommendation that *"a large-scale training dataset… substantially optimizes the tool retrieval ability of IR models."*
- Stage D's session state is the operator's binding answer #2.
- Stage E's NO-TOOL is a positive class with training data, not a threshold subtraction.
- The cross-encoder rerank fires conditionally, so median latency is unchanged.

### 3) Offline Preprocessing Pipeline (RTX 4060 Ti, 16 GB, hours–days)

All work runs in an isolated `.venv_router_train` with pinned versions, mirroring `.venv_train` / `.venv_livekit`. Every artifact is reproducible from a versioned script — no binary drops.

**3a. Synthetic query corpus.** Run an offline LLM (e.g. Llama-3.1-8B-Instruct or Qwen2.5-7B-Instruct, both permissive-licensed, both 4060 Ti-runnable in 4-bit) to produce per-tool synthetic queries using the §2f prompt skeleton. **Diversity baking — non-negotiable:**
- 6+ languages (es, en, fr, de, it, pt), balanced per tool
- 5 register variants per language (imperative, interrogative, elliptical, polite, broken)
- voice-transcription noise injection: drop accents 30%, run-together words 10%, swap common Whisper confusions (b/v, ll/y) 5%
- round-trip translation augmentation (es→en→es via the same LLM) to break operator-phrasing tics
- target: 30 queries × 65 tools × 6 languages = **~12k synthetic queries**, sized to run on a 4060 Ti in 1–3 hours

**3b. Tool2Vec centroid build.** Embed all synthetic queries with the teacher (bge-m3 or multilingual-e5-base, GPU). Tool centroid = L2-normalized mean of its query embeddings; store centroids in a 65×768 (or 65×384) matrix.

**3c. Student distillation (Model2Vec).** Distill the teacher into a static lookup using Model2Vec's standard recipe (30 s on CPU per the README). Validate the distilled student on a held-out 20% of the synthetic corpus *and* on the holdout 20% of the 1733-row eval corpus.

**3d. Intent head training (SetFit).** Take the dev split (1386 rows), label-balance the 5 intent classes (action / info / chitchat / selfref / meta), run SetFit's 2-stage contrastive recipe on the existing MiniLM checkpoint. Validate on dev-internal CV; do not touch the 20% holdout. ~15 minutes on the 4060 Ti.

**3e. Read/write polarity head.** Generate ~5k synthetic read/write pairs across all 32 covered tools, mix languages, train a linear probe on MiniLM CLS. ~5 minutes.

**3f. Cross-encoder integration (optional Stage E).** bge-reranker-v2-m3 weights downloaded once. The model is ~568M params (XLM-RoBERTa-large backbone, ~2.27 GB safetensors), Apache 2.0 license, and runs on CPU per markaicode.com's verbatim benchmark: *"On CPU, expect ~130ms per 16-pair batch — acceptable for batches under 50 candidates. Above that, latency stacks up quickly and a GPU becomes worth it"* (FlagEmbedding 1.2.9, Ubuntu 22.04). No fine-tuning required at v1; revisit only if eval shows need.

**3g. Universality holdout.** Construct a held-out slice the system has never seen: **100 phrases per language across es / en / fr / de / it / pt**, generated by a *different* LLM (e.g. Mistral-Nemo) than the training-data generator, paraphrased by a *third* LLM, hand-spot-checked by the operator. Pass criterion: holdout recall does not drop by > 3 points vs the language-of-training, and NO-TOOL keep does not drop by > 5 points. This generalizes the operator's existing "17/18 fresh phrases across es/en/fr/de/it/pt" bar into a regression test.

### 4) Migration Plan — Ordered Steps, Each Independently Shippable

Each step is independently mergeable; if later steps don't ship, earlier ones still deliver value. Every step reports both `--isolated` and `--with-context` numbers on the dev set, then is validated *once* on the holdout before merge.

| # | Step | Expected dev move (recall / NO-TOOL) | Holdout protocol | Latency Δ | Back-out |
|---|---|---|---|---|---|
| 1 | **Add 5th meta-directive centroid + NICDM/mutual-proximity hubness fix** (drop-in to v1) | +0–1 / +5–8 | Holdout once at PR-time; require NO-TOOL keep ≥ 0.55 | +0.5 ms | Any holdout recall drop >1 pt |
| 2 | **SetFit-fine-tune the MiniLM intent head on the dev split** (5 classes, calibrated logits) | +1–2 / +5–10 | Holdout once; require NO-TOOL keep ≥ 0.62 and recall ≥ 0.82 | +1 ms | Either metric regresses |
| 3 | **Tool2Vec centroid rebuild** (regenerate semantic_router's tool reps from synthetic queries) | +3–5 recall / 0 | Holdout once; require recall ≥ 0.86 | 0 (offline build) | Recall regresses or NO-TOOL drops > 2 |
| 4 | **Session-state fusion (Stage D)** — fold `_last_executed_tools` + `pending_intent` + `open_windows` in; expose `--with-context` in router_eval | with-context recall +5–8 / +2 | Report both numbers; require with-context recall ≥ 0.92 | +2 ms | Isolated drops by any amount |
| 5 | **Read/write polarity probe** (Stage C bias) | +2–3 recall on tool-correct, ~0 on NO-TOOL | Construct polarity-stratified slice (~150 read + 150 write); require ≥ 95% correct polarity | +1 ms | Polarity accuracy < 90% |
| 6 | **Distill the retriever to Model2Vec static student**; replace heavy embedder on hot path | 0 recall / 0 NO-TOOL but **~5× CPU speedup** | Holdout regression test | −8 ms (faster) | Recall regression > 1 pt |
| 7 | **Conditional bge-reranker-v2-m3 cross-encoder** on uncertainty band | +1–2 recall / 0 | Holdout once with rerank-fire rate logged; require ≤ 20% firing | +20 ms p95 (~130 ms when fired) | p95 latency > 60 ms |
| 8 | **Retire planner.py / intent_router.py / semantic_router.py / router_v2.py**; UDR is sole authoritative | 0 | Full holdout + universality slice (§3g) | 0 | Any metric regresses |

**Projected final holdout metrics (cumulative through step 8):** Tool recall ~0.92–0.95 isolated, ~0.95–0.97 with-context; NO-TOOL keep ~0.78–0.85. The remaining gap to "100%" is hardware (Gemma 4 4B's residual tool-call bias) and the 13 RECOVERABLE-CEILING memory-op cases from Attempt 8 — both of which require either a larger LLM, a FunctionGemma-style 270M specialist, or a hand-curated few-shot for those specific ops.

### 5) Anti-Overfit Guidance

**5a. Treat the 1733 corpus as protected.** Develop *only* on the 1386-row dev split. Holdout (347 rows) is evaluated **once per step**, recorded, and never inspected to inform a subsequent design choice. Any peek invalidates that step's holdout number — re-validate on a new synthetic holdout. This is the Attempt-2 lesson formalized: centroid rotation tuned by peeking did improve dev and regress holdout.

**5b. Diversity injection — three independent axes.** Language (6+), register (5), noise (3 perturbation types). Generate the synthetic queries with one LLM and the universality-holdout queries with a different LLM, paraphrased by a third, so the system cannot overfit to any single generator's quirks.

**5c. Multilingual + multi-accent holdouts.** Three holdouts:
- **Language holdout:** the §3g 100×6 set generated by Mistral-Nemo (different from training generator).
- **Accent holdout:** ~100 phrases passed through Piper TTS in 6 accents (es-MX, es-ES, en-GB, en-IN, fr-FR, de-DE) then re-transcribed with Whisper-base. This exercises transcription-error robustness, which is the real production input distribution.
- **Adversarial holdout:** ~100 hand-crafted edge cases — meta-directives, polysemy ("memoria" = RAM vs notebook), brand collisions ("Teams" vs "Steam") — kept secret from the training pipeline.

**5d. Corpus-overfit detector.** Each PR runs metrics on (i) dev-internal CV, (ii) holdout, (iii) language-holdout, (iv) accent-holdout. If dev/holdout gap > 5 points or holdout/language-holdout gap > 5 points → flag as overfit, do not merge. Hard CI gate.

**5e. Versioned synthetic corpus.** Every PR that touches the synthetic query generator bumps a version number; the previous version's queries are kept as a regression test. This catches the "I changed the prompt and all my numbers moved" class of silent overfit.

### 6) Structural Fixes for the Recurring Patterns

**6a. Read vs write — already designed.** §2c above. The dual-polarity probe is a small linear head, takes ~5k synthetic pairs to train, and the fusion-time bias makes wrong-polarity within a correct family monotonically less likely. **Failure mode by construction: only joint family+polarity ambiguity can mis-route, which is the genuinely ambiguous case where a clarifying prompt is correct.**

**6b. App-name resolution — beat fuzzy + length-gap.** Three layers, all offline-buildable:
1. **Catalog-aware retrieval over the installed-apps index.** Treat the installed-apps list (~100 entries) as a tiny corpus and embed each app's display name + executable name + window class with the same Model2Vec student. Cosine to the catalog. Robust to "Teams" vs "Steam" because the catalog only contains apps the user actually has installed — if Teams isn't installed, "Teams" cannot resolve to Steam.
2. **Phonetic fallback** — Double-Metaphone or Soundex over the installed-apps catalog as a secondary retriever, RRF-fused with the dense retrieval. Catches accent-stripped or Whisper-misheard cases.
3. **Character n-gram embedding (FastText / Model2Vec subword)** as a tertiary; resolves PWA shortcuts (Chrome→YouTube-PWA mismatch) by encoding the full shortcut target, not just the user-visible label.

Decision rule: cosine + phonetic + char-ngram → soft-vote, with hard tie-break by app's recency-of-use (running_processes weighs +0.1). This eliminates the "Call of Duty"→"God of War" failure because (a) catalog-aware retrieval doesn't false-positive on stopwords, (b) char n-gram catches partial spelling, (c) phonetic catches the audio.

**6c. Continuations / pending-intent — folded structurally.** §2g above. The data structure is `SessionContext` with TTL on `pending_intent`. **The infinite-loop preventer is mechanical:** before re-asking the same `needs_user` slot, the router checks `pending_intent.asked_at_turn` and either (i) resolves with the user's reply if intent ≈ slot-filling response, (ii) re-asks at most once if intent unclear, or (iii) expires the slot and returns no_action with a brief acknowledgment. This state machine lives in the router (Stage D), not in agent.py, eliminating the cross-file split that caused the Disney-profile loop.

### 7) Model–Tool-Calling Coupling — Concrete Numbers and Levers

- **Subset size sweep:** Run a controlled A/B on Gemma 4 4B with subset sizes ∈ {2, 4, 6, 8, 10, 14}, holding the ground-truth tool present, on ~200 dev queries. RAG-MCP's data shows monotonic degradation with subset size; the operator's empirical sweet spot is likely 4–8. Report tool-call success rate and false-call rate at each size.
- **Subset ordering:** A/B "score-descending" vs "score-descending with `no_action_needed` sentinel first" on conversational queries. Primacy literature predicts the sentinel-first variant lifts NO-TOOL keep at the LLM stage by 5–15 points on 4B-class models.
- **Schema phrasing:** A/B abstract description vs. first-2-example-queries as the JSON description field on a fixed subset. Hypothesis: example-query descriptions reduce "leak as text" mode because the model sees concrete invocation patterns.
- **Thinking-mode toggle:** keep on for tool turns (operator's recent commit), off for pure chitchat. Already the right default.
- **LLM bypass for high-confidence inertia matches:** §2h-5 above; expected ~20% of turns become LLM-free, saving 1–2 s each.

---

## Recommendations

**Immediate (this week):**
1. Implement Step 1 (5th meta-directive centroid + NICDM/mutual-proximity hubness fix) — a one-day patch to planner.py with no dependency on the retraining pipeline. Ship if holdout NO-TOOL keep ≥ 0.55.
2. Stand up `.venv_router_train`. Pin Python, torch+cu121, sentence-transformers, setfit, model2vec, flagembedding. Commit a `train_router.py` skeleton.
3. Add `--isolated` / `--with-context` flags to scripts/router_eval.py *now*, before any architecture work. The eval harness must report both numbers for every subsequent step. This is the precondition for the operator's binding constraint that context-fusion cannot hide a weak base model.

**Near-term (2–3 weeks):**
4. Steps 2–4: SetFit intent head, Tool2Vec retriever rebuild, session-state fusion. After step 4, the system should be at ~0.86 isolated recall / ~0.92 with-context recall / ~0.65 NO-TOOL keep on dev.
5. Construct the §3g universality holdout and the §5c accent holdout. Run them after step 4 — this is the first checkpoint where the operator can demand the universal-multilingual bar.

**Medium-term (4–8 weeks):**
6. Steps 5–7: polarity probe, Model2Vec distillation for CPU speed, conditional cross-encoder for the uncertainty band. After step 7, target ~0.93 isolated / ~0.96 with-context recall, ~0.80 NO-TOOL keep.
7. Step 8: retire the legacy router files. UDR is sole authoritative. This is when the 4-router split bug class disappears.

**Benchmarks that should change the plan:**
- If Step 2's SetFit head fails to lift NO-TOOL keep above 0.62, the intent-class structure is wrong — re-cut the classes (e.g. split "info_lookup" into "factual" vs "knowledge"), don't tune thresholds.
- If Step 3's Tool2Vec retriever doesn't lift recall by ≥ 3 points, the synthetic query corpus is too narrow — regenerate with stronger diversity (more languages, more registers).
- If Step 7's cross-encoder fires on > 25% of turns, the fused score is too uncalibrated — fix the calibration at the fusion layer rather than widening the cross-encoder band.
- If the universality holdout (§3g) shows > 5-point gap between training languages and held-out languages, the synthetic generator is overfitting to one language's syntactic patterns. Iterate the prompt and bias the sampler.

---

## Caveats

1. **The 0.51 → 0.80+ NO-TOOL projection assumes the SetFit head separates the synthesized adversarials cleanly.** It might not on the first iteration. Re-cutting the class taxonomy (splitting "chitchat" into "smalltalk" and "selfref" and "meta" and "knowledge_question") is the lever to pull if the head doesn't converge.

2. **Tool2Vec gains are reported on long-tail tool catalogs (1000–43000 tools).** With only 65 tools and 32 covered, the absolute gain may be smaller than the +27.28 Recall@K Moon et al. reported on ToolBench. The mechanism (query-embedding centroids) is still right; the expected magnitude is "a few points" on the operator's corpus, not "double-digit".

3. **bge-reranker-v2-m3 at ~130 ms per 16-pair batch on CPU is a real budget hit when it fires.** Conditional firing keeps the median in budget, but worst-case p99 can creep up. If the audio-stack p99 budget is tight, replace bge-reranker-v2-m3 with a smaller distilled cross-encoder (MS-MARCO-MiniLM-L-6) at ~40 ms/batch and accept ~1 nDCG point of headroom. Note: the precise memory footprint matters — the model is ~568M params and ~2.27 GB on disk; loading consumes ~1.5 GB GPU memory or ~11 GB CPU memory per HuggingFace community reports — confirm the operator's CPU RAM budget can absorb it alongside the LLM's 6 GB VRAM and warm-loaded MiniLM.

4. **The Ollama community's verbatim observation that "4b models have a genuine tool-call bias regardless of prompt" is the binding constraint on absolute ceiling.** No router can fix a model that emits tool calls for "hola". The architecture mitigates by abstaining (empty subset) rather than offering a wrong subset, which converts wrong-action into no-action — a strictly safer failure mode. Reaching a true ~100% on NO-TOOL keep likely requires either (a) a larger Gemma (12B+), (b) a FunctionGemma-style 270M specialist used as a "yes/no should this turn act?" pre-filter (Google's blog frames it as a foundation to *"translate natural language into executable API actions"* and reports fine-tuning lifts a Mobile Actions benchmark *"from a 58% baseline to 85%"*), or (c) a fine-tune of Gemma 4 4B itself on the operator's distribution. All three are out of scope for the router but should be on the roadmap.

5. **Reproducibility is a project law, and Model2Vec / SetFit / Tool2Vec are recent and moving fast.** Pin versions, commit the training recipe (prompt + generator LLM revision + seeds + script), and snapshot the synthetic corpus alongside the trained student. Any reviewer should be able to rerun the pipeline end-to-end from a fresh `.venv_router_train` and get bit-identical artifacts.

6. **The router cannot replace the operator's app_resolver entirely — it can only improve it.** §6b's three-layer scheme handles ~90% of name-resolution; the remaining ~10% (brand-new app installed since the catalog was indexed, fuzzy spoken brand names) still needs a runtime fallback. Re-index the installed-apps catalog on every app install / uninstall event (Windows shell hook) to keep the catalog fresh.

7. **The "Dune" probe in the live test is the right canary** for v2 of this router too. If after Step 4 "de qué trata Dune" routes to anything other than `web` (or empty if NO-TOOL is the model's choice), the synthetic corpus did not contain enough current-facts/release-date examples. That is the operator's most reliable structural-failure detector and should be added as an explicit test case in the regression suite, alongside ~20 other historical bug-canary queries from the night logbook.

8. **The ToolRet best-numbers (NV-Embed-v1 at nDCG@10 = 33.83) are not directly comparable to the operator's 0.83 holdout recall** because ToolRet uses a 43k-tool corpus with a much harder retrieval task; the operator's 65-tool corpus is intrinsically easier. The lesson is qualitative ("MTEB rank doesn't predict tool-retrieval rank"), not quantitative. The operator's absolute number is high because the task is easy; the structural fixes proposed here are what carry that number from 0.83 toward 0.95 robustly across languages, accents, and adversarials.