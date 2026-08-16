# CARTER MODEL REBASELINE AUDIT

**Status:** `PARTIAL_WITH_NEXT_STEP`
**Mission:** rebaseline Carter Text Core on `qwen2.5:7b-instruct`, score it under both **semantic** and **Jarvis-grade budget** taxonomies, and isolate the residual core/product backlog from model-specific failures.
**Harness:** [audit/runners/real_runtime_transcript_repro.py](../runners/real_runtime_transcript_repro.py) — **frozen** (round-4 state; not modified during this audit).
**pytest:** 481 / 481 (1 deselected) · **hardcode_guard:** 0 / 0
**Old default model:** `qwen3:8b` (rejected in round 5 as `NOT_SUITABLE_AS_CURRENT_DEFAULT`)
**Candidate default:** `qwen2.5:7b-instruct`
**Date:** 2026-05-02

> **No core, runner, validator, system prompt, tool catalogue, or routing code was changed during this audit.** All deltas are model-only.

---

## 1. Harness frozen — runs executed

| run | model | mode | cases | semantic S/H/F | budget-Jarvis S/H/F |
|-----|-------|------|-------|----------------|---------------------|
| run01 (= round-4 baseline) | qwen3:8b | warm | 13 | 2 / 1 / 10 | 0 / 0 / 13 |
| run02 | qwen3:8b | warm | 13 | 2 / 0 / 11 | 0 / 0 / 13 |
| run03 | qwen3:8b | warm | 13 | 2 / 0 / 11 | 0 / 0 / 13 |
| run04 | qwen3:8b | cold (subset 1,2,10,13) | 4 | 1 / 0 / 3 | 0 / 0 / 4 |
| run05 | qwen2.5:7b-instruct | warm | 13 | 4 / 1 / 8 | 3 / 1 / 9 |
| run06 | qwen2.5:7b-instruct | warm | 13 | 5 / 0 / 8 | 3 / 0 / 10 |
| run07 | qwen2.5:7b-instruct | warm | 13 | **6 / 1 / 6** | **4 / 1 / 8** |
| run08 | qwen2.5:7b-instruct | cold (subset 1,2,10,13) | 4 | 3 / 0 / 1 | 3 / 0 / 1 |

Per-run JSONs preserved under [audit/results/stability/](.).

---

## 2. Jarvis-grade budgets (per case)

Independent of the runner's contract `max_total_seconds` field. These are the strict "ágil / humano / Jarvis" bounds requested by the mission:

| case | input | budget |
|------|-------|--------|
| 1 | `a` | 5 s (chat / no-op) |
| 2 | `que?` | 5 s (chat) |
| 3 | `abre steam` | 8 s (single tool) |
| 4 | `saca un pantallazo` | 8 s (single vision/tool) |
| 5 | `Pon el volumen del pc a 20` | 8 s (single tool) |
| 6 | `mutea el pc` | 8 s (single tool) |
| 7 | `cierra youtube` | 8 s (single GUI/tool) |
| 8 | `maximiza whatsapp` | 8 s (single GUI/tool) |
| 9 | `quien soy yo?` | 5 s (chat) |
| 10 | `a` | 5 s (chat / no-op) |
| 11 | `Estoy trabajando en intelectra ...` | 5 s (chat + memory_save) |
| 12 | `abre steam y instala fall guys` | 16 s (2 actions × 8 s) |
| 13 | `Por eres tan inutil` | 5 s (chat) |

Budget-Jarvis scoring: a case counts as `budget_compliant_*` only if its semantic outcome is non-fail **and** observed total latency ≤ budget.

---

## 3. qwen2.5:7b-instruct repeatability matrix (3 warm runs)

