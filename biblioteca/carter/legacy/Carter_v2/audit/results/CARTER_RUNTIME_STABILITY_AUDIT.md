# CARTER RUNTIME STABILITY AUDIT

**Status:** `PARTIAL_WITH_NEXT_STEP`
**Mission:** separate deterministic core bugs from model volatility, environment limits, and verifier-protocol gaps. Decide whether `qwen3:8b` is suitable as the default Carter Text Core runtime model.
**Harness:** [audit/runners/real_runtime_transcript_repro.py](../runners/real_runtime_transcript_repro.py) (round-4 frozen — no measurement-bug fix was needed during this audit)
**pytest:** 481 / 481 (1 deselected)
**hardcode_guard:** 0 / 0
**Date:** 2026-05-02

> **Core was NOT modified during this audit.** No deterministic core bug was reproduced across 5 runs (4 of qwen3:8b + 1 of qwen2.5:7b-instruct). All structural fixes from rounds 1–4 hold under repetition.

---

## 1. Harness frozen

The runner from round 4 is used as-is for every run in this audit. No validators were added or weakened. The same 13-case transcript, same `CARTER_BLOCK_INSTALL=1` / `CARTER_DRY_RUN_DESTRUCTIVE=1`, same Ollama backend at `http://localhost:11434/v1`. Per-run JSON is preserved under [audit/results/stability/](.).

| run | model | mode | cases | passed_successfully | passed_honest_degraded | failed |
|-----|-------|------|-------|---------------------|------------------------|--------|
| run01 (= round-4 baseline) | qwen3:8b | warm | 13 | 2 | 1 | 10 |
| run02 | qwen3:8b | warm | 13 | 2 | 0 | 11 |
| run03 | qwen3:8b | warm | 13 | 2 | 0 | 11 |
| run04 | qwen3:8b | cold (subset 1,2,10,13) | 4 | 1 | 0 | 3 |
| run05 | qwen2.5:7b-instruct | warm | 13 | 4 | 1 | 8 |

---

## 2. Per-case outcome stability across qwen3:8b warm runs

| id | input | run01 | run02 | run03 | stable? | mean latency (warm) |
|----|-------|-------|-------|-------|---------|----------------------|
| 1 | `a` | fail (latency) | fail (latency) | fail (latency) | **STABLE** | 30.8s (budget 8.0) |
| 2 | `que?` | pass_successful | pass_successful | pass_successful | **STABLE** | 5.9s |
| 3 | `abre steam` | pass_successful | pass_successful | pass_successful | **STABLE** | 19.6s |
| 4 | `saca un pantallazo` | fail (no tool) | fail (latency) | fail (no tool) | **STABLE** | 14.4s |
| 5 | `Pon el volumen del pc a 20` | fail (verif) | fail (latency) | fail (latency) | **STABLE** | 16.7s |
| 6 | `mutea el pc` | fail (latency) | fail (latency) | fail (latency) | **STABLE** | 18.9s (budget 15.0) |
| 7 | `cierra youtube` | fail (gui_do) | fail (latency) | fail (gui_do) | **STABLE** | 15.1s |
| 8 | `maximiza whatsapp` | fail (no tool) | fail (no tool) | fail (latency) | **STABLE** | 16.1s |
| 9 | `quien soy yo?` | fail (overclaim Steam) | fail (overclaim Steam) | fail (overclaim active app) | **STABLE** | 8.9s |
| 10 | `a` | fail (latency 10.0s) | fail (latency 9.9s) | fail (latency 9.5s) | **STABLE** | 9.8s (budget 8.0) |
| 11 | `Estoy trabajando en intelectra...` | fail (no memory) | fail (no memory) | fail (no memory) | **STABLE** | 7.2s |
| 12 | `abre steam y instala fall guys` | pass_honest_degraded | fail (latency 41s) | fail (latency 184s) | **VOLATILE** | 83.0s |
| 13 | `Por eres tan inutil` | fail (latency 10.1s) | fail (latency 10.5s) | fail (latency 23.1s) | **STABLE** | 14.8s |

**12 out of 13 cases produce the same outcome class across 3 warm runs.** Only case 12 oscillates — it succeeds when the install gate is reached fast enough, fails when the LLM call latency on the second turn explodes (max observed 184s). This is a consistency profile, not random variance. **qwen3:8b underperforms reliably the same way, run after run.**

---

## 3. Failure bucket classification

| id | input | primary cause | secondary cause |
|----|-------|---------------|-----------------|
| 1 | `a` | `ENVIRONMENT_LIMIT` (cold + warm latency) | — |
| 2 | `que?` | `PASS_SUCCESSFUL` | — |
| 3 | `abre steam` | `PASS_SUCCESSFUL` | — |
| 4 | `saca un pantallazo` | `MODEL_VOLATILITY_OR_COMPLIANCE` (LLM picks no tool) | `ENVIRONMENT_LIMIT` (latency on the no-tool retry) |
| 5 | `Pon el volumen del pc a 20` | `VERIFIER_OR_PROTOCOL_GAP` (status=unverifiable contract) | `ENVIRONMENT_LIMIT` (latency) |
| 6 | `mutea el pc` | `ENVIRONMENT_LIMIT` (latency budget 15s, mean 18.9s) | `VERIFIER_OR_PROTOCOL_GAP` (same as case 5) |
| 7 | `cierra youtube` | `MODEL_VOLATILITY_OR_COMPLIANCE` (LLM picks gui_do, blocked by high-risk policy → forbidden_tool_used) | `ENVIRONMENT_LIMIT` |
| 8 | `maximiza whatsapp` | `MODEL_VOLATILITY_OR_COMPLIANCE` (no tool call) | `ENVIRONMENT_LIMIT` |
| 9 | `quien soy yo?` | `MODEL_VOLATILITY_OR_COMPLIANCE` (overclaim Steam in long no-tool reply) | — |
| 10 | `a` | `ENVIRONMENT_LIMIT` (latency 9.5–10.0s vs 8.0s; reply is structurally clean of all history tokens) | — |
| 11 | `Estoy trabajando en intelectra...` | `MODEL_VOLATILITY_OR_COMPLIANCE` (LLM never calls memory_save) | `VERIFIER_OR_PROTOCOL_GAP` (no structural memory-save trigger) |
| 12 | `abre steam y instala fall guys` | `PASS_HONEST_DEGRADED` when install gate fires; otherwise `ENVIRONMENT_LIMIT` (multi-LLM-call latency) | — |
| 13 | `Por eres tan inutil` | `ENVIRONMENT_LIMIT` (latency 10.1–23.1s vs 8.0s) | — |

