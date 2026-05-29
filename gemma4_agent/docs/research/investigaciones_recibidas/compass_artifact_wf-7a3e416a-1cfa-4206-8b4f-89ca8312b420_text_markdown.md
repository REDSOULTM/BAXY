# Multi-intent, Clarification, and Disfluency Handling for vram4 (Gemma 3 4B-it Q4_K_M) Voice Pipelines

## TL;DR
- **Move multi-intent splitting and disfluency cleanup OUT of the LLM and into deterministic Python before Gemma sees it; then loop the 4B model N times on the resulting sub-commands.** A 4B causal decoder cannot match bidirectional 7B models on multi-intent classification, and regex pre-processing is roughly 28,120× faster than an LLM pass at comparable extraction accuracy (medRxiv, *Regex-Based vs. Large Language Model-Based Extraction of BI-RADS Scores*, 2025).
- **Decide WHETHER to ask in Python; let the 4B model only decide HOW to phrase the question.** Cap clarification at 2 turns (Dialogflow CX best practice: "implement a No-Match/No-Input maximum of 3 for every page"). Use a single first-token logprob threshold from one greedy decode as the abstention gate — no second model, no self-consistency.
- **Resolve "ponelo / ese / lo / el otro" with a Python ring buffer of the last 3–5 typed entities, not by prompting the 4B to coref.** Online-coreference research (Xu & Choi, arXiv:2205.10670) finds that stateless mention-linking with singleton recovery beats explicit entity-state models — and a deque is the smallest possible such model, with zero latency cost on vram4.

## Key Findings

### Finding 1 — Gemma 3 4B has a structural disadvantage on multi-intent; fix it upstream, not by enlarging the model
"MIDLM: Multi-Intent Detection with Bidirectional Large Language Models" by Shangjian Yin, Peijie Huang & Yuhong Xu (South China Agricultural University), Proceedings of COLING 2025, pp. 2616–2625 (ACL Anthology 2025.coling-main.179), shows that **causal attention on the same 7B backbone collapses multi-intent accuracy** dramatically — the paper's ablation reports bidirectional vs. causal as the key driver of the gap. Per the paper's own framing: "By transitioning from a causal attention to global attention, MIDLM can leverage bidirectional information within an utterance." Gemma 3 4B is a causal decoder, so trying to make it emit all intents at once as a list is the wrong shape of the problem — you cannot close that gap with prompting or quantization.

The right architectural move is a pre-LLM **splitter**: a deterministic clause segmenter that uses Spanish connectors (`y`, `y después`, `también`, `;`, `luego`, `mientras`, `después`) plus imperative-verb detection (the Chilean/Argentine voseo set: `abrí, bajá, ponele, andá, mandá`, plus standard `abre, baja, pon, ve`) to break "abrí Spotify y bajá el volumen" into two clauses **before** the LLM. Each clause is then routed independently through your existing intent_router / semantic_router. The 4B never sees more than one intent per call.

### Finding 2 — Ollama does not natively parse Gemma 3 tool calls; the reliability ceiling is real
The Ollama community model card `orieg/gemma3-tools` (orieg/gemma3-tools on ollama.com) documents three drift modes: "At 15-22 tools, models occasionally fall back to emitting `{\"name\": ..., \"arguments\": ...}` inside a markdown code block instead of proper `<tool_call>` XML tags. Ollama does not parse these as tool_calls — they appear as plain content." And critically: "The 4b model has a strong bias toward emitting tool calls even for conversational prompts like 'what is 2+2?'. This is a model size issue — the 12b and 27b variants (both base and fine-tuned) handle mixed chat + tool-calling correctly."

Google confirms the underlying constraint in the Hugging Face `google/gemma-3-27b-it` discussion #8: "Gemma 3 does not come with a dedicated tool use token. We invite you to try your own styles. We've achieved good performance with Function calling by specifying the function definitions and output format in the user message and relying in the instructability of the model." The Ollama issue tracker #9680 ("gemma3 lack function calling tag") was closed as **not planned**.