| id | input | budget | run05 sem (lat) | run06 sem (lat) | run07 sem (lat) | stability | best |
|----|-------|--------|-----------------|-----------------|-----------------|-----------|------|
| 1 | `a` | 5.0 | fail (22.7s) | fail (24.2s) | fail (16.8s) | STABLE | fail |
| 2 | `que?` | 5.0 | pass (4.5s) | pass (4.5s) | pass (4.4s) | STABLE | budget-pass |
| 3 | `abre steam` | 8.0 | pass (9.6s) | pass (10.0s) | pass (7.5s) | STABLE | budget-pass (run07 only) |
| 4 | `saca un pantallazo` | 8.0 | fail (4.4s) | fail (4.3s) | pass (10.0s) | VOLATILE | over-budget pass |
| 5 | `Pon el volumen del pc a 20` | 8.0 | fail (8.9s) | fail (9.3s) | fail (9.6s) | STABLE | fail |
| 6 | `mutea el pc` | 8.0 | fail (5.3s) | fail (5.4s) | fail (4.0s) | STABLE | fail |
| 7 | `cierra youtube` | 8.0 | fail (6.7s) | fail (6.6s) | fail (5.1s) | STABLE | fail |
| 8 | `maximiza whatsapp` | 8.0 | fail (5.7s) | fail (4.2s) | fail (5.3s) | STABLE | fail |
| 9 | `quien soy yo?` | 5.0 | fail (4.7s) | fail (4.8s) | fail (5.4s) | STABLE | fail |
| 10 | `a` | 5.0 | pass (3.3s) | pass (3.3s) | pass (3.3s) | STABLE | budget-pass |
| 11 | `Estoy trabajando en intelectra ...` | 5.0 | fail (3.4s) | fail (4.4s) | pass (5.5s) | VOLATILE | over-budget pass |
| 12 | `abre steam y instala fall guys` | 16.0 | honest (3.8s) | pass (8.5s) | honest (3.8s) | VOLATILE | budget-pass + budget-honest |
| 13 | `Por eres tan inutil` | 5.0 | pass (4.0s) | pass (5.0s) | pass (3.9s) | STABLE | budget-pass |

10 / 13 cases STABLE across 3 warm runs. The 3 volatile cases (4, 11, 12) all favour pass on at least one run, so worst-case is never below qwen3:8b on any case.

---

## 4. Semantic score vs Jarvis-budget score (best run)

| metric | qwen3:8b best warm | qwen2.5:7b-instruct best warm (run07) |
|--------|---------------------|----------------------------------------|
| **Semantic pass_successful** | 2 | **6** |
| **Semantic pass_honest_degraded** | 1 | 1 |
| **Semantic fail** | 10 | 6 |
| **Budget-Jarvis successful** | **0** | **4** |
| **Budget-Jarvis honest_degraded** | 0 | 1 |
| **Budget-Jarvis fail** | 13 | 8 |

Cold subset (4 cases, 1, 2, 10, 13):
- qwen3:8b cold: 1 / 0 / 3 semantic, 0 / 0 / 4 budget
- qwen2.5:7b-instruct cold: **3 / 0 / 1** semantic, **3 / 0 / 1** budget

Insight: the budget-Jarvis collapse on qwen3:8b is total (zero compliant cases on any run). qwen2.5 lifts the budget-compliant floor from 0 to 4 successful + 1 honest_degraded — but **only 5 of 13 cases reach Jarvis-grade**: 2, 3, 10, 12, 13. The remaining 8 are semantic-fail, latency-fail, or both.

---

## 5. Cross-model residual table (the central question)

| id | input | qwen3:8b warm | qwen2.5:7b warm | same-family failing in BOTH? | primary interpretation |
|----|-------|---------------|------------------|------------------------------|------------------------|
| 1 | `a` | fail × 3 (latency) | fail × 3 (latency 16–24s) | **YES** | `ENVIRONMENT_LIMIT` (per-LLM-call cost on this hardware; trivial path is structurally correct) |
| 2 | `que?` | pass × 3 | pass × 3 | no | resolved both |
| 3 | `abre steam` | pass × 3 | pass × 3 | no | resolved both |
| 4 | `saca un pantallazo` | fail × 3 | 1/3 pass | no (model_specific to qwen3) | `MODEL_SPECIFIC` (qwen2.5 picks the right tool sometimes) |
| 5 | `Pon el volumen del pc a 20` | fail × 3 | fail × 3 | **YES** | `VERIFIER_PROTOCOL_GAP` (volume verifier contract — model-independent) |
| 6 | `mutea el pc` | fail × 3 | fail × 3 | **YES** | `VERIFIER_PROTOCOL_GAP` (mute verifier contract — model-independent) |
| 7 | `cierra youtube` | fail × 3 (forbidden_tool / no-op) | fail × 3 | **YES** | `CORE_OR_PRODUCT_BACKLOG` (no structural close-app route; both models fall back to gui_do or no-tool) |
| 8 | `maximiza whatsapp` | fail × 3 (no tool) | fail × 3 | **YES** | `CORE_OR_PRODUCT_BACKLOG` (window-maximize tool missing or unselectable) |
| 9 | `quien soy yo?` | fail × 3 (overclaim) | fail × 3 (overclaim) | **YES** | `CORE_OR_PRODUCT_BACKLOG` (identity-question protocol contract; both models invent context) |
| 10 | `a` | fail × 3 (latency 9.5–10s) | pass × 3 (latency 3.3s) | no | `MODEL_SPECIFIC` (qwen2.5 fast enough) |
| 11 | `Estoy trabajando en intelectra ...` | fail × 3 (no memory_save) | 1/3 pass | partial | `VERIFIER_PROTOCOL_GAP` (no structural memory_save trigger; LLM-compliance dependent on both) |
| 12 | `abre steam y instala fall guys` | 1/3 honest, 2/3 fail (latency) | 1/3 pass + 2/3 honest | no | `MODEL_SPECIFIC` (qwen2.5 reaches the install gate reliably) |
| 13 | `Por eres tan inutil` | fail × 3 (latency 10–23s) | pass × 3 (latency ~4s) | no | `MODEL_SPECIFIC` (qwen2.5 fast enough) |

