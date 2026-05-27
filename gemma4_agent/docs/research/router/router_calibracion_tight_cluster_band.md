# TIGHT_CLUSTER Band — Calibration Recommendation

**Bottom line:** Add a new `TIGHT_CLUSTER` band that fires when `dense_top1 != bm25_top1 AND top_score >= 0.025 AND rrf[4]/rrf[0] >= 0.80`, cap = **8**. This is the obvious solution; the 5 probes pin it cleanly and no fancier mechanism is justified.

## TL;DR
- **Metric:** disagreement gate + corroboration floor (`top_score ≥ 0.025`) + tight-cluster ratio (`rrf[4]/rrf[0] ≥ 0.80`); cap = 8; name = `TIGHT_CLUSTER`.
- **Soft-cap-by-score-floor: REJECT** for this sprint — operator predictability is weaker and no probe currently requires cap ∈ {5,7}; revisit only if a future probe surfaces.
- **One small commit**, ~6 lines added in `RouterV2.route()`; HIGH/MEDIUM/LOW, RRF k=60, YAML, smalltalk, cache, popular fallback all untouched (10/10 hard constraints satisfied).

## Key Findings

The two structural signals already in the router separate the 5 probes cleanly:

| Query | top_score | rrf[4]/rrf[0] | Band | Cap |
|---|---|---|---|---|
| `cierra steam` | 0.0320 | 0.88 | TIGHT_CLUSTER | 8 |
| `abre el powerpoint que hice` | ~0.030 | ~0.93 | TIGHT_CLUSTER | 8 |
| `instala vlc, después abrelo` | ~0.029 | ~0.83 | TIGHT_CLUSTER | 8 |
| `ayudame con un proyecto` | 0.0325 | 0.61 | LOW (existing) | 16 |
| `hace algo` | <0.020 | — | LOW (existing) | 16 |