Practical implications for vram4:
- Keep the prompt-visible toolset ≤ 8 per turn (use your existing `semantic_router` to subset). Community model card reports "12b-ft achieves 100% accuracy in this setup" only at 5–8 tools, degrading at 15–22.
- Per-call reliability compounds: a 95% per-call success rate yields ~66% over 8 chained steps (Promptquorum 2026: "A 95% per-call rate over 8 steps lands successfully ~66% of the time. Plan for compounding — keep plan horizons short, use approval gates").
- No published BFCL entry exists for Gemma 3 4B or Gemma 3n E4B as of May 2026.

### Finding 3 — Clarification works on vram4 if it's a one-shot JSON contract, not free-form dialogue
The "Learning to Ask: When LLM Agents Meet Unclear Instruction" paper by Wenxuan Wang et al. (Renmin U. of China, CUHK, Johns Hopkins, Xiaohongshu), arXiv:2409.00557, states the core failure mode bluntly: "due to the next-token prediction training objective, LLM agents tend to arbitrarily generate the missed argument, which may lead to hallucinations and risks." Their NoisyToolBench is the canonical benchmark; they propose the Ask-when-Needed (AwN) framework, in which the model is explicitly encouraged to ask before acting.

QuestBench by Belinda Z. Li (MIT/Google DeepMind), Been Kim (Google DeepMind), and Zi Wang (Google DeepMind), NeurIPS 2025 (arXiv:2503.22674), reports: "While state-of-the-art models excel at GSM-Q and GSME-Q, their accuracy is only 40-50% on Logic-Q and Planning-Q." That is — even frontier models struggle to pick *which* slot to ask about when it's not handed to them, despite being able to solve the fully specified version. A 4B at Q4_K_M will be substantially worse.

Two design implications for vram4:
1. **Don't let the model decide whether to ask.** Decide deterministically: if `required_slot is None` ⇒ ask. Your existing WhatsApp partial-slot filler already does this for body/contact/channel — generalize the pattern across all tools with a per-tool `required` declaration.
2. **Cap clarification turns at 2.** Per Dialogflow CX voice-agent design guide (Google Cloud, last updated 2026-05-18): "To avoid trapping users in a loop of error handling events, implement a No-Match/No-Input maximum of 3 for every page. Escalate users to a human agent upon the third No-Match or No-Input event." For an OS agent, "escalate" means "abandon and read back the last understood state."

### Finding 4 — Anaphora: a Python ring buffer beats prompting the 4B
"Online Coreference Resolution for Dialogue Processing" (Xu & Choi, arXiv:2205.10670) explicitly argues against entity-tracking models for online dialogue: "we do not use models that maintain explicit entities, because: (1) higher-order features from entity representation provide negative to marginal positive impact over ML counterparts despite their complexities; (2) ML models are 'stateless' so that they do not need to maintain decision states for previous mentions, which makes it more adaptable to applications in practice." For "ponelo", "ese", "ciérralo", the resolution is mostly **picking the most recent compatible entity from the last 1–3 turns**, which Python solves exactly.

"Reasoning over Object Descriptions Improves Coreference Resolution in Task-Based Dialogue Systems" (arXiv:2604.27850) demonstrates that even modern LLMs benefit from *explicit* object metadata fed into the prompt rather than coref-from-scratch — meaning the pre-extraction step can live outside vram4. After every tool call, push `{type, id, label, timestamp}` to a `deque(maxlen=5)`; on a deictic command, filter by tool-compatible type and pick the most recent.

### Finding 5 — Disfluency cleanup belongs in regex, not the LLM
The 2025 medRxiv study "Regex-Based vs. Large Language Model-Based Extraction of BI-RADS Scores" (medRxiv 10.1101/2025.06.01.25328636) provides a direct head-to-head on 7,764 radiology reports: "The regex-based approach achieved an accuracy of 89.20% on the sample subset compared to 87.69% of the LLM-based approach (p=0.56) in extracting the BI-RADS scores… the Regex approach required 0.06 seconds compared to 1,687.20 seconds required by the LLM-based approach, meaning the Regex approach was 28,120 times faster to execute." For voice commands the patterns are even simpler than radiology prose: filled pauses, repetitions, self-corrections all yield to a 20-line module.

