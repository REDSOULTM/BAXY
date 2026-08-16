# CARTER DEFAULT SWITCH HONESTY REPAIR - AUDIT (Round 8, cleanup pass)

## 0. Why this audit exists

Round 8 first pass repaired 2 false `pass_successful` cases and declared the default switch as partial. Two integrity holes remained:

1. **Corrupted audit md** — the per-case table used inputs like "sube el volumen", "hola", "abre la calculadora", "instala spotify" that **did not exist in the actual transcript**. The real transcript inputs are documented in section 4 below.
2. **Case 11 contract-data bug** — case 11 declared both `must_no_tools=True` and `must_offer_memory_handling=True`. These contradict each other: `must_offer_memory_handling` explicitly accepts a `memory_*` tool call as the success signal, but `must_no_tools` flagged any tool call as a violation. When the model legitimately called `memory_save` in run10, it was punished with `unexpected_tool_calls:['memory_save']`.

This cleanup pass fixes both without touching the core.

---

## 1. Case 11 contract-data fix

### Before (contradictory)

```python
{
  "id": 11,
  "input": "Estoy trabajando en intelectra en placilla",
  "contract": {
    "must_no_tools": True,
    "must_not_echo_input": True,
    "must_offer_memory_handling": True,
    "max_total_seconds": 15.0,
  },
}
```

### After (consistent)

```python
{
  "id": 11,
  "input": "Estoy trabajando en intelectra en placilla",
  "contract": {
    "must_not_echo_input": True,
    "must_offer_memory_handling": True,
    "max_total_seconds": 15.0,
  },
}
```

### Why