**Six cases (1, 5, 6, 7, 8, 9) fail in BOTH models in the same way.** These are NOT solved by switching models. They are the real residual backlog.

Five cases (4, 10, 11, 12, 13) flip from fail to pass (fully or partially) under qwen2.5 — these were genuinely model-specific to qwen3:8b.

---

## 6. Candidate default verdict

**`ADOPT_AS_NEW_DEFAULT_WITH_RESIDUAL_BACKLOG`** for `qwen2.5:7b-instruct`.

Justification (evidence-based, not intuition):

1. **Strict semantic dominance** on the same frozen harness: best 6/1/6 vs 2/1/10. Worst 4/1/8 vs 2/0/11. No qwen3:8b warm run beats any qwen2.5 warm run on any metric.
2. **Strict budget-Jarvis dominance**: 4/1/8 vs 0/0/13 on best warm runs. qwen3:8b never reached a single budget-compliant case in three runs.
3. **Cold path also better**: subset 3/0/1 vs 1/0/3.
4. **Stability**: 10/13 cases stable; the 3 volatile cases never regress below qwen3:8b worst-case on any run.
5. **No core change required** to obtain this lift.
6. **Honest disclaimer**: 5 of 13 cases are Jarvis-grade today; 6 are not (they fail in both models). qwen2.5 is the right new floor, **not** a finished product.

---

## 7. Are further core changes still justified?

**Not during this audit.** The residual backlog (6 model-independent failures + 1 latency case + 1 still-volatile case) is real and needs work, but the order is:

1. switch the default model;
2. re-baseline against the new floor;
3. then attack the residual list.

Touching the core now would mix model-floor changes with structural changes and corrupt the next baseline.

### Residual backlog (model-independent, ranked)

| priority | id | item | category |
|----------|----|------|----------|
| P1 | 5 | Volume verifier protocol contract (`must_verify_effect` accepts honest `unverifiable` banner OR adds real post-action read) | VERIFIER_PROTOCOL_GAP |
| P1 | 6 | Mute verifier protocol contract (same as case 5) | VERIFIER_PROTOCOL_GAP |
| P2 | 7 | Close-app routing (non-lexical, structural close-window route — both models pick gui_do or no-op) | CORE_OR_PRODUCT_BACKLOG |
| P2 | 8 | Maximize-window tool route (no selectable tool today) | CORE_OR_PRODUCT_BACKLOG |
| P3 | 9 | Identity-question protocol (structural reply contract; both models overclaim about Steam/active app) | CORE_OR_PRODUCT_BACKLOG |
| P4 | 1 | Per-LLM-call latency budget on trivial cases (preload/warm-up; consider smaller fast-path model) | ENVIRONMENT_LIMIT |
| P5 | 11 | Structural declarative-fact `memory_save` trigger (non-lexical) | VERIFIER_PROTOCOL_GAP |

### Independent of the above

- Implement model preload + warm-up inside `AssistantEngine.__init__` to remove cold-start as a confounder in future audits.

---

## 8. Allowed verdict

`PARTIAL_WITH_NEXT_STEP`.

### Concrete next-step order

1. **ADOPT** `qwen2.5:7b-instruct` as the new Carter Text Core default. Update `CARTER_LLM_MODEL` defaults in run scripts and documentation. **No** core/runner code change in this step.
2. **RE-BASELINE**: re-run this same audit (3 warm + 1 cold) immediately after the switch lands, to lock the new floor.
3. **ATTACK** the residual backlog in P1 → P5 order.
4. **INDEPENDENTLY**: add model preload + warm-up to remove cold-start confounder.

No `READY`. No `RC`. No `MISSION COMPLETE`. The Carter Text Core is structurally sound at the round-4 baseline; switching the default model lifts the floor from 0 to 4 budget-compliant Jarvis-grade cases without touching one line of core.