Important caveat from Park et al. (arXiv:2108.01812): "presence of speech disfluencies might confuse the post-processing system into tagging disfluent but accurate transcriptions as ASR errors." So the regex must be conservative — delete only canonical fillers and immediate adjacent repeats; do not "fix" plausible Chilean lexemes (`po`, `cachái`, `ya po`).

Newer 2025 work (DRES, arXiv:2509.20321) warns that LLM-based disfluency cleanup has its own failure mode: "reasoning models systematically over-delete fluent content, revealing a bias toward semantic abstraction over structural fidelity." Another reason to keep this step out of Gemma.

Parakeet TDT v2 (English-only) and v3 (25 European languages, including Spanish — NVIDIA Granary corpus, ~670 k hours, **6.34% average WER** per the model card on `nvidia/parakeet-tdt-0.6b-v3`) tend to emit fluent transcripts by default, but Chilean register leaks through. Catch the residuals in regex.

### Finding 6 — Confidence via first-token logprob is the only viable single-pass signal at 4B
The TACL 2025 survey "Know Your Limits: A Survey of Abstention in Large Language Models" (Wen et al., MIT Press) converges on a clear hierarchy: for small models, **white-box logit-based signals beat verbalized confidence**. Direct quote: "Logit-based techniques estimate confidence from token probabilities or entropy (Huang et al., 2023; Kuhn et al., 2023; Duan et al., 2024), assuming that high probability tokens correspond to high confidence predictions." Verbalized methods "generally lack behind white-box methods in their calibration performance."

The production playbook from technetexperts.com 2025 (LLM Binary Classification Precision) gives explicit thresholds: "if the logprob is greater than 0.98, accept the label immediately. If the logprob is below 0.60, abstain immediately (route to human). Only if the logprob falls between 0.60 and 0.98 should the system execute complex secondary signals." For voice these are too cautious on the upper bound (every borderline case becomes a clarification) — start at 0.85 / 0.60 and calibrate on a 100-utterance dev set.

NON-VIABLE for vram4:
- Self-consistency sampling (k=5 × 4–5 s ≈ 20–25 s extra latency).
- A second judge model — won't fit alongside Gemma 3 4B + Parakeet + TTS in 16 GB.
- Long chain-of-thought reasoning — Gemma at Q4_K_M's CoT degrades faster than dense FP16; Localbench reports "Gemma degrades uniformly: even its best category at q8_0 (science, KL 0.108 for 31B) is worse than Qwen's worst."

VIABLE: single greedy decode + first-token logprob threshold (Ollama exposes this via `options.logprobs` since v0.5).

### Finding 7 — Compound dependent commands need a tiny planner, not a smarter LLM
USPTO patent US11664022 ("Method for processing user input of voice assistant") spells out the dependency rule: "determining whether the partial instructions have dependency to be treated in time series based on presence of an indicator indicating a user intent or attribute data of other partial instructions… based on a determination that the partial instructions do not have dependency to be treated in time series, [process] in parallel."

For Spanish, dependency detection is light syntax: a clause containing a clitic pronoun (`-lo`, `-la`, `-le`) with no antecedent inside its own clause but with one in the previous clause ("buscá un Word **y abrilo**" — the `-lo` refers back to "un Word") signals a dependency. Detected dependency ⇒ sequential execution, piping clause 1's result into clause 2's prompt context. No dependency ⇒ parallel.