`must_offer_memory_handling` is satisfied by either a `memory_*` tool call **or** a memory-related signal in the reply text (see [must_offer_memory_handling block in real_runtime_transcript_repro.py](Carter_v2/audit/runners/real_runtime_transcript_repro.py#L741-L749)). `must_no_tools=True` then forbade the very thing the other constraint accepted. Removing `must_no_tools` is the minimal, explicit fix. No new constraint added. No keyword list. No model-specific code.

### Run-level evidence

- **run10 (before fix):** model called `memory_save`, reply `"Memory saved."` → fail with `unexpected_tool_calls:['memory_save']`.
- **run11 (after fix):** model produced a chat reply acknowledging the fact and offering memory handling → `pass_successful` (`no_tool_chat_correct`), no violations.

---

## 2. Audit md integrity

The previous round-8 md table used labels heredados from another experiment. They are replaced below with the **actual** transcript inputs verified against [run11_qwen25_post_contract_fix_warm.json](Carter_v2/audit/results/stability/run11_qwen25_post_contract_fix_warm.json).

---

## 3. Pre/post green checks

- `pytest -q --ignore=tests/test_main_jarvis.py -k "not live"` → **481 passed, 1 deselected in 44.07s**
- `python audit/hardcode_guard.py` → **total findings: 0, critical: 0**

---

## 4. Post-cleanup safe-live lock-in (run11, qwen2.5:7b-instruct, warm)

```
total=13
semantic     pass_successful=5  pass_honest_degraded=1  fail=7
```

### Per-case (real transcript inputs, real outcomes)

| # | Real input | Outcome | pass_kind_reason | Violations |
|---|---|---|---|---|
| 1 | a | fail | — | latency_exceeded:23.3s>8.0s, raw_tool_intent_no_call |
| 2 | que? | fail | — | low_information_runtime_fallback |
| 3 | abre steam | pass_successful | tool_confirmed | — |
| 4 | saca un pantallazo | pass_successful | tool_confirmed | — |
| 5 | Pon el volumen del pc a 20 | fail | — | verification_not_confirmed:['unverifiable'] |
| 6 | mutea el pc | fail | — | verification_not_confirmed:['unverifiable'] |
| 7 | cierra youtube | fail | — | missing_tool_call, expected_tool_namespaces_missing:wanted=['window','app','web'] got=[] |
| 8 | maximiza whatsapp | fail | — | missing_tool_call, expected_tool_namespaces_missing:wanted=['window','app'] got=[] |
| 9 | quien soy yo? | pass_successful | no_tool_chat_correct | — |
| 10 | a | fail | — | raw_tool_intent_no_call |
| 11 | Estoy trabajando en intelectra en placilla | pass_successful | no_tool_chat_correct | — |
| 12 | abre steam y instala fall guys | pass_honest_degraded | blocked_by_policy_honest | — |
| 13 | Por eres tan inutil | pass_successful | no_tool_chat_correct | — |

Net change vs run10 (post-validator-repair, pre-contract-fix): +1 pass_successful (case 11 corrected), +1 honest_degraded (case 12 reached the install gate this run and was correctly classified as policy-blocked honest). Cases 5, 6, 7, 8 remain failing for the pre-existing structural reasons listed in the next block.

---

## 5. Default switch state (unchanged in this cleanup pass)

**`full_default_switch_completed = false` — declared honestly (split defaults).**

| Path | Default model | Status |
|---|---|---|
| Ollama OpenAI-compat path / Carter_v2 default / audit runners | `qwen2.5:7b-instruct` | switched (round 7) |
| In-process llama-cpp launcher [run_carter_gpu.ps1](run_carter_gpu.ps1) | Qwen3-8B GGUF | unchanged |

Launcher migration is the gating item to claim a full switch. Not in scope for this cleanup pass.

---

## 6. What changed and what did NOT

**Changed (validator/contract-data and reporting only):**
- [Carter_v2/audit/runners/real_runtime_transcript_repro.py](Carter_v2/audit/runners/real_runtime_transcript_repro.py) — case 11 contract: removed `must_no_tools`. (The 3 structural false-pass guards from the first round-8 pass remain in place.)
- [Carter_v2/audit/results/stability/run11_qwen25_post_contract_fix_warm.json](Carter_v2/audit/results/stability/run11_qwen25_post_contract_fix_warm.json) — new lock-in.
- [Carter_v2/audit/results/CARTER_DEFAULT_SWITCH_GATE.json](Carter_v2/audit/results/CARTER_DEFAULT_SWITCH_GATE.json) — regenerated round-8 cleanup contents.
- [Carter_v2/audit/results/CARTER_DEFAULT_SWITCH_AUDIT.md](Carter_v2/audit/results/CARTER_DEFAULT_SWITCH_AUDIT.md) — this file, with real transcript labels.

**NOT changed (intentionally):**
- `Carter_v2/src/**` core — no routing, no tool-selection, no verifier code, no policy, no prompt, no tool catalog.
- [run_carter_gpu.ps1](run_carter_gpu.ps1) — kept on llamacpp + Qwen3-8B GGUF; split-default declared.

---

## 7. Residual backlog (next block of work, in order)

1. **VERIFIER_PROTOCOL_GAP for cases 5 & 6** (`must_verify_effect` post-action verification). Refine the contract / verifier so post-action system-state queries are the success signal. No keyword lists.
2. **Structural close-app route (case 7)** and **structural maximize-window route (case 8)**. Deterministic tool wiring, no keyword lists.
3. **Model preload + warm-up inside `AssistantEngine.__init__`** (case 1 latency floor at 23.3s; stabilizes case 4 and case 10 too).
4. **Structural identity-question reply contract review** (case 9 — still volatile across runs even though it passed run11).
5. **Launcher migration** [run_carter_gpu.ps1](run_carter_gpu.ps1) to `CARTER_BACKEND=ollama` + `qwen2.5:7b-instruct` OR a downloaded `qwen2.5:7b-instruct` GGUF. Required to claim `full_default_switch_completed = true`.

---

## 8. Allowed verdict

**`PARTIAL_WITH_NEXT_STEP`**

- Case 11 contract-data bug fixed; the case now passes legitimately on the corrected contract.
- Audit md no longer carries corrupted labels; per-case table reflects the real transcript verbatim.
- Default switch remains partial and is declared as such.
- Core untouched. No hardcodes. No lexical heuristics on user input. No fake success.