The 0.80 cutoff sits midway between the tight cases (min 0.83) and the ambiguous case (0.61) — a 19-point margin in either direction. The 0.025 floor excludes single-list rank-1 results (single-retriever rank-1 contributes 1/61 ≈ 0.0164; corroboration in the other retriever's top-25 lifts top_score above 0.025).

## Details

**1. Metric (predicate, exact form)**
```
is_tight_cluster = (dense_top1 != bm25_top1)
                   AND (top_score >= 0.025)
                   AND (rrf_scores[4] / rrf_scores[0] >= 0.80)
```

**2. Threshold + cap.** Ratio `0.80`, cap `8`. Cap=8 (not 6) because the real competitive cluster is 4–5 tools; cap=8 leaves a 3–4 tool margin for the warm tail (e.g., `installer`/`launcher`/`terminal` adjacent to `package`+`app` in the `vlc` probe). The token cost of 2 extra tool schemas in a 32K-context Gemma 4 E4B window is negligible vs. recall risk.

**3. Band name.** `TIGHT_CLUSTER`. Reject `MEDIUM_DISAGREE` — detection logic is structurally orthogonal to MEDIUM (which requires agreement); conflating them in the name hides that fact from future maintainers.

**4. Three critical tests.**
- (a) `cierra steam` (ES) ≡ `close steam` (EN) → identical TIGHT_CLUSTER + cap=8 + identical subset. Pins language-agnosticism (constraint #6).
- (b) `ayudame con un proyecto` → must stay LOW + cap=16 via the ratio gate (0.61 < 0.80). Pins the genuine-ambiguity boundary.
- (c) `hace algo` → LOW + cap=16 via the corroboration gate (`top_score < 0.025`), **not** via the ratio. Pins the low-signal fallback path so degenerate queries never produce a phantom tight cluster.

**5. Non-obvious risk: BM25-saturation phantom clusters.** In a 65-tool corpus, BM25 frequently hits 0.00 for tools whose tokens don't appear (the table already shows `accessibility=0.00` for `cierra steam`). Multiple ties at BM25=0.00 get arbitrary rank order; if one such tool sits in dense top-10, it inflates `rrf[4]` spuriously and lifts the ratio above 0.80. **Mitigation:** when computing fused ranks, treat tools with raw BM25 score = 0.00 as "not in BM25 list" (one-line guard).

**6. Soft-cap verdict: REJECT.** Under `include while rrf[i]/rrf[0] >= 0.85` the empirical output is 4–6 tools for tight queries and 8–14 for dispersed — overlapping both TIGHT_CLUSTER and LOW outputs. Operator predictability (subset size from `dense_top1`, `bm25_top1`, `top_score`) is satisfied by the hard cap but **not** by soft-cap, which depends on the full `rrf[i]` vector. The user's own decision rule therefore points to hard cap. Accept soft-cap only if a future probe shows optimal cap ∈ {5,7} and cap=8 demonstrably hurts.

**Literature sanity check.** Score-gap-based confidence signals are well-grounded — Shtok et al., *ACM TOIS* 30(2), 2012 (NQC); Cummins, Jose & O'Riordan, *SIGIR 2011* (n(σ_x%)). Result-list truncation is studied by Bahri et al., *SIGIR 2020* (Choppy, arXiv:2004.13012) and Bahri et al., arXiv:2010.09797 (Surprise / EVT), both of which warn that raw scores are *not* calibrated across queries. Bruch, Gai & Ingber, *ACM TOIS* 42(1), 2023 (arXiv:2210.11934) state verbatim: *"we find RRF to be sensitive to its parameters … a tuned RRF generalizes poorly to out-of-domain datasets."* These warnings are real but don't bite here: corpus is fixed (65 tools, frozen YAML), so cross-domain instability is irrelevant; the threshold needs to hold only on this corpus. With RRF k=60 a single ranker's `rrf[4]/rrf[0]` is ≈ 0.94 *by construction* (1/65 ÷ 1/61) — the metric varies meaningfully **only** because cross-list corroboration moves rank-1 up to ~0.032; that's precisely what makes the gate informative here.

## Recommendations

**Ship now (one commit, ~6 LOC in `RouterV2.route()` post-RRF, pre-slice):**

```python
DISAGREE = (dense_top1 != bm25_top1)
TOP_CORROBORATED = (top_score >= 0.025)
CLUSTER_TIGHT = (len(rrf_scores) >= 5
                 and rrf_scores[4] / rrf_scores[0] >= 0.80)
if DISAGREE and TOP_CORROBORATED and CLUSTER_TIGHT:
    band, cap = "TIGHT_CLUSTER", 8
# else: existing HIGH / MEDIUM / LOW logic unchanged
```

Plus the BM25=0.00 guard in the fusion step (treat as not-in-list).

**Tests to add:** the three above, plus a synthetic "two singletons" guard (both top-1s are absent from the other list → `top_score ≈ 0.0164` → LOW).

**Telemetry (cheap, valuable): SHIP IT.** Expose `cluster_size = count(i in [0..15] where rrf[i]/rrf[0] >= 0.80)`. One line; lets a future operator confirm "TIGHT_CLUSTER fires AND cluster_size ∈ [3,6]" is the normal regime, and detects BM25-saturation drift (cluster_size = 12 firing TIGHT_CLUSTER → the phantom-cluster pathology).

**Thresholds that would change this recommendation:**
- A probe where optimal cap = 6 *and* cap=8 demonstrably injects a confusing tool → tighten cap to 6 or revisit soft-cap.
- A probe with `rrf[4]/rrf[0]` in [0.70, 0.80] and optimal cap = 8 → lower ratio threshold to 0.75.
- ≥2 probes where cluster_size telemetry shows >8 → re-examine whether ratio alone is sufficient or add a `stdev(rrf[0..7])` term.

**Out of scope, follow-up sprint:** HIGH-band rank-2..5 divergence (e.g., `pone benson boone` where rank-1 is unambiguous but rank-2..4 diverge). Current cap=4 is safe because rank-1 dominates. Add a `stdev(rrf[1..4])/rrf[0]` telemetry counter; revisit after one sprint of data.

## Caveats

- All thresholds (0.025, 0.80) are calibrated against 5 probes only. Treat them as v1 — recompute after ~50 logged queries with `cluster_size` telemetry in place. The methodology (ratio + corroboration floor) is principled; the exact numerics may shift ±0.05.
- The literature (Bahri 2020/2023, Bruch 2023) warns that fixed score thresholds don't generalize across corpora. They generalize fine *within* a corpus, which is your situation. If the tool set or YAML descriptions are ever re-embedded, **re-run the probes and reconfirm both thresholds** before redeploying.
- The `top_score ≥ 0.025` floor depends on the RRF k=60 arithmetic. If RRF k is ever changed, this floor must be recomputed proportionally (it's ≈ `1/(k+1) + 1/(k+10)`).
- Language-agnosticism (constraint #6) is guaranteed by construction (no text features touched) but should still be asserted by test (a) above to prevent regression from a future "smart" change upstream.

## Completion table

| Plan item | Covered |
|---|---|
| 1. Probe-driven metric derivation | ✅ Details §1, Key Findings table |
| 2. Threshold + cap with justification | ✅ Details §2 |
| 3. Band name | ✅ Details §3 |
| 4. Three critical tests | ✅ Details §4 |
| 5. Non-obvious risk | ✅ Details §5 (BM25 saturation) |
| 6. Soft-cap verdict | ✅ Details §6 (REJECT) |
| Lit sanity check (≤20%) | ✅ Details — Shtok 2012, Cummins 2011, Bahri 2020/2023, Bruch 2023 |
| Bonus: cluster_size telemetry | ✅ Recommendations (SHIP) |
| Bonus: HIGH-band rank-2..5 | ✅ Recommendations (follow-up) |
| All 10 hard constraints satisfied | ✅ Recommendations (commit footprint) |