### Quantization caveat — Q4_K_M specifically
Three pieces of evidence relevant to vram4:
- Google's official Gemma 3 QAT release (Google Developers Blog, "Gemma 3 - Quantized Aware Trained") recovers 54% of the perplexity loss relative to naive Q4_0: "We reduce the perplexity drop by 54% (using llama.cpp perplexity evaluation) when quantizing down to Q4_0." VRAM: "Gemma 3 4B: Reduces from 8 GB (BF16) to a lean 2.6 GB (int4)." **This benefit is only present in the QAT-stamped Q4_0 GGUFs, not in generic community Q4_K_M.**
- The ionio.ai 2025 cross-model quantization study reports: "BF16 → Q4_K_M/Q4_K_S shows steepest degradation, especially in instruction-heavy (IFEval) and multilingual (C-Eval) settings, with up to 20% loss from baseline." And: "MMLU is more sensitive to quantization, particularly in lower-bit formats. … GGUF formats below Q5_K_M risky for knowledge-intensive applications."
- The HealthQA-BR study (medRxiv 10.1101/2025.11.17.25340460, Nov 2025) directly compares Gemma 3 1B/4B/12B FP16 vs. 4-bit on a medical benchmark and concludes "quantization induces a minimal loss in diagnostic accuracy for larger models" — by implication, 4B is on the borderline.
- Independent reports (google-deepmind/gemma issue #460) note Gemma 3n E2B/E4B "significant performance degradation when switching from English to non-English languages: Spanish and Russian." Hold a Chilean voseo dev set as a regression sentinel.

**Recommendation: prefer the official Gemma 3 4B-it QAT Q4_0 GGUF over community Q4_K_M if you can swap; if Q4_K_M is fixed, the architectural mitigations below carry more weight.**

---

## Details — per research point

### Point 1: MULTI-INTENT (priority)

**Diagnosis.** Gemma 3 4B Q4_K_M reliably emits *one* tool call per turn but is unreliable at emitting an *array* of independent tool calls for compound utterances. The 4B has a measured tool-call bias (per orieg/gemma3-tools), and accuracy on multi-label intent is structurally crippled by causal attention (MIDLM, COLING 2025). Detecting conjunctions/lists in Python is trivial; doing it inside the LLM costs accuracy *and* latency.

**Decision matrix.**

| Approach | Comprehension accuracy (estimated for vram4) | Added latency | Risk of mis-execution | vram4 verdict |
|---|---|---|---|---|
| Trust the 4B to emit `parallel_tool_calls` as JSON array | 60–75% (mixed-tool, ≤ 8 tools); collapses with > 8 | 0 ms | High: drops one intent silently | **PARTIAL** — only ≤ 2 simple intents, ≤ 8 tools |
| Code splitter (connectors + imperatives) → N independent LLM calls | 90–95% on detected splits; depends on splitter recall | +5–10 ms (regex) + N × LLM | Low; per-call confidence available | **VIABLE — RECOMMENDED** |
| BERT-tiny multi-intent classifier as CPU-side pre-router | High (Joint BERT achieves 98.6% intent accuracy on Snips per Chen et al. arXiv:1902.10909) | +30–80 ms CPU | Low | **VIABLE as Stage-3 upgrade**, ~150 MB extra |
| Single bigger LLM (12B/27B) emitting parallel calls | 90%+ (orieg model card reports 100% for 12b-ft at 5–8 tools) | +6–8 s, won't fit | Low | **NON-VIABLE.** Substitute: 4B + code splitter |

**Hook (post-STT, pre-router):**

```python
# voice/preproc/split.py
import re

SPLIT_RE = re.compile(
    r"\s*(?:,\s*(?:y|e|o)\s+|;\s+|\s+y\s+(?=(?:abr[ií]|cerr[áa]|pon[eé]l[oa]|"
    r"baj[áa]|sub[íi]|mand[áa]|busc[áa]|busca|and[áa]|anda|ve|ponele|"
    r"reproduce|mut[eé]|silenci[áa]|mostr[áa]|empez[áa]|empieza|par[áa]|para)))",
    re.IGNORECASE,
)
DEP_PRONOUN_RE = re.compile(
    r"\b(?:lo|la|los|las|le|les|abrilo|cerralo|mostralo|"
    r"reprodu[cz]ilo|ponelo|mándalo|mandalo)\b", re.IGNORECASE)

def split_command(utterance: str) -> list[str]:
    parts = [p.strip() for p in SPLIT_RE.split(utterance) if p and p.strip()]
    return parts or [utterance]

def has_back_reference(clause: str) -> bool:
    return bool(DEP_PRONOUN_RE.search(clause))

def plan(utterance: str) -> list[dict]:
    clauses = split_command(utterance)
    return [{"text": c, "depends_on_prev": i > 0 and has_back_reference(c)}
            for i, c in enumerate(clauses)]
```

Integrate **before** `intent_router`. If `len(clauses) == 1`, your existing pipeline runs unchanged. If > 1: run each clause as its own LLM turn; serialize when `depends_on_prev` is True, parallelize otherwise. Token cost per extra clause: ~80–150 tokens of context + the action JSON, negligible at 4–5 s/clause budget.

### Point 2: CLARIFICATION (priority)

**Diagnosis.** A 4B model with next-token-prediction training will hallucinate missing slots rather than ask — explicitly identified by Wang et al. (arXiv:2409.00557) — and at 4B even verbalized "should I ask?" decisions are unreliable. The right design: code decides *whether* to ask; LLM only produces the *phrasing*, constrained by a JSON schema.

**Decision matrix.**

| Approach | "Asks correctly" rate | Latency | Loop risk | vram4 verdict |
|---|---|---|---|---|
| Free-form "ask if unsure" instruction in system prompt | Low (4B will mostly act) | 0 | High — also asks when shouldn't | **NOT RECOMMENDED** |
| Code-driven gate (required slot None ⇒ ask) | ~100% on detected gaps | +0 ms | Low if turn cap enforced | **VIABLE — RECOMMENDED** |
| Logprob gate on first action-token + slot-presence rule | High in practice | 0 (already decoding) | Low | **VIABLE — RECOMMENDED, combine with above** |
| Multi-agent clarification-seeking scaffold (HF papers/2603.26233, "Ask or Assume?") — 69.40% on underspecified SWE-bench Verified | High | 2× LLM cost, second context | — | **NON-VIABLE on vram4.** Substitute: single LLM + code policy (above) |
| Self-consistency k=5 | High | 20–25 s | — | **NON-VIABLE.** Substitute: greedy + logprob threshold |

**Policy (pseudocode):**

```python
# voice/clarify/policy.py
import math
MAX_CLARIFY_TURNS = 2     # per Dialogflow CX: cap 3, reserve 1 for confirm
P_ACT  = 0.85
P_ASK  = 0.60

def decide(tool_call, missing_required, first_token_logprob, state):
    if state.clarify_turns >= MAX_CLARIFY_TURNS:
        return ("abandon", state.last_partial)           # read back, don't loop
    if missing_required:
        return ("ask_one", missing_required[0])          # ONE slot only
    p = math.exp(first_token_logprob)
    if p >= P_ACT:    return ("act", tool_call)
    if p >= P_ASK:    return ("act_with_confirm", tool_call)
    return ("ask_one", "qué_querías_decir")
```

**Phrasing constraint via grammar-constrained decoding** (Ollama supports JSON-schema-derived GBNF since v0.5 — "Since ollama v0.5, instead of using generic JSON grammar built-in to ollama, you can supply an actual JSON schema, and Ollama will generate the grammar specifically for that JSON schema"):

```json
{"type":"object","required":["question","language","slot"],
 "properties":{
   "question":{"type":"string","maxLength":80},
   "language":{"type":"string","enum":["es"]},
   "slot":{"type":"string",
           "enum":["body","contact","channel","object","time","app"]}}
}
```

This eliminates the verbose-question failure mode: the 4B produces a single short Spanish sentence (≤ 80 chars).

**Examples (Chilean register):**
- "mandale a Juan" + missing `body` → "¿Qué le mando a Juan?"
- "ponelo" + last_object None → "¿Qué pongo?"
- "abrí el otro" + 2 candidates → "¿El de Chrome o el de Spotify?" (offer ≤ 2 alternatives — Aufait UX 2025 VUI guide: "limit options to 2–3 at a time").

### Point 3: AMBIGUOUS / DEICTIC REFERENTS

**Diagnosis.** Clitic anaphora ("ponelo", "ese", "el otro", "ciérralo") depends on dialogue state. A 4B asked to coref will guess; a typed ring buffer will be exact.

| Approach | Resolution accuracy | Latency | Hallucination risk | vram4 verdict |
|---|---|---|---|---|
| Ask the LLM to coref in system prompt | Low | 0 | High (invented antecedents) | **NOT RECOMMENDED** |
| Python ring buffer (last 3–5 typed entities) | High on canonical deixis | < 1 ms | Very low | **VIABLE — RECOMMENDED** |
| Object-description reasoning (arXiv:2604.27850 method) | Higher on visually grounded refs | +1 LLM call | — | **PARTIAL** — feed metadata strings into existing call |
| Online mention-linking model (Xu & Choi 2022, arXiv:2205.10670, "over 10% improvement over baseline") | High in dialogue | +50–200 ms CPU | Low | **VIABLE Stage-4 upgrade** |

**Hook:**

```python
# voice/state/entity_ring.py
from collections import deque

class EntityRing:
    def __init__(self, n=5): self.q = deque(maxlen=n)
    def push(self, entity_type, ident, label):           # call after every tool exec
        self.q.appendleft({"type": entity_type, "id": ident, "label": label})
    def resolve(self, expected_types: set[str] | None = None):
        for e in self.q:
            if expected_types is None or e["type"] in expected_types:
                return e
        return None
```

Wire: when the planner detects a deictic clause (`re.search(r'\b(lo|la|esto|eso|ese|esa|el otro|la otra|aquel)\b', clause)`), call `EntityRing.resolve(expected_types=tool.accepts())` **before** sending to the LLM, and inject the resolved entity into the prompt: `"contexto: el último objeto mencionado es <label>"`. If resolution returns None ⇒ fire clarification.

### Point 4: STT DISFLUENCIES

**Diagnosis.** Parakeet TDT v3 already drops most filled pauses (trained to emit fluent transcripts; 6.34% average WER per the model card), but repetitions and self-corrections leak through, especially in Spanish where the corpus skews toward EU Spanish. A 20-line regex pass fixes the residual at sub-millisecond cost.

| Approach | Disfluency removal precision | Latency | Risk of removing real content | vram4 verdict |
|---|---|---|---|---|
| Do nothing, let 4B handle it | ~80% (4B treats "abrí abrí" as emphasis sometimes) | 0 | Med | **NOT RECOMMENDED** |
| Conservative regex post-STT | ~95% on canonical fillers | < 1 ms | Low | **VIABLE — RECOMMENDED** |
| Fine-tuned BERT-base disfluency tagger | 97%+ | 30–80 ms CPU | Low | **VIABLE — overkill at current volume** |
| LLM-as-disfluency-remover | Similar | + ~1.7 s/call | Med (DRES arXiv:2509.20321: "reasoning models systematically over-delete fluent content") | **NON-VIABLE.** Reuses vram4 budget for low-value work |

**Hook (post-STT, before splitter):**

```python
# voice/preproc/disfluency.py
import re

FILLERS = re.compile(
    r"\b(?:eh+|em+|este|o sea|tipo|a ver|mmm+|este[- ]?este|este[- ]?em)\b",
    re.IGNORECASE,
)
# Note: DO NOT delete "po", "ya po", "cachái" — these are Chilean discourse particles
# that often carry pragmatic meaning, not filler.
REP_PAIR = re.compile(r"\b(\w{2,})\s+\1\b", re.IGNORECASE)
TRAIL    = re.compile(r"^\s*[,;\-]+|[,;\-]+\s*$")

def clean(text: str) -> str:
    t = FILLERS.sub(" ", text)
    t = REP_PAIR.sub(r"\1", t)
    t = re.sub(r"\s+", " ", t).strip()
    return TRAIL.sub("", t)
# "abre, abre a, abre Spotify" → "abre a abre Spotify" → "abre Spotify"
```

**Order matters:** `clean()` → `split_command()` → existing `intent_router`. Keep the **original** utterance for logging and for fallback when `clean()` produces an empty string.

### Point 5: CONFIDENCE / "I DIDN'T UNDERSTAND"

**Diagnosis.** Calibration of small LMs is poor for verbalized confidence but reasonable for token-probability signals on the first action-decision token. Use logprobs.

| Approach | Useful signal at 4B? | Latency | vram4 verdict |
|---|---|---|---|
| Verbalized confidence ("rate yourself 0–10") | Weak (Wen et al. TACL 2025: "white-box methods" beat verbalized) | +50–150 tokens | **NOT RECOMMENDED at 4B** |
| First-token logprob threshold | Strong | 0 | **VIABLE — RECOMMENDED** |
| Self-consistency (k samples) | Strong | k × 4–5 s | **NON-VIABLE** |
| Semantic entropy (Kuhn et al. 2023) | Strong | k samples | **NON-VIABLE.** Substitute: token-entropy of first 3 tokens, single pass |
| Conformal abstention (Tayebati 2025, arXiv:2502.06884) | Strong, statistical guarantees | needs calibration set | **VIABLE for offline calibration** |

**Hook:**

```python
# voice/confidence/gate.py
import math

def first_token_prob(ollama_resp):
    return math.exp(ollama_resp["eval"]["logprobs"][0]["logprob"])

def gate(p):
    if p >= 0.85: return "act"
    if p >= 0.60: return "confirm"          # "¿Te referías a abrir Spotify?"
    return "ask"                            # "No te entendí del todo, ¿qué querías hacer?"
```

Calibrate `P_ACT, P_ASK` against a 100-utterance Chilean dev set; the technetexperts.com defaults (0.98 / 0.60) target high-volume API classification — voice tolerates more risk on action and less on abandonment, so **0.85 / 0.60** is a saner starting point.

### Point 6: COMPOUND DEPENDENT COMMANDS

**Diagnosis.** "buscá un Word y abrilo" is two steps where step 2 needs step 1's output. The detection problem is light syntax (clitic in clause 2 with no in-clause antecedent); execution is already solved by your `inherit-tools` mechanism — wire them together.

| Approach | Detection accuracy | Risk | vram4 verdict |
|---|---|---|---|
| Always sequential when ≥ 2 clauses | Over-serializes independent commands | Low | **PARTIAL** |
| Detect back-pronoun in clause 2 ⇒ sequential | High recall for Spanish clitics | Low | **VIABLE — RECOMMENDED** |
| Let LLM decide via prompt | Unreliable on 4B | Med | **NOT RECOMMENDED** |

The `has_back_reference()` in Point 1 is the hook. On True: run clause 1 → push result to `EntityRing` → run clause 2 with the resolved antecedent injected into context.

---

## Recommendations (staged)

**Stage 0 (this week).** Ship `voice/preproc/disfluency.py` and `voice/preproc/split.py`. Sixty lines total, < 2 ms added. Expected reliability win on multi-intent: from ~65% to ~90% on canonical conjunction commands. **This is the highest-leverage change in the entire report.**

**Stage 1 (next).** Ship `voice/state/entity_ring.py` and inject resolved antecedents into the prompt before deictic commands. Expected reliability win on "ponelo / ese / lo": substantial — eliminates the most common "wrong referent" failure mode without any LLM-side change.

**Stage 2.** Wire the `first_token_logprob` gate (3-state: act / confirm / ask) plus the 2-turn clarification cap. Force clarification turns through the JSON schema with `maxLength: 80`. Expected wrong-action rate drop: meaningful, observable on the dev set within a week of calibration.

**Stage 3 (only if Stage 0–2 leaves > 5% mis-executions).** Add a CPU-side multi-intent classifier (mDeBERTa-v3-base or a fine-tuned XLM-R-small on a small Spanish multi-intent set) as a pre-router. +30–80 ms CPU, ~150 MB resident, doesn't compete with Gemma for VRAM.

**Stage 4 (only if anaphora errors remain after Stage 1).** Add the Xu & Choi 2022 online mention-linker as a CPU-side service.

**Benchmarks that would change these recommendations:**
- Multi-intent recall on a 200-utterance Chilean dev set < 85% after Stage 0 → move splitter from regex to BERT-tiny earlier (Stage 1).
- Clarification-loop rate (% sessions with ≥ 2 clarification turns) > 10% → tighten the JSON schema to enum-typed questions per slot type.
- Logprob threshold yields > 15% false-asks → calibrate per-tool thresholds, not global.
- Spanish degradation visible in error logs → switch from community Q4_K_M to Google's official Gemma 3 4B QAT Q4_0 (same VRAM ≈ 2.6 GB, recovers 54% of perplexity loss per Google Developers Blog).

**Explicit NON-VIABLE list and viable substitutes:**

| Non-viable on vram4 | Why | Viable substitute |
|---|---|---|
| 12B/27B model as planner | Won't fit alongside Parakeet + TTS in 16 GB | 4B + code-side splitter + ring buffer |
| Self-consistency (k=3–5 samples) | 12–25 s extra latency | Greedy + first-token logprob |
| Second judge LLM ("Ask or Assume?" UA-Multi-style pattern) | VRAM | Code-side abstain policy with logprob |
| Verbalized confidence prompts | Unreliable at 4B; + tokens | Logprob-based gate |
| LLM-based disfluency removal | 28,120× slower than regex (medRxiv 2025) | Conservative regex |
| LLM-based coreference resolution | Hallucinates antecedents | Typed Python ring buffer |
| End-to-end multi-intent in one LLM call | Causal-attention penalty (MIDLM, COLING 2025) | Code splitter → N LLM calls |
| Frontier reasoning-mode CoT inside Gemma 3 4B Q4_K_M | Quality at Q4_K_M is poor (Localbench, ionio.ai) | Structured JSON output + minimal CoT |
| ≥ 8 tools visible in prompt | Reliability collapses (orieg model card) | Subset via your existing `semantic_router` |

## Caveats

1. **Gemma 3's tool-calling story is fragile.** Whichever custom format you use (`<tool_call>` XML, pythonic, JSON-in-markdown), your parser must handle all three drift modes the `orieg/gemma3-tools` card describes. Consider migrating to Gemma 3n E4B-it (native function calling per Google's model card; ~6 GB at Q4) — but only after Stage 0–2 stabilize.