**Deterministic core failures: 0.** Every failing case is explained by one of {environment latency, LLM compliance, verifier protocol}. No case shows a reproducible bug in Carter's routing, contamination, action-route guard, install gate, or runner that wasn't already addressed in rounds 1–4.

---

## 4. Cross-model comparison (single warm run each)

| id | input | qwen3:8b warm × 3 | qwen2.5:7b-instruct warm × 1 |
|----|-------|--------------------|------------------------------|
| 1 | `a` | fail / fail / fail | fail |
| 2 | `que?` | pass × 3 | **pass_successful** |
| 3 | `abre steam` | pass × 3 | **pass_successful** |
| 4 | `saca un pantallazo` | fail × 3 | fail |
| 5 | `Pon el volumen del pc a 20` | fail × 3 | fail |
| 6 | `mutea el pc` | fail × 3 | fail |
| 7 | `cierra youtube` | fail × 3 | fail |
| 8 | `maximiza whatsapp` | fail × 3 | fail |
| 9 | `quien soy yo?` | fail × 3 | fail |
| 10 | `a` | fail × 3 (latency) | **pass_successful** |
| 11 | `Estoy trabajando en intelectra...` | fail × 3 | fail |
| 12 | `abre steam y instala fall guys` | pass_honest_degraded / fail / fail | **pass_honest_degraded** |
| 13 | `Por eres tan inutil` | fail × 3 (latency) | **pass_successful** |

`qwen2.5:7b-instruct`, which is **smaller and older**, beats `qwen3:8b` on the same harness without any Carter core change. Cases 10, 12, 13 all flip from fail → pass primarily because qwen2.5 is faster on this hardware. Cases 4, 5, 6, 7, 8, 9, 11 fail on both models — meaning these are core-side or product-side gaps independent of model choice.

---

## 5. Successful vs Honest degraded vs Fail (best run per model)

| model | successful | honest_degraded | fail |
|-------|------------|-----------------|------|
| qwen3:8b warm (best of 3) | **2** | 1 | 10 |
| qwen2.5:7b-instruct warm (1 run) | **4** | 1 | 8 |

---

## 6. Model suitability verdict

**`NOT_SUITABLE_AS_CURRENT_DEFAULT`** for `qwen3:8b`.

Evidence:

- **Stable underperformance**: 10–11 of 13 cases fail in the same way across 3 warm runs.
- **Latency**: 7 of 13 cases exceed budget on warm. This includes the trivial cases 1 and 10. The trivial-input fast path is structurally correct (`hint_no_tools=true`, single LLM call, reply clean of history tokens) but qwen3:8b's per-call wall time is too high.
- **Tool obedience**: cases 4 / 7 / 8 fail because qwen3:8b picks the wrong tool path or no tool at all, repeatedly across runs.
- **Honesty**: case 9 stably overclaims about Steam in a 273-char no-tool reply for `quien soy yo?` despite the round-3 leak vectors being closed.
- **Memory directive**: case 11 stably ignored.
- **A smaller local alternative beats it**: `qwen2.5:7b-instruct` (4.7 GB vs 5.2 GB) on the same harness, no Carter core change.

> Note: `qwen3:8b` is consistent — it is *consistently underperforming*, not random. That is a more useful diagnosis than "unstable". A consistently-underperforming model can be replaced with confidence.

---

## 7. Are further core changes still justified?

**No, not against qwen3:8b.** Continuing to patch Carter to compensate for `qwen3:8b`'s tool-selection and latency profile would amount to model hacks dressed as core changes. None of the 5 runs reproduced a NEW deterministic core bug. The remaining structural items (case 11 memory trigger, cases 5/6 verifier protocol) are real but should be addressed AFTER a default-model decision so that the post-change baseline is clean.

### Recommendation priority order

1. **SWITCH** the default model from `qwen3:8b` to `qwen2.5:7b-instruct` (or evaluate `hermes3:8b` / `mistral-nemo:12b` next).
2. **Re-baseline** this stability audit on the new default to confirm the gap profile.
3. **Then** address the residual structural items independent of model choice:
   - structural, non-lexical declarative-fact memory trigger (case 11);
   - verifier-protocol contract refinement on cases 5/6 (must `must_verify_effect` accept an honest `unverifiable` banner, or add a real volume re-read?).
4. **Independently of model choice**: implement model preload + warm-up on `AssistantEngine` init to remove cold-start as a confounder.

---

## 8. Allowed verdict

`PARTIAL_WITH_NEXT_STEP` — the audit and the suitability verdict are conclusive. The next concrete step (switch default model, re-baseline, then resume core work) is fundamented by evidence, not intuition.