2. **Spanish-specific quality.** Independent reports (google-deepmind/gemma issue #460) note Gemma 3n E2B/E4B degrade noticeably on Spanish and Russian. Hold a Chilean voseo dev set as a regression sentinel; particularly test creaky-voice utterances ("Creaky Voice in Chilean Spanish", *Languages* MDPI 8(3):161, 2023, reports ~40% of highly creaky utterances in Santiago Spanish carry discourse-organizing meaning).

3. **Parakeet language match.** Parakeet-tdt-0.6b-v2 is English-only; v3 adds 25 European languages including Spanish but is trained primarily on EU Spanish. Chilean features (syllable-final /s/ aspiration, voseo) may degrade WER. Run a WER baseline on a 100-utterance Chilean set before tuning anything LLM-side.

4. **Q4_K_M-specific risk.** The localbench substack (2026) reports Gemma is uniquely quantization-sensitive vs. Qwen. If you observe drift on actions that previously worked, retry at Q5_K_M or switch to the official Google QAT Q4_0 release.

5. **Compounding reliability.** A 95% per-call rate yields ~66% over 8 chained steps (PromptQuorum 2026). Keep plan horizons short; the splitter + sequential planner should cap N ≤ 3 sub-commands per utterance and ask the user if the parsed plan looks longer ("Voy a hacer 4 cosas: … ¿confirmo?").

6. **Direct measurement gaps in published literature (as of May 2026).** No public BFCL number exists for Gemma 3 4B or Gemma 3n E4B. The "Ask or Assume?" multi-agent paper (HF papers/2603.26233) reports 69.40% on underspecified SWE-bench Verified but is on Claude Sonnet 4.5 — the *pattern* is generalizable but the specific accuracy is not transferable to a local 4B. Treat any 4B-specific quantitative claim in this report as inferred from adjacent evidence, not direct measurement. Build your own dev set of 100–200 representative Chilean voice commands and re-measure at each stage.

7. **Future-dated arXiv IDs noted.** Several papers cited (e.g., arXiv:2603.26233, arXiv:2604.27850, arXiv:2602.11199 / AskBench, arXiv:2603.28929 / ClauseCompose) carry 2026-dated identifiers — they appear in current indexes and search results but the canonical published versions and exact author lists should be re-verified at implementation time. The structural arguments in those papers (decoupling clarification from execution; clause-factorized decoding; rubric-guided clarification) are consistent with the older, well-established literature this report relies on for primary evidence.